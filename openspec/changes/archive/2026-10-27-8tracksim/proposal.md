# Proposal

## Why

The tracks-dn1 bank mod (shipped through 0.10) gives two banks of tracks but only the foreground bank ever sounds: one live pattern struct, one live kit, background trigs sit in mirrors nothing plays. The goal — up to 8 synth tracks sounding together with the stock 8-voice engine — cannot be reached by swapping banks. Track-type conversion reaches it instead: turn MIDI slots into synth tracks and every slot in the single live pattern sounds through the normal engine, no swap involved.

## What Changes

- MIDI tracks 5–8 (slots 4–7) become convertible to synth tracks and back, each direction preserving the other side's data in a per-track stash (pattern data, sound/params, mute) with restore on flip-back.
- New gesture: `MIDI`+`VOICE` chord on a MIDI or converted track toggles its type; on native synth tracks (1–4) the chord does nothing and falls through to stock.
- Plain `VOICE` returns to opening the voice menu everywhere (bank toggle leaves the VOICE key; its new home is decided in design).
- Any mix from 4+4 to 8+0 synth/MIDI is supported; Bank-B MIDI is dropped (never built); Bank-A MIDI is untouched.
- Releases carrying conversion ship a new flavor definition (converter + core) through the existing release driver and gates.

## Capabilities

### New Capabilities

- `track-type-conversion`: converting a MIDI track to synth and back with lossless restore, the MIDI+VOICE gesture map, per-track dual stash, persistence across save/load, and player-facing release notes.

### Modified Capabilities

- None. `firmware-repo` (layout, flavors, registry) and `firmware-verification` (gates, boot proof, honest records) apply unchanged; conversion is verified through them, not around them.

## Impact

- `tools/elekloader/mods/tracks-dn1/` (converter logic, gesture handling, stash, UI feedback); possibly a new module under `modules/dn-<name>/` if the work outgrows the bank mod — decided in design.
- `tools/release.py`: new flavor definition for converter releases.
- `docs/`: player-facing gesture documentation; emulator + hardware verification as usual.
- Load-bearing unknown: how the firmware decides track type (per-track field vs vtable vs hardcoded branches) — the type-mechanism spike, task #1, answers this before any implementation.
