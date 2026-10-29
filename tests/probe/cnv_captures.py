#!/usr/bin/env python3
"""Trig-capture proof for dn-convert 0.11 (8-track-engine).

Re-runnable headless probe. Two scenarios + a compare mode:

    python -m tests.probe.cnv_captures --scenario base --out /tmp/x/base.json
    python -m tests.probe.cnv_captures --scenario convert --out /tmp/x/conv.json
    python -m tests.probe.cnv_captures --compare /tmp/x/base.json /tmp/x/conv.json

Run from tools/digiemu with its venv (needs emu.*, unicorn). Each scenario
boots ONE Session from the persistent settled snapshot (no boot per
scenario-step, no fixed long PLAYs: PLAY windows are poll-until-stable with
caps). Audio stays ON: the sequencer step loop only advances on the audio
clock (audio=False sessions show transport=1 but S1/S2 never fire).

Scenario base (STOCK .syx + dn1-1.44 snapshot): program grid trigs on tracks
0-3, PLAY ~1-2 bars, STOP, capture.
Scenario convert (test-cnvx.syx + dn1-1465 snapshot): program tracks 0-3,
convert slot 4 via the MIDI+VOICE chord (outcome-verified by pattern-struct
diff, retried), program converted track 4, PLAY ~1-2 bars, STOP, flip back
via a second chord (round-trip-verified), capture.

Assertion coverage (recorded per run, judged in --compare):
  (a) tracks 0-3 F3 (track,a0) multisets, MIDI-byte sink, mutes, kit tail,
      framebuffer, voices_sha (phase-skew allowance documented).
  (b) converted slot-4 F3 publish: a0 must land in mod RAM; prior finding
      a0=0x43EC394C is verified live (exact match reported).
  (c) kit tail FW_KIT+0x5CE..0x85E identical pre/post flips.
  (d) allocator/sustain state for track 4 recorded (Y flags, candidate row,
      cached sounds, voice map, gates, lengths, voices buffer). No fixes.
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

from unicorn.m68k_const import UC_M68K_REG_A0, UC_M68K_REG_D4  # noqa: E402

from emu import midi, panel  # noqa: E402
from emu.fwcompare import folder_paths, pixel_diff  # noqa: E402
from emu.session import Session  # noqa: E402

# -- addresses (1.44; see docs/EMU_TESTING.md 4.2 + cnv sources) ----------------
PAT_PTR = 0x4138f214
KIT_PTR = 0x4138f220
ACTIVE = 0x41368ce0
TRANSPORT = 0x4138f208
AUDIO_MUTES = 0x41392f30      # u16 hw mask
MIDI_MUTES = 0x419c5b0c       # u32
PAT_MUTES_OFF = 0x16108       # +track, one byte each
TRACK_STRUCT = 976
KIT_TAIL_OFF = 0x5CE
KIT_TAIL_END = 0x85E
Y_BASE = 0x80003fc8            # +4*track
CAND_BASE = 0x800054d4         # +260*track, 260B rows
CAND_ROW = 260
CACHED_SOUNDS = 0x80003f5c     # 8 x u32
VOICE_TRACK = 0x80003f8c       # 8 x u32
VOICES = 0x80004110            # 8 voices x 32 samples (render copy)
VOICES_LEN = 8 * 32 * 4
VOICE_LEN = 0x80003f14         # 8 x u32 lens
GATE_ON = 0x80001f70
GATE_OFF = 0x80001f74
F3_REJOIN = 0x40094848         # synth-fire epilogue rejoin; d4=track*326
MODRAM_LO = 0x43EC0000
MODRAM_HI = 0x43EC4DA4
PRIOR_BSS_A0 = 0x43EC394C      # prior finding for slot-4 publish
REALTIME = {0xF8, 0xFA, 0xFB, 0xFC, 0xFE, 0xFF}

STOCK_FOLDER = ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
                'portable/firmware/dn1-1.44-d4f200d0')
MOD_FOLDER = ('/home/nuke/Documents/Elektron-MODS/tools/digiemu/'
              'portable/firmware/dn1-1465-b653e7ed')
STOCK_SYX_SHA = 'd4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659'
MOD_SYX_SHA = 'b653e7eda2f859072199f00814cb75efa093690f4e136b428e904e83fbf18824'

KEY_HOLD_MS = 15
KEY_AFTER_MS = 15
STEPS = ('2', '6', '10', '14')  # avoid factory-occupied step 1 on track 0
PLAY_MIN_MS = 3000
PLAY_CAP_MS = 7000
SETTLE_CAP_MS = 1500


def sha(b):
    return hashlib.sha256(bytes(b)).hexdigest()


def u32(m, a):
    b = m.peek(a, 4)
    return struct.unpack('>I', b)[0] if b and len(b) == 4 else None


def u16(m, a):
    b = m.peek(a, 2)
    return struct.unpack('>H', b)[0] if b and len(b) == 2 else None


def fb_hash(m, profile):
    buf = panel.read(m, profile.fb_front)
    return (sha(bytes(buf)), bytes(buf)) if buf is not None else (None, None)


class Run:
    def __init__(self, folder, syx_sha):
        self.t0 = time.time()
        self.wall = {}
        self.log = []
        paths = folder_paths(folder)
        os.environ.update(paths.env())
        with open(os.path.join(folder, 'firmware.json'), encoding='utf-8') as fh:
            rec = json.load(fh)
        self.syx_name = (rec.get('release') or {}).get('syx_name') or rec.get(
            'syx_name')
        self.snapshot_id = os.path.basename(folder.rstrip('/'))
        t = time.time()
        self.s = Session(paths.gui, paths.syx, audio=True)
        self.wall['boot'] = time.time() - t
        self.fires = []          # (ms, track, a0)
        self.s.at(F3_REJOIN, self._on_f3)
        self.midibuf = bytearray()
        tx = midi.MidiOut(sink=self.midibuf.extend)
        tx.install(self.s.m)
        tx.attach(self.s.m, self.s.ips)
        self.s.sources = self.s.sources + (tx,)
        self.pat = u32(self.s.m, PAT_PTR)
        self.kit = u32(self.s.m, KIT_PTR)
        assert self.pat and self.kit, 'pattern/kit pointers unreadable'
        assert self.syx_sha(paths.syx) == syx_sha, 'syx sha mismatch'
        self.marks = {}          # name -> (ms, midilen)
        self.log.append('boot snapshot=%s pat=0x%08x kit=0x%08x' % (
            self.snapshot_id, self.pat, self.kit))

    @staticmethod
    def syx_sha(path):
        h = hashlib.sha256()
        with open(path, 'rb') as fh:
            for blk in iter(lambda: fh.read(1 << 20), b''):
                h.update(blk)
        return h.hexdigest()

    def _on_f3(self, uc, addr, size, data):
        try:
            d4 = uc.reg_read(UC_M68K_REG_D4)
            a0 = uc.reg_read(UC_M68K_REG_A0)
        except Exception:
            return
        track = d4 // 326 if d4 % 326 == 0 else -1
        self.fires.append((round(self.s.ms, 1), track, a0))

    # -- input ---------------------------------------------------------------
    def key(self, name, hold=KEY_HOLD_MS, after=KEY_AFTER_MS):
        self.s.press(self.s.code(name))
        self.s.run_ms(hold)
        self.s.release(self.s.code(name))
        self.s.run_ms(after)

    def mark(self, name):
        self.marks[name] = (round(self.s.ms, 1), len(self.midibuf))

    # -- programming ---------------------------------------------------------
    def _step_on(self, track, step):
        b = self.s.m.peek(self.pat + track * TRACK_STRUCT + 2 * int(step) - 1,
                          1)
        return bool(b and b[0] & 1)

    def program(self, track, select, steps=STEPS):
        """Grid-rec `steps` onto `track`; `select` is the T-key or None
        (already selected). Verifies each step bit, fixes toggles that
        cleared a factory-occupied step."""
        t = time.time()
        if select:
            self.key(select)
            act = u32(self.s.m, ACTIVE)
            assert act == track, 'select %s: active=%s want %s' % (
                select, act, track)
        self.key('RECORD')
        for st in steps:
            self.key(st)
            if not self._step_on(track, st):
                self.key(st)  # factory had it ON; toggle back ON
            assert self._step_on(track, st), 'step %s t%d stuck OFF' % (
                st, track)
        self.key('RECORD')
        self.wall['program_t%d' % track] = time.time() - t
        self.log.append('program t%d steps=%s' % (track, ','.join(steps)))

    # -- chord ---------------------------------------------------------------
    def ensure_active(self, track, tries=4):
        """Tap MIDI until fw_active_track==track (release-retarget)."""
        for _ in range(tries):
            if u32(self.s.m, ACTIVE) == track:
                return
            self.key('MIDI', hold=50, after=50)
        assert u32(self.s.m, ACTIVE) == track, \
            'cannot select track %d (active=%s)' % (
                track, u32(self.s.m, ACTIVE))
        self.log.append('select t%d' % track)

    def chord(self, mode, reference=None):
        """MIDI+VOICE chord with positive outcome verification.

        mode='conv': pat4 must change vs loop start (MIDI->synth flip).
        mode='flip': pat4 must equal `reference` (pre-chord factory bytes).
        Selection is forced first so the MIDI-press stash is 4 either way.
        """
        t = time.time()
        self.ensure_active(4)
        start = bytes(self.s.m.peek(self.pat + 4 * TRACK_STRUCT,
                                    TRACK_STRUCT))
        ok = False
        attempts = 0
        for attempts in range(1, 4):
            self.s.press(self.s.code('MIDI'))
            self.s.run_ms(50)
            self.s.press(self.s.code('VOICE'))
            self.s.run_ms(30)
            self.s.release(self.s.code('VOICE'))
            self.s.run_ms(50)
            self.s.release(self.s.code('MIDI'))
            self.s.run_ms(100)
            after = bytes(self.s.m.peek(self.pat + 4 * TRACK_STRUCT,
                                        TRACK_STRUCT))
            if mode == 'conv' and after != start:
                ok = True
                break
            if mode == 'flip' and after == reference:
                ok = True
                break
        self.wall['chord_%s' % mode] = time.time() - t
        assert ok, 'chord %s failed after %d attempts' % (mode, attempts)
        self.log.append('chord %s attempts=%d active=%s' % (
            mode, attempts, u32(self.s.m, ACTIVE)))
        return attempts

    # -- transport -----------------------------------------------------------
    def play_until(self, need, min_ms=PLAY_MIN_MS, cap_ms=PLAY_CAP_MS):
        """PLAY then poll until `need(fires)->bool` or cap. -> elapsed ms."""
        t = time.time()
        self.key('PLAY', hold=60, after=100)
        self.mark('play_start')
        el = 0
        while el < cap_ms:
            self.s.run_ms(250)
            el += 250
            if el >= min_ms and need(self.fires):
                break
        self.mark('play_end')
        self.wall['play'] = time.time() - t
        self.log.append('play emu=%dms fires=%d' % (el, len(self.fires)))
        return el

    def stop_settle(self, select_first='T1'):
        t = time.time()
        self.key('STOP', hold=60, after=100)
        self.key('STOP', hold=60, after=100)
        if select_first:  # identical selection state for like-for-like fb
            # Leave MIDI-track bank first (T-keys select MIDI tracks there).
            for _ in range(3):
                if u32(self.s.m, ACTIVE) < 4:
                    break
                self.key('MIDI', hold=50, after=50)
            self.key(select_first)
            self.log.append('select %s pre-settle (active=%s)' % (
                select_first, u32(self.s.m, ACTIVE)))
        last = None
        stable = 0
        el = 0
        while el < SETTLE_CAP_MS:
            self.s.run_ms(200)
            el += 200
            h, _ = fb_hash(self.s.m, self.s.profile)
            if h == last:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
            last = h
        self.mark('settled')
        self.wall['stop_settle'] = time.time() - t
        self.log.append('stop emu_settle=%dms transport=%s' % (
            el, u32(self.s.m, TRANSPORT)))

    # -- captures ------------------------------------------------------------
    def capture(self, tag):
        m = self.s.m
        fbh, fbb = fb_hash(m, self.s.profile)
        tail = bytes(m.peek(self.kit + KIT_TAIL_OFF,
                            KIT_TAIL_END - KIT_TAIL_OFF))
        vbuf = bytes(m.peek(VOICES, VOICES_LEN))
        out = {
            'tag': tag,
            'ms': round(self.s.ms, 1),
            'transport': u32(m, TRANSPORT),
            'active': u32(m, ACTIVE),
            'fb_sha': fbh,
            'fb_hex': fbb.hex() if fbb is not None else None,
            'pat_sha': [sha(bytes(m.peek(self.pat + i * TRACK_STRUCT,
                                         TRACK_STRUCT))) for i in range(5)],
            'pat_hex': [bytes(m.peek(self.pat + i * TRACK_STRUCT,
                                     TRACK_STRUCT)).hex() for i in range(5)],
            'pat_step64': [bytes(m.peek(self.pat + i * TRACK_STRUCT, 64)).hex()
                           for i in range(5)],
            'kit_tail_sha': sha(tail),
            'kit_tail_hex': tail.hex(),
            'mutes_audio_hw': u16(m, AUDIO_MUTES),
            'mutes_midi': u32(m, MIDI_MUTES),
            'mutes_pat_hex': bytes(m.peek(self.pat + PAT_MUTES_OFF, 8)).hex(),
            'voice_Y': [u32(m, Y_BASE + 4 * i) for i in range(8)],
            'voice_cand_head': [bytes(m.peek(CAND_BASE + i * CAND_ROW, 8)).hex()
                                for i in range(8)],
            'voice_cached': [u32(m, CACHED_SOUNDS + 4 * i) for i in range(8)],
            'voice_track': [u32(m, VOICE_TRACK + 4 * i) for i in range(8)],
            'voice_len': [u32(m, VOICE_LEN + 4 * i) for i in range(8)],
            'gate_on': u32(m, GATE_ON),
            'gate_off': u32(m, GATE_OFF),
            'voices_sha': sha(vbuf),
            'voices_hex': vbuf.hex(),
        }
        return out

    def midi_window(self, a, b):
        """Non-realtime MIDI bytes + realtime count between marks a, b."""
        la, lb = self.marks[a][1], self.marks[b][1]
        raw = bytes(self.midibuf[la:lb])
        nonrt = bytes(x for x in raw if x not in REALTIME)
        rt = len(raw) - len(nonrt)
        return {'nonrt_hex': nonrt.hex(), 'nonrt_len': len(nonrt),
                'rt_count': rt}

    def f3_window(self, a, b):
        lo, hi = self.marks[a][0], self.marks[b][0]
        hits = [(ms, t, '0x%08x' % v) for ms, t, v in self.fires
                if lo <= ms <= hi]
        bytrk = {}
        for _, t, v in hits:
            e = bytrk.setdefault(t, {'count': 0, 'a0s': set()})
            e['count'] += 1
            e['a0s'].add(v)
        for e in bytrk.values():
            e['a0s'] = sorted(e['a0s'])
        return {'hits': hits, 'by_track': bytrk,
                'multi': [[t, v] for _, t, v in hits]}

    def close(self):
        self.s.close()
        self.wall['total'] = time.time() - self.t0


def scenario_base():
    r = Run(STOCK_FOLDER, STOCK_SYX_SHA)
    for i, t in enumerate(('T1', 'T2', 'T3', 'T4')):
        r.program(i, t)
    r.play_until(lambda f: all(
        sum(1 for _, t, _ in f if t == i) >= 2 for i in range(4)))
    play = {'f3': r.f3_window('play_start', 'play_end'),
            'midi': r.midi_window('play_start', 'play_end')}
    midplay = r.capture('play_end')
    r.stop_settle()
    final = r.capture('settled')
    final['midi_play'] = play['midi']
    final['f3_play'] = play['f3']
    final['voice_midplay'] = midplay['voice_Y'] and {
        k: midplay[k] for k in (
            'voice_Y', 'voice_cand_head', 'voice_cached', 'voice_track',
            'voice_len', 'gate_on', 'gate_off', 'voices_sha')}
    r.close()
    return pack('base', r, final)


def scenario_convert(folder=None, syx_sha=None):
    r = Run(folder or MOD_FOLDER, syx_sha or MOD_SYX_SHA)
    for i, t in enumerate(('T1', 'T2', 'T3', 'T4')):
        r.program(i, t)
    pre = r.capture('pre_chord')
    pre_pat4 = bytes(r.s.m.peek(r.pat + 4 * TRACK_STRUCT, TRACK_STRUCT))
    r.chord('conv')
    post = r.capture('post_chord')
    r.ensure_active(4)
    r.program(4, None)  # verified by struct; selection above, no T-key for 4-7
    r.pre_play = r.capture('pre_play')
    r.play_until(lambda f: all(
        sum(1 for _, t, _ in f if t == i) >= 2 for i in range(5)))
    play = {'f3': r.f3_window('play_start', 'play_end'),
            'midi': r.midi_window('play_start', 'play_end')}
    midplay = r.capture('play_end')
    r.stop_settle()
    final = r.capture('settled')
    r.chord('flip', reference=pre_pat4)
    flipped = r.capture('post_flipback')
    final['pre_chord'] = pre
    final['post_chord'] = post
    final['pre_play'] = r.pre_play
    final['midi_play'] = play['midi']
    final['f3_play'] = play['f3']
    final['voice_midplay'] = {
        k: midplay[k] for k in (
            'voice_Y', 'voice_cand_head', 'voice_cached', 'voice_track',
            'voice_len', 'gate_on', 'gate_off', 'voices_sha')}
    final['post_flipback'] = flipped
    r.close()
    return pack('convert', r, final)


def pack(scenario, r, final):
    return {
        'scenario': scenario,
        'snapshot_id': r.snapshot_id,
        'folder': STOCK_FOLDER if scenario == 'base' else MOD_FOLDER,
        'wall': {k: round(v, 1) for k, v in r.wall.items()},
        'log': r.log,
        'marks': r.marks,
        'halted': r.s.halted,
        'final': final,
    }


def compare(base, conv):
    v = {}
    fb = base['final']['f3_play']['multi']
    fc = conv['final']['f3_play']['multi']
    per = {}
    ok321 = True
    for t in (0, 1, 2, 3):
        ab = sorted(set(a for tt, a in fb if tt == t))
        ac = sorted(set(a for tt, a in fc if tt == t))
        nb = sum(1 for tt, _ in fb if tt == t)
        nc = sum(1 for tt, _ in fc if tt == t)
        same = ab == ac and len(ab) == 1
        covered = nb >= 2 and nc >= 2
        per[t] = {'a0s_base': ab, 'a0s_conv': ac, 'n_base': nb,
                  'n_conv': nc, 'same_fetch': same, 'covered': covered}
        ok321 = ok321 and same and covered
    v['a_f3_0_3'] = {'pass': ok321, 'per_track': per}
    mb = base['final']['midi_play']
    mc = conv['final']['midi_play']
    v['a_midi'] = {'pass': mb['nonrt_hex'] == mc['nonrt_hex'],
                   'base': mb, 'conv': mc}
    v['a_mutes'] = {'pass': base['final']['mutes_pat_hex'][:6] == conv[
        'final']['mutes_pat_hex'][:6] and base['final']['mutes_audio_hw'] == conv[
        'final']['mutes_audio_hw'], 'base_pat': base['final']['mutes_pat_hex'],
        'conv_pat': conv['final']['mutes_pat_hex'],
        'base_hw': base['final']['mutes_audio_hw'],
        'conv_hw': conv['final']['mutes_audio_hw']}
    v['a_kit_tail'] = {'pass': base['final']['kit_tail_sha'] == conv[
        'final']['kit_tail_sha'],
        'base': base['final']['kit_tail_sha'][:16],
        'conv': conv['final']['kit_tail_sha'][:16]}
    hbb, hcb = base['final']['fb_hex'], conv['final']['fb_hex']
    if hbb and hcb and hbb != hcb:
        import binascii
        a = binascii.unhexlify(hbb)
        b = binascii.unhexlify(hcb)
        n, box = pixel_diff(a, b)
    else:
        n, box = (0, None) if hbb == hcb else (-1, None)
    v['a_fb'] = {'pass': hbb == hcb, 'pixels_differing': n, 'box': box,
                 'base': base['final']['fb_sha'][:16],
                 'conv': conv['final']['fb_sha'][:16]}
    vb = base['final']['voices_sha']
    vc = conv['final']['voices_sha']
    oth = all([v['a_f3_0_3']['pass'], v['a_midi']['pass'],
               v['a_mutes']['pass'], v['a_kit_tail']['pass'],
               v['a_fb']['pass']])
    # voices buffer mixes in the converted track-4 voice (fires only in
    # conv); allowed to differ iff every other (a) signal is identical.
    v['a_voices'] = {'pass': vb == vc or oth, 'identical': vb == vc,
                     'skew_allowed': vb != vc and oth,
                     'base': vb[:16], 'conv': vc[:16]}
    v['a_overall'] = {'pass': all([v['a_f3_0_3']['pass'], v['a_midi']['pass'],
                                   v['a_mutes']['pass'], v['a_kit_tail']['pass'],
                                   v['a_fb']['pass'], v['a_voices']['pass']])}
    # (b) slot-4 publish
    t4 = [(ms, a) for ms, t, a in
          [(ms, t, a) for ms, t, a in conv['final']['f3_play']['hits']]
          if t == 4]
    a0s = sorted(set(a for _, a in t4))
    inram = [a for a in a0s if MODRAM_LO <= int(a, 16) < MODRAM_HI]
    v['b_publish'] = {'pass': len(inram) > 0, 'track4_hits': len(t4),
                      'a0s': a0s, 'in_modram': inram,
                      'matches_prior': ('0x%08x' % PRIOR_BSS_A0).lower() in
                      [a.lower() for a in a0s],
                      'prior': '0x%08x' % PRIOR_BSS_A0}
    # (c) kit tail pre/post flips
    tails = {'pre': conv['final']['pre_chord']['kit_tail_sha'],
             'post_chord': conv['final']['post_chord']['kit_tail_sha'],
             'settled': conv['final']['kit_tail_sha'],
             'post_flipback': conv['final']['post_flipback']['kit_tail_sha']}
    v['c_tail'] = {'pass': len(set(tails.values())) == 1,
                   'tails': {k: w[:16] for k, w in tails.items()}}
    p4 = {'pre': conv['final']['pre_chord']['pat_sha'][4],
          'post_chord': conv['final']['post_chord']['pat_sha'][4],
          'post_flipback': conv['final']['post_flipback']['pat_sha'][4]}
    v['c_roundtrip'] = {'pass': p4['pre'] == p4['post_flipback'] and p4[
        'pre'] != p4['post_chord'],
        'pat4': {k: w[:16] for k, w in p4.items()}}
    # (d) allocator/sustain state (record only)
    f4 = conv['final']
    v['d_state'] = {'midplay_Y4': f4['voice_midplay']['voice_Y'][4],
                    'settled_Y4': f4['voice_Y'][4],
                    'midplay_cand4': f4['voice_midplay']['voice_cand_head'][4],
                    'settled_cand4': f4['voice_cand_head'][4],
                    'cached': f4['voice_cached'],
                    'voice_track': f4['voice_track'],
                    'midplay_len': f4['voice_midplay']['voice_len'],
                    'settled_len': f4['voice_len'],
                    'midplay_gates': (f4['voice_midplay']['gate_on'],
                                      f4['voice_midplay']['gate_off']),
                    'settled_gates': (f4['gate_on'], f4['gate_off']),
                    'midplay_voices': f4['voice_midplay']['voices_sha'][:16],
                    'settled_voices': f4['voices_sha'][:16],
                    'f3_track4_hits': len(t4)}
    return v


def counts(multi, tracks):
    return {t: sum(1 for tt, _ in multi if tt == t) for t in tracks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scenario', choices=('base', 'convert'))
    ap.add_argument('--out')
    ap.add_argument('--compare', nargs=2, metavar=('BASE', 'CONV'))
    ap.add_argument('--folder', default=None,
                    help='override snapshot folder for convert scenario')
    ap.add_argument('--syx-sha', default=None,
                    help='override syx sha256 for convert scenario')
    args = ap.parse_args()
    if args.compare:
        with open(args.compare[0]) as fh:
            base = json.load(fh)
        with open(args.compare[1]) as fh:
            conv = json.load(fh)
        rep = {'base': base['snapshot_id'], 'conv': conv['snapshot_id'],
               'verdicts': compare(base, conv)}
        print(json.dumps(rep['verdicts'], indent=1, default=str))
        if args.out:
            with open(args.out, 'w') as fh:
                json.dump(rep, fh, indent=1, default=str)
        return
    assert args.scenario and args.out
    rep = (scenario_base() if args.scenario == 'base'
           else scenario_convert(folder=args.folder, syx_sha=args.syx_sha))
    with open(args.out, 'w') as fh:
        json.dump(rep, fh, indent=1, default=str)
    print('scenario=%s snapshot=%s halted=%s wall=%s' % (
        rep['scenario'], rep['snapshot_id'], rep['halted'], rep['wall']))


if __name__ == '__main__':
    main()
