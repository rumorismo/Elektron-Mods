# convert 0.11 re-verify — build + boot proof

Date: 2026-10-28. Lane: resolved addresses, wrote nothing — this file is the build + boot evidence.
Scope: build + boot only. Captures (MIDI/audio sustain checks) are a separate follow-up, NOT attempted here.

## 1. Build

Command (Linux-only, no WSL):

```
cd /home/nuke/Documents/Elektron-MODS/tools/elekloader && PYTHONPATH=. python3 -m elekloader.sdk.build /home/nuke/Documents/Elektron-MODS-8-track-engine/modules/dn-convert --stock /home/nuke/Documents/Elektron-MODS/firmware/Digitone_and_Digitone_Keys_OS1.44.syx --out /home/nuke/Documents/Elektron-MODS-8-track-engine/modules/dn-convert/out
```

Full output:

```
BUILT /home/nuke/Documents/Elektron-MODS-8-track-engine/modules/dn-convert/out/convert-0.11.elemod
  convert 0.11: .run 2978, .fast 0, .bss 9856 bytes; 3 sites, 117 relocations; imports fw_active_track, fw_fillrect, fw_font5, fw_kit, fw_memcpy, fw_memset, fw_pattern, fw_textf
```

Result: PASS (exit 0).

mod.json: convert 0.11, 3 sites (S1 0x40094d44 10B, S2 0x40095afa 6B, F3 0x40094832 22B), sources convert.c + cnv_route.s + cnv_fetch.s.

elemod sha256:

```
58b506039edabd9a25c1bca7fc1d1942412f34d1ca31a04f15ee7007238284fe  modules/dn-convert/out/convert-0.11.elemod
```

## 2. Lint

Command:

```
python3 -m elekloader.lint /home/nuke/Documents/Elektron-MODS-8-track-engine/modules/dn-convert/out/convert-0.11.elemod --stock /home/nuke/Documents/Elektron-MODS/firmware/Digitone_and_Digitone_Keys_OS1.44.syx --with /home/nuke/Documents/Elektron-MODS/firmware/elemods/core-dn1-4.1.1-os1.44.elemod
```

(run from /home/nuke/Documents/Elektron-MODS/tools/elekloader)

Full output:

```
OK: convert 0.11 (format 2) for Digitone mk1 1.44: 3 sites, sections {'.run': 2978, '.bss': 9856}, imports fw_active_track, fw_fillrect, fw_font5, fw_kit, fw_memcpy, fw_memset, fw_pattern, fw_textf; licence GPL-2.0-or-later
OK: links as core 4.1.1 > convert 0.11; RAM 19876 of 1310720 bytes, fast SRAM 0 of 0
NOTE: convert hooks 3 code sites itself (0x40094d44, 0x40095afa, 0x40094832); a site another mod could want belongs in the core as an event, and a pull request that adds it is welcome (docs/CORE-CONTRIBUTING.md)
```

Result: PASS (exit 0, OK + "links as core 4.1.1 > convert 0.11").

## 3. Link (OUTSIDE tracked trees)

Tag check:

```
grep -rho "tag [0-9]*" /home/nuke/Documents/Elektron-MODS/firmware/releases/*/README.md /home/nuke/Documents/Elektron-MODS-8-track-engine/firmware/releases/*/README.md 2>/dev/null | sort -u
tag 1499
```

1465 free → used as the unused version tag.

Command:

```
python3 -m elekloader.patch --stock /home/nuke/Documents/Elektron-MODS/firmware/Digitone_and_Digitone_Keys_OS1.44.syx --mod /home/nuke/Documents/Elektron-MODS/firmware/elemods/core-dn1-4.1.1-os1.44.elemod --mod /home/nuke/Documents/Elektron-MODS-8-track-engine/modules/dn-convert/out/convert-0.11.elemod --out /home/nuke/Documents/Elektron-MODS/firmware/test-cnvx.syx --version 1465
```

(run from /home/nuke/Documents/Elektron-MODS/tools/elekloader)

Full output:

