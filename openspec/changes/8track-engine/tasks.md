# Tasks: 8-track engine

## 1. Audio routing (gate for everything else)
- [ ] 1.1 Interpose S1 `0x40094d44` + S2 `0x40095afa` (converted → synth-fire `0x4009451e`), prove stock 0–3 path unchanged via cfisa + emu trig capture
- [ ] 1.2 cfisa pass over `0x4009451e` to find the `kit+0x18+326t` load site(s); interpose fetch to `.bss` `cnv_synth_snd` + warm `0x80003f5c`; emu proof: converted slot sounds, `kit+0x5CE..0x85E` untouched
- [ ] 1.3 Verify S9 `0x400e31a2` needs no widening (voices flow via `0x400ea168` 0–7 clamp); record evidence

## 2. Confirm-modal gesture
- [ ] 2.1 Replace immediate toggle with YES/NO modal (YES flips under `trk_swap_banks` mask discipline, NO/timeout cancels, plain VOICE falls through, chord on 0–3 no-op); emu key-probe on every page context
- [ ] 2.2 Shared-trig flip: keep live 976 B pattern in place, swap only 326 B / 164 B + mute + channel; first convert = fresh init sound; prove flip-back keeps same trigs

## 3. Synth UI parity (one site per step, probe-covered)
- [ ] 3.1 Sound browser: identification pass (open site + preset-apply write site), interpose open + redirect apply to `.bss` + cache warm; emu proof: double-click opens synth browser, preset sounds after select
- [ ] 3.2 Voice menu S3 `0x4003df40` + S4 `0x40043258` (prove `d4`/`d2` = track, route converted to synth fork `0x400e8be8` gate)
- [ ] 3.3 Labels S6 `0x400bbd84` + S7 `0x40061ce4` with `b1..b4` strings from mod `.rodata`
- [ ] 3.4 Synth pages S8 `0x40160968` (dataflow confirm) + S5 `0x4003ca70` classify; mute/sequencer regression (index-agnostic, no patch)

## 4. MIDI coexistence
- [ ] 4.1 Prove Bank-A MIDI byte-identity with conversions active (MIDI-byte log before/after across flips vs cached stock baseline)
- [ ] 4.2 Prove converted synth outputs on the preserved channel (e.g. pre-set 5 still outputs 5); record in release notes

## 5. Release + verification (GUI-first)
- [ ] 5.1 Converter flavor in `tools/release.py`, link first 8track-engine release (carries stepping-stone 4.1); L1 `boot-check.ps1` pass
- [ ] 5.2 Manual panel procedures (user, `dnpanel` resume): modal, convert/flip-back, browser, voice menu, b-labels, synth pages, mutes, sequencer — record concrete values in README Verification block, audio verdicts stay `hw-pending`
- [ ] 5.3 Regression-only headless probe: CNV8 ≤2 scan + MIDI-identity vs `tests/probe/baselines/` + framebuffer hash; snapshot reuse + single session + 1–2 bar windows; target <60 s per iteration (L1 cold boot stays one-time per new `.syx`)
- [ ] 5.4 `tests/smoke.ps1` green; docs updated (`EMU_TESTING.md` harness contract, `EMULATOR_WORKFLOW.md` resume/manual flow, `RELEASE_METHOD.md` L2 converter procedures); hardware audio lines recorded with date when flashed
