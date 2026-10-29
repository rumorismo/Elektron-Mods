#!/usr/bin/env python3
"""ACTIVE-reader trace for dn-convert task 3.3 (voice-menu header hunt).

The voice-menu header ("TRK.3"-style box) does not go through the R0
label renderer and E5 (0x40158770) entry carries no track in d-regs, so
the header draw must read fw_active_track (0x41368ce0) downstream (the
3.2 content caveat). This leg hooks MEM_READ on ACTIVE during a VOICE
open and reports the distinct reader PCs, so the header-draw site can
be disassembled for its label logic.
"""
import argparse
import hashlib
import json
import os
import struct
import sys

DIGIEMU = '/home/nuke/Documents/Elektron-MODS/tools/digiemu'
sys.path.insert(0, DIGIEMU)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(DIGIEMU)

import cnv_browser as B  # noqa: E402
import cnv_browser3 as B3  # noqa: E402
import cnv_voicemenu as V  # noqa: E402
from emu import panel  # noqa: E402
from unicorn.m68k_const import UC_M68K_REG_PC  # noqa: E402
from unicorn import UC_HOOK_MEM_READ  # noqa: E402
from unicorn.m68k_const import UC_M68K_REG_A7  # noqa: E402

ACTIVE = 0x41368ce0
TEXTF = 0x400dde68
FILLRECT = 0x400dd506
FRAMERECT = 0x400dd2ea
# View-renderer family members (seen as jsr targets around label draws).
VR1 = 0x400de9c8
VR2 = 0x400de120
VR3 = 0x400de32c
E5 = 0x40158770

BUILD18 = {
    'tag': 1481,
    'syx_sha': 'xx',
    'folder': ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
               'portable/firmware/dn1-1481-647d35bb'),
    'map': ('/home/nuke/Documents/Elektron-MODS/firmware/'
            'test-cnv18.syx.map.json'),
}


def sha(b):
    return hashlib.sha256(bytes(b)).hexdigest()


def u32(m, a):
    b = m.peek(a, 4)
    return struct.unpack('>I', b)[0] if b and len(b) == 4 else None


