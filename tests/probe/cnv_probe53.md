# 5.3 regression probe — close-out evidence (release 1487)

## Shape
`tests/probe/harness.py` (single entry, `--scenario NAME...`, `--out FILE`,
`--refresh-baseline`): CNV8 ≤2 scan, modal, convert/flip-back round-trip,
browser, voice menu, labels, synth pages, MIDI-identity vs checked-in
`tests/probe/baselines/stock.json` (captured once, `--refresh-baseline`
only regenerates explicitly — stock is never re-measured per run).
Snapshot reuse (persistent `dn1-1487-37c55a13`), single Session per
scenario with clean-project-reload reset, 1–2 bar poll-until-stable captures.

## Full end-to-end (2026-10-29)
- cnv8 PASS 5.1s, modal PASS 54.1s, roundtrip PASS 71.0s, browser PASS 4.6s,
  voice PASS 6.2s, labels PASS 11.8s, pages PASS 22.9s, midi PASS 205.0s.
- TOTAL PASS, wall 380.7s. Report: harness_full.json (scratch).
- Command: `tools/digiemu/.venv/bin/python tests/probe/harness.py [--out FILE]`
  (run from the sibling `tools/digiemu`, i.e. with its venv on PATH).

## Known gap
midi (205s) and roundtrip (71s) exceed the 60s per-scenario target — both
run multiple sessions back-to-back (r2+r3a+r3b / convert+flip-back+PLAY).
Slimming = shorter PLAY caps once the legs are stable; tracked as follow-up,
not a correctness issue (all assertions green).
