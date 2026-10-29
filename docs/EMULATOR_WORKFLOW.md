# Running Digitone MK1 in the Emulator (`digiemu`)

`digiemu` allows you to boot the actual Digitone firmware on your PC with a fully interactive virtual front panel, active OLED screen, working encoders, and live 48 kHz FM synthesis rendering.

## 1. Prerequisites

1. **Python 3.10+ / `uv` package manager:**
   * Python and `uv` are already available on this system.
2. **Official Digitone OS file:**
   * `Digitone_and_Digitone_Keys_OS1.44.syx` is located in `D:\Elektron-MODS\firmware\`.
3. **Patched Unicorn Engine:**
   * Digitone's ColdFire emulation and EMAC DSP instructions require specific fixes that the stock Unicorn library does not support out of the box.
   * To build and install the patched Unicorn DLL on Windows (requires Visual Studio C++ build tools and CMake, both installed on this machine):
     ```powershell
     cd D:\Elektron-MODS\tools\digiemu
     powershell -ExecutionPolicy Bypass -File tools\install-patched-unicorn.ps1
     ```

## 2. Setting Up `digiemu`

Navigate to the tool directory:
```powershell
cd D:\Elektron-MODS\tools\digiemu
uv sync
```

## 3. Initializing and Booting the Digitone

### Step 1: Add Firmware
Run the portable runner to unpack the `.syx` and prepare the snapshot.
`--add` identifies the file, creates a firmware folder named
`<device>-<version>-<sha-prefix>`, and builds it in a first-run worker
(cold boot + ladder + intro + settle, ~25–35 s on first run):

```powershell
uv run python -m emu.portable --add D:\Elektron-MODS\firmware\Digitone_and_Digitone_Keys_OS1.44.syx
```

This creates `portable/firmware/dn1-1.44-d4f200d0/` (`d4f200d0` = first 8 hex
digits of the stock SHA-256 `d4f200d0…9659`).

### Step 2: First Boot & +Drive Initialization
The very first boot performs cold-boot tasks and formats a virtual +Drive (takes ~25-35 seconds on a modern CPU).
```powershell
uv run python -m emu.portable
```
Click **Play** in the launcher. Once the factory UI settles, it saves a snapshot so future boots start up instantly.

### Step 3: Direct Panel Launch (no launcher)
To launch the Digitone virtual panel directly on an already-built snapshot,
pass the snapshot folder (or `--syx` to build/open a `.syx` in one step):

```powershell
# Resume the stock snapshot built by --add:
uv run python -m emu.dnpanel portable\firmware\dn1-1.44-d4f200d0
# …or open a .syx directly (builds the snapshot if missing):
uv run python -m emu.dnpanel default --syx D:\Elektron-MODS\firmware\Digitone_and_Digitone_Keys_OS1.44.syx
```

Full CLI: `uv run python -m emu.dnpanel [snapshot] [--syx PATH] [--save-on-exit PATH] [--no-audio] [--app]`.

### Step 4: One-Click `.bat` Launchers (`--worker panel` workflow)
The repo root ships launchers that skip the GUI launcher and open the panel
in a `--worker panel` process directly on a pinned snapshot folder:

| Launcher | Snapshot folder | Firmware |
| :--- | :--- | :--- |
| `run-stock-digitone.bat` | `tools\digiemu\portable\firmware\dn1-1.44-d4f200d0` | Stock OS 1.44 |
| `run-modded-digitone.bat` | `tools\digiemu\portable\firmware\dn1-144s-02af17fd` | MODDED OS 144S (Release 0.1: Monomachine, Plaits MACRO, SOPHIE) |
| `run-emulator.bat` | — | Opens the launcher (`emu.portable` with no args); pick any firmware |

Each `.bat` runs:

```bat
".venv\Scripts\python.exe" -m emu.portable --worker panel "%~dp0tools\digiemu\portable\firmware\dn1-1.44-d4f200d0"
```

`--worker panel <fwdir>` resumes that folder's settled snapshot
(`choose_snapshot` picks `resume.snap`; exit 3 / "Rebuild needed" means the
snapshot no longer matches — re-run `--add` on the `.syx`). A third snapshot
already exists locally: `dn1-144s-12e89a30` (Synth 0.2, `12e89a30…4b486`).
Snapshot folders stay local (see `.gitignore`); never commit them.

## 4. Testing Patched Mod Firmwares

When you compile a custom mod or export a patched `.syx` from `elekloader`:
1. Save the custom file as `Digitone_MODDED.syx`.
2. Launch `digiemu` with the modded `.syx`:
   ```powershell
   uv run python -m emu.portable --add D:\Elektron-MODS\firmware\Digitone_MODDED.syx
   ```
3. Test your mod's menus, knobs, and sound output on your screen before flashing it to real hardware.

## 5. Fast iteration: resume, don't re-boot (converter workflow)

Cold boot (`--add`: extract + card + ladder + intro + settle, ~25-35 s)
happens **once per new `.syx`**. Every check after that resumes the
settled snapshot — never re-boots per scenario:

```bash
# once per build: settle + snapshot (writes dn1-<tag>-<hash8>/gui.snap)
cd tools/digiemu && .venv/bin/python -m emu.portable --add /path/to/build.syx --yes
# every manual check after: resume the settled snapshot instantly
cd tools/digiemu && .venv/bin/python -m emu.dnpanel portable/firmware/dn1-<tag>-<hash8>
# (Windows twins: .venv\Scripts\python.exe, backslash paths)
```

Rules that keep iteration under 60 s (full reasoning in
`openspec/changes/archive/2026-10-27-8tracksim/probe-workflow.md`):
- One settled `gui.snap` per firmware hash (`dn1-<tag>-<hash8>`); rebuild
  with `--add` only on exit 3 / "Rebuild needed".
- Manual panel checks (modal, browser, voice menu, b-labels, synth pages,
  mutes, sequencer) run in the resumed panel — no headless session needed.
- Headless `Session` is regression-only (CNV8 scan, MIDI byte-identity vs
  checked-in `tests/probe/baselines/stock.json`, framebuffer hash); single
  session per scenario, reset via clean-project reload, 1–2 bar captures,
  poll-until-stable instead of fixed PLAY sleeps.
- Stock baseline is captured once (`harness.py --refresh-baseline`), not re-measured per run.
- Entry point: `tests/probe/harness.py [--scenario NAME...] [--out FILE]`
  (run from `tools/digiemu` with its venv); full-run evidence per release.

