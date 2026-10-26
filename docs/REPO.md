# REPO Map — Elektron-MODS

Home for all Digitone MK1 firmware mods, releases, and tests.

## Layout
- `firmware/releases/v1.44-<slug>-0.N/` — active releases, one folder per module-set flavor (created by `tools/release.py`)
- `firmware/releases/archive/` — frozen history: 8tracks 0.7, `8 tracks`, synth 0.1/0.2, + 0.1/0.2, `8 tracks - Copy*`. Never rebuilt or edited.
- `firmware/Digitone_and_Digitone_Keys_OS1.44.syx` — stock OS, local only (measured SHA-256 `d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659`, matches `tests/smoke.ps1` and `docs/ARCHITECTURE.md`)
- `firmware/elemods/` — curated registry of compiled module binaries the release script links (index: `firmware/elemods/README.md`; stale versions in `firmware/elemods/archive/`)
- `modules/dn-monomachine/` — ported machine modules (new Digitone modules born here)
- `modules/digitables/`, `modules/digisophie/`, `modules/digi1_mods/` — reference/upstream Digitakt sources (read-only)
- `tools/release.py` — generic release driver (see `docs/RELEASE_METHOD.md`)
- `tools/elekloader/` — patcher + `mods/tracks-dn1/` source (nested clone, local)
- `tools/digiemu/` — emulator (nested clone, `portable/` snapshots stay local)
- `docs/RELEASE_METHOD.md` — the release method every new release follows (6 steps + Verification pyramid)
- `openspec/specs/firmware-repo/spec.md` — repo capability spec

Binaries (`*.syx`, `*.bin`, `*.elemod`, `*.map.json`) are never committed per `.gitignore`.

## Build (Windows + WSL)
Follow `docs/RELEASE_METHOD.md` (the release method). In short: compile changed modules via WSL, then link a release with the driver:
```powershell
python3 tools/release.py --slug 8tracks --num 8 --tag 1448 --preset 8tracks --emu
```
That verifies the stock hash, links the elemods, writes `firmware/releases/v1.44-8tracks-0.8/` (`.syx` + manifests + README) and, with `--emu`, the digiemu snapshot + `run-8tracks.bat`.

## Test
```powershell
.\tests\smoke.ps1
```
Checks: stock hash, every release dir's manifest (`.syx.json` + `.map.json`) and README present and non-truncated, `.bat` snapshot folders exist, no firmware tracked by git, WSL toolchain present.

## Known issue
tracks 1.4 `trk_queue` fires background-bank notes on top of foreground (up to 8 tracks on 8 voices) + dnmono/dnsine load exceeds ~22k-tick headroom → voice cracking. Fix is a separate change (per-track steal, 1-voice cap, REL cutoff, eco mode).
