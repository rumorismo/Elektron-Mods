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
Run the portable runner to unpack the `.syx` and prepare the snapshot:
```powershell
uv run python -m emu.portable --add D:\Elektron-MODS\firmware\Digitone_and_Digitone_Keys_OS1.44.syx
```

### Step 2: First Boot & +Drive Initialization
The very first boot performs cold-boot tasks and formats a virtual +Drive (takes ~25-35 seconds on a modern CPU).
```powershell
uv run python -m emu.portable
```
Click **Play** in the launcher. Once the factory UI settles, it saves a snapshot so future boots start up instantly.

### Step 3: Direct Panel Launch
To launch the Digitone virtual panel directly:
```powershell
uv run python -m emu.dnpanel default --syx D:\Elektron-MODS\firmware\Digitone_and_Digitone_Keys_OS1.44.syx
```

## 4. Testing Patched Mod Firmwares

When you compile a custom mod or export a patched `.syx` from `elekloader`:
1. Save the custom file as `Digitone_MODDED.syx`.
2. Launch `digiemu` with the modded `.syx`:
   ```powershell
   uv run python -m emu.portable --add D:\Elektron-MODS\firmware\Digitone_MODDED.syx
   ```
3. Test your mod's menus, knobs, and sound output on your screen before flashing it to real hardware.

