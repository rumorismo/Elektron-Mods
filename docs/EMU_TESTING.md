# Emulator testing notes (spike findings)

Read-only investigation, no builds or emulator runs. Code refs are `tools/digiemu/emu/*.py`.

## 3.1 Snapshot-oracle (validated in code — TRUSTED for L1)

- `python -m emu.portable --add <syx>` → `add_firmware()` (`portable.py:1969`, flow `1976–2017`):
  plan → `prepare_folder()` copies syx under canonical name, records `firmware.json`
  (`1398–1423`) → `build_in_worker()` spawns `--worker first-run <fwdir>` child
  (`1083,1888`), relays JSON lines, maps child crash to failure + log path (`1909–1930`).
- Exit codes: `EXIT_OK=0`, `EXIT_NOT_READY=3`, `EXIT_NEEDS_YES=4` (untested/custom
  release without `--yes`, `1998–2001`), `EXIT_BUSY=5` (`portable.py:200–206`).
  An `--add` on an already-READY folder early-returns "already set up" (`1983–1997`)
  — boot-check must use a fresh `--home` temp dir and assert on a new snapshot dir,
  never on exit code alone.
- Snapshot naming: `emu/release.py:339 make_slug()` → `<short>-<version>-<sha256[:8]>`
  (`340–355`). Stock 1.44 = `dn1-1.44-d4f200d0` (`EMULATOR_WORKFLOW.md:39-40`).
- "Factory UI settles" = `emu/bootstrap.py:first_run()` pipeline (`1448`, stages
  extract → card → ladder → intro → settle). `settle_ui()` (`732`): the last 120
  consecutive untorn frames are all main-UI frames, checked per chunk (`750`,
  `SETTLE` budgets at `114`, ceiling 3000M instructions). Reference: cold boot
  ~130–160M instr (2–4 s), intro ~8 s, first boot + settle ~13 s at ~1300–1400M
  instr, whole setup ~25–38 s (`DIGITONE-MK1.md:28-45`, `bootstrap.py:1271`).
  Boot-check wall timeout 300 s (early exit on result record) is generous without
  masking "never settles" (the historical 1.44-without-DSP failure surfaced exactly
  as `not settled after 3000M instructions`).
- Pixel-settle is not the whole gate: `accept_settled()` (`1184`) also requires the
  first-boot card layout (`check_card`: sector-0 `BEEFBACE`, protect record, project
  slot 0 — `1017–1028`) and `check_ram` DSP/main words (`error_u32==0`,
  `progress_done==progress_total`, `mounted_u32==1`, `dsp_running_u32==2 (running)` —
  `1148–1181`).
- Snapshot written only after successful settle — CONFIRMED: settle block
  (`1698–1743`) raises `StepFailed` when `settled_at`/`saved` is None (`1704–1709`);
  on `StepFailed`, `_set_aside()` renames to `gui.snap.rejected` (`1253,1716–1722`);
  stamp + `state['card']`/`first_boot` recorded only after (`1732–1743`).
  `FirmwarePaths.gui = <root>/snapshots/<syx-stem>/gui.snap` (`bootstrap.py:206–254`).
  Caveat: `resume.snap` from a *panel* session is written on clean exit, NOT gated
  on acceptance (`_run_panel`, `portable.py:1717–1737`) — L1 asserts on `gui.snap`
  from `--add`/first-run only.
- Oracle log: `<firmware>/<slug>/logs/first-run.log` — stage events, tracebacks
  (`portable.py:1649–1652`), `worker failed before the build` (`1674`), crash
  exit-code line (`1921–1923`). `logs/panel.log` is panel sessions (`1819,1787`);
  `<APP_ROOT>/logs/launcher.log` is launcher-only. `tests/boot-check.ps1` greps
  `first-run.log` for: `not settled after`, `NOT SETTLED after`, `no live user
  interface after`, `first boot did not finish`, `+Drive did not come up`,
  `first-boot job reports error|stopped at|sample volume is not mounted|DSP did
  not come up|is not in the snapshot`, `Traceback|StepFailed|was killed|crashed|
  LOAD_FAILED|INCOMPATIBLE`, plus `truncated or damaged` (expected only in the
  negative test — `release.py:424–428`).

