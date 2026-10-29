| SPDX-License-Identifier: GPL-2.0-or-later
| dn-convert: synth-fire fetch interposition (8track-engine task 1.2).
|
| Site F3 — synth-fire 0x4009451e epilogue at 0x40094832, 22 bytes over
|   move.l #0x146,d0 | mul.l d0,d4 | movea.l $68(a7),a0
|   | lea $18(a0,d4.l),a0 | move.l a0,$2c(a2)
| At entry d4 is the firing TRACK (0-7, verified live: entry values 0 and
| 3 on a stock bar; the mul inside turns it into track*326), a2 is the
| voice/event struct, and a0 after the kit load equals [0x4138f220] 8/8.
| Rejoin is 0x40094848 (bra.s — reads no CCR).
|
| The routine calls cnv_fetch_fire(track) with the scratch registers
| saved. A 0 return means the stock kit record: the 5 instructions replay
| verbatim (the site jsr pushed a return address stock never pushed, so
| the frame-relative kit load moves $68 -> $6C; everything else is
| position-independent) and rts rejoins. A nonzero return is
| &cnv_synth_snd[track-4]: publish it to $2c(a2), leave d4 in stock shape
| (track*326, so every downstream d4 use is bit-identical) and rts to the
| rejoin — the rts consumes the site-jsr return itself. The C call already warmed the voice cache
| (map-scoped zero, all-8 fallback) so CPU #1 reloads the .bss record.
| MOVEM/LEA never touch the CCR, so the beq still sees the result test.
| No path ends in jmp: both exit via rts, so the site return is consumed
| by the rts itself on both paths (the 1.1 lesson applied in reverse:
| S1/S2's jmp exits needed an explicit pop because jmp never pops; an
| rts exit must NOT pop first).

        .section .run, "ax"

| uint8_t *cnv_fetch_fire(int track): .bss record, or 0 for stock path.
| Preserves d2-d7/a2-a6; clobbers d0-d1/a0-a1 (saved by the caller).

        .globl  cnv_site_f3
cnv_site_f3:
        lea     -16(%sp), %sp
        movem.l %d0-%d1/%a0-%a1, (%sp)
        move.l  %d4, -(%sp)
        jsr     cnv_fetch_fire
        addq.l  #4, %sp
        move.l  %d0, 8(%sp)
        tst.l   %d0
        movem.l (%sp), %d0-%d1/%a0-%a1
        lea     16(%sp), %sp
        beq.s   cnv_f3_stock
        | Converted: %a0 = &cnv_synth_snd[d4-4], %d4 = track, %a2 intact,
        | site return on top of %sp.
        move.l  %a0, 0x2c(%a2)
        muls.w  #326, %d4
        | No site-return pop here: unlike the S1/S2 MIDI jmp exits, this
        | path leaves via rts, and the rts itself must consume the site
        | jsr return (rejoin 0x40094848). Popping first would skip it and
        | return into the stock frame.
        rts
cnv_f3_stock:
        move.l  #0x146, %d0
        muls.l  %d0, %d4
        movea.l 0x6c(%a7), %a0
        lea     0x18(%a0,%d4.l), %a0
        move.l  %a0, 0x2c(%a2)
        rts
