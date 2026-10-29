#!/usr/bin/env python3
"""3.1 B5 proof for dn-convert 0.16 (extends cnv_browser, does not rewrite it).

B5 mechanism (proven on 0.15, see gate3/track2 probe runs): the browser
refresh commit is gated by stock 0x40025b76 called at 0x400400ec with
A4 = tapped track (0 native T1, 1 native T2, 4 converted slot 0).
Stock maps (u32)track <= 3 -> 1, == 8 -> 2, else 0; the caller
(0x400400f4 moveq #1,d1 + cmp + bne.w 0x40040d32) reaches the
0x400e54a2 page-commit chain (view+0x17, ctx writers) only on 1, so a
converted slot always bailed. B5 (cnv_site_b5) returns 1 for converted
slots and replicates the stock mapping otherwise.

Legs (run from tools/digiemu with its venv):
  gate16  : B5 fires with track 4 -> d0 1; 0x400e626e + 0x400e5416 fire;
            converted double-tap DRAWS (fb leaves main).
  open16 / single16 / apply16 / voice16 / native16 / kit16:
            full 3.1 legs on the 0.16 build (reused from cnv_browser).

Evidence JSONs live OUTSIDE the repo (/tmp/opencode).
"""
import argparse
import json
import struct
import sys

import cnv_browser as B

from emu import panel  # noqa: E402
from unicorn.m68k_const import UC_M68K_REG_A4, UC_M68K_REG_D0  # noqa: E402

BUILD16 = {
    'tag': 1479,
    'syx_sha': ('4c4fa67a09535b9a718dfe7dad2b911b225f78a601d8bd3c3fa77968a6'
                '77e991'),
    'folder': ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
               'portable/firmware/dn1-1479-4c4fa67a'),
    'map': ('/home/nuke/Documents/Elektron-MODS/firmware/'
            'test-cnv16.syx.map.json'),
}

BUILD17 = {
    'tag': 1480,
    'syx_sha': ('c2213f11dfa9292931f177a149205c4e07eb820faffc0d97a8ac35ce3d'
                '9687f9'),
    'folder': ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
               'portable/firmware/dn1-1480-c2213f11'),
    'map': ('/home/nuke/Documents/Elektron-MODS/firmware/'
            'test-cnv17.syx.map.json'),
}

E626E = 0x400e626e
E5416 = 0x400e5416
B5REJOIN = 0x400400f2


def use_build(b):
    """Rebind cnv_browser globals to another linked build."""
    B.FOLDER = b['folder']
    B.MAP_JSON = b['map']
    B.SYX_SHA = b['syx_sha']
    with open(b['map']) as fh:
        B._MAP = json.load(fh)
    B.MODAL_SLOT = B._addr('cnv_modal_slot')
    B.STATE = B._addr('cnv_state')
    B.SND = B._addr('cnv_synth_snd')
    B.ROW = B._addr('cnv_brow_row')
    B.SITE_B1 = B._addr('cnv_site_b1')
    B.SITE_B2 = B._addr('cnv_site_b2')
    B.SITE_B3 = B._addr('cnv_site_b3')


BROWSER_DOWN_FB = '0048b56645cd85ab'
NATIVE_YES_FB = 'd73b6922ab9ff9f3'


def open_browser(r, max_tries=40):
    """Outcome-verified converted browser open.

    Double-tap dispatch is scan-phase racy (a tap may take the select
    path), so every attempt double-taps and then navigates DOWN
    unconditionally: the browser is logically open even when the
    initial paint stays stale (fb == main). Success is the DOWN
    framebuffer matching the native browser-DOWN screen bit-exactly.
    Returns (attempt, gap) or None.
    """
    s = r.s
    for i in range(max_tries):
        r.ensure_active(4)
        gap = (150, 60, 300)[i % 3]
        s.press(s.code('T1'))
        s.run_ms(60)
        s.release(s.code('T1'))
        s.run_ms(gap)
        s.press(s.code('T1'))
        s.run_ms(60)
        s.release(s.code('T1'))
        s.run_ms(400)
        r.key('DOWN', hold=100, after=300)
        if B.sha(r.settle_fb())[:16] == BROWSER_DOWN_FB:
            return (i, gap)
        r.key('NO', hold=100, after=200)
        r.settle_fb()
    return None


