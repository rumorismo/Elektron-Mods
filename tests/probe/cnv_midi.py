#!/usr/bin/env python3
"""MIDI coexistence proof for dn-convert 0.23 (8track-engine tasks 4.1+4.2).

Coupled lane: same capture setup, one harness, per-run single Session.

  4.1  Bank-A MIDI byte-identity with conversions active. DIN-byte sink
       windows for (a) stock baseline Bank-A MIDI tracks playing, (b) the
       same pattern with conversions active (all-four converted, mixed
       2+2), (c) flip / flip-back transition windows. Assert (b),(c)
       byte-identical to (a). CLOCK SEND off for all runs (factory
       default; evidenced by zero 0xF8 in every play window).
  4.2  Converted channel preserve. Hunt the CHAN store (MID SYN1 page,
       encoder A) with a control-subtracted write hook, set track 5 to a
       non-default channel, convert, and check the external bytes + voice
       path. Flip back and re-check the stored channel. If the converted
       synth emits no external bytes, report exactly that (BLOCKED).

Snapshots: FRESH COPIES under /tmp/opencode/cnv_midi_work/ (persistent
snapshots stay pristine; conversions are unsaved RAM-only state anyway).
Audio stays ON for sequencer legs (the step loop only advances on the
audio clock); the hunt leg uses audio=False (fast).

Runs (each = ONE Session, wall budget <60 s target, reported):
  r1 stock baseline:   program MIDI tracks 4-7, PLAY fixed window, capture
  r2 all-four:         program 4-7, convert slots 0-3, PLAY (poll converted
                       F3 publish), capture
  r3 mixed+flips:      program 4-7, convert slots 0,1, PLAY mixed, flip back
                       slot 1 (transition window), flip back slot 0
                       (transition window), PLAY restored, capture
  r4 chan hunt:        stock copy, audio=False, MID page track 5, encoder
                       sweeps vs idle control, kit/pattern diffs
  r5 chan proof:       modded copy, set CHAN=5 via --chan ADDR,SIZE, convert
                       slot 1, PLAY, flip back, re-check

Compare mode judges identity (r1 vs r2 vs r3 windows + kit tails).

Run from tools/digiemu with its venv (needs emu.*, unicorn).
"""
import argparse
import collections
import hashlib
import json
import os
import shutil
import struct
import sys
import time

DIGIEMU = '/home/nuke/Documents/Elektron-MODS/tools/digiemu'
sys.path.insert(0, DIGIEMU)
os.chdir(DIGIEMU)

from unicorn.m68k_const import UC_M68K_REG_A0, UC_M68K_REG_D4  # noqa: E402
from unicorn import UC_HOOK_MEM_WRITE  # noqa: E402

from emu import midi, panel  # noqa: E402
from emu.fwcompare import folder_paths  # noqa: E402
from emu.session import Session  # noqa: E402

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
MODRAM_HI = 0x43F00000
REALTIME = {0xF8, 0xFA, 0xFB, 0xFC, 0xFE, 0xFF}

STOCK_SRC = ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
             'portable/firmware/dn1-1.44-d4f200d0')
MOD_SRC = ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
           'portable/firmware/dn1-1486-71493c78')
STOCK_SHA = 'd4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659'
MOD_SHA = '71493c7805566e40c65a801c23dc7c1b1c5c0af17622e85e84a2cfd3e4e2adab'
MOD_SYX = '/home/nuke/Documents/Elektron-MODS/firmware/test-cnv23.syx'
WORK = '/tmp/opencode/cnv_midi_work'

STEPS = ('2', '6', '10', '14')
PLAY_FIXED_MS = 2000
PLAY_MIN_MS = 1500
PLAY_CAP_MS = 7000
SETTLE_CAP_MS = 1500


def sha(b):
    return hashlib.sha256(bytes(b)).hexdigest()


def u32(m, a):
    b = m.peek(a, 4)
    return struct.unpack('>I', b)[0] if b and len(b) == 4 else None


def fb_hash(m, s):
    return sha(bytes(panel.read(m, s.profile.fb_front)))


def copy_snapshots():
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    out = {}
    for name, src in (('stock', STOCK_SRC), ('mod', MOD_SRC)):
        dst = os.path.join(WORK, os.path.basename(src))
        shutil.copytree(src, dst)
        out[name] = dst
    return out