```
stock: Digitone mk1 OS 1.44 (d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659)
mod core 4.1.1               88 sites  (file sha256 7a00f887ae14c853)
mod convert 0.11             3 sites  (file sha256 58b506039edabd9a)
the mods combine: no overlaps, stock bytes as expected, code sites whole instructions
linked core 4.1.1, convert 0.11: RAM 0x43ec0000-0x43ec4da4 (1290844 bytes spare), .fast to 0x00000000 (0 spare), blob 8552 bytes
packed the main OS: 2744856 -> 1073016 bytes (10.0 s)
verified: sections 2, 4, 5, 6, 7, 8, byte for byte; the main OS depacks to the patched image in place (min gap 424280 bytes); flash ends 0x1ca670 (1792400 bytes spare)
WROTE /home/nuke/Documents/Elektron-MODS/firmware/test-cnvx.syx
  sha256 b653e7eda2f859072199f00814cb75efa093690f4e136b428e904e83fbf18824, version 1465, 1715232 bytes
```

Result: PASS (exit 0).

- .syx: /home/nuke/Documents/Elektron-MODS/firmware/test-cnvx.syx (outside tracked trees)
- .syx sha256: b653e7eda2f859072199f00814cb75efa093690f4e136b428e904e83fbf18824
- .syx size: 1715232 bytes
- version tag: 1465

## 4. Boot

Command:

```
cd /home/nuke/Documents/Elektron-MODS/tools/digiemu && .venv/bin/python -m emu.portable --home $(mktemp -d) --add /home/nuke/Documents/Elektron-MODS/firmware/test-cnvx.syx --yes
```

(venv: tools/digiemu/.venv/bin/python, run from tools/digiemu/; NEVER uv sync.)

Full output:

```
Digitone OS 1465 (build 0107, built 2026-09-30, untested)  ->  /tmp/tmp.raLfEaLuyv/firmware/dn1-1465-b653e7ed
[  0%] copy: copying test-cnvx.syx
[  0%] copy: copied Digitone_OS1465.syx
[  0%] extract: extract ...
[  0%] extract: extract done in 2 s
[  0%] card: card ...
[  0%] card: card done in 0 s
[  0%] ladder: ladder ...
[ 11%] ladder: parked at ~130M instructions, 10 tasks, pc=0x4008d3ec
[ 15%] ladder: ladder done in 6 s
[ 15%] intro: intro ...
[ 15%] intro: symbols: intro_pit3_isr=0x40090CFC intro_done_hook=0x40091B0C frame_sem=0x4137C93C mainloop=0x40019CD4
[ 15%] intro: resume boot.snap  except_sem=['0x4137c93c']
[ 15%] intro:  instr PCSR     lit      vector       mainloop  phase
[ 29%] intro:   >> display module claimed vector 208 at 60M
[ 43%] intro:   -> user interface is live
[ 43%] intro:
intro_done fired 1 time(s); mainloop 137; lit 1803
[ 43%] intro: VERDICT: USER INTERFACE IS LIVE
[ 43%] intro: saved /tmp/tmp.raLfEaLuyv/firmware/dn1-1465-b653e7ed/snapshots/Digitone_OS1465/gui-raw.snap
[ 50%] intro: intro done in 20 s
[ 50%] settle: settle ...
[ 50%] settle:   timers: restored saved cadence
[ 50%] settle:  instr frames   overlays  quiet-run  jobs      state
[100%] settle:
SETTLED at 1250M: 120 consecutive main-UI frames with no overlay.
[100%] settle: saved /tmp/tmp.raLfEaLuyv/firmware/dn1-1465-b653e7ed/snapshots/Digitone_OS1465/gui.snap
[100%] settle: accepted: the card holds the finished first boot; RAM dsp_running_u32=0x2
[100%] settle: settle done in 30 s
Digitone OS 1465 (build 0107, built 2026-09-30, untested) is ready.
```

Result: PASS (exit 0).

