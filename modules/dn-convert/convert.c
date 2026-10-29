/* SPDX-License-Identifier: GPL-2.0-or-later
 * Copyright (C) 2026 Elektron-MODS contributors */
/* dn-convert: MIDI<->synth track converter core for the Digitone MK1.
 *
 * Task 2.1 modal gesture + task 2.2 shared trigs (convert 0.13).
 * interrupt-masked flip, following the tracks-dn1 discipline (mirror stash
 * in mod .bss, trk_swap_banks interrupt mask, TRK8-style projdata).
 * MIDI+VOICE on slots 4-7 opens a centered YES/NO card ("CONVERT TO
 * SYNTH?" / "RESTORE MIDI?", bank-HUD 96x28 geometry); YES runs the
 * masked flip, NO / ~2s timeout cancels with zero state change. Plain
 * VOICE falls through everywhere; chord on 0-3 falls through. While the
 * modal is open the chord is swallowed; after cancel plain VOICE still
 * opens the stock menu. Task 2.2: the live 976B pattern stays IN PLACE —
 * only stash/load = 326B synth sound (.bss, F3 fetch) <-> 164B MIDI
 * params (kit KIT_MIDI_OFF+slot*164, KIT_LIVE_LIMIT guard) + mute byte.
 *
 * Per slot, exactly one side is live:
 *   CNV_NATIVE  - stock MIDI live, nothing stashed;
 *   CNV_SYNTH   - converted synth live, MIDI side stashed;
 *   CNV_STASHED - flipped back to MIDI live, synth side stashed.
 *
 * Converted sound records live in mod .bss (spike-kit-capacity section 2).
 * The live kit's own 4 synth slots are never touched by this module, and
 * nothing is written past kit+0x85E. Kit-verdict (task 2.3, measured):
 * the tail past 0x85E is LIVE — a stock-RAM dump on settled 1.44
 * (fw_kit 0x41306294) shows the machine preset table starting at +0x85E
 * ("MACRO0".. with code pointers, then "DESTROYER FP", ...; 300/488
 * nonzero words in +0x85E..+0x1000). The kit cell is written only by
 * pointer-copy code in the sequencer/project-load region — no standalone
 * kit-sized op_new site was identified (2006 op_new calls scanned). So
 * there is no safe live-kit target: tail append would overwrite the
 * preset table, the 158B gap 0x530..0x5CE is too small, and overlaying
 * kit+0x5CE..0x85E stays rejected (Bank-A MIDI byte-identity, task 3.2).
 * Converted sounds stay staged in .bss; dispatch routing (S1/S2 sites,
 * cnv_route_synth) sends converted tracks down the stock synth fork, and
 * the F3 fetch interpose (task 1.2) serves converted fires from the .bss
 * record with voice-cache warm. Init timbre (sustain-trace 2026-10-28):
 * first conversion copies the live kit's slot-0 record (kit+0x18, 326B,
 * a known-good sounding patch) into .bss — a memset-0 record renders
 * silence with zero length, so the voices gate and allocate but die the
 * same tick (no sustain). The copy reads the kit only.
 * KIT_LIVE_LIMIT guards this: any future live-kit write must stay below it.
 */
#include "digitone-mk1/core3.h"

#define NUM_CONV_TRACKS     4
#define CONV_FIRST_TRACK    4
#define TRACK_DATA_SIZE     976
#define SOUND_REC_SIZE      326
#define MIDI_REC_SIZE       164
#define PAT_MUTES_OFFSET    0x16108

#define KIT_SYNTH_OFF       0x18
#define KIT_MIDI_OFF        0x5ce
/* Highest live-kit offset this module may touch. The MIDI-params restore
 * in cnv_to_midi ends at KIT_MIDI_OFF + 4*164 = 0x85E == KIT_LIVE_LIMIT. */
#define KIT_LIVE_LIMIT      0x85e
_Static_assert(KIT_MIDI_OFF + 4 * 164 <= KIT_LIVE_LIMIT,
               "MIDI params restore must not reach the preset table");

#define ADDR_AUDIO_MUTES    0x41392f30
#define ADDR_MIDI_MUTES     0x419c5b0c
#define ADDR_SET_AUDIO_MUTES 0x4009c8d4
#define ADDR_SET_MIDI_MUTES  0x400f3908
#define ADDR_SET_LED          0x40016e62
#define LED_T1                47
#define PAL_BRIGHT_GREEN      3
#define CNV_POPUP_TICKS       36  /* ~1.2s centered card, bank-HUD discipline */

typedef void (*fn_set_led_t)(void *mgr, int32_t led_code, int32_t state, int32_t pal_entry);

typedef void (*fn_set_mutes_t)(uint32_t mask);

/* Browser-row stash (defined with the browser interpose below). */
static int32_t cnv_brow_last;

/* Forward declarations: cnv_key (task 2.2) toggles via the flip pair. */
int32_t cnv_is_converted(int32_t slot);
int32_t cnv_to_synth(int32_t slot);
int32_t cnv_to_midi(int32_t slot);

/* Slot state: exactly one side live (see header comment). */
#define CNV_NATIVE   0   /* stock MIDI live, nothing stashed */
#define CNV_SYNTH    1   /* converted synth live, MIDI side stashed */
#define CNV_STASHED  2   /* MIDI live again, synth side stashed */

/* Dual stash in mod .bss, one entry per convertible slot (slot i = track 4+i).
 * Task 2.2 shared trigs: the live 976B pattern is NEVER written by the
 * flip, so no pattern stash arrays exist — only the 326B synth sound
 * (served from .bss by the F3 fetch interpose) and the 164B MIDI params
 * (restored byte-identical to the live kit on flip-back). */
static uint8_t cnv_synth_snd[NUM_CONV_TRACKS][SOUND_REC_SIZE];
static uint8_t cnv_synth_mute[NUM_CONV_TRACKS];
static uint8_t cnv_midi_prm[NUM_CONV_TRACKS][MIDI_REC_SIZE];
static uint8_t cnv_midi_mute[NUM_CONV_TRACKS];
static uint32_t cnv_state[NUM_CONV_TRACKS];

/* Task 3.1 player feedback: centered HUD toast on flip + converted-slot LEDs.
 * Popup kind: 0 = "TRACK N CONVERTED / SYNTH LIVE", 1 = "TRACK N RESTORED /
 * MIDI LIVE". Timer follows the bank-HUD discipline (set 36, ticked down in
 * cnv_tick which also nudges the redraw flag). */
static int32_t cnv_popup_ticks;
static int32_t cnv_popup_track;
static int32_t cnv_popup_kind;

/* Projdata persistence for stash validity (trk_save precedent, new tag). */
struct cnv_save_data {
    uint32_t magic;                     /* 'CNV8' = 0x434E5638 */
    uint32_t state[NUM_CONV_TRACKS];
    uint8_t  synth_mute[NUM_CONV_TRACKS];
    uint8_t  midi_mute[NUM_CONV_TRACKS];
    uint32_t reserved[4];
};
static struct cnv_save_data cnv_save;

