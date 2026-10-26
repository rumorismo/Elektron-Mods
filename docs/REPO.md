# REPO Map — Elektron-MODS

Home for all Digitone MK1 firmware mods, releases, and tests.

## Layout
- `firmware/releases/v1.44-8tracks-0.7/` — canonical 8-track build 1447 (`Digitone_OS1.44_8Tracks7.syx`, README, `.syx.json`, `.map.json`)
- `firmware/releases/8 tracks/` — same 1447 build, kept for compat
- `firmware/releases/v1.44-synth-0.1/` — pure-synth build (Synth 0.1: no pedal FX)
- `firmware/releases/v1.44-synth-0.2/` — pure-synth build (Synth 0.2: strict 1-voice cap)
- `firmware/releases/v1.44+-0.1/` — SuperPack build (0.1: all mods)
- `firmware/releases/v1.44+-0.2/` — SuperPack build (0.2: strict 1-voice cap)
- `firmware/releases/archive/` — deduped `8 tracks - Copy*` iterations (2–6)
- `firmware/Digitone_and_Digitone_Keys_OS1.44.syx` — stock OS, local only (measured SHA-256 `d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659`, matches `tests/smoke.ps1` and `docs/ARCHITECTURE.md`)
- `modules/dn-monomachine/` — Machine source reference
- `modules/digitables/`, `modules/digisophie/`, `modules/digi1_mods/` — reference mods
- `tools/elekloader/` — patcher + `mods/tracks-dn1/` source (nested clone, local)
- `tools/digiemu/` — emulator (nested clone, `portable/` snapshots stay local)
- `openspec/changes/init-firmware-repo/specs/firmware-repo/spec.md` — this repo-init plan's spec

Binaries (`*.syx`, `*.bin`, `*.elemod`, `*.map.json`) are never committed per `.gitignore`.

## Build (Windows + WSL)
WSL Ubuntu provides `m68k-linux-gnu-gcc` for ColdFire `-mcpu=54455`.
Edit in `d:\Elektron-MODS`, compile via WSL, link via Python.
`sdk.build --out` takes a **directory** (default `<moddir>/out`):
```powershell
wsl bash -c "cd /mnt/d/Elektron-MODS/tools/elekloader && PYTHONPATH=. python3 -m elekloader.sdk.build mods/tracks-dn1 --stock ../../firmware/Digitone_and_Digitone_Keys_OS1.44.syx --out mods/tracks-dn1/out"
```
Then link/patch to `.syx` with one of the release link scripts (each takes an
optional release iteration, default `0.1`; all run `elekloader.patch --stock …
--mod … --out … --version …` under the hood):
- `tools/elekloader/build_8tracks.py [N]` → `firmware/releases/v1.44-8tracks-0.N/` + `8 tracks/` (version `144N`; core + machines + dnmono + dnsine + dnthru + digihealth + tracks)
- `tools/elekloader/build_synth.py [N]` → `firmware/releases/v1.44-synth-0.N/` (version `144S`; pure synth, no pedals)
- `tools/elekloader/build_syx.py [N]` → `firmware/releases/v1.44+-0.N/` (version `144+`; every elemod = SuperPack)

## Test
```powershell
.\tests\smoke.ps1
```
Checks: stock hash, every release dir's manifest (`.syx.json` + `.map.json`) and README present and non-truncated, `.bat` snapshot folders exist, no firmware tracked by git, WSL toolchain present.

## Known issue
tracks 1.4 `trk_queue` fires background-bank notes on top of foreground (up to 8 tracks on 8 voices) + dnmono/dnsine load exceeds ~22k-tick headroom → voice cracking. Fix is a separate change (per-track steal, 1-voice cap, REL cutoff, eco mode).
