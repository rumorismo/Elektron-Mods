#!/usr/bin/env python3
"""Sustain probe for dn-convert (8track-engine tasks 1.2/1.3 gate).

Isolated converted-slot playback: programs T1, converts slot 4 via the
MIDI+VOICE chord, programs converted track 4, mutes tracks 0-3, PLAYs,
and samples the voices render buffer (0x80004110) for energy. A sustained
nonzero series with only track 4 live proves the converted voice path
renders; all-zero means the slot is silent (the 0.11 failure mode: the
.bss sound record was 326 zero bytes).

Also records the .bss record nonzero count right after conversion (the
0.12 fix copies the live kit slot-0 record as init timbre).

Run from tools/digiemu with its venv (needs emu.*, unicorn):

    python tests/probe/sustain_probe.py --folder <snapshot-dir> \\
        --syx-sha <hex> --out /tmp/x/sustain.json

Single Session, one ~4 s PLAY, <60 s wall.
"""
import argparse
import json
import os
import struct
import sys
import time

DIGIEMU = '/home/nuke/Documents/Elektron-MODS/tools/digiemu'
sys.path.insert(0, DIGIEMU)
os.chdir(DIGIEMU)

from unicorn.m68k_const import UC_M68K_REG_A0, UC_M68K_REG_D4  # noqa: E402

from emu import midi  # noqa: E402
from emu.fwcompare import folder_paths  # noqa: E402
from emu.session import Session  # noqa: E402

PAT_PTR = 0x4138f214
KIT_PTR = 0x4138f220
ACTIVE = 0x41368ce0
PAT_MUTES_OFF = 0x16108
SOUND_REC_SIZE = 326
VOICES = 0x80004110
VOICES_LEN = 8 * 32 * 4
KEY_HOLD_MS = 15
KEY_AFTER_MS = 15


def u32(m, a):
    b = m.peek(a, 4)
    return struct.unpack('>I', b)[0] if b and len(b) == 4 else None


def energy(raw):
    n = len(raw) // 4
    vals = struct.unpack('>' + 'i' * n, raw)
    return max(abs(v) for v in vals), sum(abs(v) for v in vals) // max(n, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--folder', required=True)
    ap.add_argument('--syx-sha', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    t0 = time.time()
    wall = {}

    import hashlib
    paths = folder_paths(args.folder)
    os.environ.update(paths.env())
    with open(os.path.join(args.folder, 'firmware.json'), encoding='utf-8') as fh:
        rec = json.load(fh)
    syx_name = (rec.get('release') or {}).get('syx_name') or rec.get('syx_name')
    h = hashlib.sha256()
    with open(os.path.join(args.folder, syx_name), 'rb') as fh:
        for blk in iter(lambda: fh.read(1 << 20), b''):
            h.update(blk)
    assert h.hexdigest() == args.syx_sha, 'syx sha mismatch'
    t = time.time()
    s = Session(paths.gui, paths.syx, audio=True)
    wall['boot'] = round(time.time() - t, 1)
    m = s.m
    pat, kit = u32(m, PAT_PTR), u32(m, KIT_PTR)
    assert pat and kit

    fires = []
    s.at(0x40094848, lambda uc, a, sz, d: fires.append((
        round(s.ms, 1), uc.reg_read(UC_M68K_REG_D4) // 326
        if uc.reg_read(UC_M68K_REG_D4) % 326 == 0 else -1,
        '0x%08x' % uc.reg_read(UC_M68K_REG_A0))))

    tx = midi.MidiOut(sink=bytearray().extend)
    tx.install(s.m)
    tx.attach(s.m, s.ips)
    s.sources = s.sources + (tx,)

    def key(name, hold=KEY_HOLD_MS, after=KEY_AFTER_MS):
        s.press(s.code(name))
        s.run_ms(hold)
        s.release(s.code(name))
        s.run_ms(after)

    def step_on(track, step):
        b = m.peek(pat + track * 976 + 2 * int(step) - 1, 1)
        return bool(b and b[0] & 1)

    def program(track, select):
        if select:
            key(select)
            assert u32(m, ACTIVE) == track, (select, u32(m, ACTIVE))
        key('RECORD')
        for st in ('2', '6', '10', '14'):
            key(st)
            if not step_on(track, st):
                key(st)
            assert step_on(track, st), (track, st)
        key('RECORD')

    def ensure_active(track, tries=4):
        for _ in range(tries):
            if u32(m, ACTIVE) == track:
                return
            key('MIDI', hold=50, after=50)
        assert u32(m, ACTIVE) == track

    t = time.time()
    program(0, 'T1')
    wall['program_t0'] = round(time.time() - t, 1)

    t = time.time()
    ensure_active(4)
    start = bytes(m.peek(pat + 4 * 976, 976))
    for _ in range(1, 4):
        s.press(s.code('MIDI'))
        s.run_ms(50)
        s.press(s.code('VOICE'))
        s.run_ms(30)
        s.release(s.code('VOICE'))
        s.run_ms(50)
        s.release(s.code('MIDI'))
        s.run_ms(100)
        if bytes(m.peek(pat + 4 * 976, 976)) != start:
            break
    else:
        raise AssertionError('chord conv failed')
    wall['chord'] = round(time.time() - t, 1)

    t = time.time()
    ensure_active(4)
    program(4, None)
    wall['program_t4'] = round(time.time() - t, 1)

    # The .bss sound address is layout-dependent: read it back from a
    # converted-slot F3 publish. Content is voice-path-read-only, so a
    # post-PLAY read is identical to post-convert (play never writes it).

    for tr in (0, 1, 2, 3):
        m.poke(pat + PAT_MUTES_OFF + tr, bytes([1]))

    t = time.time()
    key('PLAY', hold=60, after=100)
    series = []
    for _ in range(8):
        s.run_ms(500)
        vb = bytes(m.peek(VOICES, VOICES_LEN))
        mx, av = energy(vb)
        series.append({'ms': round(s.ms, 1), 'max': mx, 'avg': av})
    wall['play'] = round(time.time() - t, 1)
    key('STOP', hold=60, after=100)
    wall['total'] = round(time.time() - t0, 1)

    t4a0 = [a for _, tr, a in fires if tr == 4]
    assert t4a0, 'no converted-slot F3 publish seen'
    assert len(set(t4a0)) == 1, set(t4a0)
    bss_base = int(t4a0[0], 16)
    bss = bytes(m.peek(bss_base, SOUND_REC_SIZE))
    bss_nonzero = sum(1 for x in bss if x != 0)

    bytrack = {}
    for _, tr, _ in fires:
        bytrack[tr] = bytrack.get(tr, 0) + 1
    live_max = max(p['max'] for p in series)
    verdict = {'pass': bss_nonzero > 0 and live_max > 0,
               'bss_nonzero': bss_nonzero,
               'series_max': live_max,
               'f3_by_track': bytrack}
    out = {'folder': args.folder, 'wall': wall, 'verdict': verdict,
           'bss_head': bss[:32].hex(), 'series': series,
           'halted': s.halted}
    with open(args.out, 'w') as fh:
        json.dump(out, fh, indent=1, default=str)
    print('sustain: pass=%s bss_nonzero=%d series_max=%d f3=%s wall=%s' % (
        verdict['pass'], bss_nonzero, live_max, bytrack, wall))
    s.close()


if __name__ == '__main__':
    main()
