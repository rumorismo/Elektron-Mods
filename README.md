# Digitone MK1 Modding Project

Welcome to your local environment for exploring, building, and running custom firmware mods for the **Elektron Digitone MK1** (and Digitone Keys).

## Directory Structure

```
D:\Elektron-MODS\
Gö£GöÇGöÇ docs/                     # Research notes, guides, and testing procedures
Göé   Gö£GöÇGöÇ ARCHITECTURE.md       # How the Digitone hardware & OS hooks operate
Göé   Gö£GöÇGöÇ MODDING_GUIDE.md      # Step-by-step development and patching guide
Göé   Gö£GöÇGöÇ PORTING_DIGITAKT_TO_DIGITONE.md # Digitakt vs. Digitone architecture, buttons & UI/UX porting guide
Göé   GööGöÇGöÇ EMULATOR_WORKFLOW.md  # How to run and test mods in digiemu
Gö£GöÇGöÇ firmware/                 # Official and modded .syx OS files & .elemod packages
Göé   Gö£GöÇGöÇ releases/             # Versioned firmware release packages
Göé   Göé   Gö£GöÇGöÇ v1.44-synth/      # Digitone OS 1.44S (Pure Synth Edition: Monomachine, Plaits, Sophie - no FX)
Göé   Göé   GööGöÇGöÇ v1.44+/           # Digitone OS 1.44+ (All 14 mods including FX pedals)
Göé   Gö£GöÇGöÇ elemods/              # Compiled .elemod binaries
Göé   Gö£GöÇGöÇ Digitone_and_Digitone_Keys_OS1.44.syx # Stock factory OS
Göé   GööGöÇGöÇ Digitone_OS1.44_MODDED.syx # Active modded firmware sysex
Gö£GöÇGöÇ modules/                  # Source code for custom modules
Göé   Gö£GöÇGöÇ dn-monomachine/       # Ported Monomachine, SH-101, Plaits MACRO & SOPHIE machines for Digitone
Göé   Gö£GöÇGöÇ digi1_mods/           # Reference Digitakt MK1 synth & utility mod collection
Göé   Gö£GöÇGöÇ digisophie/           # Reference metallic percussion synth repository
Göé   GööGöÇGöÇ digitables/           # Reference M8-style pitch tables mod
GööGöÇGöÇ tools/                    # Cloned toolchains and emulators
    Gö£GöÇGöÇ digiemu/              # ColdFire + DSP emulator with virtual UI
    GööGöÇGöÇ elekloader/           # Binary patcher and build system
```

## Quick Start: Stock Firmware Status

The stock firmware file has been verified and placed into `D:\Elektron-MODS\firmware\`:
* `Digitone_and_Digitone_Keys_OS1.44.syx` (SHA-256: `d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659`)

You can also use `Digitone_and_Digitone_Keys_OS1.43.syx` if desired.

## Web Patcher (Fastest Path)
You can directly build custom firmwares with community mods in your browser without compiling anything:
* Visit **[elekloader Web](https://irpina.github.io/elekloader/)** and drag your stock OS file from `firmware/`.
* Pick from mods like `digitables`, `digihealth`, `fxkit`, `digiswarm`, `digiprism`, etc.

## Next Steps
Read [docs/EMULATOR_WORKFLOW.md](docs/EMULATOR_WORKFLOW.md) to set up your virtual Digitone on your desktop, or [docs/MODDING_GUIDE.md](docs/MODDING_GUIDE.md) to start creating custom mods!
