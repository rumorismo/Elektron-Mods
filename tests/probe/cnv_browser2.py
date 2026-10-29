#!/usr/bin/env python3
"""3.1b gate tracer for dn-convert (extends cnv_browser, does not rewrite it).

Question: why does the stock double-tap detector (ee72..f330 subtree)
never open the synth browser (ed68) for converted slots?

Method: hook the detector's decision points + callees and log regs for
  (a) native T1 double-tap (ACTIVE 0, control — browser OPENS) vs
  (b) converted T1 double-tap (ACTIVE 4 — browser never opens).
Diff the traces -> the exact gate (addr + compared reg + stock bytes).

Evidence JSONs + PNGs live OUTSIDE the repo (/tmp/opencode).
Run from tools/digiemu with its venv.
"""
import argparse
import json
import os
import struct
import sys
import time

import cnv_browser as B

from emu import panel  # noqa: E402
from unicorn.m68k_const import (UC_M68K_REG_A1, UC_M68K_REG_A2,  # noqa: E402
                                UC_M68K_REG_A3, UC_M68K_REG_A4,
                                UC_M68K_REG_A7, UC_M68K_REG_D0,
                                UC_M68K_REG_D1, UC_M68K_REG_D2,
                                UC_M68K_REG_D3, UC_M68K_REG_D4,
                                UC_M68K_REG_D6)

# Stock detector decision points (Digitone 1.44, see cnv_browser2.md).
DED34 = 0x400ded34
DED40 = 0x400ded40
DED50 = 0x400ded50
DED60 = 0x400ded60
DED70 = 0x400ded70
DED80 = 0x400ded80
DEDA6 = 0x400deda6

BUILD15 = {
    'tag': 1478,
    'syx_sha': '09263fd8f384481949355c74fe6c5842d9a8cf9b489329ccba26edfb41ea0c00',
    'folder': ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
               'portable/firmware/dn1-1478-09263fd8'),
    'map': ('/home/nuke/Documents/Elektron-MODS/firmware/'
            'test-cnv15.syx.map.json'),
}


def use_build(b):
    """Rebind cnv_browser globals to another linked build (map + snapshot
    + syx sha). cnv_browser.py itself is untouched."""
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
    global SITE_B1
    SITE_B1 = B.SITE_B1
F_B0 = None  # filled from map (cnv_site_b0)
F_F0C6 = 0x4004f0c6   # single-tap return (clr.b d3)
F_F330 = 0x4004f330   # dispatch epilogue (d3 -> d0 return)
F_F0B4 = 0x4004f0b4   # common bail
F_F156 = 0x4004f156   # browser-gate entry (ded50 test)
F_F166 = 0x4004f166   # tst.b $8c(a2) gate
F_F17E = 0x4004f17e   # d3 = $84(a2) captured
F_F1C6 = 0x4004f1c6   # loop-exit -> browser open with d6
F_F1DA = 0x4004f1da   # jsr ed68 (loop path, arg d6)
F_F218 = 0x4004f218   # jsr ed68 (f1fa path, arg d3)
F_ED68 = 0x4004ed68   # browser function entry
F_EDF6 = 0x4004edf6   # push d3 (open-gate struct)
F_EDF8 = 0x4004edf8   # jsr c6ba
F_EDFE = 0x4004edfe   # addq; cmp d0,d2; beq return  <- THE gate compare
F_EE02 = 0x4004ee02   # beq ee68 (gate taken)
F_EE04 = 0x4004ee04   # switch-block entry
F_EE30 = 0x4004ee30   # tst.l d0 (switch result)
F_EE32 = 0x4004ee32   # beq ee68 (switch failed -> return)
F_EE34 = 0x4004ee34   # switch proceeds to c7d2
F_C6BA = 0x4002c6ba   # gate reader entry (arg = struct)
F_C6DE = 0x4002c6de   # move.l 8(a0),d0 (nonzero result load)
F_C6E4 = 0x4002c6e4   # clr.l d0 (virtual returned 0)
F_EDAE = 0x4004edae   # synth fork rejoin (B1 target)
F_EDF6 = 0x4004edf6   # MIDI fork (B1-midi target)
F_F1FA = 0x4004f1fa   # ded80==0 path
F_EF8C = 0x4004ef8c   # e8be8 mode-check path
SITE_B1 = B.SITE_B1

