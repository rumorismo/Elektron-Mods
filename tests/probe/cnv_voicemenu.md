# 3.2 voice-menu parity — evidence (convert 0.18, tag 1481)

Date: 2026-10-28. Lane: register-proof → live-site hunt → interpose
(V8) → emu proof. Build → lint → link (new tag) → boot-settle →
headless legs, each <60 s wall. Evidence JSONs + PNGs live OUTSIDE the
repo (`/tmp/opencode/vm_*.json`, `/tmp/opencode/menu_*.png`); harness:
`tests/probe/cnv_voicemenu.py` (re-runnable).

## 0. Verdict

- **S3/S4 NOT interposed (hard-rule stop).** S3 `0x4003df40`
  (`7003b0846d3c`: moveq #3,d0; cmp.l d4,d0; blt.b `0x4003df82`) and S4
  `0x40043258` (`7203b2826d42`: moveq #3,d1; cmp.l d2,d1; blt.b
  `0x400432a0`) exist in stock with the described fork shape (synth
  forks call `0x400e8be8`/`0x40158770`/`0x400e54a2`+`SP_RELEASE`;
  routines at `0x4003df06`/`0x40043228` derive d4/d2 from the
  `0x4002c6ba` view-track reader). But entries, sites and BOTH forks
  stay silent on plain VOICE (native 0-3, converted 4-7, all five
  modal-leg page contexts) and on a gesture sweep (FUNC+VOICE, page
  keys, encoders, PTN, BANK, GLOBAL, SONG, YES-in-menu, T-select,
  single/double taps, converts). The compared regs are therefore
  UNPROVEN — patching them would be the blind patch the lane rules
  forbid. They are left stock.
- **V8 interposed instead (the live dispatch, proven).** Plain VOICE
  runs the `0x4003f62e` block for every track: `ded04(view)` must pass
  (`bcc 0x4003f63a → 0x400403bc` MIDI), then the bank check
  `jsr 0x4002e1ae` at **V8 `0x4003f642`** (`4eb94002e1ae`) must read
  synth (`tst.b d0; bne.w 0x4003f64c → 0x400403bc` MIDI on nonzero low
  byte: stock synth verdict `0xbec97400`, MIDI `0xbec97301`); else
  `bra 0x4003f650 → 0x400407e2` (V7 `ded70` block → beq to `0x40040856`
  → `jsr 0x40158770` menu builder at `0x400408de`, ret `0x400408e4`).
  `cnv_site_v8` diverts converted tracks to d0 = 0 (rejoin Z set,
  bne skips MIDI — exactly the stock synth-bank flow; d0 is dead past
  the fork, ded70's own jsr result overwrites it), else replays stock.
  Native path bit-identical by construction (stock check re-run).
- **Builder-chain parity achieved; content parity is 3.3/3.4.**
  Post-patch, converted-4 takes the reg-identical synth-builder
  invocation as native-0 (`58770←0x400408e4` + `e7020←0x400408f4`,
  same regs, same view object + bytes). The built menu still shows
  MIDI params (CHAN/BANK/… + `MID 1`, title follows the converted
  sound `FLOATER 2`) while native-0 shows synth params (ALGO/RATIO/…,
  `SYN 1`) — PNG-verified. The widget set keys off ACTIVE downstream
  of the builder at an unlisted site (S5/S6/S7/S8 all silent on VOICE;
  the view object is byte-identical between the two): labels = task
  3.3, pages = task 3.4. No crash, no kit/pattern writes, native and
  MIDI-native paths unchanged.

## 1. S3/S4 mechanism (record, not patch)

- S3 routine `0x4003df06`: `link; movem; a2=8(a6); d3=c(a6);
  d4=c6ba($a8(a2))`; flag `0x402296f0&0x80000` check → MIDI;
  `d3→0x400dbce2 → d2; beq → MIDI`; site `0x4003df40`; synth fork
  `0x4003df46` (`pea 1; jsr 0x400e8be8; tst; jsr 0x40158770; jsr
  0x400e54a2; jsr SP_RELEASE 0x40146456`); MIDI fork `0x4003df82`
  (`move.l d3,-(sp); pea 4(a2); jsr 0x400dc23c`).
- S4 routine `0x40043228`: frame args d3-d6; `d2=c6ba($74(a2))`;
  `moveq #9,d0; cmp.l d3,d0; bne → MIDI`; site `0x40043258`; synth
  fork `0x4004325e` (`pea 1; jsr 0x400e8be8; tst; bne → MIDI; jsr
  0x4002f91a(d2,$74(a2))`); MIDI fork `0x400432a0` (shared with the
  d3 early-out).
- Silence evidence: `vm_regs4.json` (12 cells, S3/S4 hit counts all
  0), `vm_routeA/B.json` (S3/S4 entries+sites hooked, 0 hits),
  `vm_sweep.txt` (14 gestures, 0 hits), `vm_conv4.txt` (0 hits).
  No `jsr abs`/`jsr (PC)`/`bsr` callers exist in the image (likely
  virtuals); plain VOICE demonstrably does not reach them.

## 2. Live dispatch proof (pre-patch, 0.17/tag 1480)

| leg | assertion | result | evidence |
|---|---|---|---|
| routeA (nat 0-3) | V7 `ded70` d2 == tapped track? | **d2 = const view ptr `0x40305f64`, NOT track** (ACTIVE == track separately); ded70 ret 0; menu fork taken; S3/S4 0 | `vm_routeA.json` |
| routeB (4 + nat 5-7) | MIDI-bank tracks reach V7? | **No** (no ded/menu hits; fb changes via MIDI path) | `vm_routeB.json` |
| routeC1 (nat 0-3) | V8 verdict/fork | `0xbec97400` → synth fork (0 synth hits required; midi hits are shared-target background) | `vm_routeC1.json` |
| routeC2 (conv 4 + nat 5-7) | V8 verdict/fork | `0xbec97301` → MIDI fork only, never synth | `vm_routeC2.json` |
| sweep | ded04/bank upstream of V8 | conv4: `ded04` passes (ret 1), bank fails → MIDI | `vm_gates.txt` |

Key derivations: only the bank verdict excludes converted tracks
(ded04 already passes); synth/MIDI verdicts differ in the low byte
(`tst.b` Z-test); the fork is the sole consumer of d0 (dead past it —
ded70's jsr overwrites d0), so returning 0 is behaviorally identical
to the stock synth-bank flow. ACTIVE == tapped track at V8 time is
established by select-verification + per-track menus in every cell;
chorded VOICE never reaches V8 (`cnv_key` swallows it), so ACTIVE
cannot be a stale chord track.

## 3. Interpose (convert 0.17 → 0.18)

- `modules/dn-convert/cnv_voice.s` (new): `cnv_site_v8` — B0/B5
  discipline (cell push already done by caller; single rts exit, no
  pop; d1/a0-a1 saved, d0 carries result; d2-d7/a2-a6 survive ABI).
- `modules/dn-convert/convert.c`: `cnv_voice_bank(cell)` — converted
  ACTIVE 4-7 → 0, else stock `cnv_bankcheck(cell)` replay. Only
  converted diverts; every other state replays stock (other block
  callers unaffected).
- `modules/dn-convert/mod.json`: 0.18 (+source, +1 site
  `0x4003f642`/`4eb94002e1ae`/`cnv_site_v8`, description).
- Build: `convert 0.18 (.run 4396, .bss 5284, 11 sites, 168 relocs)`.
  Lint: OK (links as core 4.1.1 > convert 0.18; RAM 16720/1310720).
- Link: tag **1481** (used: 1464/5/6/70/77/78/79/80 + 1499 releases)
  → `test-cnv18.syx` sha `647d35bb…a98153a737`, 1716000 B.
- Snapshot **`dn1-1481-647d35bb`** (SETTLED 1200 M, ~28 s).

Binary-verification note: an early scare (helper looked inverted in
live RAM) was a harness hook-offset mislabeling (`+0x2E` is the stock
rts, not the divert clr) plus shared-target fork noise. The linked
`.o` was disassembled with `m68k-linux-gnu-objdump` and matches the
source exactly; live capstone decode confirms; emu behavior confirms
(native stock verdicts, converted 0 verdict + synth fork).

## 4. Emu proof (post-patch, 0.18/tag 1481)

| leg | assertion | result | evidence |
|---|---|---|---|
| open nat0 | synth chain + builder caller | `58770←0x400408e4`, `e7020←0x400408f4`, menu `ae6f27a8` | `vm_open18.json`, `menu_nat0_18.png` (SYN/ALGO/RATIO/…) |
| open conv4 | same chain as native | V8 `0`, ded70 `0`, fork taken, **`58770←0x400408e4`** (same caller), menu opens | `vm_open18.json`, `menu_conv4_18.png` (MID/CHAN/BANK/… — content delta, §0) |
| open nat5 | MIDI path unchanged | stock verdicts, no ded/menu/builder hits | `vm_open18.json`, `menu_nat5_18.png` |
| regmodal | modal opens + NO-cancel + VOICE menu | PASS | `vm_regmodal18.json` (5.2 s) |
| regbrowser | single-tap select + modal + kit/pattern identity | PASS (tail `ddba55ce…` == 0.17 known-good) | `vm_regbrowser18.json` |

Per-run walls: regs4 45.7 s; routeA/B ~25 s each; routeC1/C2 ~40 s
each; open ~30 s; regmodal 5.2 s; regbrowser ~15 s.

## 5. Files changed (this lane; `tasks.md` untouched, 3.2 unticked)

- `modules/dn-convert/cnv_voice.s`: V8 detour (new).
- `modules/dn-convert/convert.c`: `cnv_voice_bank` helper (+comment).
- `modules/dn-convert/mod.json`: 0.17 → 0.18 (+source, +site).
- `modules/dn-convert/out/convert-0.18.elemod`: built artifact.
- `tests/probe/cnv_voicemenu.py`: harness (regs4/routeA/routeB/
  routeC1/routeC2/open/regmodal/regbrowser legs).
- `tests/probe/cnv_voicemenu.md`: this file (new).

No firmware committed (`.syx`/`.map.json` under sibling `firmware/`,
snapshots under sibling `portable/`, PNGs/JSONs under `/tmp`);
no `tools/` changes; S3/S4/sites left stock; no stock widening.

## 6. Follow-ups (out of 3.2 scope)

- Content classifier hunt (3.3/3.4): with V8 diverted, builder
  invocation is reg-identical and the view object byte-identical, yet
  widgets follow ACTIVE. Find the downstream ACTIVE-keyed fork
  (S5/S6/S7/S8 proven silent on VOICE — unlisted site inside the
  58770/e7020 subtree or the ded70/1d894 region).
- S3/S4 attribution: reachable from some untested gesture (virtuals?);
  identify before any patch (hard rule stands).
- Wall discipline: `routeC*`/`open` legs use fresh Sessions per track
  (boot ~4.6 s each); keep ≤4 tracks per leg.
