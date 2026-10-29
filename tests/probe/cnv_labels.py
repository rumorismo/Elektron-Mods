#!/usr/bin/env python3
"""Label parity proof for dn-convert (8track-engine task 3.3).

S6 0x400bbd84 ("TRK.%d" vs FX fork, compared reg d6) + S7 0x40061ce4
("T%d" vs "XX"/"M%d" fork, compared reg d3) are UNPROVEN spike notes:
register = track must be proven on label draws for native 0-3 and
converted 4-7 across page contexts BEFORE patching (no blind patches).
Playbook = 3.2 (cnv_voicemenu.py): the prescribed S3/S4 turned out NOT
to be on the plain-VOICE path (proven silent, left stock); the live
dispatch was found dynamically (V8) and interposed instead. Same here:
if a site never executes, it stays stock and the live site is found.

Mod RAM truth for classification; framebuffer hashes + PNG captures
(viewed, not hashed) for the label pixels.

Legs (run from tools/digiemu with its venv; needs emu.*, unicorn):
  stock : stock bytes at S6/S7 sites + format strings present in image.
  disc  : discovery sweep: hook S6/S7 entries + forks, log
          (site, compared-reg, ACTIVE, fork) across gestures x contexts
          on native track 0 and converted track 4. Finds which gestures
          draw labels.
  proof : targeted per-track cells (default tracks 0-7) in the firing
          contexts: proves compared-reg == track/ACTIVE + fork taken.
  fb    : settled fb hashes + PNG captures (native 0, converted 4,
          native-MIDI 5) documenting current label rendering.

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
import cnv_voicemenu as V  # noqa: E402
from emu import panel  # noqa: E402
from unicorn.m68k_const import (UC_M68K_REG_A5, UC_M68K_REG_A7,  # noqa: E402
                                UC_M68K_REG_D0, UC_M68K_REG_D1,
                                UC_M68K_REG_D2, UC_M68K_REG_D3,
                                UC_M68K_REG_D4, UC_M68K_REG_D5,
                                UC_M68K_REG_D6, UC_M68K_REG_D7)

S6 = 0x400bbd84
S6_SYNTH = 0x400bbd8a
S6_MIDI = 0x400bbd9a
S7 = 0x40061ce4
S7_SYNTH = 0x40061cea
S7_MIDI = 0x40061d12
# S7 family siblings (same "T%d"+"XX"/"M%d" label shape, found by
# string-xref): L2 = unconditional T-draw (no fork), L3 = fork with
# the bound in d6 and the track in a5 (cmp.l a5,d6; blt).
L2 = 0x4008393a
L3 = 0x400c28c2
L3_SYNTH = 0x400c28c6
L3_MIDI = 0x400c28ec
# H1 = voice-menu header "TRK.%c" (0x401dcd8f) draw at 0x4006365c:
# value pushed from d0 just before (0x4006365a move.l d0,-(sp)).
H1 = 0x4006365c
# R0 = shared label renderer 0x400de32c (a3 target at L2/L3/S7/S6
# family draws). At entry the pushed fmt pointer sits somewhere in
# [sp+4, sp+48); the %d/%c value is the word just above it (pushed
# earlier). Scan for the known fmt addrs and record (fmt, value).
R0 = 0x400de32c
R0_FMTS = {
    0x401e1e6d: 'TRK.%d',
    0x401da9fa: 'FX',
    0x401dc677: 'T%d',
    0x401dc67f: 'XX',
    0x401dcc71: 'M%d',
    0x401dcd8f: 'TRK.%c',
}
# Mod .rodata range (convert .run image): resolve "b%d" etc. dynamically.
# E5 = voice-menu content builder 0x40158770 (V8 chain + S3 synth fork
# target family). Log the full d-reg set at entry to find the track flow
# into the header draw.
E5 = 0x40158770

BUILD18 = {
    'tag': 1481,
    'syx_sha': ('647d35bb1f7c9e5e9f4c8d0e4f9b8e8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8'),
    'folder': ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
               'portable/firmware/dn1-1481-647d35bb'),
    'map': ('/home/nuke/Documents/Elektron-MODS/firmware/'
            'test-cnv18.syx.map.json'),
}

BUILD19 = {
    'tag': 1482,
    'syx_sha': ('f7466c0a9f99daff1e6723558114141a9e23fbd41f25f1fb517b2ce709de4914'),
    'folder': ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
               'portable/firmware/dn1-1482-f7466c0a'),
    'map': ('/home/nuke/Documents/Elektron-MODS/firmware/'
            'test-cnv19.syx.map.json'),
}

BUILD = dict(BUILD19)


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


def leg_stock():
    use_build(BUILD)
    r = B.Run(audio=False)
    m = r.s.m
    out = {'leg': 'stock', 'tag': BUILD['tag'], 's6': hex(S6),
           's7': hex(S7)}
    out['s6_bytes'] = (m.peek(S6, 6) or b'').hex()
    out['s7_bytes'] = (m.peek(S7, 6) or b'').hex()
    out['s6_expect'] = '7003b0866d10'
    out['s7_expect'] = '7003b0836d28'
    out['s6_match'] = (out['s6_bytes'] == out['s6_expect'])
    out['s7_match'] = (out['s7_bytes'] == out['s7_expect'])
    strs = {}
    for name, addr in (('TRK.%d', 0x401e1e6d), ('FX', 0x401da9fa),
                       ('T%d', 0x401dc677), ('XX', 0x401dc67f),
                       ('M%d', 0x401dcc71)):
        raw = m.peek(addr, 16) or b''
        strs[name] = repr(bytes(raw).split(b'\x00')[0].decode('latin1'))
    out['strings'] = strs
    r.close()
    out['wall'] = r.wall
    return out


class Taps:
    """One session, hooks on S6/S7 entries + forks, gesture cells."""

    def __init__(self, tag):
        use_build(BUILD)
        self.r = B.Run(audio=False)
        self.out = {'build': '0.18', 'tag': tag, 'cells': []}
        s = self.r.s
        self.hits = []
        m = s.m

        def mk(site, reg, fork):
            def cb(uc, a, sz, d):
                if len(self.hits) < 400:
                    try:
                        self.hits.append(
                            {'site': site,
                             'reg': int(uc.reg_read(reg)),
                             'active': u32(m, B.ACTIVE)})
                    except Exception:
                        pass
            return cb

        s.at(S6, mk('s6', UC_M68K_REG_D6, None))
        s.at(S6_SYNTH, mk('s6synth', UC_M68K_REG_D6, None))
        s.at(S6_MIDI, mk('s6midi', UC_M68K_REG_D6, None))
        s.at(S7, mk('s7', UC_M68K_REG_D3, None))
        s.at(S7_SYNTH, mk('s7synth', UC_M68K_REG_D3, None))
        s.at(S7_MIDI, mk('s7midi', UC_M68K_REG_D3, None))

    def convert_all(self):
        """Establish MIDI-bank memory per slot while native, then convert."""
        for slot in range(4):
            V.select(self.r, 4 + slot)
        for slot in range(4):
            V.select(self.r, 4 + slot)
            V.open_modal(self.r, slot)
            self.r.key('YES', hold=15, after=600)
            assert self.r.slot() == -1 and self.r.state(slot) == 1, \
                'convert slot %d failed' % slot
        self.out['converted'] = [self.r.state(i) for i in range(4)]

    def cell(self, ctx, nav, track, gestures=('VOICE',)):
        r = self.r
        s = r.s
        c = {'ctx': ctx, 'track': track}
        try:
            if nav:
                r.key(nav, hold=120, after=300)
            V.select(r, track)
            c['active_at_press'] = u32(s.m, B.ACTIVE)
            del self.hits[:]
            h0 = sha(fb(s.m, s))
            # Select-time draws: drain a settle window first.
            s.run_ms(400)
            pre = list(self.hits)
            for g in gestures:
                if g == 'SETTLE':
                    s.run_ms(400)
                    continue
                for _ in range(3):
                    s.press(s.code(g))
                    s.run_ms(120)
                    s.release(s.code(g))
                    s.run_ms(300)
                    if sha(fb(s.m, s)) != h0 or len(self.hits) > len(pre):
                        break
            hb = sha(r.settle_fb())
            c['fb_changed'] = (hb != h0)
            c['menu_fb'] = hb[:16]
            c['hits'] = list(self.hits)
            # Summarise per site: distinct regs, actives, fork counts.
            summ = {}
            for h in self.hits:
                e = summ.setdefault(h['site'], {'regs': set(),
                                                'actives': set(), 'n': 0})
                e['regs'].add(h['reg'])
                e['actives'].add(h['active'])
                e['n'] += 1
            c['summary'] = {k: {'regs': sorted(v['regs']),
                                'actives': sorted(v['actives']),
                                'n': v['n']}
                            for k, v in summ.items()}
        except Exception as e:
            c['blocked'] = '%s: %s' % (type(e).__name__, e)
        self.out['cells'].append(c)
        r.key('NO', hold=120, after=300)
        r.key('NO', hold=120, after=300)

    def close(self):
        self.r.close()
        self.out['wall'] = self.r.wall
        return self.out


DISC_CTXS = [('main', None), ('voice-menu', 'VOICE'),
             ('ptn-menu', 'PTN'), ('global-settings', 'GLOBAL'),
             ('song-menu', 'SONG')]
DISC_GESTURES = ('VOICE', 'SETTLE')


def leg_disc():
    t = Taps(BUILD['tag'])
    t.out['leg'] = 'disc'
    t.convert_all()
    for (ctx, nav) in DISC_CTXS:
        t.cell(ctx, nav, 0, gestures=DISC_GESTURES)
    for (ctx, nav) in DISC_CTXS:
        t.cell(ctx, nav, 4, gestures=DISC_GESTURES)
    # T-select draws on both banks (no VOICE): labels may redraw on select.
    r = t.r
    s = r.s
    for track in (1, 5):
        c = {'ctx': 't-select', 'track': track}
        try:
            del t.hits[:]
            h0 = sha(fb(s.m, s))
            V.select(r, track)
            s.run_ms(500)
            hb = sha(r.settle_fb())
            c['fb_changed'] = (hb != h0)
            c['menu_fb'] = hb[:16]
            c['hits'] = list(t.hits)
        except Exception as e:
            c['blocked'] = '%s: %s' % (type(e).__name__, e)
        t.out['cells'].append(c)
    return t.close()


def leg_proof(tracks=(0, 1, 2, 3, 4, 5, 6, 7), ctxs=('main', 'voice-menu')):
    navmap = dict(DISC_CTXS)
    t = Taps(BUILD['tag'])
    t.out['leg'] = 'proof'
    t.convert_all()
    for ctx in ctxs:
        for track in tracks:
            t.cell(ctx, navmap.get(ctx), track,
                   gestures=DISC_GESTURES)
    # Verdicts per cell: compared-reg == ACTIVE-at-press?
    for c in t.out['cells']:
        v = []
        for h in c.get('hits', []):
            if h['site'] in ('s6', 's7'):
                v.append(h['reg'] == c.get('active_at_press'))
        c['compared_is_active'] = (bool(v) and all(v)) if v else None
    return t.close()


def leg_fb():
    use_build(BUILD)
    out = {'leg': 'fb', 'tag': BUILD['tag'], 'sides': {}}
    pngdir = os.environ.get('CNV_PNGDIR')
    for track, conv, png in ((0, None, 'lbl_nat0.png'),
                             (4, 0, 'lbl_conv4.png'),
                             (5, None, 'lbl_nat5.png')):
        r = B.Run(audio=False)
        try:
            s = r.s
            V.select(r, track)
            if conv is not None:
                V.open_modal(r, conv)
                r.key('YES', hold=15, after=600)
                V.select(r, track)
            s.press(s.code('T%d' % (track % 4 + 1)))
            s.run_ms(120)
            s.release(s.code('T%d' % (track % 4 + 1)))
            s.run_ms(300)
            # Voice menu open (outcome-verified), where labels draw.
            h0 = sha(fb(s.m, s))
            for _ in range(6):
                s.press(s.code('VOICE'))
                s.run_ms(120)
                s.release(s.code('VOICE'))
                s.run_ms(300)
                if sha(fb(s.m, s)) != h0:
                    break
            buf = r.settle_fb()
            hb = sha(buf)
            e = {'fb_changed': (hb != h0), 'menu_fb': hb[:16],
                 'active': u32(s.m, B.ACTIVE)}
            if pngdir:
                p = os.path.join(pngdir, png)
                panel.write_png(buf, p)
                e['png'] = p
            out['sides'][track] = e
        finally:
            r.close()
    out['wall'] = 'see per-side sessions'
    return out


CAPS = (
    # (name, base, convert_slot, opener_keys, walks)
    ('menu_nat0', 0, None, ('VOICE',), ()),
    ('menu_conv4', 4, 0, ('VOICE',), ()),
    ('menu_nat5', 5, None, ('VOICE',), ()),
    ('kbd_nat0', 0, None, ('KEYBOARD',), ()),
    ('kbd_conv4', 4, 0, ('KEYBOARD',), ()),
    ('kbd_nat5', 5, None, ('KEYBOARD',), ()),
    ('scale_nat0', 0, None, ('FUNC+PAGE',), ()),
    ('scale_conv4', 4, 0, ('FUNC+PAGE',), ()),
    ('menu_nat1', 1, None, ('VOICE',), ()),
    ('menu_nat2', 2, None, ('VOICE',), ()),
)


def leg_caps(which=None):
    """Outcome-verified screen captures for pixel analysis.

    Each capture = fresh Session: select base, optional convert, open
    the screen (retry until fb moves), settle, hash + PNG.
    """
    use_build(BUILD)
    out = {'leg': 'caps', 'tag': BUILD['tag'], 'caps': {}}
    pngdir = os.environ.get('CNV_PNGDIR', '/tmp/opencode')
    for name, base, conv, openers, walks in CAPS:
        if which and name != which:
            continue
        r = B.Run(audio=False)
        try:
            s = r.s
            V.select(r, base)
            if conv is not None:
                V.open_modal(r, conv)
                r.key('YES', hold=15, after=600)
                V.select(r, base)
            h0 = sha(fb(s.m, s))
            for op in openers:
                if '+' in op:
                    held, tapped = op.split('+')
                    s.press(s.code(held))
                    s.run_ms(80)
                    s.press(s.code(tapped))
                    s.run_ms(150)
                    s.release(s.code(tapped))
                    s.run_ms(200)
                    s.release(s.code(held))
                    s.run_ms(400)
                else:
                    for _ in range(4):
                        s.press(s.code(op))
                        s.run_ms(120)
                        s.release(s.code(op))
                        s.run_ms(300)
                        if sha(fb(s.m, s)) != h0:
                            break
            for w in walks:
                r.key(w, hold=120, after=300)
            buf = r.settle_fb()
            hb = sha(buf)
            p = os.path.join(pngdir, 'cap_%s.png' % name)
            panel.write_png(buf, p)
            out['caps'][name] = {'opened': (hb != h0), 'fb': hb[:16],
                                 'active': u32(s.m, B.ACTIVE), 'png': p}
        finally:
            r.close()
    out['wall'] = 'see per-side sessions'
    return out


SWEEP_KEYS = ('T1', 'T2', 'T3', 'T4', 'VOICE', 'SYN1', 'SYN2', 'FLTR',
              'AMP', 'LFO', 'TRIG', 'PAGE', 'PTN', 'SONG', 'GLOBAL',
              'BANK', 'FUNC', 'KEYBOARD', 'TEMPO', 'LEFT', 'RIGHT',
              'UP', 'DOWN', 'YES')


def _home(r):
    """Best-effort return to main: NO storm + settle."""
    s = r.s
    for _ in range(4):
        s.press(s.code('NO'))
        s.run_ms(80)
        s.release(s.code('NO'))
        s.run_ms(120)
    s.run_ms(300)


CHORD_KEYS = ('FUNC+PAGE', 'FUNC+YES', 'FUNC+TRIG', 'FUNC+PTN',
              'FUNC+BANK', 'FUNC+SONG', 'FUNC+GLOBAL', 'FUNC+VOICE',
              'PTN>DOWN', 'PTN>YES', 'GLOBAL>DOWN', 'GLOBAL>YES',
              'SONG>DOWN', 'SONG>YES', 'SONG>RIGHT', 'VOICE>DOWN',
              'VOICE>UP', 'VOICE>YES', 'SYN1>YES', 'TRIG>YES',
              'PLAY', 'PLAY2STOP', 'MIDI',
              'VOICE>RIGHT', 'VOICE>LEFT', 'SYN1>RIGHT', 'FLTR>RIGHT',
              'PTN>RIGHT', 'PTN>UP', 'GLOBAL>YES>DOWN', 'SONG>UP',
              'KEYBOARD+T1', 'FUNC+LEFT', 'FUNC+RIGHT', 'FUNC+UP',
              'FUNC+DOWN', 'YES>DOWN')


def leg_sweep(converted=False, keys=SWEEP_KEYS, args_base=None):
    """Wide gesture sweep in ONE session, NO selection changes mid-sweep.

    Native: ACTIVE stays 0 (T-taps reselect 0-3 freely, reselect 0 after).
    Converted: slot 0 converted up front, ACTIVE stays 4 (T-taps inside
    the voice menu recover via MIDI toggle, never T-press).
    Per gesture: clear hits, press, settle, record hits + fb.
    Chord keys (FUNC+X) and submenu walks (MENU>KEY) are scripted;
    V8 (0x4003f642, fires on every plain VOICE) is the hook-control.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'sweep', 'converted': converted, 'tag': BUILD['tag'],
           'gestures': []}
    hits = []

    def on_hit(site, reg):
        def cb(uc, a, sz, d):
            if len(hits) < 200:
                try:
                    hits.append({'site': site,
                                 'reg': int(uc.reg_read(reg)),
                                 'active': u32(s.m, B.ACTIVE)})
                except Exception:
                    pass
        return cb

    s.at(S6, on_hit('s6', UC_M68K_REG_D6))
    s.at(S6_SYNTH, on_hit('s6synth', UC_M68K_REG_D6))
    s.at(S6_MIDI, on_hit('s6midi', UC_M68K_REG_D6))
    s.at(S7, on_hit('s7', UC_M68K_REG_D3))
    s.at(S7_SYNTH, on_hit('s7synth', UC_M68K_REG_D3))
    s.at(S7_MIDI, on_hit('s7midi', UC_M68K_REG_D3))
    s.at(L2, on_hit('l2', UC_M68K_REG_D7))
    # L3 compares cmp.l a5,d6 (d6 = 3 bound, a5 = track): log the TRACK.
    s.at(L3, on_hit('l3', UC_M68K_REG_A5))
    s.at(L3_SYNTH, on_hit('l3synth', UC_M68K_REG_A5))
    s.at(L3_MIDI, on_hit('l3midi', UC_M68K_REG_A5))
    # H1 "TRK.%c": the %c value was just pushed from d0; d0 still live.
    s.at(H1, on_hit('h1', UC_M68K_REG_D0))
    r0fmts = dict(R0_FMTS)

    def on_r0(uc, a, sz, d):
        if len(hits) < 60:
            try:
                sp = uc.reg_read(UC_M68K_REG_A7)
                words = []
                for k in range(1, 13):
                    raw = s.m.peek(sp + 4 * k, 4)
                    if not raw or len(raw) < 4:
                        break
                    import struct as _S
                    words.append(_S.unpack('>I', raw)[0])
                fmts = [(i, r0fmts[w]) for i, w in enumerate(words)
                        if w in r0fmts]
                # Mod .rodata strings (e.g. "b%d" at cnv_bfmt): resolve
                # any word pointing into the mod image to its string.
                for i, w in enumerate(words):
                    if 0x43ec0000 <= w < 0x43ec4000:
                        try:
                            raw = s.m.peek(w, 8) or b''
                            t = bytes(raw).split(b'\x00')[0]
                            if (len(t) >= 2 and len(t) <= 7 and
                                    all(32 <= c < 127 for c in t)):
                                fmts.append((i, t.decode('latin1')))
                        except Exception:
                            pass
                hits.append({'site': 'r0',
                             'reg': words[0] & 0xFFFFFFFF,
                             'active': u32(s.m, B.ACTIVE),
                             'fmts': fmts,
                             'words': ['%x' % w for w in words]})
            except Exception:
                pass

    s.at(R0, on_r0)
    def on_e5(uc, a, sz, d):
        if len(hits) < 40:
            try:
                import struct as _S
                regs = [int(uc.reg_read(r)) for r in
                        (UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2,
                         UC_M68K_REG_D3, UC_M68K_REG_D4, UC_M68K_REG_D5,
                         UC_M68K_REG_D6, UC_M68K_REG_D7)]
                sp = uc.reg_read(UC_M68K_REG_A7)
                raw = s.m.peek(sp, 4)
                ret = _S.unpack('>I', raw)[0] if raw else None
                hits.append({'site': 'e5', 'reg': regs[0],
                             'active': u32(s.m, B.ACTIVE),
                             'dregs': regs,
                             'caller': (hex(ret) if ret else None)})
            except Exception:
                pass

    s.at(E5, on_e5)
    s.at(0x4003f642, on_hit('v8ctl', UC_M68K_REG_D0))

    base = 0 if not converted else 4
    if args_base is not None:
        base = args_base
    V.select(r, base)
    if converted:
        V.open_modal(r, base - 4)
        r.key('YES', hold=15, after=600)
        assert r.slot() == -1 and r.state(base - 4) == 1, 'YES did not flip'
        V.midi_to_bank(r, True)
    out['active_start'] = u32(s.m, B.ACTIVE)
    main_fb = sha(r.settle_fb())
    out['main_fb'] = main_fb[:16]

    for key in keys:
        g = {'key': key}
        try:
            del hits[:]
            h0 = sha(fb(s.m, s))
            if '+' in key and '>' not in key and key not in ('VOICE+T',):
                held, tapped = key.split('+')
                s.press(s.code(held))
                s.run_ms(80)
                s.press(s.code(tapped))
                s.run_ms(150)
                s.release(s.code(tapped))
                s.run_ms(200)
                s.release(s.code(held))
                s.run_ms(500)
            elif '>' in key:
                parts = key.split('>')

                def _press(name):
                    if '+' in name:
                        held, tapped = name.split('+')
                        s.press(s.code(held))
                        s.run_ms(80)
                        s.press(s.code(tapped))
                        s.run_ms(150)
                        s.release(s.code(tapped))
                        s.run_ms(200)
                        s.release(s.code(held))
                        s.run_ms(400)
                    else:
                        s.press(s.code(name))
                        s.run_ms(120)
                        s.release(s.code(name))
                        s.run_ms(400)

                menu = parts[0]
                _press(menu)
                s.run_ms(100)
                for sub in parts[1:]:
                    if sub == 'T':
                        sub = 'T%d' % (base % 4 + 1)
                    _press(sub)
                    s.run_ms(100)
            elif key == 'VOICE+T':
                # Open the voice menu, then T-switch inside it (label
                # redraw candidate), then close.
                s.press(s.code('VOICE'))
                s.run_ms(120)
                s.release(s.code('VOICE'))
                s.run_ms(400)
                other = 'T2' if base == 0 else None
                if other is not None:
                    s.press(s.code(other))
                    s.run_ms(120)
                    s.release(s.code(other))
                    s.run_ms(400)
            elif key == 'ENC-A':
                s.turn('A', 2, 300)
                s.run_ms(300)
            elif key == 'PLAY2STOP':
                s.press(s.code('PLAY'))
                s.run_ms(120)
                s.release(s.code('PLAY'))
                s.run_ms(1500)
                s.press(s.code('STOP'))
                s.run_ms(120)
                s.release(s.code('STOP'))
                s.run_ms(500)
            else:
                s.press(s.code(key))
                s.run_ms(120)
                s.release(s.code(key))
                s.run_ms(500)
            g['fb'] = sha(r.settle_fb())[:16]
            g['fb_changed'] = (g['fb'] != h0[:16])
            g['active'] = u32(s.m, B.ACTIVE)
            g['hits'] = list(hits)
        except Exception as e:
            g['blocked'] = '%s: %s' % (type(e).__name__, e)
        out['gestures'].append(g)
        try:
            _home(r)
            if converted:
                V.midi_to_bank(r, True)
            else:
                V.select(r, base)
        except Exception as e:
            out.setdefault('recover_blocked', []).append(
                '%s after %s: %s' % (type(e).__name__, key, e))
            break
    out['active_end'] = u32(s.m, B.ACTIVE)
    r.close()
    out['wall'] = r.wall
    return out


