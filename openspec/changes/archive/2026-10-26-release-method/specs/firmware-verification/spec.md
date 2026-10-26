# Spec Delta

## Purpose

Defines what every firmware release must pass before it counts as done: enforced build gates, an emulator boot proof, a path to behavior tests, and an honest hardware verification record.

## ADDED Requirements

### Requirement: Build gates refuse bad releases
The release driver SHALL verify, before writing a release: the stock OS hash matches the documented pin; the linked module set matches the release flavor's definition (required modules present, forbidden modules absent); the version tag is not already used by any active or archived release; and the linked image's memory and flash spare meet the flavor's minimums.

#### Scenario: Wrong stock is refused
- **WHEN** the stock `.syx` hash does not match the pin
- **THEN** the build stops with a hash error and no release folder is written

#### Scenario: Flavor mismatch is refused
- **WHEN** a flavor forbids a module (e.g. the pure-synth flavor without FX) and it appears in the link, or a required module is missing
- **THEN** the build stops naming the violation

#### Scenario: Tag collision is refused
- **WHEN** the requested version tag already exists in any release folder, including `archive/`
- **THEN** the build stops listing the existing holder of the tag

#### Scenario: Over-budget build is refused
- **WHEN** the linked image's DDR spare or flash headroom is below the flavor's minimum
- **THEN** the build stops reporting the measured values against the minimums

### Requirement: Every release boots in the emulator before it is done
A release SHALL pass an automated boot proof: the release `.syx` is added to digiemu, and within a timeout the firmware snapshot appears (the emulator only writes it after the factory UI settles) and the emulator logs contain no fault strings.

#### Scenario: Good release passes boot proof
- **WHEN** the boot check runs against a known-good release
- **THEN** the snapshot appears within the timeout and the check reports pass

#### Scenario: Crashing firmware fails boot proof
- **WHEN** the firmware hangs or faults before the UI settles
- **THEN** no snapshot appears within the timeout and the check reports fail with the timeout and any fault lines found

### Requirement: Release record states only actual results
Every release README SHALL carry a `## Verification` block recording the output SHA-256, the toolchain that built it, and separate lines for emulator and hardware evidence, each stating only what was actually tested with a date, or `untested`.

#### Scenario: Fresh release is honest about what is unverified
- **WHEN** a release is built but not yet tried
- **THEN** its Verification block shows the build facts and `untested` for both evidence lines

#### Scenario: Emulator evidence never claims hardware proof
- **WHEN** a release passed the boot proof and panel checks in digiemu
- **THEN** its Verification block records that as emulator evidence with a date, and the hardware line stays `untested` until the user tests on the unit

### Requirement: Behavior tests target logic, not timing
Behavior verification (bank-toggle swapping, mute isolation between banks, no zombie voices after a machine switch, voice-cap enforcement) SHALL be specified as logic assertions, with the understanding that digiemu proves exercised code paths and never audio, timing, or physical-reboot behavior; the cracking verdict always requires hardware.

#### Scenario: Emulator behavior results are labeled
- **WHEN** a behavior test passes in digiemu
- **THEN** it is recorded as emulator evidence and the hardware verdict remains open

#### Scenario: Behavior automation is spike-gated
- **WHEN** the input-injection and memory-inspection spikes have not found a drivable path
- **THEN** behavior checks run manually via the panel and the spike findings say so

### Requirement: Release notes carry known issues for players
Every release SHALL include release notes written for players, at most a few lines per change, with a `Known issue:` line for any limit a player needs to know (e.g. the 1-voice cap).

#### Scenario: Player reads what changed
- **WHEN** a player opens a release README
- **THEN** they find what changed, and any known limits, without reading internals
