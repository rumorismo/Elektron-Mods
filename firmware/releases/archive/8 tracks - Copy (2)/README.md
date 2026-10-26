# Digitone MK1 & Digitone Keys OS 1.44 – 8-Track & 16-Track Matrix Expansion

**Firmware Release**: `Digitone_OS1.44_8Tracks.syx` (Version `1448`)  
**Target Hardware**: Elektron Digitone MK1 & Digitone Keys  
**Base Firmware**: Digitone OS 1.44 (compatible with 1.43)

---

## 1. Overview & Capabilities

The **8-Track Matrix Expansion** doubles the sequencer and synthesis matrix of the Elektron Digitone MK1 / Digitone Keys:
* **8 Synth Tracks**: Bank A (Synth Tracks 1–4) + Bank B (Synth Tracks 5–8).
* **8 MIDI Tracks**: Bank A (MIDI Tracks 1–4) + Bank B (MIDI Tracks 5–8).
* **Single-Press Bank Toggle**: Single-press `[VOICE]` to instantly toggle between Bank A (Tracks 1–4) and Bank B (Tracks 5–8).
* **Standard Voice Allocation Access**: `[FUNC] + [VOICE]` opens the native Voice Allocation menu.
* **Full Sound Browser on All 8 Tracks**: Double-click `[T1]–[T4]` on Bank B to open the native Digitone Sound Browser and load any patch from the +Drive (2,048 sounds) or Project Sound Pool (128 sounds).
* **Custom Synthesis Machines on All 8 Tracks**: Long-press `[T1]–[T4]` (0.4s) to open the Mod Menu (`1: MACHINES`) and assign any custom synthesis machine (`MACRO`, `SOPHIE`, `CHORD`, `ENS`, `VO-6`, `SAW`, `PULSE`, `NOISE`, `PSIN`, `SINE`, `THRU`) or stock `FM`.
* **Hardware LED Feedback**:
  * **Bank A**: Stock LED behavior (Cyan for synth tracks, Amber for MIDI).
  * **Bank B**: `[VOICE]` LED and active track `[T1]–[T4]` light **Pure Bright Red** (hardware palette 14: `R=15, G=0, B=0`), completely distinct from Cyan or Violet.
* **OLED Top Header**: Displays an inverted high-contrast badge `B:T5`–`B:T8` (or `B:M5`–`B:M8`) in the top-left status area when Bank B is active.
* **Atomic Sequencer Re-Sync**: Changing banks atomically syncs sequencer step pointers and releases active voices, eliminating timing mangling and hanging notes.

---

## 2. Controls & Workflow

| Action | Control | Function |
| :--- | :--- | :--- |
| **Switch Bank** | **Single-press `[VOICE]`** | Instantly toggles between **Bank A** (Tracks 1–4) and **Bank B** (Tracks 5–8) with 1 touch. Swallows the key event so Voice Menu never opens. |
| **Voice Allocation Menu** | **`[FUNC] + [VOICE]`** | Opens the standard Voice Allocation page (where Unison, voice stealing, and voice locking can be adjusted). |
| **Select Track** | **`[T1]–[T4]`** | Selects active track (Tracks 1–4 in Bank A; Tracks 5–8 in Bank B). |
| **Open Sound Browser** | **Double-click `[T1]–[T4]`** | Opens native Sound Browser (+Drive & Sound Pool) to load patches into the active track. |
| **Open Machine Menu** | **Long-press `[T1]–[T4]` (0.4s)** | Opens Mod Menu (`1: MACHINES`) to select custom machines or FM. |
| **Mute Track** | **`[FUNC] + [T1]–[T4]`** | Mutes/unmutes active bank tracks independently. |
| **Parameter Pages** | **`[SYN1]`, `[SYN2]`, `[FLTR]`, `[AMP]`, `[LFO]`, `[TRIG]`** | Edits the active track parameters with full encoder feedback. |
| **Grid Recording** | **`[RECORD]` + `[TRIG 1–16]`** | Enters note trigs, parameter locks, microtiming, and trig conditions. |

---

## 3. Hardware LED Feedback

* **Bank A (Normal Mode)**: Stock LED behavior.
* **Bank B (Extended Mode)**: `[VOICE]` LED and active track `[T1]–[T4]` light **Pure Bright Red** (`palette 14`: `R=15, G=0, B=0`), making it immediately obvious which bank is active.

---

## 4. Dynamic Voice Allocation & CPU Compliance

All 8 synth tracks dynamically share the 8 hardware voices according to the contracts in `docs/VOICE_OPTIMIZATION.md`:
1. **Dynamic Voice Sharing**: Idle tracks consume 0 voices. Notes are allocated dynamically across the 8 hardware voices using the native round-robin voice allocator.
2. **Per-Track Newest-Wins Stealing**: Monophonic engines on any track steal only older voices belonging to the same track.
3. **Global Custom Machine DSP Cap**: Custom DSP synthesis is capped at a maximum of **2 simultaneous voices globally** (`newer_all >= 2`), ensuring CPU #1 render load stays under **15–20%** and total system load stays well below 75%.
4. **Clean Release Cutoff**: Envelope release tails are clamped to silence at `<= 64` (-54 dB), preventing voice leaks or UI task starvation.

---

## 5. Per-Pattern & Project Persistence

* **Per-Pattern Sequences**: Sequencer steps, notes, velocities, lengths, and locks for Bank B are saved per pattern across all 128 patterns in DDR fast RAM.
* **Per-Project Sounds**: Bank B sound records and active bank state persist across project saves and reboots via `core_projdata` (tag `'TRK8'`).

---

## 6. Included Mods in this Build

This firmware (`Digitone_OS1.44_8Tracks.syx`) links 7 modular elemods:
1. `core-dn1-4.1`: Boot copier, hook bus, 1.25 MB fast RAM mapping, and event dispatcher.
2. `tracks-1.2`: 8-Track and 16-Track Matrix Expansion, single-press toggle, Red LED control, sequencer re-sync.
3. `machines-0.2`: Machine framework and 4x2 parameter grid overlay.
4. `dnmono-1.2`: Monomachine synthesis engines (SAW, PULSE, ENS, CHORD, VO-6, NOISE).
5. `dnsine-1.1`: Multi-algorithm pure additive and sine synthesis.
6. `dnthru-1.0`: Low-latency stereo audio thru machine.
7. `digihealth-1.1`: Real-time system monitoring, CPU load gauges, and memory auditing.

---

## 7. How to Flash

1. Connect the Digitone MK1 or Digitone Keys to your computer via USB.
2. Power on the unit while holding **`[FUNC]`** to enter the **Early Startup Menu**.
3. Press **`[TRIG 4]`** to enter **MIDI Upgrade** mode.
4. Send `Digitone_OS1.44_8Tracks.syx` using **Elektron Transfer**, **C6**, or `amidi`:
   ```bash
   amidi -p hw:1,0,0 -s Digitone_OS1.44_8Tracks.syx
   ```
5. Wait for the progress bar on the Digitone screen to complete (100%). The unit will verify checksums and reboot automatically.