def leg_gate17():
    use_build(BUILD17)
    r = B.Run(audio=False)
    out = {'leg': 'gate17', 'build': '0.17', 'tag': 1480}
    site_b5 = B._addr('cnv_site_b5')
    site_b6 = B._addr('cnv_site_b6')
    out['site_b5'] = hex(site_b5)
    out['site_b6'] = hex(site_b6)
    r.ensure_active(4)
    r.convert0()
    r.ensure_active(4)
    out['main_fb'] = B.sha(r.settle_fb())[:16]
    b5 = []
    b6 = []

    def on_b5(uc, a, sz, d):
        if len(b5) < 32:
            try:
                b5.append('A4=%d' % uc.reg_read(UC_M68K_REG_A4))
            except Exception:
                pass

    def on_b6(uc, a, sz, d):
        if len(b6) < 32:
            try:
                b6.append('in=%d' % uc.reg_read(UC_M68K_REG_D0))
            except Exception:
                pass
    r.s.at(site_b5, on_b5)
    r.s.at(site_b6, on_b6)
    out['b5_A4'] = b5
    out['b5_hook'] = True
    opened = open_browser(r)
    out['opened'] = opened
    out['b6_seen'] = b6
    if opened is not None:
        out['draws'] = True
    else:
        out['BLOCKED'] = 'converted browser never drew in %d tries' % 40
    r.close()
    out['wall'] = r.wall
    return out


def leg_open17():
    use_build(BUILD17)
    r = B.Run(audio=False)
    out = {'leg': 'open17', 'build': '0.17', 'tag': 1480}
    r.ensure_active(4)
    r.convert0()
    r.ensure_active(4)
    out['main_fb'] = B.sha(r.settle_fb())[:16]
    opened = open_browser(r)
    out['opened'] = opened
    if opened is None:
        out['BLOCKED'] = 'no browser draw in 40 tries'
    else:
        out['browser_down_fb'] = BROWSER_DOWN_FB
        out['native_match'] = True
    r.close()
    out['wall'] = r.wall
    return out


def leg_apply17():
    use_build(BUILD17)
    r = B.Run(audio=False)
    out = {'leg': 'apply17', 'build': '0.17', 'tag': 1480}
    r.ensure_active(4)
    r.convert0()
    r.ensure_active(4)
    snd_init = bytes(r.snd(0))
    out['snd_init_nonzero'] = sum(1 for x in snd_init if x != 0)
    slot0_pre = bytes(r.s.m.peek(r.kit + B.KIT_SND_OFF, B.SND_REC))
    tail_pre = bytes(r.s.m.peek(r.kit + B.KIT_MIDI_OFF,
                               B.KIT_TAIL_END - B.KIT_MIDI_OFF))
    opened = open_browser(r)
    out['opened'] = opened
    if opened is None:
        out['BLOCKED'] = 'no browser draw in 40 tries'
        r.close()
        out['wall'] = r.wall
        return out
    for _ in range(2):
        r.key('DOWN', hold=100, after=300)
    out['down3_fb'] = B.sha(r.settle_fb())[:16]
    r.key('YES', hold=100, after=500)
    r.settle_fb()
    out['yes_fb'] = B.sha(r.settle_fb())[:16]
    out['yes_toast'] = (out['yes_fb'] != out['down3_fb'])
    out['row16'] = hex(B.u32(r.s.m, B.ROW + 16))
    out['row16_is_snd0'] = (B.u32(r.s.m, B.ROW + 16) == B.SND)
    snd_a = bytes(r.snd(0))
    out['apply_changed'] = (snd_a != snd_init)
    out['apply_nonzero'] = sum(1 for x in snd_a if x != 0)
    out['kit_slot0_same'] = (bytes(r.s.m.peek(r.kit + B.KIT_SND_OFF,
                                              B.SND_REC)) == slot0_pre)
    out['kit_tail_same'] = (bytes(r.s.m.peek(r.kit + B.KIT_MIDI_OFF,
                                             B.KIT_TAIL_END -
                                             B.KIT_MIDI_OFF)) == tail_pre)
    r.close()
    out['wall'] = r.wall
    return out