static void cnv_proj_loaded(int32_t found)
{
    int32_t i;
    if (found && cnv_save.magic == 0x434E5638u) {
        cnv_brow_last = -1;
        for (i = 0; i < NUM_CONV_TRACKS; i++) {
            uint32_t s = cnv_save.state[i];
            cnv_state[i] = (s <= CNV_STASHED) ? s : CNV_NATIVE;
            cnv_synth_mute[i] = cnv_save.synth_mute[i] & 1;
            cnv_midi_mute[i] = cnv_save.midi_mute[i] & 1;
        }
    } else {
        cnv_save.magic = 0x434E5638u;
        cnv_brow_last = -1;
        for (i = 0; i < NUM_CONV_TRACKS; i++) {
            cnv_state[i] = CNV_NATIVE;
            cnv_save.state[i] = CNV_NATIVE;
            cnv_synth_mute[i] = 0;
            cnv_midi_mute[i] = 0;
            cnv_save.synth_mute[i] = 0;
            cnv_save.midi_mute[i] = 0;
        }
        fw_memset(cnv_save.reserved, 0, sizeof(cnv_save.reserved));
    }
}

const struct core_projdata cnv_projdata = {
    0x434E5638u, /* "CNV8" */
    sizeof(struct cnv_save_data),
    &cnv_save,
    cnv_proj_loaded
};

/* 1 when the slot's synth side is the live one, else 0. Slot -1 on bad index. */
int32_t cnv_is_converted(int32_t slot)
{
    if (slot < 0 || slot >= NUM_CONV_TRACKS)
        return -1;
    return (cnv_state[slot] == CNV_SYNTH) ? 1 : 0;
}

/* Converted-track predicate for the B4 open-gate skip (cnv_browse.s):
 * 1 iff the track is a converted synth slot (4..7 and converted).
 * Narrower than cnv_route_synth (which also returns 1 for native synth
 * tracks 0..3): B4 must skip ONLY converted opens, never native ones. */
int32_t cnv_is_converted_track(int32_t track)
{
    if (track < CONV_FIRST_TRACK ||
        track >= CONV_FIRST_TRACK + NUM_CONV_TRACKS)
        return 0;
    return (cnv_is_converted(track - CONV_FIRST_TRACK) == 1) ? 1 : 0;
}

/* MAIN value-resolver mirror (A1 site 0x4001d860, cnv_page.s). The
 * shared track->struct resolver indexes synth (20B) vs MIDI (8B)
 * sections by track: converted slots take the mirror slot's synth
 * entry (the only sane synth-side index — the synth section holds
 * 4 entries), every other track rejoins unchanged (natives replay
 * stock bit-exactly, native-MIDI keep the MIDI section). */
int32_t cnv_mirror_track(int32_t track)
{
    if (track >= CONV_FIRST_TRACK &&
        track < CONV_FIRST_TRACK + NUM_CONV_TRACKS &&
        cnv_is_converted(track - CONV_FIRST_TRACK) == 1)
        return track - CONV_FIRST_TRACK;
    return track;
}

/* Task 1.1 dispatch predicate for the S1/S2 trampolines in cnv_route.s:
 * converted(t) ? synth : (t > 3 ? midi : synth). Stock tracks 0-3 always
 * take the synth fork; out-of-range tracks keep the stock fork (t <= 3
 * synth, else MIDI). Called with d2 = track; d2-d7/a2-a6 survive the
 * call per the m68k ABI, and the trampoline saves d0-d1/a0-a1. */
int32_t cnv_route_synth(int32_t track)
{
    if (track >= CONV_FIRST_TRACK && track < CONV_FIRST_TRACK + NUM_CONV_TRACKS)
        return (cnv_is_converted(track - CONV_FIRST_TRACK) == 1) ? 1 : 0;
    return (track <= 3) ? 1 : 0;
}

/* Task 1.2 synth-fire fetch: the F3 site (synth-fire 0x4009451e epilogue
 * 0x40094832, trampoline cnv_site_f3 in cnv_fetch.s) asks, per firing
 * track, which 326B sound record the voice must load. Converted tracks
 * get the mod-.bss record; everything else returns 0 and the trampoline
 * replays the stock kit fetch bit-exactly.
 *
 * Voice-cache warm (tracks-dn1 invalidate_voice_cache precedent): a voice
 * keeps the sound it loaded last (cached per-voice pointer at
 * ADDR_VOICE_SOUNDS, core-dn1 params.s) and reloads only for another
 * sound, so publishing a fresh .bss address is enough on first play —
 * but a re-convert reuses the same stable .bss address with new content,
 * which a pointer comparison would miss. Zeroing the cached entries of
 * the voices currently on the firing track (ADDR_VOICE_TRACK map) forces
 * CPU #1 to reload the .bss record into the DSP. If the map names no
 * voice for the track (stale allocation), fall back to all 8 — the
 * tracks-dn1 swap-time behaviour — rather than risk a stale timbre.
 * Flip-time cnv_to_synth/cnv_to_midi invalidate all 8 as well: the flip
 * is the moment content changes under stable addresses, and a UI gesture
 * is the click-cheap moment (same reasoning as trk_swap_banks).
 *
 * Task 1.3 per-track voice-flag stage (8track-engine): the voice engine's
 * note-on path (loop A at 0x4009e852) admits a voice attempt only when
 * d0 == (d0 & 127) where d0 = event_byte + *(0x80003fc4) + Y(track), with
 * Y(t) = *(u32 *)(ADDR_TRACK_FLAG + 4*t), ADDR_TRACK_FLAG = 0x80003fc8
 * (== 0x800034c4 + (705+0)*4; the voice-state helper H705 at 0x4009c8f8
 * writes *(0x800034c4 + (705+idx)*4), scale x4 verified against the
 * voice->track map at 0x80003f8c == 0x800034c4 + (690+0)*4).
 * Stock stages Y(idx) = (int32)track_struct[972] for idx 0..3 only, in
 * the `for (d2 = 0; d2 < 4; d2++)` loop at 0x40094fda (per synth-fire
 * traversal, whole 976B track structs, idx+value into H705) — emuproven:
 * native notes see Y=0 (d0 = 0x3c, pass), converted track-4 notes see a
 * stuck Y(4) = 0x20000 (d0 = 0x2003c, skip) because the loop never
 * stages idx 4..7, so the allocator (0x4009f008), the voice-start store
 * (0x4009e9a2) and the gate OR (0x4009ea6a) never run for track 4.
 * S9 0x400e31a2 never fires on the note path (0 hits across all probe
 * runs): verify-only, NOT widened. Likewise the 0x400ea168 0-7 clamp
 * and mute logic are index-agnostic: untouched.
 * The mod restores the stock invariant for converted tracks only —
 * staging the same (int32)(int8)live_trk[972] value stock would stage —
 * in cnv_fetch_fire (same phase as stock's own staging: inside the
 * synth-fire traversal, before the voice engine evaluates) and at flip
 * time; flip-back zeroes the slot (boot state; the MIDI path manages
 * Y itself while MIDI-live). Native tracks 0-3 and MIDI tracks never
 * take this path: no stock behaviour changes.
 *
 * Task 1.3 voice-candidate rows (same lane): valloc (0x4009f008) reads
 * a candidate byte at ADDR_VOICE_CAND + 260*track + vel (260B rows per
 * track; the byte is consumed — zeroed — by the call). Sustain-trace
 * 2026-10-28 correction: the staged 0x01 does NOT buy single-voice.
 * Live hooks prove valloc returns 0xff (8 voices, all gated+registered)
 * for converted notes whether the entry byte reads 0x01 (staged) or is
 * forced to 0x00 at the call doorstep, while native notes (entry byte
 * 0x00) return 0x01. The 8-vs-1 divergence is decided by deeper
 * second-half state, not the CAND byte; with a real (nonzero) sound
 * record the committed voices gate, register the .bss pointer via
 * c286, render and sustain (t4-solo render energy in the millions vs
 * absolute 0 with a zeroed record). Staging row[track][*] = 0x01 is
 * retained as a harmless keep-armed measure, but it is NOT the sustain
 * lever — the init timbre is. */