def check_syx(folder, expect):
    paths = folder_paths(folder)
    with open(os.path.join(folder, 'firmware.json')) as fh:
        rec = json.load(fh)
    syx_name = ((rec.get('release') or {}).get('syx_name')
                or rec.get('syx_name'))
    h = hashlib.sha256()
    with open(os.path.join(folder, syx_name), 'rb') as fh:
        for blk in iter(lambda: fh.read(1 << 20), b''):
            h.update(blk)
    assert h.hexdigest() == expect, 'syx sha mismatch in %s' % folder
    return syx_name


class Run:
    def __init__(self, folder, syx_sha, audio=True):
        self.t0 = time.time()
        self.wall = {}
        self.log = []
        paths = folder_paths(folder)
        os.environ.update(paths.env())
        self.folder = folder
        self.snapshot_id = os.path.basename(folder.rstrip('/'))
        self.syx_name = check_syx(folder, syx_sha)
        t = time.time()
        self.s = Session(paths.gui, paths.syx, audio=audio)
        self.wall['boot'] = round(time.time() - t, 1)
        self.fires = []
        self.s.at(F3_REJOIN, self._on_f3)
        self.midibuf = bytearray()
        tx = midi.MidiOut(sink=self.midibuf.extend)
        tx.install(self.s.m)
        tx.attach(self.s.m, self.s.ips)
        self.s.sources = self.s.sources + (tx,)
        self.pat = u32(self.s.m, PAT_PTR)
        self.kit = u32(self.s.m, KIT_PTR)
        assert self.pat and self.kit, 'pattern/kit pointers unreadable'
        self.marks = {}
        self.log.append('boot snapshot=%s pat=0x%08x kit=0x%08x' % (
            self.snapshot_id, self.pat, self.kit))

    def _on_f3(self, uc, addr, size, data):
        try:
            d4 = uc.reg_read(UC_M68K_REG_D4)
            a0 = uc.reg_read(UC_M68K_REG_A0)
        except Exception:
            return
        track = d4 // 326 if d4 % 326 == 0 else -1
        self.fires.append((round(self.s.ms, 1), track, a0))

    def key(self, name, hold=15, after=15):
        self.s.press(self.s.code(name))
        self.s.run_ms(hold)
        self.s.release(self.s.code(name))
        self.s.run_ms(after)

    def mark(self, name):
        self.marks[name] = (round(self.s.ms, 1), len(self.midibuf))

    def stable_fb(self, cap_ms=SETTLE_CAP_MS, step=150, need=3):
        last, n, el = None, 0, 0
        while el < cap_ms:
            self.s.run_ms(step)
            el += step
            h = fb_hash(self.s.m, self.s)
            if h == last:
                n += 1
                if n >= need:
                    return h
            else:
                n = 0
            last = h
        return fb_hash(self.s.m, self.s)

    # -- selection (bank-aware; converted T-divert lands the track) -----
    def midi_to_bank(self, midi, tries=4):
        m = self.s.m
        want = 1 if midi else 0
        for _ in range(tries):
            if (u32(m, ACTIVE) or 0) // 4 == want:
                return True
            self.key('MIDI', hold=120, after=300)
            el = 0
            while el < 400 and (u32(m, ACTIVE) or 0) // 4 != want:
                self.s.run_ms(100)
                el += 100
        return (u32(m, ACTIVE) or 0) // 4 == want

    def select_track(self, track, tries=5):
        """T-select on the right bank. Returns ACTIVE (may be the mirror
        when B0 diverts a converted slot -- caller checks)."""
        m = self.s.m
        slot = track % 4
        for _ in range(tries):
            cur = u32(m, ACTIVE)
            if cur == track:
                return cur
            if (cur or 0) // 4 != track // 4:
                if not self.midi_to_bank(track >= 4):
                    continue
            else:
                self.key('T%d' % (slot + 1), hold=120, after=120)
                el = 0
                while el < 400 and u32(m, ACTIVE) == cur:
                    self.s.run_ms(100)
                    el += 100
        return u32(m, ACTIVE)

    # -- programming ----------------------------------------------------
    def _step_on(self, track, step):
        b = self.s.m.peek(self.pat + track * TRACK_STRUCT + 2 * int(step)
                          - 1, 1)
        return bool(b and b[0] & 1)

    def program(self, track, steps=STEPS):
        t = time.time()
        act = self.select_track(track)
        assert act == track, 'select t%d: active=%s (divert?)' % (track,
                                                                  act)
        self.key('RECORD')
        for st in steps:
            self.key(st)
            if not self._step_on(track, st):
                self.key(st)
            assert self._step_on(track, st), 'step %s t%d stuck OFF' % (
                st, track)
        self.key('RECORD')
        self.wall['program_t%d' % track] = round(time.time() - t, 1)
        self.log.append('program t%d steps=%s' % (track, ','.join(steps)))

    # -- modal chord (fb-verified; outcome verified by later PLAY) ---
    # NOTE audio=True legs: every emu-ms costs ~8x wall. No stability
    # loops here -- single fb reads around fixed short settles; the PLAY
    # F3 window outcome-verifies each flip.
    def chord(self, track):
        """MIDI+VOICE with active==track at press time. Returns True iff
        the modal card fb appeared."""
        t = time.time()
        act = self.select_track(track)
        if act != track:
            if not self.midi_to_bank(track >= 4):
                self.wall['chord_t%d' % track] = round(time.time() - t, 1)
                return False
            el = 0
            while el < 400 and u32(self.s.m, ACTIVE) != track:
                self.s.run_ms(100)
                el += 100
            if u32(self.s.m, ACTIVE) != track:
                self.log.append('chord t%d unreachable (active=%s)' % (
                    track, u32(self.s.m, ACTIVE)))
                self.wall['chord_t%d' % track] = round(time.time() - t, 1)
                return False
        h0 = fb_hash(self.s.m, self.s)
        ok = False
        for _ in range(2):
            self.s.press(self.s.code('MIDI'))
            self.s.run_ms(50)
            self.s.press(self.s.code('VOICE'))
            self.s.run_ms(30)
            self.s.release(self.s.code('VOICE'))
            self.s.run_ms(50)
            self.s.release(self.s.code('MIDI'))
            self.s.run_ms(300)
            if fb_hash(self.s.m, self.s) != h0:
                ok = True
                break
        self.wall['chord_t%d' % track] = round(time.time() - t, 1)
        self.log.append('chord t%d card=%s active=%s' % (
            track, ok, u32(self.s.m, ACTIVE)))
        return ok

    def yes(self):
        t = time.time()
        h0 = fb_hash(self.s.m, self.s)
        self.key('YES', hold=15, after=150)
        self.s.run_ms(300)
        changed = fb_hash(self.s.m, self.s) != h0
        self.wall['yes'] = round(self.wall.get('yes', 0)
                                 + (time.time() - t), 1)
        self.log.append('YES fb_changed=%s' % changed)
        return changed

    # -- transport --------------------------------------------------------
    def play_fixed(self, ms=PLAY_FIXED_MS):
        t = time.time()
        self.key('PLAY', hold=60, after=100)
        assert u32(self.s.m, TRANSPORT) == 1, 'transport did not start'
        self.mark('play_start')
        self.s.run_ms(ms)
        self.mark('play_end')
        self.wall['play'] = round(self.wall.get('play', 0)
                                  + (time.time() - t), 1)
        self.log.append('play fixed emu=%dms fires=%d' % (ms, len(self.fires)))

    def play_until(self, need, min_ms=PLAY_MIN_MS, cap_ms=PLAY_CAP_MS):
        t = time.time()
        self.key('PLAY', hold=60, after=100)
        assert u32(self.s.m, TRANSPORT) == 1, 'transport did not start'
        self.mark('play_start')
        el = 0
        while el < cap_ms:
            self.s.run_ms(250)
            el += 250
            if el >= min_ms and need(self.fires):
                break
        self.mark('play_end')
        self.wall['play'] = round(self.wall.get('play', 0)
                                  + (time.time() - t), 1)
        self.log.append('play emu=%dms fires=%d' % (el, len(self.fires)))
        return el

    def stop_settle(self):
        t = time.time()
        self.key('STOP', hold=60, after=100)
        self.key('STOP', hold=60, after=100)
        self.mark('settled')
        self.s.run_ms(500)
        self.wall['stop_settle'] = round(self.wall.get('stop_settle', 0)
                                         + (time.time() - t), 1)
        self.log.append('stop transport=%s' % u32(self.s.m, TRANSPORT))

    # -- captures -----------------------------------------------------------
    def capture(self, tag):
        m = self.s.m
        tail = bytes(m.peek(self.kit + KIT_MIDI_OFF,
                            KIT_TAIL_END - KIT_MIDI_OFF))
        vbuf = bytes(m.peek(VOICES, VOICES_LEN))
        return {
            'tag': tag,
            'ms': round(self.s.ms, 1),
            'transport': u32(m, TRANSPORT),
            'active': u32(m, ACTIVE),
            'fb_sha': fb_hash(m, self.s),
            'pat_sha': [sha(bytes(m.peek(self.pat + i * TRACK_STRUCT,
                                         TRACK_STRUCT))) for i in range(8)],
            'kit_tail_sha': sha(tail),
            'kit_tail_hex': tail.hex(),
            'mutes_pat_hex': bytes(m.peek(self.pat + PAT_MUTES_OFF, 8)).hex(),
            'mutes_audio_hw': m.peek(0x41392f30, 2).hex(),
            'mutes_midi_hw': m.peek(0x419c5b0c, 4).hex(),
            'voices_sha': sha(vbuf),
        }

    def midi_window(self, a, b):
        la, lb = self.marks[a][1], self.marks[b][1]
        raw = bytes(self.midibuf[la:lb])
        nonrt = bytes(x for x in raw if x not in REALTIME)
        rt = len(raw) - len(nonrt)
        f8 = sum(1 for x in raw if x == 0xF8)
        return {'nonrt_hex': nonrt.hex(), 'nonrt_len': len(nonrt),
                'rt_count': rt, 'clock_f8': f8, 'raw_len': len(raw)}

    def f3_window(self, a, b, tracks=None):
        lo, hi = self.marks[a][0], self.marks[b][0]
        hits = [(ms, t, '0x%08x' % v) for ms, t, v in self.fires
                if lo <= ms <= hi and (tracks is None or t in tracks)]
        return {'hits': hits, 'n': len(hits)}

    def close(self):
        self.s.close()
        self.wall['total'] = round(time.time() - self.t0, 1)