- Snapshot id: dn1-1465-b653e7ed
- gui.snap present: snapshots/Digitone_OS1465/gui.snap (also gui-raw.snap, boot.snap)
- Settle: SETTLED at 1250M, 120 consecutive main-UI frames with no overlay, settle done in 30 s
- Phase timings: extract 2 s, ladder 6 s (parked ~130M, 10 tasks, pc=0x4008d3ec), intro 20 s (display vector 208 at 60M, intro_done x1, mainloop 137, lit 1803), settle 30 s
- Wall time: real 1m1.055s (user 1m0.440s, sys 0m0.401s)
- first-run.log: /tmp/tmp.raLfEaLuyv/firmware/dn1-1465-b653e7ed/logs/first-run.log — clean; all fault strings count 0: 'NOT SETTLED', 'Traceback', 'StepFailed', 'was killed', 'crashed', 'LOAD_FAILED', 'INCOMPATIBLE', 'no live user interface', 'did not come up'. Tail confirms "SETTLED at 1250M" + "settle done in 30 s".

## 5. SUSTAIN-STATUS

Known prior gap (NOT retested here): the converted allocator engages, but converted voices don't sustain — converted tracks trigger without a sustaining voice (no audible/MIDI capture proving sustain was made). This run proves only that core 4.1.1 + convert 0.11 links cleanly and boots to a settled UI (snapshot dn1-1465-b653e7ed). Sustain/trigger capture is a separate follow-up and was deliberately NOT attempted in this lane.

## 6. Captures

Date: 2026-10-28. Follow-up to §1–§5: headless trig-capture proof for convert 0.11.
Harness: `tests/probe/cnv_captures.py` (new; re-runnable). Evidence JSONs live OUTSIDE
the repo (scratch, no firmware, no baselines checked in):
`/tmp/opencode/cnv_base.json`, `/tmp/opencode/cnv_conv.json`,
`/tmp/opencode/cnv_compare.json`.

### 6.1 Persistent snapshot

No `dn1-1465-*` dir existed under
`tools/digiemu/portable/firmware/` (sibling tree), so one `--add` WITHOUT `--home`:

```
cd /home/nuke/Documents/Elektron-MODS/tools/digiemu && .venv/bin/python -m emu.portable --add /home/nuke/Documents/Elektron-MODS/firmware/test-cnvx.syx --yes
```

Result: PASS, `dn1-1465-b653e7ed` SETTLED at 1250M (120 consecutive main-UI
frames), wall 61.0 s. Both captures below reuse settled snapshots, no rebuilds:
stock `dn1-1.44-d4f200d0` (pre-existing) and modded `dn1-1465-b653e7ed`.

### 6.2 Commands (run from `tools/digiemu` with `.venv/bin/python`)

```
python /home/nuke/Documents/Elektron-MODS-8-track-engine/tests/probe/cnv_captures.py --scenario base --out /tmp/opencode/cnv_base.json
python /home/nuke/Documents/Elektron-MODS-8-track-engine/tests/probe/cnv_captures.py --scenario convert --out /tmp/opencode/cnv_conv.json
python /home/nuke/Documents/Elektron-MODS-8-track-engine/tests/probe/cnv_captures.py --compare /tmp/opencode/cnv_base.json /tmp/opencode/cnv_conv.json --out /tmp/opencode/cnv_compare.json
```

Each scenario = ONE `Session` per boot from the persistent snapshot (no boot per
scenario-step). Shape: grid-rec program tracks 0–3 (steps 2/6/10/14, struct-verified
ON, toggle-fix for factory-occupied steps) → PLAY with poll-until-stable
(min 3000 ms emu, stop when every covered track fired ≥2, cap 7000 ms) → STOP →
T1 select + settle-poll → captures. Convert run additionally: MIDI+VOICE chord
(struct-verified, retried; MIDI-press stash/transient retarget — active reads 0
while held, conversion still lands) → program converted slot 4 (after MIDI-tap
reselect to active=4; T-keys can't address 4–7) → same PLAY (windows sliced by
marks) → flip-back chord (positive-verified: live pattern == pre-chord bytes).

Hard-won mechanics (all verified live, encoded in the harness):
- audio=True is REQUIRED: with audio=False transport goes 0→1 but S1/S2 never
  fire (sequencer steps on the audio clock). Cost ≈8× wall (2 s emu ≈ 18 s wall).
