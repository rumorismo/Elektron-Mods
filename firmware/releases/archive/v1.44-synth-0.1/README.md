# Digitone MK1 OS 1.44S (Pure Synth Edition) — Release 0.1

Streamlined custom firmware for **Elektron Digitone MK1** and **Digitone Keys**, stripped of all external input effects pedals to provide maximum DSP headroom and stability strictly focused on **internal synthesis**.

> [!IMPORTANT]
> **Release 0.1 Notes (October 2026)**
> * **CPU Overload & Latency Fix**: Resolved a critical voice lifecycle leak where FM voices retained active sustain state across machine switches, triggering 8 stuck zombie voices at 100% CPU.
> * **Voice Allocation & Stealing**: Added per-track newest-wins voice stealing and a 2-voice global mod budget to prevent release tails from overloading ColdFire CPU #1.
> * **DSP Optimization**: Enabled 2x oversampled eco mode on Mutable Instruments Plaits (`MACRO`), cutting oscillator compute time in half while preserving sonic character.
> * **SH-101 Removed**: Cleaned out `SH-101` from the machine chooser.
> * **Technical Reference**: See [`docs/VOICE_OPTIMIZATION.md`](file:///D:/Elektron-MODS/docs/VOICE_OPTIMIZATION.md) for architecture timing budgets and voice lifecycle design.

---

## Release Metadata

| Property | Value |
| :--- | :--- |
| **OS Version String** | `144S` *(renders as `1.44S` on boot screen)* |
| **Release Iteration** | `0.1` |
| **Base Firmware** | Elektron Digitone / Digitone Keys OS 1.44 |
| **Firmware File** | `Digitone_OS1.44_Synth_0.1.syx` |
| **File Size** | 1,779,744 bytes (1.70 MB) |
| **SHA-256 Checksum** | `02af17fd628cbdc73f4498fa4e5d1a8cc89314d9221f84058fa1e8cb3cd621a1` |
| **Target Hardware** | ColdFire MCF5441x (CPU #1 OS + CPU #2 DSP) |
| **Spare RAM Headroom** | **1,207,844 bytes spare** (1.2 MB free fast SRAM) |
| **Installed Modules** | 6 clean modules (zero audio intercepts) |

---

## What Was Removed?

All external audio input pedal effects from the `fxkit` ecosystem have been **completely removed**:
* ❌ `fxkit` (Effects framework & audio bus intercept)
* ❌ `digiprism` (Multi-effects pedal & insert)
* ❌ `digihalo` (12-engine Reverb pedal)
* ❌ `digireel` (Tape looper & time-warp pedal)
* ❌ `digiswarm` (Swarm looper & granular pedal)
* ❌ `digitide` (2-channel looper & rate pedal)
* ❌ `digitriad` (3-voice pitch harmonizer pedal)
* ❌ `digihoard` (Sound pool utility)

**Why this matters**:
1. **0% Audio Intercepts**: Nothing takes over or mutes internal synth tracks.
2. **Maximum CPU Headroom**: 100% of ColdFire CPU #1 and CPU #2 cycles are dedicated to running your tracks, filters, envelopes, and factory send FX (Chorus, Delay, Reverb).
3. **Rock-Solid Stability**: 1.2 MB of spare RAM ensures zero memory fragmentation.

---

## Included Modules (6 Modules)

### 1. Core Framework & Engine Dispatcher
* **`core-dn1` (v4.1)**: Dual-CPU ColdFire framework, dynamic module loader, and EMAC register preservation.
* **`machines-dn1` (v0.2)**: Front-panel machine switcher placed as **Tile #1** on long-pressing any track button (`[T1]`–`[T4]`), with custom 4×2 parameter grid replacing the FM algorithm screen on custom tracks. Full 8-voice allocation and routing into the Digitone's multimode filters, voice overdrive, and send FX.

### 2. Complete Synthesizer Machines Pack (`dnmono` v1.2)
Nine dedicated synthesis engines accessible per-track on Tracks 1 through 4:

| Machine ID | Name | Engine Type | Features & Parameters |
| :---: | :--- | :--- | :--- |
| **0** | `FM` | Stock Digitone FM | Factory 4-operator 8-algorithm FM synthesis engine (100% untouched). |
| **10** | `SAW` | SuperWave Saw | Classic Elektron Monomachine saw with multi-oscillator detune (`DETN`) and stereo spread (`SPRD`). |
| **11** | `PULSE` | SuperWave Pulse | Variable pulse width oscillator with manual PW and integrated LFO modulation (`PWM`). |
| **12** | `ENS` | Ensemble + Chorus | 4-voice unison ensemble generator with multi-octave pitch spread and internal chorus depth. |
| **13** | `CHORD` | 4-Osc Chord Machine | 16 chord voicings (Min, Maj, Sus4, 7th, Min7, Maj7, Dim, Aug, Octaves, Fifths, etc.) with inversion and spread. |
| **14** | `VO-6` | Formant Vocal Synth | 6-band resonant vocal tract model with vowel morphing (A, E, I, O, U), consonant attacks, and throat formants. |
| **15** | `NOISE` | Multimode Noise Engine | Sample & hold clocked noise, tuned resonant red/pink noise, and stereo digital grit. |
| **16** | `PSIN` | Poly Sine Synth | 3-harmonic sine wave generator with dedicated per-note pitch envelope depth (`EDEP`) and speed (`ESPD`). |
| **18** | `MACRO` | Plaits Macro Oscillator | **Mutable Instruments Plaits** (8 selectable synthesis engines on `SYN1` Knob B):<br>• *WSHP*: Non-linear waveshaper<br>• *FM2*: 2-Operator variable-feedback FM<br>• *NOIS*: Clocked & filtered noise<br>• *DUST*: Granular dust & particle noise<br>• *KICK*: Analog bass drum model<br>• *SNAR*: Analog dual-mode snare drum model<br>• *HHAT*: Analog 6-oscillator metallic hi-hat<br>• *SWRM*: Formant swarm & granular cloud<br>Expanded controls: `HARM`, `TIMB`, `MORP`, `FINE`, `PENV`, `PDEC`, `SUB`. |
| **19** | `SOPHIE` | Metallic Percussion Synth | 4 physical/FM metallic models (`FUSE`, `BOOM`, `PIPE`, `SHARD`) with frequency modulation sweep, wavefolding, and feedback resonance. |

### 3. Utility Audio Machines
* **`dnsine` (v1.1)**: Pure sinusoidal test oscillator & sub-bass generator.
* **`dnthru` (v1.0)**: Direct external audio input thru engine routed through Digitone filters and envelopes.

### 4. System Diagnostics
* **`digihealth` (v1.1)**: Hardware diagnostics, live CPU meter, and task profiling screen in the Mod Menu.

---

## Front-Panel Quick Start

1. **Selecting a Machine**:
   * Hold `[T1]`, `[T2]`, `[T3]`, or `[T4]` for **0.4 seconds** until the menu overlay appears.
   * Highlight **`1: MACHINES`** (Tile #1) and press `[YES]`.
   * Turn **Encoder A** to select your machine (e.g., `MACRO`, `SOPHIE`, `CHORD`, `SAW`).
   * Press `[YES]` or `[NO]` to return to the active track.

2. **Editing Synthesizer Parameters**:
   * **`[SYN1]` Screen**: Displays octave (`OCT`), machine engine selection (`ENGN` on Macro / `MODEL` on Sophie), and primary synthesis parameters.
   * **`[SYN2]` Screen**: Displays engine-specific parameters with dynamic labels that change automatically based on the engine selected on `SYN1` Knob B.

3. **Using Filter, Amp, and Send FX**:
   * All custom machines route directly into the Digitone MK1's dual-filter architecture:
     * `[FLTR]`: 2-pole multimode resonant filter (LP, HP, BP) + base-width filter.
     * `[AMP]`: ADSR amplitude envelope, voice overdrive, and pan.
     * `[FX]`: Master send levels for Chorus, Delay, and Reverb.

---

## Flashing Instructions

### On Physical Digitone MK1 / Digitone Keys
1. Connect your Digitone to your computer via USB.
2. Launch **Elektron Transfer** (version 1.5 or later).
3. Connect to your Digitone and navigate to the **EXPLORE / OS UPGRADE** tab.
4. Drag and drop `Digitone_OS1.44_Synth_0.1.syx` into the window.
5. Wait for the transfer and checksum verification to complete. The Digitone will reboot into **OS 1.44S**.

### In Desktop Emulator (`digiemu`)
Double-click `run-modded-digitone.bat` in the repository root.