def converted_hits(f3, tracks):
    mod = [h for h in f3['hits']
           if h[1] in tracks and MODRAM_LO <= int(h[2], 16) < MODRAM_HI]
    return mod


def leg_r1(folder):
    r = Run(folder, STOCK_SHA, audio=True)
    for t in (4, 5, 6, 7):
        r.program(t)
    pre = r.capture('pre_play')
    r.play_fixed()
    r.stop_settle()
    final = r.capture('settled')
    final['pre_play'] = pre
    final['midi_play'] = r.midi_window('play_start', 'play_end')
    final['f3_play'] = r.f3_window('play_start', 'play_end')
    out = pack('r1_stock', r, final)
    r.close()
    out['wall'] = r.wall
    out['log'] = r.log
    return out


def leg_r2(folder):
    r = Run(folder, MOD_SHA, audio=True)
    for t in (4, 5, 6, 7):
        r.program(t)
    cards = []
    for slot in range(4):
        ok = r.chord(4 + slot)
        cards.append(ok)
        assert ok, 'modal card did not open for slot %d' % slot
        r.yes()
    r.play_until(lambda f: all(
        sum(1 for _, t, _ in f if t == i) >= 1 for i in (4, 5, 6, 7)))
    r.stop_settle()
    final = r.capture('settled')
    final['modal_cards'] = cards
    final['midi_play'] = r.midi_window('play_start', 'play_end')
    final['f3_play'] = r.f3_window('play_start', 'play_end')
    final['converted_pub'] = converted_hits(final['f3_play'], (4, 5, 6, 7))
    out = pack('r2_all4', r, final)
    r.close()
    out['wall'] = r.wall
    out['log'] = r.log
    return out


