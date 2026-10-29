| SPDX-License-Identifier: GPL-2.0-or-later
| dn-convert: voice-menu bank divert (8track-engine task 3.2).
|
| Site V8 — voice-menu bank check at 0x4003f642, 6 bytes over
|   jsr 0x4002e1ae (bank check on the a8(a2) cell pushed just before)
| The plain-VOICE path runs the 0x4003f62e block for every track:
| ded04(view) must pass (bcc 0x4003f63a -> 0x400403bc MIDI), then this
| bank check must read synth (bne.w 0x4003f64c -> 0x400403bc MIDI on a
| nonzero low byte: stock synth verdict 0xbec97400, MIDI 0xbec97301);
| else bra 0x4003f650 -> 0x400407e2 (ded70 block -> 58770 menu builder
| at 0x400408de). Emu-proven (routeC legs): the site fires on plain
| VOICE for tracks 0-7 with the constant key-cell 0x40553e00 and
| ACTIVE == tapped track; ded04 already passes for converted slots, so
| the bank verdict alone excludes them (converted 4 and native-MIDI
| 5-7 take 0x400403bc, native 0-3 take the synth chain).
| The task's S3 0x4003df40 / S4 0x40043258 sites never execute on plain
| VOICE (or any swept gesture: FUNC+VOICE, pages, encoders, PTN, BANK,
| SONG, YES, T-select) — entries, sites and both forks stay silent
| across whole sessions, so per the no-blind-patch rule they are NOT
| interposed (see cnv_voicemenu.md); V8 is the live dispatch.
|
| Whole-instruction/jsr discipline (B0/B5 precedent): the detour covers
| the bare jsr (the caller's move.l a8(a2),-(sp) already pushed the cell
| arg and the rejoin's addq.l #4,%sp drops it), so the single exit is
| rts: the helper returns the commit value in d0 and rts consumes the
| site return, landing at 0x4003f648. Converted: d0 = 0 (low byte zero
| sets Z in the rejoin tst.b, so bne skips MIDI exactly like the stock
| synth verdict; d0 is dead past the fork — ded70's jsr clobbers it —
| so the zero payload cannot leak downstream). Native: the helper
| re-ran the stock check through the same cell arg (B0 discipline),
| bit-exact. d1/a0-a1 saved (C scratch); d0 carries the result.
| d2-d7/a2-a6 survive the C call per ABI (d2 is the constant view ptr
| the downstream ded70 block reuses untouched).

        .section .run, "ax"

| int cnv_voice_bank(void *cell): 0 = synth path, else stock bank value.
| Clobbers d0-d1/a0-a1 (d0 is the rejoin value, like B0/B5).

        .globl  cnv_site_v8
cnv_site_v8:
        lea     -12(%sp), %sp
        movem.l %d1/%a0-%a1, (%sp)
        move.l  16(%sp), -(%sp)
        jsr     cnv_voice_bank
        addq.l  #4, %sp
        movem.l (%sp), %d1/%a0-%a1
        lea     12(%sp), %sp
        rts
