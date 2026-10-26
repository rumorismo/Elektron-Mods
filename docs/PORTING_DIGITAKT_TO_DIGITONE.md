# Porting Digitakt MK1 Modules to Digitone MK1: Architecture & UI/UX Guide

This guide documents the architectural, DSP, control-surface, parameter-slot, and UI/UX differences between the **Elektron Digitakt MK1** (OS 1.53 / 1.54) and the **Elektron Digitone MK1 / Keys** (OS 1.43 / 1.44), along proven best practices for porting community modules (`digi1_mods`, `digisophie`, `digitables`, etc.) across the two platforms using `elekloader`.

---

## 1. Hardware & Audio Pipeline Comparison

| Subsystem | Digitakt MK1 (`digitakt-mk1`) | Digitone MK1 (`digitone-mk1`) | Porting Impact |
| :--- | :--- | :--- | :--- |
| **Main CPU (CPU #1)** | 1× Freescale ColdFire **MCF54455** (`m68k`, 250 MHz, hardware EMAC) | 1× Freescale ColdFire **MCF5441x** (`m68k`, 250 MHz, hardware EMAC) | Pure C and ColdFire assembly (`-mcpu=54455`) compile identically on both devices. |
| **Voice / FM DSP (CPU #2)** | None (Single-CPU architecture; CPU #1 renders all 8 sample tracks) | 2nd Freescale ColdFire **MCF5441x** running Section 7 (renders 8× 4-Op FM voices + FM AMP envelope) | On Digitone, CPU #2 sends 32-sample blocks (`Q1.31`) via 128 KB Dual-Port Shared RAM (eDMA ch 47) to CPU #1 SRAM (`0x80004110`, `fw_voices`). |
| **Track / Voice Topology** | **8 Audio Tracks** = **8 Monophonic Voices** (1 fixed voice per track) + 8 MIDI Tracks | **4 Synth Tracks (`T1–T4`)** dynamically sharing a **pool of 8 Voices (`0–7`)** + 4 MIDI Tracks | Digitakt machines render per-track (`0–7`); Digitone `machines-dn1` renders per-voice (`0–7`, where `v->track` is `0–3`). |
| **Voice Signal Chain** | `SRC` Machine → Multimode Filter → Base/Width Filter → Overdrive → AMP Envelope → Pan / Sends | CPU #2 FM *(or `machines-dn1` override on CPU #1)* → Multimode Filter → Base/Width Filter → Overdrive → Pan / Chorus / Delay / Reverb | Because CPU #2 applies the AMP envelope *inside* the FM DSP, `machines-dn1` applies a software ADSR envelope (slots `66–69`) + velocity on CPU #1 right after `m->render()`. |
| **Peak Audio Level** | `int16_t` (`Q15`, `±32767`) per sample | `int32_t` (`Q1.31`) with nominal peak `DNM_PEAK = 0x08000000` (`Q15 << 12`) | Shift 16-bit `Q15` Digitakt synth outputs left by 12 (`block[i] = ((int32_t)out[i]) << 12`) to match stock FM loudness. |
| **Mod RAM Budget** | `128 KB` (or `256 KB` with `core 4.0`) + `2,304 B` `.fast` SRAM | `1.25 MB` (`0x43EC0000` with `core-dn1 4.0+`) | Digitone has **5× more DDR RAM** for mods than Digitakt, so large lookup tables and multi-engine packs (`dnmono` + `fxkit` + 7 pedals) fit easily with >880 KB to spare. |

---

## 2. Front-Panel Buttons & Navigation Differences

A major pitfall when porting Digitakt mods to Digitone is assuming the same button combinations exist:

| Action / Concept | Digitakt MK1 | Digitone MK1 | Best Practice on Digitone |
| :--- | :--- | :--- | :--- |
| **Synth / Source Pages** | 1 button: **`[SRC]`** | 2 buttons: **`[SYN1]`** and **`[SYN2]`** | Map Octave (`OCT`) to `SYN1` Knob A, and map main `0–127` synthesis controls to `SYN2` Knobs A–H. |
| **`FUNC` + Synth Button** | **`[FUNC] + [SRC]`** opens the Machine Picker | **`[FUNC] + [SYN1]`** = **Master Chorus**<br>**`[FUNC] + [SYN2]`** = **Master Delay**<br>**`[FUNC] + [FLTR]`** = **Master Reverb**<br>**`[FUNC] + [PTN]`** = **Arpeggiator** | **Never hijack `FUNC + SYN1/SYN2/FLTR/PTN`** on Digitone, or you will break access to Master FX or the Arpeggiator. |
| **Opening the Mod / Machine Menu** | **`[FUNC] + [SRC]`** *(or triple-tap `[SRC]`)* | **Long-press Track button `[T1]`–`[T4]` (~0.4s)** (`ev_hold` / `core_menu`) | Keep **`MACHINES` at `order: 1`** in `core_menu` so holding `T1–T4` immediately highlights `1: MACHINES` as the first tile. |
| **Track Selection** | Dedicated buttons `[TRK 1]`–`[TRK 8]` (or `[FUNC] + [TRIG 1–16]`) | Dedicated buttons **`[T1]`–`[T4]`** for Synth Tracks (`0–3`), plus **`[MIDI]` + `[T1]`–`[T4]`** | Always check `track >= 0 && track < 4` when indexing `fw_kit` sound slots. |

---

## 3. Parameter Ranges: Why `SYN1` and `SYN2` Differ on Digitone

On the Digitakt, all 7 machine parameters on `[SRC]` (`B–H`) have a uniform **`0..127`** range (`8.8` fixed point: `0 .. 127<<8`).

On the Digitone, `machines-dn1` borrows the existing FM sound slots so that **Parameter Locks (p-locks), LFO destinations, Sound Pool presets, and MIDI CCs** work automatically without corrupting stock projects. Because the DSP still reads those slots, each knob retains its stock min/max range:

### `SYN1` Page 1 (`knobs[0..7]`) — Non-Uniform FM Ranges
| Knob Index | Encoder | Stock FM Param | Sound Slot | Stock Range (`value >> 8`) | Recommended Use in Custom Machines |
| :---: | :---: | :---: | :---: | :--- | :--- |
| `0` | **A** | `ALGO` | `17` | **`0..7`** (8 detents) | **`OCT`** (Octave transpose: `(val >> 8) - 3` = `-3..+4`) |
| `1` | **B** | `C` Ratio | `18` | `0..18` (19 indices) | Leave unused (`0`), or use for coarse selector |
| `2` | **C** | `A` Ratio | `19` | `0..35` (36 indices) | Leave unused (`0`) |
| `3` | **D** | `B` Ratio | `20` | `0..323` | Leave unused (`0`) |
| `4` | **E** | `HARM` | `21` | `-26..+26` | Leave unused (`0`), or bipolar fine control |
| `5` | **F** | `DTUN` | `22` | **`0..127`** | Auxiliary `0..127` control (e.g. `TIMB` on `MACRO`, `FOLD` on `SINE`) |
| `6` | **G** | `FDBK` | `23` | **`0..127`** | Auxiliary `0..127` control (e.g. `MORP` on `MACRO`, `SUB` on `SINE`) |
| `7` | **H** | `MIX` | `24` | `-63..+63` | Leave unused (`0`), or bipolar balance |

### `SYN2` Page 1 (`knobs[8..15]`) — Uniform `0..127` Ranges
| Knob Index | Encoder | Stock FM Param | Sound Slot | Stock Range (`value >> 8`) | Recommended Use in Custom Machines |
| :---: | :---: | :---: | :---: | :---: | :--- |
| `8..15` | **A–H** | Operator Env / Level | `27..34` | **All `0..127`** | **Primary synthesis parameters** (`p[0..7]` ported directly from Digitakt `SRC` knobs `B–H`) |

### `SYN1` & `SYN2` Page 2 (`knobs[16..31]`, enabled with `DNM_PAGES2`)
- `16..19` (`SYN1 2/2 A–D`): `0..127.99` in `1/256` steps (default `64.00`) — ideal for high-resolution fine tune (`FINE`).
- `24, 28` (`SYN2 2/2 A, E`): `0..127`.
- `25, 26, 29, 30` (`SYN2 2/2 B, C, F, G`): `0..1` binary switches.
- `27` (`SYN2 2/2 D`): `0..4` (5 choices).

---

## 4. GUI / OLED Restyling Best Practices (`SYN1` & `SYN2` Overlay)

### The Stock Digitone UI Problem
When a track uses a custom machine, `core_param_override` relabels the parameter names and popup toasts, **but the stock Digitone view still paints FM graphics on the screen**:
1. **`SYN1` Page 1** paints the **4-Operator FM Algorithm Diagram** across the center of the screen (which morphs when turning Knob A `OCT`!).
2. **`SYN2` Page 1** paints **two large FM Operator Envelope Graphs** across the top half of the screen, truncates the 8 bottom labels to **3 characters** (`ENG` instead of `ENGN`, `MOD` instead of `MODEL`), and hides formatted text (`WSHAPE`, `FUSE`, `MAJ7`, `OO`) until a knob is actively turned.

### The Solution (`machines-dn1` 4×2 Grid Overlay)
In [`tools/elekloader/mods/machines-dn1/machines.c`](../tools/elekloader/mods/machines-dn1/machines.c), we subscribe to `ev_draw`, `ev_tick`, `ev_key`, and `ev_enc`:
1. **Strict Gating (Zero Loss of Stock Functionality)**:
   - If the active track is set to stock **`FM` (`mid == 0`)**, `dnm_draw` returns immediately—preserving 100% of the stock FM Algorithm diagram and Operator Envelope graphs.
   - If any modal, menu, sound browser, or `[FUNC]` copy/paste/clear toast is active (`bottom != top` or `dnm_msg_suppressed()`), `dnm_draw` yields immediately so popups are never covered.
2. **Digitakt-Style 4×2 Parameter Grid on Custom Machine Tracks**:
   - Clears only the page content area (`x = 15..127, y = 11..63`), keeping the top status bar (including `digihealth` CPU/DSP/RAM meters), page title bar, and left `SYN1`/`SYN2` indicator rail untouched.
   - Draws all 8 parameters (`A–D` top row, `E–H` bottom row) with:
     - Full **5-character labels** (`MODEL`, `COLOR`, `METAL`, `SWEEP`, `ENGN`, `HARM`, `TIMB`, `MORP`).
     - **Always-visible formatted value text** (`WSHAPE`, `2OP FM`, `FUSE`, `SHARD`, `MAJ7`, `OO`, `16'`).
     - **Automatic unipolar or bipolar progress bars** computed from `dnm_knob_range(k, &min, &max)`.
     - **Active encoder highlight box** when turning a knob.
     - **Grid Recording p-lock support**: holding a trig step `[1]–[16]` reads the step's locked value from `fw_pattern` and inverts the cell (`XOR` fill) just like native Elektron parameter locks.
3. **`SYN1` Machine Header Badge**:
   - On `SYN1` Page 1, when knobs `B–D` are unused by a machine, the overlay draws a framed header badge (`MACH: <NAME>` / `SYN2 -> PARAMS`) so the user immediately sees which engine is loaded on the track and knows that `SYN2` holds the main controls.

---

## 5. CPU #1 Load & EMAC Register Safety Checklist

When porting a Digitakt DSP engine (`mono.c`, `macro.c`, `sophie.c`; `sh101.c` reference-only, not shipped — see note below) to Digitone:

1. **Always Save and Restore ColdFire EMAC Registers**:
   - The Digitone's audio interrupt on CPU #1 uses the ColdFire hardware Multiply-Accumulate unit (`MACSR`, `ACC0`, `ACCEXT01`) in its per-voice multimode filters right after `ev_render_voices`.
   - Any custom machine using `mac.l` / `msac.l` **must** wrap its render block in `emac_enter()` and `emac_leave()` to save and restore `MACSR`, `ACC0`, and `ACCEXT01`.
2. **Account for Polyphony vs. Per-Track Monophony**:
   - On Digitakt, a track only ever triggers 1 voice. On Digitone, playing a 4-note chord on a track calls your machine's `render()` **4 times per audio block** (once for each allocated voice `0..7`).
   - For lightweight engines (`SINE`, `SAW`, `PULSE`, `NOISE`, `PSIN`), polyphonic voice allocation works great across multiple voices.
   - > **SH-101 removed from shipping builds:** `modules/dn-monomachine/sh101.c` is retained as source reference only — it is **not** registered in the `dnmono.c` machine table (which ships SAW, PULSE, ENS, CHORD, VO-6, NOISE, PSIN, MACRO, SOPHIE: IDs 10–16, 18, 19) and is not described in the dnmono `mod.json`. Do not port new Digitakt engines onto SH-101 knob layouts; use the shipped `MACRO`/`SINE`-style `SYN2` `0..127` slots.
   - For CPU-intensive physical/FM percussion models (`SOPHIE`), use a **per-track newest-wins voice cap** (`rank >= 1` per `v->track` outputs silence) so rapid trigs or chords on a percussion track never starve CPU #1, while all 4 tracks can still play simultaneously.
3. **Never Run Plain `uv sync` in `tools/digiemu`**:
   - `digiemu` requires the custom-compiled `unicorn.dll` (built with Visual Studio 2026 via `tools\install-patched-unicorn.ps1`) for accurate ColdFire EMAC and CCR emulation. A plain `uv sync` installs the stock Unicorn wheel, which lacks the EMAC/CCR patches and silently mistimes audio and corrupts MAC-unit DSP results — always (re)run `tools\install-patched-unicorn.ps1` after any sync or fresh clone (see `docs/EMULATOR_WORKFLOW.md`).
