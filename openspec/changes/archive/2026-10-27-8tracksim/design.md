# Design

## Context

tracks-dn1 today is a foreground swap: one live pattern struct (8 slots, 0–3 synth / 4–7 MIDI) and one live kit; Bank B lives in mirrors and never sounds (`trk_queue` observes but queues nothing — masked context, recursion risk, garbage note-builder). The stock sequencer steps only the live struct, and `mod.json` order-10 `ev_key` handling already owns `VOICE`/`FUNC`+`VOICE` chords. See proposal.md for why conversion replaces banks as the route to 8 simultaneous synth tracks.

## Goals / Non-Goals

**Goals:** any synth/MIDI mix up to 8+0 sounding together through the stock engine; lossless reversible conversion; Bank-A MIDI byte-identical behavior; all new behavior behind the existing release gates.

**Non-Goals:** Bank-B MIDI (dropped by omission); changing the 8-voice stealing behavior (stock rules apply); touching native synth track handling; reworking the bank swap (it stays as-is until conversion supersedes it, then it is removed — not maintained in parallel).

## Decisions

- **Conversion target is the live MIDI slot, not a struct merge.** A converted track keeps its slot (4–7) and pattern data in place; only its *type* flips. Alternative (copy trigs into spare slots) rejected: there are no spare slots, and moving data breaks the stash-restore symmetry.
- **Type mechanism decided by spike, in this order:** per-track type field (flip the field) → vtable/presenter swap (patch the track's page/render entry) → hardcoded `track<4` branches (enumerate and patch each site). Alternatives ordered by blast radius, smallest first.
- **Kit capacity via allocation extension, not overlay.** Sound records for converted tracks need live kit space past the 4-synth/4-MIDI layout; overlaying the MIDI-params region is rejected (provenance risk — cf. the +0x18/+0x2c window lesson). Exact bytes come from the spike.
- **Dual stash mirrors the bank-mirror discipline.** Per converted track: synth side (976B track data + 326B sound + mute) and MIDI side (976B + 164B params + mute); exactly one live. Persistence rides project data like `trk_save`.
- **Gesture is the `MIDI`+`VOICE` chord, mod-side only.** No stock chord exists there today (mod has no handler; stock collision verified in emu at implementation). Plain `VOICE` keeps opening the menu everywhere; native synth ignores the chord.
- **Module home decided after the spike.** If conversion is a type-field flip plus handlers, it lives in tracks-dn1; if it needs its own tables/pages, it is born as `modules/dn-<name>/` per `firmware-repo` rules. No new module until the spike reports size.

## Risks / Trade-offs

- [Track type is hardcoded in N scattered branches] → Spike enumerates all sites first; if N is large or includes DSP-side code, descope to fewer convertible tracks rather than patching blindly.
- [Kit extension overflows DDR/flavor minima] → Linker refuses over-budget builds by design; shrink stash (fewer convertible tracks) before touching minima.
- [8 synth tracks starve voices] → Stock stealing applies; no custom stealing in v1. Document expected stealing in release notes (verification spec requires the `Known issue:` line).
- [Conversion loses user data on crash mid-flip] → Flip under the same interrupt-mask discipline as `trk_swap_banks`; stash write completes before the live pointer/field flips.
- [MIDI+VOICE collides with stock on some OS page] → Emu check on every page context before shipping; fall back to hold-to-confirm or Mod-Menu entry.

## Migration Plan

New flavor definition (converter + core) in `tools/release.py`; first converter release links alongside but never replaces bank releases until B2-equivalent proofs (emu L1/L2 + user hardware audio) pass; bank swap code removed only after conversion supersedes it. Rollback is reflash of any prior release.

**Wrap-up note (2026-10-27, user-directed):** this change closed as a stepping stone for the next overhaul rather than shipping a release. The converter module (0.3) exists, builds, and passed lint, L1, and emu probes, but the flavor definition, first release, panel probes, and hardware audio verdicts were explicitly deferred to the overhaul (see tasks.md Stepping-stone wrap-up).

## Open Questions

- First-conversion synth content: fresh init sound vs copy of a template — answerable during implementation, default fresh init.
- Convert feedback: HUD toast (bank-HUD precedent) and/or track LED color — cosmetic, implementer picks.
- Bank toggle's new home once VOICE is the menu key again — deferred until conversion works; toggle stays until then.
- Stash persistence format details — follows `trk_save` precedent, finalized at implementation.

## Spike resolution (tasks 1.1–1.2, 2026-10-27; gates task 2.x)

Reports: `spike-track-type.md`, `spike-kit-capacity.md` (read-only;
`firmware/stock_main.bin` == digiemu section_3 image, 2,736,304 B,
load `0x40000400`).

- **Mechanism: branch patching (interposition), not field flip or
  vtable swap.** No per-track type field exists (`INIT_SEQ
  0x40015180` + `INIT_CONF 0x4001511c` run identically for all 8
  slots — no track-index-dependent byte) and there is no
  track-type vtable/presenter. Type is a hardcoded `track > 3 →
  MIDI` branch (`moveq #3,dx; cmp.l track,dx; blt → MIDI-side`) at
  each dispatch site. Site count: **2 confirmed audio sites**
  (first-step builder `0x40094d44`, step-fire loop `0x40095afa`;
  synth-fire `0x4009451e`, MIDI-fire `0x400948c0`) **+ ~6 probable
  UI sites** (voice-view presenter `0x4003df40`, `0x40043258`,
  `0x4003ca70`, label/menu `0x400bbd84`, `0x40061ce4`,
  param/page `0x40160968`) **+ 1 synth-only loop** (`0x400e31a2`
  iterates 0–3). Downstream code is pure index arithmetic
  (`track*976` pattern, `track*326` kit sounds at `kit+0x18`, MIDI
  params at `kit+0x5ce`, mutes at `+0x16108`) and needs no changes
  if dispatch routes converted tracks to the synth side.
- **Kit window:** synth records `kit+0x18..0x530` (slots at
  `+326t+0x2c`), MIDI params `kit+0x5CE..0x85E`, 158 B gap
  unusable. 4 extra sound records (1304 B) live in mod DDR `.bss`
  (≈287 KB spare on 0.11, flavor minima 150 KB / 1500 KB met);
  MIDI-params overlay rejected. Open follow-up for implementation:
  kit allocator site + live `kit+` write target past `0x85E`
  (cfisa pass before any live-kit write).
- **Module home: new `modules/dn-convert/`** (self-contained: own
  `mod.json`, compiled in place, per `firmware-repo` rules).
  Conversion is not a type-field flip plus handlers — it is
  per-site interposition, which outgrows the bank mod — and
  `tools/elekloader/mods/tracks-dn1/` cannot host it anyway: that
  tree is an untracked upstream clone (`git ls-files` empty;
  never `git add tools/`), so converter code would not be
  committable. `tracks-dn1` discipline (mirror stash,
  interrupt-masked flip, `TRK8` projdata) is reused as precedent,
  not as host. Phasing: audio path (S1+S2) first, UI sites after;
  bank swap stays until conversion supersedes it (Migration Plan
  unchanged).
