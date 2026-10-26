# firmware-repo Specification

## Purpose
Provide a clean, reproducible home for all Digitone MK1 firmware modifications, releases, and tests so builds and voice issues can be reproduced without binary clutter.

## Requirements

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
- **THEN** the stock hash matches `d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659` or the build stops with a hash error

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

### Requirement: Releases are built from flavor definitions
The release method SHALL define each release flavor as an explicit module set (which elemods it requires and forbids), and the release driver SHALL build a release only from a flavor definition or an explicitly named module list.

#### Scenario: Building a flavor
- **WHEN** the user builds the 8tracks flavor at iteration 0.8
- **THEN** the driver links exactly the flavor's module set and writes `firmware/releases/v1.44-8tracks-0.8/`

### Requirement: New modules are born in modules/dn
A newly ported or written module SHALL live as a self-contained buildable mod in `modules/dn-<name>/` (its own `mod.json` and sources, compiled in place), while reference and upstream collections under `modules/` stay read-only and are never edited.

#### Scenario: Porting a Digitakt module
- **WHEN** the user ports a module from a reference collection
- **THEN** the work happens in a new `modules/dn-<name>/` directory and the reference stays untouched

#### Scenario: Building a modules/dn mod
- **WHEN** a `modules/dn-<name>/` mod is compiled
- **THEN** `sdk.build` is pointed at that directory and the produced `.elemod` is copied into `firmware/elemods/`

### Requirement: firmware/elemods is a curated registry
`firmware/elemods/` SHALL hold only the current version of each module the release method links, documented by an index mapping each `.elemod` to its source home and version; superseded versions move to a local `firmware/elemods/archive/` that is never linked.

#### Scenario: Registry is navigable
- **WHEN** a contributor opens the elemods index
- **THEN** every `.elemod` present is listed with its source directory and version

#### Scenario: Stale versions are not linkable
- **WHEN** a module is superseded by a newer version
- **THEN** the old `.elemod` is not in the linkable registry directory