#define ADDR_VOICE_SOUNDS     0x80003f5c
#define ADDR_VOICE_TRACK      0x80003f8c
/* Task 1.3: per-track voice flag Y(t) = *(u32 *)(base + 4t). Stock's
 * H705 clear-loop covers t = 0..3 only; converted tracks are staged here
 * (see the cnv_fetch_fire comment). Source byte mirrors the stock loop's
 * mvsb track_struct[972] over 976B structs. Candidate rows: valloc reads
 * ADDR_VOICE_CAND + 260*track + vel; stock stages rows 0..3 only. */
#define ADDR_TRACK_FLAG       0x80003fc8
#define ADDR_VOICE_CAND       0x800054d4
#define VOICE_CAND_ROW        260
#define TRACK_STRUCT_SIZE     976
#define TRACK_FLAG_SRC_OFF    972

static void cnv_invalidate_voice_cache(uint32_t mask)
{
    volatile uint32_t *cached_sounds = (volatile uint32_t *)ADDR_VOICE_SOUNDS;
    int32_t v;
    for (v = 0; v < 8; v++) {
        if (mask & (1u << (uint32_t)v))
            cached_sounds[v] = 0;
    }
}

uint8_t *cnv_fetch_fire(int32_t track)
{
    volatile uint32_t *voice_track = (volatile uint32_t *)ADDR_VOICE_TRACK;
    volatile uint32_t *cached_sounds = (volatile uint32_t *)ADDR_VOICE_SOUNDS;
    int32_t v;
    uint32_t warmed = 0;

    if (track < CONV_FIRST_TRACK || track >= CONV_FIRST_TRACK + NUM_CONV_TRACKS)
        return 0;
    if (cnv_is_converted(track - CONV_FIRST_TRACK) != 1)
        return 0;

    for (v = 0; v < 8; v++) {
        if (voice_track[v] == (uint32_t)track) {
            cached_sounds[v] = 0;
            warmed |= (1u << (uint32_t)v);
        }
    }
    if (!warmed)
        cnv_invalidate_voice_cache(0xFFu);
    /* Task 1.3: restore the stock per-track flag invariant. Stock's
     * H705-loop stages Y(0..3) = (int32)(int8)track_struct[972] on every
     * synth-fire traversal but never idx 4..7, so a stale Y(track)
     * (observed 0x20000) fails the voice engine's d0 == d0&127 admission
     * check and no voice ever starts. Stage the same value stock would:
     * the live (synth-side) pattern struct's byte 972. */
    if (fw_pattern) {
        uint8_t *live_trk = fw_pattern + (uint32_t)track * TRACK_STRUCT_SIZE;
        int8_t b = (int8_t)live_trk[TRACK_FLAG_SRC_OFF];
        *(volatile int32_t *)(ADDR_TRACK_FLAG + (uint32_t)track * 4) =
            (int32_t)b;
        /* Task 1.3: stage the voice-candidate row the same way. Stock
         * stages rows 0..3 only; an unstaged row reads 0xFF and the
         * caller commits 8 voices that never sustain. 0x01 admits a
         * single voice 0, mirroring native track-0 behaviour. The whole
         * row is staged (velocity-agnostic): valloc consumes one byte
         * per note. */
        fw_memset((uint8_t *)(ADDR_VOICE_CAND + (uint32_t)track *
                              VOICE_CAND_ROW),
                  1, VOICE_CAND_ROW);
    }
    return &cnv_synth_snd[track - CONV_FIRST_TRACK][0];
}

/* Task 3.1 sound-browser parity: mod-owned 808B browser rows.
 *
 * The synth browser session runs on 808B rows of a heap table
 * (base 0x41a722f0, observed stable across boots; rows at base+96+808t).
 * Rows 0-3 are the synth tracks' sessions (all share the static session
 * object 0x40196104); rows 4-7 are the MIDI tracks' sessions (different
 * objects). A converted track routed into the browser with its own index
 * 4..7 would land on a MIDI row (wrong session object, MIDI side effects
 * in the apply bookkeeping) or be clamped to row 3 (cross-talk with a
 * native track's session). So converted tracks get their own rows here
 * in mod .bss, filled per use from the mirror native row (track-4).
 *
 * The preset-apply write (function B at 0x4001d710) takes its destination
 * from the row: dst = *(row+16) via the session-object virtual at +40
 * (0x401535c4, a pure field read). Wiring our row's +16 to the slot's
 * .bss sound record redirects the stock 326B MEMCPY into .bss with no
 * kit write; the next synth-fire (F3 fetch) warms the voice cache and
 * serves it. The row copy is refreshed on every use (open + apply), so a
 * clobbered +16 (the session object has a +16 setter used mid-session)
 * is always rewired before the apply reads it. Native tracks never take
 * the mod-row path: every helper returns 0/stock for them. */
#define BROW_ROW_SIZE       808
#define BROW_ROW_OFF        96
#define BROW_ROW_PTR_OFF    16
static uint8_t cnv_brow_row[NUM_CONV_TRACKS][BROW_ROW_SIZE];
/* Last browser row served by B2 (mod row slot), or -1. The YES/apply path
 * (function B at 0x4001d710) passes the BROWSER track (session-derived:
 * 0 for our mod rows, whose session object is the shared static synth
 * session) — not the tapped track — so B3 keys its divert off this
 * stash instead of d2. B2's site fires only on browser open (row fetch),
 * never on DOWN-navigation or the idle row refreshes (different call
 * sites), so the stash always describes the currently open browser.
 * -1 (no converted browser open) is the boot state, restored in
 * cnv_proj_loaded and on every native serve. */
static int32_t cnv_brow_last = -1;

/* Stock MIDI-bank predicate (T-key dispatch 0x4004ef1a site): nonzero =
 * MIDI bank. Called through a pointer like the mute setters. */
static int (*const cnv_bankcheck)(void *) = (int (*)(void *))0x4002e1ae;

/* Task 3.2 voice-menu bank divert (V8 site 0x4003f642, B0/B5
 * discipline). The plain-VOICE path runs the 0x4003f62e block for
 * every track: ded04(view) then this bank check on the a8(a2) cell,
 * whose nonzero low byte sends MIDI-bank tracks to 0x400403bc while
 * the zero low byte of the synth verdict falls through to the synth
 * menu chain (0x400407e2 ded70 block -> 58770 builder). Emu-proven
 * (routeC legs): the site fires with the constant key-cell
 * 0x40553e00 and ACTIVE == tapped track on plain VOICE for 0-7;
 * ded04 already passes for converted slots, so the bank verdict
 * alone excludes them. The helper returns 0 (synth path: the rejoin
 * tst.b sets Z, bne skips MIDI; d0 is dead past the fork — ded70's
 * own jsr result overwrites it) for converted tracks, else re-runs
 * the stock check through the same cell (bit-exact native replay).
 * Only ACTIVE 4-7 + converted divert; every other state replays
 * stock, so other callers of the block are unaffected. */
