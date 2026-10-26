# Step-by-Step Mod Development Guide

This guide walks through how to study, write, package, and flash mods for the Digitone MK1.

## 1. Fast Track: Using Prebuilt Mods via Web Patcher

If you simply want to install existing community mods on your Digitone, you do **not** need a C cross-compiler:

1. Open **[elekloader Web](https://irpina.github.io/elekloader/)** in Chrome or an Edge browser (supports WebMIDI).
2. Drag and drop your official `Digitone_and_Digitone_Keys_OS1.44.syx` (found in `D:\Elektron-MODS\firmware\`).
3. Select the desired mods from the catalog:
   * **`core-dn1` (v4.1)**: Essential foundation providing the Mod Menu (hold `T1`–`T4`) and hook engine.
   * **`digitables`**: M8-style pitch tables for arpeggios, trills, and strummed chords.
   * **`digihealth`**: Adds real-time CPU, DSP load, and free RAM to the top status bar.
   * **`fxkit-dn1`**: Master effects insert framework with integrated mixer and 2 extra LFOs.
   * **Pedal Effects**: `digiswarm` (chorus/ensemble/looper), `digiprism` (spectral resonator), `digireel` (tape saturation/flutter), `digihalo` (shimmer reverb), `digitide` (phaser/filter sweeps), `digitriad` (pitch shifter).
   * **`machines-dn1`**: Replaces standard FM synthesis with alternative synth engine machines.
4. Click **BUILD FIRMWARE**.
5. Flash the output `.syx` file directly to your hardware using Elektron Transfer over USB.

---

## 2. Developing Custom Mods

### Toolchain Requirements
The Digitone MK1 main CPU is a **ColdFire MCF5441x** (Motorola 68k family).
* **Compiler**: `m68k-linux-gnu-gcc` or `m68k-elf-gcc`
* **Target ISA**: ColdFire V4 (`-mcpu=54455`)
* **Standard C Flags**: `-mcpu=54455 -O2 -ffreestanding -fno-builtin -nostdlib -fno-pic -fno-pie -fomit-frame-pointer -Wall`
* On Windows, install the `m68k-linux-gnu-gcc` toolchain inside WSL (Ubuntu/Debian: `sudo apt install gcc-m68k-linux-gnu binutils-m68k-linux-gnu`).

### Study Reference Implementations
* **`D:\Elektron-MODS\modules\digitables`**: Full C source showing how to handle UI pages, project persistence (`projdata`), 24 PPQN ticks, and note-on pitch offsets.
* **`D:\Elektron-MODS\tools\elekloader\mods\`**: Extensive collection of official modules (`core-dn1`, `machines-dn1`, `fxkit-dn1`, etc.).

### Mod Specification (`mod.json`)
Each mod directory defines metadata and hooks in `mod.json`:
* `subscribe`: Array of events to handle (`ev_key`, `ev_enc`, `ev_draw`, `ev_tick`, `ev_voice_on`, `ev_render_voices`).
* `contribute`: Register parameters into `core_params`, pages into `core_pages`, or entries in `core_menu`.
* `resources`: Declares required `core` version (e.g. `4.1`) and claimed memory slots.

---

## 3. The Development & Verification Loop

```
┌─────────────────────────────────┐
│ Write C / ASM Code              │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ Compile to .elemod              │ (python -m elekloader.sdk.build <dir> --stock <syx>)
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ Patch via elekloader            │ (python -m elekloader.patch --stock <syx> --mod <elemod> --out modded.syx)
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ Test in digiemu Emulator        │ (uv run python -m emu.portable or emu.dnpanel)
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ Flash to Digitone MK1           │ (Via USB using Elektron Transfer)
└─────────────────────────────────┘
```

---

## 4. Hardware Safety & Recovery

* **Bootloader Protection:** `elekloader` only modifies Section 3 (the Main OS). The factory bootloader and bootstrap updater (Sections 2 and 4) are completely untouched.
* **Factory Recovery:** If custom firmware hangs or crashes:
  1. Hold **[FUNC]** while powering on the unit to enter the **Early Startup Menu**.
  2. Press **[TRIG 4]** (OS UPGRADE).
  3. Send the clean stock `Digitone_and_Digitone_Keys_OS1.44.syx` using Elektron Transfer (Legacy OS Upgrade) to restore factory firmware.

