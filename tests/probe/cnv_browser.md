# convert 0.14 — sound-browser parity (8track-engine task 3.1)

Date: 2026-10-28. Lane: identification pass (read-only) → interpose
(B0/B1/B2/B3) → emu proof. Build → lint → link (new tag) → boot-settle →
headless single-Session legs, <60 s/run. Evidence JSONs live OUTSIDE the
repo (scratch, no firmware, no baselines):
`/tmp/opencode/br_open.json`, `br_single.json`, `br_kit.json`,
`br_native.json`, `br_b1.json`. Harness: `tests/probe/cnv_browser.py`
(new, re-runnable). **Verdict: 3.1 BLOCKED** — the open chain (B0/B1/B2)
and the apply row path (B3) are proven and working, but the stock
double-tap browser gate (f330 subtree, 0x4004f330) never opens the
browser for converted slots (0/25+ double-taps, gaps 60–500 ms, 5 tags).
Per the lane hard rules the unproven gate is recorded, not patched.

## 0. Method note

Classification ground truth is mod RAM + link map, not pixels. The
link map `test-cnv14f.syx.map.json` (sibling `firmware/`, never
committed) gives exact mod addresses per build (current tag 1477:
MODAL_SLOT 0x43ec2300, STATE 0x43ec3798, SND 0x43ec3a40,
ROW 0x43ec2ac0, B0 0x43ec14f8, B1 0x43ec1536, B2 0x43ec1566,
B3 0x43ec1596) — no layout reverse-engineering per build. Boot asserts
MODAL_SLOT == -1 and STATE == 0. Emu input is racy (key-scan phase;
see cnv_modal.md §7), so every gesture is outcome-verified with retries;
code hooks occasionally miss (obs8 saga — a hook firing 0 times proves
nothing by itself; every site below was proven by hooks that DID fire
across repeated runs, plus readback effects).

## 1. Build

```
cd /home/nuke/Documents/Elektron-MODS/tools/elekloader && PYTHONPATH=. \
  python3 -m elekloader.sdk.build \
  /home/nuke/Documents/Elektron-MODS-8-track-engine/modules/dn-convert \
  --stock /home/nuke/Documents/Elektron-MODS/firmware/Digitone_and_Digitone_Keys_OS1.44.syx \
  --out /home/nuke/Documents/Elektron-MODS-8-track-engine/modules/dn-convert/out
```

```
BUILT .../modules/dn-convert/out/convert-0.14.elemod
  convert 0.14: .run 3892, .fast 0, .bss 5284 bytes; 7 sites, 150 relocations; imports fw_active_track, fw_fillrect, fw_font5, fw_kit, fw_memcpy, fw_memset, fw_pattern, fw_textf
```

Result: PASS. `.bss` 2052 → 5284 (+4×808 B browser rows). Intermediate
tags 1471/1472/1474/1476 were bench iterations (B2 stack-arg swap bug,
`addq #12` assemblergap, B2-disabled experiment); their `.syx` files
were deleted, only tag 1477 is live.

## 2. Lint

```
python3 -m elekloader.lint .../out/convert-0.14.elemod \
  --stock .../Digitone_and_Digitone_Keys_OS1.44.syx \
  --with .../firmware/elemods/core-dn1-4.1.1-os1.44.elemod
```

```
OK: convert 0.14 (format 2) for Digitone mk1 1.44: 7 sites, ...
OK: links as core 4.1.1 > convert 0.14; RAM 16216 of 1310720 bytes, fast SRAM 0 of 0
```

Result: PASS.

## 3. Link (OUTSIDE tracked trees)

Tag check: release READMEs in both checkouts carry only `tag 1499`;
test tags 1470 (0.13), 1471/1472/1476 (0.14 bench) exist on disk → 1477
free (1474 skipped: built with a broken `addq #12`, never booted).

```
python3 -m elekloader.patch --stock .../Digitone_and_Digitone_Keys_OS1.44.syx \
  --mod .../core-dn1-4.1.1-os1.44.elemod \
  --mod .../modules/dn-convert/out/convert-0.14.elemod \
  --out /home/nuke/Documents/Elektron-MODS/firmware/test-cnv14f.syx --version 1477
```

```
WROTE /home/nuke/Documents/Elektron-MODS/firmware/test-cnv14f.syx
  sha256 cc9e5776ab61abfd73f826fd0197df78708c6a1179bf192dd99f227b4be00cd3, version 1477, 1715744 bytes
```

Result: PASS.

## 4. Boot

```
cd /home/nuke/Documents/Elektron-MODS/tools/digiemu && .venv/bin/python \
  -m emu.portable --add /home/nuke/Documents/Elektron-MODS/firmware/test-cnv14f.syx --yes
```