CAP = 600  # per-site hit cap


class Tracer(B.Run):
    def __init__(self, audio=False):
        super().__init__(audio=audio)
        self.hits = {}
        self.order = []

    def watch(self, addr, name, extra=None):
        def cb(uc, a, sz, d):
            lst = self.hits.setdefault(name, [])
            if len(lst) >= CAP:
                return
            try:
                rec = {'ms': round(self.s.ms, 1)}
                for rn, rc in (('d0', UC_M68K_REG_D0),
                               ('d1', UC_M68K_REG_D1),
                               ('d2', UC_M68K_REG_D2),
                               ('d3', UC_M68K_REG_D3),
                               ('d4', UC_M68K_REG_D4),
                               ('d6', UC_M68K_REG_D6),
                               ('a1', UC_M68K_REG_A1),
                               ('a2', UC_M68K_REG_A2),
                               ('a3', UC_M68K_REG_A3),
                               ('a4', UC_M68K_REG_A4)):
                    try:
                        rec[rn] = '0x%08x' % uc.reg_read(rc)
                    except Exception:
                        pass
                if extra == 'ded':
                    # callee entry: stack arg + caller ret
                    sp = uc.reg_read(UC_M68K_REG_A7)
                    raw = self.s.m.peek(sp, 8)
                    if raw and len(raw) == 8:
                        ret, arg = struct.unpack('>II', raw)
                        rec['caller'] = '0x%08x' % ret
                        rec['cell'] = '0x%08x' % arg
                        c = self.s.m.peek(arg + 0x10, 4)
                        if c and len(c) == 4:
                            rec['cell10'] = '0x%08x' % struct.unpack(
                                '>I', c)[0]
                elif extra == 'f166':
                    a2 = uc.reg_read(UC_M68K_REG_A2)
                    for off, k in ((0x84, 'a2_84'), (0x8c, 'a2_8c')):
                        v = self.s.m.peek(a2 + off, 4)
                        if v and len(v) == 4:
                            rec[k] = '0x%08x' % struct.unpack('>I', v)[0]
                elif extra == 'ed68':
                    sp = uc.reg_read(UC_M68K_REG_A7)
                    raw = self.s.m.peek(sp, 8)
                    if raw and len(raw) == 8:
                        ret, arg = struct.unpack('>II', raw)
                        rec['caller'] = '0x%08x' % ret
                        rec['arg_track'] = arg
                elif extra == 'rowargs':
                    sp = uc.reg_read(UC_M68K_REG_A7)
                    raw = self.s.m.peek(sp, 16)
                    if raw and len(raw) == 16:
                        ret, tab, trk, wire = struct.unpack('>IIII', raw)
                        rec['caller'] = '0x%08x' % ret
                        rec['table'] = '0x%08x' % tab
                        rec['track'] = trk
                        rec['wire'] = wire
                self.order.append(name)
                lst.append(rec)
            except Exception as e:
                lst.append({'err': str(e)})
        self.s.at(addr, cb)


def install(t):
    global F_B0
    F_B0 = B._addr('cnv_site_b0')
    SITE_B2 = B._addr('cnv_site_b2')
    ROWFOR = B._addr('cnv_brow_row_for')
    t.watch(F_B0, 'B0', None)
    t.watch(SITE_B2, 'B2', None)
    t.watch(ROWFOR, 'rowfor', 'rowargs')
    for a, n in ((DED34, 'ded34'), (DED40, 'ded40'), (DED50, 'ded50'),
                 (DED60, 'ded60'), (DED70, 'ded70'), (DED80, 'ded80'),
                 (DEDA6, 'deda6')):
        t.watch(a, n, 'ded')
    for a, n in ((F_F0C6, 'f0c6'), (F_F330, 'f330'), (F_F0B4, 'f0b4'),
                 (F_F156, 'f156'), (F_F17E, 'f17e'), (F_F1C6, 'f1c6'),
                 (F_F1DA, 'f1da'), (F_F218, 'f218'), (F_F1FA, 'f1fa'),
                 (F_EF8C, 'ef8c'), (F_EDAE, 'edae'), (F_EDF6, 'edf6'),
                 (F_EDFE, 'edfe'), (F_EDF8, 'edf8'), (F_C6DE, 'c6de'),
                 (F_C6E4, 'c6e4'), (SITE_B1, 'B1'),
                 (F_EE02, 'ee02'), (F_EE04, 'ee04'), (F_EE30, 'ee30'),
                 (F_EE32, 'ee32'), (F_EE34, 'ee34'),
                 (0x4004edb8, 'edb8'),
                 (0x400ae202, 'ae202'), (0x4018a6be, 'a6be'),
                 (0x400e539e, 'e539e')):
        t.watch(a, n, None)
    t.watch(F_C6BA, 'c6ba', 'ed68')
    t.watch(F_F166, 'f166', 'f166')
    t.watch(F_ED68, 'ed68', 'ed68')


