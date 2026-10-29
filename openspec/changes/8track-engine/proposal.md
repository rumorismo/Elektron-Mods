# Proposal: 8-track engine (full converter parity)

## Why
The 8tracksim stepping stone proved conversion is a per-site `track>3` branch patch with a `.bss` stash, but converted slots don't sound yet and have no synth UI. Players want up to 8 synth tracks that behave like native: sound, sequence, mute, browse sounds, edit synth params — with a safe gesture and the MIDI channel they already configured.

## What Changes
- `MIDI`+`VOICE` on slots 4–7 opens a YES/NO modal ("convert to synth/midi?"). YES flips, NO/timeout cancels. Plain `VOICE` still opens the voice menu everywhere. Chord on slots 0–3 is a no-op for stock.
- Converted slots behave like native synth: trig dispatch through synth-fire, sound fetch from mod `.bss` + voice-cache warm, sequencer/mutes, double-click sound browser, voice menu, synth param pages, b1..b4 labels.
- Shared trigs: one 976 B pattern per slot shared by both sides; only engine routing + sound/params flip. MIDI channel configured pre-convert is preserved and the converted synth outputs on that channel.
- Labels show `b1..b4` top-left for converted slots (intentionally distinct, not native `TRK.n`).
- Probe strategy goes GUI-first: user covers browser/menu/labels/mute/sequencer by hand in `dnpanel` (run `cd tools/digiemu && .venv/bin/python -m emu.dnpanel portable/firmware/<slug>`); headless probe shrinks to regression-only (CNV8, MIDI byte-identity vs a freshly captured stock MIDI-byte log, framebuffer hash) with snapshot reuse + single session + minimal windows (<60 s target).

## Capabilities
### New Capabilities
- None (extends `track-type-conversion`).

### Modified Capabilities
- `track-type-conversion`: confirm-modal gesture, full synth parity (audio/browser/menu/labels/pages), shared-trig stash, MIDI-channel preserve, b1..b4 labels.
- `firmware-verification`: GUI-first L2 for converter parity + regression-only headless probe (snapshot reuse, freshly captured stock baselines).

## Impact
- `modules/dn-convert/` (converter 0.11 → full parity: browser sites, S3/S4, S6/S7 b-labels, S8, S5 classify, S9 verify, modal UI, shared-trig flip, channel preserve — S1/S2/F3 + fetch interpose + allocator staging already landed; voice sustain still open).
- `tools/release.py`: converter flavor + first release (carried from stepping stone 4.1).
- `docs/`: `EMU_TESTING.md` (regression-only harness contract), `EMULATOR_WORKFLOW.md` (resume + manual panel flow), `RELEASE_METHOD.md` L2 (converter B-procedures replace bank B1–B4 for this line).
- Load-bearing unknowns: exact fetch load site inside `0x4009451e`; browser open/apply sites (unenumerated); S3/S4/S8 register proof (`d4`/`d2`/`d0` = track).

## Out of scope
- Bank-swap maintenance (removed once conversion supersedes it, never in parallel).
- Voice-stealing changes (stock 8-voice rules unchanged).
- Hardware audio verdicts in this change (stay `hw-pending`, recorded in release README).
