# Spike 1.1 — How the firmware decides track type (read-only)

Date: 2026-10-27. Image: `firmware/stock_main.bin` == digiemu
`sections/section_3_MAIN_OS.bin` (2,736,304 B, load `0x40000400`;
byte-identical, verified). All addresses absolute. No files written
during the spike; nothing built. Method: cfisa linear passes
(Capstone-m68k cannot decode ColdFire-only `mvsz`/`mvs`, so all
Capstone output was cross-checked with `emu/cfisa`); 32-bit
absolute-operand scans for known globals; forward-decode context
dumps of the `moveq #3; cmp.l; blt` idiom over ~470k in-code
instructions in clean-decode windows; seq-events-dn1 `mod.json` /
`dev.h` as ground truth for the fire path.

## Verdict

No per-track type field, no track-type vtable/presenter. Type =
hardcoded `track > 3 → MIDI` branches at every dispatch site. The
idiom is always `moveq #3,dx; cmp.l track,dx; blt → MIDI-side`
(the constant lives in a register, which is why there are zero
`cmpi #4` in code; the one `cmpi.l #8` at `0x4028c934` is a
voice-loop bound, and 31 raw `cmpi.b #4/#8` hits are all
misaligned ghosts inside `movem` masks, verified dead by
flag-consumption analysis). Callees then do pure index arithmetic.
Conversion must patch or interpose at each site (or above them).

## Confirmed dispatch sites (register proven = track index)

- S1 — first-step builder, `0x40094d44`. Function entry
  `0x40094be2` (= `SQ_REARM` 1.44): `d2=starttrack; cmp.l d2,#7;
  bcs→single else d2=0, count($38(a7))=8`. Loop top `0x40094c90`
  (`cmp.l $38(a7),d2; bge →0x40094df6 exit`), per-iteration `d2+=1`,
  track structs advanced by `0x3d0` (976). Dispatch:
  `0x40094d44 moveq #3,d1 | 0x40094d4a cmp.l d2,d1 |
  0x40094d4c blt → 0x40094d74` (MIDI-fire `0x400948c0`);
  fallthrough → synth-fire `0x4009451e` (pc-rel jsr),
  `bra 0x40094da4` over the MIDI fork. Prologue also computes MIDI
  sub-index `d4 = track-4` (`0x40094c12 subq #4,d4; muls`). Both
  forks receive identical `(pattern 0x4138f214, kit 0x4138f220,
  track d2)` args.
- S2 — step-fire loop, `0x40095afa`. Same idiom: `moveq #3,d0;
  cmp.l d2,d0; blt → 0x40095b4e` (MIDI-fire) else synth-fire
  `0x4009451e` + `bra 0x40095b60`. `d2` is proven track:
  `move.l d2,$8(a0)` stamps `FW_EVENT_TRACK` before the fork, so
  MIDI events carry 4–7, synth events 0–3. Synth-fire =
  `0x4009451e`, MIDI-fire = `0x400948c0` (separate routines;
  seq-events-dn1 hooks 8 s-sites `0x40094532–0x4009480a` + 7
  m-sites `0x400948d4–0x40094bc2`). Both scale pattern data by
  `track*976` (`muls #0x3d0` at `0x40094552`, `0x400948f4`); no
  masking, no type-field read.

## Probable UI dispatch sites (same idiom, divergent forks; compared register not fully traced to track)

- S3 — voice-view presenter, `0x4003df40` (`moveq #3,d0; cmp.l d4,d0;
  blt → 0x4003df82`). In routine at `0x4003df06` where
  `d4 = jsr $4002c6ba($a8(a2))`. Synth fork calls
  `0x400e8be8/0x40158770/0x400e54a2` + `SP_RELEASE 0x40146456`;
  MIDI fork calls `0x400dc23c`. Same `0x400e8be8`-gate shape recurs
  at S4 `0x40043258` (`cmp.l d2; blt → 0x400432a0`, then
  `jsr $4002f91a(d2, $74(a2))`).
