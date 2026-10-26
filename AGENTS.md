# AGENTS.md — Elektron-MODS (Digitone MK1 firmware mods)

Digitone MK1 custom firmware project. This repo holds source, method, and docs; firmware binaries stay local. Work is planned and tracked via OpenSpec (`openspec/`).

## Rules that will bite you

- **Never commit firmware.** `*.syx`, `*.bin`, `*.elemod`, `*.map.json` are gitignored; `tests/smoke.ps1` fails if any is tracked. The stock OS is *not* an exception: it stays local, pinned by SHA-256 `d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659`.
- **`tools/elekloader/` and `tools/digiemu/` are upstream clones** with their own rules: read `tools/elekloader/AGENTS.md` before touching anything inside (never weaken its checks; the writer must stay byte-exact; Python changes need the `js/` port updated). They are untracked at this root — never `git add tools/`.
- **`modules/digi1_mods/`, `modules/digisophie/`, `modules/digitables/` are read-only reference clones.** New ported modules are born in `modules/dn-<name>/` (self-contained: own `mod.json`, sources; compiled in place — see `docs/RELEASE_METHOD.md`).
- **`firmware/releases/archive/` is frozen.** Never rebuild or edit archived releases. Active releases go in `firmware/releases/v1.44-<slug>-0.<N>/` via `tools/release.py`, and the version tag must not collide with any active or archived release.
- **Voice budget truth:** the shipped cap is **1** custom voice (`newer_all >= 1` in `tools/elekloader/mods/machines-dn1/machines.c`). `docs/VOICE_OPTIMIZATION.md` explains why; do not regress to 2 without re-measuring. Cracking/audio verdicts need hardware — the emulator proves code paths only, never timing or audio.

## Commands

- Verify everything: `powershell -ExecutionPolicy Bypass -File tests/smoke.ps1` (stock hash, release manifests, launcher snapshots, no firmware tracked, WSL toolchain). Run this before committing.
- Cross-compile a mod (ColdFire, WSL Ubuntu has `m68k-linux-gnu-gcc`):
  ```
  wsl bash -c "cd /mnt/d/Elektron-MODS/tools/elekloader && PYTHONPATH=. python3 -m elekloader.sdk.build mods/<name> --stock ../../firmware/Digitone_and_Digitone_Keys_OS1.44.syx --out mods/<name>/out"
  ```
  Then copy the `.elemod` into `firmware/elemods/` (the curated registry; stale versions go to its local `archive/`).
- Build a release: `python3 tools/release.py --slug <slug> --num <N> --tag <tag> --preset 8tracks [--emu]` — links elemods, writes release folder + manifests + README, and with `--emu` the digiemu snapshot + `run-<slug>.bat`.
- Try in emulator: `run-<slug>.bat` (or `run-stock-digitone.bat`). digiemu's `--add` writes a snapshot `dn1-<tag>-<hash8>` only after the factory UI settles — snapshot-within-timeout is the boot oracle.

## Environment gotchas

- Windows PowerShell: no GNU tools (`head`, `tail`, `sed` are missing — use `Select-Object`). Quote paths with spaces (`"firmware/releases/8 tracks"`).
- digiemu needs the patched `unicorn.dll`: never plain `uv sync` in `tools/digiemu/`; use `tools\install-patched-unicorn.ps1` if the venv breaks. `portable/` holds multi-GB snapshots and stays local.
- Git: origin `https://github.com/rumorismo/Elektron-Mods.git`, branch `main`. `gh` is installed and authed as `rumorismo`.

## OpenSpec usage

- Changes live in `openspec/changes/`; capabilities sync to `openspec/specs/` at archive time. Workflow commands: `/opsx-explore`, `/opsx-propose`, `/opsx-apply`, `/opsx-update`, `/opsx-archive` (in `.opencode/commands/`).
- CLI syntax trap: `openspec validate <name> --type change` (positional name; there is no `--change` flag). `openspec list` shows in-flight changes; `openspec list --specs` shows capabilities.
- Archive order matters: a change that modifies a capability can only archive after the capability's main spec exists (i.e., after the change that introduced it archives).

## Where things are documented (don't duplicate, point)

- `docs/RELEASE_METHOD.md` — the 6-step release loop (prepare → link → smoke → try → commit → flash)
- `docs/REPO.md` — layout map; `docs/ARCHITECTURE.md` — hardware/OS hooks; `docs/MODDING_GUIDE.md` — build/lint/patch loop; `docs/EMULATOR_WORKFLOW.md` — digiemu flows; `docs/PORTING_DIGITAKT_TO_DIGITONE.md` — porting rules; `docs/VOICE_OPTIMIZATION.md` — CPU budget math
- `todo.txt` — user's feature wishlist (arp-to-midi, global fx, sticky browser); becomes OpenSpec changes, not drive-by edits
