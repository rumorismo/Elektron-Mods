# Probe workflow — audit + fix proposal (exploration lane, 2026-10-27)

## Audit: why an iteration costs 5–10 minutes

Measured per iteration (2.2–3.3 lanes, Measure-Command): build ~1 s,
lint ~1 s, link 10–15 s, L1 cold boot **26–83 s per new .syx**
(snapshot oracle only settles after factory UI), headless probe
**176–503 s**. The probe cost decomposes as:

- **Fresh emu session per scenario** — boot + settle (~30–60 s)
  repeated for stock control, modded-before, modded-after, each
  extra slot/variant.
- **Manual setup replayed every run** — OUTPUT TO → MIDI+USB, MIDI
  CHAN enable (the two 3.2 discoveries), pattern programming
  (steps/mutes), all via slow synthetic key sequences.
- **Generous capture windows** — 8 s PLAY to observe a 4-trig
  pattern.
- **Stock baseline re-measured every time** instead of cached.
- **One-off scripts** — `tools/probe-*.py` precedent + scratch
  copies in `C:/Users/sgarz/AppData/Local/Temp/opencode`
  (`probe-convert-01.py`, `probe-voice-33.py`), results as loose
  JSON/.raw files; nothing rerunnable, nothing in-repo.

## Proposal: one reusable harness, batched sessions, cached baseline

Home: `tests/probe/` in-repo (sibling of `boot-check.ps1`; docs land
in `docs/EMU_TESTING.md`, which is the designated home for L2/emu
findings — don't duplicate). Scripts stop being one-offs: scenario
definitions are data, the runner is shared.

```
tests/probe/harness.py          # runner + Panel/Capture library
tests/probe/scenarios/*.py      # one file per behavior check
tests/probe/baselines/*.json    # cached stock-control hashes/bytes
```

Runner shape:

```
uv run python tests/probe/harness.py --syx <build.syx> \
    --scenarios convert,flipback,midi-identity [--stock-control] \
    --out <scratch>
```

Mechanics that kill the cost:

1. **Snapshot reuse.** Resume the settled snapshot for the firmware
   hash (`dn1-<tag>-<hash8>`); rebuild only on mismatch (dnpanel
   exit 3 → `--add` once). Cold boot happens once per new .syx,
   never per scenario.
2. **Single session, all scenarios.** Boot once, run every scenario
   sequentially in the same instance; reset between scenarios by
   loading a clean project (unsaved edits die with the session —
   verified in 3.2 — so a reload is a deterministic reset).
3. **Setup as library calls.** `panel.route_midi()`,
   `panel.enable_chan(1)`, `panel.program(steps, trigs)` — the
   discovered key sequences become helpers, not per-script code.
4. **Minimal windows.** Capture the shortest window that contains
   the event (1–2 bars), assert, stop. No fixed 8 s plays.
5. **Cached stock baseline.** `baselines/<scenario>.json` stores the
   stock bytes/hashes per scenario; `--refresh-baseline` regenerates
   only when stock behavior or the fixture changes. Iterations
   compare modded-vs-baseline only.
6. **Structured output.** One JSON report per run (scenario, pass/
   fail, observed values, artifact paths); screens kept as hashes +
   raw only on failure.

Kept as probes: state reads (CNV8 scan with the ≤2 validation),
framebuffer identity vs baseline, MIDI byte sink, memory peeks.
Kept **manual L2**: anything audible (mix, stealing, mute feel),
LED visual feel, and all hardware verdicts (evidence hierarchy).

## Target math

Resume + settle ~5–10 s; per scenario setup ~2–5 s (helpers) +
capture 2–4 s; report <1 s. A behavior-check iteration lands well
under 60 s; L1 cold boot stays a one-time ~30–80 s cost per new
build. Existing hard-won protocol details to carry into the harness
docs: `DT2_*` env mirroring of the panel worker, MIDI key retargets
`fw_active_track` (reselect before acting), CNV8 magic false-positive
guard, CLOCK SEND off for byte-identity runs.