## 5. Converter probe contract (GUI-first, regression-only headless)

Manual panel (user, resumed `dn1-<tag>-<hash8>`) covers: confirm modal,
convert/flip-back, browser, voice menu, b-labels, synth pages, mutes,
sequencer. Record concrete values in the release README; audio verdicts
stay `hw-pending`.

Headless probe (home `tests/probe/`: `harness.py` + `baselines/stock.json`,
scenario legs in `cnv_*.py`) asserts only:
- CNV8 scan with the `<=2` validation guard,
- MIDI byte-sink vs cached stock baseline (`--refresh-baseline` only when
  the fixture changes; never re-measure stock per run),
- framebuffer hash (screens kept as hash; raw/PNG only on failure),
- memory peeks at `FW_PATTERN 0x4138f214`, `FW_KIT 0x4138f220`,
  `FW_ACTIVE_TRACK 0x41368ce0`, mutes `+0x16108`.

Mechanics (built as `tests/probe/harness.py`; full reasoning in
`openspec/changes/archive/2026-10-27-8tracksim/probe-workflow.md`):
snapshot reuse (rebuild on exit 3 only), single `Session` per scenario
with clean-project-reload reset, 1–2 bar captures with
poll-until-stable settle (no fixed 8 s PLAYs), one JSON report per run.
Target: behavior-check iteration well under 60 s; L1 cold boot stays a
one-time ~30–80 s cost per new build. Anything audible (mix, stealing,
mute feel) and all hardware verdicts stay manual per the evidence hierarchy.

## Evaluation record (2026-10-26, strict gate in force)

- Stock OS 1.44: PASS (`dn1-1.44-d4f200d0`, `gui.snap` + clean `first-run.log`).
- Archived 8tracks-0.7 (tag 1447, tracks-1.4): FAIL —
  `NOT SETTLED after 3000M instructions -- the +Drive overlay is still being
  drawn` (14439 frames, 4803 overlays, quiet run 2). No valid `gui.snap`.
  Standing interpretation: the oracle works; the build does not settle in-emu
  (suspect: tracks HUD popup card / +Drive overlay never dismissed — possibly an
  emu timing artifact, possibly a real stuck overlay). No release based on
  tracks-1.4 ships until a rebuild passes L1; the 8tracks-0.8 build conversation
  owns that verdict. Run it explicitly any time with:
  `powershell -ExecutionPolicy Bypass -File tests/boot-check.ps1 -ExtraSyx
  firmware/releases/archive/v1.44-8tracks-0.7/Digitone_OS1.44_8Tracks7.syx`.
- Deliberately truncated syx: correctly refused (`truncated or damaged`, no snap).

## 4.1 Input injection (drivable paths, most useful first)

1. **`emu.session.Session` + `emu.fwcompare` script language (headless, repeatable)
   — primary automation path.** `Session(snapshot, syx, ...)` builds the window's
   machine headlessly, steps in emulated time (`session.py:1–36,79–128`);
   `press/release/tap/turn/run_ms/screen_at/close` (`184–360`); `run_script`
   verbs `wait/tap/press/release/turn/snap` (`371–395`); grammar `parse_script`
   (`fwcompare.py:90–129`: `wait <ms>`, `tap <KEY> [HOLD] [AFTER]`, `press/release/
   turn/snap`, `#` comments; `script_problems` validates names `132–152`).
   Batch: `python -m emu.fwcompare STOCK CUSTOM [--script FILE] [--out DIR]`
   (`361–390`); full gate `python -m emu.fwcheck` (`fwcheck.py:651–665`);
   `portable --check SYX [--baseline STOCK] [--timing]` → `worker_check` →
   `fwcheck.run_check` (`portable.py:2453–2526,2546–2567`).
