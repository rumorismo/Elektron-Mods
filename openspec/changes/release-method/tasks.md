# Tasks

## 1. Adopt the existing scaffolding

- [x] 1.1 Commit the on-disk scaffolding (`tools/release.py`, `docs/RELEASE_METHOD.md`, dynamic `tests/smoke.ps1`, `docs/REPO.md`, `README.md` tree update, release archive moves) and verify `smoke.ps1` passes and `git status` shows no firmware tracked
- [x] 1.2 Add `docs/RELEASE_METHOD.md` verification section (pyramid, evidence hierarchy, hardware checklist from the research: simultaneous instances, track isolation, project persistence, reboot survival) and verify every command in the doc runs as written

## 2. Constrained release driver

- [x] 2.1 Add flavor definitions to `tools/release.py` (required/forbidden elemods per flavor, starting with `8tracks`) and verify a flavor-mismatch build refuses
- [x] 2.2 Add tag-collision scan across `firmware/releases/**` manifests (active + archive) and verify reusing tag `1447` refuses
- [x] 2.3 Add budget assertions (`ddr_spare`, `flash_headroom` minimums per flavor) and verification of `link.order`/`tables` counts from the written `.syx.json`, and verify an over-budget or wrong-set build refuses with measured values
- [x] 2.4 Extend the README stub with `## Verification` block (output SHA-256, WSL gcc version, `emu boot: untested <date>` / `hardware: untested`) and `Known issue:` release-notes line, and verify a dry build writes all of it

## 3. Boot proof (L1)

- [x] 3.1 Spike: validate the snapshot-oracle against stock OS 1.44 and the archived 8tracks-0.7 build (`--add`, timeout, confirm snapshot appears only after UI settles; check which log files carry fault output) and record findings in `docs/EMU_TESTING.md`
- [x] 3.2 Write `tests/boot-check.ps1` (add syx to digiemu, wait with timeout, assert snapshot dir, grep logs for fault strings) and verify it passes on stock and on 8tracks-0.7, and fails/times out on a deliberately truncated syx
- [x] 3.3 Wire boot-check into the documented release flow (RELEASE_METHOD step 3) and verify the doc's command sequence runs end-to-end against a real build

## 4. Behavior-test path (L2, spike-gated)

- [x] 4.1 Spike: investigate digiemu input injection (panel scripting, `emu/midi.py` MIDI-in path, headless runner) and record what is drivable in `docs/EMU_TESTING.md`
- [x] 4.2 Spike: investigate emulated-memory inspection for voice-state asserts (snapshot/checkpoint APIs vs the mod's `vs[]` addresses) and record feasibility in `docs/EMU_TESTING.md`
- [x] 4.3 Specify the four behavior tests (bank-toggle swap, mute isolation, no zombie voices after machine switch, voice-cap enforcement) as manual panel procedures in `docs/RELEASE_METHOD.md`, automated only to the extent the spikes allow, and verify each procedure is followable on the panel

## 5. Registry and docs

- [x] 5.1 Write the elemods index (`firmware/elemods/README.md`: elemod → source home, version) and move stale versions (tracks-1.0–1.3, non-`-os1.44` strays) to `firmware/elemods/archive/`, and verify the index lists every linkable file
- [x] 5.2 Update `docs/REPO.md` and `README.md` to point at the method and registry, and verify all referenced paths exist

## 6. Final validation

- [x] 6.1 Run smoke + boot-check green, `openspec validate release-method`, `git status` clean of firmware, and verify the change is ready for its first consumer (the 8tracks-0.8 build conversation)

## Workflow follow-up

- Archive `init-firmware-repo` BEFORE applying this change's firmware-repo delta (the main spec must exist first).
- After apply: archive this change, then start the `v1.44-8tracks-0.8` build in a fresh conversation following `docs/RELEASE_METHOD.md`.
