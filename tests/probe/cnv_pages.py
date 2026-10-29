#!/usr/bin/env python3
"""Param-page parity proof for dn-convert (8track-engine task 3.4).

S8 0x40160968 (`moveq #3,d1; cmp.l d0,d1; blt -> 0x4016098a`) + S5
0x4003ca70 (`moveq #3,d0; cmp.l d6,d0; blt -> 0x4003cab2`) are UNPROVEN
spike notes: compared-reg = track must be proven on param-page opens for
native 0-3 and converted 4-7 across page contexts BEFORE patching (no
blind patches). Playbook = 3.2 (cnv_voicemenu.py: S3/S4 silent, live V8
found dynamically) + 3.3 (cnv_labels.py: S6/S7 silent, live L3 found).
If a site never executes, it stays stock and the live dispatch is found.

Mod RAM truth for classification; framebuffer hashes + PNG captures
(viewed, not hashed) for the page pixels.

Legs (run from tools/digiemu with its venv; needs emu.*, unicorn):
  stock : stock bytes at S8/S5 sites + fork targets present in image.
  sweep : hook S8/S5 entries + sites + forks, log (site, regs, ACTIVE,
          fork) across page gestures x contexts on native 0 and
          converted 4. Finds which gestures draw param pages.
  proof : targeted per-track cells in the firing contexts: proves
          compared-reg == ACTIVE/track + fork taken.

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
from unicorn.m68k_const import (UC_M68K_REG_D0, UC_M68K_REG_D1,  # noqa: E402
                                UC_M68K_REG_D2, UC_M68K_REG_D3,
                                UC_M68K_REG_D4, UC_M68K_REG_D5,
                                UC_M68K_REG_D6, UC_M68K_REG_D7,
                                UC_M68K_REG_A5, UC_M68K_REG_A7)

S8 = 0x40160968
S8_SYNTH = 0x4016096e   # fallthrough: tst.l -24(a5); bne; jsr $401880e6
S8_VIRT = 0x40160982    # virtual jsr (a0) with d0
S8_MIDI = 0x4016098a    # moveq #$f,d0 ... jsr (a3)
S8_ENTRY = 0x401608d4   # enclosing function (link)
S8_SYNTHFN = 0x401880e6  # synth fork helper
S5 = 0x4003ca70
S5_SYNTH1 = 0x4003ca86  # jsr $40031ce2 (synth chain leg 1)
S5_SYNTH2 = 0x4003caa0  # jsr $40031972 (synth chain leg 2)
S5_MIDI = 0x4003cab2    # jsr $400ded80 (MIDI chain)
S5_MIDIFN = 0x400ded80
# Candidate synth-chain functions (spike §S5 synth fork + S8 synth fork).
C1DCF2 = 0x4001dcf2
C31CE2 = 0x40031ce2
C31972 = 0x40031972

BUILD19 = {
    'tag': 1482,
    'syx_sha': ('f7466c0a9f99daff1e6723558114141a9e23fbd41f25f1fb517b2ce709de4914'),
    'folder': ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
               'portable/firmware/dn1-1482-f7466c0a'),
    'map': ('/home/nuke/Documents/Elektron-MODS/firmware/'
            'test-cnv19.syx.map.json'),
}

BUILD20 = {
    'tag': 1483,
    'syx_sha': ('299549145a8550192ccf266eae864876d28736093a6332c790b6c805ecf6af06'),
    'folder': ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
               'portable/firmware/dn1-1483-29954914'),
    'map': ('/home/nuke/Documents/Elektron-MODS/firmware/'
            'test-cnv20.syx.map.json'),
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
    out = {'leg': 'stock', 'tag': BUILD['tag'],
           's8': hex(S8), 's5': hex(S5)}
    out['s8_bytes'] = (m.peek(S8, 6) or b'').hex()
    out['s5_bytes'] = (m.peek(S5, 6) or b'').hex()
    out['s8_expect'] = '7203b2806d1c'
    out['s5_expect'] = '7003b0866d3c'
    out['s8_match'] = (out['s8_bytes'] == out['s8_expect'])
    out['s5_match'] = (out['s5_bytes'] == out['s5_expect'])
    # Fork context bytes (synth vs MIDI legs).
    out['s8_synth_jsr'] = (m.peek(0x40160974, 6) or b'').hex()
    out['s8_synth_jsr_expect'] = '4eb9401880e6'
    out['s8_midi_head'] = (m.peek(S8_MIDI, 6) or b'').hex()
    out['s5_synth1_jsr'] = (m.peek(S5_SYNTH1, 6) or b'').hex()
    out['s5_midi_jsr'] = (m.peek(S5_MIDI + 2, 6) or b'').hex()
    out['s5_midi_jsr_expect'] = '4eb9400ded80'
    r.close()
    out['wall'] = r.wall
    return out


PAGE_KEYS = ('SYN1', 'SYN2', 'FLTR', 'AMP', 'LFO', 'TRIG', 'PAGE',
             'SYN1>RIGHT', 'FLTR>RIGHT', 'AMP>RIGHT', 'ENC-A',
             'FUNC+SYN1', 'FUNC+FLTR', 'UP', 'DOWN', 'LEFT', 'RIGHT')

# Live page-dispatch function (found dynamically, 0.19 chain leg):
# entry 0x4004221c calls the c6ba view-track reader (0x40042240),
# d4 = result (0x40042248), compares track vs 3 at P_CMP 0x40042258
# (`moveq #3,d0; cmp.l d4,d0`), synth page chain via P_GATE 0x40042530
# (`tst.l -$4d(a6)`) -> c1dcf2 row fetch (0x4004253c, track clamped
# 0..3 x 808B rows) -> c31972 session-virtual chain (0x40042544).
P_ENTRY = 0x4004221c
P_C6BARET = 0x40042246  # d0 = c6ba view-track result
P_CMP = 0x40042258      # moveq #3,d0; cmp.l d4,d0
P_GATE = 0x40042530     # synth-chain gate
P_ROWJSR = 0x4004253c   # jsr c1dcf2 (row fetch)
KIT_SND_OFF = 0x18
SND_REC = 326


def _home(r):
    s = r.s
    for _ in range(4):
        s.press(s.code('NO'))
        s.run_ms(80)
        s.release(s.code('NO'))
        s.run_ms(120)
    s.run_ms(300)


def leg_sweep(converted=False, keys=PAGE_KEYS, base=None):
    """Page-gesture sweep in ONE session, selection fixed per session.

    Native: ACTIVE stays `base` (default 0). Converted: slot (base-4)
    converted up front, ACTIVE stays on the MIDI bank via toggle.
    Per gesture: clear hits, press, settle, record hits + fb.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'sweep', 'converted': converted, 'tag': BUILD['tag'],
           'gestures': []}
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
    s.at(S8_ENTRY, on_hit('s8entry', DREGS))
    s.at(S8, on_hit('s8', (('d0', UC_M68K_REG_D0),
                           ('d1', UC_M68K_REG_D1))))
    s.at(S8_SYNTH, on_hit('s8synth', (('d0', UC_M68K_REG_D0),)))
    s.at(S8_VIRT, on_hit('s8virt', DREGS))
    s.at(S8_MIDI, on_hit('s8midi', (('d0', UC_M68K_REG_D0),)))
    s.at(S8_SYNTHFN, on_hit('s8synthfn', DREGS))
    s.at(S5, on_hit('s5', (('d6', UC_M68K_REG_D6),
                           ('d0', UC_M68K_REG_D0))))
    s.at(S5_SYNTH1, on_hit('s5synth1', DREGS))
    s.at(S5_SYNTH2, on_hit('s5synth2', DREGS))
    s.at(S5_MIDI, on_hit('s5midi', DREGS))
    s.at(S5_MIDIFN, on_hit('s5midifn', DREGS))

    b = 0 if not converted else 4
    if base is not None:
        b = base
    V.select(r, b)
    if converted:
        V.open_modal(r, b - 4)
        r.key('YES', hold=15, after=600)
        assert r.slot() == -1 and r.state(b - 4) == 1, 'YES did not flip'
        V.midi_to_bank(r, True)
    out['active_start'] = u32(s.m, B.ACTIVE)
    out['main_fb'] = sha(r.settle_fb())[:16]

    for key in keys:
        g = {'key': key}
        try:
            del hits[:]
            h0 = sha(fb(s.m, s))
            if '+' in key and '>' not in key:
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
                    s.press(s.code(name))
                    s.run_ms(120)
                    s.release(s.code(name))
                    s.run_ms(400)

                _press(parts[0])
                s.run_ms(100)
                for sub in parts[1:]:
                    _press(sub)
                    s.run_ms(100)
            elif key == 'ENC-A':
                s.turn(1, 2, 300)
                s.run_ms(300)
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
                V.select(r, b)
        except Exception as e:
            out.setdefault('recover_blocked', []).append(
                '%s after %s: %s' % (type(e).__name__, key, e))
            break
    out['active_end'] = u32(s.m, B.ACTIVE)
    r.close()
    out['wall'] = r.wall
    return out