2. **`emu.panelin` wire-level injection (headless, finest-grained).** `feed()`
   writes the panel UART8 ring + raises vector 154 (`panelin.py:54–70`);
   `buttons/press/release/encoder` + `encode_*` (`73–134`); `Held(device)` chord
   tracking (`241–305`); `device.wire_for/code_for` (`225–239`).
   `Session` uses this internally (`_feed` → `panelin.feed`, `session.py:252–253`).
3. **`emu.midi.MidiIn` MIDI-in path (headless or GUI-live).** `feed()` writes the
   eDMA-ch36 ring + raises vector 156 (`midi.py:96–106`); `put()` from any thread,
   `deliver(m)` at chunk boundaries or `attach(m, ips)` + `step/service` as
   `longrun.spin` source (`109–348`). Host `HostMidi` via python-rtmidi (`--extra
   midi`; `DIGIEMU_MIDI_IN/OUT` selectors; `561–695`). Firmware-side filter:
   `MIDI CONFIG > PORT CONFIG > INPUT FROM` must include MIDI (`midi.py:12–16`).
4. **GUI panel (interactive/manual, NOT scripted).** `emu.dnpanel` (`dnpanel.py:1–106`)
   over `emu.dtpanel` (`dtpanel.py:28–64,1041–1323`); no `--script`/headless flag
   on the panel itself. Exit codes 0/2/4/5/6 (`dtpanel.py:99–106`). Until L2
   automation lands, behavior checks run manually — see `RELEASE_METHOD.md` B1–B4.

## 4.2 Memory inspection (voice-state asserts — POSSIBLE WITH WORK, not turnkey)

- Primitives exist: `emu/snapshot.py:save()` dumps regs + mapped pages (zlib per
  1 MB `PAGE`) + MMIO/ctlregs + components + manifest (`326–362`); `restore()`
  (`381–398`); `restore_into()` (`428–481`); `checkpoint.make/resume/extend`
  (`checkpoint.py:37–54`). Offline read without executing:
  `bootstrap.snapshot_reader(path)` → `read(addr, n)`, None for unmapped
  (`bootstrap.py:1116–1145`) — `check_ram(read, acceptance)` is the existing assert
  pattern (`1148–1181`). Live read: `Machine.peek(addr, n)` (`harness.py:255–280`);
  `Session(..., on_machine=...)` probe hook (`session.py:34–35,79–81`).
- Voice-state addresses (elekloader `mod.json`, 1.44 values): `FW_VOICES 0x80004110`
  (render's copy of the DSP's eight voices, 32 samples each), `FW_VOICE_TRACK
  0x80003f8c`, `FW_VOICE_PARAMS 0x800034c4`, `FW_VOICE_LEN 0x80003f14`,
  `VOICE_PITCH 0x41392f80`, `VOICE_PREP 0x40098fc4`, `VOICES_LOOP 0x4009e0ac` /
  `VOICES_DONE 0x4009e106` (`core-dn1/mod.json:24–59,200–239`, `core-dn1/fw.s:45`);
  tracks mod adds `ADDR_VOICE_SOUNDS 0x80003f5c` (`tracks-dn1/tracks.c:31–58`).
- The "with work" half: no voice-content oracle exists (`check_ram` only asserts
  configured acceptance u32s; digitone.toml carries no `[firmware.acceptance]` of
  its own — DSP-running is injected from the profile, `bootstrap.py:1394–1396`);
  assertions must define *which* snapshot moment (post-`snap playing` mark) and
  expected values per fixture. Feasible shape: `Session` + tour script →
  `snapshot.save(session.m, tmp)` or `peek` at snap marks → compare u32/voice
  buffers stock-vs-mod or against golden values.