- S5 `0x4003ca70` (`cmp.l d6; blt → 0x4003cab2 → jsr 0x400ded80`)
  vs synth fork (`$a8(a2)` → `0x4001dcf2` →
  `0x40031ce2/0x40031972`).
- S6 `0x400bbd84` (`cmp.l d6; blt → "FX"-string path
  `pea $401da9fa + jsr (a2)`) vs `pea "TRK.%d" ($401e1e6d) +
  pea 1+d6` — track-label/menu dispatch.
- S7 `0x40061ce4` (`cmp.l d3; blt`): forks differ only in `"T%d"`
  (`$401dc677`) vs `"XX"` (`$401dc67f`) format strings — UI label
  dispatch.
- S8 `0x40160968` (`cmp.l d0; blt → 0x4016098a`
  sets `-$2c(a6)=$f` + `jsr (a3)`) vs `jsr $401880e6` + virtual
  `jsr (a0)` with d0 — param/page region, needs dataflow to confirm.
- S9 `0x400e31a2` is a synth-only loop (`cmp.l d2,#3; blt →
  rts-exit`, body `jsr (a0)`, `d2+=1`) — synth engine iterates 0–3
  separately (no MIDI counterpart in that routine).
- Deprioritized: `0x40007f1c/0x400083e4/0x40008b4e/0x40009902/
  0x40009d22` (saturating `min(x,3)` clamp idiom — forks
  reconverge, no divergent behavior);
  `0x4008fa08/0x4008c62c/0x400a018a/0x4010d13a/0x40046d30`
  (counters/chained range checks vs 3-and-5, length math, object
  gates — not track-shaped).

## Per-track field: none found

- The 8-track init loop `0x4000906c–0x400090b0` calls `INIT_SEQ
  0x40015180` + `INIT_CONF 0x4001511c` identically for all 8 slots
  (`mode=0`, `locks=0`, stride `+0x3d0` until `0x1e80`):
  `INIT_CONF` writes `$3c0–$3cf` (NOTE `$3c0=$3c`, LEN `$3c5=$10`,
  ROOT `$3cb=$3c`, SCALE `$3ce=$ff`, `$3ca=4`, `$3c7=2`,
  `$3c8=$64`); `INIT_SEQ` writes step words, `$80/$c0/$100/$140/
  $17f` flags, `$1c0` notes + optional lock table via
  `jsr $400fbb20`. No track-index-dependent byte anywhere in
  either routine.
- The only other `INIT_CONF` caller is the tail-jump thunk
  `0x400360d8→jmp 0x4001511c` (no in-code callers found — likely
  register-called or legacy).
- Anchors (core-dn1 1.44 defsym): `FW_ACTIVE_TRACK 0x41368ce0`,
  `FW_PATTERN 0x4138f214`, `FW_KIT 0x4138f220`, `FW_TRANSPORT
  0x4138f208`, `MEMCPY 0x400fbad8`, `SP_RELEASE 0x40146456`,
  `KEYDISP 0x40016fc0`. The 9 active-track readers are all
  index-agnostic (clamp to 0–7 at `0x400ea168`, `==active`
  compares at `0x400ea25e/0x400ea3a0`, bitmask loop at `0x400eb1c6`
  over tracks 0–7 vs `PAT_SLOT 0x1611d`) — none is a type branch.
  The 41 pattern-refs are small accessors (e.g. `get_cur_ptn
  0x4009446a`); the 13 kit-refs pass the kit base into the fire
  routines, which index it arithmetically.

## Implication

Mechanism = "hardcoded `track<4` branches": 2 confirmed (S1, S2)
+ ~6 probable UI sites (S3–S8) + 1 synth-only loop (S9). No field
to flip, no vtable to swap. The audio path needs only S1+S2
(mute/voice logic is already index-agnostic over 0–7), while full
conversion (browser, voice menu, labels, params) needs the UI
sites too. Downstream code (`track*976` pattern, `track*326` kit
sounds at `kit+0x18`, MIDI params at `kit+0x5ce`,
`PAT_MUTES_OFFSET 0x16108`) is pure arithmetic on the passed
index and needs no changes if the dispatch sites route converted
tracks to the synth side.
