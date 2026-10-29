# Behavior map — converter end-state (exploration lane, 2026-10-27)

What "converted" must mean, per `specs/track-type-conversion/spec.md`:
a converted track (slot 4–7) behaves **exactly like a native synth
track**. Grounded in `spike-track-type.md` (S-sites) and
`spike-kit-capacity.md` (kit window). Current module state (0.3) =
stash + chord + feedback only; everything below marked **open** is
the remaining work this map scopes.

## Audio (prerequisite for everything else)

- **Trig dispatch:** S1 `0x40094d44` / S2 `0x40095afa` route slot
  ≥4 to MIDI-fire `0x400948c0`. End-state: converted slots take the
  synth-fire fork `0x4009451e` (interpose at the two confirmed
  branches). Downstream code is index arithmetic — no further
  audio-path patches (`track*976` pattern, `PAT_MUTES_OFFSET
  0x16108`).
- **Sound-record fetch — the real routing problem.** Synth-fire
  reads track t's 326 B kit record at `kit+0x18+326*t`. For t=4
  that is `kit+0x530..0x65E`, colliding with the MIDI-params region
  `kit+0x5CE..0x85E` (spike-kit §2 rejected overlaying it). With
  tail append past `0x85E` also blocked (live machine-preset data),
  the fetch itself must be interposed: converted slots load their
  record from the mod `.bss` stash (already sized, 4×326 B) instead
  of the kit, then warm the per-voice cache `ADDR_VOICE_SOUNDS
  0x80003f5c` (tracks.c `invalidate_voice_cache` precedent). Exact
  load site(s) inside `0x4009451e`: one cfisa pass, TBD.
- **Check item:** S9 `0x400e31a2` iterates synth tracks 0–3 only.
  Confirm converted slots' voices flow through the index-agnostic
  allocator (0–7 clamp at `0x400ea168`), not this loop; widen only
  if evidence says otherwise.
- Stock 8-voice stealing applies unchanged (design non-goal).

## UI parity (each row = one dispatch site)

| Behavior | Site(s) | Status |
|---|---|---|
| Plain VOICE opens voice menu, synth fork on converted track | S3 `0x4003df40`, S4 `0x40043258` | open — today MIDI fork `0x400dc23c` would render |
| Double-click opens sound browser (presets) | **not yet enumerated** — identification pass needed | open |
| Synth param pages respond | S8 `0x40160968` (dataflow unconfirmed) | open |
| Track labels/type read SYNTH | S6 `0x400bbd84` ("TRK.%d" vs FX), S7 `0x40061ce4` ("T%d" vs "XX") | open |
| S5 `0x4003ca70` menu/param fork (`0x400ded80` vs synth chain) | classify during the same pass | open |

Already working (no further work): mutes (index-agnostic), plain
VOICE reaching stock everywhere (2.2 byte-identical screens), HUD
toast + LEDs (3.1), CNV8 persistence (2.1), Bank-A MIDI identity
(3.2, byte-exact).

## Open design question — UI scope

**Option A: double-click sound browser first.** One behavior, but
its dispatch site is unenumerated; the browser likely branches on
track type internally (source list, preset filter), so it may cost
2+ sites. Highest player value first (pick a sound immediately after
converting); risk: mid-size site count, discovered during the pass.

**Option B: all synth pages at once** (S3/S4 + S6 + S7 + S8 in one
release). Complete parity in one go; risk: 5+ sites patched
simultaneously, a regression is hard to bisect, and every site needs
its own before/after probe.

**Recommendation: A, after audio routing.** Audio first (without it
a converted track cannot sound, so browser results would be silent),
then the browser alone as one shippable increment, then remaining
sites (S3/S4, S6/S7, S8) one probe-covered step at a time. Matches
the design's interposition discipline: smallest blast radius first,
each site verified before the next.

## Sequencing

1. Audio routing (fetch interposition + cache warm) → emu proof:
   converted slot sounds, kit+0x5CE..0x85E untouched.
2. Sound browser (site identification pass, then interpose).
3. Voice menu + labels + params (S3/S4, S6/S7, S8), per-site.
4. L2 panel pass + hardware audio verdicts (existing 4.x tasks).
