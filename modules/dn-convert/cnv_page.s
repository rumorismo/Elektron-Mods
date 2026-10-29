| SPDX-License-Identifier: GPL-2.0-or-later
| dn-convert: synth param-page parity divert (8track-engine task 3.4).
|
| The live page dispatch is the page function at 0x4004221c (found
| dynamically: the spike's S8 0x40160968 and S5 0x4003ca70 sites never
| execute on any page gesture across banks — sweep + chain legs prove
| them silent, so per the no-blind-patch rule they are NOT interposed;
| see tests/probe/cnv_pages.py). The page function calls the c6ba
| view-track reader, keeps d4 = result (proven == ACTIVE track on page
| opens for native 0-3, converted 4-7 and native-MIDI 5-7), compares
| vs 3 at P_CMP 0x40042258, and runs the synth page chain (P_GATE
| 0x40042530 -> c1dcf2 row fetch -> c31972 session virtuals). The row
| fetch resolves the page's sound through row+16 (proven ==
| kit+0x18+326t on natives — the same +16 mechanism as the browser
| rows in cnv_browse.s).
|
| P1 — view-track call at 0x40042240, 6 bytes over
|   jsr 0x4002c6ba (session -> view track)
| The detour covers the bare jsr (the caller's move.l a8(a2),-(sp)
| already pushed the session arg; the rejoin keeps it for the later
| addq), so like B0/B5/B6 the single exit is rts: the helper re-runs
| the stock reader by pointer (B0 discipline) and maps a converted
| track to its mirror slot; native rejoins with the stock value
| bit-exactly. d1/a0-a1 saved (C scratch); d0 carries the result.
| d4 (the page function's track, set from d0 at 0x40042248) becomes
| the mirror slot on the converted path; the row fetch (P2) tells the
| converted slot apart via fw_active_track (V8 precedent).
|
| P2 — page-row fetch at 0x4004253c, 6 bytes over
|   move.l d4,(sp)- | move.l X,(sp)- | jsr 0x4001dcf2
| d4 = track (mirror-mapped by P1 on the converted path), X = the row
| table. The pushes land the table on TOP ([site-ret][table][track]):
| C right-to-left order gives the helper (table, track). Converted:
| the C helper copies the mirror row into the mod page row, wires +16
| to the slot's .bss sound, and the detour returns the mod row in d0
| via rts (d0 is outside the save set, like B0/B2). Native: jmp to
| 0x4001dcf2 — its rts consumes the site return and rejoins
| 0x40042542 (the pushes already happened, so nothing is replayed and
| no stack fixup is needed). d1/a0-a1 saved (C scratch); d0 carries
| the result; d2-d7/a2-a6 survive the C call per ABI.

        .section .run, "ax"

| int cnv_page_track(void *session): mirror slot or stock track.
| Clobbers d0-d1/a0-a1 (d0 is the rejoin value, like B0/B5/B6).

        .globl  cnv_site_p1
cnv_site_p1:
        lea     -12(%sp), %sp
        movem.l %d1/%a0-%a1, (%sp)
        move.l  16(%sp), -(%sp)
        jsr     cnv_page_track
        addq.l  #4, %sp
        movem.l (%sp), %d1/%a0-%a1
        lea     12(%sp), %sp
        rts

| uint8_t *cnv_page_row_for(uint8_t *table, int track): mod row or 0.
| Clobbers d1/a0-a1 (saved); d0 carries the result, d2-d7/a2-a6
| survive (d4 = the caller's track is untouched: the helper reads the
| track from the already-pushed stack words).

        .globl  cnv_site_p2
cnv_site_p2:
        lea     -12(%sp), %sp
        movem.l %d1/%a0-%a1, (%sp)
        move.l  20(%sp), -(%sp)
        move.l  20(%sp), -(%sp)
        jsr     cnv_page_row_for
        addq.l  #8, %sp
        tst.l   %d0
        movem.l (%sp), %d1/%a0-%a1
        lea     12(%sp), %sp
        beq.s   cnv_p2_stock
        rts
cnv_p2_stock:
        | Call-site shape: the pushes already happened, so jmp to the
        | stock callee; its rts consumes the site return (rejoin
        | 0x40042542, which pushes the row for the c31972 chain).
        jmp     0x4001dcf2

| P3 — view-9 gate branch at 0x40042da8, 6 bytes over
|   move.l d0,d2 | beq.w -> 0x40042e5e (skip)
| d0 = the first virtual's verdict (9 = synth view on natives, proven;
| 0 on converted/MIDI). The detour covers the whole move+branch (B1
| discipline): the C helper takes (caller, verdict) — the caller is
| the v84 return at detour-entry-sp+40 — and forces the synth
| fallthrough only when the verdict is 0 for the MIDI-page renderer
| caller with a converted slot active (V8 caller+ACTIVE guard);
| otherwise the stock move+branch replays bit-exactly (fallthrough
| rejoins 0x40042dae via rts; the skip pops the site return and
| jmps, the S1/S2 jmp discipline). Forced d0 = 9, the proven native
| view-9 verdict, so the downstream flow (viewfn d2 = 9 -> P1 -> P2)
| runs exactly as on native. d0-d1/a0-a1 saved; d2-d7/a2-a6 survive.

        .globl  cnv_site_p3
