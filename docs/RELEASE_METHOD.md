# Release Method

The repeatable way this repo turns module work into firmware releases.
One conversation can own a release end-to-end; this doc is the checklist.

## Principles

- **One folder per release**: `firmware/releases/v1.44-<slug>-0.<N>/` containing the `.syx`, `.syx.json`, `.map.json`, `README.md`. Nothing else lives at that level except `archive/`.
- **`archive/` is frozen history.** Old releases (8tracks 0.7, synth 0.1/0.2, + 0.1/0.2, `8 tracks`) live there. Never rebuild or edit archived releases; new work starts at the next `0.N`.
- **Binaries stay local** (`*.syx`, `*.bin`, `*.elemod`, `*.map.json` are gitignored); manifests and READMEs are committed so every build is reproducible and verifiable.
- **Every release passes smoke + emulator boot before it is considered done.** Hardware flashing is the user's manual step.

## Steps

### 1. Prepare modules
Compiled `.elemod` files live in `firmware/elemods/`. For a module you changed or newly ported, compile it first (WSL provides `m68k-linux-gnu-gcc`):

```powershell
wsl bash -c "cd /mnt/d/Elektron-MODS/tools/elekloader && PYTHONPATH=. python3 -m elekloader.sdk.build mods/<modname> --stock ../../firmware/Digitone_and_Digitone_Keys_OS1.44.syx --out mods/<modname>/out"
```

Then copy the produced `.elemod` into `firmware/elemods/`.

**Ported Digitakt modules are new modules**: create `modules/dn-<name>/` (own `mod.json`, `device: digitone-mk1`), port the code per `docs/PORTING_DIGITAKT_TO_DIGITONE.md`, then compile as above. Reference/upstream Digitakt sources stay in `modules/digi1_mods/`, `modules/digisophie/`, `modules/digitables/` and are never edited.

### 2. Link the release

```powershell
python3 tools/release.py --slug 8tracks --num 8 --tag 1448 --preset 8tracks
# or pick modules explicitly:
python3 tools/release.py --slug myset --num 1 --tag 1449 --mod core-dn1-4.1-os1.44.elemod --mod <...>
```

The script verifies the stock hash, links via `elekloader.patch` (writes `.syx` + `.json` + `.map.json`), and writes a README stub with date, module list, and output SHA-256. Add `--emu` to also create the digiemu snapshot and a `run-<slug>.bat` launcher in the same step.

### 3. Smoke + boot proof

```powershell
powershell -ExecutionPolicy Bypass -File tests/smoke.ps1
powershell -ExecutionPolicy Bypass -File tests/boot-check.ps1
```

Checks stock hash, every active release's manifest + README, `.bat` snapshot existence, no firmware tracked by git, WSL toolchain — then boot proof: each release `.syx` (stock + latest known-good) is added to digiemu in an isolated temp home, the factory UI must settle (snapshot appears, no fault strings in `first-run.log`), and a deliberately truncated syx must refuse.

### 4. Try in emulator

```powershell
# first time (or after each rebuild): create the snapshot + launcher
python3 tools/release.py ... --emu
# then just:
run-<slug>.bat
```

The panel gives you the full front surface: bank toggle (`[VOICE]`), mutes, machines menu (long-press T1-T4), transport. Boot + interaction are emulator-testable; exact CPU/tick behavior is not (see `docs/VOICE_OPTIMIZATION.md`).

### 5. Commit

```powershell
git add docs tests tools/release.py firmware/releases README.md run-<slug>.bat
git commit -m "release: v1.44-<slug>-0.<N> (tag <tag>)"
git push
```

The `.syx` itself stays local (gitignored) - the committed manifest pins its hash.

### 6. Flash to hardware (manual)
Hold **[FUNC]** while powering on -> **[TRIG 4]** (MIDI upgrade) -> send the release `.syx` with Elektron Transfer. Recovery: same path with the stock OS from `firmware/`.

## Verification

Every release passes a four-level pyramid before it counts as done.
`tools/release.py` auto-enforces the L0 gates; L1 is the `tests/boot-check.ps1`
snapshot-oracle plus log fault grep; L2 behavior tests are manual panel
procedures until the input-injection / memory-inspection spikes land (see L2);
L3 is the user's hardware record in the release README's `## Verification`
block.

### L0 — build gates (auto-enforced by `tools/release.py`)

The driver refuses to write a release unless: the stock OS hash matches the pin
(`d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659`); the linked
module set matches the flavor's required/forbidden definitions; `--tag` is
unused by any active or archived release; and the linked image's `ddr_spare` /
`flash_headroom` meet the flavor minimums (read back from the written
`.syx.json`: `link.order`, `tables` entry counts).

### L1 — boot proof (`tests/boot-check.ps1`)

The release `.syx` is added to digiemu; within a timeout the firmware snapshot
must appear (digiemu only writes it after the factory UI settles — no snapshot
without a settled UI) and the emulator logs must contain no fault strings.
It passes on stock OS 1.44, requires a pass on every `--preset`/release build
(the strict gate: a release that does not settle does not ship — archived
8tracks-0.7 evaluated 2026-10-26 FAILS L1, `NOT SETTLED after 3000M
instructions, +Drive overlay still drawn`; see `docs/EMU_TESTING.md`), and fails /
times out on a deliberately truncated `.syx`.

