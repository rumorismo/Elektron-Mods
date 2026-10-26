# Design

## Context

`init-firmware-repo` delivered the repo (live on GitHub, docs reconciled, smoke green) and archived all pre-existing releases; its remaining test tasks moved here. Uncommitted scaffolding already on disk: `tools/release.py`, `docs/RELEASE_METHOD.md`, dynamic `tests/smoke.ps1`, `docs/REPO.md` + `README.md` layout updates, archive moves. Research (Modwerk `DEVELOPER_WORKFLOW.md`, `modwerk.app/submit`, elekloader `docs/BUILDING.md`, elektronmods forum threads 20/30) confirms the verification pyramid and adds: exact-build qualification, evidence hierarchy, isolation checklists, known-issue release notes. `modules/dn-monomachine/` proves a mod can be self-contained and buildable outside the elekloader clone.

## Goals / Non-Goals

**Goals:**
- A release process a fresh conversation can follow end-to-end: flavor-defined build with enforced gates, boot proof, honest verification record, emulator try, commit.
- New modules ported as first-class `modules/dn-*` mods, built in place.
- Verification v1 automated: L0 gates + L1 boot proof; L2 spike-gated; L3 manual-and-recorded.

**Non-Goals:**
- No firmware logic changes (tracks/voice fix is a later change).
- No L2 automation before the spikes say it is possible.
- No Modwerk/elekloader submission, no upstream PRs.

## Decisions

- **release.py as the single driver** (not per-flavor scripts): `--slug --num --tag --preset|--mod [--emu]`. Flavor definitions live in the script as presets; constraints are enforced in code (refusal, not convention). Alternative — keeping `build_8tracks.py` and adding siblings — rejected: N scripts diverge, one driver with data cannot.
- **modules/dn-* as source of truth for new modules**: `dn-monomachine` pattern (own `mod.json`, compiled by pointing `sdk.build` at the directory — the tool takes any path). `tools/elekloader/mods/` remains for the framework mods that ship with elekloader (core, machines, tracks, pedals); `modules/digi*` are read-only references. Copy into `firmware/elemods/` after compiling.
- **Tag uniqueness by scan, not ledger**: on build, scan `firmware/releases/**` (active + archive) manifests for the tag and refuse collisions. No separate file to maintain; the manifests are already the record.
- **Verification pyramid v1 = L0 + L1 + record**: L0 reads the `.syx.json` manifest (stock pin, link order, version, `ddr_spare`, `flash_headroom`, `tables` entry counts) plus elekloader's own enforced guarantees (bootloader byte-for-byte stock, checksums, unpack simulation — BUILDING.md). L1 uses the snapshot-oracle: digiemu writes the snapshot only after the factory UI settles, so snapshot-within-timeout + no fault strings in logs = boot proof. L2 (behavior) is specified but spike-gated. L3 is the user on hardware with the digihealth meters; results land in the `## Verification` block.
- **Evidence hierarchy adopted from Modwerk**: an emulator run proves the code paths it exercised, never audio, timing, saved-project survival, or physical reboot. Emulator evidence is labeled emulator evidence; hardware lines stay `untested` until actually tested on the unit. "Record only actual results."
- **Exact-build qualification**: README stub records output SHA-256 (manifest already does) + WSL gcc version; a rebuild can be checked identical. Mirrors Modwerk's pinned-toolchain rebuild requirement at our scale.
- **elemods curated**: index maps elemod → source home + version; stale versions (tracks-1.0–1.3, non-`-os1.44` strays) move to `firmware/elemods/archive/` locally. Binaries are untracked, so this is registry hygiene for the driver's link-by-filename contract.

## Risks / Trade-offs

- [L2 may not be automatable] digiemu's panel may have no scriptable input → Mitigation: spikes first (input injection via `emu/midi.py` or panel hooks; memory inspection for voice-state asserts); until then behavior checks stay manual and the spec says so.
- [Emulator false signals] emu audio dropouts are a known emu-side artifact (forum thread 20) → Mitigation: L1 greps logs for firmware faults only; no audio-quality judgment ever runs on emu.
- [Snapshot-oracle assumption] if digiemu writes snapshots even on a half-booted firmware, L1 weakens → Mitigation: spike validates the oracle against stock + a known-good archived build before trusting it in CI.
- [release.py grows toward a build system] → Mitigation: keep it stdlib-only, one file, data-driven presets; anything smarter belongs upstream in elekloader.

## Migration Plan

1. Commit the existing scaffolding as-is (it already matches this design).
2. Add gates to release.py (flavor definitions, tag scan, budget asserts, Verification + toolchain in stub).
3. Add `tests/boot-check` (snapshot oracle + log grep), validate on stock and an archived known-good build.
4. Elemods index + archive; docs final; smoke green; validate.
5. First consumer: build `v1.44-8tracks-0.8` in a fresh conversation following `docs/RELEASE_METHOD.md`.
Rollback: scaffolding is additive; `git revert` restores any step.

## Open Questions

- None blocking. Spike outcomes decide L2 timing only, and v1 ships without L2 by design.