Result: PASS — persistent snapshot `dn1-1477-cc9e5776`, SETTLED at
1200 M, settle ~30 s. All legs below boot ONE Session from it.

## 5. Identification (read-only; stock 1.44 image + emu observation)

Browser-open path (double-tap T-key), traced with block-set diffs
(single- vs double-tap) + call-site/return-address-filtered predicate
logging + row-table dumps:

- T-key dispatch (0x4004ed72 region): bank check
  `jsr 0x4002e1ae` at **0x4004ef1a** (MIDI bank → skip double-tap arm via
  0x4004ef26 `addil #-38,d3`, d3 = track 4..7; synth bank → arm check).
- Double-tap arm predicates on the key-cell struct 0x40553eac+16
  (ed34 = bit0, ed60 = bit2, ed70 = bit1, ed80 = bit0&~bit3); both taps
  of a double reach the shared `jsr 0x400ded34` with d3 = track
  (logged 0 native / 4 MIDI).
- Browser function 0x4004ed68 → open branch at **0x4004eda8**
  (`moveq #3,d1; cmpl d2,d1; bcs 0x4004edf6`): d2 = track (proven:
  ed68 fp+8 = pushed d3; dcf2 logs index == track for T1–T4; B1 hook
  logs d2 = 4 on converted taps — `br_b1.json`).
- Browser rows: 808B rows at table base+96+808t (base 0x41a722f0,
  stable across boots). Rows 0–3 share the static synth session object
  0x40196104; rows 4–7 are MIDI sessions (different objects). Rows are
  STATIC across open/DOWN/YES (obs27) — session/highlight lives
  elsewhere. dcf2 (0x4001dcf2) clamps index 0..3.
- Apply (preset YES): function B at 0x4001d710; the 326B kit write is a
  stock MEMCPY call at **0x4001d764** (ret 0x4001d76a) with
  dst = kit+0x18+326t (virtual `*(row+16)`, 0x401535c4, pure field
  read), src = 0x41c194a0 staging, len = 326 (hooked: single call,
  `ret=0x4001d76a dst=0x413062ac src=0x41c194a0 len=326` for track 0;
  d2 = active track at entry: 0 for track 0, 2 after switching to
  track 2 with the browser open — the YES handler passes ACTIVE track).
  Toast "LOADED '…'"; slot changes; no halt.

## 6. Interpose (convert 0.13 → 0.14)

