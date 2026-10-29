# MAIN-page parity — follow-up to 3.4 (convert 0.24/0.25, tags 1488/1489)

Bug (live panel session, change 8track-engine): after MIDI+VOICE → YES
convert + double-tap browse + YES apply (LOADED toast, slot voices), the
track MAIN page (TRIG key — the panel has no SRC key; TRIG = MAIN) still
renders the MIDI SRC UI instead of the synth UI. Task 3.4 proved the
SYN1/SYN2/FLTR/AMP pages via the P1/P2 page-function divert; the MAIN
page dispatch is a separate path.

Harness: tests/probe/cnv_mainpage.py (stock/repro/s5proof/trigsweep/
maintrace/override/trigvals/trigdiv/bankread_trig/textf/labelwrite/
labelregs/labelchain/trigsub/mirrorproof/mainsynth/fixreg legs).
Raw JSONs + PNGs live OUTSIDE the repo (/tmp/opencode/mainpage/).

## Ruling (prove-before-patch)

- S5 `0x4003ca70` (`moveq #3,d0; cmp.l d6,d0; blt -> MIDI`): SILENT on
  TRIG opens — 0 hits on native t0, converted t4 and native-MIDI t5
  (s5proof leg) → index-agnostic suspicion DISCHARGED, left stock.
  (S8 `0x40160968` likewise silent on page gestures per 3.4.)
- Live MAIN dispatches (all with compared-reg == ACTIVE/track proven on
  TRIG opens, fork-taken diverging exactly on converted):
  - C `0x4003db2c` (`moveq #3,d1; cmp.l d3,d1; bcs -> 0x4003db3c`):
    d3 == ACTIVE (0 nat / 4 conv / 5 MIDI), synth table a2+$f0 vs MIDI
    table a2+$148 — the exact P4 entry-filler shape (P4's filler at
    0x4003f184 never runs on the TRIG flow: 0 fork hits on converted
    TRIG). Refresh-time fill (66-71x/open), so the converted MAIN page
    follows it every frame. Interposed as C1 (0.24).
  - A `0x4001d860` (`moveq #3,d2; cmp.l d1,d2; bcs -> 0x4001d87a`):
    d1 == ACTIVE (0 nat / 4 conv), synth math track*20+$d00 vs MIDI
    math (track+$1d3)*8 — the shared track->struct resolver feeding
    the MAIN page's knob values. Open-time burst (~70x/open); converted
    takes the MIDI math. A live d1->slot override flips the converted
    LEN dial to the slot's synth struct (before/after PNG diff is the
    LEN dial only); a d0->0 override at S4B changes nothing visible
    (S4B/D left stock). Interposed as A1 (0.25, mirror d1).
  - D/S4B `0x4004348a`: compared d0 == ACTIVE proven, but the fork is
    benign on the MAIN path (native SYN TRIG takes the "MIDI" return-1
    fork and renders fine; forcing return-1 on converted changes zero
    pixels) → left stock, no patch.
- Native replays are bit-exact: full-fb nat0/mid5 hashes identical
  across 0.23/0.24/0.25; title-band run jitter (~1px text shift) is
  masked for comparison (panel y<12 zeroed) — masked nat0
  `2eaed16dcc087415` uniform over all runs/builds.

## What the bug was (emu-proven)

- Converted TRIG (0.23): "MID 1" + FULL synth layout (same params as
  native SYN TRIG). Layout already synth via P1/P2; values via MIDI
  math (A-stock) — the LEN dial renders MIDI-struct values.
- TRIG values are pattern-level (shared trigs, apply-invariant — same
  on native: native TRIG knobs leave the kit sound untouched,
  live_diff_n=0 x4, parity with converted snd_diff_n=0 x4) plus
  A-resolved slot values (synth-routed post-A1).
- The "MID 1" track-box label is bank identity, same convention as the
  3.4-accepted converted SYN1 page ("MID 1" + "Synth (1/2)" title) —
  shared track-box routine (identical writer PCs nat/conv), not a page
  fork; consistently out of scope (no page-fork evidence implicates
  it: A/C/D interventions leave it unchanged).
