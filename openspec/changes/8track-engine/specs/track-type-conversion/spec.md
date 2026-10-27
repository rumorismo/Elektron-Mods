# Spec Delta: 8-track engine

## Purpose
Full converter parity: confirmed modal flips, converted slots that sound/sequence/mute/browse/edit like native synth (with b1..b4 labels), preserved MIDI channels, and GUI-first verification with a fast regression probe.

## MODIFIED Requirements

### Requirement: MIDI track converts to synth track
The system SHALL offer conversion via a YES/NO modal on the `MIDI`+`VOICE` chord on slots 4–7 and convert on YES, sharing the slot's trig pattern and preserving its MIDI channel for the converted synth's output.

#### Scenario: Convert MIDI track to synth
- **WHEN** the player holds `MIDI` and presses `VOICE` on a MIDI track
- **THEN** the track sounds as a synth track and its prior MIDI data is retained in the stash

#### Scenario: Modal confirm converts with shared trigs
- **WHEN** the player confirms YES on a MIDI track modal
- **THEN** the slot sequences as synth on the same channel with the same trigs and MIDI-side params stashed

### Requirement: Converted track flips back with restore
The system SHALL offer restore via the same modal on converted tracks and return the stashed MIDI-side data intact, keeping the shared trigs.

#### Scenario: Flip back restores MIDI data
- **WHEN** the player repeats the chord on a converted track
- **THEN** the track behaves as a MIDI track again with its original MIDI data and the synth side is stashed

#### Scenario: Modal restore keeps trigs
- **WHEN** the player confirms YES on a converted track modal
- **THEN** the slot returns to MIDI with the same trigs and the synth side stashed

### Requirement: Chord ignored on native synth tracks
The system SHALL ignore the `MIDI`+`VOICE` chord on slots 0–3 (no modal), falling through to stock behavior.

#### Scenario: Native synth track unaffected
- **WHEN** the player presses the chord on a native synth track
- **THEN** nothing changes and stock handling proceeds

#### Scenario: No modal on native tracks
- **WHEN** the player presses the chord on slots 0–3
- **THEN** no modal appears and stock handling proceeds

### Requirement: Voice menu stays on VOICE alone
The system SHALL open the voice menu on plain `VOICE` everywhere and open the synth voice menu (S3/S4 synth fork) on converted tracks.

#### Scenario: Menu opens everywhere
- **WHEN** the player taps `VOICE` on any track without modifiers
- **THEN** the voice menu opens and track type is unchanged

#### Scenario: Converted track opens synth voice menu
- **WHEN** the player taps `VOICE` on a converted track without modifiers
- **THEN** the synth voice menu opens and type is unchanged

### Requirement: Converted tracks sound together with all others
The system SHALL sound converted tracks through synth-fire (S1/S2) with `.bss` sound fetch + voice-cache warm, sequenced and muted like native, subject only to stock 8-voice stealing.

#### Scenario: Eight synth tracks at once
- **WHEN** all MIDI tracks are converted and all eight synth tracks receive trigs
- **THEN** all eight sound subject only to stock 8-voice stealing

#### Scenario: Converted mutes and sequencer match native
- **WHEN** the player mutes or sequences a converted track
- **THEN** it silences and triggers exactly like a native synth track

### Requirement: Bank-A MIDI keeps working
The system SHALL leave Bank-A MIDI byte-identical with conversions active and preserve each slot's channel through conversion.

#### Scenario: MIDI plays alongside converted tracks
- **WHEN** conversions are active and a Bank-A MIDI track plays
- **THEN** its MIDI output is unaffected

#### Scenario: Converted channel preserved
- **WHEN** a slot set to channel 5 is converted
- **THEN** the converted synth outputs on channel 5

## ADDED Requirements

### Requirement: Confirm-modal gesture
The system SHALL require YES confirmation before any flip; NO, the NO key, or timeout cancels with no state change.

#### Scenario: Cancel leaves state unchanged
- **WHEN** the modal is open and the player presses NO or lets it time out
- **THEN** the track type, stash, and pattern are unchanged

### Requirement: Sound browser on converted tracks
The system SHALL open the synth sound browser on double-click of a converted track and write the chosen preset to that slot's `.bss` record.

#### Scenario: Double-click opens synth browser
- **WHEN** the player double-clicks a converted track key
- **THEN** the synth preset browser opens and the selected sound voices on that slot

### Requirement: Converted labels read b1..b4
The system SHALL display converted slots as `b1..b4` (S6/S7) instead of native `TRK.n`/`T n`.

#### Scenario: Converted labels show bank marker
- **WHEN** the player views track labels with conversions active
- **THEN** slots 4–7 show `b1..b4` while native slots keep stock labels

### Requirement: Synth param pages follow type
The system SHALL route converted tracks to the synth param chain (S8/S5 synth fork).

#### Scenario: Converted synth pages respond
- **WHEN** the player opens param pages on a converted track
- **THEN** synth pages (SYN1/SYN2/FLTR/AMP/FX) respond as on native tracks

### Requirement: GUI-first verification with fast regression probe
The system SHALL verify converter parity via manual panel procedures plus a regression-only headless probe (snapshot resume, single session, cached stock baselines, 1–2 bar captures) completing well under the old 5–10 min loop.

#### Scenario: Fast regression iteration
- **WHEN** iterating on converter builds
- **THEN** manual checks cover modal/browser/menu/labels/pages/mutes/sequencer and the probe asserts CNV8 + MIDI-identity + framebuffer hash in <60 s (L1 cold boot excepted)