```powershell
powershell -ExecutionPolicy Bypass -File tests/boot-check.ps1
```

### L2 — behavior tests (manual panel procedures, spike-gated)

Automation is pending spike findings, which land in `docs/EMU_TESTING.md`
(not yet written). Until then, run these four checks by hand on the panel
(emulator or hardware) and record the outcome in the release README.
Emulator results are emulator evidence only (see Evidence hierarchy).

#### Converter line (8track-engine): GUI-first L2
Converter releases verify parity by hand in the resumed panel
(`docs/EMULATOR_WORKFLOW.md` section 5: resume `dn1-<tag>-<hash8>`, no
re-boot per check). Headless probe is regression-only: CNV8 scan,
MIDI byte-identity vs cached `tests/probe/baselines/`, framebuffer hash —
single `Session`, project-reload reset, 1–2 bar captures,
poll-until-stable, target <60 s per iteration (L1 cold boot excepted).
Full harness reasoning lives in
`openspec/changes/archive/2026-10-27-8tracksim/probe-workflow.md`.

C1 — modal convert / restore (shared trigs, channel preserved):
1. On MIDI slot 5–8 press `MIDI`+`VOICE` → YES/NO modal appears.
2. YES → slot voices as synth (`b1..b4` label) on the same channel with
   the same trigs; NO/timeout → unchanged. Repeat chord + YES restores MIDI.

C2 — sound browser + synth pages + voice menu:
1. Double-click a converted slot → synth preset browser opens, chosen
   preset sounds on that slot. 2. Plain `VOICE` opens the synth voice menu.
3. Synth pages (SYN1/SYN2/FLTR/AMP/FX) respond as on native tracks.

C3 — mutes + sequencer + MIDI coexistence:
1. Mute/unmute each converted slot; sequence all 8 together.
2. Expected: per-track mutes, no leaks, stock 8-voice stealing only.
3. Unconverted MIDI slots stay byte-identical (regression probe asserts).

#### Bank line (legacy B1–B4, bank releases only)

#### B1 — bank-toggle swap
1. Load a pattern with distinct sequences on tracks T1–T4 (foreground bank).
2. Program a contrasting sequence on the background bank (tracks 5–8).
3. Press **[VOICE]** to toggle banks.
4. Expected logic result: the sounding tracks swap foreground ↔ background
   cleanly; no foreground note keeps ringing from the wrong bank after the swap.

#### B2 — mute isolation between banks
1. Start the sequencer (**[PLAY]**) with both banks programmed.
2. Mute a foreground track (**[FUNC]** + its track key T1–T4).
3. Toggle to the background bank (**[VOICE]**) and back.
4. Expected logic result: the muted track stays silent in both banks;
   unmuting restores it; mutes never leak from one bank to the other.

#### B3 — no zombie voices after machine switch
1. Play a sustained note on a track, then long-press its track key (T1–T4) to
   open the machines menu and switch the track to a different machine.
2. Stop all notes, then trigger the track again.
3. Expected logic result: the old machine's voice is fully released at the
   switch — no stuck/droning note; the new machine sounds normally on the
   next trigger.

#### B4 — voice-cap enforcement
1. Sequence all sounding tracks at once (maximum polyphony + background bank).
2. Play through a dense passage.
3. Expected logic result: at most the flavor's documented custom-voice cap
   sounds at once; excess notes are stolen/dropped per the flavor's rule and
   the firmware never crashes. Any cracking is recorded as a known issue.

### L3 — hardware record (release README `## Verification` block)

After flashing (step 6), the user runs the L2 procedures plus this checklist on
the unit and records only actual results in the release README:
- Simultaneous instances (all tracks + background bank sounding together)
- Track isolation (mutes/solos affect exactly one track)
- Project persistence (save, power-cycle, reload — pattern and sounds intact)
- Reboot survival (power-cycle mid-pattern; unit reboots clean, no brick)

### Evidence hierarchy

- Emulator evidence is emulator evidence only: it proves the exercised code
  paths, never timing, audio quality, saved-project survival, or
  physical-reboot behavior. Label it as such (`emu boot: pass <date>`, never
  `hardware: pass`).
- The cracking/audio verdict always requires hardware.
- Record only actual results: each evidence line states what was tested with a
  date, or `untested`. A fresh build shows build facts + `untested`/`untested`.

## Versioning

- `--tag` is what the hardware displays (e.g. `1448` shows as 1.448). Convention so far: `144<num>` for the 8tracks line, `144S` for synth, `144+` for superpack.
- `--num` increments per flavor: `v1.44-8tracks-0.8` follows the archived `0.7`.
- New flavor = new slug, start at `0.1`.

## Known-issue tracking
Open problems (e.g. the voice-cracking budget issue) live in `docs/REPO.md` "Known issue" and get their own OpenSpec change when worked on - release steps never bundle silent fixes.
