# 3.1 browser parity — close-out evidence (convert 0.17, tag 1480)

## Chain (all interposes proven, native path bit-identical throughout)
- B0 `0x4004ef1a` bank-check divert, B1 `0x4004eda8` track>3 branch (d2=track proven),
  B2 `0x4004edb2` mod-row provider, B3 `0x4001d73e` apply-row computation,
  B4 `0x4004edfe` open-gate skip (converted + caller f21c only),
  B5 `0x400400ec` refresh-commit gate (`cnv_brow_gate`: converted 4..7→1),
  B6 `0x400cdb8e` apply-gate (`cnv_brow_gate_apply`: converted→mirror slot).
- Vector-4 fix: apply-path rows use stash-slot mirror + synth session
  (`0x40196104`→`0x401535c4`); zero vector-4 across all 0.17 runs.

## Full user path (snapshot `dn1-1480-c2213f11`, SETTLED)
Double-tap converted slot → browser opens (state bit-identical to native,
82 items) → DOWN draws pixel-identical to native (`0048b56645cd85ab`) →
YES → LOADED toast, `.bss` 101→91 nonzero, kit slot+tail untouched
(`ddba55ce`) → PLAY: F3 publishes SND from mod RAM, voices energy 20M+, `pass:true`.

## Legs (all <60s)
gate17 / open17 / single17 / native17 / kit17 / apply17 / voice17 — all PASS.
Raw JSONs were kept under /tmp/opencode/br17_*.json (scratch); the durable
proof is the snapshot + harness: tests/probe/cnv_browser3.py (re-runnable).

## Parked wart
Initial post-double paint stays stale (MIDI page) until first DOWN — state is
committed identically pre-DOWN. Needs a paint-scheduling gate proof; cosmetic,
out of 3.1 scope.

Build: convert 0.17 (10 sites, lint OK, RAM 16632/1310720), tag 1480,
`test-cnv17.syx` sha `c2213f11…`. Audio verdicts stay hw-pending.
