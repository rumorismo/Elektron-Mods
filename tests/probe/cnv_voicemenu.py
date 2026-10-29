#!/usr/bin/env python3
"""Voice-menu parity proof for dn-convert (8track-engine task 3.2).

Mod RAM truth (NOT pixels) for classification; link map per build gives
exact mod addresses (sibling firmware/, never committed). Framebuffer is
lively (cnv_modal.md); menu-open outcome = fork-taken hooks + settled
hash + PNG captures (viewed, not hashed).

TASK DEVIATION (hard-rule stop, documented): the task names S3
0x4003df40 (d4 = track) + S4 0x40043258 (d2 = track) as the voice-menu
dispatch. Probed and DISPROVEN: S3/S4 entries, sites and both forks
stay silent on plain VOICE (native 0-3, converted 4-7, all modal-leg
page contexts) and on a gesture sweep (FUNC+VOICE, pages, encoders,
PTN, BANK, SONG, YES, T-select). Per the no-blind-patch rule they are
NOT interposed. The live dispatch was found dynamically and proven
instead: V8 bank-check 0x4003f642 (this lane's interpose) -> V7 ded70
block 0x400407e4 -> 58770 menu builder at 0x400408de.

Legs (run from tools/digiemu with its venv; needs emu.*, unicorn):
  regs4   : S3/S4 silence on plain VOICE (slot 0 converted + native
            0-3, main/voice-menu/settings/ptn contexts + midi-bank 4).
  routeA  : V7 ded70 block on native 0-3: d2 = const view ptr
            (NOT track), ded70 ret 0, menu fork taken, S3/S4 silent.
  routeB  : MIDI-bank tracks 4-7 (slot 0 converted) never reach V7.
  routeC1 : V8 proof, native 0-3: stock synth verdict, synth fork.
  routeC2 : V8 proof, converted 4 + native-MIDI 5-7: stock MIDI
            verdict, MIDI fork (pre-patch); S3/S4 silent throughout.
  open    : post-patch parity: native 0 vs converted 4 vs native 5 —
            V8 verdict, ded70 verdict, synth-fork taken, 58770 caller
            (must be 0x400408e4 on both), settled fb + PNG capture.
  regmodal: modal open + NO-cancel subset (state untouched).
  regbrowser: browser single-tap + kit-identity subset (proven legs).

Each leg = fresh Session(s) from the persistent settled snapshot.
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(DIGIEMU)

import cnv_browser as B  # noqa: E402
import cnv_browser3 as B3  # noqa: E402
from emu import panel  # noqa: E402
from emu.fwcompare import pixel_diff  # noqa: E402
from unicorn.m68k_const import (UC_M68K_REG_D0, UC_M68K_REG_D1,  # noqa: E402
                                UC_M68K_REG_D2, UC_M68K_REG_D4,
                                UC_M68K_REG_A7)

S3 = 0x4003df40
S3_SYNTH = 0x4003df46
S3_MIDI = 0x4003df82
S4 = 0x40043258
S4_SYNTH = 0x4004325e
E8BE8 = 0x400e8be8
E58770 = 0x40158770
E54A2 = 0x400e54a2

BUILD17 = {
    'tag': 1480,
    'syx_sha': ('c2213f11dfa9292931f177a149205c4e07eb820faffc0d97a8ac35ce3d'
                '9687f9'),
    'folder': ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
               'portable/firmware/dn1-1480-c2213f11'),
    'map': ('/home/nuke/Documents/Elektron-MODS/firmware/'
            'test-cnv17.syx.map.json'),
}

BUILD = dict(BUILD17)


def use_build(b):
    global BUILD
    BUILD = dict(b)
    B3.use_build(b)


def sha(b):
    return hashlib.sha256(bytes(b)).hexdigest()


def u32(m, a):
    b = m.peek(a, 4)
    return struct.unpack('>I', b)[0] if b and len(b) == 4 else None


def fb(m, s):
    return panel.read(m, s.profile.fb_front)


def midi_to_bank(r, midi, tries=6):
    """MIDI toggle until ACTIVE is on the wanted bank (slot preserved)."""
    m = r.s.m
    s = r.s
    want = 1 if midi else 0
    for _ in range(tries):
        if (u32(m, B.ACTIVE) // 4) == want:
            return True
        s.press(s.code('MIDI'))
        s.run_ms(120)
        s.release(s.code('MIDI'))
        el = 0
        while el < 1000 and (u32(m, B.ACTIVE) // 4) != want:
            s.run_ms(100)
            el += 100
    return (u32(m, B.ACTIVE) // 4) == want


def select(r, track, tries=12):
    """Bank-aware track select with outcome verification.

    Selection model (probed 2026-10-28, controlled runs): per-bank slot
    memory — MIDI switches bank (active = that bank's remembered slot,
    toggles never write memory), T1-T4 select the slot within the
    current bank. Short holds get missed by the key scan, so holds are
    120 ms and every press is polled (UI-task latency). Converted slots
    can never be T-selected on the MIDI bank (B0 divert routes the tap
    to the synth path: ACTIVE jumps to the synth slot instead), so
    callers must establish the MIDI-bank memory (select the track while
    native) BEFORE converting, then reach converted tracks via the MIDI
    toggle only. Native MIDI tracks T-select directly on the MIDI bank.
    """
    m = r.s.m
    s = r.s
    slot = track % 4
    for _ in range(tries):
        cur = u32(m, B.ACTIVE)
        if cur == track:
            return
        if (cur // 4) != (track // 4):
            if not midi_to_bank(r, track >= 4):
                continue
        else:
            code = s.code('T%d' % (slot + 1))
            s.press(code)
            s.run_ms(120)
            s.release(code)
            el = 0
            while el < 1000 and u32(m, B.ACTIVE) != track:
                s.run_ms(100)
                el += 100
    assert u32(m, B.ACTIVE) == track, 'select t%d failed' % track


def open_modal(r, slot=0, attempts=4):
    """B.open_modal with bank-aware select (B's ensure_active only does
    the 0<->4 toggle, so slots 1-3 need T-key selection)."""
    track = 4 + slot
    for _ in range(attempts):
        select(r, track)
        s = r.s
        s.press(s.code('MIDI'))
        s.run_ms(50)
        s.press(s.code('VOICE'))
        s.run_ms(30)
        s.release(s.code('VOICE'))
        s.run_ms(50)
        s.release(s.code('MIDI'))
        el = 0
        while el < 800:
            if r.slot() == slot:
                return
            s.run_ms(100)
            el += 100
        s.run_ms(200)
    raise AssertionError('modal did not open after %d chords' % attempts)


def press_voice(r, retries=3):
    """Plain VOICE with outcome verification (fb change). Returns the menu
    fb hash or None when the screen never changes."""
    s = r.s
    h0 = sha(fb(s.m, s))
    for _ in range(retries):
        s.press(s.code('VOICE'))
        s.run_ms(120)
        s.release(s.code('VOICE'))
        s.run_ms(300)
        hb = sha(r.settle_fb())
        if hb != h0:
            return hb
    return None


class Regs:
    """Shared register-proof session: hooks S3/S4 sites + fork entries,
    runs (context, track) plain-VOICE cells."""

    def __init__(self, tag, build):
        use_build(BUILD17)
        self.r = B.Run(audio=False)
        self.out = {'build': build, 'tag': tag,
                    's3': hex(S3), 's4': hex(S4), 'cells': []}
        s = self.r.s
        self.s3hits, self.s4hits = [], []
        self.s3fork, self.s4fork = [], []
        sh, fh = self.s3hits, self.s4hits

        def on_s3(uc, a, sz, d):
            if len(sh) < 64:
                try:
                    sh.append(int(uc.reg_read(UC_M68K_REG_D4)))
                except Exception:
                    pass

        def on_s4(uc, a, sz, d):
            if len(fh) < 64:
                try:
                    fh.append(int(uc.reg_read(UC_M68K_REG_D2)))
                except Exception:
                    pass

        def on_s3s(uc, a, sz, d):
            self.s3fork.append('synth')

        def on_s3m(uc, a, sz, d):
            self.s3fork.append('midi')

        def on_s4s(uc, a, sz, d):
            self.s4fork.append('synth')

        s.at(S3, on_s3)
        s.at(S4, on_s4)
        s.at(S3_SYNTH, on_s3s)
        s.at(S3_MIDI, on_s3m)
        s.at(S4_SYNTH, on_s4s)

    def convert(self, slot):
        r = self.r
        select(r, 4 + slot)
        open_modal(r, slot)
        r.key('YES', hold=15, after=600)
        assert r.slot() == -1 and r.state(slot) == 1, \
            'convert slot %d failed' % slot

    def cell(self, ctx, nav, track):
        r = self.r
        s = r.s
        c = {'ctx': ctx, 'track': track}
        try:
            if nav:
                r.key(nav, hold=120, after=300)
            select(r, track)
            c['active_at_press'] = u32(s.m, B.ACTIVE)
            h0 = sha(fb(s.m, s))
            del self.s3hits[:], self.s4hits[:]
            del self.s3fork[:], self.s4fork[:]
            # Press until the menu code runs (hits) or the screen moves
            # (max 4: key-scan misses happen even at 120 ms holds).
            for _ in range(4):
                s.press(s.code('VOICE'))
                s.run_ms(120)
                s.release(s.code('VOICE'))
                s.run_ms(300)
                if self.s3hits or self.s4hits or sha(fb(s.m, s)) != h0:
                    break
            hb = sha(r.settle_fb())
            c['fb_changed'] = (hb != h0)
            c['menu_fb'] = hb[:16]
            c['s3_d4'] = list(self.s3hits)
            c['s4_d2'] = list(self.s4hits)
            c['s3_fork'] = list(self.s3fork)
            c['s4_synth_hits'] = len(self.s4fork)
            at = c['active_at_press']
            c['s3_proven'] = (bool(self.s3hits) and
                              all(v == at for v in self.s3hits))
            c['s4_proven'] = (bool(self.s4hits) and
                              all(v == at for v in self.s4hits))
        except Exception as e:
            c['blocked'] = '%s: %s' % (type(e).__name__, e)
            c['s3_proven'] = c['s4_proven'] = False
        self.out['cells'].append(c)
        # Restore: NO (x2, scan-miss safety) closes the voice menu.
        r.key('NO', hold=120, after=300)
        r.key('NO', hold=120, after=300)

    def close(self):
        self.r.close()
        self.out['wall'] = self.r.wall
        cells = self.out['cells']
        self.out['s3_all_proven'] = all(c['s3_proven'] for c in cells)
        self.out['s4_all_proven'] = all(c['s4_proven'] for c in cells)
        return self.out


def leg_regs4():
    """Slot 0 + native: convert 4 (memory 0), all track-4 contexts +
    native 0-3 (main) + native 0 in voice-menu/settings/ptn contexts."""
    g = Regs(BUILD17['tag'], '0.17')
    g.out['leg'] = 'regs4'
    g.convert(0)
    g.out['converted'] = [g.r.state(i) for i in range(4)]
    for (ctx, nav) in CONTS:
        if ctx != 'midi-bank':
            g.cell(ctx, nav, 4)
    for t in (0, 1, 2, 3):
        g.cell('main', None, t)
    for (ctx, nav) in (('voice-menu', 'VOICE'),
                       ('global-settings', 'GLOBAL'),
                       ('ptn-menu', 'PTN')):
        g.cell(ctx, nav, 0)
    g.cell('midi-bank', None, 4)
    return g.close()


def _route_tracks(tracks, convert_slot=None, tag='route'):
    """One fresh Session per track (menu starts closed, no cross-cell
    contamination): select, optional convert, plain VOICE; log ded70
    d2 + ACTIVE, ded70 d0, fork taken, S3/S4 silence, menu fb."""
    use_build(BUILD17)
    out = {'leg': tag, 'build': '0.17', 'tag_build': BUILD17['tag'],
           'cells': []}
    for track in tracks:
        r = B.Run(audio=False)
        s = r.s
        m = s.m
        ded, ret, fork, s34 = [], [], [], []

        def on_ded(uc, a, sz, d, _ded=ded):
            try:
                _ded.append((int(uc.reg_read(UC_M68K_REG_D2)),
                             u32(m, B.ACTIVE)))
            except Exception:
                pass

        def on_ret(uc, a, sz, d, _ret=ret):
            try:
                _ret.append(int(uc.reg_read(UC_M68K_REG_D0)))
            except Exception:
                pass

        def on_menu(uc, a, sz, d):
            fork.append('menu')

        def on_else(uc, a, sz, d):
            fork.append('else')

        def on_s34(uc, a, sz, d):
            s34.append(True)

        s.at(VDED, on_ded)
        s.at(VDEDRET, on_ret)
        s.at(VMENU, on_menu)
        s.at(VELSE, on_else)
        for a in (S3, 0x4003df06, S4, 0x40043228):
            s.at(a, on_s34)
        c = {'track': track}
        try:
            select(r, track)
            if convert_slot is not None and track == 4 + convert_slot:
                open_modal(r, convert_slot)
                r.key('YES', hold=15, after=600)
                c['converted'] = (r.slot() == -1 and
                                  r.state(convert_slot) == 1)
                select(r, track)
            c['active_at_press'] = u32(m, B.ACTIVE)
            h0 = sha(fb(m, s))
            for _ in range(4):
                s.press(s.code('VOICE'))
                s.run_ms(120)
                s.release(s.code('VOICE'))
                s.run_ms(300)
                if ded or fork or sha(fb(m, s)) != h0:
                    break
            s.run_ms(400)
            hb = sha(fb(m, s))
            c['fb_changed'] = (hb != h0)
            c['menu_fb'] = hb[:16]
            c['ded70_d2_active'] = list(ded)
            c['ded70_ret'] = list(ret)
            c['fork'] = list(fork)
            c['s34_hits'] = len(s34)
            at = c['active_at_press']
            c['d2_is_tapped'] = (bool(ded) and
                                 all(v[0] == at and v[1] == at
                                     for v in ded))
        except Exception as e:
            c['blocked'] = '%s: %s' % (type(e).__name__, e)
        out['cells'].append(c)
        r.close()
    return out


# Voice-menu fork V7 (cfisa-verified): the plain-VOICE path reaches the
# ded70 predicate call at 0x400407e4. beq at 0x400407ee to 0x40040856
# (pea; bra to the 58770 menu builder at 0x400408de) on d0 == 0.
VDED = 0x400407e4
VDEDRET = 0x400407ea
VMENU = 0x40040856
VELSE = 0x400407f0

# Voice-menu bank gate V8 (cfisa-verified): the plain-VOICE path for
# every track runs the 0x4003f62e block: ded04(view) must pass
# (bcc 0x4003f63a -> 0x400403bc MIDI), then the bank check
# jsr 0x4002e1ae at 0x4003f642 must read synth (bcc 0x4003f64c ->
# 0x400403bc MIDI); else bra 0x4003f650 -> 0x400407e2 (ded70 block ->
# 58770 menu builder). Site shape (cell push + 6-byte jsr, rejoin
# addq #4,sp + tst.b d0) matches the B0 discipline exactly.
V8 = 0x4003f642
V8RET = 0x4003f648
V8PASS = 0x4003f63e
V8FAIL = 0x400403bc
V8SYNTH = 0x400407e2


def leg_routeC1():
    out = _routeC_tracks((0, 1, 2, 3), None, tag='routeC1')
    return out


def leg_routeC2():
    out = _routeC_tracks((4, 5, 6, 7), 0, tag='routeC2')
    return out


def _routeC_tracks(tracks, convert_slot, tag):
    use_build(BUILD)
    out = {'leg': tag, 'build': '0.18' if BUILD['tag'] == 1481 else '0.17',
           'tag_build': BUILD['tag'], 'v8': hex(V8), 'cells': []}
    for track in tracks:
        r = B.Run(audio=False)
        s = r.s
        m = s.m
        calls, ret, fork = [], [], []

        def on_v8(uc, a, sz, d, _calls=calls):
            try:
                sp = uc.reg_read(UC_M68K_REG_A7)
                raw = m.peek(sp + 4, 4)
                cell = struct.unpack('>I', raw)[0] if raw else None
                _calls.append((hex(cell) if cell else None,
                               u32(m, B.ACTIVE)))
            except Exception:
                pass

        def on_ret(uc, a, sz, d, _ret=ret):
            try:
                _ret.append(int(uc.reg_read(UC_M68K_REG_D0)))
            except Exception:
                pass

        def on_fail(uc, a, sz, d):
            fork.append('midi')

        def on_synth(uc, a, sz, d):
            fork.append('synth')

        s.at(V8, on_v8)
        s.at(V8RET, on_ret)
        s.at(V8FAIL, on_fail)
        s.at(V8SYNTH, on_synth)
        c = {'track': track}
        try:
            select(r, track)
            if convert_slot is not None and track == 4 + convert_slot:
                open_modal(r, convert_slot)
                r.key('YES', hold=15, after=600)
                c['converted'] = (r.slot() == -1 and
                                  r.state(convert_slot) == 1)
                select(r, track)
            c['active_at_press'] = u32(m, B.ACTIVE)
            h0 = sha(fb(m, s))
            for _ in range(4):
                s.press(s.code('VOICE'))
                s.run_ms(120)
                s.release(s.code('VOICE'))
                s.run_ms(300)
                if calls or fork or sha(fb(m, s)) != h0:
                    break
            s.run_ms(400)
            hb = sha(fb(m, s))
            c['fb_changed'] = (hb != h0)
            c['menu_fb'] = hb[:16]
            c['v8_cell_active'] = list(calls)
            c['v8_bankret'] = list(ret)
            c['fork'] = list(fork)
        except Exception as e:
            c['blocked'] = '%s: %s' % (type(e).__name__, e)
        out['cells'].append(c)
        r.close()
    return out


def leg_routeA():
    out = _route_tracks((0, 1, 2, 3), tag='routeA')
    out['wall'] = 'see per-cell sessions'
    return out


def leg_routeB():
    out = _route_tracks((4, 5, 6, 7), convert_slot=0, tag='routeB')
    return out


VMENU = 0x40040856
V58770R = 0x400408e4


def _menu_capture(r, track, convert_slot, png_path, label):
    """Select track (T-press for the selected state), optional convert,
    plain VOICE with outcome verification; record the builder chain
    (V8 verdict, ded70 verdict, menu entry, 58770 caller, e7020
    caller) + settled fb hash. One Session per call."""
    s = r.s
    m = s.m
    vret, dret, fork, bld = [], [], [], []
    import struct as _S

    def on_vret(uc, a, sz, d):
        try:
            vret.append(int(uc.reg_read(UC_M68K_REG_D0)))
        except Exception:
            pass

    def on_dret(uc, a, sz, d):
        try:
            dret.append(int(uc.reg_read(UC_M68K_REG_D0)))
        except Exception:
            pass

    def on_fork(uc, a, sz, d, _f=fork):
        _f.append(True)

    def on_b(uc, a, sz, d, _b=bld):
        try:
            sp = uc.reg_read(UC_M68K_REG_A7)
            raw = m.peek(sp, 4)
            ret = _S.unpack('>I', raw)[0] if raw else None
            _b.append(hex(ret) if ret else None)
        except Exception:
            pass

    s.at(V8RET, on_vret)
    s.at(VDEDRET, on_dret)
    s.at(V8SYNTH, lambda uc, a, sz, d: on_fork(uc, a, sz, d))
    s.at(VMENU, lambda uc, a, sz, d: on_fork(uc, a, sz, d))
    s.at(E58770, on_b)
    s.at(E54A2, on_b)
    s.at(0x400e7020, on_b)
    out = {'track': track}
    select(r, track)
    if convert_slot is not None:
        open_modal(r, convert_slot)
        r.key('YES', hold=15, after=600)
        out['converted'] = (r.slot() == -1 and
                            r.state(convert_slot) == 1)
        select(r, track)
    # T-press for the selected state (a bare ACTIVE match leaves the
    # panel on main; the menu opens reliably only from selected state).
    s.press(s.code('T%d' % (track % 4 + 1)))
    s.run_ms(120)
    s.release(s.code('T%d' % (track % 4 + 1)))
    s.run_ms(300)
    out['active_at_press'] = u32(m, B.ACTIVE)
    h0 = sha(fb(m, s))
    for _ in range(6):
        s.press(s.code('VOICE'))
        s.run_ms(120)
        s.release(s.code('VOICE'))
        s.run_ms(300)
        if bld or sha(fb(m, s)) != h0:
            break
    buf = r.settle_fb()
    hb = sha(buf)
    out['fb_changed'] = (hb != h0)
    out['menu_fb'] = hb[:16]
    out['v8_verdict'] = list(vret)
    out['ded70_verdict'] = list(dret)
    out['synth_fork'] = len(fork)
    out['builders'] = list(bld)
    if png_path:
        panel.write_png(buf, png_path)
        out['png'] = png_path
    return out


def leg_open():
    use_build(BUILD)
    out = {'leg': 'open', 'tag': BUILD['tag'], 'build': BUILD['tag'],
           'sides': {}}
    pngdir = os.environ.get('CNV_PNGDIR')
    for track, conv, png in ((0, None, 'menu_nat0_18.png'),
                            (4, 0, 'menu_conv4_18.png'),
                            (5, None, 'menu_nat5_18.png')):
        r = B.Run(audio=False)
        try:
            c = _menu_capture(
                r, track, conv,
                os.path.join(pngdir, png) if pngdir else None,
                png)
        finally:
            r.close()
        out['sides'][track] = c
    n0, c4 = out['sides'][0], out['sides'][4]
    # Parity assertions: converted takes the same synth-builder chain.
    out['conv_takes_synth_fork'] = c4['synth_fork'] > 0
    out['conv_builder_is_408e4'] = '0x400408e4' in c4['builders']
    out['native_builder_is_408e4'] = '0x400408e4' in n0['builders']
    out['v8_diverts_converted'] = (0 in c4['v8_verdict'] and
                                   len(c4['v8_verdict']) > 0)
    out['v8_native_stock'] = (all(v == 3200873472 for v in n0['v8_verdict'])
                              and len(n0['v8_verdict']) > 0)
    nbuf = c4.get('png') and None
    out['wall'] = 'see per-side sessions'
    return out


def leg_regmodal():
    use_build(BUILD)
    r = B.Run(audio=False)
    out = {'leg': 'regmodal', 'tag': BUILD['tag']}
    r.ensure_active(4)
    r.open_modal(0)
    out['modal_opens'] = (r.slot() == 0)
    s0 = r.state(0)
    r.key('#14', hold=15, after=200)
    out['cancel_idle'] = (r.slot() == -1 and r.state(0) == s0)
    r.ensure_active(0)
    out['voice_menu'] = press_voice(r) is not None
    r.close()
    out['wall'] = r.wall
    return out


def leg_regbrowser():
    use_build(BUILD)
    single = B.leg_single()
    kit = B.leg_kit()
    return {'leg': 'regbrowser', 'tag': BUILD['tag'],
            'single': single, 'kit': kit}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--leg', choices=('regs4', 'routeA', 'routeB',
                                      'routeC1', 'routeC2', 'open',
                                      'regmodal', 'regbrowser'),
                    required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--tag', type=int, default=None,
                    help='rebind to another linked build tag (needs --folder'
                    ' and --map; sha read from folder firmware.json)')
    ap.add_argument('--folder', default=None)
    ap.add_argument('--map', default=None)
    args = ap.parse_args()
    if args.tag is not None:
        assert args.folder and args.map, '--tag needs --folder and --map'
        with open(os.path.join(args.folder, 'firmware.json')) as fh:
            rec = json.load(fh)
        sha = ((rec.get('release') or {}).get('sha256') or rec.get('sha256')
               or rec.get('syx_sha256'))
        use_build({'tag': args.tag, 'syx_sha': sha,
                   'folder': args.folder, 'map': args.map})
    fn = {'regs4': leg_regs4, 'routeA': leg_routeA, 'routeB': leg_routeB,
          'routeC1': leg_routeC1, 'routeC2': leg_routeC2,
          'open': leg_open, 'regmodal': leg_regmodal,
          'regbrowser': leg_regbrowser}[args.leg]
    rep = fn()
    with open(args.out, 'w') as fh:
        json.dump(rep, fh, indent=1, default=str)
    print('%s wall=%s' % (args.leg, rep.get('wall')))
    if args.leg == 'regs4':
        for c in rep['cells']:
            print('ctx=%-15s t=%s fb=%s s3=%s s4=%s %s/%s %s' % (
                c.get('ctx'), c.get('track'), c.get('fb_changed'),
                c.get('s3_d4'), c.get('s4_d2'), c.get('s3_proven'),
                c.get('s4_proven'), c.get('blocked', '')))


if __name__ == '__main__':
    main()
