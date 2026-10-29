# MIDI coexistence proof — 8track-engine tasks 4.1 + 4.2

Date: 2026-10-28. Lane: coupled proof, one harness, one Session per run.
`tests/probe/cnv_midi.py` (new, re-runnable) + this file (new). No firmware
change, no `mod.json` bump, no relink, no `.syx` built (tag 1486 reused),
`tasks.md` untouched.

Convert 0.23 boots from the persistent settled snapshot
`dn1-1486-71493c78` (sibling `portable/`, SETTLED; test `.syx`
`test-cnv23.syx`, tag **1486**,
`sha256 71493c7805566e40c65a801c23dc7c1b1c5c0af17622e85e84a2cfd3e4e2adab`).
Stock baseline is the stock snapshot `dn1-1.44-d4f200d0`
(`Digitone_and_Digitone_Keys_OS1.44.syx`,
`sha256 d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b80cc13c9659`).

## Method (read first)

- **Snapshot copies.** Every proof run boots a FRESH COPY under
  `/tmp/opencode/cnv_midi_work/` (persistent snapshots pristine; the
  harness copies at start via `--copies`, verifies both `.syx` sha256,
  records folder + syx name). Conversions are unsaved RAM-only state and
  die with the session; the copies' cards are never saved to.
- **MIDI-DIN sink.** `emu.midi.MidiOut(sink=midibuf.extend)` attached
  exactly like `cnv_captures.py` (extend it, don't rewrite it). Windows
  are sliced by marks (`play_start/end`, `flipN_start/end`);
  `nonrt_hex` = bytes minus realtime set `{F8 FA FB FC FE FF}`,
  `clock_f8` counts `0xF8` explicitly.
- **CLOCK SEND off** for every run (factory default). Evidenced, not
  assumed: `clock_f8 == 0` and `rt_count == 0` in ALL 8 play/transition
  windows (total ~20 s emu). Recorded here as the setting.
- **OUTPUT TO is factory (USB).** The DIN sink is therefore mute by
  construction; see §4.2 BLOCKED. Enabling OUTPUT TO → MIDI needs the
  GLOBAL → MIDI CONFIG menu, which proved unscriptable headlessly
  (single-key delivery flake: GLOBAL/VOICE/turns land ~per-session, not
  per-press; arrows dismiss the SETTINGS overlay; see §6). No global was
  changed on any snapshot (copies or originals).
- **Audio stays ON** for sequencer legs (the step loop only advances on
  the audio clock; ~8x wall per emu-ms). The hunt leg (r4) uses
  audio=False (fast).
- **Outcome-verified flips.** Convert 0.23 uses the YES/NO modal with
  shared trigs (pattern NEVER changes), so chord verification is by
  framebuffer card + post-PLAY F3 publish (`track*326`, a0 in mod RAM),
  never by pattern diff. Flip-back is verified by F3 silence + mute-byte
  restore + kit tail.
- Evidence JSONs live OUTSIDE the repo (scratch):
  `/tmp/opencode/cnv_m_{r1,r2,r3a,r3b,r4,r5,cmp}.json`,
  PNGs `/tmp/opencode/cnv_m_png/`.

## 1. Task 4.1 — Bank-A MIDI byte-identity (PASS)

| # | assertion | verdict | evidence |
|---|---|---|---|
| 4.1a | stock baseline DIN stream captured (Bank-A MIDI 4–7, steps 2/6/10/14, 1–2 bar PLAY) | PASS | r1: `nonrt_len 0, rt_count 0, clock_f8 0, raw_len 0` (empty) |
| 4.1b1 | all-four converted play byte-identical to baseline | PASS | r2: empty; `same_as_baseline true` |
| 4.1b2 | mixed 2+2 play byte-identical to baseline | PASS | r3a + r3b-mixed: empty; `same_as_baseline true` |
| 4.1b3 | post-flipback play byte-identical to baseline | PASS | r3b-postflip1: empty; `same_as_baseline true` |
| 4.1c | flip + flip-back transition windows emit nothing | PASS | 3 windows (conv0, conv1, flip1): all `raw_len 0` |
| 4.1d | kit tail `KIT+0x5CE..0x85E` identical everywhere | PASS | `ddba55cebc7550b0` at all 7 captures (r1, r2, r3a, r3b-mixed, r3b-postflip1, r5 ×2) |
| 4.1e | pattern mute bytes round-trip | PASS | r3b final `0000285000010010` == r1 baseline exactly (`slot1_byte_restored true`); first-convert unmute (byte→0x00) is specified flip behavior, restored on flip-back |
| 4.1f | converted slots actually sounded during the identity plays (voice path engaged, not muted-by-accident) | PASS | r2: 8/8 publishes `0x43ec4ba8/…cee/…e34/…f7a` (326 B spacing, mod RAM); r3a: 4/4 (`…a8/…ce`); r3b-postflip1: track4 publishes ×2, track5 zero |

`overall_41.pass: true` (`cnv_m_cmp.json`).

- Mod publish addresses (0.23, stable across runs/slots): slot0
  `0x43ec4ba8`, slot1 `0x43ec4cee`, slot2 `0x43ec4e34`, slot3
  `0x43ec4f7a` (each = prior + 326 = `.bss` records).
- Native F3 fires (tracks 0/3 factory trig) present in all plays; not
  asserted (differs by design: converted tracks fire, MIDI tracks don't).
- First-convert unmute detail: factory mute bytes track5=`0x01`,
  track7=`0x10` are zeroed by the flip (`live byte = synth_mute = 0`,
  specified in `convert.c`) and the stashed value returns on flip-back
  (r3b final == r1 byte-exact).

## 2. Task 4.2 — Converted channel preserve (BLOCKED, with positive halves)

| # | assertion | verdict | evidence |
|---|---|---|---|
| 4.2a | set track-5 CHAN to 5 via MID-page encoder | FAIL (mechanical) | `set_ok false` ×4 sessions; display stays `X` (see below); candidate cell stays `10` |
| 4.2b | converted synth emits on the preserved channel (external DIN bytes) | BLOCKED | `midi_conv`: `nonrt_len 0, raw_len 0` — no bytes exist to carry any channel (factory OUTPUT TO=USB) |
| 4.2c | voice path unaffected while converted | PASS | track5 publishes `.bss 0x43ec4cee` ×2 during converted PLAY (r5 `conv_pub`); voices buffer renders (`ce08cde6…`) |
| 4.2d | MIDI side still holds state after flip-back | PASS (storage) | kit tail `ddba55ce…` identical pre/post; kit164 == factory (`00007000…`); mute byte5 restored `01`; pattern structs untouched (`ab28e98a…` all four) |
| 4.2e | channel-storage location recorded | PARTIAL | NOT in kit164 (164 B identical across CHAN-edit turns, r4) and NOT in pattern976 (identical, r4) → excluded from the flip's 164 B/976 B regions (structural preserve). Unconfirmed turn-tracking u32 at `0x41bf2a44` (below); exact offset unisolated |

Actual behavior, exactly: with factory OUTPUT TO the DIN sink observes
zero bytes in every window, so a converted slot's external channel is
unobservable headlessly; the on-screen MID page shows `X` for all eight
params on stock AND modded (factory rendering of the blank project, not
a convert regression — stock PNG `stock_mid5.png` identical); the
candidate channel cell reads `10` at all R5 stages
(factory/pre/convert/settled/flipback/follow-track6).

## 3. R4 hunt — where CHAN is not, and one candidate

Control-subtracted write hook (turns-window vs idle-window) on stock,
MID page track 5, encoder A sweeps (CCW6/CW12/CCW6):

- kit164 slot1 sha `daec2574…` BEFORE == AFTER; pattern976 track5
  identical BEFORE == AFTER. **The MID-page CHAN edit path writes
  neither the kit MIDI params nor the pattern struct.** The channel
  does not live in the flip's 164 B/976 B regions — preservation across
  flips is structural (the flip write-set excludes it), which is
  consistent with 4.2d passing.
- 5 candidates outside idle-addrs; the standout is `0x41bf2a44` (u32,
  n=20 ≈ 24 turn-calls): values ramp 9→2 (CCW) then 3→10 (CW) —
  bidirectional turn-tracking. Writer PC on a later probe: `0x400b0e64`
  (`move.l d0, $a4(a0)`), inside a 0..10 clamped stepper
  (`tst.b d0` direction; `ble` clamp 0; `moveq #9`/`blt` clamp 10;
  callback registered as a function pointer at `0x400b12b2`).
- **Not confirmed as CHAN**: R5 (×4 sessions) never moves it (stays
  `10`), and a 0..10 clamp fits no MIDI-channel range. Reported as an
  unconfirmed lead with disassembly, not a finding.

## 4. Why 4.2 is BLOCKED (stop-and-report, not forcing)

1. **No external bytes exist to judge.** Factory PORT CONFIG routes
   output to USB; the DIN sink is empty with or without conversions
   (§1). Proving "emits on channel 5" needs OUTPUT TO → MIDI, which
   needs GLOBAL-menu navigation.
2. **The menu path is unscriptable in this harness.** Per-key delivery
   is per-session flaky (GLOBAL opened the menu in 4/≈12 sessions; UP/
   DOWN dismiss the SETTINGS overlay and act on the main screen; no
   key combination navigated past the top list in any session).
   Full transcripts + PNGs: `/tmp/opencode/nav*.png`,
   recon scripts `/tmp/opencode/midi_nav*.py`.
3. **The encoder path is session-flaky too.** R4 turns moved the
   candidate cell; R5's identical turns (4 sessions, then a liveness
   gate: abort unless cell-or-fb moves) never moved it or the display.
   The X-display blocks UI-value ground truth.
4. Nothing here implicates `convert.c`: no code changed, no relink, no
   `mod.json` bump. The flip mechanics (publish/mute/tail/round-trip)
   all pass; the gaps are output-routing (global setting) and
   headless-input delivery (emulator), both outside the mod.

## 5. Incidental finding — flip-back reachability (UI law, for the record)

Only the MIDI-bank memorized slot is flip-back-reachable per session:
T-taps on a converted slot never change ACTIVE (B0 divert does not
deliver the converted track; polled 5×, active frozen), and bank
toggles only recall bank memory. Probed: convert 0,1 → flip-back 1
(memory ✓) → flip-back 0 **unreachable** (no card; assert with logs,
not forced). R3b is shaped around this law (convert transitions ×2,
mixed play, flip-back-1 transition + post play with slot 0 still
converted; slot 0 left converted is RAM-only and dies with the session).
Whether B0 should deliver the converted track (its comment claims
d4=track 4..7) is left to the implementer lane — recorded, not fixed.

## 6. Wall times (target <60 s/run; overruns reported, not hidden)

| run | wall | note |
|---|---|---|
| r1 stock baseline | 47.6 s | PASS budget |
| r2 all-four | 79.8 s | 4 modals + play (audio 8×) |
| r3a mixed | 58.8 s | PASS budget |
| r3b flips | 87.8 s | 2 plays + 3 modals |
| r4 hunt | 24.9 s | audio=False |
| r5 chan ×4 attempts | 82–108 s | 2 plays + 2 modals + set phase |

Overruns are inherent to convert-leg content (each modal ≈ 6–8 s wall,
each PLAY ≈ 13–26 s wall under audio 8×). No run was cut to fit the
budget; evidence is complete per run.

## 7. Files changed (this lane)

- `tests/probe/cnv_midi.py` (new): harness — legs r1/r2/r3a/r3b/r4/r5
  + compare. Boots snapshot copies, never the persistent folders.
- `tests/probe/cnv_midi.md` (this file).
- No other repo files touched. No firmware committed (all `.syx` under
  sibling `firmware/` or `/tmp`; proof runs used `/tmp` copies
  exclusively). `tasks.md` left unticked per instructions.

## 8. Reproduce

```
cd /home/nuke/Documents/Elektron-MODS/tools/digiemu
.venv/bin/python /home/nuke/Documents/Elektron-MODS-8-track-engine/tests/probe/cnv_midi.py --copies
.venv/bin/python .../cnv_midi.py --run r1 --out /tmp/opencode/cnv_m_r1.json
.venv/bin/python .../cnv_midi.py --run r2 --out /tmp/opencode/cnv_m_r2.json
.venv/bin/python .../cnv_midi.py --run r3a --out /tmp/opencode/cnv_m_r3a.json
.venv/bin/python .../cnv_midi.py --run r3b --out /tmp/opencode/cnv_m_r3b.json
.venv/bin/python .../cnv_midi.py --run r4 --out /tmp/opencode/cnv_m_r4.json
.venv/bin/python .../cnv_midi.py --run r5 --chan 0x41bf2a44,4 --out /tmp/opencode/cnv_m_r5.json
.venv/bin/python .../cnv_midi.py --compare r1 r2 r3a r3b --out cmp.json
```

## 9. Verdict table (for the orchestrator)

| assertion | result |
|---|---|
| 4.1 DIN byte-identity incl. flips | **PASS** (6 windows + 3 transitions, all empty-identical, clock 0) |
| 4.1 kit-tail identity | **PASS** (`ddba55cebc7550b0` ×7) |
| 4.1 mute round-trip + convert publishes | **PASS** |
| 4.2 set CHAN=5 | **FAIL (mechanical)** — turns dead 4/4 R5 sessions; display X |
| 4.2 converted emits on preserved channel | **BLOCKED** — zero DIN bytes observable (OUTPUT TO=USB) |
| 4.2 voice path unaffected | **PASS** (publish `0x43ec4cee` ×2 + render) |
| 4.2 MIDI side preserved across flip-back | **PASS** (storage: tail/kit164/mute/pattern identical) |
| 4.2 storage location | **PARTIAL** — excluded from 164 B/976 B; `0x41bf2a44` unconfirmed |
| code changes needed | **none** |