def leg_r3a(folder):
    """Mixed 2+2 play (modded, audio=True). Program 4-7, convert slots
    0,1, PLAY with the mixed bank."""
    r = Run(folder, MOD_SHA, audio=True)
    for t in (4, 5, 6, 7):
        r.program(t)
    for slot in (0, 1):
        ok = r.chord(4 + slot)
        assert ok, 'modal card did not open for slot %d' % slot
        r.yes()
    r.play_until(lambda f: all(
        sum(1 for _, t, _ in f if t == i) >= 1 for i in (4, 5)))
    r.stop_settle()
    final = r.capture('mixed_settled')
    final['midi_mixed_play'] = r.midi_window('play_start', 'play_end')
    final['f3_mixed_play'] = r.f3_window('play_start', 'play_end')
    final['converted_pub'] = converted_hits(final['f3_mixed_play'], (4, 5))
    out = pack('r3a_mixed', r, final)
    r.close()
    out['wall'] = r.wall
    out['log'] = r.log
    return out


def leg_r3b(folder):
    """Flip/flip-back transitions + post-flipback play (modded, audio=True).

    UI law (probed 2026-10-28, see evidence md): only the MIDI-bank
    memorized slot is flip-back-reachable per session -- T-taps on a
    converted slot never change ACTIVE (B0 divert does not deliver the
    converted track), and toggles only recall bank memory. So: convert
    slots 0,1 (transition windows), PLAY mixed, flip back slot 1 (the
    memorized slot; transition window), PLAY again with slot 0 still
    converted. Slot 0 is left converted (RAM-only, dies with the session;
    the snapshot copy is untouched).
    """
    r = Run(folder, MOD_SHA, audio=True)
    for t in (4, 5, 6, 7):
        r.program(t)
    trans = []
    for slot in (0, 1):
        ok = r.chord(4 + slot)
        assert ok, 'modal card did not open for slot %d' % slot
        r.mark('conv%d_start' % slot)
        r.yes()
        r.mark('conv%d_end' % slot)
        trans.append({'slot': slot, 'dir': 'convert',
                      'midi': r.midi_window('conv%d_start' % slot,
                                            'conv%d_end' % slot)})
    r.play_until(lambda f: all(
        sum(1 for _, t, _ in f if t == i) >= 1 for i in (4, 5)))
    r.stop_settle()
    mixed = {'midi': r.midi_window('play_start', 'play_end'),
             'f3': r.f3_window('play_start', 'play_end'),
             'tail': r.capture('mixed_settled')}
    ok = r.chord(5)
    assert ok, 'restore card did not open for slot 1'
    r.mark('flip1_start')
    r.yes()
    r.mark('flip1_end')
    trans.append({'slot': 1, 'dir': 'flipback',
                  'midi': r.midi_window('flip1_start', 'flip1_end')})
    r.play_until(lambda f: sum(1 for _, t, _ in f if t == 4) >= 1)
    r.stop_settle()
    final = r.capture('postflip1_settled')
    final['mixed'] = mixed
    final['transitions'] = trans
    final['midi_postflip1_play'] = r.midi_window('play_start', 'play_end')
    final['f3_postflip1_play'] = r.f3_window('play_start', 'play_end')
    out = pack('r3b_flips', r, final)
    r.close()
    out['wall'] = r.wall
    out['log'] = r.log
    return out


