# Tasks

## 1. Type-mechanism spike (read-only, no implementation)

- [x] 1.1 Enumerate how the firmware decides track type by tracing synth vs MIDI track paths in the 1.44 image with digiemu cfisa, verify a written report names each decision site as per-track field, vtable/presenter, or hardcoded branch with addresses
- [x] 1.2 Map live kit capacity for 8 sound records by locating the kit allocation, synth slots, and MIDI params region, verify the report gives exact offsets and the collision-free extension window in bytes
- [x] 1.3 Record the mechanism verdict (field flip vs vtable swap vs branch patching, with site count) plus module-home recommendation (tracks-dn1 vs new modules/dn-<name>), verify the verdict is written into design.md Open Questions resolution before any code task starts

## 2. Converter core

- [x] 2.1 Implement per-track dual stash (synth side 976B+326B+mute, MIDI side 976B+164B+mute) with interrupt-masked flip, verify WSL build succeeds and elekloader lint ok true with stock syx
- [x] 2.2 Implement the MIDI+VOICE chord (act on MIDI/converted tracks, ignore native synth, plain VOICE still opens menu), verify emu key-probe shows convert on MIDI, flip-back with restore, and no-op on synth tracks
- [x] 2.3 Extend the live kit allocation for converted sound records per the spike window, verify link succeeds with DDR/flash spares above flavor minima and no overlay of the MIDI params region

## 3. Feedback and coexistence

- [x] 3.1 Add convert/flip-back player feedback (HUD toast following the bank-HUD precedent, track LED state), verify OLED snaps show convert and restore announcements
- [x] 3.2 Prove Bank-A MIDI byte-identical behavior with conversions active (MIDI output compare before/after across flips), verify emu MIDI-byte log matches stock
- [ ] 3.3 Prove converted tracks sound with native tracks under voice pressure (8 trigs at once), verify emu voice-remap evidence and record expected stock stealing as a Known issue line

## 4. Release and prove

- [ ] 4.1 Add the converter flavor definition to tools/release.py and link the first 8tracksim release, verify syx plus json plus map plus README exist with a fresh tag
- [ ] 4.2 Pass L1 boot-check and L2 convert/flip/mute panel probes on the release, verify emu-only results with concrete values are written in the README Verification block and audio verdicts stay hw-pending
- [ ] 4.3 Run tests/smoke.ps1 green and flash hardware for the audio verdicts (mute behavior, mix, stealing audibility), verify hardware lines in the README record actual results with a date

## Workflow follow-up

- Archive the change after review and hardware verdicts decide the release is done.
- Remove the bank-swap path only after conversion supersedes it; never maintain both paths in one release.
- Open Questions carried with defaults: first-conversion sound = fresh init; feedback visuals = implementer picks; bank toggle home = deferred (toggle stays until conversion works); stash persistence = trk_save precedent.

## Stepping-stone wrap-up (2026-10-27, user-directed)

At the user's direction, the remaining tasks are explicitly deferred to the next overhaul (the synth-parity work planned in the `8-track-engine` worktree) rather than silently dropped:

- 3.3 (voice pressure proof): deferred. The user opted to cover sounding behavior by hand via the GUI/hardware rather than an emu probe; the stock-stealing expectation stands as documented in design Risks.
- 4.1 (converter flavor + first release): deferred at the user's choice. The convert 0.3 module exists and passed build, lint, L1, and emu probes, but no converter release has been linked; the overhaul's first release carries this.
- 4.2 (L1/L2 on the release) and 4.3 (smoke + hardware audio verdicts): deferred with 4.1, since no release exists to verify.

Nothing above was silently narrowed: the converter module exists, builds, and passed lint, L1, and emu probes; only the release packaging and hardware/panel verification remain outstanding and carry into the next overhaul.
