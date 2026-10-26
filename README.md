# Digitone MK1 Modding Project

Welcome to your local environment for exploring, building, and running custom firmware mods for the **Elektron Digitone MK1** (and Digitone Keys).

## Directory Structure

```
D:\Elektron-MODS\
|-- docs\                     # Research notes, guides, and testing procedures
|   |-- ARCHITECTURE.md       # How the Digitone hardware & OS hooks operate
|   |-- EMULATOR_WORKFLOW.md  # How to run and test mods in digiemu
|   |-- MODDING_GUIDE.md      # Step-by-step development and patching guide
|   |-- PORTING_DIGITAKT_TO_DIGITONE.md # Digitakt vs. Digitone architecture, buttons & UI/UX porting guide
|   |-- REPO.md               # Repo map: releases, builds, and tests
|   `-- VOICE_OPTIMIZATION.md # Architecture timing budgets and voice lifecycle design
|-- firmware\                 # Official and modded .syx OS files & .elemod packages
|   |-- Digitone_and_Digitone_Keys_OS1.44.syx # Stock factory OS
|   |-- Digitone_OS1.44_8Tracks.syx / Digitone_OS1.44_8Tracks7.syx # 8-track build files at root
|   |-- Digitone_OS1.44_MODDED.syx # Active modded firmware sysex (+ .json / .map.json)
|   |-- 8tracks2_main.bin / stock_main.bin # Extracted OS images used as build inputs
|   |-- releases\             # Versioned firmware release packages
|   |   |-- 8 tracks\         # 8-track build 1447, kept for compat (old + Build 7 .syx)
|   |   |-- v1.44-8tracks-0.7\ # Canonical 8-track build 1447 (Digitone_OS1.44_8Tracks7.syx)
|   |   |-- v1.44-synth-0.1\  # OS 1.44S pure synth release 0.1 (no FX pedals)
|   |   |-- v1.44-synth-0.2\  # OS 1.44S pure synth release 0.2 (no FX pedals)
|   |   |-- v1.44+-0.1\       # OS 1.44+ superpack release 0.1 (all 14 mods)
|   |   |-- v1.44+-0.2\       # OS 1.44+ superpack release 0.2 (all 14 mods)
|   |   `-- archive\          # Deduped `8 tracks - Copy*` iterations
|   `-- elemods\              # Compiled .elemod binaries (core, tracks, machines, dnmono, fxkit, ...) + .work build dirs
|-- modules\                  # Source code for custom modules
|   |-- dn-monomachine\       # Ported Monomachine, SH-101, Plaits MACRO & SOPHIE machines for Digitone
|   |-- digi1_mods\           # Reference Digitakt MK1 synth & utility mod collection
|   |-- digisophie\           # Reference metallic percussion synth repository
|   `-- digitables\           # Reference M8-style pitch tables mod
|-- tools\                    # Cloned toolchains and emulators
|   |-- digiemu\              # ColdFire + DSP emulator with virtual UI
|   `-- elekloader\           # Binary patcher and build system (web shop catalog under web/)
|-- openspec\                 # Change proposals and specs (changes\, specs\, config.yaml)
|-- tests\
|   `-- smoke.ps1             # Checks: stock hash, release manifest, git-clean, toolchain
|-- run-emulator.bat          # Launch the digiemu picker
|-- run-modded-digitone.bat   # Launch the emulator with the modded OS
`-- run-stock-digitone.bat    # Launch the emulator with stock OS 1.44
```

## Quick Start: Stock Firmware Status

The stock firmware file has been verified and placed into `D:\Elektron-MODS\firmware\`:
* `Digitone_and_Digitone_Keys_OS1.44.syx` (SHA-256: `d4f200d04483c33d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659`)

You can also use `Digitone_and_Digitone_Keys_OS1.43.syx` if desired.

## Web Patcher (Fastest Path)
You can build a custom Digitone firmware in your browser with nothing to install:
* Visit **[elekloader Web](https://irpina.github.io/elekloader/)** and drop in your stock OS file from `firmware/`. Tick mods, build, and download the resulting `.syx` — everything happens in the tab, your files are never uploaded.
* The page only offers downloads: it never talks to the instrument, so there is no Web MIDI/USB flashing. Send the downloaded `.syx` to the Digitone with Elektron Transfer, like any OS update.
* The shop's Digitone selection is [`digihealth`](https://modwerk.app/digitone/module/digihealth/) (system telemetry) and [`digitables`](https://modwerk.app/digitone/module/digitables/) (M8-style pitch tables). The other mods bundled in this repo's releases (tracks, machines, dnmono, the fxkit pedal chain, ...) are built locally with elekloader, not from the shop.
* More mods and discussion: [elekloader library](https://github.com/irpina/elekloader/blob/main/web/catalog.json) (the shop's curated, sha256-pinned mod list), [Modwerk Digitone modules](https://modwerk.app), and the elektronmods forum — [Elekloader thread 30](https://elektronmods.com/thread-30-elekloader-a-mod-loader-for-elektron-devices), [digiemu thread 20](https://elektronmods.com/thread-20-digiemu-a-digitakt-and-digitone-emulator), [stock firmware download list thread 27](https://elektronmods.com/thread-27-elektron-firmware-download-list).

## Next Steps
Read [docs/EMULATOR_WORKFLOW.md](docs/EMULATOR_WORKFLOW.md) to set up your virtual Digitone on your desktop, or [docs/MODDING_GUIDE.md](docs/MODDING_GUIDE.md) to start creating custom mods!