int32_t cnv_voice_bank(void *cell)
{
    int32_t track = fw_active_track;
    int32_t r = cnv_bankcheck(cell);
    if (track >= CONV_FIRST_TRACK &&
        track < CONV_FIRST_TRACK + NUM_CONV_TRACKS &&
        cnv_is_converted(track - CONV_FIRST_TRACK) == 1)
        return 0;
    return r;
}

/* Task 3.3 keyboard transpose-row divert (L3 site 0x400c28c2,
 * cnv_label.s). The keyboard view (entry 0x400c23b2) sets a5 once from
 * the 0x4002c6ea view-track reader and uses it as the row/track index;
 * emu-proven a5 == ACTIVE on the keyboard page (native 0/2 synth fork,
 * converted 4 / native-MIDI 5 MIDI fork). Returns 1 iff the track is a
 * converted synth slot (4..7 + converted) — the detour then draws the
 * synth-shape row with the custom "b%d" format from mod .rodata;
 * native tracks return 0 and the detour replays the stock fork
 * bit-exactly ("T%d"+track+1 for 0..3, "M%d"+track-3 for 4..7).
 * Only converted 4-7 divert; every other caller state replays stock,
 * so other users of the view are unaffected. */
int32_t cnv_label_transp(int32_t track)
{
    return cnv_is_converted_track(track);
}

/* B0 divert predicate (T-key dispatch bank-check site 0x4004ef1a).
 * keycode = T-key panel code (42..45 = T1..T4). Returns the converted
 * track (4..7) when this press addresses a converted slot on the MIDI
 * bank, else the stock bank value (0 = synth, nonzero = MIDI) for the
 * stock rejoin. The asm detour diverts on 4..7 (setting d4 = track and
 * d0 = 0 for the synth path) and rejoins stock otherwise. keycode-38 is
 * the MIDI-bank track (obs: ef26 addil #-38; ed74 d3 = 4..7); slot =
 * keycode-42. The synth bank can never address a converted slot
 * (keycode-42 there is track 0..3, always native). */
int32_t cnv_brow_open(void *cell, int32_t keycode)
{
    int32_t slot, bank;
    if (keycode < 42 || keycode > 45)
        return 0;
    slot = keycode - 42;
    bank = cnv_bankcheck(cell);
    if (!bank)
        return bank;
    if (cnv_is_converted(slot) != 1)
        return bank;
    return (int32_t)(slot + CONV_FIRST_TRACK);
}

/* Task 3.1 B6 vector-4 root cause (found 0.17 YES-probing, fixed here):
 * the mod row's +0 session object is copied from the mirror row, and a
 * DOWN-navigation B2 fetch can source the mirror from the MIDI-bank row
 * table (session 0x4019a388, whose +0x28 virtual is 0x72506167 — data
 * misread as code, the exact deterministic vector-4 fault PC). The
 * post-copy bookkeeping (0x40030f70) calls that virtual, so a converted
 * YES jumped to 0x72506167 every time (emu skips the faulting insn, so
 * the apply still landed, but no LOADED toast painted). Native rows
 * carry the static synth session 0x40196104 (whose +0x28 virtual
 * 0x401535c4 is a pure field read). Converted slots are synth-side, so
 * the divert wires +0 to the synth session on the apply path (wire=1).
 * The open path (wire=0) keeps the copied +0: draw/navigation are
 * proven working with it (bit-identical browser PNGs), minimal blast
 * radius. The +16 SND wiring (B3) is untouched. */
#define BROW_ROW_SESS_OFF   0
#define SYNTH_SESSION_OBJ   ((uint8_t *)0x40196104)

/* B2/B3 row provider (browser-open call site 0x4004edb2, apply row site
 * 0x4001d73e). table = stock row-table base (dcf2 arg / function-B a3),
 * track = stock track index. Returns the mod row for converted tracks
 * (fresh copy of the mirror native row + dst wired to .bss + voice-cache
 * invalidate, same click-cheap discipline as the flip), else 0 for the
 * stock path. */
uint8_t *cnv_brow_row_for(uint8_t *table, int32_t track, int32_t wire)
{
    int32_t slot;
    if (track >= CONV_FIRST_TRACK &&
        track < CONV_FIRST_TRACK + NUM_CONV_TRACKS &&
        cnv_is_converted(track - CONV_FIRST_TRACK) == 1) {
        slot = track - CONV_FIRST_TRACK;
    } else if (wire && cnv_brow_last >= 0 &&
               cnv_brow_last < NUM_CONV_TRACKS &&
               cnv_is_converted(cnv_brow_last) == 1) {
        /* Apply path (wire=1) for a converted open: function B passes the
         * browser track (session-derived, 0 for our mod rows), not the
         * tapped track. Divert off the B2 stash (the actually open row).
         * Never on the open path (wire=0): there d2 is authoritative. */
        slot = cnv_brow_last;
    } else {
        if (!wire)
            cnv_brow_last = -1;
        return 0;
    }
    cnv_brow_last = slot;
    fw_memcpy(cnv_brow_row[slot],
              table + BROW_ROW_OFF + (uint32_t)(slot) *
              BROW_ROW_SIZE,
              BROW_ROW_SIZE);
    if (!wire)
        return &cnv_brow_row[slot][0];
    /* Apply path: the caller passes the browser track (session-derived,
     * 0 for mod rows), so the mirror index must be the stash slot, not
     * the track (track-4 underflows to an out-of-bounds read). The slot
     * mirror keeps every field bank-consistent; +0/+16 are wired below
     * regardless (B7 vector-4: +0 could still carry a MIDI session when
     * the table itself is the MIDI-bank one). */
    *(uint32_t *)(cnv_brow_row[slot] + BROW_ROW_SESS_OFF) =
        (uint32_t)SYNTH_SESSION_OBJ;
    *(uint32_t *)(cnv_brow_row[slot] + BROW_ROW_PTR_OFF) =
        (uint32_t)&cnv_synth_snd[slot][0];
    cnv_invalidate_voice_cache(0xFFu);
    return &cnv_brow_row[slot][0];
}

/* B5 browser-refresh gate (call site 0x400400ec, 0.16).
 * Stock 0x40025b76 maps track -> 1 (0..3), 2 (8), else 0; the caller
 * continues to the 0x400e54a2 page-commit chain (view+0x17, ctx
 * +0x160/+0x164/+0x18c writers — the refresh that DRAWS the browser)
 * only on 1 (0x400400f4 moveq #1,d1 + cmp + bne.w 0x40040d32).
 * Emu-proven (gate3/track2 legs, 0.15): at the call A4 = tapped track
 * (0 native T1, 1 native T2, 4 converted slot 0) and 25b76 returns
 * 1 / 1 / 0 — so a converted slot always bails and the commit chain
 * never runs. Converted slots take the 1 path; native tracks replicate
 * the pure stock mapping bit-exactly (no memory touched, all inputs). */
