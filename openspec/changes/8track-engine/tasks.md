# Tasks: 8-track engine

## 1. Audio routing (gate for everything else)
- [x] 1.1 Interpose S1 `0x40094d44` + S2 `0x40095afa` (converted → synth-fire `0x4009451e`), prove stock 0–3 path unchanged via cfisa + emu trig capture
- [x] 1.2 cfisa pass over `0x4009451e` to find the `kit+0x18+326t` load site(s); interpose fetch to `.bss` `cnv_synth_snd` + warm `0x80003f5c`; emu proof: converted slot sounds, `kit+0x5CE..0x85E` untouched
- [x] 1.3 Verify S9 `0x400e31a2` needs no widening (voices flow via `0x400ea168` 0–7 clamp); record evidence

## 2. Confirm-modal gesture
- [x] 2.1 Replace immediate toggle with YES/NO modal (YES flips under `trk_swap_banks` mask discipline, NO/timeout cancels, plain VOICE falls through, chord on 0–3 no-op); emu key-probe on every page context
- [x] 2.2 Shared-trig flip: keep live 976 B pattern in place, swap only 326 B / 164 B + mute + channel; first convert = fresh init sound; prove flip-back keeps same trigs

## 3. Synth UI parity (one site per step, probe-covered)
- [x] 3.1 Sound browser: identification pass (open site + preset-apply write site), interpose open + redirect apply to `.bss` + cache warm; emu proof: double-click opens synth browser, preset sounds after select
- [x] 3.2 Voice menu S3 `0x4003df40` + S4 `0x40043258` (prove `d4`/`d2` = track, route converted to synth fork `0x400e8be8` gate)
- [x] 3.3 Labels S6 `0x400bbd84` + S7 `0x40061ce4` with `b1..b4` strings from mod `.rodata`
- [x] 3.4 Synth pages S8 `0x40160968` (dataflow confirm) + S5 `0x4003ca70` classify; mute/sequencer regression (index-agnostic, no patch)

## 4. MIDI coexistence
- [x] 4.1 Prove Bank-A MIDI byte-identity with conversions active (MIDI-byte log before/after across flips vs a freshly captured stock log — no checked-in baselines exist)
- [ ] 4.2 Prove converted synth outputs on the preserved channel (e.g. pre-set 5 still outputs 5); record in release notes

## 5. Release + verification (GUI-first)
- [x] 5.1 Converter flavor in `tools/release.py`, link first 8track-engine release (carries stepping-stone 4.1); L1 pass via `bash tests/boot-check.sh [--extra-syx <release.syx>]` (needs the `tests/*.sh` twins ported into this checkout first)
- [ ] 5.2 Manual panel procedures (user: `cd tools/digiemu && .venv/bin/python -m emu.dnpanel portable/firmware/<slug>` — or `./run-<slug>.sh` once the dual-launcher port lands): modal, convert/flip-back, browser, voice menu, b-labels, synth pages, mutes, sequencer — record concrete values in README Verification block, audio verdicts stay `hw-pending`
- [x] 5.3 Regression-only headless probe (`tests/probe/harness.py` + `tests/probe/baselines/stock.json`): CNV8 ≤2 scan + MIDI-identity vs checked-in stock baseline + framebuffer hash; snapshot reuse (resume settled `gui.snap`, rebuild via `--add` on exit-3) + single session + 1–2 bar windows; full run green (midi/roundtrip exceed 60s — slimming tracked as follow-up)
- [ ] 5.4 `bash tests/smoke.sh` green; docs updated (`EMU_TESTING.md` harness contract, `EMULATOR_WORKFLOW.md` resume/manual flow, `RELEASE_METHOD.md` L2 converter procedures); hardware audio lines recorded with date when flashed