`modules/dn-convert/cnv_browse.s` (new) + 2 C helpers (convert.c) +
4 sites (mod.json). Discipline: whole-instruction/jsr, scratch saved,
rts exits consume the site return (no pop), jmp exits pop first
(addq.l #4,%sp before the replayed CMP):

- **B0** 0x4004ef1a (6 B `4eb94002e1ae`, bank-check jsr): detour calls
  `cnv_brow_open(cell, keycode)` (re-runs the stock check by pointer,
  so native rejoins bit-exactly). Converted MIDI-bank T-press →
  d4 = track, d0 = 0 (synth path); else d0 = stock bank value, rts to
  0x4004ef20. d3 = keycode (42..45) selects the slot; d4 is the divert
  output (outside the save set), d0 the rejoin value.
- **B1** 0x4004eda8 (6 B `7203b2826548`): `cnv_route_synth(d2)`; synth
  → replay moveq/cmp + rts (rejoin 0x4004edae); MIDI → pop + replay +
  jmp 0x4004edf6 (S1/S2 discipline). d2 = track (proven §5).
- **B2** 0x4004edb2 (6 B `4eb94001dcf2`, row call site): stack holds
  [ret][d0=base][d2=track] — the pushes land base on top. Detour pushes
  (track, table) (C right-to-left) and calls
  `cnv_brow_row_for(table, track, wire=0)`: converted → fresh copy of
  the mirror native row into mod `.bss`, returns mod row in d0 + rts;
  native → jmp 0x4001dcf2 (its rts rejoins 0x4004edb8). Two stack-arg
  bugs were caught by emu readback during the lane (swapped pushes;
  `addq #12` is not encodable — fixed to `lea`).
- **B3** 0x4001d73e (8 B `4c00280045f32860`, mulsl+lea, jsr+nop-pad):
  detour calls `cnv_brow_row_for(a3, d2, wire=1)`; converted →
  a2 = mod row, d2 -= 4 (slot, so the following stock deref loads the
  synth session object, never a MIDI-row object), rts; native → replay
  muls+lea + rts. The helper copies the mirror row, wires +16 to
  `&cnv_synth_snd[slot]` and invalidates the voice cache — so the stock
  326B MEMCPY lands in `.bss` (kit untouched; next F3 fire warms it).
- `cnv_brow_row[4][808]` in `.bss`; row+16 wiring verified live
  (row16 == SND after diverted taps; mirror-row copy verified:
  copy-only row reads back kit slot 0's pointer).

## 7. Emu proof

| # | assertion | verdict | evidence |
|---|---|---|---|
| a | B0 diverts converted T-taps to the synth path | PASS | ef2e-synth hits on single+double taps; ACTIVE stays 4 |
| b | B1 compared reg is track; routes converted to edae | PASS | `br_b1.json`: d2 = [4,0,4,0,4,0,4] at SITE_B1 |
| c | B2 serves mod rows for converted (copy + wire) | PASS | row16 == SND readback; mirror-row content readback |
| d | double-click converted slot opens the SYNTH browser | **BLOCKED** | 0/25+ double-taps (gaps 60–500 ms, 5 builds) + 8 immediate-YES + 14 triple-taps: fb never the browser; SND never changes |
| e | preset apply lands in `.bss` + voices | BLOCKED on (d) | B3 built, never fires for converted (no browser open) |
| f | native browser path bit-identical | PASS | `br_native.json`: browser fb 3404de42 == stock; kit slot changes via stock path; SND/ROW untouched |
| g | single-tap parity (select stable, MIDI page, modal works) | PASS | `br_single.json`: ACTIVE=4, stable select fb 629c3a9d, modal opens after |
| h | kit tail + slot-4 region + pattern identical across convert+taps+flip-back | PASS | `br_kit.json`: tail `ddba55ce…`, pattern/slot hashes equal |
| i | per-run wall <60 s | PASS | open 22.8 s, single 6.5 s, kit 5.7 s, native 6.9 s |

BLOCKED detail (the f330-subtree gate): a recognized double-tap takes
f0c6 (`clrb d3`) → f330 with d3 = 0 on BOTH banks. Native (ACTIVE 0)
opens the browser from there; converted (ACTIVE 4) never does (fb
stays MIDI main; SND unchanged even with immediate YES). Same view
object (0x41a715a0) and same regs (d3 = 0) at f330 in both cases —
the gate reads MIDI-bank context downstream (ACTIVE/view/row; the 9
ACTIVE-global readers stay silent in the post-f0c6 window, so it is
not a plain ACTIVE-global branch — likely view/row-identity or an
indexed virtual). No single `moveq #3;cmp;blt` (or compared-reg ==
track) site was found on that path despite block-diff tracing
(native→0x40045abe/synth-voice-menu vs converted→0x40042b56/MIDI
path after common prefix …e57e0). Per the lane hard rules the gate is
recorded, not patched: B4+ would be guessing at a view/object cascade
with no proven track comparison.

## 8. Files changed (this lane; `tasks.md` untouched, 3.1 unticked)

- `modules/dn-convert/convert.c`: `cnv_brow_row[4][808]`,
  `cnv_brow_open`, `cnv_brow_row_for` (+comment block)
- `modules/dn-convert/cnv_browse.s`: B0/B1/B2/B3 detours (new)
- `modules/dn-convert/mod.json`: 0.13 → 0.14 (+source, +4 sites,
  description)
- `modules/dn-convert/out/convert-0.14.elemod`: built artifact
  (tag-1477 link; intermediate bench tags deleted)
- `tests/probe/cnv_browser.py`: this lane's harness (new;
  legs open/single/apply/voice/native/kit)
- `tests/probe/cnv_browser.md`: this file (new)

No firmware committed (all `.syx`/`.map.json` under sibling
`firmware/` + `/tmp`); no `tools/` changes; no stock widening.

## 9. Build / snapshot ids

- elemod `convert 0.14` (`.run 3892, .bss 5284`, 7 sites, 150 relocs)
- `.syx` `test-cnv14f.syx` tag **1477**
  `sha256 cc9e5776…be00cd`
- snapshot **`dn1-1477-cc9e5776`** (SETTLED 1200 M, settle ~30 s)
- core 4.1.1 unchanged; RAM 16216/1310720 B

## 10. Follow-up (lane 3.1b proposal)

Prove the f330 gate's compared value (candidate: the post-f0c6 f330
args with ACTIVE forced 0..3 on a converted slot, or the view-track
field read in the e53xx/e54xx fork), then add ONE site there (converted
→ synth fork). Reuse: B0/B1/B2 stay; B3 + modrow + `+16 → .bss` wiring
already deliver the apply the moment any opener reaches function B
with d2 = active track. Alternative opener: mod-side double-tap
detect (cnv_key already sees raw presses) driving the stock f0c6→f330
path — needs the same gate proof first.