int32_t cnv_brow_gate(int32_t track)
{
    if (track >= CONV_FIRST_TRACK &&
        track < CONV_FIRST_TRACK + NUM_CONV_TRACKS &&
        cnv_is_converted(track - CONV_FIRST_TRACK) == 1)
        return 1;
    {
        uint32_t u = (uint32_t)track;
        if (u <= 3)
            return 1;
        if (u == 8)
            return 2;
        return 0;
    }
}

/* Task 3.1 B6 preset-apply N/A gate reader (call site 0x400cdb8e, 0.17).
 * Stock feeds this c6ba view-track result into 0x40025b76 twice
 * (0x400cdb9a/0x400cdba0 via d4); 25b76 maps 0..3 -> 1 (LOADED path,
 * function B) and everything else -> 0/2 ("N/A ON THIS TRACK" toast).
 * Emu-proven (c6ba leg): the reader returns 0 on a native YES but the
 * converted track (4) on a converted YES — the compared value IS the
 * converted track again. The helper re-runs the stock reader by
 * pointer (B0 discipline; c6ba already invokes its virtual twice per
 * call and YES-apply is click-cheap) and maps a converted track to its
 * mirror slot, so 25b76 sees 0..3 and the LOADED path (function B +
 * B3 stash divert) runs. Native tracks return the stock value
 * bit-exactly. Only this call site is interposed: every other c6ba
 * caller (notably B4's already-computed d0) keeps stock behavior. */
static int (*const cnv_viewtrack)(void *) = (int (*)(void *))0x4002c6ba;

int32_t cnv_brow_gate_apply(void *session)
{
    int32_t track = cnv_viewtrack(session);
    if (track >= CONV_FIRST_TRACK &&
        track < CONV_FIRST_TRACK + NUM_CONV_TRACKS &&
        cnv_is_converted(track - CONV_FIRST_TRACK) == 1)
        return track - CONV_FIRST_TRACK;
    return track;
}

/* Task 3.4 synth param pages (P1 type divert + P2 row divert,
 * cnv_page.s). The live page dispatch is the page function at
 * 0x4004221c (NOT the spike's S8 0x40160968 / S5 0x4003ca70, both
 * proven silent on every page gesture across banks and left stock —
 * see tests/probe/cnv_pages.py): the function calls the c6ba
 * view-track reader (P1 site 0x40042240), keeps d4 = result (proven ==
 * ACTIVE track on page opens for native 0-3, converted 4-7 and
 * native-MIDI 5-7), compares vs 3 (P_CMP 0x40042258) and runs the
 * synth page chain (P_GATE 0x40042530 -> c1dcf2 row fetch at
 * 0x4004253c -> c31972 session virtuals). The row fetch resolves the
 * page's sound through row+16 (proven == kit+0x18+326t on natives, the
 * same +16 mechanism as the browser rows), so converted tracks take
 * the stock synth chain with a mod-owned page row whose +16 points at
 * the slot's .bss sound: draws read .bss, knob edits write .bss.
 * Mutes + sequencer are index-agnostic (track*976 pattern, 0-7 clamps)
 * and verified by capture only — never patched. */
static uint8_t cnv_page_row[NUM_CONV_TRACKS][BROW_ROW_SIZE];

/* P1 type divert (call site 0x40042240, B6 discipline). The helper
 * re-runs the stock c6ba reader through the same cell and maps a
 * converted track to its mirror slot, so the page function takes the
 * stock synth chain; native tracks rejoin bit-exactly. Only this call
 * site is interposed: every other c6ba caller keeps stock behavior. */
int32_t cnv_page_track(void *session)
{
    int32_t track = cnv_viewtrack(session);
    if (track >= CONV_FIRST_TRACK &&
        track < CONV_FIRST_TRACK + NUM_CONV_TRACKS &&
        cnv_is_converted(track - CONV_FIRST_TRACK) == 1)
        return track - CONV_FIRST_TRACK;
    return track;
}

/* P2 row provider (row-fetch call site 0x4004253c, B2 discipline).
 * table = stock page-row table (0x41a722f0, same 808B rows at +96 as
 * the browser table), track = the c1dcf2 track arg (already
 * mirror-mapped by P1, so 0..3 on the converted path). The converted
 * slot is keyed off fw_active_track (V8 precedent; proven ACTIVE ==
 * track on every page open): slot = ACTIVE-4 with the guard
 * track == slot, so incoherent states (and all native pages) replay
 * stock bit-exactly. The divert serves a fresh copy of the mirror row
 * in mod .bss with +16 wired to the slot's .bss sound (the +0 session
 * object is kept copied: the page table already carries synth
 * sessions, the browser open-path precedent). Native tracks return 0
 * for the stock c1dcf2 path. */
uint8_t *cnv_page_row_for(uint8_t *table, int32_t track)
{
    int32_t active = fw_active_track;
    int32_t slot;
    if (active < CONV_FIRST_TRACK ||
        active >= CONV_FIRST_TRACK + NUM_CONV_TRACKS)
        return 0;
    slot = active - CONV_FIRST_TRACK;
    if (cnv_is_converted(slot) != 1)
        return 0;
    if (track != slot)
        return 0;
    fw_memcpy(cnv_page_row[slot],
              table + BROW_ROW_OFF + (uint32_t)track *
              BROW_ROW_SIZE,
              BROW_ROW_SIZE);
    *(uint32_t *)(cnv_page_row[slot] + BROW_ROW_PTR_OFF) =
        (uint32_t)&cnv_synth_snd[slot][0];
    return &cnv_page_row[slot][0];
}

/* P3 view-9 gate (branch site 0x40042da8, B1/S1 discipline). The v84
 * page function (0x40042d84) runs its first virtual (a0+$a0)(8, a2)
 * and takes the synth-view path (fallthrough to the (a0+$58) virtual
 * -> ret 0x40042dbe -> viewfn view 9 -> c6ba -> P1 mirror ->
 * 0x4002f91a builder) unless d0 == 0 (beq.w -> 0x40042e5e skip);
 * emu-proven (v84gate leg) d0 = 9 on native synth pages but 0 on
 * converted and native-MIDI pages (taken 14/0/0, skip 14/14/15). The
 * helper forces the fallthrough (returns 1) only when the stock
 * verdict is 0 for the MIDI-page renderer caller (0x40042f8a, the
 * single proven converted-page caller, read from the v84 return
 * slot) while a converted slot is active; every other caller,
 * every nonzero verdict and every native state replays the stock
 * move + branch bit-exactly. The forced d0 = 9 reproduces the
 * native view-9 register flow exactly (viewfn d2 = 9 -> P1 mirror
 * -> P2 mod row). */
int32_t cnv_view9_path(uint32_t caller, int32_t verdict)
{
    int32_t track;
    if (caller != 0x40042f8au)
        return 0;
    if (verdict != 0)
        return 0;
    track = fw_active_track;
    if (track < CONV_FIRST_TRACK ||
        track >= CONV_FIRST_TRACK + NUM_CONV_TRACKS)
        return 0;
    return (cnv_is_converted(track - CONV_FIRST_TRACK) == 1) ? 1 : 0;
}