def leg_actread(converted=False, base=None):
    B3.use_build(BUILD18)
    with open(os.path.join(BUILD18['folder'], 'firmware.json')) as fh:
        rec = json.load(fh)
    BUILD18['syx_sha'] = ((rec.get('release') or {}).get('sha256')
                          or rec.get('syx_sha256'))
    B3.use_build(BUILD18)
    r = B.Run(audio=False)
    s = r.s
    out = {'tag': 1481, 'converted': converted}
    base = (4 if converted else 0) if base is None else base
    V.select(r, base)
    if converted:
        V.open_modal(r, base - 4)
        r.key('YES', hold=15, after=600)
        V.select(r, base)
    out['active_start'] = u32(s.m, B.ACTIVE)
    readers = {}

    def on_read(uc, access, addr, size, value, user):
        try:
            pc = uc.reg_read(UC_M68K_REG_PC)
            e = readers.setdefault(pc, 0)
            readers[pc] = e + 1
        except Exception:
            pass

    # The settled snapshot boots WITH the voice menu open (track 0):
    # VOICE closes it to main; the traced VOICE press is then a real open.
    # (200 ms holds: the key scan misses shorter ones on this screen;
    # retry each transition until the fb actually moves.)
    boot_fb = sha(panel.read(s.m, s.profile.fb_front))
    for _ in range(10):
        s.press(s.code('VOICE'))
        s.run_ms(200)
        s.release(s.code('VOICE'))
        s.run_ms(400)
        main_fb = sha(panel.read(s.m, s.profile.fb_front))
        if main_fb != boot_fb:
            break
    out['main_fb'] = main_fb[:16]
    out['closed'] = (main_fb != boot_fb)
    h = s.m.uc.hook_add(UC_HOOK_MEM_READ, on_read, begin=ACTIVE,
                        end=ACTIVE + 3)
    for _ in range(10):
        s.press(s.code('VOICE'))
        s.run_ms(200)
        s.release(s.code('VOICE'))
        s.run_ms(400)
        if sha(panel.read(s.m, s.profile.fb_front)) != main_fb:
            break
    s.run_ms(500)
    s.m.uc.hook_del(h)
    out['fb_changed'] = (sha(r.settle_fb()) != main_fb)
    out['readers'] = sorted(('0x%x' % pc, n)
                            for pc, n in readers.items())

    # Enumerate the fw_textf draws of a second VOICE cycle (close+open)
    # to find the header-box format. Close to main first.
    for _ in range(10):
        s.press(s.code('VOICE'))
        s.run_ms(200)
        s.release(s.code('VOICE'))
        s.run_ms(400)
        if sha(panel.read(s.m, s.profile.fb_front)) == main_fb:
            break
    texts = []

    def on_textf(uc, a, sz, d):
        if len(texts) < 80:
            try:
                sp = uc.reg_read(UC_M68K_REG_A7)
                words = []
                for k in range(16):
                    raw = s.m.peek(sp + 4 * k, 4)
                    if not raw or len(raw) < 4:
                        break
                    words.append(struct.unpack('>I', raw)[0])
                strs = []
                for w in words:
                    if 0x401c0000 <= w < 0x402a0000:
                        raw = s.m.peek(w, 24) or b''
                        t = bytes(raw).split(b'\x00')[0]
                        if all(32 <= c < 127 for c in t) and len(t) >= 2:
                            strs.append((hex(w), t.decode('latin1')))
                texts.append({'active': u32(s.m, B.ACTIVE),
                              'strs': strs,
                              'words': ['%x' % w for w in words[:10]]})
            except Exception:
                pass

    s.at(TEXTF, on_textf)
    for _ in range(10):
        s.press(s.code('VOICE'))
        s.run_ms(200)
        s.release(s.code('VOICE'))
        s.run_ms(400)
        if sha(panel.read(s.m, s.profile.fb_front)) != main_fb:
            break
    s.run_ms(500)
    out['menu_fb'] = sha(r.settle_fb())[:16]
    out['texts'] = texts

    # Rect-draw enumeration: hook FILLRECT/FRAMERECT, log caller + args.
    for _ in range(10):
        s.press(s.code('VOICE'))
        s.run_ms(200)
        s.release(s.code('VOICE'))
        s.run_ms(400)
        if sha(panel.read(s.m, s.profile.fb_front)) == main_fb:
            break
    rects = []

    def on_rect(tag):
        def cb(uc, a, sz, d):
            if len(rects) < 120:
                try:
                    import struct as _S
                    sp = uc.reg_read(UC_M68K_REG_A7)
                    words = []
                    for k in range(8):
                        raw = s.m.peek(sp + 4 * k, 4)
                        if not raw or len(raw) < 4:
                            break
                        words.append(_S.unpack('>I', raw)[0])
                    rects.append({'fn': tag,
                                  'active': u32(s.m, B.ACTIVE),
                                  'words': ['%x' % w for w in words]})
                except Exception:
                    pass
        return cb

    s.at(FILLRECT, on_rect('fill'))
    s.at(FRAMERECT, on_rect('frame'))
    for tag, addr in (('vr1', VR1), ('vr2', VR2)):
        s.at(addr, on_rect(tag))
    for _ in range(10):
        s.press(s.code('VOICE'))
        s.run_ms(200)
        s.release(s.code('VOICE'))
        s.run_ms(400)
        if sha(panel.read(s.m, s.profile.fb_front)) != main_fb:
            break
    s.run_ms(500)
    out['rects'] = rects

    # Phase: T-switch INSIDE the open menu (header rebuild). Collect
    # ACTIVE readers + R0 windows + E5 regs during the switch.
    readers2 = {}
    r0wins = []
    e5regs = []

    def on_read2(uc, access, addr, size, value, user):
        try:
            pc = uc.reg_read(UC_M68K_REG_PC)
            readers2[pc] = readers2.get(pc, 0) + 1
        except Exception:
            pass

    h2 = s.m.uc.hook_add(UC_HOOK_MEM_READ, on_read2, begin=ACTIVE,
                         end=ACTIVE + 3)

    def on_r0b(uc, a, sz, d):
        if len(r0wins) < 60:
            try:
                import struct as _S
                sp = uc.reg_read(UC_M68K_REG_A7)
                words = []
                for k in range(12):
                    raw = s.m.peek(sp + 4 * k, 4)
                    if not raw or len(raw) < 4:
                        break
                    words.append(_S.unpack('>I', raw)[0])
                r0wins.append(['%x' % w for w in words])
            except Exception:
                pass

    def on_e5b(uc, a, sz, d):
        if len(e5regs) < 20:
            try:
                from unicorn.m68k_const import (
                    UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3,
                    UC_M68K_REG_D4, UC_M68K_REG_D5, UC_M68K_REG_D6,
                    UC_M68K_REG_D7)
                regs = [int(uc.reg_read(x)) for x in
                        (UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2,
                         UC_M68K_REG_D3, UC_M68K_REG_D4, UC_M68K_REG_D5,
                         UC_M68K_REG_D6, UC_M68K_REG_D7)]
                e5regs.append({'active': u32(s.m, B.ACTIVE), 'd': regs})
            except Exception:
                pass

    s.at(VR3, on_r0b)
    s.at(E5, on_e5b)
    for _ in range(6):
        s.press(s.code('T3'))
        s.run_ms(200)
        s.release(s.code('T3'))
        s.run_ms(400)
        if u32(s.m, B.ACTIVE) == 2:
            break
    s.run_ms(600)
    s.m.uc.hook_del(h2)
    out['switch_active'] = u32(s.m, B.ACTIVE)
    out['switch_fb'] = sha(r.settle_fb())[:16]
    out['switch_readers'] = sorted(('0x%x' % pc, n)
                                   for pc, n in readers2.items())
    out['switch_r0'] = r0wins
    out['switch_e5'] = e5regs
    r.close()
    out['wall'] = r.wall
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--conv', action='store_true')
    ap.add_argument('--base', type=int, default=None)
    args = ap.parse_args()
    rep = leg_actread(converted=args.conv, base=args.base)
    with open(args.out, 'w') as fh:
        json.dump(rep, fh, indent=1, default=str)
    print('wall=%s fb_changed=%s nreaders=%d' % (
        rep.get('wall'), rep.get('fb_changed'), len(rep['readers'])))
    for pc, n in rep['readers'][:60]:
        print('  %s x%d' % (pc, n))


if __name__ == '__main__':
    main()
