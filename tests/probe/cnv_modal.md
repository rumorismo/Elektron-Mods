# convert 0.13 — modal + shared-trig proof (8track-engine tasks 2.1 + 2.2)

Date: 2026-10-28. Lane: implement modal + shared trigs in `dn-convert`
0.12 → 0.13, build → lint → link (new tag) → boot-settle → headless
single-Session 1–2 bar captures, <60 s/run. Evidence JSONs live OUTSIDE
the repo (scratch, no firmware, no baselines):
`/tmp/opencode/cnv_sweep_{a,b}.json`, `cnv_ctx_{a,b}.json`,
`cnv_browser.json`, `cnv_timeout.json`, `cnv_sharthash.json`,
`cnv_sustain.json`. Harness: `tests/probe/cnv_modal.py` (new, re-runnable).

## 0. Method note (read first)

The framebuffer proved too lively for hash-equality assertions: lit-pixel
counts swing across identical UI states (background animation/refresh
phase; see §7). The settled main screen itself is bit-stable, but any
transition needs poll-until-stable, and stock's MIDI-tap bank toggle
leaves history-dependent screens. So classification ground truth is
**mod RAM**, resolved once per boot by scanning mod RAM for the CNV8
projdata descriptor (`magic,size=0x2C,dataptr,fn` → `.run` base = fn −
0xAC) and the zero-neighboured CNV8 save magic (→ `.bss` base = addr −
0x0C):

- `MODAL_SLOT` (`.run+0xce4`): −1 = IDLE, else the pending slot
- `STATE[i]` (`.bss+0x44+4i`): 0 NATIVE / 1 SYNTH / 2 STASHED
- `POPUP` (`.bss+0x40`): toast ticks remaining

Offsets AC/CE4/0C/44/40 are convert-0.13 `.o` layout
(`m68k-linux-gnu-nm`; recompute after any rebuild). Boot asserts
`MODAL_SLOT == -1`. Framebuffer is supporting evidence only (card
presence/geometry, menu open/close as change-vs-base with settle polling).

Framebuffer geometry: 128×64 1 bpp (`panel.read`); card rect x16..112,
y18..46 — the bank-HUD geometry reused by the modal/toast.

## 1. Build

```
cd /home/nuke/Documents/Elektron-MODS/tools/elekloader && PYTHONPATH=. \
  python3 -m elekloader.sdk.build \
  /home/nuke/Documents/Elektron-MODS-8-track-engine/modules/dn-convert \
  --stock /home/nuke/Documents/Elektron-MODS/firmware/Digitone_and_Digitone_Keys_OS1.44.syx \
  --out /home/nuke/Documents/Elektron-MODS-8-track-engine/modules/dn-convert/out
```

```
BUILT .../modules/dn-convert/out/convert-0.13.elemod
  convert 0.13: .run 3428, .fast 0, .bss 2052 bytes; 3 sites, 141 relocations; imports fw_active_track, fw_fillrect, fw_font5, fw_kit, fw_memcpy, fw_memset, fw_pattern, fw_textf
```

Result: PASS. `.bss` 9856 → 2052 (both 976 B pattern stashes deleted —
the shared-trig flip never writes the live pattern). Rebuild at lane end
is byte-identical
(`sha256 925936f6…6c4d60a` both copies) — the tested `.syx` matches source.

mod.json: convert 0.13, same 3 sites (S1 `0x40094d44` 10 B,
S2 `0x40095afa` 6 B, F3 `0x40094832` 22 B).

## 2. Lint

```
python3 -m elekloader.lint .../out/convert-0.13.elemod \
  --stock .../Digitone_and_Digitone_Keys_OS1.44.syx \
  --with .../firmware/elemods/core-dn1-4.1.1-os1.44.elemod
```

```
OK: convert 0.13 (format 2) for Digitone mk1 1.44: 3 sites, ...
OK: links as core 4.1.1 > convert 0.13; RAM 12520 of 1310720 bytes, fast SRAM 0 of 0
```

Result: PASS.

## 3. Link (OUTSIDE tracked trees)

Tag check: release READMEs in both checkouts carry only `tag 1499`;
test syx on disk use 1464/1465/1466 → 1470 free.

```
python3 -m elekloader.patch --stock .../Digitone_and_Digitone_Keys_OS1.44.syx \
  --mod .../core-dn1-4.1.1-os1.44.elemod \
  --mod .../modules/dn-convert/out/convert-0.13.elemod \
  --out /home/nuke/Documents/Elektron-MODS/firmware/test-cnv13.syx --version 1470
```