- No TRIG subpages (RIGHT/TRIG/LEFT are no-ops on all banks); no SRC
  key on the Digitone panel; stock MIDI TRIG is the sparse layout
  (dotted boxes) — converted never shows it (full layout throughout).

## Proof (0.25 / tag 1489, snapshot dn1-1489-b1c8baee, SETTLED)

- mirrorproof: no-browse convert -> TRIG fb `68dcba99e30ab53b`
  BIT-EXACT vs the 0.23 live-override evidence fb (A-divert works
  precisely as designed); nat0 masked `2eaed16dcc087415` (bit-exact);
  mid5 `4ae000c892e61593` unchanged. PASS.
- maintrace on 1489: conv TRIG takes asynth with d1=0 (mirror),
  csynth (was cmidi on 0.23), dsynth (stock); SYN1-conv takes asynth
  d1=0 + csynth + p4synth; natives take stock forks (nat0 asynth
  d1=0/csynth/p4synth; flip-back stock4 amidi/cmidi/p4midi). PASS.
- mainsynth on 1489 (full bug flow: convert+browse+apply+TRIG):
  conv renders the slot-synth values (masked == override hash);
  nat0/mid5 unchanged. PASS. (Full-fb title jitter noted; masked
  compare used.)
- trigvals: knob codes 1-4 on conv TRIG leave .bss AND kit MIDI
  untouched (pattern-target, correct); display moves focus only.
  Native parity: kit sound untouched likewise. PASS.
- Release 1487 repro: conv TRIG fb `fb74f0600561c859` — identical to
  the 1486 test build (bug present on the release build; same applied
  preset bytes `27ea...`). PASS (bug confirmed pre-fix state).
- fixreg (3.4 subset on 1489): pageopen — t0/t4 SYN1/SYN2 green
  (p1 mirror, mod row, row16 .bss/kit, S8/S5 silent); t5 native-MIDI
  cells identical to the 1486 baseline (row16 False = stock MIDI-row
  behavior, verified parity, not a regression). knob — SND changes,
  kit + MIDI params untouched, flip-back STASHED. timbre — PASS
  (render energy 48M/12M, series differ). muteseq — sequencer energy
  119M on converted (>0); UI mute-gesture leg finds no single-chord
  flip (harness limitation, same as 3.4 — B0 divert steals T-taps;
  poke-based mute proofs in 3.4 stand). All green; wall 300.4 s
  (one-off full-subset run, like 3.4's 97/75 s notes).

## Builds

- convert 0.24 (19 sites: +C1): lint OK, linked tag 1488
  (`93f80b31…`), snapshot dn1-1488-93f80b31 SETTLED. C1 alone is
  pixel-invisible on TRIG (masked fb unchanged) but selects the synth
  views section in the refresh filler for converted (fork-verified).
- convert 0.25 (20 sites: +A1 `0x4001d860` + `cnv_mirror_track`):
  lint OK (problems []), linked tag 1489 (`b1c8baee…`), snapshot
  dn1-1489-b1c8baee SETTLED (66 s one-off settle). Post-link .s edit
  was comment-only (machine code identical — 58 metadata-hash bytes
  differ at the container tail); registry copy re-synced.
- Used tags: test 1464/1466/1470/1477-1486, release 1487, test
  1488/1489. No collisions.

## Files changed (this change only)

- modules/dn-convert/cnv_page.s: +C1 block (P4-discipline filler
  divert, reuses cnv_c3_route) and +A1 block (mirror divert).
- modules/dn-convert/convert.c: +cnv_mirror_track (no other C changes).
- modules/dn-convert/mod.json: 0.23 -> 0.24 -> 0.25, +2 site entries
  (C1 `7203b283650a`, A1 `7403b4816514`).
- tests/probe/cnv_mainpage.py: new harness (this file's legs) + this md.
- Untouched: earlier cnv_* files, tasks.md, openspec, docs, releases.