/* P4 content-fork divert (call site 0x4003f184, B1/S1 discipline).
 * The entry-filler's caller (0x4003f1e6) selects the views source
 * table section: `moveq #3,d0; cmp.l d3,d0; bcs MIDI-table` —
 * emu-proven (c3proof leg) d3 == ACTIVE track on page-key opens for
 * native 0-3 (synth table a2+0xf0), converted 4-7 and native-MIDI
 * 5-7 (MIDI table a2+0x148); d2 is the page index (1 SYN1, 3 FLTR).
 * The helper forces the synth section for converted tracks and
 * replays the stock fork otherwise. d3 is NOT rewritten (it is only
 * read by the fork; downstream state stays indexed by the real
 * track/ACTIVE). Synth fallthrough rejoins 0x4003f18a via rts; the
 * MIDI exit pops the site return and jmps (S1/S2 jmp discipline). */
int32_t cnv_c3_route(int32_t track)
{
    if (track >= CONV_FIRST_TRACK &&
        track < CONV_FIRST_TRACK + NUM_CONV_TRACKS)
        return (cnv_is_converted(track - CONV_FIRST_TRACK) == 1) ? 1 : 0;
    return (track <= 3) ? 1 : 0;
}

/* P5a/P5b param-edit sound divert (call sites 0x4002102a + 0x400215d0,
 * B2/P2 whole-virtual-jsr discipline). Knob edits resolve the sound
 * record through the row session's +$28 virtual (pure *(row+16)
 * read: 0x401535c4 on synth rows, 0x4014e9aa on MIDI rows) — the
 * native synth path lands on the kit sound, but converted slots land
 * on kit MIDI/gap bytes (the row is view-bound, not P2-diverted) so
 * edits never reach the .bss record (timbre follows only the live
 * voice). The helper returns the slot's .bss sound for converted
 * slots (ACTIVE-guarded, V8 discipline; the caller applies its own
 * param offset onto the base, so draws via P2 and edits stay
 * consistent) and 0 for everything else, in which case the stock
 * virtual replays bit-exactly via jmp (a0) — its rts consumes the
 * site return and rejoins site+6 (the pushed row arg is dropped by
 * the rejoin's addq, like P2/B2). Both edit functions are covered
 * (synth-editor site + MIDI-editor site) so every param on every
 * page diverts; native tracks replay stock on both. d1/a0-a1 saved
 * (C scratch); d0 carries the result; d2-d7/a2-a6 survive. */
uint8_t *cnv_edit_snd_for(void)
{
    int32_t track = fw_active_track;
    if (track < CONV_FIRST_TRACK ||
        track >= CONV_FIRST_TRACK + NUM_CONV_TRACKS)
        return 0;
    if (cnv_is_converted(track - CONV_FIRST_TRACK) != 1)
        return 0;
    return &cnv_synth_snd[track - CONV_FIRST_TRACK][0];
}

/* Key codes (tracks-dn1 precedent for 1/2/8; YES/NO from the sibling
 * tree: pedal_ui.inc + fxkit.c both define KEY_YES 13 / KEY_NO 14,
 * matching the Digitone panel order RECORD/STOP/YES/NO = 10/12/13/14 —
 * verified behaviorally in tests/probe/cnv_modal.md, §2 key sweep). */
#define KEY_FUNC            1
#define KEY_MIDI            2
#define KEY_VOICE           8
#define KEY_YES             13
#define KEY_NO              14

/* Task 2.1 modal state: -1 = IDLE (no card), else the pending slot with
 * an open YES/NO card. cnv_modal_ticks counts down in cnv_tick; expiry
 * cancels with zero state change. Evicted-slot rule: at most one modal;
 * a re-chord while open refreshes the timer on the original slot. */
#define CNV_MODAL_TICKS     60  /* ~2s at the ~30Hz ev_tick cadence */
static int32_t cnv_modal_slot = -1;
static int32_t cnv_modal_ticks;

/* MIDI-held tracking across ev_key calls (trk_keys_down discipline). */
static uint32_t cnv_keys_down[2];

/* The MIDI key toggles MIDI-track addressing as a side effect: pressing it
 * can retarget fw_active_track to a synth track before the chord's VOICE
 * press arrives (observed in emu: active 4 at the converting VOICE press,
 * active 0 at the next chord's VOICE press). Stash the active track on the
 * MIDI press edge so the chord still reaches the intended slot. */
static int32_t cnv_midi_track = -1;

/* Task 2.1 gesture: MIDI+VOICE chord. Tracks MIDI-held state; on VOICE
 * press while MIDI is held with the active convertible slot (slot =
 * active-4) and no modal open, OPENS the YES/NO modal and swallows the
 * event (return 1 — stock never sees it). YES (down) while open runs the
 * masked flip for the modal slot and swallows; NO (down) while open
 * cancels with zero state change and swallows. A re-chord while open
 * refreshes the timer (same slot) and swallows. Plain VOICE while open
 * is swallowed to protect the card; after cancel/timeout the state is
 * IDLE again so plain VOICE falls through (return 0) and the stock voice
 * menu opens. Plain VOICE without MIDI held always falls through.
 * Chord with an active track on 0-3 falls through (stock proceeds). */
int32_t cnv_key(void *brain, void *ev)
{
    int32_t id = *(int32_t *)((char *)ev + 12);
    uint32_t flags = *(uint32_t *)((char *)ev + 16);
    int32_t down = (flags & 1) != 0;
    int32_t midi_held;
    (void)brain;

    /* Track all keys down, one bit per id across the two words
     * (core-dn1 menu.s note_key discipline: word id>>5, bit id&31). */
    if (id >= 0 && id < 64) {
        if (down)
            cnv_keys_down[(uint32_t)id >> 5] |= (1u << ((uint32_t)id & 31));
        else
            cnv_keys_down[(uint32_t)id >> 5] &= ~(1u << ((uint32_t)id & 31));
    }

    if (id == KEY_MIDI) {
        /* Stash before any stock retarget: the chord acts on the track
         * that was active when MIDI went down (see header comment). */
        if (down)
            cnv_midi_track = fw_active_track;
        return 0;
    }

    if (!down)
        return 0; /* releases always fall through (orphan-safe: stock
                   * pairs press/release, and modal close on press
                   * already consumed the gesture) */

    if (cnv_modal_slot >= 0) {
        /* Modal open: YES flips, NO cancels, VOICE/chord swallowed. */
        if (id == KEY_YES) {
            int32_t slot = cnv_modal_slot;
            cnv_modal_slot = -1;
            cnv_modal_ticks = 0;
            if (cnv_is_converted(slot))
                cnv_to_midi(slot);
            else
                cnv_to_synth(slot);
            return 1;
        }
        if (id == KEY_NO) {
            cnv_modal_slot = -1; /* zero state change */
            cnv_modal_ticks = 0;
            return 1;
        }
        if (id == KEY_VOICE) {
            /* Swallow (plain or chorded) to protect the card; a
             * MIDI-held re-chord refreshes the timer, plain VOICE
             * leaves it running (timeout still cancels). */
            midi_held = (cnv_keys_down[(uint32_t)KEY_MIDI >> 5] &
                         (1u << ((uint32_t)KEY_MIDI & 31))) != 0;
            if (midi_held)
                cnv_modal_ticks = CNV_MODAL_TICKS;
            return 1;
        }
        return 0; /* anything else falls through; modal stays until
                   * YES/NO/timeout */
    }

    if (id != KEY_VOICE)
        return 0;

    midi_held = (cnv_keys_down[(uint32_t)KEY_MIDI >> 5] &
                 (1u << ((uint32_t)KEY_MIDI & 31))) != 0;
    if (!midi_held)
        return 0; /* plain VOICE: stock opens the menu everywhere */

    {
        /* Fresh selection wins; the MIDI-press stash covers the toggle
         * retarget (fresh synth, stash MIDI). Both synth: fall through. */
        int32_t target = fw_active_track;
        if (target < CONV_FIRST_TRACK ||
            target >= CONV_FIRST_TRACK + NUM_CONV_TRACKS) {
            if (cnv_midi_track < CONV_FIRST_TRACK ||
                cnv_midi_track >= CONV_FIRST_TRACK + NUM_CONV_TRACKS)
                return 0; /* native synth: chord ignored, stock proceeds */
            target = cnv_midi_track;
        }
        cnv_modal_slot = target - CONV_FIRST_TRACK;
        cnv_modal_ticks = CNV_MODAL_TICKS;
        return 1; /* swallowed: stock never sees the chord */
    }
}

