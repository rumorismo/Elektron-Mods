| SPDX-License-Identifier: GPL-2.0-or-later
| dn-convert: S1/S2 dispatch interposition (8track-engine task 1.1).
|
| Stock firmware decides synth vs MIDI with a hardcoded `track > 3' fork
| at two audio sites (1.44 absolute addresses). Each site below covers
| whole stock instructions; its routine replays the displaced work
| exactly, then either returns (synth fallthrough) or jumps to the MIDI
| fork. Scratch registers the stock code still needs (d0-d1/a0-a1) are
| saved around the C call; d2 (track) survives it per the m68k ABI
| (d2-d7/a2-a6 callee-saved) and is passed on the stack. MOVEM/LEA never
| touch the CCR, so the TST flags survive the restore into the branch.
|
| S1 — first-step builder at 0x40094d44, 10 bytes over
|   moveq #3,d1 | move.b d7,$f3(a0) | cmp.l d2,d1 | blt -> 0x40094d74
| The $f3(a0) store is UNRELATED work: it is replayed on BOTH paths.
| Synth fallthrough (return address) is 0x40094d4e, which pushes
| (pattern, kit, track d2) and calls synth-fire 0x4009451e (pc-rel jsr).
| MIDI fork 0x40094d74 starts with moveq #1,d1.
|
| S2 — step-fire loop at 0x40095afa, 6 bytes over
|   moveq #3,d0 | cmp.l d2,d0 | blt -> 0x40095b4e
| The synth fallthrough is NOT the synth-fire call directly: it runs a
| lock/jsr prologue (jsr $400ffff2.l, setup, jsr 0x40100178), pushes
| (d7, 0, d0, d6, d5, track d2) and calls synth-fire 0x4009451e at
| 0x40095b48 (pc-rel jsr), rejoining at 0x40095b60. The MIDI fork at
| 0x40095b4e pushes the same shape and calls MIDI-fire 0x400948c0,
| rejoining at the same 0x40095b60. So routing before the prologue is
| sufficient: converted tracks take the whole stock synth path.
| d0 is dead past this fork on both sides (fallthrough overwrites it via
| the lock jsr; the MIDI fork's first use is a push), but it is replayed
| anyway so the fork entry state is bit-identical to stock.
|
| Stock 0-3 path: cnv_route_synth returns 1, the routine replays the
| displaced bytes and returns to the fallthrough — same fork, same args.
| Fetch interposition inside synth-fire 0x4009451e is task 1.2, NOT here.

        .section .run, "ax"

| int cnv_route_synth(int track): 1 = synth fork, 0 = MIDI fork.
| Preserves d2-d7/a2-a6; clobbers d0-d1/a0-a1 (saved by the caller).

        .globl  cnv_site_s1
cnv_site_s1:
        lea     -16(%sp), %sp
        movem.l %d0-%d1/%a0-%a1, (%sp)
        move.l  %d2, -(%sp)
        jsr     cnv_route_synth
        addq.l  #4, %sp
        tst.l   %d0
        movem.l (%sp), %d0-%d1/%a0-%a1
        lea     16(%sp), %sp
        beq.s   cnv_s1_midi
        moveq   #3, %d1
        move.b  %d7, 0xf3(%a0)
        cmp.l   %d2, %d1
        rts
cnv_s1_midi:
        | The site jsr pushed a return address that jmp will NOT pop
        | (stock blt pushes nothing): discard it so the fork sees the
        | exact stock stack. ADDQ runs before the replayed CMP, so the
        | fork's CCR still comes from CMP, exactly like stock.
        addq.l  #4, %sp
        moveq   #3, %d1
        move.b  %d7, 0xf3(%a0)
        cmp.l   %d2, %d1
        jmp     0x40094d74

        .globl  cnv_site_s2
cnv_site_s2:
        lea     -16(%sp), %sp
        movem.l %d0-%d1/%a0-%a1, (%sp)
        move.l  %d2, -(%sp)
        jsr     cnv_route_synth
        addq.l  #4, %sp
        tst.l   %d0
        movem.l (%sp), %d0-%d1/%a0-%a1
        lea     16(%sp), %sp
        beq.s   cnv_s2_midi
        moveq   #3, %d0
        cmp.l   %d2, %d0
        rts
cnv_s2_midi:
        | Same site-return pop as S1: jmp leaves it pushed, stock blt
        | pushes nothing. ADDQ before the replayed CMP keeps CCR exact.
        addq.l  #4, %sp
        moveq   #3, %d0
        cmp.l   %d2, %d0
        jmp     0x40095b4e