cnv_site_p3:
        lea     -16(%sp), %sp
        movem.l %d0-%d1/%a0-%a1, (%sp)
        move.l  %d0, -(%sp)
        move.l  60(%sp), -(%sp)
        jsr     cnv_view9_path
        addq.l  #8, %sp
        tst.l   %d0
        movem.l (%sp), %d0-%d1/%a0-%a1
        lea     16(%sp), %sp
        beq.s   cnv_p3_stock
        | Force path: reproduce the taken-fallthrough register state
        | (d0 = d2 = 9) and rejoin the synth leg. The site-jsr return
        | is still pushed (fallthrough pushes nothing): drop it first,
        | then replay the move and jmp to the fallthrough (S1/S2 jmp
        | discipline; jmp consumes nothing).
        moveq   #9, %d0
        addq.l  #4, %sp
        move.l  %d0, %d2
        jmp     0x40042dae
cnv_p3_stock:
        | Stock replay, bit-exact: the move sets the CCR exactly like
        | stock, so the branch still governs on the verdict.
        move.l  %d0, %d2
        beq.s   cnv_p3_skip
        rts
cnv_p3_skip:
        | Skip exit: jmp leaves the site return pushed, stock beq
        | pushes nothing: drop it first (S1/S2 jmp discipline).
        addq.l  #4, %sp
        jmp     0x40042e5e

| P4 — content-fork branch at 0x4003f184, 6 bytes over
|   moveq #3,d0 | cmp.l d3,d0 | bcs -> 0x4003f190 (MIDI table)
| d3 = track (proven == ACTIVE on page-key opens), d2 = page index.
| The detour covers the whole moveq+cmp+bcs (B1 discipline): the C
| helper takes the track in d3 (callee-saved, survives the call) and
| forces the synth-table fallthrough for converted tracks, else
| replays the stock fork bit-exactly (fallthrough rejoins
| 0x4003f18a via rts; the MIDI exit pops the site return and jmps,
| the S1/S2 jmp discipline). d3 is NOT rewritten (downstream state
| stays indexed by the real track/ACTIVE). d0-d1/a0-a1 saved;
| d2-d7/a2-a6 survive; MOVEM/LEA never touch the CCR, so the tst
| still governs the branch.

        .globl  cnv_site_p4
cnv_site_p4:
        lea     -16(%sp), %sp
        movem.l %d0-%d1/%a0-%a1, (%sp)
        move.l  %d3, -(%sp)
        jsr     cnv_c3_route
        addq.l  #4, %sp
        tst.l   %d0
        movem.l (%sp), %d0-%d1/%a0-%a1
        lea     16(%sp), %sp
        beq.s   cnv_p4_midi
        moveq   #3, %d0
        cmp.l   %d3, %d0
        rts
cnv_p4_midi:
        | MIDI exit: jmp leaves the site return pushed, stock bcs
        | pushes nothing: drop it first (S1/S2 jmp discipline). ADDQ
        | before the replayed CMP keeps the fork's CCR exact.
        addq.l  #4, %sp
        moveq   #3, %d0
        cmp.l   %d3, %d0
        jmp     0x4003f190

| C1 — MAIN-page content-filler branch at 0x4003db2c, 6 bytes over
|   moveq #3,d1 | cmp.l d3,d1 | bcs -> 0x4003db3c (MIDI table)
| d3 = track (proven == ACTIVE on TRIG opens: native 0 synth table
| a2+0xf0, converted 4 and native-MIDI 5 MIDI table a2+0x148 —
| trigsweep + maintrace legs in tests/probe/cnv_mainpage.py; fork
| taken diverges exactly on converted). Same entry-copy shape as P4
| (synth table a2+0xf0 vs MIDI table a2+0x148, the bank-views
| registry): P4's filler (0x4003f184) never runs on the TRIG open
| flow (0 fork hits on converted TRIG), so the refresh-time C fill
| is the only views fill the MAIN page gets: stock C fills MIDI
| views every frame on the converted MAIN page. The detour covers
| the whole
| moveq+cmp+bcs (B1 discipline): the C helper takes the track in d3
| (callee-saved, survives the call) and forces the synth-table
| fallthrough for converted tracks, else replays the stock fork
| bit-exactly (fallthrough rejoins 0x4003db32 via rts; the MIDI exit
| pops the site return and jmps, the S1/S2 jmp discipline). d3 is
| NOT rewritten (downstream state stays indexed by the real
| track/ACTIVE). d0-d1/a0-a1 saved; d2-d7/a2-a6 survive; MOVEM/LEA
| never touch the CCR, so the tst still governs the branch.
| Reuses the P4 predicate cnv_c3_route (no new C code).

        .globl  cnv_site_c1
