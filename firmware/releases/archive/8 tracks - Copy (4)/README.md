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
* **Direct Voice Allocation Access**: `[FUNC] + [VOICE]` directly opens the native Voice Allocation menu, completely swallowing the key event so Unison is never triggered.
* **Settings Menu Integration**: `VOICE ALLOCATION` is added directly into the Settings menu (`GLOBAL` key) right below `SYSTEM INFO`.
* **Seamless Continuous Live Playback**: Switching banks while the sequencer is running continues playback without stopping, resetting, or dropping beats.
* **Completely Independent Mutes per Bank**: Live hardware mutes (`0x41392f30`) and pattern mutes are saved and restored per bank. Muting Track 5 in Bank B (`[FUNC] + [T1]`) leaves Track 1 in Bank A completely unaffected.
* **Clean Pattern Sequence Init**: Bank B tracks are initialized using native firmware sequencer calls (`0x40015180` and `0x4001511c`), starting with completely empty patterns and zero ghost trigs.
* **Sleek HUD Popup Card**: Pressing `[VOICE]` displays a centered modal card (`BANK B: TRACKS 5-8` / `BANK A: TRACKS 1-4`) for 1.2 seconds before fading, keeping screens clean without solid blocks.
* **Full Sound Browser on All 8 Tracks**: Double-click `[T1]–[T4]` on Bank B to open the native Digitone Sound Browser and load any patch from the +Drive (2,048 sounds) or Project Sound Pool (128 sounds).
* **Custom Synthesis Machines on All 8 Tracks**: Long-press `[T1]–[T4]` (0.4s) to open the Mod Menu (`1: MACHINES`) and assign any custom synthesis machine (`MACRO`, `SOPHIE`, `CHORD`, `ENS`, `VO-6`, `SAW`, `PULSE`, `NOISE`, `PSIN`, `SINE`, `THRU`) or stock `FM`.
* **Hardware LED Feedback**:
  * **Bank A**: Stock LED behavior (Cyan for synth tracks, Amber for MIDI).
  * **Bank B**: `[VOICE]` LED and active track `[T1]–[T4]` light **Pure Bright Red** (hardware palette 14: `R=15, G=0, B=0`), completely distinct from Cyan or Violet.

---

## 2. Controls & Workflow

| Action | Control | Function |
| :--- | :--- | :--- |
| **Switch Bank** | **Single-press `[VOICE]`** | Instantly toggles between **Bank A** (Tracks 1–4) and **Bank B** (Tracks 5–8). Seamless playback continues if playing. Triggers popup card HUD. |
| **Voice Allocation Menu (Button)** | **`[FUNC] + [VOICE]`** | Opens the standard Voice Allocation page directly (Unison shortcut is cleanly bypassed). |
| **Voice Allocation Menu (Settings)** | **`[GLOBAL]` -> `VOICE ALLOCATION`** | Opens the standard Voice Allocation page right below `SYSTEM INFO`. |
| **Select Track** | **`[T1]–[T4]`** | Selects active track (Tracks 1–4 in Bank A; Tracks 5–8 in Bank B). |
| **Mute Track (Bank-Independent)** | **`[FUNC] + [T1]–[T4]`** | Mutes/unmutes active bank tracks independently. Bank A and Bank B mutes are completely isolated. |
| **Open Sound Browser** | **Double-click `[T1]–[T4]`** | Opens native Sound Browser (+Drive & Sound Pool) to load patches into the active track. |
| **Open Machine Menu** | **Long-press `[T1]–[T4]` (0.4s)** | Opens Mod Menu (`1: MACHINES`) to select custom machines or FM. |
| **Parameter Pages** | **`[SYN1]`, `[SYN2]`, `[FLTR]`, `[AMP]`, `[LFO]`, `[TRIG]`** | Edits the active track parameters with full encoder feedback. |
| **Grid Recording** | **`[RECORD]` + `[TRIG 1–16]`** | Enters note trigs, parameter locks, microtiming, and trig conditions. |

---

## 3. Included Mods in this Build

This firmware (`Digitone_OS1.44_8Tracks.syx`) links 7 modular elemods:
1. `core-dn1-4.1`: Boot copier, hook bus, 1.25 MB fast RAM mapping, and event dispatcher.
2. `tracks-1.4`: 8-Track and 16-Track Matrix Expansion, single-press toggle, Red LED control, popup HUD, independent bank mutes, continuous live playback, Settings menu integration.
3. `machines-0.2`: Machine framework and 4x2 parameter grid overlay.
4. `dnmono-1.2`: Monomachine synthesis engines (SAW, PULSE, ENS, CHORD, VO-6, NOISE).
5. `dnsine-1.1`: Multi-algorithm pure additive and sine synthesis.
6. `dnthru-1.0`: Low-latency stereo audio thru machine.
7. `digihealth-1.1`: Real-time system monitoring, CPU load gauges, and memory auditing.

---

## 4. How to Flash

1. Connect the Digitone MK1 or Digitone Keys to your computer via USB.
2. Power on the unit while holding **`[FUNC]`** to enter the **Early Startup Menu**.
3. Press **`[TRIG 4]`** to enter **MIDI Upgrade** mode.
4. Send `Digitone_OS1.44_8Tracks.syx` using **Elektron Transfer**, **C6**, or `amidi`:
   ```bash
   amidi -p hw:1,0,0 -s Digitone_OS1.44_8Tracks.syx
   ```
5. Wait for the progress bar on the Digitone screen to complete (100%). The unit will verify checksums and reboot automatically.