def leg_proof(tracks=(0, 1, 2, 3, 4, 5, 6, 7), keys=('SYN1',),
              convtracks=(4,)):
    """Targeted per-track cells on the firing gestures (live P sites).

    S8/S5 proved silent on page opens (sweep + chain legs); the live
    dispatch is the page function at P_ENTRY 0x4004221c: d4 = c6ba
    view-track result, compared vs 3 at P_CMP 0x40042258, synth chain
    via P_GATE 0x40042530 -> c1dcf2 row fetch -> c31972 virtuals.
    Per cell: page open (outcome-verified), P_CMP d4 + ACTIVE, P_C6BARET
    d0, gate/chain fork taken, row+16 vs kit sound, S8/S5 silence.
    Verdict per cell: d4 == ACTIVE-at-press?
    Converted slots are converted in-track-order in ONE session (ACTIVE
    only moves forward); natives select normally.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn.m68k_const import UC_M68K_REG_A7
    out = {'leg': 'proof', 'tag': BUILD['tag'],
           'keys': list(keys), 'cells': []}
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

    def on_row(uc, a, sz, d):
        if len(hits) < 300:
            try:
                sp = int(uc.reg_read(UC_M68K_REG_A7))
                words = []
                for k in range(6):
                    raw = s.m.peek(sp + 4 * k, 4)
                    if not raw or len(raw) < 4:
                        break
                    words.append(struct.unpack('>I', raw)[0])
                e = {'site': 'c1dcf2', 'active': u32(s.m, B.ACTIVE),
                     'stack': ['0x%x' % w for w in words]}
                # track arg = first pushed (sp+8: caller pushes
                # track then table, jsr pushes ret).
                if len(words) >= 3:
                    e['track'] = words[2] & 0xFFFFFFFF
                hits.append(e)
            except Exception:
                pass

    def on_chain(uc, a, sz, d):
        if len(hits) < 300:
            try:
                sp = int(uc.reg_read(UC_M68K_REG_A7))
                raw = s.m.peek(sp + 4, 4)
                row = struct.unpack('>I', raw)[0] if raw else None
                e = {'site': 'c31972', 'active': u32(s.m, B.ACTIVE),
                     'row': ('0x%08x' % row) if row else None}
                if row:
                    r16 = s.m.peek(row + 16, 4)
                    e['row16'] = ('0x%08x' % struct.unpack(
                        '>I', r16)[0]) if r16 else None
                    kit = u32(s.m, 0x4138f220)
                    e['kit_snd'] = ['0x%08x' % (kit + KIT_SND_OFF +
                                                SND_REC * t)
                                    for t in range(8)] if kit else None
                hits.append(e)
            except Exception:
                pass

    s.at(P_C6BARET, on_hit('p_c6baret', (('d0', UC_M68K_REG_D0),)))
    s.at(P_CMP, on_hit('p_cmp', (('d4', UC_M68K_REG_D4),
                                 ('d0', UC_M68K_REG_D0))))
    s.at(P_GATE, on_hit('p_gate', DREGS))
    s.at(C1DCF2, on_row)
    s.at(C31972, on_chain)
    s.at(P_ROWJSR + 6, on_hit('p_rowret', (('d0', UC_M68K_REG_D0),)))
    # S8/S5 silence witnesses (must stay empty on page opens).
    s.at(S8, on_hit('s8', (('d0', UC_M68K_REG_D0),)))
    s.at(S5, on_hit('s5', (('d6', UC_M68K_REG_D6),)))

    # Natives + native-MIDI first (T-select works), then sequential
    # convert + prove per slot (ACTIVE stays 4+i; no backward travel).
    done_conv = set()
    for track in tracks:
        for key in keys:
            c = {'track': track, 'key': key}
            try:
                if track in convtracks and \
                        r.state(track - 4) != 1:
                    # Establish bank memory while native, then convert.
                    V.select(r, track)
                    V.open_modal(r, track - 4)
                    r.key('YES', hold=15, after=600)
                    assert r.slot() == -1 and \
                        r.state(track - 4) == 1, 'YES did not flip'
                    done_conv.add(track - 4)
                    V.midi_to_bank(r, True)
                elif track < 4 or r.state(track - 4) == 1:
                    if track < 4:
                        V.select(r, track)
                    else:
                        # Already-converted slot: ride the MIDI toggle
                        # back (bank memory intact; never T-select
                        # converted).
                        V.midi_to_bank(r, True)
                        assert u32(s.m, B.ACTIVE) == track, \
                            'toggle did not reach t%d' % track
                else:
                    # Native MIDI track: bank-aware select (never convert).
                    V.select(r, track)
                c['active_at_press'] = u32(s.m, B.ACTIVE)
                del hits[:]
                h0 = sha(fb(s.m, s))
                for _ in range(4):
                    s.press(s.code(key))
                    s.run_ms(120)
                    s.release(s.code(key))
                    s.run_ms(400)
                    if sha(fb(s.m, s)) != h0:
                        break
                s.run_ms(300)
                c['fb'] = sha(r.settle_fb())[:16]
                c['fb_changed'] = (c['fb'] != h0[:16])
                c['hits'] = list(hits)
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
                    k: {'n': v['n'], 'regs': sorted(v['regs']),
                        'actives': sorted(v['actives'])}
                    for k, v in summ.items()}
                # Verdicts: P_CMP d4 == ACTIVE? c6ba d0 == ACTIVE?
                # row+16 == kit sound of which track?
                for h in hits:
                    if h['site'] == 'p_cmp':
                        h['d4_is_active'] = (
                            h['d4'] == c['active_at_press'])
                    if h['site'] == 'p_c6baret':
                        h['d0_is_active'] = (
                            h['d0'] == c['active_at_press'])
                    if h['site'] == 'c31972' and h.get('row16'):
                        h['row16_is_kit'] = (
                            h['row16'] in (h.get('kit_snd') or []))
            except Exception as e:
                c['blocked'] = '%s: %s' % (type(e).__name__, e)
            out['cells'].append(c)
            _home(r)
    out['converted'] = [r.state(i) for i in range(4)]
    r.close()
    out['wall'] = r.wall
    return out


def leg_chain(tracks=(0, 4, 5), keys=('SYN1', 'SYN2', 'FLTR'),
              convtracks=(4,)):
    """Chain-entry discovery: who draws param pages on each track?

    Hooks entries of the spike's synth-chain functions (0x4001dcf2,
    0x40031ce2, 0x40031972), the S8 synth helper (0x401880e6), the S5
    MIDI function (0x400ded80) and the S8 enclosing entry. Logs d-regs
    + ACTIVE + caller (return address) per page open. Converted slots
    are converted in-track-order in ONE session; natives select
    normally; converted reached via MIDI toggle.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn.m68k_const import UC_M68K_REG_A7
    out = {'leg': 'chain', 'tag': BUILD['tag'],
           'tracks': list(tracks), 'keys': list(keys), 'cells': []}
    hits = []

    def on_hit(site, regs):
        def cb(uc, a, sz, d):
            if len(hits) < 300:
                try:
                    e = {'site': site,
                         'active': u32(s.m, B.ACTIVE)}
                    for nm, rg in regs:
                        e[nm] = int(uc.reg_read(rg))
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

    DREGS = (('d0', UC_M68K_REG_D0), ('d1', UC_M68K_REG_D1),
             ('d2', UC_M68K_REG_D2), ('d3', UC_M68K_REG_D3),
             ('d4', UC_M68K_REG_D4), ('d5', UC_M68K_REG_D5),
             ('d6', UC_M68K_REG_D6), ('d7', UC_M68K_REG_D7))
    s.at(C1DCF2, on_hit('c1dcf2', DREGS))
    s.at(C31CE2, on_hit('c31ce2', DREGS))
    s.at(C31972, on_hit('c31972', DREGS))
    s.at(S8_SYNTHFN, on_hit('s8synthfn', DREGS))
    s.at(S5_MIDIFN, on_hit('s5midifn', DREGS))
    s.at(S8_ENTRY, on_hit('s8entry', DREGS))
    s.at(S8_VIRT, on_hit('s8virt', DREGS))
    s.at(S8_MIDI, on_hit('s8midi', DREGS))

    done_conv = set()
    for track in tracks:
        for key in keys:
            c = {'track': track, 'key': key}
            try:
                if track in convtracks and r.state(track - 4) != 1:
                    V.select(r, track)
                    V.open_modal(r, track - 4)
                    r.key('YES', hold=15, after=600)
                    assert r.slot() == -1 and \
                        r.state(track - 4) == 1, 'YES did not flip'
                    done_conv.add(track - 4)
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
                for _ in range(4):
                    s.press(s.code(key))
                    s.run_ms(120)
                    s.release(s.code(key))
                    s.run_ms(400)
                    if sha(fb(s.m, s)) != h0:
                        break
                s.run_ms(300)
                c['fb'] = sha(r.settle_fb())[:16]
                c['fb_changed'] = (c['fb'] != h0[:16])
                c['hits'] = list(hits)
                summ = {}
                for h in hits:
                    e = summ.setdefault(h['site'], {'n': 0, 'regs': set(),
                                                    'callers': set()})
                    e['n'] += 1
                    e['callers'].add(h.get('caller'))
                    for k, v in h.items():
                        if k.startswith('d') and len(k) == 2:
                            e['regs'].add('%s=%d' % (k, v))
                c['summary'] = {
                    k: {'n': v['n'], 'regs': sorted(v['regs'])[:10],
                        'callers': sorted(x for x in v['callers']
                                          if x)}
                    for k, v in summ.items()}
            except Exception as e:
                c['blocked'] = '%s: %s' % (type(e).__name__, e)
            out['cells'].append(c)
            _home(r)
    out['converted'] = [r.state(i) for i in range(4)]
    r.close()
    out['wall'] = r.wall
    return out


