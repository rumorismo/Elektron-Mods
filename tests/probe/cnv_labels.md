# 3.3 labels — close-out evidence (convert 0.19, tag 1482)

## Ruling (prove-before-patch)
- S6 `0x400bbd84`: d6 = track PROVEN, but silent for converted 4–7 and
  native-MIDI 5 (MIDI-bank scale page draws different rows) → left stock.
- S7 `0x40061ce4`, H1 `0x4006365c`: never execute on ~60 swept gestures → stock.
- L2 `0x4008393a`: fires but draws static T1..T4 (navigation, not identity) → stock.
- Voice-menu header/tabs/content ruled out (static tabs; content = per-preset
  heap structs + cached bitmap; no TRK.n/T n draw).

## Live site: L3 `0x400c28c2` (keyboard transpose row)
Stock 10 B `bc8d 6d26 4879418e934c`. Compared reg a5 = track PROVEN
(set once at view entry from `0x4002c6ea`; emu a5 == ACTIVE).
`cnv_site_l3`: converted → synth-shape row with custom "b%d" (mod .rodata)
+ value a5−3, selector 3, rejoin stock tail `0x400c2910`. Native → bit-exact
stock replay of both forks. (A replayed-pea-before-rts crashed live as
vector-4 at `0x418e934c`; fixed before relink.)

## Proof (snapshot `dn1-1482-f7466c0a`, SETTLED; raw JSONs were /tmp/opencode scratch)
- Converted 4/5/6/7 transpose row = "b1".."b4": PASS.
- Native 0/2 = "T1"/"T3", native-MIDI 5 = "M2", MIDI fork still executes: PASS.
- Flip-back slot 3 → "M4" via stock MIDI fork: PASS.
- Regression: voice-menu open parity, modal open/NO-cancel, browser
  single-tap + kit identity: PASS. Scale S6 native unchanged: PASS.
- All runs <60 s. Out of scope: converted scale page (3.4); audio hw-pending.

Build: convert 0.19 (12 sites, lint OK), tag 1482, `f7466c0a…`.
Harness: tests/probe/cnv_labels.py (+ cnv_labels_trace.py), re-runnable.