```
linked core 4.1.1, convert 0.13: RAM 0x43ec0000-0x43ec30e8 (1298200 bytes spare), ...
WROTE /home/nuke/Documents/Elektron-MODS/firmware/test-cnv13.syx
  sha256 bd6df8649424d94e422df054452f3fe38d1382386250047601609d7f9128536d, version 1470, 1715360 bytes
```

Result: PASS.

## 4. Boot

```
cd /home/nuke/Documents/Elektron-MODS/tools/digiemu && .venv/bin/python \
  -m emu.portable --add /home/nuke/Documents/Elektron-MODS/firmware/test-cnv13.syx --yes
```

Result: PASS — persistent snapshot `dn1-1470-bd6df864`, SETTLED at
1200 M (120 consecutive main-UI frames, no overlay), settle 27 s.
All legs below boot ONE Session from this snapshot.

## 5. Design deltas (what changed in convert.c)

- **Modal state machine** (`cnv_key`/`cnv_tick`/`cnv_draw`): `cnv_modal_slot`
  (−1 IDLE, else pending slot) + `cnv_modal_ticks` (60 ≈ 2 s at the
  measured ~30 Hz `ev_tick`; timeout measured 2000 ms, §8). MIDI+VOICE on
  slots 4–7 opens the card and swallows (return 1 — stock never sees the
  chord). YES (down) while open runs the masked flip for the modal slot
  and swallows; NO (down) while open cancels with zero state change and
  swallows; re-chord (MIDI-held VOICE) while open refreshes the timer on
  the same slot and swallows; plain VOICE while open is swallowed to
  protect the card. After cancel/timeout the state is IDLE so plain VOICE
  falls through and the stock menu opens. Chord on 0–3 falls through
  (stock proceeds). Releases always fall through.
- **YES/NO key ids**: 13 / 14 — sourced from the sibling tree
  (`digireel-dn1/pedal_ui.inc` `KEY_YES 13` / `KEY_NO 14`,
  `fxkit-dn1/fxkit.c` same, Digitone panel-toml RECORD/STOP/YES/NO =
  10/12/13/14 order) and **proven behaviorally** by the §6 sweep (only
  panel code 13 flips, only 14 cancels, of codes 1–25).
- **Shared-trig flip** (`cnv_to_synth`/`cnv_to_midi`): the live 976 B
  pattern is NEVER written — no `live_trk` memcpy either direction.
  `to_synth`: stash 164 B kit params + MIDI mute → `.bss`; live writes =
  pattern mute byte + audio-mute hw mask + setter + voice-cache/flag
  staging only. First convert stages the kit slot-0 326 B timbre into
  `.bss` (proven sounding); later flips reuse the staged record.
  `to_midi`: stash synth mute; restore 164 B params byte-identical
  (memcpy of provably identical bytes — the live region is never written
  while synth-live); mute byte + MIDI-mute hw mask + setter; voice regs.
  `CNV_MASKED_BEGIN/END` discipline kept; CNV8 projdata in sync
  (`cnv_sync_save` unchanged; STASHED = 2 after flip-back, by design).
- **Channel preserve**: the flip write-set excludes all param storage,
  so the MIDI channel byte — wherever stock keeps it inside the preserved
  164 B/976 B regions — is untouched by construction; the live 164 B hash
  is constant across convert + flip-back (§9). (Byte offset not isolated:
  factory slots 4–7 carry byte-identical 164 B records
  `daec2574…`, so no differential read is possible without a UI channel
  change; task 4.2 will prove the external-MIDI-output half.)
- Draw: modal card reuses the 96×28 bank-HUD geometry with
  `CONVERT TO SYNTH?` / `RESTORE MIDI?` + `YES FLIP  NO KEEP`; toast and
  LED behaviour unchanged.
- Y-stage source note: factory byte 972 reads 0 on all 8 tracks (read-only
  probe on the 0.12 snapshot), so the shared-live Y-stage is the native 0.

## 6. YES/NO key discovery — sweep panel codes 1–25 (RAM verdicts)

`sweep` legs: fresh modal per candidate (`--codes 1-13`, `--codes 14-25`).
Outcome-verified chord with retries (see §7), press candidate, poll RAM:
`slot==0` → held-open; `slot==-1,state==1` → flip (then parked back via a
fresh modal + YES, lands STASHED=2); `slot==-1,state unchanged` →
cancel. Wall 19.4 s + 15.9 s.