def leg_pageopen(tracks=(0, 4, 5), keys=('SYN1', 'SYN2', 'FLTR', 'AMP'),
                 convtracks=(4,)):
    """Post-patch page parity (0.20): converted slots take the synth chain.

    Per cell: convert as needed, open the page (outcome-verified), log
    P1 result (d0: mirror slot for converted, stock track native), P2
    result (d0: mod page row for converted, stock heap row native),
    c31972 row+16 (must be the slot .bss SND for converted, kit sound
    native), S8/S5 silence witnesses, settled fb + PNG capture.
    SND address comes from the linked build map.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn.m68k_const import UC_M68K_REG_D0, UC_M68K_REG_A7
    SND = B._addr('cnv_synth_snd')
    out = {'leg': 'pageopen', 'tag': BUILD['tag'],
           'tracks': list(tracks), 'keys': list(keys),
           'snd': '0x%08x' % SND, 'cells': []}
    pngdir = os.environ.get('CNV_PNGDIR')
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

    def on_p2(uc, a, sz, d):
        if len(hits) < 300:
            try:
                sp = int(uc.reg_read(UC_M68K_REG_A7))
                args = []
                for k in range(1, 3):
                    raw = s.m.peek(sp + 4 * k, 4)
                    if raw and len(raw) == 4:
                        args.append(struct.unpack('>I', raw)[0])
                e = {'site': 'p2', 'active': u32(s.m, B.ACTIVE),
                     'stack': ['0x%x' % v for v in args]}
                hits.append(e)
            except Exception:
                pass

    def on_chain(uc, a, sz, d):
        if len(hits) < 100:
            try:
                sp = int(uc.reg_read(UC_M68K_REG_A7))
                raw = s.m.peek(sp + 4, 4)
                row = struct.unpack('>I', raw)[0] if raw else None
                e = {'site': 'c31972', 'active': u32(s.m, B.ACTIVE),
                     'row': ('0x%08x' % row) if row else None}
                if row:
                    r16 = s.m.peek(row + 16, 4)
                    e['row16'] = ('0x%08x' % struct.unpack(
                        '>I', r16)[0]) if r16 else None
                    slot = (e['active'] - 4
                            if e['active'] is not None else None)
                    if slot is not None and 0 <= slot < 4:
                        e['snd_slot'] = '0x%08x' % (SND + 326 * slot)
                hits.append(e)
            except Exception:
                pass

    s.at(0x40042240, on_hit('p1', (('d0', UC_M68K_REG_D0),)))
    s.at(0x40042246, on_hit('p1ret', (('d0', UC_M68K_REG_D0),)))
    s.at(P_ROWJSR, on_p2)
    s.at(P_ROWJSR + 6, on_hit('p2ret', (('d0', UC_M68K_REG_D0),)))
    s.at(C31972, on_chain)
    s.at(S8, on_hit('s8', (('d0', UC_M68K_REG_D0),)))
    s.at(S5, on_hit('s5', (('d6', UC_M68K_REG_D6),)))

    for track in tracks:
        for key in keys:
            c = {'track': track, 'key': key}
            try:
                if track in convtracks and r.state(track - 4) != 1:
                    V.select(r, track)
                    V.open_modal(r, track - 4)
                    r.key('YES', hold=15, after=600)
                    assert r.slot() == -1 and \
                        r.state(track - 4) == 1, 'YES did not flip'
                    V.midi_to_bank(r, True)
                elif track < 4 or r.state(track - 4) == 1:
                    if track < 4:
                        V.select(r, track)
                    else:
                        V.midi_to_bank(r, True)
                        assert u32(s.m, B.ACTIVE) == track, \
                            'toggle did not reach t%d' % track
                else:
                    V.select(r, track)
                c['active_at_press'] = u32(s.m, B.ACTIVE)
                del hits[:]
                h0 = sha(fb(s.m, s))
                # ONE press only: the open page, settled. Extra presses
                # toggle subpages ((1/2) <-> (2/2)) and would capture the
                # wrong page (the old loop over-pressed on slow draws).
                s.press(s.code(key))
                s.run_ms(120)
                s.release(s.code(key))
                s.run_ms(1500)
                buf = r.settle_fb()
                c['fb'] = sha(buf)[:16]
                c['fb_changed'] = (c['fb'] != h0[:16])
                if pngdir:
                    p = os.path.join(
                        pngdir, 'cap_pageopen_t%d_%s.png' % (track, key))
                    panel.write_png(buf, p)
                    c['png'] = p
                p1 = [h['d0'] for h in hits if h['site'] == 'p1ret']
                p2 = [h.get('stack') for h in hits if h['site'] == 'p2']
                p2r = [h['d0'] for h in hits if h['site'] == 'p2ret']
                ch = [h for h in hits if h['site'] == 'c31972']
                c['p1_d0'] = sorted(set(p1))
                c['p2_stack'] = sorted(set(tuple(s_) for s_ in p2 if s_))
                c['p2ret_d0'] = sorted(set('0x%x' % v for v in p2r))
                c['chain_rows'] = sorted(set(
                    h.get('row16') for h in ch if h.get('row16')))
                c['s8_n'] = sum(1 for h in hits if h['site'] == 's8')
                c['s5_n'] = sum(1 for h in hits if h['site'] == 's5')
                # Verdicts.
                slot = (track - 4 if track in convtracks else None)
                if slot is not None:
                    c['p1_is_mirror'] = (c['p1_d0'] == [slot])
                    c['p2_is_modrow'] = all(
                        0x43ec0000 <= v < 0x43ec4000 for v in p2r)
                    c['row16_is_snd'] = (
                        bool(ch) and all(
                            h.get('row16') == h.get('snd_slot')
                            for h in ch))
                else:
                    c['p1_is_track'] = (c['p1_d0'] == [track])
                    kit = u32(s.m, 0x4138f220)
                    ksnd = ('0x%08x' % (kit + KIT_SND_OFF +
                                        SND_REC * track)) if kit else None
                    c['row16_is_kit'] = (
                        bool(ch) and all(
                            h.get('row16') == ksnd for h in ch))
            except Exception as e:
                c['blocked'] = '%s: %s' % (type(e).__name__, e)
            out['cells'].append(c)
            _home(r)
    out['converted'] = [r.state(i) for i in range(4)]
    r.close()
    out['wall'] = r.wall
    return out


def leg_knob(slot=0, key='SYN1', turns=3):
    """Post-patch knob proof: encoder edits write the slot .bss record.

    Convert slot, open the page, snapshot SND + kit slot region, turn
    encoder A, re-snapshot: .bss bytes must change, kit sounds must
    not. Flip-back + restore keep working afterwards.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    SND = B._addr('cnv_synth_snd')
    out = {'leg': 'knob', 'tag': BUILD['tag'], 'slot': slot, 'key': key}
    try:
        track = 4 + slot
        V.select(r, track)
        V.open_modal(r, slot)
        r.key('YES', hold=15, after=600)
        assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
        V.midi_to_bank(r, True)
        h0 = sha(fb(s.m, s))
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        kit = u32(s.m, 0x4138f220)
        snd_pre = bytes(s.m.peek(SND + 326 * slot, 326))
        kit_pre = bytes(s.m.peek(kit + KIT_SND_OFF, 326 * 4))
        midi_pre = bytes(s.m.peek(kit + 0x5ce, 164 * 4))
        for _ in range(turns):
            s.turn(1, 2, 300)
            s.run_ms(300)
        r.settle_fb()
        snd_post = bytes(s.m.peek(SND + 326 * slot, 326))
        kit_post = bytes(s.m.peek(kit + KIT_SND_OFF, 326 * 4))
        midi_post = bytes(s.m.peek(kit + 0x5ce, 164 * 4))
        out['snd_changed'] = (snd_post != snd_pre)
        out['snd_diff_n'] = sum(1 for a, b in zip(snd_pre, snd_post)
                                if a != b)
        out['kit_same'] = (kit_post == kit_pre)
        out['midi_changed'] = (midi_post != midi_pre)
        out['midi_diff_n'] = sum(1 for a, b in zip(midi_pre, midi_post)
                                 if a != b)
        # Flip-back still works after knob edits.
        V.midi_to_bank(r, True)
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
        out['flipback_state'] = r.state(slot)
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_timbre(slot=0, key='SYN1'):
    """Post-patch timbre proof: the knob edit changes the rendered sound.

    audio=True, converted slot sounding via sequencer: PLAY energy
    series E1, tweak encoder A on the SYN1 page, PLAY energy series E2.
    Both must render (max > 0) and the series must differ. Other tracks
    muted via pattern-mute poke (cnv_browser voice-leg discipline).
    """
    use_build(BUILD)
    r = B.Run(audio=True)
    s = r.s
    m = s.m
    out = {'leg': 'timbre', 'tag': BUILD['tag'], 'slot': slot}
    try:
        from emu import midi  # noqa: E402
        tx = midi.MidiOut(sink=bytearray().extend)
        tx.install(s.m)
        tx.attach(s.m, s.ips)
        s.sources = s.sources + (tx,)

        def tap(name, hold=15, after=15):
            s.press(s.code(name))
            s.run_ms(hold)
            s.release(s.code(name))
            s.run_ms(after)

        track = 4 + slot
        V.select(r, track)
        V.open_modal(r, slot)
        r.key('YES', hold=15, after=600)
        assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
        V.midi_to_bank(r, True)
        # Program trigs 2/6/10/14 on the converted track.
        tap('RECORD')
        for st in ('2', '6', '10', '14'):
            tap(st)
        tap('RECORD')
        for tr in (0, 1, 2, 3):
            m.poke(r.pat + B.PAT_MUTES_OFF + tr, bytes([1]))

        def play_series():
            tap('PLAY', hold=60, after=100)
            series = []
            for _ in range(8):
                s.run_ms(500)
                raw = bytes(m.peek(B.VOICES, B.VOICES_LEN))
                n = len(raw) // 4
                vals = struct.unpack('>' + 'i' * n, raw)
                series.append({'max': max(abs(v) for v in vals),
                               'avg': sum(abs(v) for v in vals) // n})
            tap('STOP', hold=60, after=100)
            tap('STOP', hold=60, after=100)
            return series

        e1 = play_series()
        # Tweak a knob on the synth page.
        h0 = sha(fb(s.m, s))
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.turn(1, -32, 300)
        s.run_ms(300)
        e2 = play_series()
        out['e1_max'] = max(p['max'] for p in e1)
        out['e2_max'] = max(p['max'] for p in e2)
        out['series_differ'] = (e1 != e2)
        out['pass'] = (out['e1_max'] > 0 and out['e2_max'] > 0 and
                       out['series_differ'])
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_muteseq(slot=0):
    """Mute + sequencer index-agnostic verify (no patch, captures only).

    Mute: FUNC+T-key toggle on the converted track flips the pattern
    mute byte + audio-mask bit and back. Sequencer: 2-bar PLAY renders
    converted-track voices energy > 0. Either may BLOCK with evidence.
    """
    use_build(BUILD)
    r = B.Run(audio=True)
    s = r.s
    m = s.m
    out = {'leg': 'muteseq', 'tag': BUILD['tag'], 'slot': slot}
    try:
        from emu import midi  # noqa: E402
        tx = midi.MidiOut(sink=bytearray().extend)
        tx.install(s.m)
        tx.attach(s.m, s.ips)
        s.sources = s.sources + (tx,)

        def key(name, hold=120, after=300):
            s.press(s.code(name))
            s.run_ms(hold)
            s.release(s.code(name))
            s.run_ms(after)

        track = 4 + slot
        V.select(r, track)
        V.open_modal(r, slot)
        r.key('YES', hold=15, after=600)
        assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
        V.midi_to_bank(r, True)
        muteb = r.pat + B.PAT_MUTES_OFF + track
        out['mute_pre'] = m.peek(muteb, 1)[0]
        # Candidate mute gestures; first one that flips the byte wins.
        flipped = None
        for g in ('FUNC+T1', 'FUNC+T2', 'FUNC+T3', 'FUNC+T4'):
            tkey = 'T%d' % (slot + 1)
            held, tapped = g.split('+')
            if tapped != tkey:
                continue
            s.press(s.code(held))
            s.run_ms(80)
            s.press(s.code(tapped))
            s.run_ms(150)
            s.release(s.code(tapped))
            s.run_ms(200)
            s.release(s.code(held))
            s.run_ms(500)
            if m.peek(muteb, 1)[0] != out['mute_pre']:
                flipped = g
                break
        out['mute_gesture'] = flipped
        out['mute_post'] = m.peek(muteb, 1)[0]
        out['mute_flips'] = (out['mute_post'] != out['mute_pre'])
        # Flip back for the sequencer leg.
        if out['mute_flips']:
            held, tapped = flipped.split('+')
            s.press(s.code(held))
            s.run_ms(80)
            s.press(s.code(tapped))
            s.run_ms(150)
            s.release(s.code(tapped))
            s.run_ms(200)
            s.release(s.code(held))
            s.run_ms(500)
            out['mute_restored'] = (m.peek(muteb, 1)[0] == out['mute_pre'])
        # Sequencer: program + PLAY 2 bars, voices energy.
        key('RECORD')
        for st in ('2', '6', '10', '14'):
            key(st)
        key('RECORD')
        for tr in (0, 1, 2, 3):
            m.poke(r.pat + B.PAT_MUTES_OFF + tr, bytes([1]))
        key('PLAY', hold=60, after=100)
        mx = 0
        for _ in range(8):
            s.run_ms(500)
            raw = bytes(m.peek(B.VOICES, B.VOICES_LEN))
            n = len(raw) // 4
            vals = struct.unpack('>' + 'i' * n, raw)
            mx = max(mx, max(abs(v) for v in vals))
        key('STOP', hold=60, after=100)
        key('STOP', hold=60, after=100)
        out['seq_energy_max'] = mx
        out['seq_sounds'] = mx > 0
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_fixreg():
    """Post-patch regression subset on the new build (proven 3.1/3.2/3.3).

    Voice-menu open parity (V8 divert + ded70 + 58770 caller +
    synth-fork taken + settled fb + PNGs), modal open/NO-cancel, and
    browser single-tap + kit-identity — all rebound to the new build.
    """
    use_build(BUILD)
    V.use_build(dict(BUILD))
    out = {'leg': 'fixreg', 'tag': BUILD['tag']}
    t0 = time.time()
    out['open'] = V.leg_open()
    out['regmodal'] = V.leg_regmodal()
    out['regbrowser'] = V.leg_regbrowser()
    out['wall'] = round(time.time() - t0, 1)
    return out


def leg_knobtrace(slot=0, key='SYN1', conv=True):
    """Knob-edit path trace on a converted page (diagnostic).

    Opens the converted page, then turns encoder 1 with hooks on the
    S8 family (entry/site/synth/virt/midi), the P1/P2 sites, the c31972
    chain and s5midifn. Records regs + ACTIVE + fb change + SND delta.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn.m68k_const import UC_M68K_REG_D0, UC_M68K_REG_A7
    SND = B._addr('cnv_synth_snd')
    out = {'leg': 'knobtrace', 'tag': BUILD['tag'], 'slot': slot,
           'key': key}
    hits = []

    def on_hit(site, regs):
        def cb(uc, a, sz, d):
            if len(hits) < 400:
                try:
                    e = {'site': site,
                         'active': u32(s.m, B.ACTIVE)}
                    for nm, rg in regs:
                        e[nm] = int(uc.reg_read(rg))
                    hits.append(e)
                except Exception:
                    pass
        return cb

    D1 = (('d0', UC_M68K_REG_D0),)
    DREGS = (('d0', UC_M68K_REG_D0), ('d1', UC_M68K_REG_D1),
             ('d2', UC_M68K_REG_D2), ('d3', UC_M68K_REG_D3),
             ('d4', UC_M68K_REG_D4), ('d5', UC_M68K_REG_D5),
             ('d6', UC_M68K_REG_D6), ('d7', UC_M68K_REG_D7))
    s.at(S8_ENTRY, on_hit('s8entry', DREGS))
    s.at(S8, on_hit('s8', DREGS))
    s.at(S8_SYNTH, on_hit('s8synth', D1))
    s.at(S8_VIRT, on_hit('s8virt', DREGS))
    s.at(S8_MIDI, on_hit('s8midi', D1))
    s.at(S8_SYNTHFN, on_hit('s8synthfn', DREGS))
    s.at(0x40042240, on_hit('p1', D1))
    s.at(P_ROWJSR, on_hit('p2', D1))
    s.at(C31972, on_hit('c31972', D1))
    s.at(S5_MIDIFN, on_hit('s5midifn', D1))
    s.at(S5, on_hit('s5', DREGS))
    try:
        if conv:
            track = 4 + slot
            V.select(r, track)
            V.open_modal(r, slot)
            r.key('YES', hold=15, after=600)
            assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
            V.midi_to_bank(r, True)
        else:
            track = slot
            V.select(r, track)
        out['converted_slot'] = conv
        h0 = sha(fb(s.m, s))
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        snd_pre = bytes(s.m.peek(SND + 326 * slot, 326))
        del hits[:]
        h1 = sha(fb(s.m, s))
        s.turn(1, 4, 300)
        s.run_ms(500)
        buf = r.settle_fb()
        out['fb_changed'] = (sha(buf) != h1)
        out['png_fb'] = sha(buf)[:16]
        snd_post = bytes(s.m.peek(SND + 326 * slot, 326))
        out['snd_changed'] = (snd_post != snd_pre)
        out['snd_diff_n'] = sum(1 for a, b in zip(snd_pre, snd_post)
                                if a != b)
        summ = {}
        for h in hits:
            e = summ.setdefault(h['site'], {'n': 0, 'regs': set(),
                                            'actives': set()})
            e['n'] += 1
            e['actives'].add(h['active'])
            for k, v in h.items():
                if k.startswith('d') and len(k) == 2:
                    e['regs'].add('%s=%d' % (k, v))
        out['summary'] = {
            k: {'n': v['n'], 'regs': sorted(v['regs'])[:12],
                'actives': sorted(v['actives'])}
            for k, v in summ.items()}
        out['hits'] = hits[:60]
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_edittrace(slot=0, key='SYN1', conv=True):
    """Edit-write path trace (diagnostic): where do knob edits land?

    Native or converted page open, encoder turn with a mem-write watch
    over the whole kit cell (0x1000B): log writer PC + addr + size for
    every write during the turn and during commit-gesture candidates
    (YES, SYN2, PAGE). Reveals the edit buffer/commit site.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn.m68k_const import UC_M68K_REG_PC
    from unicorn import UC_HOOK_MEM_WRITE
    out = {'leg': 'edittrace', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    writes = []
    kit = u32(s.m, 0x4138f220)
    KIT_END = kit + 0x1000

    def on_write(uc, access, address, size, value, data):
        if len(writes) < 200:
            try:
                writes.append({'pc': '0x%08x' % int(uc.reg_read(
                    UC_M68K_REG_PC)), 'addr': '0x%08x' % address,
                    'size': size})
            except Exception:
                pass

    s.m.uc.hook_add(UC_HOOK_MEM_WRITE, on_write, kit, KIT_END - 1)
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
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        del writes[:]
        s.turn(1, 4, 300)
        s.run_ms(500)
        out['turn_writes'] = list(writes)
        for g in ('YES', 'SYN2', 'PAGE'):
            del writes[:]
            h1 = sha(fb(s.m, s))
            s.press(s.code(g))
            s.run_ms(120)
            s.release(s.code(g))
            s.run_ms(500)
            out['commit_%s_fb' % g] = (sha(r.settle_fb()) != h1)
            out['commit_%s_writes' % g] = list(writes)
            _home(r)
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_editcommit(slot=0, key='SYN1', conv=False):
    """Edit-commit path (diagnostic): which gesture writes the sound?

    Native or converted page open, snapshot the LIVE sound record
    (kit slot sound native / .bss SND converted), turn encoder 1,
    re-snapshot, then try commit gestures (YES, SYN2, PAGE, NO, TRIG,
    FUNC+YES...) re-snapshotting after each. Reports the first
    gesture after which the live record differs. No hooks, no noise.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'editcommit', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    try:
        kit = u32(s.m, 0x4138f220)
        SND = B._addr('cnv_synth_snd')
        if conv:
            track = 4 + slot
            V.select(r, track)
            V.open_modal(r, slot)
            r.key('YES', hold=15, after=600)
            assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
            V.midi_to_bank(r, True)
            base = SND + 326 * slot
        else:
            V.select(r, slot)
            base = kit + KIT_SND_OFF + 326 * slot
        out['live_rec'] = '0x%08x' % base
        h0 = sha(fb(s.m, s))
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        pre = bytes(s.m.peek(base, 326))
        neg = (key == 'SYN1')
        s.turn(1, -32 if neg else 8, 300)
        s.run_ms(500)
        steps = [('turn', bytes(s.m.peek(base, 326)))]
        for g in ('YES', 'SYN2', 'PAGE', 'NO', 'TRIG', 'RIGHT', 'LEFT'):
            s.press(s.code(g))
            s.run_ms(120)
            s.release(s.code(g))
            s.run_ms(500)
            steps.append((g, bytes(s.m.peek(base, 326))))
            _home(r)
            if conv:
                V.midi_to_bank(r, True)
            else:
                V.select(r, slot)
        first = None
        for name, snap in steps:
            if snap != pre:
                first = name
                break
        out['first_change'] = first
        out['diffs'] = {name: sum(1 for a, b in zip(pre, snap) if a != b)
                        for name, snap in steps}
        out['fb_changed_on_turn'] = True
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_contenttrace(slot=0, key='FLTR', conv=True):
    """Content-dispatch trace (diagnostic): who picks MIDI vs synth view?

    Single page-key press on native vs converted track with hooks on
    the three classifier entries (bankcheck 0x4002e1ae, view-track
    0x4002c6ba, trackmap 0x40025b76). Each hit logs caller + d-regs +
    ACTIVE + timestamp; analysis splits the open window (<600ms after
    the press) from settled refresh. The divergent open-window caller
    is the content dispatch.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn.m68k_const import UC_M68K_REG_A7, UC_M68K_REG_A2
    DREGS = (('d0', UC_M68K_REG_D0), ('d1', UC_M68K_REG_D1),
             ('d2', UC_M68K_REG_D2), ('d3', UC_M68K_REG_D3),
             ('d4', UC_M68K_REG_D4), ('d5', UC_M68K_REG_D5),
             ('d6', UC_M68K_REG_D6), ('d7', UC_M68K_REG_D7))
    E1AE = 0x4002e1ae
    C6BA = 0x4002c6ba
    T2576 = 0x40025b76
    out = {'leg': 'contenttrace', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    hits = []

    def on_cls(site, regs):
        def cb(uc, a, sz, d):
            if len(hits) < 600:
                try:
                    e = {'site': site, 'ms': round(s.ms, 1),
                         'active': u32(s.m, B.ACTIVE)}
                    for nm, rg in regs:
                        e[nm] = int(uc.reg_read(rg))
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

    s.at(E1AE, on_cls('e1ae', DREGS))
    s.at(C6BA, on_cls('c6ba', DREGS))
    s.at(T2576, on_cls('t2576', DREGS))
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
        t_press = round(s.ms, 1)
        s.press(s.code(key))
        s.run_ms(120)
        s.release(s.code(key))
        s.run_ms(800)
        buf = r.settle_fb()
        out['t_press'] = t_press
        out['fb_changed'] = (sha(buf) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        if os.environ.get('CNV_PNGDIR'):
            p = os.path.join(os.environ['CNV_PNGDIR'],
                             'cap_content_t%d_%s.png' %
                             ((4 + slot if conv else slot), key))
            panel.write_png(buf, p)
            out['png'] = p
        openw = [h for h in hits if h['ms'] - t_press < 600]
        out['open_hits'] = openw[:120]
        oc = {}
        for h in openw:
            oc[h['site'], h['caller']] = oc.get(
                (h['site'], h['caller']), 0) + 1
        out['open_callers'] = sorted(
            ((k[0], k[1], v) for k, v in oc.items()))
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_s4proof(tracks=(0, 2, 4, 5, 6, 7), keys=('FLTR', 'SYN1'),
                convtracks=(4, 6)):
    """S4-region proof (diagnostic): the page-key content dispatch.

    The prescribed S4 0x40043258 IS on the page-key path (silent only
    on VOICE, which is all 3.2 swept): c6ba result d0 -> d2, S4_PRE
    0x40043252 (moveq #9 view check), S4A 0x40043258 (moveq #3,d0;
    cmp.l d2,d0; blt MIDI) -> synth view builder 0x4002f91a vs MIDI
    fork 0x400432a0; downstream S4B 0x4004348a (own c6ba call at
    0x40043482) -> c1dd1a row fetch vs MIDI fork 0x400434c6.
    Per cell: single page-key press, S4A d2 + ACTIVE, S4B regs +
    ACTIVE, fork taken. Verdict: compared-reg == ACTIVE-at-press?
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn.m68k_const import UC_M68K_REG_A7, UC_M68K_REG_A2
    DREGS = (('d0', UC_M68K_REG_D0), ('d1', UC_M68K_REG_D1),
             ('d2', UC_M68K_REG_D2), ('d3', UC_M68K_REG_D3),
             ('d4', UC_M68K_REG_D4), ('d5', UC_M68K_REG_D5),
             ('d6', UC_M68K_REG_D6), ('d7', UC_M68K_REG_D7))
    S4_PRE = 0x40043252
    S4A = 0x40043258
    S4_SYNTH = 0x4004325e
    S4_MIDI = 0x400432a0
    S4_C6BA2 = 0x40043482
    S4B = 0x4004348a
    S4B_SYNTH = 0x40043490
    S4B_MIDI = 0x400434c6
    out = {'leg': 's4proof', 'tag': BUILD['tag'],
           'tracks': list(tracks), 'keys': list(keys), 'cells': []}
    hits = []

    def on_hit(site, regs):
        def cb(uc, a, sz, d):
            if len(hits) < 500:
                try:
                    e = {'site': site,
                         'active': u32(s.m, B.ACTIVE)}
                    for nm, rg in regs:
                        e[nm] = int(uc.reg_read(rg))
                    hits.append(e)
                except Exception:
                    pass
        return cb

    s.at(S4_PRE, on_hit('s4pre', DREGS))
    s.at(S4A, on_hit('s4a', (('d2', UC_M68K_REG_D2),
                             ('d0', UC_M68K_REG_D0))))
    s.at(S4_SYNTH, on_hit('s4synth', (('d2', UC_M68K_REG_D2),)))
    s.at(S4_MIDI, on_hit('s4midi', DREGS))
    s.at(S4_C6BA2, on_hit('s4c6ba2', DREGS))
    s.at(S4B, on_hit('s4b', DREGS))
    s.at(S4B_SYNTH, on_hit('s4bsynth', DREGS))
    s.at(S4B_MIDI, on_hit('s4bmidi', DREGS))

    for track in tracks:
        for key in keys:
            c = {'track': track, 'key': key}
            try:
                if track in convtracks and r.state(track - 4) != 1:
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
                s.press(s.code(key))
                s.run_ms(120)
                s.release(s.code(key))
                s.run_ms(1500)
                buf = r.settle_fb()
                c['fb'] = sha(buf)[:16]
                c['fb_changed'] = (c['fb'] != h0[:16])
                if os.environ.get('CNV_PNGDIR'):
                    p = os.path.join(os.environ['CNV_PNGDIR'],
                                     'cap_s4_t%d_%s.png' % (track, key))
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
                    if h['site'] == 's4a':
                        h['d2_is_active'] = (
                            h['d2'] == c['active_at_press'])
            except Exception as e:
                c['blocked'] = '%s: %s' % (type(e).__name__, e)
            out['cells'].append(c)
            _home(r)
    out['converted'] = [r.state(i) for i in range(4)]
    r.close()
    out['wall'] = r.wall
    return out


def leg_viewarg(slot=0, key='FLTR', conv=True):
    """View-id trace (diagnostic): what view does the key handler request?

    Hooks the 0x400432dc view-function entry (stack view-id args) +
    its 0x4004bd40 caller on native vs converted page-key opens.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn.m68k_const import UC_M68K_REG_A7, UC_M68K_REG_A2
    DREGS = (('d0', UC_M68K_REG_D0), ('d1', UC_M68K_REG_D1),
             ('d2', UC_M68K_REG_D2), ('d3', UC_M68K_REG_D3),
             ('d4', UC_M68K_REG_D4), ('d5', UC_M68K_REG_D5),
             ('d6', UC_M68K_REG_D6), ('d7', UC_M68K_REG_D7))
    out = {'leg': 'viewarg', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    hits = []

    def on_entry(uc, a, sz, d):
        if len(hits) < 100:
            try:
                sp = int(uc.reg_read(UC_M68K_REG_A7))
                words = []
                for k in range(8):
                    raw = s.m.peek(sp + 4 * k, 4)
                    if not raw or len(raw) < 4:
                        break
                    words.append(struct.unpack('>I', raw)[0])
                hits.append({'site': 'viewfn', 'ms': round(s.ms, 1),
                             'active': u32(s.m, B.ACTIVE),
                             'a2': '0x%08x' % int(uc.reg_read(
                                 UC_M68K_REG_A2)),
                             'stack': ['0x%x' % w for w in words]})
            except Exception:
                pass

    def on_hit(site, regs):
        def cb(uc, a, sz, d):
            if len(hits) < 100:
                try:
                    e = {'site': site, 'ms': round(s.ms, 1),
                         'active': u32(s.m, B.ACTIVE)}
                    for nm, rg in regs:
                        e[nm] = int(uc.reg_read(rg))
                    try:
                        sp = int(uc.reg_read(UC_M68K_REG_A7))
                        raw = s.m.peek(sp, 4)
                        e['caller'] = ('0x%08x' % struct.unpack(
                            '>I', raw)[0]) if raw else None
                        stk = []
                        for k in range(1, 5):
                            r2 = s.m.peek(sp + 4 * k, 4)
                            if r2 and len(r2) == 4:
                                stk.append(struct.unpack('>I', r2)[0])
                        e['stack'] = ['0x%x' % w for w in stk]
                    except Exception:
                        pass
                    hits.append(e)
                except Exception:
                    pass
        return cb

    s.at(0x400432dc, on_entry)
    s.at(0x4004bd40, on_hit('viewcall', DREGS))
    s.at(0x40042d84, on_hit('v84', DREGS))
    s.at(0x40042e68, on_hit('e68', DREGS))
    s.at(0x400e5f0e, on_hit('e5f0e', DREGS))
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
        t_press = round(s.ms, 1)
        s.press(s.code(key))
        s.run_ms(120)
        s.release(s.code(key))
        s.run_ms(250)
        out['open_hits'] = [h for h in hits]
        s.run_ms(800)
        buf = r.settle_fb()
        out['t_press'] = t_press
        out['fb_changed'] = (sha(buf) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        if os.environ.get('CNV_PNGDIR'):
            p = os.path.join(os.environ['CNV_PNGDIR'],
                             'cap_viewarg_t%d_%s.png' %
                             ((4 + slot if conv else slot), key))
            panel.write_png(buf, p)
            out['png'] = p
        out['hits'] = hits[:40]
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_bankread(slot=0, key='FLTR', conv=False):
    """Bank/state read trace (diagnostic): who reads ACTIVE/the bank?

    Mem-read hook on FW_ACTIVE_TRACK (0x41368ce0) during a single
    page-key open: log reader PC + ACTIVE. The page-key content
    selection must read the track/bank from somewhere; the divergent
    reader (or its absence) locates it.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn import UC_HOOK_MEM_READ
    from unicorn.m68k_const import UC_M68K_REG_PC
    ACTIVE = 0x41368ce0
    out = {'leg': 'bankread', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    reads = []

    def on_read(uc, access, address, size, value, data):
        if len(reads) < 300:
            try:
                reads.append({'pc': '0x%08x' % int(uc.reg_read(
                    UC_M68K_REG_PC)), 'addr': '0x%08x' % address,
                    'size': size})
            except Exception:
                pass

    s.m.uc.hook_add(UC_HOOK_MEM_READ, on_read, ACTIVE, ACTIVE + 3)
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
        del reads[:]
        t_press = round(s.ms, 1)
        s.press(s.code(key))
        s.run_ms(120)
        s.release(s.code(key))
        s.run_ms(400)
        out['t_press'] = t_press
        out['open_reads'] = list(reads)
        pcs = {}
        for rd in reads:
            pcs[rd['pc']] = pcs.get(rd['pc'], 0) + 1
        out['open_pcs'] = sorted(pcs.items(), key=lambda kv: -kv[1])[:30]
        buf = r.settle_fb()
        out['fb_changed'] = (sha(buf) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_idiomsweep(slot=0, key='FLTR', conv=False):
    """Track-fork sweep (diagnostic): find the content fork dynamically.

    Scans the MAIN image for the spike's `moveq #3,r; cmp.l; bcc`
    idiom, hooks every site (d-regs + ACTIVE), single page-key press.
    Sites firing with a compared-reg == ACTIVE on BOTH native and
    converted opens are content/render fork candidates. Pre-known
    sites (S1/S2/P_CMP/S4A/S8/S5) are flagged, not re-proven.
    """
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
        # cmp.l within next 2..6 bytes, then bcc within 2..4 after.
        for j in (i + 2, i + 4):
            if img[j] & 0xF0 != 0xB0:
                continue
            for k in (j + 2, j + 4):
                if img[k] & 0xFF != 0x6D and img[k] & 0xF0 != 0x60:
                    continue
                cands.append(a)
                break
            break
    cands = sorted(set(cands))[:60]
    r = B.Run(audio=False)
    s = r.s
    DREGS = (('d0', UC_M68K_REG_D0), ('d1', UC_M68K_REG_D1),
             ('d2', UC_M68K_REG_D2), ('d3', UC_M68K_REG_D3),
             ('d4', UC_M68K_REG_D4), ('d5', UC_M68K_REG_D5),
             ('d6', UC_M68K_REG_D6), ('d7', UC_M68K_REG_D7))
    from unicorn.m68k_const import UC_M68K_REG_A7  # noqa: E402
    out = {'leg': 'idiomsweep', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv, 'nsites': len(cands)}
    hits = []

    def mk(site):
        def cb(uc, a, sz, d):
            if len(hits) < 800:
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
        s.press(s.code(key))
        s.run_ms(120)
        s.release(s.code(key))
        s.run_ms(600)
        buf = r.settle_fb()
        out['fb_changed'] = (sha(buf) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        matched = {}
        for h in hits:
            regs = [v for k, v in h.items()
                    if k.startswith('d') and len(k) == 2]
            if h['active'] in regs:
                e = matched.setdefault(h['site'], {'n': 0})
                e['n'] += 1
        out['matched'] = sorted(matched.items())
        out['nsites_fired'] = len(set(h['site'] for h in hits))
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_listhead(slot=0, key='FLTR', conv=False):
    """Page-list selection trace (diagnostic): who sets the view list?

    The draw bus walks the page list at 1c(a2) (a2 = 0x41a0a7e0 both
    banks); the key handler must swap the list head on page opens.
    Mem-write watch on that word during a single open: the writer PC
    is the content selector. Short window keeps the unfiltered hook
    tractable (list-head writes are rare).
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn import UC_HOOK_MEM_WRITE
    from unicorn.m68k_const import UC_M68K_REG_PC
    LISTHEAD = 0x41a0a7e0 + 0x1c
    out = {'leg': 'listhead', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    writes = []

    def on_write(uc, access, address, size, value, data):
        if address != LISTHEAD:
            return
        if len(writes) < 40:
            try:
                writes.append({'pc': '0x%08x' % int(uc.reg_read(
                    UC_M68K_REG_PC)),
                    'value': '0x%08x' % value, 'size': size,
                    'ms': round(s.ms, 1),
                    'active': u32(s.m, B.ACTIVE)})
            except Exception:
                pass

    s.m.uc.hook_add(UC_HOOK_MEM_WRITE, on_write)
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
        del writes[:]
        s.press(s.code(key))
        s.run_ms(120)
        s.release(s.code(key))
        s.run_ms(600)
        buf = r.settle_fb()
        out['fb_changed'] = (sha(buf) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        out['writes'] = list(writes)
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_v84gate(slot=0, key='FLTR', conv=False):
    """v84 view-9 gate verify (diagnostic): the content fork candidate.

    v84 (0x40042d84) first virtual (a0+$a0)(8,a2) -> d0; beq 0x40042e5e
    skips the view-9 path (jsr (a0+$58) -> ret 0x40042dbe -> viewfn 9
    -> c6ba -> synth builder), else takes it. Log d0 at 0x40042da8 +
    taken/skip + ACTIVE on native/converted/native-MIDI opens. Gate
    proven iff nat d0 != 0 (taken) and conv/MIDI d0 == 0 (skip).
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    D1 = (('d0', UC_M68K_REG_D0),)
    out = {'leg': 'v84gate', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
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

    s.at(0x40042da8, on_hit('v84d0', D1))
    s.at(0x40042dbe, on_hit('v84taken', D1))
    s.at(0x40042e5e, on_hit('v84skip', D1))
    # P3 caller witness: at the (patched) site, sp -> [site-ret];
    # v84 ret sits 36 bytes above (entry lea-36, args already dropped
    # by the rejoin addq #8). Logs the word the detour reads.
    def on_site(uc, a, sz, d):
        if len(hits) < 300:
            try:
                from unicorn.m68k_const import UC_M68K_REG_A7
                sp = int(uc.reg_read(UC_M68K_REG_A7))
                raw = s.m.peek(sp + 36, 4)
                hits.append({'site': 'p3site',
                             'active': u32(s.m, B.ACTIVE),
                             'd0': int(uc.reg_read(
                                 UC_M68K_REG_D0)),
                             'ret36': ('0x%08x' % struct.unpack(
                                 '>I', raw)[0]) if raw else None})
            except Exception:
                pass
    s.at(0x40042da8, on_site)
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
        s.press(s.code(key))
        s.run_ms(120)
        s.release(s.code(key))
        s.run_ms(600)
        buf = r.settle_fb()
        out['fb_changed'] = (sha(buf) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        d0s = sorted(set(h['d0'] for h in hits if h['site'] == 'v84d0'))
        out['v84_d0'] = d0s
        out['taken_n'] = sum(1 for h in hits if h['site'] == 'v84taken')
        out['skip_n'] = sum(1 for h in hits if h['site'] == 'v84skip')
        out['p3rets'] = sorted(set(
            h.get('ret36') for h in hits if h['site'] == 'p3site'))
        out['p3d0'] = sorted(set(
            h.get('d0') for h in hits if h['site'] == 'p3site'))
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_viewfn9(slot=0, key='FLTR', conv=True):
    """Forced-path trace (diagnostic): does view-9 reach the builder?

    Hooks the viewfn entry (0x400432dc, stack view-id arg), the
    c6ba-after-view9 site and the 0x4002f91a builder on a converted
    page open with P3 forcing. If the synth builder runs but the
    screen stays MIDI, the view SWITCH (not the render) is missing.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn.m68k_const import UC_M68K_REG_A7
    D1 = (('d0', UC_M68K_REG_D0),)
    out = {'leg': 'viewfn9', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
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

    def on_viewfn(uc, a, sz, d):
        if len(hits) < 300:
            try:
                sp = int(uc.reg_read(UC_M68K_REG_A7))
                words = []
                for k in range(4):
                    raw = s.m.peek(sp + 4 * k, 4)
                    words.append(struct.unpack('>I', raw)[0]
                                 if raw else None)
                hits.append({'site': 'viewfn',
                             'active': u32(s.m, B.ACTIVE),
                             'stack': ['0x%x' % w if w is not None
                                       else None for w in words]})
            except Exception:
                pass

    s.at(0x400432dc, on_viewfn)
    s.at(0x4002f91a, on_hit('builder', D1))
    s.at(0x40042dbe, on_hit('v84taken', D1))
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
        s.press(s.code(key))
        s.run_ms(120)
        s.release(s.code(key))
        s.run_ms(600)
        buf = r.settle_fb()
        out['fb_changed'] = (sha(buf) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        if os.environ.get('CNV_PNGDIR'):
            p = os.path.join(os.environ['CNV_PNGDIR'],
                             'cap_viewfn9_t%d_%s.png' %
                             ((4 + slot if conv else slot), key))
            panel.write_png(buf, p)
            out['png'] = p
        vf = [h for h in hits if h['site'] == 'viewfn']
        out['viewfn_n'] = len(vf)
        out['viewfn_views'] = sorted(set(
            h['stack'][2] for h in vf if len(h.get('stack', [])) > 2))
        out['builder_n'] = sum(
            1 for h in hits if h['site'] == 'builder')
        out['taken_n'] = sum(
            1 for h in hits if h['site'] == 'v84taken')
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_tablescan(slot=0):
    """View-table scan (diagnostic): find the bank-views registry.

    The synth views object (0x41a6c8a0, nat FLTR) and MIDI views
    object (0x41a6f8a4, conv/MIDI FLTR) must co-reside in a registry
    struct/table selected by bank. Scan heap + UI state for windows
    containing BOTH pointers; the selector reads near the match.
    No convert needed (objects exist at boot).
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'tablescan', 'tag': BUILD['tag']}
    try:
        V.select(r, slot)
        r.settle_fb()
        targets = (0x41a6c8a0, 0x41a6f8a4)
        found = {t: [] for t in targets}
        # Heap views range + UI state range, 64KB chunks.
        regions = [(0x41a00000, 0x41c00000), (0x40550000, 0x40560000)]
        for lo, hi in regions:
            a = lo
            while a < hi:
                n = min(0x10000, hi - a)
                raw = s.m.peek(a, n)
                if not raw or len(raw) < n:
                    a += n
                    continue
                for i in range(0, n - 4, 4):
                    w = struct.unpack('>I', raw[i:i + 4])[0]
                    if w in targets and len(found[w]) < 20:
                        found[w].append('0x%08x' % (a + i))
                a += n
        out['addrs'] = {hex(k): v for k, v in found.items()}
        # Pair windows: 256B windows containing both.
        both = []
        for lo, hi in regions:
            a = lo
            while a < hi:
                n = min(0x1000, hi - a)
                raw = s.m.peek(a, n)
                if raw and len(raw) >= n:
                    words = set(struct.unpack('>I', raw[i:i + 4])[0]
                                for i in range(0, n - 4, 4))
                    if all(t in words for t in targets):
                        both.append('0x%08x' % a)
                        if len(both) >= 10:
                            break
                a += n
            if len(both) >= 10:
                break
        out['pair_windows'] = both
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_entrywrite(slot=0, key='FLTR', conv=False):
    """Page-entry write trace (diagnostic): who fills the bank views?

    Page-list entries carry per-bank view slots (entry 0x41bfcbd0
    words 6,7 + entry 0x41bfcbe0 words 2,3 differ nat-vs-conv: synth
    views 0x41a6c8a0 vs MIDI views 0x41a704a4/0x41a6f8a4). Watch
    writes to those words during a single open: the writer PC is the
    content selector. Short window keeps the unfiltered hook usable.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn import UC_HOOK_MEM_WRITE
    from unicorn.m68k_const import UC_M68K_REG_PC
    OUT = {'leg': 'entrywrite', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    WATCH = (0x41bfcbd0 + 16, 0x41bfcbd0 + 32,
             0x41bfcbe0 + 0, 0x41bfcbe0 + 16)
    writes = []

    def on_write(uc, access, address, size, value, data):
        if not any(w <= address < w + 16 for w in WATCH):
            return
        if len(writes) < 60:
            try:
                writes.append({'pc': '0x%08x' % int(uc.reg_read(
                    UC_M68K_REG_PC)), 'addr': '0x%08x' % address,
                    'size': size, 'value': '0x%08x' % value,
                    'ms': round(s.ms, 1),
                    'active': u32(s.m, B.ACTIVE)})
            except Exception:
                pass

    s.m.uc.hook_add(UC_HOOK_MEM_WRITE, on_write)
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
        del writes[:]
        s.press(s.code(key))
        s.run_ms(120)
        s.release(s.code(key))
        s.run_ms(600)
        buf = r.settle_fb()
        OUT['fb_changed'] = (sha(buf) != h0)
        OUT['active'] = u32(s.m, B.ACTIVE)
        OUT['writes'] = list(writes)
    except Exception as e:
        OUT['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    OUT['wall'] = r.wall
    return OUT


def leg_c3proof(tracks=(0, 2, 4, 5, 6, 7), keys=('FLTR', 'SYN1'),
                convtracks=(4, 6)):
    """Content-fork proof (diagnostic): the bank-table selection.

    Caller 0x4003f1e6 of the entry-filler selects the views source
    table: `moveq #3,d0; cmp.l d3,d0; bcs MIDI-table` at 0x4003f184
    (synth table a2+0xf0 vs MIDI table a2+0x148, entry = table+8*d2).
    Per cell: single page-key press, d3 + d2 + ACTIVE. Verdict:
    d3 == ACTIVE-at-press (compared-reg = track)?
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    DREGS = (('d0', UC_M68K_REG_D0), ('d1', UC_M68K_REG_D1),
             ('d2', UC_M68K_REG_D2), ('d3', UC_M68K_REG_D3),
             ('d4', UC_M68K_REG_D4), ('d5', UC_M68K_REG_D5),
             ('d6', UC_M68K_REG_D6), ('d7', UC_M68K_REG_D7))
    C3 = 0x4003f184
    C3_MIDI = 0x4003f190
    C3_SYNTH = 0x4003f18a
    out = {'leg': 'c3proof', 'tag': BUILD['tag'],
           'tracks': list(tracks), 'keys': list(keys), 'cells': []}
    hits = []

    def on_hit(site, regs):
        def cb(uc, a, sz, d):
            if len(hits) < 500:
                try:
                    e = {'site': site,
                         'active': u32(s.m, B.ACTIVE)}
                    for nm, rg in regs:
                        e[nm] = int(uc.reg_read(rg))
                    hits.append(e)
                except Exception:
                    pass
        return cb

    s.at(C3, on_hit('c3', (('d3', UC_M68K_REG_D3),
                           ('d2', UC_M68K_REG_D2))))
    s.at(C3_SYNTH, on_hit('c3synth', (('d3', UC_M68K_REG_D3),)))
    s.at(C3_MIDI, on_hit('c3midi', (('d3', UC_M68K_REG_D3),)))
    for track in tracks:
        for key in keys:
            c = {'track': track, 'key': key}
            try:
                if track in convtracks and r.state(track - 4) != 1:
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
                s.press(s.code(key))
                s.run_ms(120)
                s.release(s.code(key))
                s.run_ms(1500)
                buf = r.settle_fb()
                c['fb'] = sha(buf)[:16]
                c['fb_changed'] = (c['fb'] != h0[:16])
                if os.environ.get('CNV_PNGDIR'):
                    p = os.path.join(os.environ['CNV_PNGDIR'],
                                     'cap_c3_t%d_%s.png' % (track, key))
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
                    if h['site'] == 'c3':
                        h['d3_is_active'] = (
                            h['d3'] == c['active_at_press'])
                c['d3_all_active'] = all(
                    h.get('d3_is_active', False)
                    for h in hits if h['site'] == 'c3')
            except Exception as e:
                c['blocked'] = '%s: %s' % (type(e).__name__, e)
            out['cells'].append(c)
            _home(r)
    out['converted'] = [r.state(i) for i in range(4)]
    r.close()
    out['wall'] = r.wall
    return out


def leg_editdiff(slot=0, key='SYN1', conv=False):
    """Edit-target RAM diff (diagnostic): where do knob edits land?

    Native page open, snapshot candidate regions (kit cell, pattern
    track structs, voice-sound cache, page row table, heap views),
    turn encoder 1, re-snapshot: report changed regions + first
    differing offsets. Reveals the edit buffer/commit path.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'editdiff', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    try:
        kit = u32(s.m, 0x4138f220)
        pat = u32(s.m, 0x4138f214)
        SND = B._addr('cnv_synth_snd')
        if conv:
            track = 4 + slot
            V.select(r, track)
            V.open_modal(r, slot)
            r.key('YES', hold=15, after=600)
            assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
            V.midi_to_bank(r, True)
            live = SND + 326 * slot
        else:
            V.select(r, slot)
            live = kit + KIT_SND_OFF + 326 * slot
        out['live_rec'] = '0x%08x' % live
        h0 = sha(fb(s.m, s))
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        regions = {
            'kit': (kit, 0x1000),
            'live': (live, 326),
            'pattern': (pat, 8 * 976),
            'rowtable': (0x41a722f0, 96 + 808 * 4),
            'voicesnd': (0x80003f5c, 8 * 4),
        }
        if conv:
            SNDR = B._addr('cnv_synth_snd')
            PROW = B._addr('cnv_page_row')
            regions['snd0'] = (SNDR, 326)
            regions['pagerow0'] = (PROW, 808)
            regions['voicesndall'] = (0x80003f5c, 8 * 8 * 4)
            regions['voicetrack'] = (0x80003f8c, 8 * 4)
            regions['trackflag'] = (0x80003fc8, 8 * 4)
            regions['voicecand'] = (0x800054d4, 8 * 260)
        pre = {k: bytes(s.m.peek(a, n)) for k, (a, n) in regions.items()}
        if os.environ.get('CNV_PNGDIR'):
            panel.write_png(r.settle_fb(),
                            os.path.join(os.environ['CNV_PNGDIR'],
                                         'cap_edit_pre_t%d.png' % slot))
        neg = (key == 'SYN1')
        s.turn(1, -32 if neg else 8, 300)
        s.run_ms(500)
        buf = r.settle_fb()
        out['fb_changed'] = (sha(buf) != h0)
        if os.environ.get('CNV_PNGDIR'):
            panel.write_png(buf,
                            os.path.join(os.environ['CNV_PNGDIR'],
                                         'cap_edit_post_t%d.png' % slot))
        post = {k: bytes(s.m.peek(a, n)) for k, (a, n) in regions.items()}
        diffs = {}
        for k in regions:
            a, n = regions[k]
            idx = [i for i, (x, y) in enumerate(zip(pre[k], post[k]))
                   if x != y]
            if idx:
                diffs[k] = {'n': len(idx), 'first': idx[:12],
                            'addr': '0x%08x' % (a + idx[0])}
        out['diffs'] = diffs
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_editscan(slot=0, key='SYN1', conv=False):
    """Encoder scan (diagnostic): which encoder channel edits values?

    For rotation codes 1..9: turn 16 detents, record fb hash + live
    record diff. Identifies the value-editing encoder for the knob
    proof (code 1 only moves focus on SYN pages).
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'editscan', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv, 'encs': []}
    try:
        kit = u32(s.m, 0x4138f220)
        SND = B._addr('cnv_synth_snd')
        if conv:
            track = 4 + slot
            V.select(r, track)
            V.open_modal(r, slot)
            r.key('YES', hold=15, after=600)
            assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
            V.midi_to_bank(r, True)
            live = SND + 326 * slot
        else:
            V.select(r, slot)
            live = kit + KIT_SND_OFF + 326 * slot
        h0 = sha(fb(s.m, s))
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        for code in (1, -1, 2, -2):
            e = {'code': code}
            try:
                pre = bytes(s.m.peek(live, 326))
                hpre = sha(fb(s.m, s))
                s.turn(abs(code), 16 * (1 if code > 0 else -1), 300)
                s.run_ms(300)
                buf = r.settle_fb()
                e['fb'] = sha(buf)[:16]
                e['fb_changed'] = (e['fb'] != hpre[:16])
                post = bytes(s.m.peek(live, 326))
                e['snd_diff_n'] = sum(
                    1 for a, b in zip(pre, post) if a != b)
                if os.environ.get('CNV_PNGDIR'):
                    p = os.path.join(
                        os.environ['CNV_PNGDIR'],
                        'cap_editscan_c%d.png' % code)
                    panel.write_png(buf, p)
                    e['png'] = p
            except Exception as ex:
                e['blocked'] = '%s: %s' % (type(ex).__name__, ex)
            out['encs'].append(e)
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_editwrite(slot=0, key='SYN1', conv=True):
    """Edit-write site trace (diagnostic): where does the param write go?

    Mem-write watch over the kit synth sounds + MIDI params during a
    knob turn on a converted synth page: log writer PC + addr + size.
    The edit path resolves track->sound via kit arithmetic (NOT the
    row+16 P2 divert) — this finds the formula's write site to divert.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn import UC_HOOK_MEM_WRITE
    from unicorn.m68k_const import UC_M68K_REG_PC
    out = {'leg': 'editwrite', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    writes = []
    kit = u32(s.m, 0x4138f220)
    SND0 = kit + KIT_SND_OFF
    SEND = SND0 + 326 * 8
    MEND = kit + 0x5ce + 164 * 4

    def on_write(uc, access, address, size, value, data):
        if len(writes) < 500:
            try:
                writes.append({'pc': '0x%08x' % int(uc.reg_read(
                    UC_M68K_REG_PC)), 'addr': '0x%08x' % address,
                    'size': size, 'ms': round(s.ms, 1)})
            except Exception:
                pass

    s.m.uc.hook_add(UC_HOOK_MEM_WRITE, on_write)
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
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        del writes[:]
        s.turn(1, 8, 300)
        s.run_ms(3000)
        out['writes'] = list(writes)
        pcs = {}
        for w in writes:
            pcs[w['pc']] = pcs.get(w['pc'], 0) + 1
        out['pcs'] = sorted(pcs.items())
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_midioff(slot=0, key='SYN1', conv=True):
    """MIDI-byte timing trace (diagnostic): when does the stray write land?

    Snapshot kit MIDI params before the turn, immediately after, +2s,
    +7s: report differing offsets + values. Locates the exact byte the
    converted-page knob edit writes (wrong-destination write).
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'midioff', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    try:
        kit = u32(s.m, 0x4138f220)
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
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        base = kit + 0x5ce
        pre = bytes(s.m.peek(base, 656))

        def diffs():
            cur = bytes(s.m.peek(base, 656))
            return [('0x%x' % (base + i), pre[i], cur[i])
                    for i, (a, b) in enumerate(zip(pre, cur)) if a != b]

        s.turn(1, 8, 300)
        out['t0'] = diffs()
        s.run_ms(2000)
        out['t2'] = diffs()
        s.run_ms(5000)
        out['t7'] = diffs()
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_editwrite2(slot=0, key='SYN1', conv=True):
    """Edit write site trace, negative turns (diagnostic).

    Like editwrite but with value-changing (negative) turns: watch
    kit sounds + kit MIDI + .bss during the turn. Finds the edit
    write site + destination for converted slots (kit arithmetic vs
    row+16 .bss).
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn import UC_HOOK_MEM_WRITE
    from unicorn.m68k_const import UC_M68K_REG_PC
    out = {'leg': 'editwrite2', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    writes = []
    kit = u32(s.m, 0x4138f220)
    SND = B._addr('cnv_synth_snd')

    def on_write(uc, access, address, size, value, data):
        if len(writes) < 300:
            try:
                writes.append({'pc': '0x%08x' % int(uc.reg_read(
                    UC_M68K_REG_PC)), 'addr': '0x%08x' % address,
                    'size': size, 'val': value,
                    'ms': round(s.ms, 1)})
            except Exception:
                pass

    s.m.uc.hook_add(UC_HOOK_MEM_WRITE, on_write)
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
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        live = (SND + 326 * slot) if conv else (kit + KIT_SND_OFF +
                                                326 * slot)
        pre = bytes(s.m.peek(live, 326))
        del writes[:]
        s.turn(1, -32, 300)
        s.run_ms(1500)
        post = bytes(s.m.peek(live, 326))
        out['live_diff_n'] = sum(
            1 for a, b in zip(pre, post) if a != b)
        rel = []
        for w in writes:
            a = int(w['addr'], 16)
            tag = ''
            if kit + KIT_SND_OFF <= a < kit + KIT_SND_OFF + 326 * 4:
                tag = 'kitsnd%d+%d' % ((a - kit - KIT_SND_OFF) // 326,
                                       (a - kit - KIT_SND_OFF) % 326)
            elif kit + 0x5ce <= a < kit + 0x5ce + 164 * 4:
                tag = 'kitmidi%d+%d' % ((a - kit - 0x5ce) // 164,
                                        (a - kit - 0x5ce) % 164)
            elif SND <= a < SND + 326 * 4:
                tag = 'bss%d+%d' % ((a - SND) // 326, (a - SND) % 326)
            w['region'] = tag
            if tag:
                rel.append(w)
        pcs = {}
        for w in rel:
            pcs[w['pc']] = pcs.get(w['pc'], 0) + 1
        out['rel_pcs'] = sorted(pcs.items())
        out['rel_writes'] = rel[:20]
        apcs = {}
        for w in writes:
            apcs[w['pc']] = apcs.get(w['pc'], 0) + 1
        out['all_pcs'] = sorted(apcs.items(), key=lambda kv: -kv[1])[:25]
        out['n_writes'] = len(writes)
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_knobproof(slot=0, key='SYN1', conv=False):
    """Knob proof (diagnostic): value-edit write destination, both banks.

    Open page, snapshot SND + kit sounds + kit MIDI, turn +16 (focus)
    then -16 (value edit, the editscan-proven sequence), re-snapshot,
    report diffs per region + value PNGs. Native must show kit-sound
    bytes change; converted must show .bss bytes change (task proof).
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'knobproof', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    try:
        kit = u32(s.m, 0x4138f220)
        SND = B._addr('cnv_synth_snd')
        if conv:
            track = 4 + slot
            V.select(r, track)
            V.open_modal(r, slot)
            r.key('YES', hold=15, after=600)
            assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
            V.midi_to_bank(r, True)
            sndbase = SND + 326 * slot
        else:
            V.select(r, slot)
            sndbase = kit + KIT_SND_OFF + 326 * slot
        h0 = sha(fb(s.m, s))
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        regions = {'snd': (sndbase, 326),
                   'kitsnd': (kit + KIT_SND_OFF, 326 * 4),
                   'kitgap': (kit + 0x18 + 326 * 4, 0x5ce - 0x18 - 326 * 4),
                   'kitmidi': (kit + 0x5ce, 164 * 4)}
        pre = {k: bytes(s.m.peek(a, n)) for k, (a, n) in regions.items()}
        s.turn(1, 16, 300)
        s.run_ms(300)
        s.turn(1, -16, 300)
        s.run_ms(500)
        buf = r.settle_fb()
        out['fb'] = sha(buf)[:16]
        if os.environ.get('CNV_PNGDIR'):
            panel.write_png(buf, os.path.join(
                os.environ['CNV_PNGDIR'],
                'cap_knobproof_%s.png' % ('conv' if conv else 'nat')))
            out['png'] = True
        post = {k: bytes(s.m.peek(a, n)) for k, (a, n) in regions.items()}
        diffs = {}
        for k, (a, n) in regions.items():
            idx = [(a + i, pre[k][i], post[k][i])
                   for i in range(n) if pre[k][i] != post[k][i]]
            if idx:
                diffs[k] = idx[:16]
        out['diffs'] = diffs
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_editwrite3(slot=0, key='SYN1', conv=False):
    """Native edit write site (diagnostic): catch the 2-byte kit write.

    Mem-write watch limited to the slot's kit sound (326B) during
    a single value-changing turn: clean signal for the param-write
    PC + address. Run native (proves site) then converted (shows the
    wrong-destination write, if any).
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn import UC_HOOK_MEM_WRITE
    from unicorn.m68k_const import UC_M68K_REG_PC
    out = {'leg': 'editwrite3', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    writes = []
    kit = u32(s.m, 0x4138f220)
    SND = B._addr('cnv_synth_snd')
    if conv:
        track = 4 + slot
        base = kit + KIT_SND_OFF + 326 * 4
    else:
        track = slot
        base = kit + KIT_SND_OFF + 326 * slot
    BND = (base, base + 326)

    def on_write(uc, access, address, size, value, data):
        if not (BND[0] <= address < BND[1]):
            return
        if len(writes) < 40:
            try:
                writes.append({'pc': '0x%08x' % int(uc.reg_read(
                    UC_M68K_REG_PC)), 'off': address - BND[0],
                    'size': size, 'ms': round(s.ms, 1)})
            except Exception:
                pass

    s.m.uc.hook_add(UC_HOOK_MEM_WRITE, on_write)
    try:
        if conv:
            V.select(r, track)
            V.open_modal(r, slot)
            r.key('YES', hold=15, after=600)
            assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
            V.midi_to_bank(r, True)
        else:
            V.select(r, slot)
        h0 = sha(fb(s.m, s))
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        live = (SND + 326 * slot) if conv else base
        pre = bytes(s.m.peek(live, 326))
        del writes[:]
        s.turn(1, 16, 300)
        s.run_ms(300)
        s.turn(1, -16, 300)
        s.run_ms(800)
        post = bytes(s.m.peek(live, 326))
        out['live_diff_n'] = sum(
            1 for a, b in zip(pre, post) if a != b)
        out['writes'] = list(writes)
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_editvirt(slot=0, key='SYN1', conv=False):
    """Edit virtual trace (diagnostic): who resolves the sound pointer?

    Hooks the +$28 virtual jsr at both edit write sites (nat
    0x4002102a, conv 0x400215d0): log a0 (method), a1 (vtable),
    ACTIVE. If both reach the SAME method with different objects, a
    central method-entry divert (return .bss for converted) fixes all
    param edits at once.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn.m68k_const import UC_M68K_REG_A0, UC_M68K_REG_A1
    out = {'leg': 'editvirt', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    hits = []

    def on_virt(site):
        def cb(uc, a, sz, d):
            if len(hits) < 60:
                try:
                    row = int(uc.reg_read(UC_M68K_REG_A0))
                    sess = int(uc.reg_read(UC_M68K_REG_A1))
                    e = {'site': site,
                         'active': u32(s.m, B.ACTIVE),
                         'row': '0x%08x' % row,
                         'sess': '0x%08x' % sess}
                    vt = s.m.peek(row, 4)
                    if vt and len(vt) == 4:
                        vt = struct.unpack('>I', vt)[0]
                        e['vtable'] = '0x%08x' % vt
                        m28 = s.m.peek(vt + 0x28, 4)
                        if m28 and len(m28) == 4:
                            e['method28'] = '0x%08x' % struct.unpack(
                                '>I', m28)[0]
                    r16 = s.m.peek(row + 16, 4)
                    if r16 and len(r16) == 4:
                        e['row16'] = '0x%08x' % struct.unpack(
                            '>I', r16)[0]
                    hits.append(e)
                except Exception:
                    pass
        return cb

    s.at(0x4002102a, on_virt('natjsr'))
    s.at(0x400215d0, on_virt('convjsr'))
    s.at(0x40020fc0, on_virt('natentry'))
    s.at(0x40021570, on_virt('conventry'))
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
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        del hits[:]
        s.turn(1, 16, 300)
        s.run_ms(300)
        s.turn(1, -16, 300)
        s.run_ms(800)
        out['hits'] = list(hits)
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_editrow(slot=0, key='SYN1', conv=True):
    """Edit row-fetch trace (diagnostic): which table does the edit use?

    Hooks the c1dcf2 row-indexer entry during a value-changing turn:
    log (table, track, caller, ACTIVE). The edit's row (conv
    0x41a73098) differs from the draw row (P2 mod row) — if the edit
    calls c1dcf2 with its own table/track, that call site takes the
    same P2 helper (new site P5).
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn.m68k_const import UC_M68K_REG_A7
    out = {'leg': 'editrow', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    hits = []

    def on_row(uc, a, sz, d):
        if len(hits) < 60:
            try:
                sp = int(uc.reg_read(UC_M68K_REG_A7))
                words = []
                for k in range(4):
                    raw = s.m.peek(sp + 4 * k, 4)
                    words.append(struct.unpack('>I', raw)[0]
                                 if raw and len(raw) == 4 else None)
                hits.append({'site': 'c1dcf2',
                             'active': u32(s.m, B.ACTIVE),
                             'stack': ['0x%x' % w if w is not None
                                       else None for w in words]})
            except Exception:
                pass

    s.at(C1DCF2, on_row)
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
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        del hits[:]
        s.turn(1, 16, 300)
        s.run_ms(300)
        s.turn(1, -16, 300)
        s.run_ms(800)
        out['hits'] = list(hits)
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_openrow(slot=0, key='SYN1', conv=True):
    """Open-time row-fetch trace (diagnostic): who fetches the edit row?

    Hooks c1dcf2 entry during a page OPEN: log (caller, table,
    track, ACTIVE). The edit row (conv 0x41a73098) is resolved at open
    (not per turn) — its call site takes the P2 helper (new site P5).
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    from unicorn.m68k_const import UC_M68K_REG_A7
    out = {'leg': 'openrow', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    hits = []

    def on_row(uc, a, sz, d):
        if len(hits) < 120:
            try:
                sp = int(uc.reg_read(UC_M68K_REG_A7))
                words = []
                for k in range(4):
                    raw = s.m.peek(sp + 4 * k, 4)
                    words.append(struct.unpack('>I', raw)[0]
                                 if raw and len(raw) == 4 else None)
                hits.append({'site': 'c1dcf2',
                             'active': u32(s.m, B.ACTIVE),
                             'stack': ['0x%x' % w if w is not None
                                       else None for w in words]})
            except Exception:
                pass

    s.at(C1DCF2, on_row)
    s.at(0x4001dd1a, on_row)
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
        s.press(s.code(key))
        s.run_ms(120)
        s.release(s.code(key))
        s.run_ms(1500)
        buf = r.settle_fb()
        out['fb_changed'] = (sha(buf) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        del hits[:]
        s.turn(1, 16, 300)
        s.run_ms(300)
        s.turn(1, -16, 300)
        s.run_ms(800)
        seen = {}
        for h in hits:
            st = tuple(h['stack'])
            if st not in seen:
                seen[st] = 0
            seen[st] += 1
        out['calls'] = sorted(
            (list(k), v) for k, v in seen.items())
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_rowdump(slot=0, key='SYN1', conv=True):
    """Row dump (diagnostic): compare draw row vs edit row structures.

    Dumps the P2 mod row, the draw row, and the edit row (0x41a73098)
    + neighbor rows to identify the edit row's table.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'rowdump', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv}
    try:
        SND = B._addr('cnv_synth_snd')
        PROW = B._addr('cnv_page_row')
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
        for _ in range(4):
            s.press(s.code(key))
            s.run_ms(120)
            s.release(s.code(key))
            s.run_ms(400)
            if sha(fb(s.m, s)) != h0:
                break
        s.run_ms(300)
        out['page_opened'] = (sha(r.settle_fb()) != h0)
        out['active'] = u32(s.m, B.ACTIVE)
        rows = {'modrow': PROW + 808 * slot,
                'editrow': 0x41a73098,
                'editrow-808': 0x41a73098 - 808,
                'editrow+808': 0x41a73098 + 808,
                'drawrow0': 0x41a72350}
        for name, addr in rows.items():
            raw = bytes(s.m.peek(addr, 64))
            out[name] = {'addr': '0x%08x' % addr,
                         'head': raw.hex()}
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_knobsweep(slot=0, key='SYN1', conv=False):
    """Per-encoder edit map (diagnostic): which encoder writes where?

    Per rotation code 1..8: focus (+16) then value (-16), snapshot
    SND + kit sounds + kit MIDI + gap before/after. Maps
    (encoder, bank) -> destination region + offsets. Settles focus
    per encoder by re-opening the page each time.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'knobsweep', 'tag': BUILD['tag'], 'slot': slot,
           'key': key, 'conv': conv, 'encs': []}
    try:
        kit = u32(s.m, 0x4138f220)
        SND = B._addr('cnv_synth_snd')
        if conv:
            track = 4 + slot
            # Convert once up front (bank memory established while
            # native); per cell, ride the MIDI toggle back.
            V.select(r, track)
            V.open_modal(r, slot)
            r.key('YES', hold=15, after=600)
            assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
        else:
            track = slot
        regions = {'snd': (SND + 326 * slot, 326) if conv else None,
                   'kitsnd': (kit + KIT_SND_OFF, 326 * 4),
                   'kitgap': (kit + 0x18 + 326 * 4, 0x5ce - 0x18 - 326 * 4),
                   'kitmidi': (kit + 0x5ce, 164 * 4)}
        regions = {k: v for k, v in regions.items() if v}
        for code in range(1, 9):
            e = {'code': code}
            try:
                if conv:
                    V.midi_to_bank(r, True)
                    assert u32(s.m, B.ACTIVE) == track, 'toggle lost t%d'
                else:
                    V.select(r, track)
                # Fresh convert per encoder would disturb focus; convert
                # once up front instead.
                h0 = sha(fb(s.m, s))
                for _ in range(4):
                    s.press(s.code(key))
                    s.run_ms(120)
                    s.release(s.code(key))
                    s.run_ms(400)
                    if sha(fb(s.m, s)) != h0:
                        break
                s.run_ms(300)
                pre = {k: bytes(s.m.peek(a, n))
                       for k, (a, n) in regions.items()}
                s.turn(code, 16, 200)
                s.run_ms(200)
                s.turn(code, -16, 300)
                s.run_ms(500)
                e['fb'] = sha(r.settle_fb())[:16]
                post = {k: bytes(s.m.peek(a, n))
                        for k, (a, n) in regions.items()}
                dd = {}
                for k, (a, n) in regions.items():
                    idx = [(a + i, pre[k][i], post[k][i])
                           for i in range(n) if pre[k][i] != post[k][i]]
                    if idx:
                        dd[k] = idx[:8]
                e['diffs'] = dd
            except Exception as ex:
                e['blocked'] = '%s: %s' % (type(ex).__name__, ex)
            out['encs'].append(e)
            _home(r)
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_muteprobe(slot=0, conv=True):
    """Mute-gesture probe (diagnostic): which chord flips the mute byte?

    Tries candidate mute gestures on the converted slot, reading
    PAT_MUTES+track + ACTIVE after each (B0 divert may steal T-taps:
    ACTIVE jumping bank = stolen, not muted). First flip wins.
    """
    use_build(BUILD)
    r = B.Run(audio=False)
    s = r.s
    out = {'leg': 'muteprobe', 'tag': BUILD['tag'], 'slot': slot}
    try:
        if conv:
            track = 4 + slot
            V.select(r, track)
            V.open_modal(r, slot)
            r.key('YES', hold=15, after=600)
            assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
            V.midi_to_bank(r, True)
        else:
            V.select(r, track if conv else slot)
            track = slot
        muteb = r.pat + B.PAT_MUTES_OFF + track
        out['mute_pre'] = s.m.peek(muteb, 1)[0]
        cands = [('FUNC+T1', 'FUNC', 'T1', 80, 150),
                 ('FUNC+T1-long', 'FUNC', 'T1', 200, 400),
                 ('T1+FUNC', 'T1', 'FUNC', 80, 150),
                 ('FUNC+T1-modal', 'FUNC', 'T1', 50, 30)]
        for name, held, tapped, h1, h2 in cands:
            pre = s.m.peek(muteb, 1)[0]
            a0 = u32(s.m, B.ACTIVE)
            fbh = sha(fb(s.m, s))
            s.press(s.code(held))
            s.run_ms(h1)
            s.press(s.code(tapped))
            s.run_ms(h2)
            s.release(s.code(tapped))
            s.run_ms(200)
            s.release(s.code(held))
            s.run_ms(500)
            post = s.m.peek(muteb, 1)[0]
            a1 = u32(s.m, B.ACTIVE)
            out.setdefault('tries', []).append(
                {'g': name, 'mute': (pre, post), 'active': (a0, a1),
                 'fb': sha(r.settle_fb())[:16] != fbh[:16]})
            if post != pre:
                out['mute_gesture'] = name
                out['mute_flipped'] = True
                break
        else:
            out['mute_gesture'] = None
            out['mute_flipped'] = False
        out['mute_post'] = s.m.peek(muteb, 1)[0]
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_mutepath(slot=0):
    """Mute-path proof (no UI gesture): the mute byte gates audio.

    Convert slot, program trigs on the converted track only, mute ALL
    other tracks via pattern-mute pokes (stock index-agnostic mute
    bytes, never patched): PLAY renders converted audio (energy > 0).
    Then poke the converted slot's own mute byte: PLAY must render
    ~0 (muted). Unpoke: sounds again. Proves the mute mask/voice
    path treats converted slots identically (index-agnostic).
    """
    use_build(BUILD)
    r = B.Run(audio=True)
    s = r.s
    m = s.m
    out = {'leg': 'mutepath', 'tag': BUILD['tag'], 'slot': slot}
    try:
        from emu import midi  # noqa: E402
        tx = midi.MidiOut(sink=bytearray().extend)
        tx.install(s.m)
        tx.attach(s.m, s.ips)
        s.sources = s.sources + (tx,)

        def key(name, hold=15, after=15):
            s.press(s.code(name))
            s.run_ms(hold)
            s.release(s.code(name))
            s.run_ms(after)

        track = 4 + slot
        V.select(r, track)
        V.open_modal(r, slot)
        r.key('YES', hold=15, after=600)
        assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
        V.midi_to_bank(r, True)
        key('RECORD')
        for st in ('2', '6', '10', '14'):
            key(st)
        key('RECORD')
        for tr in range(8):
            if tr != track:
                m.poke(r.pat + B.PAT_MUTES_OFF + tr, bytes([1]))

        def play_energy():
            key('PLAY', hold=60, after=100)
            mx = 0
            for _ in range(8):
                s.run_ms(500)
                raw = bytes(m.peek(B.VOICES, B.VOICES_LEN))
                n = len(raw) // 4
                vals = struct.unpack('>' + 'i' * n, raw)
                mx = max(mx, max(abs(v) for v in vals))
            key('STOP', hold=60, after=100)
            key('STOP', hold=60, after=100)
            return mx

        out['e_unmuted'] = play_energy()
        m.poke(r.pat + B.PAT_MUTES_OFF + track, bytes([1]))
        out['e_muted'] = play_energy()
        m.poke(r.pat + B.PAT_MUTES_OFF + track, bytes([0]))
        out['e_restored'] = play_energy()
        out['pass'] = (out['e_unmuted'] > 0 and out['e_restored'] > 0 and
                       out['e_muted'] < out['e_unmuted'] // 10)
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def leg_mutemask(slot=0):
    """Mute-mask probe (diagnostic): which mask bit gates converted audio?

    Finds the audio-mask bit for the converted track by clearing
    candidate bits around PLAYs (pattern trigs only on the converted
    track, others pattern-muted). Proves mask gating is
    index-agnostic without the UI gesture.
    """
    use_build(BUILD)
    r = B.Run(audio=True)
    s = r.s
    m = s.m
    AMASK = 0x41392f30
    out = {'leg': 'mutemask', 'tag': BUILD['tag'], 'slot': slot}
    try:
        from emu import midi  # noqa: E402
        tx = midi.MidiOut(sink=bytearray().extend)
        tx.install(s.m)
        tx.attach(s.m, s.ips)
        s.sources = s.sources + (tx,)

        def key(name, hold=15, after=15):
            s.press(s.code(name))
            s.run_ms(hold)
            s.release(s.code(name))
            s.run_ms(after)

        track = 4 + slot
        V.select(r, track)
        V.open_modal(r, slot)
        r.key('YES', hold=15, after=600)
        assert r.slot() == -1 and r.state(slot) == 1, 'YES did not flip'
        V.midi_to_bank(r, True)
        key('RECORD')
        for st in ('2', '6', '10', '14'):
            key(st)
        key('RECORD')
        for tr in range(8):
            if tr != track:
                m.poke(r.pat + B.PAT_MUTES_OFF + tr, bytes([1]))

        def play_energy():
            key('PLAY', hold=60, after=100)
            mx = 0
            for _ in range(8):
                s.run_ms(500)
                raw = bytes(m.peek(B.VOICES, B.VOICES_LEN))
                n = len(raw) // 4
                vals = struct.unpack('>' + 'i' * n, raw)
                mx = max(mx, max(abs(v) for v in vals))
            key('STOP', hold=60, after=100)
            key('STOP', hold=60, after=100)
            return mx

        base_mask = struct.unpack(
            '>H', bytes(m.peek(AMASK, 2)))[0]
        out['mask_base'] = '0x%04x' % base_mask
        out['e_base'] = play_energy()
        for bit in (track, slot, 4 + slot):
            if bit > 15:
                continue
            m.poke(AMASK, struct.pack(
                '>H', base_mask & ~(1 << bit)))
            e = play_energy()
            out['e_bit%d' % bit] = e
            m.poke(AMASK, struct.pack('>H', base_mask))
        out['e_restored'] = play_energy()
    except Exception as e:
        out['blocked'] = '%s: %s' % (type(e).__name__, e)
    r.close()
    out['wall'] = r.wall
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--leg', choices=('stock', 'sweep', 'proof', 'chain',
                                     'pageopen', 'knob', 'knobtrace',
                                     'edittrace', 'editcommit',
                                     'contenttrace', 's4proof', 'viewarg',
                                     'bankread', 'idiomsweep', 'listhead',
                                     'v84gate', 'viewfn9', 'tablescan',
                                     'entrywrite', 'c3proof', 'editdiff',
                                     'editscan', 'editwrite', 'editwrite2',
                                     'midioff', 'knobproof', 'editwrite3',
                                     'editvirt', 'editrow', 'openrow',
                                     'rowdump', 'knobsweep', 'muteprobe',
                                     'mutepath', 'mutemask', 'timbre',
                                     'muteseq', 'fixreg'),
                    required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--tag', type=int, default=None)
    ap.add_argument('--folder', default=None)
    ap.add_argument('--map', default=None)
    ap.add_argument('--tracks', default='0,1,2,3,4,5,6,7')
    ap.add_argument('--convtracks', default='4',
                    help='tracks to convert in proof/chain legs')
    ap.add_argument('--slot', type=int, default=0,
                    help='slot for single-slot legs (viewarg/knob)')
    ap.add_argument('--keys', default=None)
    ap.add_argument('--conv', action='store_true')
    ap.add_argument('--native', action='store_true',
                    help='knobtrace on native track (no convert)')
    ap.add_argument('--base', type=int, default=None)
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
    elif args.leg == 'sweep':
        keys = (tuple(args.keys.split(',')) if args.keys else PAGE_KEYS)
        rep = leg_sweep(converted=args.conv, keys=keys, base=args.base)
    elif args.leg == 'chain':
        rep = leg_chain(tuple(int(x) for x in args.tracks.split(',')),
                        tuple(args.keys.split(',')) if args.keys
                        else ('SYN1', 'SYN2', 'FLTR'),
                        tuple(int(x) for x in args.convtracks.split(','))
                        if args.convtracks else ())
    elif args.leg == 'pageopen':
        rep = leg_pageopen(
            tuple(int(x) for x in args.tracks.split(',')),
            tuple(args.keys.split(',')) if args.keys
            else ('SYN1', 'SYN2', 'FLTR', 'AMP'),
            tuple(int(x) for x in args.convtracks.split(','))
            if args.convtracks else ())
    elif args.leg == 'knob':
        rep = leg_knob()
    elif args.leg == 'knobtrace':
        rep = leg_knobtrace(conv=not args.native)
    elif args.leg == 'edittrace':
        rep = leg_edittrace(conv=not args.native)
    elif args.leg == 'editcommit':
        rep = leg_editcommit(conv=not args.native)
    elif args.leg == 'contenttrace':
        rep = leg_contenttrace(conv=not args.native)
    elif args.leg == 'viewarg':
        rep = leg_viewarg(slot=args.slot, conv=not args.native)
    elif args.leg == 'bankread':
        rep = leg_bankread(slot=args.slot, conv=not args.native)
    elif args.leg == 'idiomsweep':
        rep = leg_idiomsweep(slot=args.slot, conv=not args.native)
    elif args.leg == 'listhead':
        rep = leg_listhead(slot=args.slot, conv=not args.native)
    elif args.leg == 'v84gate':
        rep = leg_v84gate(slot=args.slot, conv=not args.native)
    elif args.leg == 'viewfn9':
        rep = leg_viewfn9(slot=args.slot, conv=not args.native)
    elif args.leg == 'tablescan':
        rep = leg_tablescan(slot=args.slot)
    elif args.leg == 'entrywrite':
        rep = leg_entrywrite(slot=args.slot, conv=not args.native)
    elif args.leg == 'editdiff':
        rep = leg_editdiff(slot=args.slot, conv=not args.native)
    elif args.leg == 'editscan':
        rep = leg_editscan(slot=args.slot, conv=not args.native)
    elif args.leg == 'editwrite':
        rep = leg_editwrite(slot=args.slot, conv=not args.native)
    elif args.leg == 'editwrite2':
        rep = leg_editwrite2(slot=args.slot, conv=not args.native)
    elif args.leg == 'midioff':
        rep = leg_midioff(slot=args.slot, conv=not args.native)
    elif args.leg == 'knobproof':
        rep = leg_knobproof(slot=args.slot, conv=not args.native)
    elif args.leg == 'editwrite3':
        rep = leg_editwrite3(slot=args.slot, conv=not args.native)
    elif args.leg == 'editvirt':
        rep = leg_editvirt(slot=args.slot, conv=not args.native)
    elif args.leg == 'editrow':
        rep = leg_editrow(slot=args.slot, conv=not args.native)
    elif args.leg == 'openrow':
        rep = leg_openrow(slot=args.slot, conv=not args.native)
    elif args.leg == 'rowdump':
        rep = leg_rowdump(slot=args.slot, conv=not args.native)
    elif args.leg == 'knobsweep':
        rep = leg_knobsweep(slot=args.slot, conv=not args.native)
    elif args.leg == 'muteprobe':
        rep = leg_muteprobe(slot=args.slot, conv=not args.native)
    elif args.leg == 'mutepath':
        rep = leg_mutepath(slot=args.slot)
    elif args.leg == 'mutemask':
        rep = leg_mutemask(slot=args.slot)
    elif args.leg == 'c3proof':
        rep = leg_c3proof(
            tuple(int(x) for x in args.tracks.split(',')),
            tuple(args.keys.split(',')) if args.keys else ('FLTR',),
            tuple(int(x) for x in args.convtracks.split(','))
            if args.convtracks else ())
    elif args.leg == 's4proof':
        rep = leg_s4proof(
            tuple(int(x) for x in args.tracks.split(',')),
            tuple(args.keys.split(',')) if args.keys else ('FLTR',),
            tuple(int(x) for x in args.convtracks.split(','))
            if args.convtracks else ())
    elif args.leg == 'timbre':
        rep = leg_timbre()
    elif args.leg == 'muteseq':
        rep = leg_muteseq()
    elif args.leg == 'fixreg':
        rep = leg_fixreg()
    else:
        rep = leg_proof(tuple(int(x) for x in args.tracks.split(',')),
                        tuple(args.keys.split(',')) if args.keys
                        else ('SYN1',),
                        tuple(int(x) for x in args.convtracks.split(','))
                        if args.convtracks else ())
    with open(args.out, 'w') as fh:
        json.dump(rep, fh, indent=1, default=str)
    print('%s wall=%s' % (args.leg, rep.get('wall')))
    if args.leg == 'stock':
        print({k: v for k, v in rep.items() if k != 'wall'})
    if args.leg == 'sweep':
        for g in rep['gestures']:
            hs = {}
            for h in g.get('hits', []):
                e = hs.setdefault(h['site'], {'n': 0, 'regs': set()})
                e['n'] += 1
                for k, v in h.items():
                    if k.startswith('d') and len(k) == 2:
                        e['regs'].add('%s=%d' % (k, v))
            det = ' '.join('%s:n=%d,regs=%s' % (k, v['n'],
                                                sorted(v['regs']))
                           for k, v in hs.items()) or '-'
            print('%-10s fb=%s act=%s %s %s' % (
                g.get('key'), g.get('fb_changed'), g.get('active'),
                det, g.get('blocked', '')))
    if args.leg in ('proof', 'chain', 's4proof', 'c3proof'):
        for c in rep['cells']:
            print('t=%s key=%-5s fb=%s act=%s %s' % (
                c.get('track'), c.get('key'), c.get('fb_changed'),
                c.get('active_at_press'), c.get('blocked', '')))
            for site, sm in c.get('summary', {}).items():
                print('    %-8s n=%-4d regs=%s %s' % (
                    site, sm['n'], sm['regs'][:8],
                    sm.get('actives', sm.get('callers'))))
        print('converted:', rep.get('converted'))
    if args.leg == 'pageopen':
        for c in rep['cells']:
            print('t=%s key=%-5s fb=%s p1=%s p2mod=%s row16snd=%s kit=%s '
                  's8=%s s5=%s %s' % (
                      c.get('track'), c.get('key'), c.get('fb_changed'),
                      c.get('p1_is_mirror', c.get('p1_is_track')),
                      c.get('p2_is_modrow'), c.get('row16_is_snd',
                                                  c.get('row16_is_kit')),
                      c.get('row16_is_kit'), c.get('s8_n'),
                      c.get('s5_n'), c.get('blocked', '')))
    if args.leg in ('knob', 'knobtrace', 'edittrace', 'editcommit',
                    'bankread', 'idiomsweep', 'listhead', 'v84gate',
                    'viewfn9', 'tablescan', 'entrywrite', 'editdiff',
                    'editscan', 'editwrite', 'editwrite2', 'midioff',
                    'knobproof', 'editwrite3', 'editvirt', 'editrow',
                    'openrow', 'rowdump', 'knobsweep', 'muteprobe',
                    'mutepath', 'mutemask', 'timbre', 'muteseq',
                    'fixreg'):
        print({k: v for k, v in rep.items()
               if k not in ('wall',)})


if __name__ == '__main__':
    main()