- Key timing 15/15 ms registers reliably (struct-verified); MIDI bank toggles on
  release (hold reads active=0, release→4), so selection is poll-verified, and a
  pre-settle MIDI-bank-restore + T1 makes both settled screens like-for-like.
- Monotonic single session per boot: scenarios build on each other intentionally
  (tracks 0–3 pattern hashes bit-identical pre/post chord), so no clean-project
  reload is needed; stock-vs-modded isolation is by separate boots/snapshots.

### 6.3 Wall times (budget: each capture run <60 s)

- base (stock): total 45.8 s — boot 4.6, program 1.5+1.6+1.5+1.5, play 24.9, stop/settle 10.2.
- convert (modded): total 53.1 s — boot 4.6, program 1.5+1.5+1.5+1.5, chord_conv 2.3, program_t4 1.3, play 24.5, stop/settle 11.2, chord_flip 2.4.
- compare: instant (JSON-only). Neither run halted (`halted: None` both).

### 6.4 Verdicts

(a) Stock tracks 0–3 trig capture modded-vs-stock identical: PASS.
- F3 per-track fetch identical: t0 5/5 × `0x413062ac`, t1 4/4 × `0x413063f2`,
  t2 4/4 × `0x41306538`, t3 5/5 × `0x4130667e` (= kit+0x18+326t each; multiset
  comparison would be poll-phase-brittle, so per-track a0-sets + ≥2 coverage).
- MIDI-byte sink: identical, both empty (`nonrt_len` 0, `rt_count` 0 — clock send
  off by default; realtime bytes filtered regardless).
- Mutes identical: pattern bytes `0000285000010010` both, hw mask `0x0000` both.
- Kit tail identical: `ddba55cebc7550b0` both.
- Framebuffer: PIXEL-IDENTICAL (`fddfc317b1b18176` both, 0 px differ).
- voices_sha: differs (`a709d972…` vs `5f70bf18…`) — ALLOWED documented skew:
  the voices buffer mixes in converted track-4 voice content that only the
  modded run produces; every other (a) signal above is identical.

(b) Converted slot-4 fires publish the .bss record through F3: PASS.
- 4 track-4 hits at 2172.0/2874.4/3571.1/4267.7 ms, ALL with a0=`0x43ec394c`
  (in mod RAM `0x43EC0000–0x43EC4DA4`), matching the prior finding `0x43EC394C`
  exactly — verified live.

(c) Kit tail identical pre/post flips: PASS.
- `FW_KIT+0x5CE..0x85E` sha `ddba55cebc7550b0` at all four moments
  (pre-chord / post-chord / settled / post-flipback).
- Round-trip positive: pattern-4 `581a47b1…` (factory MIDI) → `ceeffeb6…`
  (converted synth) → programmed `f914b155…` (pre-play) unchanged by PLAY →
  `581a47b1…` after flip-back (byte-identical restore).

(d) Allocator/sustain state for track 4 (record only, NO fixes attempted): INFO.
- Y(4) (`0x80003fd8`): 0 mid-play (per-fire warm restores the stock invariant —
  same as native Y=0) / `0x20000` settled (prior stuck value returns post-STOP).
- Candidate row 4 head: `01`×8 mid-play and settled (single-voice staging holds).
- Cached sounds (`0x80003f5c`): all 0 (invalidated). Voice map (`0x80003f8c`):
  `[4,1,2,4,4,4,4,4]` settled (five voices on track 4 — allocator engaged).
- Lens (`0x80003f14`): `0xFFFFF000` ×8 both phases (idle sentinel; cf. prior
  prose "lens 0" — the live word reads -4096). Gates `0x80001f70/0x80001f74`:
  0/0 both phases. Voices buffer: `c0e766d0…` mid-play / `5f70bf18…` settled.
- F3 track-4 fires: 4 (dispatch + fetch + allocator all engage). No sustain
  observed headless; audio verdict stays hw-pending per the evidence hierarchy.

Nothing was committed as firmware (all `.syx` stayed in the sibling
`firmware/` or temp dirs); no audio verdict is claimed. The convert chord is
drivable headless (outcome-verified, retried); nothing blocked the proof.
