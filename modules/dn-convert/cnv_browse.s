| SPDX-License-Identifier: GPL-2.0-or-later
| dn-convert: sound-browser parity interpose (8track-engine task 3.1).
|
| Four sites, one per proven dispatch/row point (see cnv_browser.md for
| the identification evidence). Whole-instruction/jsr discipline throughout
| (cnv_route.s S1/S2 + cnv_fetch.s F3 precedent): each detour covers whole
| stock instructions, saves the scratch regs the stock code still needs
| (d0-d1/a0-a1, or the subset it clobbers), calls a C helper, then either
| replays the displaced work exactly and returns to the fallthrough, or
| pops the site return first (addq.l #4,%sp, before the replayed CMP — the
| S1/S2 MIDI-jmp discipline) and jumps to the stock fork. An rts exit
| consumes the site-jsr return itself (the F3 discipline) and must NOT pop
| first. MOVEM/LEA never touch the CCR, so a tst/cmp before the restore
| still governs the branch after it.
|
| B0 — T-key bank-check call at 0x4004ef1a, 6 bytes over
|   move.l a2@(132),(sp)- | jsr 0x4002e1ae (returns 0 = synth bank)
| The site jsr pushed a return stock never pushed on the divert path... but
| BOTH exits here are rts (rejoin 0x4004ef20: addq #4,sp | tst.b d0 |
| beq -> 0x4004ef2e synth path): rts consumes the site return on both
| paths, so NO pop is needed (unlike the S1/S2 jmp exits). The pushed cell
| arg stays for the rejoin's addq. d4 is OUTSIDE the save set on purpose:
| the divert path sets d4 = track (ef3e's move.l d4,d3 then carries it).
| d0 is also outside the set: it carries the helper result (track 4..7 =
| divert, else the stock bank value) straight to the rejoin's tst.
| C preservation covers the rest (d2-d3/d5-d7/a2-a6 survive per ABI).
| Native: helper re-ran the bank check through the same cell arg, d0 =
| stock bank value, rejoin behaves bit-exactly.
|
| B1 — browser open branch at 0x4004eda8, 6 bytes over
|   moveq #3,d1 | cmp.l d2,d1 | bcs -> 0x4004edf6 (MIDI path)
| d2 is the track (proven: ed68 fp+8 = pushed d3 = track; dcf2 logs
| index = track). Same shape as S1/S2: synth fallthrough rejoins at
| 0x4004edae via rts; MIDI exit pops the site return first, then replays
| the CMP (ADDQ before CMP keeps the fork's CCR exact) and jmps.
|
| B2 — browser-row call site at 0x4004edb2, 6 bytes over
|   move.l d2,(sp)- | move.l d0,(sp)- | jsr 0x4001dcf2 (row = base+96+808t)
| d2 = track, d0 = table base. The pushes land base on TOP
| ([site-ret][d0=base][d2=track]): the stack track (orig sp+8) is
| pushed first, then the stack base (shifted). C right-to-left order
| gives the helper (table, track). Converted: the C helper copies
| the mirror native row into the mod row, wires +16 to the slot's
| cache, and the detour returns the mod row in d0 via rts (d0 is outside
| the save set, like B0). Native: jmp to 0x4001dcf2 — its rts consumes
| the site return and rejoins 0x4004edb8 (the pushes already happened, so
| nothing is replayed and no stack fixup is needed).
|
| B3 — apply row computation at 0x4001d73e, 8 bytes over
|   muls.l d0,d2 | lea 0x60(a3,d2.l),a2 (row = table+96+808t; d2 = track)
| d0 = 808 here (set by the preceding move.l, outside the site). The
| helper takes (table = a3, track = d2). Converted: a2 = mod row (set
| before the restore — a2 is outside the save set, like B0's d4) and
| d2 -= 4 (slot, so the following stock deref loads the synth session
| object, not a MIDI-row object); the helper already rewired +16 to .bss
| and invalidated the cache. Native: replay muls+lea verbatim, rts.
| The SDK nop-pads the 6-byte jsr to the 8-byte stock length.

        .section .run, "ax"

| int cnv_brow_open(void *cell, int keycode): converted track or stock bank.
| Clobbers d0-d1/a0-a1 (saved); d4 is the divert output, d0 the rejoin value.

        .globl  cnv_site_b0
cnv_site_b0:
        lea     -12(%sp), %sp
        movem.l %d1/%a0-%a1, (%sp)
        move.l  %d3, -(%sp)
        move.l  20(%sp), -(%sp)
        jsr     cnv_brow_open
        addq.l  #8, %sp
        cmp.l   #4, %d0
        blt.s   cnv_b0_stock
        cmp.l   #7, %d0
        bgt.s   cnv_b0_stock
        move.l  %d0, %d4
        movem.l (%sp), %d1/%a0-%a1
        lea     12(%sp), %sp
        moveq   #0, %d0
        rts
cnv_b0_stock:
        movem.l (%sp), %d1/%a0-%a1
        lea     12(%sp), %sp
        rts

| int cnv_is_converted_track(int track): 1 = converted slot, else 0.
| (Narrower than the B1 predicate: native synth tracks must replay stock.)

        .globl  cnv_site_b1
cnv_site_b1:
        lea     -16(%sp), %sp
        movem.l %d0-%d1/%a0-%a1, (%sp)
        move.l  %d2, -(%sp)
        jsr     cnv_route_synth
        addq.l  #4, %sp
        tst.l   %d0
        movem.l (%sp), %d0-%d1/%a0-%a1
        lea     16(%sp), %sp
        beq.s   cnv_b1_midi
        moveq   #3, %d1
        cmp.l   %d2, %d1
        rts
cnv_b1_midi:
        | Same site-return pop as S1/S2: jmp leaves it pushed, stock bcs
        | pushes nothing. ADDQ before the replayed CMP keeps CCR exact.
        addq.l  #4, %sp
        moveq   #3, %d1
        cmp.l   %d2, %d1
        jmp     0x4004edf6

| uint8_t *cnv_brow_row_for(uint8_t *table, int track): mod row or 0.
| Clobbers d1/a0-a1 (saved); d0 carries the result, d2 survives the C call.

        .globl  cnv_site_b2
cnv_site_b2:
        lea     -12(%sp), %sp
        movem.l %d1/%a0-%a1, (%sp)
        clr.l   -(%sp)
        move.l  24(%sp), -(%sp)
        move.l  24(%sp), -(%sp)
        jsr     cnv_brow_row_for
        lea     12(%sp), %sp
        tst.l   %d0
        movem.l (%sp), %d1/%a0-%a1
        lea     12(%sp), %sp
        beq.s   cnv_b2_stock
        rts
cnv_b2_stock:
        | Call-site shape: the pushes already happened, so jmp to the
        | stock callee; its rts consumes the site return (rejoin 0x4004edb8).
        jmp     0x4001dcf2

| B4 — browser open-gate at 0x4004edfe, 6 bytes over
|   addq.l #4,a7 | cmp.l d0,d2 | beq -> 0x4004ee68 (skip switch block)
| d2 is the track (proven: B1 logs d2 = 4 on converted taps, 0 native;
| ed68 entry arg, untouched from 0x4004ed94 to the site). d0 is the
| view-track reader c6ba(0x4002c6ba) result: 0 while the synth view sits
| on track 0; it never reports a converted slot, so converted always
| falls into the stock track-switch block at 0x4004ee04, which runs to
| completion yet never lands the slot on a synth view (0/25+ doubles, fb
| always back on the select page — see cnv_browser2.md). The native open
| path (view-track == tapped track, beq taken to 0x4004ee68) proves the
| row setup already done above (B2 mod row + stock render calls) plus the
| caller refresh is sufficient to open the browser.
| Converted skips ONLY on the f218 double-tap caller (ed68 caller ret
| 0x4004f21c at 44(sp) — proven 9/9: f1de for boot/convert/MIDI-select,
| f21c only for the double-tap second press). Every other caller keeps
| the stock switch block: it is load-bearing outside double-taps.
| Native/MIDI: replay the compare bit-exactly. Stack discipline: the
| site-jsr return sits ATOP the pushed d3arg, so a naive addq replay drops
| the ret and rets into the d3arg word as PC (observed: illegal jump to
| the $84(a2) view word 0x41a720d0). Jmp exits drop both words first; the
| rts exit reshapes [ret][d3arg] into [ret] with a d1 scratch.

        .globl  cnv_site_b4
| B4 detour: the site replaces addq+cmp+beq, but the site-jsr return sits
| ATOP the pushed d3arg, so a naive replay (addq+rts) drops the ret and
| rets into the d3arg word as PC. Every exit below accounts for [ret]
| [d3arg]: rts paths juggle the words back, jmp paths drop both first.
cnv_site_b4:
        lea     -16(%sp), %sp
        movem.l %d0-%d1/%a0-%a1, (%sp)
        move.l  %d2, -(%sp)
        jsr     cnv_is_converted_track
        addq.l  #4, %sp
        tst.l   %d0
        beq.s   cnv_b4_rejoin
        | converted (helper = 1): scratch regs still saved, so d0 is free.
        | sp = site-sp-20 here (lea16 + movem + pushed d2, jsr ret popped);
        | the ed68 caller ret at site-sp+44 = 64(sp) (proven: f1de boot and
        | f21c double-tap second press, 9/9 at the site-sp+44 slot).
        | Only the f218 double-tap caller (0x4004f21c, proven 9/9: f1de for
        | boot/convert/MIDI-select, f21c for the double-tap second press)
        | may skip the switch block; every other caller keeps the stock
        | switch, which is load-bearing outside double-taps.
        move.l  64(%sp), %d0
        cmp.l   #0x4004f21c, %d0
        bne.s   cnv_b4_rejoin
        movem.l (%sp), %d0-%d1/%a0-%a1
        lea     16(%sp), %sp
        addq.l  #8, %sp
        jmp     0x4004ee68
cnv_b4_rejoin:
        movem.l (%sp), %d0-%d1/%a0-%a1
        lea     16(%sp), %sp
        cmp.l   %d0, %d2
        bne.s   cnv_b4_rts
        addq.l  #8, %sp
        jmp     0x4004ee68
cnv_b4_rts:
        | Untaken replay: reshape [ret][d3arg] into [ret] for the rts.
        move.l  %d1, -(%sp)
        move.l  4(%sp), %d1
        move.l  %d1, 8(%sp)
        move.l  (%sp)+, %d1
        addq.l  #4, %sp
        rts
        .globl  cnv_site_b3
cnv_site_b3:
        lea     -16(%sp), %sp
        movem.l %d0-%d1/%a0-%a1, (%sp)
        moveq   #1, %d0
        move.l  %d0, -(%sp)
        move.l  %d2, -(%sp)
        move.l  %a3, -(%sp)
        jsr     cnv_brow_row_for
        lea     12(%sp), %sp
        tst.l   %d0
        move.l  %d0, %a2
        movem.l (%sp), %d0-%d1/%a0-%a1
        lea     16(%sp), %sp
        tst.l   %a2
        beq.s   cnv_b3_stock
        | Diverted: d2 = the stash slot (row_for set it on every divert;
        | the browser track in d2 is session-derived and reads 0 for our
        | mod rows). abs32, same reloc class as the existing .run->.bss.
        move.l  cnv_brow_last, %d2
        rts
cnv_b3_stock:
        muls.l  %d0, %d2
        lea     0x60(%a3,%d2:l), %a2
        rts

| B5 — browser-refresh gate call at 0x400400ec, 6 bytes over
|   jsr 0x40025b76 (track -> 1 synth / 2 / 0 else)
| Stock maps (u32)track <= 3 -> 1, == 8 -> 2, else 0; the caller
| continues to the 0x400e54a2 page-commit chain only on 1
| (0x400400f4: moveq #1,d1 | cmp.l d0,d1 | bne.w 0x40040d32), so a
| converted slot (track 4..7 -> 0) always bails and the view+0x17 /
| ctx+0x160/+0x164/+0x18c writers never run (proven: A4 = tapped track
| at the call — 0 native T1, 1 native T2, 4 converted slot 0 — with
| 25b76 returning 1 / 1 / 0; see the gate3/track2 probe legs).
| The detour covers the bare jsr (the caller's move.l a4,-(sp) already
| pushed the arg and the rejoin's addq.l #4,%sp drops it), so like B0
| the single exit is rts: the helper returns the commit decision in d0
| and rts consumes the site return, landing at 0x400400f2. Converted:
| d0 = 1. Native: the helper replicates the pure stock mapping
| bit-exactly (no memory touched, all inputs). d1/a0-a1 saved (C
| scratch); d0 carries the result, like B0/B2.

        .globl  cnv_site_b5
cnv_site_b5:
        lea     -12(%sp), %sp
        movem.l %d1/%a0-%a1, (%sp)
        move.l  16(%sp), -(%sp)
        jsr     cnv_brow_gate
        addq.l  #4, %sp
        movem.l (%sp), %d1/%a0-%a1
        lea     12(%sp), %sp
        rts

| B6 — preset-apply N/A-gate reader at 0x400cdb8e, 6 bytes over
|   jsr 0x4002c6ba (session -> view track)
| Stock feeds the result (0 native, 4 converted) into 0x40025b76 twice
| (0x400cdb9a/0x400cdba0 via d4); 25b76 maps (u32)track <= 3 -> 1, which
| the caller (0x400cdba6: moveq #1,d1 | cmp.l d0,d1 | beq 0x400cdc14)
| needs for the LOADED path (function B at 0x4001d710 + B3 stash
| divert); otherwise the "N/A ON THIS TRACK" toast fires (proven: d0 =
| 4 on converted YES, 0 native; see the c6ba legs). The detour covers
| the bare jsr (the caller's move.l d0,-(sp) already pushed the session
| arg and the later lea $10,%sp drops it), so like B0/B5 the single
| exit is rts: the helper re-runs the stock reader by pointer (B0
| discipline) and maps a converted track to its mirror slot; native
| rejoins with the stock value bit-exactly. d1/a0-a1 saved (C scratch);
| d0 carries the result, like B0/B2/B5.

        .globl  cnv_site_b6
cnv_site_b6:
        lea     -12(%sp), %sp
        movem.l %d1/%a0-%a1, (%sp)
        move.l  16(%sp), -(%sp)
        jsr     cnv_brow_gate_apply
        addq.l  #4, %sp
        movem.l (%sp), %d1/%a0-%a1
        lea     12(%sp), %sp
        rts
