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
The system SHALL provide one canonical folder per firmware version under `firmware/releases/` with README, `.syx`, and build manifest (`.syx.json` + `.map.json`).

#### Scenario: 8-track release is unambiguous
- **WHEN** a user opens `firmware/releases/`
- **THEN** `v1.44-8tracks-0.7/` is the single source for build 1447 and no `8 tracks - Copy*` duplicate remains in the main tree

### Requirement: Stock OS is pinned
The system SHALL document the stock `Digitone_and_Digitone_Keys_OS1.44.syx` SHA-256 pin and require elekloader builds to verify against it.

#### Scenario: Build uses correct stock
- **WHEN** a user builds via elekloader patch/build commands
- **THEN** the stock hash matches `d4f200d04484333d82822db7744e6484d0def8f2bc67b7752bd55ee2fb780cc13c9659` or the build stops with a hash error

### Requirement: Test entry points exist
The system SHALL provide a `tests/` folder with runnable smoke checks for stock boot, 8-track boot in digiemu, and voice-budget reporting.

#### Scenario: Contributor runs smoke tests
- **WHEN** a contributor runs the documented test command
- **THEN** stock boots, 8-track boots, and voice load is reported against the ~22k-tick headroom

### Requirement: Repo map documentation
The system SHALL provide `docs/REPO.md` mapping source (`tools/elekloader/mods/tracks-dn1/`), releases, build, and emulator test flow.

#### Scenario: New contributor onboards
- **WHEN** a new contributor reads `docs/REPO.md`
- **THEN** they can locate mod source, build a `.syx`, and boot it in digiemu without asking for paths
