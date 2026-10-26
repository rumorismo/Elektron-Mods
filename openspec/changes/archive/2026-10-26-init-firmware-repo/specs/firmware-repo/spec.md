# Spec Delta

## Purpose

Provide a clean, reproducible home for all Digitone MK1 firmware modifications, releases, and tests so builds and voice issues can be reproduced without binary clutter.

## ADDED Requirements

### Requirement: Firmware binaries are excluded from git
The system SHALL ignore Elektron derived binaries via root `.gitignore` so clones contain only source, docs, and pins.

#### Scenario: Fresh clone has no binaries
- **WHEN** a user clones the repo and lists tracked files
- **THEN** no `*.syx`, `*.bin`, `*.elemod`, or `*.map.json` is tracked except the pinned stock OS reference documented in docs

### Requirement: Canonical release layout
The system SHALL provide one folder per firmware release under `firmware/releases/v1.44-<slug>-0.<N>/` with README, `.syx`, and build manifest (`.syx.json` + `.map.json`), and SHALL keep every superseded release in `firmware/releases/archive/` unchanged.

#### Scenario: Release tree is unambiguous
- **WHEN** a user opens `firmware/releases/`
- **THEN** every folder except `archive/` is an active release created by the release driver, and no duplicate or copy-named folder exists outside `archive/`

#### Scenario: Archive is frozen
- **WHEN** a release is superseded by a newer one
- **THEN** the old folder moves to `archive/` and is never rebuilt or edited

### Requirement: Stock OS is pinned
The system SHALL document the stock `Digitone_and_Digitone_Keys_OS1.44.syx` SHA-256 pin and require elekloader builds to verify against it.

#### Scenario: Build uses correct stock
- **WHEN** a user builds via elekloader patch/build commands
- **THEN** the stock hash matches `d4f200d04484333d82822db7744e6484d0def8f2bc67b7752bd55ee2fb780cc13c9659` or the build stops with a hash error

### Requirement: Test entry points exist
The system SHALL provide a `tests/` folder with runnable smoke checks for repo and release integrity, and a documented way to try firmware in the emulator.

#### Scenario: Contributor runs smoke tests
- **WHEN** a contributor runs `tests/smoke.ps1`
- **THEN** stock hash, active-release manifests and READMEs, launcher snapshots, git cleanliness (no firmware tracked), and the WSL toolchain are all verified

#### Scenario: Contributor tries firmware in the emulator
- **WHEN** a contributor follows the documented emulator flow (`docs/EMULATOR_WORKFLOW.md`, `run-*.bat`)
- **THEN** the release boots in digiemu without manual path setup

### Requirement: Repo map documentation
The system SHALL provide `docs/REPO.md` mapping source (`tools/elekloader/mods/tracks-dn1/`), releases, build, and emulator test flow.

#### Scenario: New contributor onboards
- **WHEN** a new contributor reads `docs/REPO.md`
- **THEN** they can locate mod source, build a `.syx`, and boot it in digiemu without asking for paths