def double_tap(t, gap=150):
    s = t.s
    s.press(s.code('T1'))
    s.run_ms(60)
    s.release(s.code('T1'))
    s.run_ms(gap)
    s.press(s.code('T1'))
    s.run_ms(60)
    s.release(s.code('T1'))
    s.run_ms(400)


def summ(hits):
    out = {}
    for k, v in hits.items():
        out[k] = {'n': len(v), 'first': v[0] if v else None,
                  'last': v[-1] if v else None}
    return out


RAW_KEYS = ('c6ba', 'c6de', 'c6e4', 'edf6', 'edf8', 'edfe', 'f218',
            'f1da', 'B1', 'ed68', 'edae', 'B0', 'ee02', 'ee04', 'ee30',
            'ee32', 'ee34', 'B2', 'rowfor', 'edb8', 'ae202', 'a6be',
            'e539e')


def raw(hits):
    return {k: v for k, v in hits.items() if k in RAW_KEYS}


def leg_trace_native():
    t = Tracer()
    out = {'leg': 'trace_native'}
    install(t)
    out['pre_fb'] = B.sha(t.settle_fb())[:16]
    double_tap(t)
    out['post_fb'] = B.sha(t.settle_fb())[:16]
    out['browser_opened'] = (out['pre_fb'] != out['post_fb'])
    out['counts'] = {k: len(v) for k, v in t.hits.items()}
    out['detail'] = summ(t.hits)
    out['raw'] = raw(t.hits)
    t.close()
    out['wall'] = t.wall
    return out


def leg_trace_cnv():
    t = Tracer()
    out = {'leg': 'trace_cnv'}
    install(t)
    t.ensure_active(4)
    t.convert0()
    t.ensure_active(4)
    out['pre_fb'] = B.sha(t.settle_fb())[:16]
    main = out['pre_fb']
    for gap in (150, 300, 60):
        double_tap(t, gap=gap)
        fb = B.sha(t.settle_fb())[:16]
        out['fb_gap_%d' % gap] = fb
        if fb != main:
            out['browser_opened'] = True
            break
    else:
        out['browser_opened'] = False
    out['counts'] = {k: len(v) for k, v in t.hits.items()}
    out['detail'] = summ(t.hits)
    out['raw'] = raw(t.hits)
    t.close()
    out['wall'] = t.wall
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--leg', choices=('trace_native', 'trace_cnv',
                                      'open15', 'single15', 'apply15',
                                      'voice15', 'native15', 'kit15'),
                    required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    if args.leg in ('open15', 'single15', 'apply15', 'voice15', 'native15',
                     'kit15', 'trace_native', 'trace_cnv') and \
            args.leg.endswith('15'):
        use_build(BUILD15)
        fn = {'open15': B.leg_open, 'single15': B.leg_single,
              'apply15': B.leg_apply, 'voice15': B.leg_voice,
              'native15': B.leg_native, 'kit15': B.leg_kit}[args.leg]
    else:
        fn = {'trace_native': leg_trace_native,
              'trace_cnv': leg_trace_cnv}[args.leg]
    rep = fn()
    with open(args.out, 'w') as fh:
        json.dump(rep, fh, indent=1, default=str)
    print('%s wall=%s' % (args.leg, rep.get('wall')))
    slim = {k: v for k, v in rep.items() if k not in ('series', 'detail')}
    print(json.dumps(slim, indent=1, default=str))


if __name__ == '__main__':
    main()