def leg_voice17():
    use_build(BUILD17)
    import struct as _struct
    from unicorn.m68k_const import UC_M68K_REG_A0 as _A0
    from unicorn.m68k_const import UC_M68K_REG_D4 as _D4
    from emu import midi as _midi
    r = B.Run(audio=True)
    s = r.s
    m = s.m
    out = {'leg': 'voice17', 'build': '0.17', 'tag': 1480}
    fires = []
    s.at(B.F3_REJOIN, lambda uc, a, sz, d: fires.append((
        round(s.ms, 1), uc.reg_read(_D4) // 326
        if uc.reg_read(_D4) % 326 == 0 else -1,
        '0x%08x' % uc.reg_read(_A0))))
    tx = _midi.MidiOut(sink=bytearray().extend)
    tx.install(s.m)
    tx.attach(s.m, s.ips)
    s.sources = s.sources + (tx,)

    def key(name, hold=15, after=15):
        s.press(s.code(name))
        s.run_ms(hold)
        s.release(s.code(name))
        s.run_ms(after)

    def step_on(track, step):
        b = m.peek(r.pat + track * B.TRACK_STRUCT + 2 * int(step) - 1, 1)
        return bool(b and b[0] & 1)

    def program(track, select):
        if select:
            key(select)
            assert B.u32(m, B.ACTIVE) == track
        key('RECORD')
        for st in ('2', '6', '10', '14'):
            key(st)
            if not step_on(track, st):
                key(st)
            assert step_on(track, st), (track, st)
        key('RECORD')

    r.convert0()
    out['converted'] = True
    opened = open_browser(r)
    out['opened'] = opened
    if opened is None:
        out['BLOCKED'] = 'no browser draw in 40 tries'
        r.close()
        out['wall'] = r.wall
        return out
    for _ in range(3):
        r.key('DOWN', hold=100, after=200)
    r.key('YES', hold=100, after=500)
    r.settle_fb()
    snd = bytes(r.snd(0))
    out['snd_changed'] = (snd != bytes(326))
    out['snd_nonzero'] = sum(1 for x in snd if x != 0)
    r.ensure_active(4)
    program(4, None)
    for tr in (0, 1, 2, 3):
        m.poke(r.pat + B.PAT_MUTES_OFF + tr, bytes([1]))
    import time as _time
    t = _time.time()
    key('PLAY', hold=60, after=100)
    series = []
    for _ in range(3):
        s.run_ms(400)
        raw = bytes(m.peek(B.VOICES, B.VOICES_LEN))
        n = len(raw) // 4
        vals = _struct.unpack('>' + 'i' * n, raw)
        mx, av = max(abs(v) for v in vals), sum(abs(v) for v in vals) // max(n, 1)
        series.append({'ms': round(s.ms, 1), 'max': mx, 'avg': av})
    play_wall = round(_time.time() - t, 1)
    key('STOP', hold=60, after=100)
    key('STOP', hold=60, after=100)
    t4a0 = [a for _, tr, a in fires if tr == 4]
    a0s = sorted(set(t4a0))
    inram = [a for a in a0s
             if B.MODRAM_LO <= int(a, 16) < B.MODRAM_HI]
    live_max = max(p['max'] for p in series)
    out.update({
        't4_hits': len(t4a0), 't4_a0s': a0s, 't4_in_modram': inram,
        'series_max': live_max, 'series': series, 'play_wall': play_wall,
        'pass': bool(inram) and live_max > 0,
    })
    r.close()
    out['wall'] = r.wall
    return out


def _wrap(name):
    use_build(BUILD17)
    return getattr(B, 'leg_' + name)()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--leg', choices=('gate17', 'open17', 'apply17',
                                      'voice17', 'single17', 'native17',
                                      'kit17'),
                    required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    if args.leg in ('gate17', 'open17', 'apply17', 'voice17'):
        rep = {'gate17': leg_gate17, 'open17': leg_open17,
               'apply17': leg_apply17,
               'voice17': leg_voice17}[args.leg]()
    else:
        rep = _wrap(args.leg[0:-2])
        rep['leg'] = args.leg
        rep['build'] = '0.17'
        rep['tag'] = 1480
    with open(args.out, 'w') as fh:
        json.dump(rep, fh, indent=1, default=str)
    print('%s wall=%s' % (args.leg, rep.get('wall')))
    print(json.dumps({k: v for k, v in rep.items() if k != 'series'},
                     indent=1, default=str))


if __name__ == '__main__':
    main()
