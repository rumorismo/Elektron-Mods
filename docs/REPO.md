# REPO Map — Elektron-MODS

Home for all Digitone MK1 firmware mods, releases, and tests.

## Layout
- `firmware/releases/v1.44-8tracks-0.7/` — canonical 8-track build 1447 (`Digitone_OS1.44_8Tracks7.syx`, README, `.syx.json`, `.map.json`)
- `firmware/releases/8 tracks/` — same 1447 build, kept for compat
- `firmware/releases/archive/` — deduped `8 tracks - Copy*` iterations
- `firmware/Digitone_and_Digitone_Keys_OS1.44.syx` — stock OS, local only (measured SHA-256 `d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659`; README previously listed `...bc67...`, 8-track build manifest used `...bc67...` — re-verify stock download before next build)
- `modules/dn-monomachine/` — Machine source reference
- `modules/digitables/`, `modules/digisophie/`, `modules/digi1_mods/` — reference mods
- `tools/elekloader/` — patcher + `mods/tracks-dn1/` source (nested clone, local)
- `tools/digiemu/` — emulator (nested clone, `portable/` snapshots stay local)
- `openspec/changes/init-firmware-repo/` — this repo-init plan

Binaries (`*.syx`, `*.bin`, `*.elemod`, `*.map.json`) are never committed per `.gitignore`.

## Build (Windows + WSL)
WSL Ubuntu provides `m68k-linux-gnu-gcc` for ColdFire `-mcpu=54455`.
Edit in `d:\Elektron-MODS`, compile via WSL, link via Python:
```powershell
wsl bash -c "cd /mnt/d/Elektron-MODS/tools/elekloader && PYTHONPATH=. python3 -m elekloader.sdk.build mods/tracks-dn1 --stock ../../firmware/Digitone_and_Digitone_Keys_OS1.44.syx --out mods/tracks-dn1/out/tracks-1.4-os1.44.elemod"
```
Then link/patch to `.syx` with `build_8tracks.py` (elekloader.patch).

## Test
```powershell
.\tests\smoke.ps1
```
Checks: stock hash, canonical release manifest present, no firmware tracked by git, WSL toolchain present.

## Known issue
tracks 1.4 `trk_queue` fires background-bank notes on top of foreground (up to 8 tracks on 8 voices) + dnmono/dnsine load exceeds ~22k-tick headroom → voice cracking. Fix is a separate change (per-track steal, 2-voice cap, REL cutoff, eco mode).