| codes | verdict |
|---|---|
| 13 (YES) | **flip** (0→SYNTH, parked back →STASHED); only flip-class key |
| 14 (NO) | **cancel** (state untouched); only cancel-class key |
| 1–12, 15–25 (FUNC, MIDI, KEYBOARD, PTN, BANK, SONG, GLOBAL, VOICE, TEMPO, RECORD, PLAY, STOP, UP, DOWN, LEFT, RIGHT, PAGE, TRIG, SYN1, SYN2, FLTR, AMP, LFO) | **held-open** — modal stays, zero state change |

No NO-MODAL, no UNEXPECTED in any trial. Raw `#13`/`#14` and the `YES`/`NO`
labels are equivalent (sweep uses raw codes; §§8–10 use labels) — raw panel
code == firmware key id for these keys.

## 7. Emu input-timing caveat (why everything is outcome-verified)

15–30 ms key presses intermittently miss the firmware key scan depending
on UI-task phase (plain-VOICE hold=30 opens the menu only sometimes;
hold=100 + retry-until-fb-change is reliable). The MIDI+VOICE chord races
stock's MIDI-press bank retarget (active reads 4 or 0 during the hold in
strict alternation at fixed 50 ms holds), so `open_modal` re-ensures
active=4 and retries up to 4× with RAM polling — the 0.11 precedent
(`cnv_captures` chord retries). Human-held chords do not see this
aliasing; no firmware change. Same flake class: short RECORD presses miss
grid-rec → `sharthash` uses fb-verified RECORD + struct-verified step
toggles. NO-press cleanup uses hold=100 + slot poll.

## 8. Timeout + re-chord micro-probes

`timeout` leg (wall 8.7 s): modal opens (RAM) → first `slot==-1` poll at
**2000 ms** → `in_window_1200_3000` PASS, `zero_state_change`
(state==0) PASS → post-timeout plain VOICE opens the stock menu PASS
(retry helper).
Re-chord probe (`/tmp/opencode/rechord.py`, console): with MIDI held,
VOICE re-press refreshes the timer 30 → 59 ticks on the same slot with
state untouched → RECHORD-REFRESH PASS; cancel after PASS.

## 9. Shared-trig proof — `sharthash` leg (wall 10.9 s)

Verified programming (two grid steps toggled with struct-bit checks, so
the pattern differs from factory `581a47b1…` → `04ab7d0b…`), convert via
modal YES, flip back via YES on the RESTORE card:

- `program_changed_pat` True, `yes_flipped` True (slot −1, state 1),
  `yes_restored` True (slot −1, state 2 = STASHED)
- 976 B live pattern hash identical pre-convert / post-convert /
  post-flip-back: PASS (`conv_pat_same`, `back_pat_same`)
- 164 B kit params: live region hash constant across the flip;
  post-flip-back bytes identical to pre-convert: PASS
  (`conv_prm_live_same`, `back_prm_identical`, `prm_sha daec2574…`)
- kit tail `5CE..85E` (`ddba55ce…`) + pattern mute byte identical
  throughout: PASS (`back_tail_same`, `back_mute_same`)
- Mute semantics unchanged: same audio/MIDI hw-mask registers + setters,
  same pattern-mute-byte convention (code review + `back_mute_same`).

## 10. Sounding still works + native 0–3 untouched — `sustain` leg

Adapted `sustain_probe` shape (YES-confirm; conversion verified by F3
publish, not struct diff — the pattern no longer changes). Programs
tracks 0–3 + converted 4, PLAY ~4 s emu, voices-buffer energy series.
Wall 56.9 s (audio 8× cost; play 34.7 s).

- Converted slot-4 fires publish `0x43EC2BD0` (inside mod RAM
  `0x43EC0000–0x43EC30E8`; layout moved vs 0.12's `0x43EC394C` since
  `.bss` shrank): 6/6 hits, PASS
- `.bss` sound record nonzero = 101/326 (kit slot-0 timbre staged): PASS
- Voices render energy with t4 live: series max 58 M (all 8 samples >2 M):
  PASS. Overall `pass: true`. Audio verdict stays hw-pending per hierarchy.
- Native 0–3 F3 fetch parity: `0x413062ac`, `0x413063f2`, `0x41306538`,
  `0x4130667e` — each exactly `kit+0x18+326t`, bit-identical: PASS
  (`native_fetch_parity: true`).