cnv_site_c1:
        lea     -16(%sp), %sp
        movem.l %d0-%d1/%a0-%a1, (%sp)
        move.l  %d3, -(%sp)
        jsr     cnv_c3_route
        addq.l  #4, %sp
        tst.l   %d0
        movem.l (%sp), %d0-%d1/%a0-%a1
        lea     16(%sp), %sp
        beq.s   cnv_c1_midi
        moveq   #3, %d1
        cmp.l   %d3, %d1
        rts
cnv_c1_midi:
        | MIDI exit: jmp leaves the site return pushed, stock bcs
        | pushes nothing: drop it first (S1/S2 jmp discipline). ADDQ
        | before the replayed CMP keeps the fork's CCR exact.
        addq.l  #4, %sp
        moveq   #3, %d1
        cmp.l   %d3, %d1
        jmp     0x4003db3c

| A1 — MAIN value-resolver mirror at 0x4001d860, 6 bytes over
|   moveq #3,d2 | cmp.l d1,d2 | bcs -> 0x4001d87a (MIDI math)
| d1 = track (proven == ACTIVE on TRIG opens: native 0 synth math
| track*20+0xd00, converted 4 and native-MIDI 5 MIDI math
| (track+0x1d3)*8 — trigsweep + maintrace + override legs in
| tests/probe/cnv_mainpage.py; the MIDI fork taken diverges exactly
| on converted, and a live d1->slot override flips the converted
| TRIG knob values to the slot's synth struct while a d0->0
| override at S4B changes nothing). The shared track->struct
| resolver feeds the MAIN page's knob values: converted slots take
| the mirror slot's synth entry, natives replay stock bit-exactly.
| The C helper maps a converted track to its mirror slot and
| rejoins every other track unchanged; the detour writes the
| mirror into the saved d1 slot, replays the stock moveq+cmp+bcs
| (B1 discipline: fallthrough rejoins 0x4001d866 via rts; the MIDI
| exit pops the site return and jmps, the S1/S2 jmp discipline).
| Stock clobbers d1 in both forks (exit d1 = the offset), so the
| caller cannot rely on the entry value surviving; the exit offset
| is exactly what stock computes for the mirror track. d0-d1/a0-a1
| saved; d2-d7/a2-a6 survive; MOVEM/LEA never touch the CCR, so
| the replayed CMP governs the branch.

        .globl  cnv_site_a1
cnv_site_a1:
        lea     -16(%sp), %sp
        movem.l %d0-%d1/%a0-%a1, (%sp)
        move.l  %d1, -(%sp)
        jsr     cnv_mirror_track
        addq.l  #4, %sp
        move.l  %d0, 4(%sp)
        movem.l (%sp), %d0-%d1/%a0-%a1
        lea     16(%sp), %sp
        moveq   #3, %d2
        cmp.l   %d1, %d2
        bcs.s   cnv_a1_midi
        rts
cnv_a1_midi:
        | MIDI exit: jmp leaves the site return pushed, stock bcs
        | pushes nothing: drop it first (S1/S2 jmp discipline).
        addq.l  #4, %sp
        jmp     0x4001d87a

| P5a/P5b — param-edit sound virtuals, 6 bytes each over
|   movea.l $28(a1),a0 | jsr (a0)   [row session +$28 = *(row+16)]
| P5a at 0x4002102a (synth-editor `20690028 4e90`), P5b at 0x400215d0
| (MIDI-editor `20690028 4e90`). Same C helper (ACTIVE-guarded, no
| args needed): converted slots get the .bss sound base (the caller
| applies its param offset), everything else replays the stock
| virtual via jmp (a0) — whose rts consumes the site return and
| rejoins site+6 (the pushed row arg is dropped by the rejoin's
| addq, like P2/B2). d1/a0-a1 saved (C scratch); d0 carries the
| result; d2-d7/a2-a6 survive per ABI.

        .globl  cnv_site_p5a
cnv_site_p5a:
        lea     -12(%sp), %sp
        movem.l %d1/%a0-%a1, (%sp)
        jsr     cnv_edit_snd_for
        tst.l   %d0
        movem.l (%sp), %d1/%a0-%a1
        lea     12(%sp), %sp
        beq.s   cnv_p5a_stock
        rts
cnv_p5a_stock:
        jmp     (%a0)

        .globl  cnv_site_p5b
cnv_site_p5b:
        lea     -12(%sp), %sp
        movem.l %d1/%a0-%a1, (%sp)
        jsr     cnv_edit_snd_for
        tst.l   %d0
        movem.l (%sp), %d1/%a0-%a1
        lea     12(%sp), %sp
        beq.s   cnv_p5b_stock
        rts
cnv_p5b_stock:
        jmp     (%a0)
