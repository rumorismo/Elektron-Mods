# Digitone OS 1.44 - 8Track-Engine2 (tag 1490)

Built 2026-10-29 with tools/release.py against stock OS 1.44
(SHA-256 `d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659`).

Output SHA-256: `38aa5ba596564b940f85678c14ce13c6ef61eb5d709f78be5ba6d7c8fb7962fa`

Toolchain: `m68k-linux-gnu-gcc (Ubuntu 13.3.0-6ubuntu2~24.04) 13.3.0`

## Modules
- `core-dn1-4.1.1-os1.44.elemod`
- `convert-0.23-os1.44.elemod`

## Verification
- emu boot: PASS 2026-10-29 (`bash tests/boot-check.sh --extra-syx ...8Track-Engine2.syx`: stock + 1490 settle with clean logs, truncated negative refused)
- hardware: untested

## Release notes
Known issue: 1-voice cap — simultaneous custom-machine voices may cause
audio cracking under load; see docs/VOICE_OPTIMIZATION.md.

## Try in emulator
Run `run-8track-engine.sh` (Linux) or `run-8track-engine.bat` (Windows) at the repo root (first run: build with `--emu`).

## Flash
Hold [FUNC] while powering on, press [TRIG 4] (MIDI upgrade), send
`Digitone_OS1.44_8Track-Engine2.syx` with Elektron Transfer.
