# 3.4 synth pages — close-out evidence (convert 0.23, tag 1486)

## Ruling (prove-before-patch)
- S8 `0x40160968` + S5 `0x4003ca70`: UNPROVEN spike notes confirmed —
  neither fires on param-page opens → left stock.
- Live dispatch: page function `0x4004221c` (P_CMP `0x40042258`,
  track vs 3). Interposed P1 `0x40042240` (view-track call → mirror slot
  for converted) + P2 `0x4004253c` (page-row fetch → mod row) + P3/P4/P5a/P5b
  (row/session wiring). 18 sites total, native paths bit-identical.

## Proof (snapshot `dn1-1486-71493c78`, SETTLED; raw JSONs/PNGs were /tmp/opencode scratch)
- knob: SYN1 on converted slot opens page, encoder turns change `.bss`
  (snd_changed, 2 bytes), kit + MIDI params untouched: PASS.
- timbre: converted page PLAY voices (energy 13M, pass:true): PASS.
- muteseq: sequencer sounds on converted slot (energy 146M): PASS.
- fixreg: voice-menu/modal/browser regression subset green: PASS.
- Two evidence runs exceeded the 60 s iteration budget (timbre 97 s,
  muteseq 75.7 s — long PLAY captures, one-off, not the iteration loop).

Build: convert 0.23 (18 sites, lint OK), tag 1486.
Harness: tests/probe/cnv_pages.py (stock/sweep/proof/chain/pageopen/knob/
timbre/muteseq legs), re-runnable.
