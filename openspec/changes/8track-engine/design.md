# Design: 8-track engine

## Context
`dn-convert` 0.3 = dual stash + immediate-toggle chord + HUD/LED + CNV8. Stepping-stone spikes proved: no per-track type field (INIT_SEQ `0x40015180` / INIT_CONF `0x4001511c` identical for all 8 slots), type = hardcoded `moveq #3; cmp.l track; blt → MIDI` at 2 confirmed audio sites + ~6 probable UI sites + 1 synth-only loop. Kit tail past `0x85E` is live preset table — no append. User decisions for this run: confirm-modal, b1..b4 labels, shared trigs, channel preserve, GUI-first probe.

## Goals / Non-Goals
Goals: any mix to 8+0 sounding through stock engine; converted = native synth except b-label; reversible via modal; Bank-A MIDI byte-identical; GUI-first verification with <60 s regression probe.
Non-Goals: stealing changes; bank-swap upkeep; hardware audio verdicts (recorded, not claimed).

## Decisions
- **Confirm-modal gesture (replaces 0.3 immediate toggle).** `MIDI`+`VOICE` on 4–7 opens centered YES/NO card ("CONVERT TO SYNTH?" / "RESTORE MIDI?"). YES runs the masked flip, NO/`NO` key/timeout (~2 s, bank-HUD tick discipline) cancels. Plain `VOICE` falls through to stock everywhere; chord on 0–3 falls through. Rationale: destructive flip deserves confirm; reuses `cnv_draw`/`cnv_tick` card geometry.
- **Shared trigs, split sound/params.** Live 976 B pattern stays in place on flip (no `live_trk` copy); only stash/load = 326 B synth sound ↔ 164 B MIDI params + mute byte `PAT_MUTES_OFFSET+track` + channel. First convert stages fresh init sound in `.bss` (default); later flips swap staged records. `KIT_LIVE_LIMIT 0x85E` guard stays: MIDI restore ends exactly at `0x85E`, synth records never touch live kit.
- **Audio = S1+S2+fetch.** Interpose S1 `0x40094d44` / S2 `0x40095afa` with `converted(t) ? synth : (t>3 ? midi : synth)`; interpose fetch inside synth-fire `0x4009451e` (one cfisa pass to find `kit+0x18+326t` load) to read `cnv_synth_snd[t-4]` + warm `ADDR_VOICE_SOUNDS 0x80003f5c`. S9 `0x400e31a2` verify-only (allocator clamp `0x400ea168` is 0–7 agnostic).
- **UI parity per site, smallest blast radius.** Browser (open + preset-apply redirect to `.bss`, identification pass first) → S3 `0x4003df40` + S4 `0x40043258` voice menu → S6 `0x400bbd84` / S7 `0x40061ce4` with custom `b1..b4` strings (not native `TRK.n`) → S8 `0x40160968` pages → S5 `0x4003ca70` classify. Each site proved (`compared reg = track`) before patching; browser-apply shares A3 fetch path if possible.
- **MIDI channel preserve.** Channel lives in MIDI params; converted synth keeps the slot's output channel (e.g. 5) for external MIDI out. Sequencer/mutes stay index-agnostic (`track*976`, `0x16108`, active-track clamp).
- **GUI-first verification.** Manual `dnpanel` resume covers modal/browser/menu/labels/pages/mute/sequencer (user). Headless keeps CNV8 ≤2 scan, MIDI byte-sink vs cached `tests/probe/baselines/`, framebuffer hash (screens as hash, raw only on fail); snapshot reuse (resume settled `dn1-<tag>-<hash8>`, rebuild on exit-3 only), single `Session` + project-reload reset, 1–2 bar captures, poll-until-stable settle.

## Risks / Trade-offs
- [Fetch site hunt fails inside `0x4009451e`] → ship S1/S2 only behind a flag, browser silent until fetch lands; never fake sounding.
- [Browser is 2+ sites with own kit-write] → split open-site vs apply-site into two probe-covered steps.
- [Modal collides with stock on some page] → emu check every page context (as with chord), fall back to hold-to-confirm.
- [Shared trigs surprise MIDI users] → documented in release notes; flip-back keeps same notes by design.
- [`b1..b4` strings need new UI bytes] → stash strings in mod `.rodata`, never live-kit writes.

## Migration Plan
`dn-convert` grows in place (no new module); bank swap stays until conversion supersedes it, then removed. New flavor in `tools/release.py`; first converter release links alongside but never replaces bank releases until B-equivalent proofs (emu L1/L2 + user hardware audio) pass. Rollback = reflash prior release.

## Open Questions
- Exact fetch load site(s) in `0x4009451e` (cfisa pass).
- Browser open + apply site addresses; does apply share the fetch path?
- S3/S4/S8 register proof; S5 fork classification.
- Modal YES/NO key codes + timeout length (implementer picks, emu-verified).