/* Mask interrupts exactly like trk_swap_banks: stash-write completes
 * before any live pointer/field write, and the flip is atomic. */
#define CNV_MASKED_BEGIN(sr) \
    __asm__ volatile ("move.w %%sr, %0; move.w #0x2700, %%sr" : "=d"(sr) : : "memory")
#define CNV_MASKED_END(sr) \
    __asm__ volatile ("move.w %0, %%sr" : : "d"(sr) : "memory")

static void cnv_sync_save(int32_t slot)
{
    cnv_save.state[slot] = cnv_state[slot];
    cnv_save.synth_mute[slot] = cnv_synth_mute[slot];
    cnv_save.midi_mute[slot] = cnv_midi_mute[slot];
}

/* MIDI -> synth. Task 2.2 shared trigs: the live 976B pattern struct is
 * NEVER written — it stays in place and keeps its trigs/pitch bytes on
 * both sides of the flip. First call stashes the live MIDI side (164B
 * kit params + mute) and builds the synth side (kit slot-0 timbre copy
 * into .bss, proven sounding; a zeroed record renders silence); later
 * calls reuse the .bss record already staged. Live kit MIDI params stay
 * in place (dispatch routes converted tracks synth-side via S1/S2), so
 * the MIDI channel byte (wherever the stock layout keeps it inside the
 * preserved 164B/976B regions) is untouched by construction — the flip
 * write-set below is exactly: stash copies to .bss, the pattern mute
 * byte, the audio-mute hw mask + setter call, and voice-cache/flag
 * staging. Returns 0 on success, -1 on a bad slot or missing structs. */
int32_t cnv_to_synth(int32_t slot)
{
    int32_t track;
    uint16_t sr;
    fn_set_mutes_t set_audio_mutes = (fn_set_mutes_t)ADDR_SET_AUDIO_MUTES;

    if (slot < 0 || slot >= NUM_CONV_TRACKS)
        return -1;
    if (!fw_kit || !fw_pattern)
        return -1;
    if (cnv_state[slot] == CNV_SYNTH)
        return 0;

    track = CONV_FIRST_TRACK + slot;

    if (cnv_state[slot] == CNV_NATIVE) {
        /* First conversion: fresh synth side = KNOWN-GOOD init timbre
         * (live kit slot-0 record, kit+0x18, 326B; read-only from kit).
         * Sustain-trace 2026-10-28: a zeroed record renders silence with
         * zero length, so the .bss record must carry a real patch. */
        fw_memcpy(cnv_synth_snd[slot], fw_kit + KIT_SYNTH_OFF,
                  SOUND_REC_SIZE);
        cnv_synth_mute[slot] = 0;
    }

    CNV_MASKED_BEGIN(sr);

    /* 1. Stash-write of the live MIDI side completes first. */
    fw_memcpy(cnv_midi_prm[slot], fw_kit + KIT_MIDI_OFF + (uint32_t)slot * MIDI_REC_SIZE,
              MIDI_REC_SIZE);
    cnv_midi_mute[slot] = (fw_pattern[PAT_MUTES_OFFSET + track] != 0) ? 1 : 0;

    /* 2. Live writes: mute byte only (indexed from the pattern base, one
     * byte per track, not from the per-track pointer). 0 = unmuted
     * (fresh-bank init convention); hardware mask bit set = unmuted.
     * The 976B pattern and 164B kit params stay in place: shared trigs.
     * Kit note (task 2.3 verdict): converted sound records stay in mod
     * .bss; nothing is written past kit+0x85E (live preset table — see
     * file header). Dispatch routes converted tracks synth-side
     * (cnv_route_synth + S1/S2 sites). */
    /* Mute byte is indexed from the pattern base (one byte per track),
     * not from the per-track pointer. 0 = unmuted (fresh-bank init
     * convention); hardware mask bit set = unmuted. */
    fw_pattern[PAT_MUTES_OFFSET + track] = cnv_synth_mute[slot];
    if (cnv_synth_mute[slot])
        *(volatile uint16_t *)ADDR_AUDIO_MUTES &= (uint16_t)~(1u << slot);
    else
        *(volatile uint16_t *)ADDR_AUDIO_MUTES |= (uint16_t)(1u << slot);
    set_audio_mutes(*(volatile uint16_t *)ADDR_AUDIO_MUTES);

    /* Task 1.2: content changed under the stable .bss fetch addresses —
     * drop the cached voice sound pointers so the next converted fire
     * reloads (see cnv_fetch_fire). */
    cnv_invalidate_voice_cache(0xFFu);

    /* Task 1.3: stage the per-track voice flag for the converted track
     * from the shared live pattern (same value the per-fire warm in
     * cnv_fetch_fire maintains; keeps the voice engine's admission
     * invariant across UI previews before the first sequencer fire),
     * plus the voice-candidate row (single voice 0, as in the warm).
     * Probed 2026-10-28: byte 972 reads 0 on all 8 factory tracks, so
     * the staged Y(track) is 0 — the native value. */
    {
        uint8_t *live_trk2 = fw_pattern + (uint32_t)track * TRACK_STRUCT_SIZE;
        int8_t b2 = (int8_t)live_trk2[TRACK_FLAG_SRC_OFF];
        *(volatile int32_t *)(ADDR_TRACK_FLAG + (uint32_t)track * 4) =
            (int32_t)b2;
        fw_memset((uint8_t *)(ADDR_VOICE_CAND + (uint32_t)track *
                              VOICE_CAND_ROW),
                  1, VOICE_CAND_ROW);
    }

    CNV_MASKED_END(sr);

    cnv_state[slot] = CNV_SYNTH;
    cnv_sync_save(slot);
    cnv_popup_track = track;
    cnv_popup_kind = 0;
    cnv_popup_ticks = CNV_POPUP_TICKS;
    return 0;
}

