# Digitone MK1 Architecture & Modding Principles

## 1. Dual-Core Architecture

The Digitone MK1 (and Digitone Keys) runs on a dual ColdFire processor layout:

1. **Main CPU (ColdFire MCF5441x):**
   * Executes Section 3 of the firmware depacked into DDR RAM at `0x40000400`.
   * Runs an RTOS handling the user interface (128x64 OLED display, 72 key LEDs, encoders), 24 PPQN sequencer timing, project storage (+Drive), USB/MIDI communication, audio routing, send effects (delay, reverb, chorus, overdrive), and master mixing.
   * Total DDR RAM: 128 MB (`0x40000000` to `0x48000000`). Stack grows downward from `0x48000000`.
   * Mod code execution area (`core-dn1` 4.0+): `0x43EC0000` - `0x44000000` (1.25 MB allocated for mod code, tables, and variables).
   * **Bulk Buffer Area (`0x44000000` - `0x47BE0000`):** ~60 MB of contiguous unmapped DDR available for mods requiring large memory buffers (e.g. 60-second audio loopers, delay memory, custom sample buffers).
   * Target architecture for compilation: ColdFire V4 (`-mcpu=54455`, `m68k-linux-gnu-gcc` / `m68k-elf-gcc`).

2. **Sound Engine CPU (Second ColdFire MCF5441x, referred to as the DSP):**
   * Dedicated processor rendering the 8 FM voices at 48 kHz.
   * Runs Section 7 loaded at `0x40000400`.
   * Communicates with the main CPU via a 128 KB dual-port shared RAM:
     * Main CPU maps it at FlexBus `0x10000000`.
     * DSP maps it at `0x00000000`.
   * Hardware synchronization via GPIO interrupts:
     * Main `PB6` controls the DSP reset line.
     * DSP `PG2` drives Main edge port pin 4 (vector 68).
     * Main `PA4` toggles DSP DMA timer 0 capture input (vector 96) every 32-sample audio block (1500 times/second).
   * Parameter transfer: Main CPU writes voice parameters to shared RAM `0x000`–`0x39F`, and the DSP writes the 8 rendered voice blocks (32 samples each in Q1.31 format) back to `0x3A0`–`0x79F`.

## 2. Supported Firmware Releases

Firmware is distributed by Elektron as MIDI System Exclusive files (`.syx`). Both Digitone desktop and Digitone Keys use the exact same firmware binary:

* **OS 1.44 (Latest):**
  * `.syx` SHA-256: `d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659`
  * Main OS SHA-256: `fce648a97c6c5d93b961732e8f8db6b02e0820c6d344c7e2131fa05a4b3168e4` (length: 2,736,304 bytes)
* **OS 1.43:**
  * `.syx` SHA-256: `c5a54cc05b921f2e4bd814834c5365c2a5aa01d7772a9a2961fac1c3095bf9aa`
  * Main OS SHA-256: `3831a477a2a22befb23c42e47e782853da49566ef5d0a1767fcf6c30e6767414` (length: 2,732,208 bytes)

The bootloader partition is **never** touched by `elekloader`. Only Section 3 (the Main OS) is patched.

## 3. The `core-dn1` Framework

Community mods connect through `core-dn1` (version 4.1 recommended), which hooks into the RTOS and provides:

* **The Mod Menu:** Opened by holding any track key (`T1`–`T4`) for ~500ms.
* **Page Injections:** Adding custom parameter pages to existing menus (e.g. `AMP` page 3, custom `SYN` pages).
* **Machine Replacement:** The `machines-dn1` companion allows custom synthesizer engines to substitute for FM voices on selected tracks.
* **Audio Interceptions:** Exclusive and insert audio effects processing (`fxkit-dn1`).
* **Hook Events:**
  * `ev_key`: Intercept or modify front panel key presses.
  * `ev_enc`: Intercept and translate knob movements.
  * `ev_draw`: Render custom visual elements directly to the OLED display buffer.
  * `ev_tick`: Periodic UI update tasks.
  * `ev_voice_on` & `ev_render_voices`: Intercept note triggers, adjust pitch/envelope offsets, or supply synthetic voice audio.
  * `ev_midi_cc` & `ev_midi_pc`: MIDI CC and Program Change event hooks.

