# Spike 1.2 — Live kit capacity for 8 sound records (read-only)

Date: 2026-10-27. No builds, no edits, no binaries touched.
Sources: `tools/elekloader/mods/tracks-dn1/tracks.c`,
`tools/elekloader/mods/core-dn1/fw.s` + `params.s`
(`core_sound_set`), `elekloader/sdk/include/digitone-mk1/core3.h`,
`docs/ADAPTING.md` firmware-location table, `tools/release.py`
flavors, `firmware/releases/v1.44-8tracks-0.{8..11}/*.syx.json` +
`*.map.json`, `firmware/releases/archive/` READMEs (SuperPack 0.2,
Synth 0.2), `docs/ARCHITECTURE.md`, `docs/VOICE_OPTIMIZATION.md`.

## 1. Live kit struct — exact known offsets (1.44)

- Kit pointer: `FW_KIT = 0x4138f220` (1.44; 1.43 was `0x4138e220`,
  +0x1000 RAM shift). It points at the live kit in DDR.
- Sound-slot accessor (authoritative, `core_sound_set` in
  `params.s:302-324`, `core3.h:45`): `slot(t,k) = kit + 326*t +
  0x2c + 2*k`, t = 0..3, k = 0..78 (79 slots × 2 B = 158 B of live
  8.8 params per track). `core_sound_set` multiplies the track by
  326 against the kit base, so track t's 326 B sound record starts
  at `kit + 326*t`, with slots at record+20.
- `tracks.c` copies whole records at `fw_kit + 0x18`: 4 × 326 B =
  1304 B, i.e. `kit+0x18 .. kit+0x530` (0x18 = 24; 24 + 1304 =
  1328 = 0x530). Per-record layout: 20 B header (`0x18..0x2c`
  gap) + 158 B slots (`0x2c..0xCA` of record) + 148 B tail per
  sound record (326 − 178), contents unmapped in this spike.
- MIDI params: `fw_kit + 0x5ce`, 4 × 164 B = 656 B, i.e.
  `kit+0x5CE .. kit+0x85E` (1486..2142).
- Gap synth-end → MIDI-start: `0x530..0x5CE` = 158 B — not usable
  for a sound record (needs 326 B contiguous).
- Known-used prefix: `kit+0x0 .. kit+0x85E` = 2142 B. Total kit
  allocation size and what follows `kit+0x85E` (collision
  candidates: kit tail fields, next heap object) are not in any
  doc or mod source — the kit allocator site was not identified.
  That is a cfisa follow-up: find the `op_new` caller sizing the
  kit and dump `kit+0x85E` onward in the stock image
  (`firmware/stock_main.bin`, loads at `0x40000400`).

## 2. Collision-free extension window

- Need: 4 × 326 B = 1304 B for converted tracks 4–7.
- Rejected: overlaying `kit+0x5CE..0x85E` (MIDI params) — same
  provenance reason as the old +0x18/+0x2c lesson, and it would
  corrupt Bank-A MIDI behavior (violates task 3.2 gate).
- Rejected: the 158 B gap `0x530..0x5CE` — too small.
- Adopted window: mod DDR `.bss` (the `bank_b_*` precedent:
  `tracks.c:106-127` already keeps full-size mirrors in mod RAM,
  and the linker refused the 128-pattern mirror at ~+999 KB, so
  size discipline is enforced at link). 1304 B stash + 656 B
  optional MIDI-side mirror fit trivially — see §3. Copy-down
  discipline: converted sound copied into a scratch slot only at
  flip time under the existing interrupt mask (`trk_swap_banks`
  pattern); live kit's own 4 synth slots untouched. The exact
  live `kit+` target for converted records (append past `0x85E`
  vs scratch-then-swap) waits on the allocator site from §1 and is
  an implementation follow-up, not a spike blocker: either way the
  bytes live in mod `.bss` until flip time.

## 3. Linker DDR/flash spare (measured, recent releases)

- `v1.44-8tracks-0.8..0.11` (`core 4.1.1 + tracks 1.4`): ddr_spare
  287380 / 287308 / 287220 / 287148 B, flash_headroom ≈ 1 792 064
  B, layout `ddr 0x43EC0000..`, `ddr_size` 1310720. Verified
  0.11 directly: `ddr_spare 287148`, `ddr_size 1310720`,
  `FW_KIT 0x4138f220` (1.44 port override; base `0x4138e220`).
  Flavor minima (`release.py:59-73`): 150 000 / 1 500 000 —
  current margin ≈ +137 KB / +292 KB. The 1304 B extension
  consumes <0.5% of DDR spare.
- Full-preset (core+machines+dnmono+dnsine+dnthru+digihealth+
  tracks) has no linked release in `firmware/releases/`; nearest
  datapoints: SuperPack 0.2 (14 mods) reports
  `0x43ec0000–0x43f20620` used, ≈916 KB spare headroom; Synth 0.2
  reports 1.2 MB free fast SRAM.
- Bulk area `0x44000000–0x47BE0000` (~60 MB) available per
  `ARCHITECTURE.md` if stash ever outgrows `.bss`; not needed for
  ~2 KB.
- Voice budget unchanged: 1-voice cap (`newer_all >= 1`,
  `machines.c`; `VOICE_OPTIMIZATION.md`) — converted tracks sound
  through stock FM voices, no custom render cost.

## 4. `trk_save` / projdata stash precedent

- `tracks.c:130-161`: `struct trk_save_data` = magic +
  active_bank + initialized + 8 B mutes + 12 B reserved = 32 B,
  registered as `core_projdata` tag `TRK8`, persists via project
  data.
- Converter stash (task 2.1: per-track 976 B pattern + 326/164 B +
  mute, ×4 convertible ≈ ~5.3 KB synth-side + ~4.6 KB MIDI-side)
  is ~300× larger than `trk_save` but ~50× smaller than DDR spare;
  precedent covers mechanism (tag + `loaded()`), not size — size is
  covered by §3 linker budgets.

## Verdict for task 1.2

Exact offsets: synth `kit+0x18..0x530` (slots at `+326t+0x2c`),
MIDI `kit+0x5CE..0x85E`, gap 158 B unusable, need 1304 B.
Extension lives in mod DDR `.bss` (≈287 KB spare, minima met);
kit-tail append past `0x85E` needs the allocator address from a
cfisa pass before any live-kit write.