def leg_r4(folder):
    """CHAN store hunt (stock, audio=False). MID page track 5, encoder A
    sweeps vs an idle control window."""
    r = Run(folder, STOCK_SHA, audio=False)
    m = r.s.m
    assert r.select_track(5) == 5, 'cannot select track 5'
    r.key('SYN1', hold=120, after=500)
    h_page = fb_hash(m, r.s)
    pre_prm = bytes(m.peek(r.kit + KIT_MIDI_OFF + MIDI_REC, MIDI_REC))
    pre_pat = bytes(m.peek(r.pat + 5 * TRACK_STRUCT, TRACK_STRUCT))

    idle_addrs = set()

    def hook_idle(uc, access, address, size, value, data):
        idle_addrs.add(address)
        return True

    h = m.uc.hook_add(UC_HOOK_MEM_WRITE, hook_idle)
    r.s.run_ms(3000)
    m.uc.hook_del(h)

    turn_vals = collections.defaultdict(list)

    def hook_turn(uc, access, address, size, value, data):
        if len(turn_vals) < 30000:
            turn_vals[address].append((size, value))
        return True

    h = m.uc.hook_add(UC_HOOK_MEM_WRITE, hook_turn)
    for _ in range(6):
        r.s.turn(1, -2, 300)
        r.s.run_ms(200)
    for _ in range(12):
        r.s.turn(1, 2, 300)
        r.s.run_ms(200)
    for _ in range(6):
        r.s.turn(1, -2, 300)
        r.s.run_ms(200)
    m.uc.hook_del(h)
    h_turn = fb_hash(m, r.s)
    post_prm = bytes(m.peek(r.kit + KIT_MIDI_OFF + MIDI_REC, MIDI_REC))
    post_pat = bytes(m.peek(r.pat + 5 * TRACK_STRUCT, TRACK_STRUCT))

    cands = []
    for a, vs in turn_vals.items():
        if a in idle_addrs or len(vs) > 200:
            continue
        sizes = set(s for s, _ in vs)
        if sizes not in ({1}, {2}, {4}):
            continue
        vals = [v & 0xFF if s == 1 else v for s, v in vs]
        if max(vals) > 64 or min(vals) < 0:
            continue
        if max(vals) - min(vals) >= 1:
            cands.append({'addr': '0x%08x' % a, 'n': len(vs),
                          'sizes': sorted(sizes),
                          'min': min(vals), 'max': max(vals),
                          'first': vals[:8], 'last': vals[-8:]})
    cands.sort(key=lambda c: -c['n'])
    out = pack('r4_hunt', r, {
        'page_fb': h_page[:16],
        'post_turn_fb': h_turn[:16],
        'fb_changed': h_page != h_turn,
        'kit164_same': post_prm == pre_prm,
        'kit164_sha': sha(post_prm)[:16],
        'pat976_same': post_pat == pre_pat,
        'n_turn_addrs': len(turn_vals),
        'n_idle_addrs': len(idle_addrs),
        'candidates': cands[:25],
    })
    r.close()
    out['wall'] = r.wall
    out['log'] = r.log
    return out


