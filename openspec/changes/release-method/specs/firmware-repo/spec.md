# Spec Delta

## ADDED Requirements

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