/* Synth -> MIDI (flip back). Task 2.2 shared trigs: the live 976B
 * pattern stays in place (same trigs before/after by construction); the
 * synth sound record already lives in .bss (nothing to stash back). The
 * flip restores the stashed 164B MIDI params byte-identical to the live
 * kit (a memcpy of provably identical bytes — the live region is never
 * written while synth-live) and the MIDI mute byte; mute semantics
 * unchanged (audio vs MIDI mute registers as today). The MIDI channel
 * byte is untouched: it lives inside the preserved 164B/976B regions and
 * the flip write-set excludes all param storage (mute byte + hw masks +
 * voice regs only).
 * Returns 0 on success, -1 on a bad slot or missing live structs. */
int32_t cnv_to_midi(int32_t slot)
{
    int32_t track;
    uint16_t sr;
    fn_set_mutes_t set_midi_mutes = (fn_set_mutes_t)ADDR_SET_MIDI_MUTES;

    if (slot < 0 || slot >= NUM_CONV_TRACKS)
        return -1;
    if (!fw_kit || !fw_pattern)
        return -1;
    if (cnv_state[slot] != CNV_SYNTH)
        return 0;

    track = CONV_FIRST_TRACK + slot;

    CNV_MASKED_BEGIN(sr);

    /* 1. Stash-write of the live synth mute completes first. The 976B
     * live pattern stays in place; the synth sound already lives in
     * mod .bss (never written to the live kit past kit+0x85E — live
     * preset table, see file header). */
    cnv_synth_mute[slot] = (fw_pattern[PAT_MUTES_OFFSET + track] != 0) ? 1 : 0;

    /* 2. Live writes: MIDI params restored byte-identical (the live
     * region is never written while synth-live, so this is a memcpy of
     * identical bytes — keeps the KIT_LIVE_LIMIT discipline explicit and
     * protects the channel byte by restoring the stashed record) plus
     * the mute byte (indexed from the pattern base, one byte per track;
     * 0 = unmuted; mask bit set = unmuted). The 976B pattern is untouched:
     * shared trigs keep the same notes. */
    fw_pattern[PAT_MUTES_OFFSET + track] = cnv_midi_mute[slot];
    fw_memcpy(fw_kit + KIT_MIDI_OFF + (uint32_t)slot * MIDI_REC_SIZE,
              cnv_midi_prm[slot], MIDI_REC_SIZE);
    if (cnv_midi_mute[slot])
        *(volatile uint16_t *)ADDR_MIDI_MUTES &= (uint16_t)~(1u << slot);
    else
        *(volatile uint16_t *)ADDR_MIDI_MUTES |= (uint16_t)(1u << slot);
    set_midi_mutes(*(volatile uint16_t *)ADDR_MIDI_MUTES);

    /* Task 1.2: same flip-time invalidate as cnv_to_synth — voices may
     * still cache the .bss address from the synth-live period. */
    cnv_invalidate_voice_cache(0xFFu);

    /* Task 1.3: release the per-track voice flag slot (boot state 0).
     * While MIDI-live the MIDI path manages Y itself (its param staging
     * reads Y(4..7) via tstl); leaving a synth-period 0x20000 behind
     * would suppress MIDI param staging for the slot. */
    *(volatile int32_t *)(ADDR_TRACK_FLAG + (uint32_t)track * 4) = 0;

    CNV_MASKED_END(sr);

    cnv_state[slot] = CNV_STASHED;
    cnv_sync_save(slot);
    cnv_popup_track = track;
    cnv_popup_kind = 1;
    cnv_popup_ticks = CNV_POPUP_TICKS;
    return 0;
}

/* Tick handler: modal-card timeout (~2s, bank-HUD discipline) plus the
 * popup-toast timer. Timeout cancels with zero state change. Either
 * timer running nudges the redraw flag. */
void cnv_tick(void *ctrl)
{
    if (cnv_modal_slot >= 0 && cnv_modal_ticks > 0) {
        if (--cnv_modal_ticks == 0)
            cnv_modal_slot = -1; /* timeout: cancel, zero state change */
        if (ctrl)
            ((volatile uint8_t *)ctrl)[0x20] = 1;
    }
    if (cnv_popup_ticks > 0) {
        cnv_popup_ticks--;
        if (ctrl)
            ((volatile uint8_t *)ctrl)[0x20] = 1;
    }
}

/* Draw handler: the YES/NO modal card while one is open, else the
 * centered HUD toast while the popup timer runs. Card geometry copies
 * the bank-HUD popup (96x28 at x16..112, y18..46). */
void cnv_draw(void *bmp, void *ctrl)
{
    int32_t num;
    (void)ctrl;
    if (!bmp)
        return;

    if (cnv_modal_slot >= 0) {
        fw_fillrect(bmp, 16, 18, 112, 46, 0);  /* clear card background */
        fw_fillrect(bmp, 16, 18, 112, 19, 1);  /* top border */
        fw_fillrect(bmp, 16, 45, 112, 46, 1);  /* bottom border */
        fw_fillrect(bmp, 16, 18, 17, 46, 1);   /* left border */
        fw_fillrect(bmp, 111, 18, 112, 46, 1); /* right border */
        if (cnv_is_converted(cnv_modal_slot))
            fw_textf(bmp, fw_font5, 28, 24, -1, "RESTORE MIDI?");
        else
            fw_textf(bmp, fw_font5, 22, 24, -1, "CONVERT TO SYNTH?");
        fw_textf(bmp, fw_font5, 22, 34, -1, "YES FLIP  NO KEEP");
        return;
    }

    if (cnv_popup_ticks <= 0)
        return;

    num = cnv_popup_track + 1;
    fw_fillrect(bmp, 16, 18, 112, 46, 0);  /* clear card background */
    fw_fillrect(bmp, 16, 18, 112, 19, 1);  /* top border */
    fw_fillrect(bmp, 16, 45, 112, 46, 1);  /* bottom border */
    fw_fillrect(bmp, 16, 18, 17, 46, 1);   /* left border */
    fw_fillrect(bmp, 111, 18, 112, 46, 1); /* right border */

    if (cnv_popup_kind == 0) {
        fw_textf(bmp, fw_font5, 22, 34, -1, "TRACK %d CONVERTED", num);
        fw_textf(bmp, fw_font5, 26, 24, -1, "SYNTH LIVE");
    } else {
        fw_textf(bmp, fw_font5, 22, 34, -1, "TRACK %d RESTORED", num);
        fw_textf(bmp, fw_font5, 26, 24, -1, "MIDI LIVE");
    }
}

/* LED handler: converted slots light their T-key bright green (palette 3,
 * first-setter-wins over the stock view); muted converted slots go dark. */
void cnv_key_leds(void *mgr)
{
    fn_set_led_t set_led = (fn_set_led_t)ADDR_SET_LED;
    int32_t i;
    if (!mgr || !fw_pattern)
        return;
    for (i = 0; i < NUM_CONV_TRACKS; i++) {
        if (cnv_state[i] != CNV_SYNTH)
            continue;
        if (fw_pattern[PAT_MUTES_OFFSET + CONV_FIRST_TRACK + i] != 0)
            set_led(mgr, LED_T1 + i, 0, 0);
        else
            set_led(mgr, LED_T1 + i, 2, PAL_BRIGHT_GREEN);
    }
}