def leg_r5(folder, chan_addr, chan_size):
    """Channel preserve (modded, audio=True). Program 4-7, open the MID
    page on track 5, attempt CHAN=5, convert slot 1, PLAY (DIN + F3 +
    channel peeks), flip back, re-check. The R4 hunt found the live cell;
    this leg tests whether convert/flipback preserve it."""
    r = Run(folder, MOD_SHA, audio=True)
    m = r.s.m
    for t in (4, 5, 6, 7):
        r.program(t)
    assert r.select_track(5) == 5, 'cannot select track 5'
    h_main = fb_hash(m, r.s)
    r.key('SYN1', hold=120, after=500)
    if fb_hash(m, r.s) == h_main:
        r.key('SYN1', hold=120, after=500)
    page_open = fb_hash(m, r.s) != h_main
    pngdir = '/tmp/opencode/cnv_m_png'
    try:
        os.makedirs(pngdir, exist_ok=True)
        panel.write_png(panel.read(m, r.s.profile.fb_front),
                        os.path.join(pngdir, 'r5_midpage.png'), scale=4)
        png_saved = True
    except Exception:
        png_saved = False

    def read_chan():
        b = m.peek(chan_addr, chan_size)
        return int.from_bytes(bytes(b), 'big')

    def window():
        return bytes(m.peek(chan_addr - 32, 96)).hex()

    v0 = read_chan()
    w0 = window()
    # Turn-liveness gate (per-session input flake class): the set phase
    # is meaningless if turns never land. Probe with 4 turns; abort fast
    # unless the cell or the fb moves.
    h_gate0 = fb_hash(m, r.s)
    for _ in range(4):
        r.s.turn(1, 2, 300)
        r.s.run_ms(200)
    gate_live = (read_chan() != v0 or fb_hash(m, r.s) != h_gate0)
    if not gate_live:
        r.close()
        return {'scenario': 'r5_aborted', 'snapshot_id': 'n/a',
                'folder': folder, 'syx': MOD_SHA, 'halted': None,
                'reason': 'turn-dead session: 4 encoder turns moved '
                          'neither the candidate cell nor the framebuffer',
                'cell': '0x%08x' % chan_addr, 'cell_value': v0,
                'page_open': page_open, 'png_saved': png_saved,
                'wall': r.wall, 'log': r.log}
    # Hunt (r4) showed CW turns increase this cell; storage reads as the UI
    # value (0=OFF, 1..16). Bounded probe + step toward 5 (audio=True legs
    # cost ~8x wall per emu-ms, so no long turn loops).
    target = 5
    v_set = v0

    def step(d, n=2):
        for _ in range(n):
            r.s.turn(1, d, 300)
            r.s.run_ms(200)
        return read_chan()

    v1 = step(2)
    up = 1 if v1 > v0 else (-1 if v1 < v0 else 0)
    if up == 0:
        v1 = step(-2)
        up = 1 if v1 > v0 else (-1 if v1 < v0 else 0)
    if up != 0:
        for _ in range(6):
            if (v1 - target) * up >= 0:
                break
            v1 = step(2 * up, n=1)
    v_set = read_chan()
    set_ok = (v_set == target)
    try:
        if png_saved:
            panel.write_png(panel.read(m, r.s.profile.fb_front),
                            os.path.join(pngdir, 'r5_midpage_post.png'),
                            scale=4)
    except Exception:
        pass
    r.key('TRIG', hold=120, after=300)
    pre_prm = bytes(m.peek(r.kit + KIT_MIDI_OFF + MIDI_REC, MIDI_REC))
    ok = r.chord(5)
    assert ok, 'modal card did not open for slot 1'
    r.yes()
    v_preplay = read_chan()
    r.play_until(lambda f: sum(1 for _, t, _ in f if t == 5) >= 1)
    conv = {'midi': r.midi_window('play_start', 'play_end'),
            'f3': r.f3_window('play_start', 'play_end', tracks=(5,))}
    conv_pub = converted_hits(conv['f3'], (5,))
    v_conv = read_chan()
    r.stop_settle()
    v_settled = read_chan()
    ok2 = r.chord(5)
    assert ok2, 'restore card did not open for slot 1'
    r.yes()
    v_back = read_chan()
    # follow test: does the cell track the selected track?
    r.select_track(6)
    v_follow = read_chan()
    # No restored play: the empty-DIN and F3-silence halves are covered by
    # r3b (slot-1 flipback -> zero track-5 F3, mute restore, tail); this
    # leg's unique content is the channel-store set/preserve across convert.
    r.stop_settle()
    final = r.capture('settled')
    final['chan'] = {'addr': '0x%08x' % chan_addr, 'size': chan_size,
                     'factory': v0, 'set': v_set, 'set_ok': set_ok,
                     'page_open': page_open,
                     'pre_play': v_preplay,
                     'during_convert': v_conv, 'settled': v_settled,
                     'after_flipback': v_back, 'follow_track6': v_follow,
                     'window_pre': w0, 'window_post': window(),
                     'preserved': v_back == target and v_set == target}
    final['kit164_pre_hex'] = pre_prm.hex()
    final['midi_conv_play'] = conv['midi']
    final['f3_conv_play'] = conv['f3']
    final['conv_pub'] = conv_pub
    out = pack('r5_chan', r, final)
    r.close()
    out['wall'] = r.wall
    out['log'] = r.log
    return out


