# Proposal

## Why

The repo init is done and old releases are frozen in `archive/`, but the work of building new releases has no defined path: a release driver, method doc, and smoke updates already exist on disk uncommitted and unowned by any change, the test gaps moved out of `init-firmware-repo` (build smoke, boot smoke, voice-budget reporting) have no home, and the first fresh release (8tracks 0.8) is waiting on a repeatable, verifiable process.

## What Changes

- Adopt the existing uncommitted scaffolding: `tools/release.py` (generic release driver: `--slug --num --tag --preset/--mod [--emu]`), `docs/RELEASE_METHOD.md` (the 6-step method), the dynamic-discovery `tests/smoke.ps1`, updated `docs/REPO.md` + `README.md` tree, and the archive moves.
- Extend `tools/release.py` into a constrained builder: per-flavor module sets (required/forbidden elemods), tag-collision refusal across active + archived releases, memory/flash budget assertions, and a release README stub that records output SHA-256, toolchain version, and a `## Verification` block (emu/hardware evidence kept separate, only actual results recorded).
- New-module source-of-truth: new ported modules are born as buildable mods in `modules/dn-<name>/` (the `dn-monomachine` pattern: own `mod.json`, compiled in place by `sdk.build`); `modules/digi*` stay read-only references; `firmware/elemods/` is a curated registry (index + local archive of stale versions).
- Verification loop (v1): L0 build gates (manifest constraints, auto-enforced), L1 boot proof (digiemu snapshot-oracle test with timeout + log fault grep), L3 hardware record (Verification block + checklist); L2 behavior tests (mute isolation, doubling, zombie voices, voice cap) gated on two investigation spikes — digiemu input injection and emulated-memory inspection.
- Fold in the researched best practices: exact-build qualification (deterministic hash + toolchain), evidence hierarchy (emulator evidence is emulator evidence, never timing/audio proof), release-notes `Known issue:` discipline, previous release stays available while a new one is pending.

## Capabilities

### New Capabilities
- `firmware-verification`: the build gates, emulator boot proof, behavior-test path, and hardware verification record that every release must pass before it counts as done.

### Modified Capabilities
- `firmware-repo`: adds release-workflow requirements — flavor-defined module sets, `modules/dn-*` as new-module source of truth, `firmware/elemods/` as curated registry, tag uniqueness across releases. (Delta uses ADDED requirements; requires `init-firmware-repo` to be archived first so the main spec exists.)

## Impact

- `tools/release.py`, `docs/RELEASE_METHOD.md`, `docs/REPO.md`, `README.md`, `tests/smoke.ps1`, new `tests/boot-check` script, `firmware/elemods/` index + local archive, two spike findings docs.
- No firmware logic changes; the tracks/voice fix stays a separate later change.
- First consumer: the `v1.44-8tracks-0.8` release built in a fresh conversation following `docs/RELEASE_METHOD.md`.
