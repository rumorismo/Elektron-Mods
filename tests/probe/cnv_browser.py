#!/usr/bin/env python3
"""Browser parity proof for dn-convert 0.14 (8track-engine task 3.1).

Mod RAM truth (no pixels for classification): addresses come from the
link map `test-cnv14f.syx.map.json` next to the .syx (sibling firmware/,
never committed) — no layout reverse-engineering per build (current:
  MODAL_SLOT 0x43ec2300 (-1 = IDLE, else pending slot),
  STATE 0x43ec3798 + 4i (0 NATIVE / 1 SYNTH / 2 STASHED),
  SND 0x43ec3a40 + 326i (slot .bss sound),
  ROW 0x43ec2ac0 + 808i (slot mod browser row)).
Boot asserts MODAL_SLOT == -1 and STATE == 0 (fresh project).

Legs (run from tools/digiemu with its venv; needs emu.*, unicorn):
  open    : convert slot 0; B1 hook logs d2 (must be 4: compared reg =
            track, site proven not blind); double-tap with retry; then
            DOWN + YES; success = SND[0] changes (only the synth browser
            can stage a 326B preset). CURRENTLY BLOCKED (records evidence,
            see cnv_browser.md): the browser never opens for converted
            slots (f330-subtree gate), so won stays None.
  single  : single-tap converted slot: ACTIVE stays 4, select stable on
            the MIDI page (single-tap parity: B0 divert-all must not alter
            selection); modal still opens afterwards.
  apply   : (BLOCKED on open) in the converted browser: DOWN x1 + YES ->
            SND[0] changes; DOWN x3 + YES -> different bytes (write
            follows the selection); kit tail + kit slot region untouched;
            ROW+16 wired to SND at apply time (read back).
  voice   : (BLOCKED on open) audio=True: program converted track, PLAY
            ~4 s, voices-buffer energy series; F3 hook: converted fires
            publish SND (mod RAM) and render energy > 0.
  native  : native track-0 browser fb + apply: kit slot hash changes via
            the stock path; SND/ROW untouched (no converted cross-talk).
  kit     : kit tail + slot-4 region + full pattern identical across
            convert + taps + flip-back (B-sites write no kit).

Each leg = ONE Session from the persistent settled snapshot, <60 s wall.
Evidence JSONs + PNGs live OUTSIDE the repo (/tmp/opencode).
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
from emu.fwcompare import folder_paths  # noqa: E402
from emu.session import Session  # noqa: E402

try:
    from unicorn.m68k_const import (UC_M68K_REG_A0, UC_M68K_REG_D2,  # noqa: E402
                                    UC_M68K_REG_D4, UC_M68K_REG_A7)
except Exception:
    UC_M68K_REG_A0 = UC_M68K_REG_D2 = UC_M68K_REG_D4 = UC_M68K_REG_A7 = None

PAT_PTR = 0x4138f214
KIT_PTR = 0x4138f220
ACTIVE = 0x41368ce0
PAT_MUTES_OFF = 0x16108
TRACK_STRUCT = 976
KIT_MIDI_OFF = 0x5CE
MIDI_REC = 164
KIT_TAIL_END = 0x85E
KIT_SND_OFF = 0x18
SND_REC = 326
VOICES = 0x80004110
VOICES_LEN = 8 * 32 * 4
F3_REJOIN = 0x40094848
MODRAM_LO = 0x43EC0000
MODRAM_HI = 0x43EC4000
FOLDER = ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
          'portable/firmware/dn1-1477-cc9e5776')
MAP_JSON = ('/home/nuke/Documents/Elektron-MODS/firmware/'
            'test-cnv14f.syx.map.json')
SYX_SHA = 'cc9e5776ab61abfd73f826fd0197df78708c6a1179bf192dd99f227b4be00cd3'

with open(MAP_JSON) as _fh:
    _MAP = json.load(_fh)


def _addr(k):
    v = _MAP[k]
    return int(v, 16) if isinstance(v, str) else v


MODAL_SLOT = _addr('cnv_modal_slot')
STATE = _addr('cnv_state')
SND = _addr('cnv_synth_snd')
ROW = _addr('cnv_brow_row')
SITE_B1 = _addr('cnv_site_b1')
SITE_B2 = _addr('cnv_site_b2')
SITE_B3 = _addr('cnv_site_b3')


def sha(b):
    return hashlib.sha256(bytes(b)).hexdigest()


def u32(m, a):
    b = m.peek(a, 4)
    return struct.unpack('>I', b)[0] if b and len(b) == 4 else None


def s32(m, a):
    b = m.peek(a, 4)
    return struct.unpack('>i', b)[0] if b and len(b) == 4 else None


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
        assert s32(m, MODAL_SLOT) == -1, 'modal not IDLE at boot'
        assert u32(m, STATE) == 0, 'slot 0 not NATIVE at boot'

    def slot(self):
        return s32(self.s.m, MODAL_SLOT)

    def state(self, i=0):
        return u32(self.s.m, STATE + 4 * i)

    def snd(self, i=0):
        return bytes(self.s.m.peek(SND + 326 * i, 326))

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
            buf = panel.read(self.s.m, self.s.profile.fb_front)
            h = sha(buf) if buf is not None else None
            if h == last:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
            last = h
        return buf

    def open_modal(self, slot=0, attempts=4):
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
            el = 0
            while el < 800:
                if self.slot() == slot:
                    return
                s.run_ms(100)
                el += 100
            s.run_ms(200)
        raise AssertionError('modal did not open after %d chords' % attempts)

    def convert0(self):
        self.open_modal(0)
        self.key('YES', hold=15, after=600)
        assert self.slot() == -1 and self.state(0) == 1, 'YES did not flip'

    def double_tap(self, retries=6, gap=150):
        """Double-tap T1 with outcome verification (fb change)."""
        base = sha(self.settle_fb())
        for _ in range(retries):
            s = self.s
            s.press(s.code('T1'))
            s.run_ms(60)
            s.release(s.code('T1'))
            s.run_ms(gap)
            s.press(s.code('T1'))
            s.run_ms(60)
            s.release(s.code('T1'))
            s.run_ms(300)
            hb = sha(self.settle_fb())
            if hb != base:
                return hb
            s.run_ms(200)
        raise AssertionError('double-tap never changed fb')

    def close(self):
        self.s.close()
        self.wall['total'] = round(time.time() - self.t0, 1)


def leg_open():
    r = Run(audio=False)
    out = {'leg': 'open'}
    r.ensure_active(4)
    out['pre_main_fb'] = sha(r.settle_fb())[:16]
    r.convert0()
    out['converted'] = True
    r.ensure_active(4)
    main = sha(r.settle_fb())
    out['post_convert_main_fb'] = main[:16]
    snd_init = r.snd(0)
    # B1 hook: log d2 (compared reg) at the open branch
    seen = []

    def on_b1(uc, a, sz, d):
        if len(seen) < 16:
            seen.append(uc.reg_read(UC_M68K_REG_D2))
    r.s.at(SITE_B1, on_b1)
    # Outcome-verified open: double-tap, DOWN, YES; success = SND[0]
    # changes (only the synth browser can stage a 326B preset). The fb
    # right after the successful double-tap (before DOWN) is recorded as
    # the converted browser screen.
    won = None
    for attempt in range(8):
        s = r.s
        s.press(s.code('T1'))
        s.run_ms(60)
        s.release(s.code('T1'))
        s.run_ms(150)
        s.press(s.code('T1'))
        s.run_ms(60)
        s.release(s.code('T1'))
        s.run_ms(300)
        fb = sha(r.settle_fb())
        if fb == main:
            continue
        r.key('DOWN', hold=100, after=300)
        r.key('YES', hold=100, after=500)
        r.settle_fb()
        if r.snd(0) != snd_init:
            won = {'attempt': attempt, 'browser_fb': fb[:16]}
            break
        r.key('NO', hold=100, after=200)
        r.settle_fb()
    out['b1_d2'] = seen
    out['b1_d2_has_track4'] = (4 in seen)
    if won is None:
        out['BLOCKED'] = ('browser never opened+applied in 8 attempts; '
                          'f330-subtree gate (see cnv_browser.md)')
    else:
        out.update(won)
        out['apply_changed'] = True
        out['snd_nonzero'] = sum(1 for x in r.snd(0) if x != 0)
    r.close()
    out['wall'] = r.wall
    return out


def leg_single():
    r = Run(audio=False)
    out = {'leg': 'single'}
    r.ensure_active(4)
    r.convert0()
    r.ensure_active(4)
    h0 = sha(r.settle_fb())
    r.key('T1', hold=60, after=300)
    h1 = sha(r.settle_fb())
    out['tap_active'] = u32(r.s.m, ACTIVE)
    # parity: single-tap selects stably (idempotent, no menu/pop, no bank
    # jump). The fb lands on the MIDI select page (same as stock MIDI
    # single-tap); what matters is ACTIVE==4, stability, and that the
    # modal still works afterwards.
    r.key('T1', hold=60, after=300)
    h2 = sha(r.settle_fb())
    out['tap_select_stable'] = (h1 == h2)
    out['tap_select_fb'] = h1[:16]
    r.open_modal(0)
    out['modal_still_opens'] = (r.slot() == 0)
    r.key('#14', hold=15, after=200)
    out['tap_active_end'] = u32(r.s.m, ACTIVE)
    r.close()
    out['wall'] = r.wall
    return out


def leg_apply():
    r = Run(audio=False)
    out = {'leg': 'apply'}
    r.ensure_active(4)
    r.convert0()
    r.ensure_active(4)
    snd_init = r.snd(0)
    out['snd_init_nonzero'] = sum(1 for x in snd_init if x != 0)
    tail_pre = bytes(r.s.m.peek(r.kit + KIT_MIDI_OFF,
                                KIT_TAIL_END - KIT_MIDI_OFF))
    slot4_pre = bytes(r.s.m.peek(r.kit + KIT_SND_OFF + 326 * 4, 326))
    r.double_tap()
    r.key('DOWN', hold=100, after=300)
    r.key('YES', hold=100, after=500)
    r.settle_fb()
    snd_a = r.snd(0)
    out['apply1_changed'] = (snd_a != snd_init)
    out['apply1_nonzero'] = sum(1 for x in snd_a if x != 0)
    # row +16 wiring must point at SND[0]
    out['row16'] = hex(u32(r.s.m, ROW + 16))
    out['row16_is_snd0'] = (u32(r.s.m, ROW + 16) == SND)
    # different selection -> different bytes (write follows selection)
    r.double_tap()
    for _ in range(3):
        r.key('DOWN', hold=100, after=200)
    r.key('YES', hold=100, after=500)
    r.settle_fb()
    snd_b = r.snd(0)
    out['apply2_changed'] = (snd_b != snd_a)
    out['apply2_nonzero'] = sum(1 for x in snd_b if x != 0)
    tail_post = bytes(r.s.m.peek(r.kit + KIT_MIDI_OFF,
                                 KIT_TAIL_END - KIT_MIDI_OFF))
    slot4_post = bytes(r.s.m.peek(r.kit + KIT_SND_OFF + 326 * 4, 326))
    out['kit_tail_same'] = (tail_post == tail_pre)
    out['kit_slot4_same'] = (slot4_post == slot4_pre)
    out['tail_sha'] = sha(tail_pre)[:16]
    r.close()
    out['wall'] = r.wall
    return out


def leg_kit():
    """Kit/pattern untouched by the browser interpose (no browser needed:
    B3 only fires inside the browser apply, B2 writes mod rows only)."""
    r = Run(audio=False)
    out = {'leg': 'kit'}
    r.ensure_active(4)
    p_pre = bytes(r.s.m.peek(r.pat, 8 * TRACK_STRUCT))
    tail_pre = bytes(r.s.m.peek(r.kit + KIT_MIDI_OFF,
                                KIT_TAIL_END - KIT_MIDI_OFF))
    slot4_pre = bytes(r.s.m.peek(r.kit + KIT_SND_OFF + 326 * 4, SND_REC))
    r.convert0()
    out['converted'] = True
    r.ensure_active(4)
    # single + double taps (B0/B1/B2 paths, no browser open expected)
    r.key('T1', hold=60, after=300)
    s = r.s
    s.press(s.code('T1')); s.run_ms(60); s.release(s.code('T1')); s.run_ms(150)
    s.press(s.code('T1')); s.run_ms(60); s.release(s.code('T1')); s.run_ms(300)
    r.settle_fb()
    # flip back via modal YES on the RESTORE card
    r.open_modal(0)
    r.key('YES', hold=15, after=600)
    out['restored'] = (r.slot() == -1 and r.state(0) == 2)
    p_post = bytes(r.s.m.peek(r.pat, 8 * TRACK_STRUCT))
    tail_post = bytes(r.s.m.peek(r.kit + KIT_MIDI_OFF,
                                 KIT_TAIL_END - KIT_MIDI_OFF))
    slot4_post = bytes(r.s.m.peek(r.kit + KIT_SND_OFF + 326 * 4, SND_REC))
    out['pattern_same'] = (p_post == p_pre)
    out['kit_tail_same'] = (tail_post == tail_pre)
    out['kit_slot4_same'] = (slot4_post == slot4_pre)
    out['tail_sha'] = sha(tail_pre)[:16]
    r.close()
    out['wall'] = r.wall
    return out


def energy(raw):
    n = len(raw) // 4
    vals = struct.unpack('>' + 'i' * n, raw)
    return max(abs(v) for v in vals), sum(abs(v) for v in vals) // max(n, 1)


def leg_voice():
    r = Run(audio=True)
    s = r.s
    m = s.m
    out = {'leg': 'voice'}
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
        b = m.peek(r.pat + track * TRACK_STRUCT + 2 * int(step) - 1, 1)
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

    r.convert0()
    out['converted'] = True
    r.double_tap()
    r.key('DOWN', hold=100, after=300)
    r.key('YES', hold=100, after=500)
    r.settle_fb()
    out['snd_nonzero'] = sum(1 for x in r.snd(0) if x != 0)
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
    live_max = max(p['max'] for p in series)
    out.update({
        't4_hits': len(t4a0), 't4_a0s': a0s, 't4_in_modram': inram,
        'series_max': live_max, 'series': series, 'play_wall': play_wall,
        'pass': bool(inram) and live_max > 0,
    })
    r.close()
    out['wall'] = r.wall
    return out


def leg_native():
    r = Run(audio=False)
    out = {'leg': 'native'}
    h0 = sha(r.settle_fb())
    r.double_tap()
    out['browser_fb'] = sha(r.settle_fb())[:16]
    slot0_pre = bytes(r.s.m.peek(r.kit + KIT_SND_OFF, SND_REC))
    r.key('DOWN', hold=100, after=300)
    r.key('YES', hold=100, after=500)
    r.settle_fb()
    slot0_post = bytes(r.s.m.peek(r.kit + KIT_SND_OFF, SND_REC))
    out['native_apply_changed'] = (slot0_post != slot0_pre)
    out['snd0_untouched'] = (r.snd(0) == bytes(326))
    out['row0_ptr_not_snd'] = (u32(r.s.m, ROW + 16) != SND)
    out['main_fb'] = h0[:16]
    r.close()
    out['wall'] = r.wall
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--leg', choices=('open', 'single', 'apply', 'voice',
                                      'native', 'kit'),
                    required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    fn = {'open': leg_open, 'single': leg_single, 'apply': leg_apply,
          'voice': leg_voice, 'native': leg_native,
          'kit': leg_kit}[args.leg]
    rep = fn()
    with open(args.out, 'w') as fh:
        json.dump(rep, fh, indent=1, default=str)
    print('%s wall=%s' % (args.leg, rep.get('wall')))
    print(json.dumps({k: v for k, v in rep.items() if k != 'series'},
                     indent=1, default=str))


if __name__ == '__main__':
    main()