def pack(scenario, r, final):
    return {'scenario': scenario, 'snapshot_id': r.snapshot_id,
            'folder': r.folder, 'syx': r.syx_name,
            'marks': r.marks, 'halted': r.s.halted, 'final': final}


def compare(r1, r2, r3a, r3b):
    v = {}
    base = r1['final']['midi_play']
    tails = {'r1': r1['final']['kit_tail_sha']}
    ok_all, rows = True, {}
    for name, win in (('r2_all4', r2['final']['midi_play']),
                      ('r3a_mixed', r3a['final']['midi_mixed_play']),
                      ('r3b_mixed', r3b['final']['mixed']['midi']),
                      ('r3b_postflip1', r3b['final']['midi_postflip1_play'])):
        same = win['nonrt_hex'] == base['nonrt_hex']
        rows[name] = {'same_as_baseline': same,
                      'nonrt_len': win['nonrt_len'],
                      'rt_count': win['rt_count'],
                      'clock_f8': win['clock_f8']}
        ok_all = ok_all and same
    v['din_identity'] = {'pass': ok_all, 'baseline': {
        'nonrt_len': base['nonrt_len'], 'rt_count': base['rt_count'],
        'clock_f8': base['clock_f8'],
        'nonrt_hex': base['nonrt_hex'][:64]}, 'rows': rows}
    tails.update({'r2': r2['final']['kit_tail_sha'],
                  'r3a_mixed': r3a['final']['kit_tail_sha'],
                  'r3b_mixed': r3b['final']['mixed']['tail'][
                      'kit_tail_sha'],
                  'r3b_postflip1': r3b['final']['kit_tail_sha']})
    v['kit_tail'] = {'pass': len(set(tails.values())) == 1,
                     'tails': {k: w[:16] for k, w in tails.items()}}
    tr = [t['midi'] for t in r3b['final']['transitions']]
    v['transitions'] = {'pass': all(
        t['nonrt_hex'] == base['nonrt_hex'] for t in tr),
        'windows': [{'nonrt_len': t['nonrt_len'],
                     'rt_count': t['rt_count']} for t in tr]}
    mutes = {'r1': r1['final']['mutes_pat_hex'],
             'r2': r2['final']['mutes_pat_hex'],
             'r3a_mixed': r3a['final']['mutes_pat_hex'],
             'r3b_mixed': r3b['final']['mixed']['tail']['mutes_pat_hex'],
             'r3b_postflip1': r3b['final']['mutes_pat_hex']}
    # Flip-back must restore the stashed MIDI mute byte (track 5 = byte 5:
    # factory 0x01); the first-convert unmute (byte -> 0x00) is specified
    # flip behavior (convert.c: live byte = synth_mute, 0 when fresh).
    b1, b3 = r1['final']['mutes_pat_hex'], r3b['final']['mutes_pat_hex']
    restored_ok = (len(b1) == 16 and len(b3) == 16 and b3[10:12] == b1[10:12]
                   and b3[12:16] == b1[12:16])
    v['mutes'] = {'pass': b1 == b3 and restored_ok,
                  'mutes': mutes,
                  'slot1_byte_restored': restored_ok,
                  'note': 'first-convert writes live mute byte = 0 '
                          '(fresh synth_mute); flip-back restores stashed '
                          'MIDI mute'}
    c0 = [h for h in r2['final']['f3_play']['hits'] if h[1] in (4, 5, 6, 7)]
    v['r2_publish'] = {'track47_hits': len(c0),
                       'in_modram': len(r2['final'].get('converted_pub', [])),
                       'a0s': sorted(set(h[2] for h in r2['final'].get(
                           'converted_pub', [])))}
    cm = [h for h in r3a['final']['f3_mixed_play']['hits']
          if h[1] in (4, 5)]
    v['r3a_mixed_publish'] = {'track45_hits': len(cm),
                              'in_modram': len(r3a['final'].get(
                                  'converted_pub', [])),
                              'a0s': sorted(set(h[2] for h in r3a['final'].get(
                                  'converted_pub', [])))}
    cr = [h for h in r3b['final']['f3_postflip1_play']['hits']]
    cr4 = [h for h in cr if h[1] == 4]
    cr5 = [h for h in cr if h[1] == 5]
    cr4mod = [h for h in cr4
              if MODRAM_LO <= int(h[2], 16) < MODRAM_HI]
    v['r3b_postflip1_f3'] = {'track4_hits': len(cr4),
                             'track4_modram': len(cr4mod),
                             'track5_hits': len(cr5),
                             'pass': len(cr4mod) > 0 and len(cr5) == 0}
    v['overall_41'] = {'pass': all([v['din_identity']['pass'],
                                    v['kit_tail']['pass'],
                                    v['transitions']['pass'],
                                    v['mutes']['pass'],
                                    v['r3b_postflip1_f3']['pass']])}
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', choices=('r1', 'r2', 'r3a', 'r3b', 'r4', 'r5'))
    ap.add_argument('--out')
    ap.add_argument('--copies', action='store_true')
    ap.add_argument('--compare', nargs=4, metavar=('R1', 'R2', 'R3A', 'R3B'))
    ap.add_argument('--chan', default=None,
                    help='ADDR,SIZE for r5 (e.g. 0x41a0b000,1)')
    args = ap.parse_args()
    if args.copies:
        out = copy_snapshots()
        print(json.dumps(out, indent=1))
        return
    if args.compare:
        reps = []
        for p in args.compare:
            with open(p) as fh:
                reps.append(json.load(fh))
        rep = {'verdicts': compare(*reps)}
        print(json.dumps(rep['verdicts'], indent=1))
        if args.out:
            with open(args.out, 'w') as fh:
                json.dump(rep, fh, indent=1)
        return
    assert args.run and args.out
    folders = {'stock': os.path.join(WORK, os.path.basename(STOCK_SRC)),
               'mod': os.path.join(WORK, os.path.basename(MOD_SRC))}
    if args.run == 'r1':
        rep = leg_r1(folders['stock'])
    elif args.run == 'r2':
        rep = leg_r2(folders['mod'])
    elif args.run == 'r3a':
        rep = leg_r3a(folders['mod'])
    elif args.run == 'r3b':
        rep = leg_r3b(folders['mod'])
    elif args.run == 'r4':
        rep = leg_r4(folders['stock'])
    elif args.run == 'r5':
        assert args.chan, '--chan ADDR,SIZE required for r5'
        a, s = args.chan.split(',')
        rep = leg_r5(folders['mod'], int(a, 0), int(s))
    with open(args.out, 'w') as fh:
        json.dump(rep, fh, indent=1)
    print('scenario=%s halted=%s wall=%s' % (
        rep['scenario'], rep['halted'], rep.get('wall')))


if __name__ == '__main__':
    main()