- Observation (not a regression): pattern-mute-byte pokes for tracks 0–3
  pre-play did not suppress S1/S2 fires in emu (t0:13, t3:13 fires) —
  stock mute-path timing, outside this lane (mute UI is 3.x; flip uses the
  same hw-mask setters as 0.12).

## 11. Page contexts — `contexts` + `browser` legs

`contexts a` (main, voice-menu, global-settings; 48.7 s) + `contexts b`
(midi-bank, ptn-menu; 27.7 s). Per context (RAM gates):

- chord on slot 4 opens the modal (swallowed): PASS all 5
- NO cancels to IDLE with zero conversion-state change: PASS all 5
  (post-cancel ACTIVE/screen = stock's own MIDI-release bank toggle —
  post-cancel fb is bit-identical to a lone MIDI tap from the same bank,
  `ae6f27a8…`; the VOICE half of the chord is fully swallowed)
- chord on slot 0: no modal (falls through): PASS all 5 (ACTIVE ends 4 via
  stock's release toggle; its fb delta vs a lone tap is stock's own
  MIDI+VOICE handling on a synth track — no mod state change: slot −1,
  state untouched)
- plain VOICE opens the stock menu (retry helper): PASS all 5
- chord → NO → VOICE still opens the stock menu: PASS all 5
  (menu-fb identity vs the plain-VOICE menu varies with bank history on
  some pages — stock UI memory, not gated)

Card pixels: `modal_card_differs` True all 5; diff box exactly
`[16,17,112,45]` (≈ card rect) on the voice-menu and ptn-menu runs;
full-screen elsewhere is the stock bank-toggle background shifting behind
the static card (midi-bank, where no bank change occurs, likewise shows
card-region diffs).
`browser` leg (14.9 s): double-T1 page, BANK page, SONG page all show a
changed screen on which the modal opens (RAM) and cancels to IDLE — PASS;
FUNC+T1 changes nothing. Whether the double-T1 page IS the sound browser
is task 3.1's call (manual follow-up); the MIDI CONFIG submenu was not
reached headless (manual follow-up). No context swallowed vs fell through
differently: the gesture behaves identically on every probed page.

## 12. Verdict table

| # | assertion | verdict | evidence |
|---|---|---|---|
| a | modal opens/cancels/flips per spec on all probed page contexts | PASS | §§6, 8, 11; `cnv_ctx_{a,b}.json`, `cnv_timeout.json` |
| b | 976 B pattern hash identical across convert + flip-back | PASS | §9 `cnv_sharthash.json` |
| c | MIDI params restored byte-identical | PASS | §9 `cnv_sharthash.json` |
| d | sounding still works post-change | PASS (emu; hw-pending) | §10 `cnv_sustain.json` |
| e | native 0–3 untouched | PASS (pattern/kit/fb + F3 fetch) | §§10–11 `cnv_sustain.json` |
| — | YES=13 / NO=14 discovered, not guessed | PASS | §6 `cnv_sweep_{a,b}.json` |
| — | 2nd plain VOICE opens stock menu after cancel | PASS | §§8, 11 |
| — | re-chord refreshes, chord swallowed while open | PASS | §8 |
| — | channel preserved (region proof) | PASS (constructional) | §5 + §9 |

BLOCKED: none. Nothing was parked — the YES/NO discovery the task
allowed to block on succeeded behaviorally.

## 13. Files changed (this lane; `tasks.md` untouched per instructions)

- `modules/dn-convert/convert.c`: modal state machine (`cnv_key`,
  `cnv_tick`, `cnv_draw`), shared-trig flips, −8 KB pattern stashes
- `modules/dn-convert/mod.json`: 0.12 → 0.13 (+description)
- `modules/dn-convert/out/convert-0.13.elemod`: built artifact
  (`sha256 925936f6…6c4d60a`)
- `tests/probe/cnv_modal.py`: this lane's harness (new)
- `tests/probe/cnv_modal.md`: this file (new)

No firmware committed (all `.syx` under sibling `firmware/` + `/tmp`);
no stock widening; no `tools/` changes.

## 14. Build / snapshot ids

- elemod `convert 0.13` (`.run 3428, .bss 2052`, 3 sites, 141 relocs)
- `.syx` `test-cnv13.syx` tag **1470** `sha256 bd6df864…9128536d`
- snapshot **`dn1-1470-bd6df864`** (SETTLED 1200 M, settle 27 s)
- core 4.1.1 unchanged; RAM 12520/1310720 B
