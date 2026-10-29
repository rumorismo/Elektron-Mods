| SPDX-License-Identifier: GPL-2.0-or-later
| dn-convert: keyboard transpose-row label divert (8track-engine task 3.3).
|
| Site L3 — keyboard-view transpose row at 0x400c28c2, 10 bytes over
|   cmp.l a5,d6 | blt.b -> 0x400c28ec (MIDI fork) | pea.l $418e934c (view)
| a5 is the track: the view function (entry 0x400c23b2) sets it once from
| the 0x4002c6ea view-track reader (movea.l d0,a5 at 0x400c23da) and uses
| it as the row/track index throughout (lea (a2,a5.l) at 0x400c2836,
| pea 1(a5) / pea -3(a5) in the forks). Emu-proven (cnv_labels sweep
| legs): a5 == ACTIVE on the keyboard page for native 0 (7x synth fork),
| native 2 (5x synth), converted 4 (8x MIDI fork), native-MIDI 5 (5x
| MIDI fork). d6 is the constant 3 bound (moveq #3,d6 at 0x400c289c).
| Synth fork (a5 <= 3): pea 1(a5) + "T%d" + "XX" + 0,0 + $39 + 3, then
| the setup jsr (a0) (a0 = 0x400de9c8, lea at 0x400c28bc) and the common
| tail at 0x400c2910. MIDI fork (a5 > 3): pea -3(a5) + "M%d" + "XX" +
| 0,0 + $39 + 2. Converted slot 0 shows stock "M1" (value a5-3 = 1).
|
| The detour covers cmp+blt+pea (the lea that sets up a0 stays, and the
| synth rejoin is the jsr (a0) at 0x400c28cc). Whole-instruction/jsr
| discipline throughout (cnv_route.s S1/S2 + cnv_browse.s B1/B4
| precedent): the detour saves the scratch regs the stock code still
| needs (d0-d1/a0-a1; a5/d6 and d2-d5/d7/a2-a6 survive the C call per
| the m68k ABI), calls the C predicate, then either replays the stock
| fork decision exactly (native: own cmp+branch; synth path drops the
| site return, replays the pea and jmps to 0x400c28cc — a replayed pea
| must never precede an rts, it would bury the site return and rts
| would consume the pushed pointer as PC; MIDI path pops the site
| return first — the S1/S2 jmp discipline — and jmps to 0x400c28ec) or draws the converted
| row (pop site-ret, then the synth-fork shape with the custom "b%d"
| format from mod .rodata and the synth-style trailing 3: converted is
| synth-side everywhere else, e.g. the V8 voice-menu divert): pea view,
| jsr (a0) to reproduce d0 for the tail, pea slot+1 (a5-3, the same
| arithmetic as the MIDI fork), custom fmt, stock "XX", 0,0, $39, 3,
| then jmp to the common tail 0x400c2910. An rts exit consumes the site
| return itself (the F3 discipline) and must NOT pop first; jmp exits
| pop it first (the S1/S2 discipline). MOVEM/LEA never touch the CCR,
| so the helper tst still governs the branch after the restore.
|
| The sibling S6 0x400bbd84 ("TRK.%d", d6 = c6ba view-track result,
| proven == ACTIVE on the synth-bank scale page for 0 and 2) never
| executes for converted or native-MIDI tracks (the MIDI-bank scale page
| draws different rows), the S7 0x40061ce4 / H1 0x4006365c "T%d"/"TRK.%c"
| sites never execute on any swept gesture (~60 cells: voice menu,
| keyboard, scale, browser, PTN/GLOBAL/SONG walks, octave shifts), and
| the L2 0x4008393a voice-menu tabs draw static T1..T4 (values 1-4 on
| every open regardless of ACTIVE). Per the no-blind-patch rule those
| sites are NOT interposed (see tests/probe/cnv_labels*.py evidence).

        .section .run, "ax"

| int cnv_label_transp(int track): 1 = converted slot, else 0.
| Clobbers d0-d1/a0-a1 (saved); a5/d6 survive (a5 is the C arg).

        .globl  cnv_site_l3
cnv_site_l3:
        lea     -16(%sp), %sp
        movem.l %d0-%d1/%a0-%a1, (%sp)
        move.l  %a5, -(%sp)
        jsr     cnv_label_transp
        addq.l  #4, %sp
        tst.l   %d0
        movem.l (%sp), %d0-%d1/%a0-%a1
        lea     16(%sp), %sp
        beq.s   cnv_l3_native
        | Converted: synth-shape row with the b-label. The site-jsr
        | return is still pushed (jmp leaves it): drop it first.
        addq.l  #4, %sp
        pea.l   0x418e934c
        jsr     (%a0)
        pea.l   -3(%a5)
        pea.l   cnv_bfmt
        pea.l   0x401dc67f
        clr.l   -(%sp)
        clr.l   -(%sp)
        pea.l   0x39
        pea.l   3
        jmp     0x400c2910
cnv_l3_native:
        | Stock fork decision, replayed bit-exactly (d6 = 3 bound, a5 =
        | track; both survived the C call). NOTE: the replayed pea must
        | NOT precede an rts (the pea would bury the site return and rts
        | would consume the view pointer as PC — observed vector-4 at
        | 0x418e934c): pop the site-ret first, replay the pea, and jmp to
        | the rejoin (the S1/S2 jmp discipline; jmp consumes nothing).
        cmp.l   %a5, %d6
        blt.s   cnv_l3_midi
        addq.l  #4, %sp
        pea.l   0x418e934c
        jmp     0x400c28cc
cnv_l3_midi:
        | Same site-return pop as S1/S2/B1: jmp leaves it pushed, stock
        | blt pushes nothing. ADDQ before the replayed CMP keeps the
        | fork's CCR exact (harmless here: the fork target reads no CCR,
        | but the discipline costs nothing).
        addq.l  #4, %sp
        cmp.l   %a5, %d6
        jmp     0x400c28ec

        .section .rodata
| Converted-slot label format for the L3 transpose row ("b%d" + the
| slot+1 value the detour pushes, mirroring the MIDI fork's a5-3
| arithmetic: a5 = 4..7 -> 1..4 -> "b1".."b4").
cnv_bfmt:
        .asciz  "b%d"
