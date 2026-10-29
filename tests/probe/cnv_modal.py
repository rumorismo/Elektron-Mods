#!/usr/bin/env python3
"""Modal + shared-trig proof for dn-convert 0.13 (8track-engine tasks 2.1/2.2).

Classification ground truth is mod RAM, NOT pixels: the framebuffer proved
too lively for hash equality (background animation/refresh phase changes
lit counts across identical UI states; see cnv_modal.md §1). Resolved once
per boot:
  MODAL_SLOT : -1 = IDLE, else the pending slot (cnv_modal_slot, .run+0xce4)
  STATE[i]   : 0 NATIVE / 1 SYNTH / 2 STASHED (cnv_state, .bss+0x44+4i)
  POPUP      : toast ticks remaining (.bss+0x40)
Resolution: scan mod RAM for the CNV8 projdata descriptor
(magic,size=0x2c,dataptr,fn) -> run_base = fn - AC; cnv_save magic with
zero-like neighbors -> bss_base = addr - 0C. Offsets AC/CE4/0C/44/40 are
convert-0.13 .o layout (m68k-linux-gnu-nm); recompute after any rebuild.

Legs (run from tools/digiemu with its venv; needs emu.*, unicorn):
  sweep    --codes A-B : YES/NO key discovery. Fresh modal per candidate
             panel code; classifies flip / cancel / held-open by RAM.
  contexts              : modal open/cancel/flip on every reachable page
             context; chord-on-0-3 fall-through; plain-VOICE fall-through
             incl. post-cancel stock menu; timeout measurement.
  sharthash             : 976B pattern + 164B params + kit tail identical
             across convert + flip-back; MIDI params byte-identical.
  sustain               : converted slot sounds post-change (sustain_probe
             shape, adapted: YES-confirm, F3-publish verify) + native
             0-3 F3 fetch parity.

UI legs use audio=False (fast); sustain uses audio=True (sequencer clock).
Each leg = ONE Session from the persistent settled snapshot, <60 s wall.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import time

DIGIEMU = '/home/nuke/Documents/Elektron-MODS/tools/digiemu'
sys.path.insert(0, DIGIEMU)
os.chdir(DIGIEMU)

from emu import midi, panel  # noqa: E402
from emu.fwcompare import folder_paths, pixel_diff  # noqa: E402
from emu.session import Session  # noqa: E402

try:
    from unicorn.m68k_const import UC_M68K_REG_A0, UC_M68K_REG_D4  # noqa: E402
except Exception:  # audio-less legs do not need the F3 hook
    UC_M68K_REG_A0 = UC_M68K_REG_D4 = None

PAT_PTR = 0x4138f214
KIT_PTR = 0x4138f220
ACTIVE = 0x41368ce0
TRANSPORT = 0x4138f208
PAT_MUTES_OFF = 0x16108
TRACK_STRUCT = 976
KIT_MIDI_OFF = 0x5CE
MIDI_REC = 164
KIT_TAIL_END = 0x85E
VOICES = 0x80004110
VOICES_LEN = 8 * 32 * 4
F3_REJOIN = 0x40094848
MODRAM_LO = 0x43EC0000
MODRAM_HI = 0x43EC30E8
FOLDER = ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
          'portable/firmware/dn1-1470-bd6df864')
SYX_SHA = 'bd6df8649424d94e422df054452f3fe38d1382386250047601609d7f9128536d'

CARD = (16, 18, 112, 46)  # bank-HUD geometry reused by the modal/toast


def sha(b):
    return hashlib.sha256(bytes(b)).hexdigest()


def u32(m, a):
    b = m.peek(a, 4)
    return struct.unpack('>I', b)[0] if b and len(b) == 4 else None


def fb(m, s):
    return panel.read(m, s.profile.fb_front)


def card_crop(buf):
    x0, y0, x1, y1 = CARD
    return {(x, y) for (x, y) in panel.lit(buf)
            if x0 <= x <= x1 and y0 <= y <= y1}


def resolve_addrs(m):
    """-> (MODAL_SLOT, STATE, POPUP) runtime addresses for convert 0.13."""
    blob = bytes(m.peek(MODRAM_LO, MODRAM_HI - MODRAM_LO))
    magic = struct.pack('>I', 0x434E5638)
    bss = run = None
    off = 0
    while True:
        idx = blob.find(magic, off)
        if idx < 0:
            break
        w = struct.unpack('>6I', blob[idx + 4:idx + 28])
        if all(v <= 2 for v in w):
            bss = MODRAM_LO + idx - 0x0C  # cnv_save @ .bss+0x0c
        elif (w[0] == 0x2C and MODRAM_LO <= w[1] < MODRAM_HI
                and MODRAM_LO <= w[2] < MODRAM_HI):
            run = w[2] - 0xAC  # cnv_proj_loaded @ .run+0xac
        off = idx + 4
    assert bss is not None and run is not None, 'addr resolution failed'
    return run + 0xCE4, bss + 0x44, bss + 0x40  # slot, state, popup


class Run:
    def __init__(self, audio=False):
        self.t0 = time.time()
        self.wall = {}
        paths = folder_paths(FOLDER)
        os.environ.update(paths.env())
        with open(os.path.join(FOLDER, 'firmware.json')) as fh:
            rec = json.load(fh)
        self.syx_name = ((rec.get('release') or {}).get('syx_name')
                         or rec.get('syx_name'))
        t = time.time()
        self.s = Session(paths.gui, paths.syx, audio=audio)
        self.wall['boot'] = round(time.time() - t, 1)
        m = self.s.m
        self.pat = u32(m, PAT_PTR)
        self.kit = u32(m, KIT_PTR)
        assert self.pat and self.kit, 'pattern/kit unreadable'
        h = hashlib.sha256()
        with open(os.path.join(FOLDER, self.syx_name), 'rb') as fh:
            for blk in iter(lambda: fh.read(1 << 20), b''):
                h.update(blk)
        assert h.hexdigest() == SYX_SHA, 'syx sha mismatch'
        self.MODAL_SLOT, self.STATE, self.POPUP = resolve_addrs(m)
        assert u32(m, self.MODAL_SLOT) == 0xFFFFFFFF, 'modal not IDLE at boot'

    def slot(self):
        v = u32(self.s.m, self.MODAL_SLOT)
        return -1 if v == 0xFFFFFFFF else v

    def state(self, i=0):
        return u32(self.s.m, self.STATE + 4 * i)

    def key(self, name, hold=15, after=15):
        self.s.press(self.s.code(name))
        self.s.run_ms(hold)
        self.s.release(self.s.code(name))
        self.s.run_ms(after)

    def ensure_active(self, track, tries=6):
        for _ in range(tries):
            if u32(self.s.m, ACTIVE) == track:
                return
            self.key('MIDI', hold=50, after=50)
        assert u32(self.s.m, ACTIVE) == track, 'select t%d failed' % track

    def settle_fb(self, tries=6, step=150):
        last, stable, buf = None, 0, None
        for _ in range(tries):
            self.s.run_ms(step)
            buf = fb(self.s.m, self.s)
            h = sha(buf) if buf is not None else None
            if h == last:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
            last = h
        return buf

    def fb_hash(self):
        b = fb(self.s.m, self.s)
        return sha(b) if b is not None else None

    def restore_main(self):
        m = self.s.m
        if self.slot() != -1:
            self.key('#14', hold=15, after=200)
        if u32(m, TRANSPORT) == 1:
            self.key('STOP', hold=60, after=100)
            self.key('STOP', hold=60, after=100)
        self.key('NO', hold=15, after=100)
        self.key('NO', hold=15, after=100)
        self.ensure_active(0)
        self.key('T1', hold=15, after=200)
        return self.settle_fb()

    def wait_slot(self, want=None, timeout_ms=1500, step_ms=100):
        """Poll MODAL_SLOT until it equals `want` (or any change from the
        entry value when want is None). Returns the slot. Event latency
        from panel feed to ev_key processing varies with UI cadence, so
        single-shot reads after fixed delays flake."""
        el = 0
        while el < timeout_ms:
            v = self.slot()
            if want is None or v == want:
                return v
            self.s.run_ms(step_ms)
            el += step_ms
        return self.slot()

    def voice_menu(self, tag):
        """Plain VOICE with outcome verification + retries (30 ms presses
        are missed by the key scan depending on phase; 100 ms + retry
        until the framebuffer changes). Returns the menu fb hash."""
        base = sha(self.settle_fb())
        for _ in range(4):
            self.key('VOICE', hold=100, after=200)
            hb = self.settle_fb()
            if sha(hb) != base:
                return sha(hb)
        raise AssertionError('%s: voice menu never opened' % tag)

    def open_modal(self, slot=0, attempts=4):
        """MIDI+VOICE chord with outcome verification + retries.

        The chord races stock's MIDI-press bank retarget (active reads 4
        or 0 during the hold depending on UI-task phase — strict
        alternation at fixed 50 ms holds; cnv_captures §6.2 hit the same
        and retries). Each attempt re-ensures active=4 (MIDI taps flip
        the phase) and polls for the pending slot. Human-held chords do
        not see this aliasing; no firmware change.
        """
        track = 4 + slot
        for _ in range(attempts):
            self.ensure_active(track)
            s = self.s
            s.press(s.code('MIDI'))
            s.run_ms(50)
            s.press(s.code('VOICE'))
            s.run_ms(30)
            s.release(s.code('VOICE'))
            s.run_ms(50)
            s.release(s.code('MIDI'))
            if self.wait_slot(want=slot, timeout_ms=800) == slot:
                return
            s.run_ms(200)
        raise AssertionError('modal did not open after %d chords' % attempts)

    def pat4(self, track=4):
        return bytes(self.s.m.peek(self.pat + track * TRACK_STRUCT,
                                   TRACK_STRUCT))

    def prm4(self, slot=0):
        return bytes(self.s.m.peek(self.kit + KIT_MIDI_OFF
                                   + slot * MIDI_REC, MIDI_REC))

    def close(self):
        self.s.close()
        self.wall['total'] = round(time.time() - self.t0, 1)


def leg_sweep(lo, hi):
    r = Run(audio=False)
    out = {'leg': 'sweep', 'codes': [lo, hi],
           'addrs': {'slot': hex(r.MODAL_SLOT), 'state': hex(r.STATE)},
           'trials': []}
    for code in range(lo, hi + 1):
        t = {'code': code}
        try:
            r.s.code('#%d' % code)
        except Exception:
            t['class'] = 'no-such-key'
            out['trials'].append(t)
            continue
        r.restore_main()
        start_state = r.state(0)
        assert start_state in (0, 2), 'state leak from a previous trial'
        r.open_modal(0)
        r.s.press(code)
        r.s.run_ms(30)
        r.s.release(code)
        # poll for resolution (event latency; modal budget ~2 s from open)
        slot, st = r.slot(), r.state(0)
        el = 0
        while (slot, st) == (0, start_state) and el < 1000:
            r.s.run_ms(100)
            el += 100
            slot, st = r.slot(), r.state(0)
        if slot == 0 and st == start_state:
            t['class'] = 'held-open'
        elif slot == -1 and st == 1 and start_state in (0, 2):
            t['class'] = 'flip'
            # park: flip back via a fresh modal + YES (lands STASHED)
            r.open_modal(0)
            assert r.slot() == 0
            r.key('#13', hold=15, after=200)
            assert r.wait_slot(want=-1, timeout_ms=1000) == -1 \
                and r.state(0) == 2, 'park flip-back failed'
            t['parked_back'] = True
        elif slot == -1 and st == start_state:
            t['class'] = 'cancel'
        else:
            t['class'] = 'UNEXPECTED slot=%s state=%s' % (slot, st)
        if r.slot() != -1:
            r.key('#14', hold=15, after=300)
            t['cleanup_cancel'] = (r.slot() == -1)
        t['end_state'] = r.state(0)
        out['trials'].append(t)
    r.close()
    out['wall'] = r.wall
    return out


def leg_contexts(only=None):
    r = Run(audio=False)
    out = {'leg': 'contexts', 'contexts': []}

    def ctx(name, nav):
        c = {'name': name}
        r.restore_main()
        nav()
        fbc = r.settle_fb()
        hc = sha(fbc)
        # control: stock MIDI-tap alone (bank toggle) on this page
        r.key('MIDI', hold=100, after=200)
        fb_midi = r.settle_fb()
        hmidi = sha(fb_midi)
        c['midi_tap_changes_fb'] = (hmidi != hc)
        c['midi_tap_active'] = u32(r.s.m, ACTIVE)
        r.restore_main()
        nav()
        r.settle_fb()
        # (i) chord on slot 4 opens the modal (RAM truth). NO immediately
        # (modal budget ~2 s; no long settles while open).
        r.open_modal(0)
        c['modal_opens'] = (r.slot() == 0)
        r.s.run_ms(400)  # one redraw cycle; no settle (2 s budget)
        fbm = fb(r.s.m, r.s)
        crop = card_crop(fbm) if fbm is not None else set()
        cropbase = card_crop(fbc) if fbc is not None else set()
        c['modal_card_differs'] = (crop != cropbase)
        c['modal_card_lit'] = len(crop)
        _, c['modal_box'] = pixel_diff(fbc, fbm)
        # (ii) NO cancels with zero state change (RAM gate); stock saw
        # nothing beyond its own MIDI-tap bank toggle (fb recorded, not
        # gated: toggle history differs lone-tap vs chord paths)
        r.key('#14', hold=15, after=200)
        c['cancel_state_idle'] = (r.slot() == -1 and r.state(0) == 0)
        c['cancel_active'] = u32(r.s.m, ACTIVE)
        fbn = r.settle_fb()
        c['cancel_fb'] = (sha(fbn) or '')[:16]
        c['cancel_fb_is_midi_tap'] = (sha(fbn) == hmidi)
        # (iii) chord on slot 0 falls through: no modal (RAM gate);
        # active + fb recorded (stock's own chord handling, if any)
        r.ensure_active(0)
        r.settle_fb()
        s = r.s
        s.press(s.code('MIDI'))
        s.run_ms(50)
        s.press(s.code('VOICE'))
        s.run_ms(30)
        s.release(s.code('VOICE'))
        s.run_ms(50)
        s.release(s.code('MIDI'))
        s.run_ms(300)
        c['chord03_no_modal'] = (r.slot() == -1)
        c['chord03_active'] = u32(r.s.m, ACTIVE)
        hx = r.settle_fb()
        c['chord03_fb'] = (sha(hx) or '')[:16]
        # (iv) plain VOICE falls through -> stock menu opens
        r.restore_main()
        nav()
        r.settle_fb()
        r.ensure_active(0)
        c['voice_opens_menu'] = True
        try:
            c['voice_menu_fb'] = r.voice_menu('iv')[0:16]
        except AssertionError:
            c['voice_opens_menu'] = False
        # (v) chord -> NO -> VOICE still opens the stock menu
        r.restore_main()
        nav()
        r.settle_fb()
        r.ensure_active(4)
        r.open_modal(0)
        r.key('#14', hold=15, after=200)
        c['cancel2_idle'] = (r.slot() == -1)
        r.ensure_active(0)
        c['post_cancel_voice_menu'] = True
        try:
            c['post_cancel_menu_fb'] = r.voice_menu('v')[0:16]
        except AssertionError:
            c['post_cancel_voice_menu'] = False
        c['menu_same_as_plain'] = (c.get('post_cancel_menu_fb') ==
                                   c.get('voice_menu_fb'))
        out['contexts'].append(c)

    if only != 'b':
        ctx('main', lambda: None)
        ctx('voice-menu', lambda: r.key('VOICE', hold=100, after=200))
        ctx('global-settings', lambda: r.key('GLOBAL', hold=100, after=200))
    if only != 'a':
        ctx('midi-bank', lambda: r.ensure_active(4))
        ctx('ptn-menu', lambda: r.key('PTN', hold=100, after=200))
    r.close()
    out['wall'] = r.wall
    return out


def leg_browser():
    """Browser-reachability attempts (double-tap T1 per task 3.1 note,
    FUNC+T1 chord, BANK, SONG). Honest record either way."""
    r = Run(audio=False)
    out = {'leg': 'browser', 'attempts': []}
    r.restore_main()
    h0 = sha(r.settle_fb())

    def attempt(name, fn):
        r.restore_main()
        fn()
        hb = r.settle_fb()
        changed = (sha(hb) != h0)
        a = {'name': name, 'fb_changed': changed,
             'fb': (sha(hb) or '')[:16]}
        if changed:
            r.ensure_active(4)
            try:
                r.open_modal(0)
                a['modal_opens'] = True
                r.key('#14', hold=15, after=200)
                a['cancel_idle'] = (r.slot() == -1)
            except AssertionError as e:
                a['modal_opens'] = False
                a['note'] = str(e)
        # back out of whatever page opened
        r.key('NO', hold=15, after=200)
        r.restore_main()
        a['backed_out'] = True
        out['attempts'].append(a)

    attempt('double-T1', lambda: (r.key('T1', hold=30, after=80),
                                  r.key('T1', hold=30, after=300)))
    s = r.s

    def func_t1():
        s.press(s.code('FUNC'))
        s.run_ms(50)
        s.press(s.code('T1'))
        s.run_ms(30)
        s.release(s.code('T1'))
        s.run_ms(50)
        s.release(s.code('FUNC'))
        s.run_ms(300)
    attempt('FUNC+T1', func_t1)
    attempt('BANK', lambda: r.key('BANK', hold=30, after=300))
    attempt('SONG', lambda: r.key('SONG', hold=30, after=300))
    r.close()
    out['wall'] = r.wall
    return out


def leg_timeout():
    r = Run(audio=False)
    out = {'leg': 'timeout'}
    r.restore_main()
    r.open_modal(0)
    out['modal_opened'] = (r.slot() == 0)
    found = None
    el = 0
    while el < 5000:
        r.s.run_ms(250)
        el += 250
        if r.slot() == -1:
            found = el
            break
    out['auto_cancel_ms'] = found
    out['zero_state_change'] = (r.state(0) == 0)
    out['in_window_1200_3000'] = found is not None and 1200 <= found <= 3000
    r.ensure_active(0)
    try:
        r.voice_menu('post-timeout')
        out['post_timeout_voice_menu'] = True
    except AssertionError:
        out['post_timeout_voice_menu'] = False
    r.close()
    out['wall'] = r.wall
    return out


def leg_sharthash():
    r = Run(audio=False)
    out = {'leg': 'sharthash'}
    r.restore_main()
    r.ensure_active(4)
    p_pre = r.pat4()
    k_pre = r.prm4()
    tail_pre = bytes(r.s.m.peek(r.kit + KIT_MIDI_OFF,
                                KIT_TAIL_END - KIT_MIDI_OFF))
    mute_pre = bytes(r.s.m.peek(r.pat + PAT_MUTES_OFF + 4, 1))
    # program grid steps on the MIDI-live slot (trig content the flip
    # keeps): verified programming — RECORD until the grid screen shows
    # (fb change, retried: short presses can miss the key scan), toggle
    # two steps with struct-bit verification, RECORD off until fb back.
    def step_on(track, step):
        b = r.s.m.peek(r.pat + track * TRACK_STRUCT + 2 * int(step) - 1, 1)
        return bool(b and b[0] & 1)

    hb = sha(r.settle_fb())
    for _ in range(4):
        r.key('RECORD', hold=100, after=200)
        if sha(r.settle_fb()) != hb:
            break
    assert sha(r.settle_fb()) != hb, 'grid-rec never opened'
    for st in ('2', '6'):
        before = step_on(4, st)
        for _ in range(4):
            r.key(st, hold=30, after=100)
            if step_on(4, st) != before:
                break
        assert step_on(4, st) != before, 'step %s did not toggle' % st
    hg = sha(r.settle_fb())
    for _ in range(4):
        r.key('RECORD', hold=100, after=200)
        if sha(r.settle_fb()) != hg:
            break
    p_prog = r.pat4()
    out['program_changed_pat'] = (sha(p_prog) != sha(p_pre))
    # convert via modal YES (label form; sweep used raw #13)
    r.open_modal(0)
    r.key('YES', hold=15, after=600)
    out['yes_flipped'] = (r.slot() == -1 and r.state(0) == 1)
    p_conv = r.pat4()
    k_conv = r.prm4()
    out['conv_pat_same'] = (sha(p_conv) == sha(p_prog))
    out['conv_prm_live_same'] = (sha(k_conv) == sha(k_pre))
    out['pat_sha'] = sha(p_prog)[:16]
    # flip back via YES on the RESTORE card
    r.open_modal(0)
    r.key('YES', hold=15, after=600)
    out['yes_restored'] = (r.slot() == -1 and r.state(0) == 2)
    p_back = r.pat4()
    k_back = r.prm4()
    tail_back = bytes(r.s.m.peek(r.kit + KIT_MIDI_OFF,
                                 KIT_TAIL_END - KIT_MIDI_OFF))
    mute_back = bytes(r.s.m.peek(r.pat + PAT_MUTES_OFF + 4, 1))
    out['back_pat_same'] = (sha(p_back) == sha(p_prog))
    out['back_prm_identical'] = (k_back == k_pre)
    out['back_tail_same'] = (sha(tail_back) == sha(tail_pre))
    out['back_mute_same'] = (mute_back == mute_pre)
    out['prm_sha'] = sha(k_pre)[:16]
    out['tail_sha'] = sha(tail_pre)[:16]
    r.close()
    out['wall'] = r.wall
    return out


def energy(raw):
    n = len(raw) // 4
    vals = struct.unpack('>' + 'i' * n, raw)
    return max(abs(v) for v in vals), sum(abs(v) for v in vals) // max(n, 1)


def leg_sustain():
    r = Run(audio=True)
    s = r.s
    m = s.m
    out = {'leg': 'sustain'}
    fires = []
    s.at(F3_REJOIN, lambda uc, a, sz, d: fires.append((
        round(s.ms, 1), uc.reg_read(UC_M68K_REG_D4) // 326
        if uc.reg_read(UC_M68K_REG_D4) % 326 == 0 else -1,
        '0x%08x' % uc.reg_read(UC_M68K_REG_A0))))
    tx = midi.MidiOut(sink=bytearray().extend)
    tx.install(s.m)
    tx.attach(s.m, s.ips)
    s.sources = s.sources + (tx,)

    def key(name, hold=15, after=15):
        s.press(s.code(name))
        s.run_ms(hold)
        s.release(s.code(name))
        s.run_ms(after)

    def step_on(track, step):
        b = m.peek(r.pat + track * 976 + 2 * int(step) - 1, 1)
        return bool(b and b[0] & 1)

    def program(track, select):
        if select:
            key(select)
            assert u32(m, ACTIVE) == track
        key('RECORD')
        for st in ('2', '6', '10', '14'):
            key(st)
            if not step_on(track, st):
                key(st)
            assert step_on(track, st), (track, st)
        key('RECORD')

    program(0, 'T1')
    program(1, 'T2')
    program(2, 'T3')
    program(3, 'T4')
    r.open_modal(0)
    key('YES', hold=15, after=600)
    assert r.slot() == -1 and r.state(0) == 1, 'YES did not flip'
    out['yes_flipped'] = True
    r.ensure_active(4)
    program(4, None)
    for tr in (0, 1, 2, 3):
        m.poke(r.pat + PAT_MUTES_OFF + tr, bytes([1]))
    t = time.time()
    key('PLAY', hold=60, after=100)
    series = []
    for _ in range(8):
        s.run_ms(500)
        mx, av = energy(bytes(m.peek(VOICES, VOICES_LEN)))
        series.append({'ms': round(s.ms, 1), 'max': mx, 'avg': av})
    play_wall = round(time.time() - t, 1)
    key('STOP', hold=60, after=100)
    key('STOP', hold=60, after=100)
    t4a0 = [a for _, tr, a in fires if tr == 4]
    a0s = sorted(set(t4a0))
    inram = [a for a in a0s
             if MODRAM_LO <= int(a, 16) < MODRAM_HI]
    bytrack = {}
    for _, tr, _ in fires:
        bytrack[tr] = bytrack.get(tr, 0) + 1
    kit = r.kit
    native_ok = True
    for t in (0, 1, 2, 3):
        want = '0x%08x' % (kit + 0x18 + 326 * t)
        got = sorted({a for _, tr, a in fires if tr == t})
        if got != [want]:
            native_ok = False
        out['native_t%d' % t] = {'want': want, 'got': got}
    bss_nonzero = None
    if t4a0:
        bss = bytes(m.peek(int(t4a0[0], 16), 326))
        bss_nonzero = sum(1 for x in bss if x != 0)
    live_max = max(p['max'] for p in series)
    out.update({
        't4_hits': len(t4a0), 't4_a0s': a0s, 't4_in_modram': inram,
        'f3_by_track': bytrack, 'native_fetch_parity': native_ok,
        'bss_nonzero': bss_nonzero, 'series_max': live_max,
        'series': series, 'play_wall': play_wall,
        'pass': bool(inram) and (bss_nonzero or 0) > 0 and live_max > 0,
    })
    r.close()
    out['wall'] = r.wall
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--leg', choices=('sweep', 'contexts', 'browser',
                                      'timeout', 'sharthash', 'sustain'),
                    required=True)
    ap.add_argument('--codes', default=None,
                    help='lo-hi for sweep (e.g. 1-12); a|b for contexts')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    if args.leg == 'sweep':
        lo, hi = (int(x) for x in args.codes.split('-'))
        rep = leg_sweep(lo, hi)
    elif args.leg == 'contexts':
        rep = leg_contexts(args.codes)
    elif args.leg == 'browser':
        rep = leg_browser()
    elif args.leg == 'timeout':
        rep = leg_timeout()
    elif args.leg == 'sharthash':
        rep = leg_sharthash()
    else:
        rep = leg_sustain()
    with open(args.out, 'w') as fh:
        json.dump(rep, fh, indent=1, default=str)
    print('%s wall=%s' % (args.leg, rep.get('wall')))
    if args.leg == 'sweep':
        for t in rep['trials']:
            print('code=%2d class=%-28s end_state=%s' % (
                t['code'], t.get('class'), t.get('end_state')))


if __name__ == '__main__':
    main()