def leg_fixreg():
    """Post-patch regression subset on 0.19 (reuses proven 3.1/3.2 legs).

    Voice-menu open parity (V8 divert + ded70 + 58770 caller +
    synth-fork taken + settled fb + PNGs), modal open/NO-cancel, and
    browser single-tap + kit-identity — all rebound to the new build.
    """
    use_build(BUILD)
    V.use_build(dict(BUILD))
    out = {'leg': 'fixreg', 'tag': BUILD['tag']}
    t0 = __import__('time').time()
    out['open'] = V.leg_open()
    out['regmodal'] = V.leg_regmodal()
    out['regbrowser'] = V.leg_regbrowser()
    out['wall'] = round(__import__('time').time() - t0, 1)
    return out


def leg_fixkbd(slots=(0, 1, 2, 3)):
    """Post-patch label proof (0.19, L3 divert) in ONE session.

    Natives first (0, 2, 5: T-select works), then sequential convert +
    prove per slot (ACTIVE stays 4+i; no backward travel needed).
    Per track: KEYBOARD open (outcome-verified), L3 fork + R0 windows
    (fmt + value). Converted must show the mod "b%d" fmt with slot+1;
    natives keep stock "T%d"/"M%d".
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'fixkbd', 'tag': BUILD['tag'], 'cells': []}
    hits = []

    def on_hit(site, reg):
        def cb(uc, a, sz, d):
            if len(hits) < 200:
                try:
                    hits.append({'site': site,
                                 'reg': int(uc.reg_read(reg)),
                                 'active': u32(s.m, B.ACTIVE)})
                except Exception:
                    pass
        return cb

    s.at(S6, on_hit('s6', UC_M68K_REG_D6))
    s.at(S6_SYNTH, on_hit('s6synth', UC_M68K_REG_D6))
    s.at(S6_MIDI, on_hit('s6midi', UC_M68K_REG_D6))
    s.at(L3, on_hit('l3', UC_M68K_REG_A5))
    s.at(L3_SYNTH, on_hit('l3synth', UC_M68K_REG_A5))
    s.at(L3_MIDI, on_hit('l3midi', UC_M68K_REG_A5))
    s.at(R0, on_r0_with(s, hits))

    # Mod .rodata fmt resolution for R0 windows (shared with on_r0).
    def kbd_cell(track, conv_slot=None, preselected=False):
        c = {'track': track}
        pngdir = os.environ.get('CNV_PNGDIR')
        try:
            # NOTE: no re-select for converted slots: the caller selects
            # while native (bank memory) before converting; a post-convert
            # T-select would hit the B0 divert and lose ACTIVE. Native
            # cells select normally.
            if not preselected:
                V.select(r, track)
            if conv_slot is not None:
                # Inline chord (no re-select: ACTIVE is already the
                # slot; V.open_modal would re-select and hit the B0
                # divert on converted slots).
                for _ in range(4):
                    s.press(s.code('MIDI'))
                    s.run_ms(50)
                    s.press(s.code('VOICE'))
                    s.run_ms(30)
                    s.release(s.code('VOICE'))
                    s.run_ms(50)
                    s.release(s.code('MIDI'))
                    el = 0
                    while el < 800:
                        if r.slot() == conv_slot:
                            break
                        s.run_ms(100)
                        el += 100
                    if r.slot() == conv_slot:
                        break
                assert r.slot() == conv_slot, 'modal did not open'
                r.key('YES', hold=15, after=600)
                assert (r.slot() == -1 and
                        r.state(conv_slot) == 1), 'YES did not flip'
                # The chord's MIDI press toggles ACTIVE to the synth bank
                # as a side effect; ride the toggle back (bank memory is
                # intact — toggles never write it).
                V.midi_to_bank(r, True)
            # Outcome-verified KEYBOARD open (200 ms holds: the scan
            # misses shorter ones on this screen). Clear first: the
            # label draws happen during the open presses.
            del hits[:]
            h0 = sha(fb(s.m, s))
            for _ in range(6):
                s.press(s.code('KEYBOARD'))
                s.run_ms(200)
                s.release(s.code('KEYBOARD'))
                s.run_ms(400)
                if sha(fb(s.m, s)) != h0:
                    break
            s.run_ms(500)
            buf = r.settle_fb()
            c['fb'] = sha(buf)[:16]
            c['active'] = u32(s.m, B.ACTIVE)
            l3 = [h for h in hits if h['site'] in ('l3', 'l3synth',
                                                   'l3midi')]
            r0 = [h for h in hits if h['site'] == 'r0']
            c['l3'] = [(h['site'], h['reg']) for h in l3]
            cw = {}
            wins = []
            for h in r0:
                key = (tuple(f for _, f in h.get('fmts', [])),
                       h['words'][8] if len(h.get('words', [])) > 8
                       else None)
                cw[key] = cw.get(key, 0) + 1
                if any(f in ('b%d', 'T%d', 'M%d')
                       for _, f in h.get('fmts', [])) and len(wins) < 3:
                    wins.append(h['words'])
            c['r0'] = sorted(cw.items(), key=lambda kv: -kv[1])
            c['r0wins'] = wins
            if pngdir:
                p = os.path.join(pngdir, 'cap_fixkbd_t%d.png' % track)
                panel.write_png(buf, p)
                c['png'] = p
        except Exception as e:
            c['blocked'] = '%s: %s' % (type(e).__name__, e)
        out['cells'].append(c)
        _home(r)

    for track in (0, 2, 5):
        kbd_cell(track)
        V.select(r, 0)
    for slot in slots:
        track = 4 + slot
        V.select(r, track)
        kbd_cell(track, conv_slot=slot, preselected=True)
    out['converted'] = [r.state(i) for i in range(4)]

    # Flip-back release proof (last slot, no travel needed): modal
    # chord -> RESTORE/MIDI YES -> STASHED; the transpose row must read
    # the stock MIDI label again (M%d, value track-3) via the replayed
    # stock fork — proving the divert releases cleanly per draw.
    if slots:
        slot = slots[-1]
        track = 4 + slot
        cell = {'track': track, 'flipback': True}
        try:
            for _ in range(4):
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
                        break
                    s.run_ms(100)
                    el += 100
                if r.slot() == slot:
                    break
            assert r.slot() == slot, 'restore modal did not open'
            r.key('YES', hold=15, after=600)
            assert r.slot() == -1 and r.state(slot) == 2, \
                'YES did not flip back (state %s)' % r.state(slot)
            V.midi_to_bank(r, True)
            del hits[:]
            h0 = sha(fb(s.m, s))
            for _ in range(6):
                s.press(s.code('KEYBOARD'))
                s.run_ms(200)
                s.release(s.code('KEYBOARD'))
                s.run_ms(400)
                if sha(fb(s.m, s)) != h0:
                    break
            s.run_ms(500)
            cell['active'] = u32(s.m, B.ACTIVE)
            l3 = [h for h in hits if h['site'] in ('l3', 'l3synth',
                                                   'l3midi')]
            cell['l3'] = [(h['site'], h['reg']) for h in l3]
            cw = {}
            for h in (h for h in hits if h['site'] == 'r0'):
                key = (tuple(f for _, f in h.get('fmts', [])),
                       h['words'][9] if len(h.get('words', [])) > 9
                       else None)
                cw[key] = cw.get(key, 0) + 1
            cell['r0'] = sorted(cw.items(), key=lambda kv: -kv[1])
        except Exception as e:
            cell['blocked'] = '%s: %s' % (type(e).__name__, e)
        out['cells'].append(cell)
        _home(r)
    r.close()
    out['wall'] = r.wall
    return out


def on_r0_with(s, hits):
    """R0 window hook with stock + mod-.rodata fmt resolution."""
    r0fmts = dict(R0_FMTS)

    def on_r0(uc, a, sz, d):
        if len(hits) < 200:
            try:
                sp = uc.reg_read(UC_M68K_REG_A7)
                words = []
                for k in range(12):
                    raw = s.m.peek(sp + 4 * k, 4)
                    if not raw or len(raw) < 4:
                        break
                    import struct as _S
                    words.append(_S.unpack('>I', raw)[0])
                fmts = [(i, r0fmts[w]) for i, w in enumerate(words)
                        if w in r0fmts]
                for i, w in enumerate(words):
                    if 0x43ec0000 <= w < 0x43ec4000:
                        try:
                            raw = s.m.peek(w, 8) or b''
                            t = bytes(raw).split(b'\x00')[0]
                            if (len(t) >= 2 and len(t) <= 7 and
                                    all(32 <= c < 127 for c in t)):
                                fmts.append((i, t.decode('latin1')))
                        except Exception:
                            pass
                hits.append({'site': 'r0',
                             'reg': words[0] & 0xFFFFFFFF,
                             'active': u32(s.m, B.ACTIVE),
                             'fmts': fmts,
                             'words': ['%x' % w for w in words]})
            except Exception:
                pass
    return on_r0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--leg', choices=('stock', 'disc', 'proof', 'fb',
                                    'sweep', 'caps', 'fixkbd', 'fixreg'),
                    required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--tag', type=int, default=None)
    ap.add_argument('--folder', default=None)
    ap.add_argument('--map', default=None)
    ap.add_argument('--tracks', default='0,1,2,3,4,5,6,7')
    ap.add_argument('--ctxs', default='main,voice-menu')
    ap.add_argument('--conv', action='store_true')
    ap.add_argument('--base', type=int, default=None)
    ap.add_argument('--keys', default=None)
    args = ap.parse_args()
    if args.tag is not None:
        assert args.folder and args.map, '--tag needs --folder and --map'
        with open(os.path.join(args.folder, 'firmware.json')) as fh:
            rec = json.load(fh)
        sh = ((rec.get('release') or {}).get('sha256') or rec.get('syx_sha256'))
        use_build({'tag': args.tag, 'syx_sha': sh,
                   'folder': args.folder, 'map': args.map})
    else:
        # Fix the placeholder sha from the build map.
        with open(os.path.join(BUILD['folder'], 'firmware.json')) as fh:
            rec = json.load(fh)
        BUILD['syx_sha'] = ((rec.get('release') or {}).get('sha256')
                            or rec.get('syx_sha256'))
        use_build(BUILD)
    if args.leg == 'stock':
        rep = leg_stock()
    elif args.leg == 'disc':
        rep = leg_disc()
    elif args.leg == 'proof':
        rep = leg_proof(tuple(int(x) for x in args.tracks.split(',')),
                        tuple(x for x in args.ctxs.split(',')))
    elif args.leg == 'sweep':
        keys = (tuple(args.keys.split(',')) if args.keys
                else SWEEP_KEYS + ('VOICE+T', 'ENC-A'))
        rep = leg_sweep(converted=args.conv, keys=keys, args_base=args.base)
    elif args.leg == 'caps':
        rep = leg_caps(which=args.keys)
    elif args.leg == 'fixkbd':
        rep = leg_fixkbd()
    elif args.leg == 'fixreg':
        rep = leg_fixreg()
    else:
        rep = leg_fb()
    with open(args.out, 'w') as fh:
        json.dump(rep, fh, indent=1, default=str)
    print('%s wall=%s' % (args.leg, rep.get('wall')))
    if args.leg in ('disc', 'proof'):
        for c in rep['cells']:
            print('ctx=%-15s t=%s fb=%s active=%s cmp_active=%s %s' % (
                c.get('ctx'), c.get('track'), c.get('fb_changed'),
                c.get('active_at_press'), c.get('compared_is_active'),
                c.get('blocked', '')))
            for site, sm in c.get('summary', {}).items():
                print('    %-8s n=%-4d regs=%s actives=%s' % (
                    site, sm['n'], sm['regs'], sm['actives']))
    if args.leg == 'sweep':
        for g in rep['gestures']:
            hs = {}
            for h in g.get('hits', []):
                e = hs.setdefault(h['site'], {'n': 0, 'regs': set()})
                e['n'] += 1
                e['regs'].add(h['reg'])
            det = ' '.join('%s:n=%d,regs=%s' % (k, v['n'],
                                                sorted(v['regs']))
                           for k, v in hs.items()) or '-'
            print('%-8s fb=%s act=%s %s %s' % (
                g.get('key'), g.get('fb_changed'), g.get('active'),
                det, g.get('blocked', '')))
    if args.leg == 'fixkbd':
        for c in rep['cells']:
            print('t=%s act=%s l3=%s' % (
                c.get('track'), c.get('active'), c.get('l3')))
            for kv, n in c.get('r0', []):
                print('    r0 x%d %s' % (n, kv))
            if c.get('blocked'):
                print('    BLOCKED:', c['blocked'])
        print('converted:', rep.get('converted'))
    if args.leg == 'fixreg':
        o, m, b = rep['open'], rep['regmodal'], rep['regbrowser']
        print('open: conv_fork=%s conv_bld=%s nat_bld=%s v8div=%s v8nat=%s' % (
            o.get('conv_takes_synth_fork'),
            o.get('conv_builder_is_408e4'),
            o.get('native_builder_is_408e4'),
            o.get('v8_diverts_converted'), o.get('v8_native_stock')))
        print('regmodal:', {k: v for k, v in m.items() if k != 'wall'})
        print('regbrowser single converted=%s kit_tail=%s' % (
            b.get('single', {}).get('converted')
            if isinstance(b.get('single'), dict) else b.get('single'),
            str(b.get('kit'))[:200]))


if __name__ == '__main__':
    main()
