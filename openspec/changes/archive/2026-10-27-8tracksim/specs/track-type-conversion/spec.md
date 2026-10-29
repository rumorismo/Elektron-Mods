# Spec Delta

## Purpose

Lets players turn Digitone MK1 MIDI tracks into synth tracks and back, reaching any synth/MIDI mix up to eight simultaneous synth tracks through the stock voice engine.

## ADDED Requirements

### Requirement: MIDI track converts to synth track
The system SHALL convert a MIDI track (slots 4–7) into a synth track on the `MIDI`+`VOICE` chord, preserving the track's MIDI-side data in a per-track stash.

#### Scenario: Convert MIDI track to synth
- **WHEN** the player holds `MIDI` and presses `VOICE` on a MIDI track
- **THEN** the track sounds as a synth track and its prior MIDI data is retained in the stash

### Requirement: Converted track flips back with restore
The system SHALL restore a converted track to a MIDI track on a second `MIDI`+`VOICE` chord, returning the stashed MIDI-side data intact and stashing the synth-side data for a future flip.

#### Scenario: Flip back restores MIDI data
- **WHEN** the player repeats the chord on a converted track
- **THEN** the track behaves as a MIDI track again with its original MIDI data and the synth side is stashed

### Requirement: Chord ignored on native synth tracks
The system SHALL ignore the `MIDI`+`VOICE` chord on native synth tracks (slots 0–3), falling through to stock behavior.

#### Scenario: Native synth track unaffected
- **WHEN** the player presses the chord on a native synth track
- **THEN** nothing changes and stock handling proceeds

### Requirement: Voice menu stays on VOICE alone
The system SHALL open the voice allocation menu on a plain `VOICE` press on every track, with no bank or type side effects.

#### Scenario: Menu opens everywhere
- **WHEN** the player taps `VOICE` on any track without modifiers
- **THEN** the voice menu opens and track type is unchanged

### Requirement: Converted tracks sound together with all others
The system SHALL sound converted synth tracks simultaneously with native synth tracks and Bank-A MIDI tracks through the shared 8-voice engine with normal voice sharing.

#### Scenario: Eight synth tracks at once
- **WHEN** all MIDI tracks are converted and all eight synth tracks receive trigs
- **THEN** all eight sound subject only to stock 8-voice stealing

### Requirement: Bank-A MIDI keeps working
The system SHALL leave Bank-A MIDI tracks fully functional regardless of how many conversions are active.

#### Scenario: MIDI plays alongside converted tracks
- **WHEN** conversions are active and a Bank-A MIDI track plays
- **THEN** its MIDI output is unaffected
