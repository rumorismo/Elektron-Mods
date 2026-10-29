#!/usr/bin/env python3
"""MAIN-page parity proof for dn-convert (8track-engine follow-up to 3.4).

Bug: after MIDI+VOICE -> YES convert + double-tap browse + YES apply
(LOADED toast, slot voices), the track MAIN page (TRIG key, SRC view)
still renders the MIDI SRC UI (MID n + LEV/PB/AT/MW/BC) instead of the
synth UI. Task 3.4 proved SYN1/SYN2/FLTR/AMP pages + knob edits via the
P1/P2 page-function divert; the MAIN (SRC) page dispatch is evidently a
separate path that was never interposed.

Playbook = 3.4 (cnv_pages.py): prove-before-patch — the compared-reg
must be proven == ACTIVE/track on MAIN opens before any patch; silent
sites stay stock. Mod RAM truth for classification; framebuffer hashes
+ PNG captures (viewed, not hashed) for the page pixels.

Build: convert 0.23, tag 1486 (test .syx test-cnv23.syx, sibling
firmware/; snapshot dn1-1486-71493c78 persistent in sibling portable/),
then re-verify on the release build (tag 1487) per the task.

Legs (run from tools/digiemu with its venv; needs emu.*, unicorn):
  stock    : S5 0x4003ca70 bytes + fork targets + P_CMP bytes present.
  repro    : bug repro — convert slot 0, browse+apply preset (LOADED:
             SND changes), open MAIN (TRIG) on native t0 / converted t4 /
             native-MIDI t5; report fb hashes + PNGs (which UI renders).
  s5proof  : hook S5 entry + synth/midi forks + P_CMP on TRIG opens for
             native 0 / converted 4 / native-MIDI 5. Verdict per cell:
             S5 fired? compared-reg == ACTIVE-at-press? fork taken?
  trigsweep: TRIG-key track-fork sweep (3.4 idiomsweep adapted): scan
             the MAIN image for the `moveq #3,r; cmp.l; bcc` idiom, hook
             every site, single TRIG press native vs converted. Sites
             firing with compared-reg == ACTIVE on BOTH opens are MAIN
             content/render fork candidates (S5/P_CMP flagged, not
             re-proven).
  mainsynth: post-patch MAIN parity (converted TRIG renders synth UI,
             preset name/values track the applied preset, natives
             unchanged; framebuffer compare where stable).
  fixreg   : 3.4 regression subset rebound to the new build (pageopen /
             knob / timbre / muteseq legs or equivalent).

Each leg = fresh Session(s) from the persistent settled snapshot.
Evidence JSONs + PNGs live OUTSIDE the repo (/tmp/opencode); the .md
next to this file carries the close-out summary.
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
from unicorn.m68k_const import (UC_M68K_REG_D0, UC_M68K_REG_D1,  # noqa: E402
                                UC_M68K_REG_D2, UC_M68K_REG_D3,
                                UC_M68K_REG_D4, UC_M68K_REG_D5,
                                UC_M68K_REG_D6, UC_M68K_REG_D7)

S5 = 0x4003ca70
S5_SYNTH1 = 0x4003ca86
S5_SYNTH2 = 0x4003caa0
S5_MIDI = 0x4003cab2
S5_MIDIFN = 0x400ded80
P_CMP = 0x40042258
P_C6BARET = 0x40042246
P_GATE = 0x40042530

BUILD1486 = {
    'tag': 1486,
    'syx_sha': ('71493c7805566e40c65a801c23dc7c1b1c5c0af17622e85e84a2cfd3e4e2adab'),
    'folder': ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
               'portable/firmware/dn1-1486-71493c78'),
    'map': ('/home/nuke/Documents/Elektron-MODS/firmware/'
            'test-cnv23.syx.map.json'),
}

BUILD1487 = {
    'tag': 1487,
    'syx_sha': ('37c55a1305f816f7172a7e8a790508b2d224f3354224eec495384943da524fc4'),
    'folder': ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
               'portable/firmware/dn1-1487-37c55a13'),
    'map': None,  # release build: resolved via --map at runtime
}

BUILD = dict(BUILD1486)


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


def _home(r):
    s = r.s
    for _ in range(4):
        s.press(s.code('NO'))
        s.run_ms(80)
        s.release(s.code('NO'))
        s.run_ms(120)
    s.run_ms(300)


def _convert_slot0(r):
    """Convert slot 0 in a fresh session; ACTIVE ends on MIDI bank."""
    s = r.s
    V.select(r, 4)
    V.open_modal(r, 0)
    r.key('YES', hold=15, after=600)
    assert r.slot() == -1 and r.state(0) == 1, 'YES did not flip'
    V.midi_to_bank(r, True)
    assert u32(s.m, B.ACTIVE) == 4, 'toggle did not reach t4'


def _browse_apply(r):
    """Open the converted browser, DOWN x2, YES; return snd-change info."""
    out = {}
    SND = B._addr('cnv_synth_snd')
    snd_pre = bytes(r.s.m.peek(SND, 326))
    opened = B3.open_browser(r)
    out['opened'] = opened
    if opened is None:
        out['BLOCKED'] = 'converted browser never drew'
        return out
    for _ in range(2):
        r.key('DOWN', hold=100, after=300)
    out['down_fb'] = sha(r.settle_fb())[:16]
    r.key('YES', hold=100, after=500)
    r.settle_fb()
    out['yes_fb'] = sha(r.settle_fb())[:16]
    snd_post = bytes(r.s.m.peek(SND, 326))
    out['snd_changed'] = (snd_post != snd_pre)
    out['snd_nonzero'] = sum(1 for x in snd_post if x != 0)
    out['snd_sha'] = sha(snd_post)[:16]
    return out


def _trig_open(r, track):
    """Press TRIG once on ACTIVE==track; return settled fb hash + PNG."""
    s = r.s
    assert u32(s.m, B.ACTIVE) == track, 'not on t%d' % track
    h0 = sha(fb(s.m, s))
    s.press(s.code('TRIG'))
    s.run_ms(120)
    s.release(s.code('TRIG'))
    s.run_ms(400)
    buf = r.settle_fb()
    h = sha(buf)
    return {'fb_changed': h != h0, 'fb': h[:16], 'buf': buf}


def leg_stock():
    use_build(BUILD)
    r = B.Run(audio=False)
    m = r.s.m
    out = {'leg': 'stock', 'tag': BUILD['tag'], 's5': hex(S5)}
    out['s5_bytes'] = (m.peek(S5, 6) or b'').hex()
    out['s5_expect'] = '7003b0866d3c'
    out['s5_match'] = (out['s5_bytes'] == out['s5_expect'])
    out['s5_synth1_jsr'] = (m.peek(S5_SYNTH1, 6) or b'').hex()
    out['s5_midi_jsr'] = (m.peek(S5_MIDI + 2, 6) or b'').hex()
    out['s5_midi_jsr_expect'] = '4eb9400ded80'
    out['pcmp_bytes'] = (m.peek(P_CMP, 6) or b'').hex()
    r.close()
    out['wall'] = r.wall
    return out


def leg_repro():
    """Bug repro: native t0 TRIG, convert + browse/apply, converted t4
    TRIG, native-MIDI t5 TRIG. Reports which UI each MAIN page renders."""
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'repro', 'tag': BUILD['tag']}
    pngdir = os.environ.get('CNV_PNGDIR')
    try:
        V.select(r, 0)
        c = _trig_open(r, 0)
        out['nat0_trig'] = {k: v for k, v in c.items() if k != 'buf'}
        if pngdir:
            p = os.path.join(pngdir, 'cap_main_nat0_trig.png')
            panel.write_png(c['buf'], p)
            out['nat0_trig']['png'] = p
        _home(r)

        _convert_slot0(r)
        out['converted'] = [r.state(i) for i in range(4)]
        ba = _browse_apply(r)
        out['apply'] = ba
        if ba.get('BLOCKED'):
            out['BLOCKED'] = ba['BLOCKED']
            r.close()
            out['wall'] = r.wall
            return out
        V.midi_to_bank(r, True)
        c = _trig_open(r, 4)
        out['conv4_trig'] = {k: v for k, v in c.items() if k != 'buf'}
        if pngdir:
            p = os.path.join(pngdir, 'cap_main_conv4_trig.png')
            panel.write_png(c['buf'], p)
            out['conv4_trig']['png'] = p
        _home(r)

        V.select(r, 5)
        c = _trig_open(r, 5)
        out['mid5_trig'] = {k: v for k, v in c.items() if k != 'buf'}
        if pngdir:
            p = os.path.join(pngdir, 'cap_main_mid5_trig.png')
            panel.write_png(c['buf'], p)
            out['mid5_trig']['png'] = p

        out['conv_is_nat'] = (out['conv4_trig']['fb'] ==
                              out['nat0_trig']['fb'])
        out['conv_is_mid'] = (out['conv4_trig']['fb'] ==
                              out['mid5_trig']['fb'])
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_s5proof(tracks=(0, 4, 5)):
    """S5 vs P_CMP on TRIG opens. Converted slots converted in-track-order
    in ONE session; natives select normally; converted reached via the
    MIDI toggle. Verdict per cell: S5 fired? compared-reg == ACTIVE?"""
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 's5proof', 'tag': BUILD['tag'],
           'tracks': list(tracks), 'cells': []}
    hits = []

    def on_hit(site, regs):
        def cb(uc, a, sz, d):
            if len(hits) < 300:
                try:
                    e = {'site': site,
                         'active': u32(s.m, B.ACTIVE)}
                    for nm, rg in regs:
                        e[nm] = int(uc.reg_read(rg))
                    hits.append(e)
                except Exception:
                    pass
        return cb

    DREGS = (('d0', UC_M68K_REG_D0), ('d1', UC_M68K_REG_D1),
             ('d2', UC_M68K_REG_D2), ('d3', UC_M68K_REG_D3),
             ('d4', UC_M68K_REG_D4), ('d5', UC_M68K_REG_D5),
             ('d6', UC_M68K_REG_D6), ('d7', UC_M68K_REG_D7))
    s.at(S5, on_hit('s5', (('d6', UC_M68K_REG_D6),
                           ('d0', UC_M68K_REG_D0))))
    s.at(S5_SYNTH1, on_hit('s5synth1', (('d6', UC_M68K_REG_D6),)))
    s.at(S5_SYNTH2, on_hit('s5synth2', (('d6', UC_M68K_REG_D6),)))
    s.at(S5_MIDI, on_hit('s5midi', (('d6', UC_M68K_REG_D6),)))
    s.at(P_C6BARET, on_hit('p_c6baret', (('d0', UC_M68K_REG_D0),)))
    s.at(P_CMP, on_hit('p_cmp', (('d4', UC_M68K_REG_D4),
                                ('d0', UC_M68K_REG_D0))))

    for track in tracks:
        c = {'track': track}
        try:
            if track >= 4 and r.state(track - 4) != 1:
                V.select(r, track)
                V.open_modal(r, track - 4)
                r.key('YES', hold=15, after=600)
                assert r.slot() == -1 and \
                    r.state(track - 4) == 1, 'YES did not flip'
                V.midi_to_bank(r, True)
            elif track < 4:
                V.select(r, track)
            elif r.state(track - 4) == 1:
                V.midi_to_bank(r, True)
                assert u32(s.m, B.ACTIVE) == track, \
                    'toggle did not reach t%d' % track
            else:
                V.select(r, track)
            c['active_at_press'] = u32(s.m, B.ACTIVE)
            del hits[:]
            h0 = sha(fb(s.m, s))
            s.press(s.code('TRIG'))
            s.run_ms(120)
            s.release(s.code('TRIG'))
            s.run_ms(1500)
            buf = r.settle_fb()
            c['fb'] = sha(buf)[:16]
            c['fb_changed'] = (c['fb'] != h0[:16])
            if os.environ.get('CNV_PNGDIR'):
                p = os.path.join(os.environ['CNV_PNGDIR'],
                                 'cap_s5proof_t%d_trig.png' % track)
                panel.write_png(buf, p)
            summ = {}
            for h in hits:
                e = summ.setdefault(h['site'], {'n': 0, 'regs': set(),
                                                'actives': set()})
                e['n'] += 1
                e['actives'].add(h['active'])
                for k, v in h.items():
                    if k.startswith('d') and len(k) == 2:
                        e['regs'].add('%s=%d' % (k, v))
            c['summary'] = {
                k: {'n': v['n'], 'regs': sorted(v['regs'])[:10],
                    'actives': sorted(v['actives'])}
                for k, v in summ.items()}
            for h in hits:
                if h['site'] == 's5':
                    h['d6_is_active'] = (
                        h['d6'] == c['active_at_press'])
                if h['site'] == 'p_cmp':
                    h['d4_is_active'] = (
                        h['d4'] == c['active_at_press'])
            s5hits = [h for h in hits if h['site'] == 's5']
            c['s5_n'] = len(s5hits)
            c['s5_d6_all_active'] = (
                bool(s5hits) and all(h.get('d6_is_active', False)
                                     for h in s5hits))
            c['s5synth_n'] = sum(1 for h in hits
                                 if h['site'] in ('s5synth1', 's5synth2'))
            c['s5midi_n'] = sum(1 for h in hits if h['site'] == 's5midi')
        except Exception as e:
            c['blocked'] = '%s: %s' % (type(e).__name__, e)
        out['cells'].append(c)
        _home(r)
    out['converted'] = [r.state(i) for i in range(4)]
    r.close()
    out['wall'] = r.wall
    return out


def leg_trigsweep(slot=0, conv=False):
    """TRIG-key track-fork sweep: find the MAIN content dispatch.

    Scans the MAIN image for the `moveq #3,r; cmp.l; bcc` idiom, hooks
    every site (d-regs + ACTIVE), single TRIG press. Sites firing with
    a compared-reg == ACTIVE on the open are MAIN content/render fork
    candidates. Pre-known sites (S5/P_CMP/S4A) are flagged, not
    re-proven."""
    use_build(BUILD)
    img = open(os.path.join(
        os.path.dirname(BUILD['folder']),
        os.path.basename(BUILD['folder']),
        'sections', 'section_3_MAIN_OS.bin'), 'rb').read()
    base = 0x40000400
    cands = []
    for i in range(len(img) - 8):
        if img[i] & 0xF1 != 0x70 or img[i + 1] != 0x03:
            continue
        a = base + i
        for j in (i + 2, i + 4):
            if img[j] & 0xF0 != 0xB0:
                continue
            for k in (j + 2, j + 4):
                if img[k] & 0xFF != 0x6D and img[k] & 0xF0 != 0x60:
                    continue
                cands.append(a)
                break
            break
    cands = sorted(set(cands))[:80]
    r = B.Run(audio=False)
    s = r.s
    DREGS = (('d0', UC_M68K_REG_D0), ('d1', UC_M68K_REG_D1),
             ('d2', UC_M68K_REG_D2), ('d3', UC_M68K_REG_D3),
             ('d4', UC_M68K_REG_D4), ('d5', UC_M68K_REG_D5),
             ('d6', UC_M68K_REG_D6), ('d7', UC_M68K_REG_D7))
    out = {'leg': 'trigsweep', 'tag': BUILD['tag'], 'slot': slot,
           'conv': conv, 'nsites': len(cands)}
    hits = []

    def mk(site):
        def cb(uc, a, sz, d):
            if len(hits) < 1200:
                try:
                    e = {'site': '0x%08x' % site,
                         'active': u32(s.m, B.ACTIVE)}
                    for nm, rg in DREGS:
                        e[nm] = int(uc.reg_read(rg))
                    hits.append(e)
                except Exception:
                    pass
        return cb

    for site in cands:
        try:
            s.at(site, mk(site))
        except Exception:
            pass
    try:
        if conv:
            track = 4 + slot
            V.select(r, track)
            V.open_modal(r, slot)
            r.key('YES', hold=15, after=600)
            assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
            V.midi_to_bank(r, True)
        else:
            V.select(r, slot)
        h0 = sha(fb(s.m, s))
        del hits[:]
        s.press(s.code('TRIG'))
        s.run_ms(120)
        s.release(s.code('TRIG'))
        s.run_ms(600)
        buf = r.settle_fb()
        out['fb_changed'] = (sha(buf) != h0)
        out['fb'] = sha(buf)[:16]
        out['active'] = u32(s.m, B.ACTIVE)
        if os.environ.get('CNV_PNGDIR'):
            p = os.path.join(os.environ['CNV_PNGDIR'],
                             'cap_trigsweep_%s.png' %
                             ('conv' if conv else 'nat'))
            panel.write_png(buf, p)
            out['png'] = p
        matched = {}
        for h in hits:
            regs = [v for k, v in h.items()
                    if k.startswith('d') and len(k) == 2]
            if h['active'] in regs:
                e = matched.setdefault(h['site'], {'n': 0})
                e['n'] += 1
        out['matched'] = sorted(matched.items())
        out['nsites_fired'] = len(set(h['site'] for h in hits))
        # Per-site register detail for the matched sites only.
        det = {}
        for h in hits:
            if h['site'] in matched:
                e = det.setdefault(h['site'], set())
                for k, v in h.items():
                    if k.startswith('d') and len(k) == 2:
                        e.add('%s=%d' % (k, v))
        out['matched_regs'] = {k: sorted(v)[:14]
                               for k, v in det.items()}
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


P4_SYNTH = 0x4003f18a
P4_MIDI = 0x4003f190
C_SITE = 0x4003db2c
C_SYNTH = 0x4003db32
C_MIDI = 0x4003db3c
A_SITE = 0x4001d860
A_SYNTH = 0x4001d866
A_MIDI = 0x4001d87a
D_SITE = 0x4004348a
D_SYNTH = 0x40043490
D_MIDI = 0x400434c6


def leg_maintrace():
    """MAIN fork-taken trace: which fork does each track take at the
    TRIG-page content candidates (P4 filler, C filler, A resolver, S4B)?

    Hooks each site + both fork targets; TRIG on native t0, converted
    t4, native-MIDI t5 (all outcome-verified). Also captures the stock
    reference (flip-back to MIDI, t4 TRIG) and the converted SYN1
    header for comparison."""
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'maintrace', 'tag': BUILD['tag']}
    pngdir = os.environ.get('CNV_PNGDIR')
    hits = []

    def on_hit(site, regs):
        def cb(uc, a, sz, d):
            if len(hits) < 600:
                try:
                    e = {'site': site,
                         'active': u32(s.m, B.ACTIVE)}
                    for nm, rg in regs:
                        e[nm] = int(uc.reg_read(rg))
                    hits.append(e)
                except Exception:
                    pass
        return cb

    D1 = (('d1', UC_M68K_REG_D1),)
    D3 = (('d3', UC_M68K_REG_D3),)
    D0 = (('d0', UC_M68K_REG_D0),)
    D30 = (('d3', UC_M68K_REG_D3), ('d0', UC_M68K_REG_D0))
    s.at(P4_SYNTH, on_hit('p4synth', D3))
    s.at(P4_MIDI, on_hit('p4midi', D3))
    s.at(C_SITE, on_hit('c', D30))
    s.at(C_SYNTH, on_hit('csynth', D3))
    s.at(C_MIDI, on_hit('cmidi', D3))
    s.at(A_SITE, on_hit('a', D1))
    s.at(A_SYNTH, on_hit('asynth', D1))
    s.at(A_MIDI, on_hit('amidi', D1))
    s.at(D_SITE, on_hit('d', D0))
    s.at(D_SYNTH, on_hit('dsynth', D0))
    s.at(D_MIDI, on_hit('dmidi', D0))

    def trig_cell(track, name, key='TRIG'):
        c = {'track': track, 'key': key}
        del hits[:]
        h0 = sha(fb(s.m, s))
        s.press(s.code(key))
        s.run_ms(120)
        s.release(s.code(key))
        s.run_ms(1500)
        buf = r.settle_fb()
        c['fb'] = sha(buf)[:16]
        c['fb_changed'] = (c['fb'] != h0[:16])
        if pngdir:
            p = os.path.join(pngdir, 'cap_trace_%s.png' % name)
            panel.write_png(buf, p)
            c['png'] = p
        summ = {}
        for h in hits:
            e = summ.setdefault(h['site'], {'n': 0, 'regs': set(),
                                             'actives': set()})
            e['n'] += 1
            e['actives'].add(h['active'])
            for k, v in h.items():
                if k.startswith('d') and len(k) == 2:
                    e['regs'].add('%s=%d' % (k, v))
        c['summary'] = {
            k: {'n': v['n'], 'regs': sorted(v['regs'])[:10],
                'actives': sorted(v['actives'])}
            for k, v in summ.items()}
        return c

    try:
        V.select(r, 0)
        out['nat0'] = trig_cell(0, 'nat0_trig')
        _home(r)
        _convert_slot0(r)
        out['converted'] = [r.state(i) for i in range(4)]
        V.midi_to_bank(r, True)
        out['conv4'] = trig_cell(4, 'conv4_trig')
        _home(r)
        # Control: SYN1 on converted t4 — does the refresh filler see
        # the mirrored slot (P1 propagation) or the real track?
        # (TRIG page may still be open from conv4 if NO never exits
        # it, so force a bank toggle to guarantee a fresh open.)
        V.midi_to_bank(r, False)
        V.midi_to_bank(r, True)
        out['conv4_syn1'] = trig_cell(4, 'conv4_syn1', key='SYN1')
        _home(r)
        # Native SYN1 reference.
        V.midi_to_bank(r, False)
        out['nat0_syn1'] = trig_cell(0, 'nat0_syn1', key='SYN1')
        # Converted SYN1 header reference (what the diverted synth
        # param page shows).
        V.midi_to_bank(r, True)
        s.press(s.code('SYN1'))
        s.run_ms(120)
        s.release(s.code('SYN1'))
        s.run_ms(1500)
        buf = r.settle_fb()
        if pngdir:
            p = os.path.join(pngdir, 'cap_trace_conv4_syn1.png')
            panel.write_png(buf, p)
            out['conv4_syn1_png'] = p
        out['conv4_syn1_fb'] = sha(buf)[:16]
        _home(r)
        # Stock reference: flip back to MIDI, t4 TRIG. Reach t4 via
        # the MIDI toggle (V.select cannot T-select; slot 0 is
        # converted until the flip-back below).
        V.midi_to_bank(r, False)
        V.midi_to_bank(r, True)
        assert u32(s.m, B.ACTIVE) == 4, 'toggle did not reach t4'
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
                if r.slot() == 0:
                    break
                s.run_ms(100)
                el += 100
            if r.slot() == 0:
                break
        assert r.slot() == 0, 'restore modal did not open'
        r.key('YES', hold=15, after=600)
        out['flipback_state'] = r.state(0)
        V.midi_to_bank(r, True)
        out['stock4'] = trig_cell(4, 'stock4_trig')
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_override(mode='a'):
    """Live register-override experiment (no patch): emulate a divert by
    rewriting the compared register at the fork site when a converted
    slot is active, then open TRIG and capture the label.

    Modes: 'a' (d1->slot at A 0x4001d860), 'd' (d0->0 at D 0x4004348a),
    'ad' (both). Natives untouched (override only fires converted).
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn.m68k_const import UC_M68K_REG_D0, UC_M68K_REG_D1
    out = {'leg': 'override', 'mode': mode, 'tag': BUILD['tag']}
    pngdir = os.environ.get('CNV_PNGDIR')

    def on_a(uc, a, sz, d):
        try:
            if u32(s.m, B.ACTIVE) >= 4 and \
                    r.state(u32(s.m, B.ACTIVE) - 4) == 1:
                uc.reg_write(UC_M68K_REG_D1,
                             u32(s.m, B.ACTIVE) - 4)
        except Exception:
            pass

    def on_d(uc, a, sz, d):
        try:
            if u32(s.m, B.ACTIVE) >= 4 and \
                    r.state(u32(s.m, B.ACTIVE) - 4) == 1:
                uc.reg_write(UC_M68K_REG_D0, 0)
        except Exception:
            pass

    if mode in ('a', 'ad'):
        s.at(A_SITE, on_a)
    if mode in ('d', 'ad'):
        s.at(D_SITE, on_d)
    try:
        V.select(r, 0)
        c = _trig_open(r, 0)
        out['nat0_trig'] = c['fb']
        _home(r)
        _convert_slot0(r)
        V.midi_to_bank(r, True)
        c = _trig_open(r, 4)
        out['conv4_trig'] = c['fb']
        if pngdir:
            p = os.path.join(pngdir, 'cap_override_%s_conv4.png' % mode)
            panel.write_png(c['buf'], p)
            out['png'] = p
        out['conv_is_nat'] = (out['conv4_trig'] == out['nat0_trig'])
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_trigvals(native=False):
    """Do TRIG-page values track the applied preset + knob writes?

    Converted (default): convert slot 0, TRIG capture (init timbre),
    browse+apply a preset, TRIG capture again, knob turns on TRIG
    with SND snapshots. Native: same flow on track 0 (kit sound +
    pattern snapshots) as the parity control — TRIG knobs target
    pattern params on both banks, so SND/kit-sound must stay
    untouched while the display may move focus.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'trigvals', 'tag': BUILD['tag'], 'native': native}
    pngdir = os.environ.get('CNV_PNGDIR')
    try:
        if native:
            V.select(r, 0)
            live = u32(s.m, 0x4138f220) + 0x18
            live_n = 326
        else:
            SND = B._addr('cnv_synth_snd')
            kit = u32(s.m, 0x4138f220)
            _convert_slot0(r)
            V.midi_to_bank(r, True)
            live, live_n = SND, 326
        c = _trig_open(r, 0 if native else 4)
        out['trig_init_fb'] = c['fb']
        out['live_init_sha'] = sha(bytes(s.m.peek(live, live_n)))[:16]
        if pngdir and not native:
            p = os.path.join(pngdir, 'cap_trigvals_init.png')
            panel.write_png(c['buf'], p)
        _home(r)
        if native:
            # Native browser apply on track 0: single-tap T1 opens
            # the synth browser directly (3.1 regbrowser parity).
            for _ in range(4):
                s.press(s.code('T1'))
                s.run_ms(60)
                s.release(s.code('T1'))
                s.run_ms(300)
            r.key('DOWN', hold=100, after=300)
            r.key('DOWN', hold=100, after=300)
            out['apply'] = {'down_fb': sha(r.settle_fb())[:16]}
            live_pre = bytes(s.m.peek(live, live_n))
            r.key('YES', hold=100, after=500)
            r.settle_fb()
            out['apply']['yes_fb'] = sha(r.settle_fb())[:16]
            live_post = bytes(s.m.peek(live, live_n))
            out['apply']['live_changed'] = (live_post != live_pre)
            out['apply']['live_post_sha'] = sha(live_post)[:16]
        else:
            ba = _browse_apply(r)
            out['apply'] = {k: v for k, v in ba.items() if k != 'BLOCKED'}
            if ba.get('BLOCKED'):
                out['BLOCKED'] = ba['BLOCKED']
                r.close()
                out['wall'] = r.wall
                return out
            V.midi_to_bank(r, True)
        c = _trig_open(r, 0 if native else 4)
        out['trig_applied_fb'] = c['fb']
        out['live_applied_sha'] = sha(
            bytes(s.m.peek(live, live_n)))[:16]
        if pngdir:
            p = os.path.join(
                pngdir, 'cap_trigvals_%s_applied.png' %
                ('nat' if native else 'conv'))
            panel.write_png(c['buf'], p)
            out['png_applied'] = p
        out['fb_tracks_apply'] = (out['trig_applied_fb'] !=
                                  out['trig_init_fb'])
        out['knobs'] = []
        for code in (1, 2, 3, 4):
            pre = bytes(s.m.peek(live, live_n))
            s.turn(code, 16, 200)
            s.run_ms(200)
            s.turn(code, -16, 300)
            s.run_ms(500)
            post = bytes(s.m.peek(live, live_n))
            e = {'code': code,
                 'live_diff_n': sum(1 for a, b in zip(pre, post)
                                    if a != b)}
            out['knobs'].append(e)
        buf = r.settle_fb()
        out['trig_postknob_fb'] = sha(buf)[:16]
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'trigvals', 'tag': BUILD['tag']}
    pngdir = os.environ.get('CNV_PNGDIR')
    try:
        SND = B._addr('cnv_synth_snd')
        kit = u32(s.m, 0x4138f220)
        _convert_slot0(r)
        V.midi_to_bank(r, True)
        c = _trig_open(r, 4)
        out['trig_init_fb'] = c['fb']
        out['snd_init_sha'] = sha(bytes(s.m.peek(SND, 326)))[:16]
        if pngdir:
            p = os.path.join(pngdir, 'cap_trigvals_init.png')
            panel.write_png(c['buf'], p)
        _home(r)
        ba = _browse_apply(r)
        out['apply'] = {k: v for k, v in ba.items() if k != 'BLOCKED'}
        if ba.get('BLOCKED'):
            out['BLOCKED'] = ba['BLOCKED']
            r.close()
            out['wall'] = r.wall
            return out
        V.midi_to_bank(r, True)
        c = _trig_open(r, 4)
        out['trig_applied_fb'] = c['fb']
        out['snd_applied_sha'] = sha(bytes(s.m.peek(SND, 326)))[:16]
        if pngdir:
            p = os.path.join(pngdir, 'cap_trigvals_applied.png')
            panel.write_png(c['buf'], p)
            out['png_applied'] = p
        out['fb_tracks_apply'] = (out['trig_applied_fb'] !=
                                  out['trig_init_fb'])
        # Knob turns on the TRIG page: which encoder writes .bss?
        out['knobs'] = []
        for code in (1, 2, 3, 4):
            pre = bytes(s.m.peek(SND, 326))
            kit_pre = bytes(s.m.peek(kit + 0x18, 326))
            s.turn(code, 16, 200)
            s.run_ms(200)
            s.turn(code, -16, 300)
            s.run_ms(500)
            post = bytes(s.m.peek(SND, 326))
            kit_post = bytes(s.m.peek(kit + 0x18, 326))
            e = {'code': code,
                 'snd_diff_n': sum(1 for a, b in zip(pre, post)
                                   if a != b),
                 'kit_same': (kit_post == kit_pre)}
            out['knobs'].append(e)
        buf = r.settle_fb()
        out['trig_postknob_fb'] = sha(buf)[:16]
        if pngdir:
            p = os.path.join(pngdir, 'cap_trigvals_postknob.png')
            panel.write_png(buf, p)
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_trigdiv():
    """TRIG open-window divergence: ordered hit sequence (ms, site,
    caller, regs) on a single TRIG press, native t0 vs converted t4.
    The first site where the flows differ is the MAIN dispatch."""
    use_build(BUILD)
    out = {'leg': 'trigdiv', 'tag': BUILD['tag'], 'cells': []}
    for conv in (False, True):
        r = B.Run(audio=False)
        s = r.s
        from unicorn.m68k_const import UC_M68K_REG_A7
        DREGS = (('d0', UC_M68K_REG_D0), ('d1', UC_M68K_REG_D1),
                 ('d2', UC_M68K_REG_D2), ('d3', UC_M68K_REG_D3))
        hits = []

        def mk(site, regs=DREGS, caller=True):
            def cb(uc, a, sz, d):
                if len(hits) < 500:
                    try:
                        e = {'ms': round(s.ms, 1), 'site': site,
                             'active': u32(s.m, B.ACTIVE)}
                        for nm, rg in regs:
                            e[nm] = int(uc.reg_read(rg))
                        if caller:
                            try:
                                sp = int(uc.reg_read(UC_M68K_REG_A7))
                                raw = s.m.peek(sp, 4)
                                e['caller'] = ('0x%08x' % struct.unpack(
                                    '>I', raw)[0]) if raw else None
                            except Exception:
                                e['caller'] = None
                        hits.append(e)
                    except Exception:
                        pass
            return cb

        D0 = (('d0', UC_M68K_REG_D0),)
        D1 = (('d1', UC_M68K_REG_D1),)
        D2 = (('d2', UC_M68K_REG_D2),)
        D3 = (('d3', UC_M68K_REG_D3),)
        D4 = (('d4', UC_M68K_REG_D4),)
        ONE = (('d0', UC_M68K_REG_D0), ('d1', UC_M68K_REG_D1),
               ('d2', UC_M68K_REG_D2), ('d3', UC_M68K_REG_D3),
               ('d4', UC_M68K_REG_D4), ('d5', UC_M68K_REG_D5),
               ('d6', UC_M68K_REG_D6), ('d7', UC_M68K_REG_D7))
        E1AE = 0x4002e1ae
        C6BA = 0x4002c6ba
        T2576 = 0x40025b76
        s.at(E1AE, mk('e1ae', ONE))
        s.at(C6BA, mk('c6ba', ONE))
        s.at(T2576, mk('t2576', ONE))
        s.at(P_C6BARET, mk('p1ret', D0, caller=False))
        s.at(P_CMP, mk('pcmp', D4, caller=False))
        s.at(P4_SYNTH, mk('p4synth', D3, caller=False))
        s.at(P4_MIDI, mk('p4midi', D3, caller=False))
        s.at(C_SITE, mk('c', D3, caller=False))
        s.at(C_SYNTH, mk('csynth', D3, caller=False))
        s.at(C_MIDI, mk('cmidi', D3, caller=False))
        s.at(A_SITE, mk('a', D1, caller=False))
        s.at(A_SYNTH, mk('asynth', D1, caller=False))
        s.at(A_MIDI, mk('amidi', D1, caller=False))
        s.at(D_SITE, mk('d', D0, caller=False))
        s.at(D_SYNTH, mk('dsynth', D0, caller=False))
        s.at(D_MIDI, mk('dmidi', D0, caller=False))
        s.at(0x40043258, mk('s4a', D2, caller=False))
        s.at(0x4004325e, mk('s4synth', D2, caller=False))
        s.at(0x400432a0, mk('s4midi', D2, caller=False))
        s.at(0x4002f91a, mk('builder', D0, caller=False))
        c = {'conv': conv}
        try:
            if conv:
                _convert_slot0(r)
                V.midi_to_bank(r, True)
                track = 4
            else:
                V.select(r, 0)
                track = 0
            c['active_at_press'] = u32(s.m, B.ACTIVE)
            del hits[:]
            h0 = sha(fb(s.m, s))
            t_press = round(s.ms, 1)
            s.press(s.code('TRIG'))
            s.run_ms(120)
            s.release(s.code('TRIG'))
            s.run_ms(800)
            buf = r.settle_fb()
            c['t_press'] = t_press
            c['fb_changed'] = (sha(buf) != h0)
            c['fb'] = sha(buf)[:16]
            c['hits'] = [h for h in hits if h['ms'] - t_press < 900]
        except Exception as e:
            c['blocked'] = '%s: %s' % (type(e).__name__, e)
        out['cells'].append(c)
        r.close()
    out['wall'] = r.wall if 'r' in dir() else None
    return out


def leg_bankread_trig():
    """ACTIVE/bank readers during a TRIG open, native vs converted.

    Mem-read watch on FW_ACTIVE_TRACK: the label/bank readers show up
    as PCs. A reader present on the converted MID-label path but with
    a synth verdict on native is the label-dispatch reader."""
    use_build(BUILD)
    import cnv_pages as P
    P.use_build(dict(BUILD))
    out = {'leg': 'bankread_trig', 'tag': BUILD['tag']}
    out['nat'] = P.leg_bankread(slot=0, key='TRIG', conv=False)
    out['conv'] = P.leg_bankread(slot=0, key='TRIG', conv=True)
    return out


def leg_textf():
    """fw_textf strings on the settled TRIG page, native vs converted.

    Hooks TEXTF (0x400de0dc): logs caller + format string + position
    for every text draw during ~500 ms of settled TRIG display. The
    SYN/MID label draw (caller + string source) identifies the label
    dispatch."""
    use_build(BUILD)
    import cnv_pages as P
    P.use_build(dict(BUILD))
    out = {'leg': 'textf', 'tag': BUILD['tag'], 'cells': []}
    TEXTF = 0x400de0dc
    for conv in (False, True):
        r = B.Run(audio=False)
        s = r.s
        from unicorn.m68k_const import UC_M68K_REG_A7
        c = {'conv': conv}
        hits = []

        def on_textf(uc, a, sz, d):
            if len(hits) < 300:
                try:
                    sp = int(uc.reg_read(UC_M68K_REG_A7))
                    words = []
                    for k in range(8):
                        raw = s.m.peek(sp + 4 * k, 4)
                        if not raw or len(raw) < 4:
                            break
                        words.append(struct.unpack('>I', raw)[0])
                    e = {'ms': round(s.ms, 1),
                         'active': u32(s.m, B.ACTIVE)}
                    e['caller'] = ('0x%08x' % words[0]) if words else None
                    e['stack'] = ['0x%x' % w for w in words[1:]]
                    # fmt is one of the stack words: find the one
                    # pointing at a short printable string.
                    for w in words[1:]:
                        raw = s.m.peek(w, 24)
                        if not raw:
                            continue
                        try:
                            z = bytes(raw).split(b'\x00')[0]
                            if 1 <= len(z) <= 20 and all(
                                    32 <= b < 127 for b in z):
                                e['str'] = z.decode()
                                e['str_at'] = '0x%08x' % w
                                break
                        except Exception:
                            pass
                    hits.append(e)
                except Exception:
                    pass

        s.at(TEXTF, on_textf)
        try:
            if conv:
                _convert_slot0(r)
                V.midi_to_bank(r, True)
            else:
                V.select(r, 0)
            h0 = sha(fb(s.m, s))
            s.press(s.code('TRIG'))
            s.run_ms(120)
            s.release(s.code('TRIG'))
            s.run_ms(1500)
            buf = r.settle_fb()
            c['fb'] = sha(buf)[:16]
            c['fb_changed'] = (c['fb'] != h0[:16])
            if os.environ.get('CNV_PNGDIR'):
                p = os.path.join(os.environ['CNV_PNGDIR'],
                                 'cap_textf_%s.png' % ('conv' if conv
                                                      else 'nat'))
                panel.write_png(buf, p)
            # Re-open with the hook recording the OPEN draws: hop to
            # SYN1 first (NO does not exit the TRIG page; a page key
            # does), then back to TRIG.
            s.press(s.code('SYN1'))
            s.run_ms(120)
            s.release(s.code('SYN1'))
            s.run_ms(800)
            r.settle_fb()
            del hits[:]
            s.press(s.code('TRIG'))
            s.run_ms(120)
            s.release(s.code('TRIG'))
            s.run_ms(1500)
            r.settle_fb()
            c['nhits'] = len(hits)
            # Aggregate by (caller, str).
            agg = {}
            for h in hits:
                k = (h.get('caller'), h.get('str'))
                agg[k] = agg.get(k, 0) + 1
            c['draws'] = sorted(
                ((k[0], k[1], v) for k, v in agg.items()),
                key=lambda x: -x[2])[:60]
        except Exception as e:
            c['blocked'] = '%s: %s' % (type(e).__name__, e)
        out['cells'].append(c)
        r.close()
    return out


def leg_labelwrite():
    """Framebuffer write-watch on the track-label box during a fresh
    TRIG open, native vs converted. The writer PC (+ regs) identifies
    the label draw; its character source (view/struct/row) is the
    label dispatch."""
    use_build(BUILD)
    out = {'leg': 'labelwrite', 'tag': BUILD['tag'], 'cells': []}
    from unicorn import UC_HOOK_MEM_WRITE
    from unicorn.m68k_const import UC_M68K_REG_PC
    for conv in (False, True):
        r = B.Run(audio=False)
        s = r.s
        c = {'conv': conv}
        writes = []
        try:
            fba = s.profile.fb_front
            base = u32(s.m, fba)
            c['fb_base'] = ('0x%08x' % base) if base else None
            c['fb_front_ptr'] = ('0x%08x' % fba) if fba else None
            # Label box in 128x64 panel coords (from the 6x PNGs:
            # track box spans roughly x 0..22, y 18..44).
            label = set()
            for x in range(0, 23):
                for y in range(18, 45):
                    label.add((7 - (y // 8)) + 8 * x)

            def on_write(uc, access, address, size, value, data):
                if len(writes) >= 120:
                    return
                try:
                    off = address - base
                    if off in label:
                        writes.append({
                            'pc': '0x%08x' % int(uc.reg_read(
                                UC_M68K_REG_PC)),
                            'off': off, 'size': size,
                            'ms': round(s.ms, 1)})
                except Exception:
                    pass

            s.m.uc.hook_add(UC_HOOK_MEM_WRITE, on_write, base,
                            base + 1023)
            if conv:
                _convert_slot0(r)
                V.midi_to_bank(r, True)
            else:
                V.select(r, 0)
            h0 = sha(fb(s.m, s))
            s.press(s.code('TRIG'))
            s.run_ms(120)
            s.release(s.code('TRIG'))
            s.run_ms(1500)
            buf = r.settle_fb()
            c['fb'] = sha(buf)[:16]
            c['fb_changed'] = (c['fb'] != h0[:16])
            if os.environ.get('CNV_PNGDIR'):
                p = os.path.join(
                    os.environ['CNV_PNGDIR'],
                    'cap_labelwrite_%s.png' % ('conv' if conv
                                               else 'nat'))
                panel.write_png(buf, p)
            pcs = {}
            for w in writes:
                pcs[w['pc']] = pcs.get(w['pc'], 0) + 1
            c['nwrites'] = len(writes)
            c['writer_pcs'] = sorted(pcs.items(),
                                     key=lambda kv: -kv[1])[:15]
            c['writes'] = writes[:40]
        except Exception as e:
            c['blocked'] = '%s: %s' % (type(e).__name__, e)
        out['cells'].append(c)
        r.close()
    return out


def leg_labelregs():
    """Register dump at the label-box writer PCs, native vs converted.

    Full d-regs + a0/a1 at each top writer on a fresh TRIG open. The
    differing register is the character/data source = label dispatch."""
    use_build(BUILD)
    out = {'leg': 'labelregs', 'tag': BUILD['tag'], 'cells': []}
    PCS = (0x400dca4a, 0x400de044, 0x400de61c,
           0x400dd5ee, 0x400dd5fe, 0x400dd5dc, 0x400dcc2e,
           0x400ddfc2)
    for conv in (False, True):
        r = B.Run(audio=False)
        s = r.s
        from unicorn.m68k_const import (UC_M68K_REG_D0, UC_M68K_REG_D1,
                                        UC_M68K_REG_D2, UC_M68K_REG_D3,
                                        UC_M68K_REG_D4, UC_M68K_REG_D5,
                                        UC_M68K_REG_D6, UC_M68K_REG_D7,
                                        UC_M68K_REG_A0, UC_M68K_REG_A1,
                                        UC_M68K_REG_A7)
        c = {'conv': conv}
        hits = []

        def mk(site):
            def cb(uc, a, sz, d):
                if len(hits) < 120:
                    try:
                        e = {'site': site,
                             'active': u32(s.m, B.ACTIVE)}
                        for nm, rg in (('d0', UC_M68K_REG_D0),
                                       ('d1', UC_M68K_REG_D1),
                                       ('d2', UC_M68K_REG_D2),
                                       ('d3', UC_M68K_REG_D3),
                                       ('a0', UC_M68K_REG_A0),
                                       ('a1', UC_M68K_REG_A1)):
                            v = int(uc.reg_read(rg))
                            e[nm] = ('0x%08x' % v
                                     if v > 0x10000 else v)
                        hits.append(e)
                    except Exception:
                        pass
            return cb

        for pc in PCS:
            try:
                s.at(pc, mk('0x%08x' % pc))
            except Exception:
                pass
        try:
            if conv:
                _convert_slot0(r)
                V.midi_to_bank(r, True)
            else:
                V.select(r, 0)
            h0 = sha(fb(s.m, s))
            s.press(s.code('TRIG'))
            s.run_ms(120)
            s.release(s.code('TRIG'))
            s.run_ms(1500)
            buf = r.settle_fb()
            c['fb'] = sha(buf)[:16]
            c['fb_changed'] = (c['fb'] != h0[:16])
            agg = {}
            for h in hits:
                k = (h['site'], tuple(sorted(
                    (kk, vv) for kk, vv in h.items()
                    if kk not in ('site', 'active'))))
                agg[k] = agg.get(k, 0) + 1
            c['regs'] = [({'site': k[0], 'regs': dict(k[1]),
                           'n': v}) for k, v in sorted(
                agg.items(), key=lambda kv: -kv[1])[:40]]
        except Exception as e:
            c['blocked'] = '%s: %s' % (type(e).__name__, e)
        out['cells'].append(c)
        r.close()
    return out


def leg_trigsub():
    """TRIG subpages: RIGHT-arrow (and TRIG-again) on the TRIG page,
    native t0 vs converted t4 vs native-MIDI t5. The MIDI SRC assigns
    (PB/AT/MW/BC) may live on a second TRIG subpage with its own
    dispatch."""
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'trigsub', 'tag': BUILD['tag'], 'cells': []}
    pngdir = os.environ.get('CNV_PNGDIR')
    try:
        V.select(r, 0)
        # Establish converted slot 0 first (bank memory), then walk.
        V.select(r, 4)
        V.open_modal(r, 0)
        r.key('YES', hold=15, after=600)
        assert r.slot() == -1 and r.state(0) == 1, 'YES did not flip'
        for track, name in ((0, 'nat0'), (4, 'conv4'), (5, 'mid5')):
            if track < 4:
                V.select(r, track)
            elif r.state(track - 4) == 1:
                V.midi_to_bank(r, True)
                assert u32(s.m, B.ACTIVE) == track
            else:
                V.select(r, track)
            c = {'track': track}
            h0 = sha(fb(s.m, s))
            s.press(s.code('TRIG'))
            s.run_ms(120)
            s.release(s.code('TRIG'))
            s.run_ms(1200)
            buf = r.settle_fb()
            c['trig1_fb'] = sha(buf)[:16]
            if pngdir:
                p = os.path.join(pngdir,
                                 'cap_sub_%s_trig1.png' % name)
                panel.write_png(buf, p)
            for g, gn in (('RIGHT', 'right'), ('TRIG', 'trig2'),
                          ('LEFT', 'left')):
                s.press(s.code(g))
                s.run_ms(120)
                s.release(s.code(g))
                s.run_ms(1200)
                buf = r.settle_fb()
                c['%s_fb' % gn] = sha(buf)[:16]
                c['%s_changed' % gn] = (
                    c['%s_fb' % gn] != c['trig1_fb'])
                if pngdir:
                    p = os.path.join(
                        pngdir, 'cap_sub_%s_%s.png' % (name, gn))
                    panel.write_png(buf, p)
            out['cells'].append(c)
            _home(r)
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_labelchain():
    """Call chain above the label-box blitter on a fresh TRIG open.

    First hit at 0x400dca4a only: dump sp words (return chain) + regs,
    native vs converted. The track-box routine's bank read is the
    label dispatch."""
    use_build(BUILD)
    out = {'leg': 'labelchain', 'tag': BUILD['tag'], 'cells': []}
    for conv in (False, True):
        r = B.Run(audio=False)
        s = r.s
        from unicorn.m68k_const import (UC_M68K_REG_D0, UC_M68K_REG_D1,
                                        UC_M68K_REG_D2, UC_M68K_REG_D3,
                                        UC_M68K_REG_A0, UC_M68K_REG_A1,
                                        UC_M68K_REG_A7)
        c = {'conv': conv}
        hits = []

        def on_blit(uc, a, sz, d):
            if len(hits) >= 40:
                return
            try:
                sp = int(uc.reg_read(UC_M68K_REG_A7))
                words = []
                for k in range(14):
                    raw = s.m.peek(sp + 4 * k, 4)
                    if not raw or len(raw) < 4:
                        break
                    words.append(struct.unpack('>I', raw)[0])
                e = {'ms': round(s.ms, 1),
                     'active': u32(s.m, B.ACTIVE),
                     'stack': ['0x%x' % w for w in words]}
                for nm, rg in (('d0', UC_M68K_REG_D0),
                                ('d1', UC_M68K_REG_D1),
                                ('d2', UC_M68K_REG_D2),
                                ('d3', UC_M68K_REG_D3),
                                ('a0', UC_M68K_REG_A0),
                                ('a1', UC_M68K_REG_A1)):
                    v = int(uc.reg_read(rg))
                    e[nm] = '0x%08x' % v if v > 0x10000 else v
                hits.append(e)
            except Exception:
                pass

        s.at(0x400dca4a, on_blit)
        try:
            if conv:
                _convert_slot0(r)
                V.midi_to_bank(r, True)
            else:
                V.select(r, 0)
            h0 = sha(fb(s.m, s))
            t_press = round(s.ms, 1)
            c['t_press'] = t_press
            s.press(s.code('TRIG'))
            s.run_ms(120)
            s.release(s.code('TRIG'))
            s.run_ms(1500)
            buf = r.settle_fb()
            c['fb'] = sha(buf)[:16]
            c['fb_changed'] = (c['fb'] != h0[:16])
            c['hits'] = [h for h in hits if h['ms'] - t_press < 900]
        except Exception as e:
            c['blocked'] = '%s: %s' % (type(e).__name__, e)
        out['cells'].append(c)
        r.close()
    return out


def leg_mirrorproof():
    """A1 bit-exact proof: no-browse convert -> TRIG must equal the
    0.23 live-override evidence fb (d1->slot at A), natives unchanged."""
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'mirrorproof', 'tag': BUILD['tag'],
           'expect_conv': '68dcba99e30ab53b',
           'expect_nat0': '30477ded3db29dde'}
    pngdir = os.environ.get('CNV_PNGDIR')
    try:
        V.select(r, 0)
        c = _trig_open(r, 0)
        out['nat0_trig'] = c['fb']
        out['nat0_match'] = (c['fb'] == out['expect_nat0'])
        if pngdir:
            p = os.path.join(pngdir, 'cap_mirrorproof_nat0.png')
            panel.write_png(c['buf'], p)
        _home(r)
        _convert_slot0(r)
        V.midi_to_bank(r, True)
        c = _trig_open(r, 4)
        out['conv4_trig'] = c['fb']
        out['conv_match_override'] = (c['fb'] == out['expect_conv'])
        if pngdir:
            p = os.path.join(pngdir, 'cap_mirrorproof_conv4.png')
            panel.write_png(c['buf'], p)
            out['png'] = p
        _home(r)
        V.select(r, 5)
        c = _trig_open(r, 5)
        out['mid5_trig'] = c['fb']
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_mainsynth():
    """Post-patch MAIN parity: converted TRIG renders the synth UI."""
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'mainsynth', 'tag': BUILD['tag']}
    pngdir = os.environ.get('CNV_PNGDIR')
    try:
        V.select(r, 0)
        c = _trig_open(r, 0)
        out['nat0_trig'] = c['fb']
        _home(r)
        _convert_slot0(r)
        ba = _browse_apply(r)
        out['apply'] = {k: v for k, v in ba.items() if k != 'BLOCKED'}
        if ba.get('BLOCKED'):
            out['BLOCKED'] = ba['BLOCKED']
            r.close()
            out['wall'] = r.wall
            return out
        V.midi_to_bank(r, True)
        c = _trig_open(r, 4)
        out['conv4_trig'] = c['fb']
        if pngdir:
            p = os.path.join(pngdir, 'cap_mainsynth_conv4.png')
            panel.write_png(c['buf'], p)
            out['png'] = p
        out['conv_is_nat'] = (out['conv4_trig'] == out['nat0_trig'])
        _home(r)
        V.select(r, 5)
        c = _trig_open(r, 5)
        out['mid5_trig'] = c['fb']
        out['conv_is_mid'] = (out['conv4_trig'] == out['mid5_trig'])
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_fixreg():
    """3.4 regression subset rebound to the new build."""
    use_build(BUILD)
    import cnv_pages as P
    P.use_build(dict(BUILD))
    out = {'leg': 'fixreg', 'tag': BUILD['tag']}
    t0 = time.time()
    out['pageopen'] = P.leg_pageopen((0, 4, 5), ('SYN1', 'SYN2'), (4,))
    out['knob'] = P.leg_knob()
    out['timbre'] = P.leg_timbre()
    out['muteseq'] = P.leg_muteseq()
    out['wall'] = round(time.time() - t0, 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--leg', choices=('stock', 'repro', 's5proof',
                                      'trigsweep', 'maintrace',
                                      'override', 'trigvals',
                                      'trigdiv', 'bankread_trig',
                                      'textf', 'labelwrite',
                                      'labelregs', 'labelchain',
                                      'trigsub', 'mirrorproof',
                                      'mainsynth', 'fixreg'),
                    required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--tag', type=int, default=None)
    ap.add_argument('--folder', default=None)
    ap.add_argument('--map', default=None)
    ap.add_argument('--slot', type=int, default=0)
    ap.add_argument('--native', action='store_true',
                    help='native-track variant (trigvals)')
    ap.add_argument('--mode', default='a',
                    help='override mode for the override leg (a/d/ad)')
    ap.add_argument('--conv', action='store_true')
    ap.add_argument('--tracks', default='0,4,5')
    args = ap.parse_args()
    if args.tag is not None:
        assert args.folder and args.map, '--tag needs --folder and --map'
        with open(os.path.join(args.folder, 'firmware.json')) as fh:
            rec = json.load(fh)
        sh = ((rec.get('release') or {}).get('sha256') or
              rec.get('syx_sha256'))
        use_build({'tag': args.tag, 'syx_sha': sh,
                   'folder': args.folder, 'map': args.map})
    else:
        with open(os.path.join(BUILD['folder'], 'firmware.json')) as fh:
            rec = json.load(fh)
        BUILD['syx_sha'] = ((rec.get('release') or {}).get('sha256')
                            or rec.get('syx_sha256'))
        use_build(BUILD)
    if args.leg == 'stock':
        rep = leg_stock()
    elif args.leg == 'repro':
        rep = leg_repro()
    elif args.leg == 's5proof':
        rep = leg_s5proof(tuple(int(x) for x in args.tracks.split(',')))
    elif args.leg == 'trigsweep':
        rep = leg_trigsweep(slot=args.slot, conv=args.conv)
    elif args.leg == 'maintrace':
        rep = leg_maintrace()
    elif args.leg == 'override':
        rep = leg_override(args.mode)
    elif args.leg == 'trigvals':
        rep = leg_trigvals(native=args.native)
    elif args.leg == 'trigdiv':
        rep = leg_trigdiv()
    elif args.leg == 'labelwrite':
        rep = leg_labelwrite()
    elif args.leg == 'labelregs':
        rep = leg_labelregs()
    elif args.leg == 'labelchain':
        rep = leg_labelchain()
    elif args.leg == 'mirrorproof':
        rep = leg_mirrorproof()
    elif args.leg == 'trigsub':
        rep = leg_trigsub()
    elif args.leg == 'textf':
        rep = leg_textf()
    elif args.leg == 'bankread_trig':
        rep = leg_bankread_trig()
    elif args.leg == 'mainsynth':
        rep = leg_mainsynth()
    elif args.leg == 'fixreg':
        rep = leg_fixreg()
    with open(args.out, 'w') as fh:
        json.dump(rep, fh, indent=1, default=str)
    print('%s wall=%s' % (args.leg, rep.get('wall')))
    print(json.dumps({k: v for k, v in rep.items() if k != 'buf'},
                     indent=1, default=str)[:6000])


if __name__ == '__main__':
    main()
