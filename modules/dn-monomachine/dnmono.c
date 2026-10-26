/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Digitone MK1 port of the Monomachine (Digi Mono), Plaits (Macro), and Sophie synth engines
 * onto the Digitone's machines-dn1 framework (digitone-mk1/machines.h).
 *
 * Dual-CPU + DSP architecture notes:
 * - Digitone MK1 runs the 8-voice FM synth + AMP envelope on CPU #2 (DSP, ColdFire MCF5441x)
 *   and transfers 32-sample blocks via 128 KB Dual-Port Shared RAM (eDMA ch 47) to CPU #1
 *   (Main OS, ColdFire MCF5441x) SRAM at 0x80004110 before the per-voice multimode filters.
 * - `machines-dn1` intercepts `ev_render_voices` on CPU #1, calls `render()` below to replace
 *   the 32-sample block (scaled to DNM_PEAK = Q15 << 12), and applies the voice's AMP ADSR
 *   envelope + velocity on CPU #1 before the Digitone's multimode filter, overdrive, and FX.
 * - `mono.c` preserves CPU #1's EMAC registers (`MACSR`, `ACC0`,
 *   `ACCEXT01`) via `emac_enter`/`emac_leave`.
 */
#include "digitone-mk1/machines.h"
#include "mono.h"
#include "macro.h"
#include "sophie.h"

#define VOICES 8

static struct mono_voice mvoices[VOICES];
static struct macro_voice macvoices[VOICES];
static struct ds_voice sophvoices[VOICES];
static uint8_t m_inited[VOICES];
static uint8_t mac_inited[VOICES];
static uint8_t soph_inited[VOICES];
static uint8_t last_model[VOICES];
static uint8_t soph_sounding[VOICES];
static uint32_t soph_birth[VOICES];
static int32_t soph_track[VOICES];
static uint32_t soph_clock;
static uint32_t mac_sub_phase[VOICES];
static int32_t mac_penv[VOICES];

/* ---- Formatting helpers ---- */

static char *put_s(char *o, const char *t)
{
    while ((*o = *t++))
        o++;
    return o;
}

static char *put_u(char *o, uint32_t n)
{
    char d[10];
    int i = 0;
    do {
        d[i++] = (char)('0' + n % 10);
        n /= 10;
    } while (n);
    while (i)
        *o++ = d[--i];
    *o = 0;
    return o;
}

static void fmt_oct(int32_t value, char *buf)
{
    int32_t o = (value >> 8) - 3;
    char *b = buf;
    if (o > 0)
        *b++ = '+';
    if (o < 0) {
        *b++ = '-';
        o = -o;
    }
    put_u(b, (uint32_t)o);
}

static void fmt_semi(int32_t value, char *buf)
{
    int s = ((value >> 8) & 0x7f) - 63;
    char *o = buf;
    s = s < -36 ? -36 : s > 36 ? 36 : s;
    if (s > 0)
        *o++ = '+';
    if (s < 0) {
        *o++ = '-';
        s = -s;
    }
    o = put_u(o, (uint32_t)s);
    put_s(o, "st");
}

static void fmt_saws(int32_t value, char *buf)
{
    int v = (value >> 8) & 0x7f;
    char *o = put_u(buf, v < 43 ? 1 : v < 86 ? 2 : 3);
    put_s(o, v < 43 ? " SAW" : " SAWS");
}

static void fmt_pct(int32_t value, char *buf)
{
    int v = (value >> 8) & 0x7f;
    char *o = put_u(buf, (uint32_t)((v * 100 + 63) / 127));
    put_s(o, "%");
}

static void fmt_vowel(int32_t value, char *buf)
{
    static const char *const vowel_name[10] = {"OO", "U", "AW", "AH", "UH", "AE", "EH", "IH", "EE", "ER"};
    int v = (value >> 8) & 0x7f;
    put_s(buf, vowel_name[(v * 9 * 2 + 127) / 254]);
}

static void fmt_cons(int32_t value, char *buf)
{
    static const char *const cons_name[8] = {"-", "S", "SH", "F", "H", "T", "K", "P"};
    int v = (value >> 8) & 0x7f;
    put_s(buf, cons_name[v >> 4]);
}

static void fmt_chord(int32_t value, char *buf)
{
    extern const char *const mono_chord_name[];
    extern int mono_chord_type(int v);
    int v = (value >> 8) & 0x7f;
    put_s(buf, mono_chord_name[mono_chord_type(v)]);
}

static void fmt_inv(int32_t value, char *buf)
{
    static const char *const inv_name[4] = {"ROOT", "1ST", "2ND", "3RD"};
    int v = (value >> 8) & 0x7f;
    put_s(buf, inv_name[v >> 5]);
}

static void fmt_sprd(int32_t value, char *buf)
{
    static const char *const sprd_name[4] = {"CLOSE", "OPEN", "WIDE", "XWIDE"};
    int v = (value >> 8) & 0x7f;
    put_s(buf, sprd_name[v >> 5]);
}

static int macro_eng_from_syn1b(int32_t val88)
{
    int v = val88 >> 8;
    if (v < 0)
        v = 0;
    if (v > 18)
        v = 18;
    return (v * 8) / 19;
}

static int soph_mod_from_syn1b(int32_t val88)
{
    int v = val88 >> 8;
    if (v < 0)
        v = 0;
    if (v > 18)
        v = 18;
    return (v * 4) / 19;
}

static void fmt_macro_eng(int32_t value, char *buf)
{
    put_s(buf, macro_engine_name[macro_eng_from_syn1b(value)]);
}

static void fmt_soph_model(int32_t value, char *buf)
{
    static const char *const models[4] = {"FUSE", "BOOM", "PIPE", "SHARD"};
    put_s(buf, models[soph_mod_from_syn1b(value)]);
}

static void fmt_soph_sweep(int32_t value, char *buf)
{
    int d = ((value >> 8) & 0x7f) - 64;
    char *o = buf;
    if (d > 0)
        *o++ = '+';
    if (d < 0) {
        *o++ = '-';
        d = -d;
    }
    put_u(o, (uint32_t)d);
}

static void fmt_soph_tune(int32_t value, char *buf)
{
    int raw = (value >> 8) & 0x7f;
    int cents = ((raw - 64) * 25) >> 4;
    char *o = buf;
    if (cents > 0)
        *o++ = '+';
    if (cents < 0) {
        *o++ = '-';
        cents = -cents;
    }
    put_u(o, (uint32_t)cents);
}

/* ---- Render callbacks ---- */

static void render_mono_model(int32_t voice, int32_t *block, const struct dnm_voice *v, int model)
{
    struct mono_voice *mv;
    uint8_t p[MONO_PARAMS];
    int16_t out[32];
    int32_t oct, pitch_128;
    int i;

    if ((uint32_t)voice >= VOICES)
        return;
    digimono_eco = 1;
    mv = &mvoices[voice];
    if (!m_inited[voice]) {
        mono_init(mv);
        mv->rng ^= (uint32_t)voice * 0x9e3779b9u;
        m_inited[voice] = 1;
    }
    if (last_model[voice] != (uint8_t)(model + 1)) {
        mv->own = 0;
        last_model[voice] = (uint8_t)(model + 1);
    }
    if (v->fresh)
        mono_trig(mv, model);

    for (i = 0; i < MONO_PARAMS; i++) {
        int32_t kv = dnm_knob(voice, 8 + i) >> 8;
        p[i] = kv < 0 ? 0 : kv > 127 ? 127 : (uint8_t)kv;
    }
    if (model == MONO_ENS || model == MONO_CHORD)
        p[4] = (uint8_t)(64 + (p[4] >> 1));

    oct = (dnm_knob(voice, 0) >> 8) - 3;
    pitch_128 = (v->pitch >> 9) + oct * (12 << 7);
    mono_render(mv, model, p, mono_pitch_inc(pitch_128), out, 32);

    for (i = 0; i < 32; i++)
        block[i] = ((int32_t)out[i]) << 12;
}

static void render_saw(int32_t voice, int32_t *block, const struct dnm_voice *v)
{
    render_mono_model(voice, block, v, MONO_SAW);
}

static void render_puls(int32_t voice, int32_t *block, const struct dnm_voice *v)
{
    render_mono_model(voice, block, v, MONO_PULS);
}

static void render_ens(int32_t voice, int32_t *block, const struct dnm_voice *v)
{
    render_mono_model(voice, block, v, MONO_ENS);
}

static void render_chord(int32_t voice, int32_t *block, const struct dnm_voice *v)
{
    render_mono_model(voice, block, v, MONO_CHORD);
}

static void render_vo(int32_t voice, int32_t *block, const struct dnm_voice *v)
{
    render_mono_model(voice, block, v, MONO_VO);
}

static void render_nois(int32_t voice, int32_t *block, const struct dnm_voice *v)
{
    render_mono_model(voice, block, v, MONO_NOIS);
}

static void render_psin(int32_t voice, int32_t *block, const struct dnm_voice *v)
{
    render_mono_model(voice, block, v, MONO_PSIN);
}

static void render_macro(int32_t voice, int32_t *block, const struct dnm_voice *v)
{
    struct macro_voice *mv;
    uint8_t p[MACRO_PARAMS];
    int16_t out[32];
    int32_t oct, eng, harm, timb, morp, fine, penv_amt, pdec, sub_mix;
    int32_t cents, penv_semi_128, pitch_128;
    uint32_t inc, sub_p;
    int i;

    if ((uint32_t)voice >= VOICES)
        return;
    digimono_eco = 1;
    mv = &macvoices[voice];
    if (!mac_inited[voice]) {
        macro_init(mv);
        mv->rng ^= (uint32_t)voice * 0x9e3779b9u;
        mac_inited[voice] = 1;
    }
    if (v->fresh) {
        macro_trig(mv);
        mac_penv[voice] = 32767;
    }

    oct  = (dnm_knob(voice, 0) >> 8) - 3;
    eng  = macro_eng_from_syn1b(dnm_knob(voice, 1));
    harm = (dnm_knob(voice, 8) >> 8) & 0x7f;
    timb = (dnm_knob(voice, 9) >> 8) & 0x7f;
    morp = (dnm_knob(voice, 10) >> 8) & 0x7f;
    fine = (dnm_knob(voice, 11) >> 8) & 0x7f;
    penv_amt = ((dnm_knob(voice, 12) >> 8) & 0x7f) - 63;
    pdec = (dnm_knob(voice, 13) >> 8) & 0x7f;
    sub_mix = (dnm_knob(voice, 14) >> 8) & 0x7f;

    p[0] = (uint8_t)(eng << MACRO_ZONE_SHIFT);
    p[1] = (uint8_t)harm;
    p[2] = (uint8_t)timb;
    p[3] = (uint8_t)morp;
    p[4] = p[5] = p[6] = 0;

    if (penv_amt < -36)
        penv_amt = -36;
    if (penv_amt > 36)
        penv_amt = 36;
    if (mac_penv[voice] > 0) {
        int32_t step = 64 + ((127 - pdec) * 16);
        mac_penv[voice] -= step;
        if (mac_penv[voice] < 0)
            mac_penv[voice] = 0;
    }
    penv_semi_128 = (penv_amt * mac_penv[voice]) >> 8;
    cents = ((fine - 64) * 25) >> 4;
    pitch_128 = (v->pitch >> 9) + oct * (12 << 7) + penv_semi_128 + ((cents * 128) / 100);
    inc = mono_pitch_inc(pitch_128);
    macro_render(mv, p, inc, out, 32);

    sub_p = mac_sub_phase[voice];
    for (i = 0; i < 32; i++) {
        int32_t s = out[i];
        if (sub_mix > 0) {
            int32_t sub_s = dnm_sin(sub_p);
            s = (s * (127 - (sub_mix >> 1)) + sub_s * (sub_mix >> 1)) >> 7;
        }
        block[i] = s << 12;
        sub_p += inc >> 1;
    }
    mac_sub_phase[voice] = sub_p;
}

static void render_sophie(int32_t voice, int32_t *block, const struct dnm_voice *v)
{
    struct ds_voice *ds;
    struct ds_params p;
    int32_t oct, model, colorr, metalr, sweepr, fbkr, foldr, tuner, cents, vel;
    uint32_t inc;
    int i, w, rank;

    if ((uint32_t)voice >= VOICES)
        return;
    ds = &sophvoices[voice];
    if (!soph_inited[voice]) {
        ds_voice_init(ds);
        ds->rng ^= (uint32_t)voice * 0x9e3779b9u;
        soph_inited[voice] = 1;
    }

    if (v->fresh) {
        soph_sounding[voice] = 1;
        soph_birth[voice] = ++soph_clock;
        soph_track[voice] = v->track;
    } else if (!soph_sounding[voice]) {
        soph_sounding[voice] = 1;
        soph_birth[voice] = ++soph_clock;
        soph_track[voice] = v->track;
    }

    /* Per-track newest-wins voice cap (1 voice per track, up to 4 tracks simultaneously) */
    rank = 0;
    for (w = 0; w < VOICES; w++) {
        if (soph_sounding[w] && soph_track[w] == v->track &&
            (int32_t)(soph_birth[w] - soph_birth[voice]) > 0)
            rank++;
    }
    if (rank >= 1) {
        soph_sounding[voice] = 0;
        for (i = 0; i < 32; i++)
            block[i] = 0;
        return;
    }

    ds_voice_gate(ds, v->gate ? (1 << 23) : 0, 3);

    if (!v->fresh && (!ds->active || ds->sleeping)) {
        for (i = 0; i < 32; i++)
            block[i] = 0;
        return;
    }

    oct    = (dnm_knob(voice, 0) >> 8) - 3;
    model  = soph_mod_from_syn1b(dnm_knob(voice, 1));
    colorr = (dnm_knob(voice, 8) >> 8) & 0x7f;
    metalr = (dnm_knob(voice, 9) >> 8) & 0x7f;
    sweepr = (dnm_knob(voice, 10) >> 8) & 0x7f;
    fbkr   = (dnm_knob(voice, 11) >> 8) & 0x7f;
    foldr  = (dnm_knob(voice, 12) >> 8) & 0x7f;
    tuner  = (dnm_knob(voice, 13) >> 8) & 0x7f;

    cents = ((tuner - 64) * 25) >> 4;
    inc = dnm_phase_inc(v->pitch + (oct * 12 << 16) + cents * 655) >> 16;
    if (inc < 8)
        inc = 8;
    if (inc > 24576)
        inc = 24576;

    p.phase_inc = (uint16_t)inc;
    p.model = (uint8_t)(model & 3);
    p.color = (uint8_t)colorr;
    p.metal = (uint8_t)metalr;
    p.sweep = (int8_t)(sweepr - 64);
    p.feedback = (uint8_t)fbkr;
    vel = v->velocity < 0 ? 0 : v->velocity > 127 ? 127 : v->velocity;
    p.velocity = (uint8_t)vel;
    p.fold = (uint8_t)foldr;

    ds_voice_render(ds, &p, v->fresh, block, 32);
    ds_fold_block(block, 32, p.fold);
    for (i = 0; i < 32; i++)
        block[i] >>= 2;
}

/* ---- Knob tables & defaults (SYN1 A=0, F=5, G=6; SYN2 A..H = 8..15) ---- */

static const struct dnm_knob knobs_saw[DNM_KNOBS] = {
    [0] = { "OCT", fmt_oct, 0 },
    [8] = { "UNIL", 0, 0 }, [9] = { "UNIW", 0, 0 }, [10] = { "UNIX", fmt_saws, 0 },
    [12] = { "SUBX", fmt_pct, 0 }, [13] = { "SUB1", 0, 0 }, [14] = { "SUB2", 0, 0 },
};
static const int16_t def_saw[DNM_KNOBS] = {
    3 << 8, -1, -1, -1, -1, -1, -1, -1,
    0 << 8, 40 << 8, 0 << 8, 0 << 8, 0 << 8, 0 << 8, 0 << 8, -1
};

static const struct dnm_knob knobs_puls[DNM_KNOBS] = {
    [0] = { "OCT", fmt_oct, 0 },
    [8] = { "UNIL", 0, 0 }, [9] = { "UNIW", 0, 0 }, [10] = { "SUB1", 0, 0 }, [11] = { "SUB2", 0, 0 },
    [12] = { "PW", 0, 0 }, [13] = { "PWAD", 0, 0 }, [14] = { "PWRS", 0, 0 },
};
static const int16_t def_puls[DNM_KNOBS] = {
    3 << 8, -1, -1, -1, -1, -1, -1, -1,
    0 << 8, 40 << 8, 0 << 8, 0 << 8, 64 << 8, 0 << 8, 40 << 8, -1
};

static const struct dnm_knob knobs_ens[DNM_KNOBS] = {
    [0] = { "OCT", fmt_oct, 0 },
    [8] = { "PCH2", fmt_semi, 0 }, [9] = { "PCH3", fmt_semi, 0 }, [10] = { "PCH4", fmt_semi, 0 },
    [11] = { "WAVE", fmt_pct, 0 }, [12] = { "PW", 0, 0 }, [13] = { "CHRL", 0, 0 }, [14] = { "CHRW", 0, 0 },
};
static const int16_t def_ens[DNM_KNOBS] = {
    3 << 8, -1, -1, -1, -1, -1, -1, -1,
    63 << 8, 63 << 8, 63 << 8, 0 << 8, 0 << 8, 64 << 8, 127 << 8, -1
};

static const struct dnm_knob knobs_chord[DNM_KNOBS] = {
    [0] = { "OCT", fmt_oct, 0 },
    [8] = { "TYPE", fmt_chord, 0 }, [9] = { "INV", fmt_inv, 0 }, [10] = { "SPRD", fmt_sprd, 0 },
    [11] = { "WAVE", 0, 0 }, [12] = { "PW", 0, 0 }, [13] = { "CHRL", 0, 0 }, [14] = { "CHRW", 0, 0 },
};
static const int16_t def_chord[DNM_KNOBS] = {
    3 << 8, -1, -1, -1, -1, -1, -1, -1,
    0 << 8, 0 << 8, 0 << 8, 16 << 8, 0 << 8, 64 << 8, 127 << 8, -1
};

static const struct dnm_knob knobs_vo[DNM_KNOBS] = {
    [0] = { "OCT", fmt_oct, 0 },
    [8] = { "VOC1", fmt_vowel, 0 }, [9] = { "VOC2", fmt_vowel, 0 }, [10] = { "V-SW", 0, 0 },
    [11] = { "VOIC", 0, 0 }, [12] = { "CONS", fmt_cons, 0 }, [13] = { "CLEN", 0, 0 }, [14] = { "CVOL", 0, 0 },
};
static const int16_t def_vo[DNM_KNOBS] = {
    3 << 8, -1, -1, -1, -1, -1, -1, -1,
    43 << 8, 113 << 8, 64 << 8, 0 << 8, 0 << 8, 40 << 8, 100 << 8, -1
};

static const struct dnm_knob knobs_nois[DNM_KNOBS] = {
    [0] = { "OCT", fmt_oct, 0 },
    [8] = { "S&H", 0, 0 }, [9] = { "RED", 0, 0 }, [10] = { "TONE", 0, 0 },
};
static const int16_t def_nois[DNM_KNOBS] = {
    3 << 8, -1, -1, -1, -1, -1, -1, -1,
    0 << 8, 0 << 8, 64 << 8, -1, -1, -1, -1, -1
};

static const struct dnm_knob knobs_psin[DNM_KNOBS] = {
    [0] = { "OCT", fmt_oct, 0 },
    [8] = { "NOT1", fmt_semi, 0 }, [9] = { "NOT2", fmt_semi, 0 }, [10] = { "NOT3", fmt_semi, 0 },
    [11] = { "EDEP", 0, 0 }, [12] = { "ESPD", 0, 0 },
};
static const int16_t def_psin[DNM_KNOBS] = {
    3 << 8, -1, -1, -1, -1, -1, -1, -1,
    63 << 8, 70 << 8, 75 << 8, 64 << 8, 64 << 8, -1, -1, -1
};

static const struct dnm_knob knobs_macro[DNM_KNOBS] = {
    [0] = { "OCT", fmt_oct, 0 }, [1] = { "ENGN", fmt_macro_eng, 0 },
    [8] = { "HARM", fmt_pct, 0 }, [9] = { "TIMB", fmt_pct, 0 },
    [10] = { "MORP", fmt_pct, 0 }, [11] = { "FINE", fmt_soph_tune, 0 },
    [12] = { "PENV", fmt_semi, 0 }, [13] = { "PDEC", fmt_pct, 0 },
    [14] = { "SUB", fmt_pct, 0 },
};
static const int16_t def_macro[DNM_KNOBS] = {
    3 << 8, 0 << 8, -1, -1, -1, -1, -1, -1,
    64 << 8, 64 << 8, 64 << 8, 64 << 8, 63 << 8, 64 << 8, 0 << 8, -1
};

static const struct dnm_knob knobs_sophie[DNM_KNOBS] = {
    [0] = { "OCT", fmt_oct, 0 }, [1] = { "MODEL", fmt_soph_model, 0 },
    [8] = { "COLOR", fmt_pct, 0 }, [9] = { "METAL", fmt_pct, 0 },
    [10] = { "SWEEP", fmt_soph_sweep, 0 }, [11] = { "FBK", fmt_pct, 0 },
    [12] = { "FOLD", fmt_pct, 0 }, [13] = { "TUNE", fmt_soph_tune, 0 },
};
static const int16_t def_sophie[DNM_KNOBS] = {
    3 << 8, 0 << 8, -1, -1, -1, -1, -1, -1,
    64 << 8, 64 << 8, 64 << 8, 32 << 8, 0 << 8, 64 << 8, -1, -1
};

/* ---- 16x16 tile icons ---- */

static const uint16_t icon_saw[16] = {
    0x0000, 0x0000, 0x0820, 0x0c60, 0x0aa0, 0x0920, 0x1860, 0x1020,
    0x2020, 0x2020, 0x4020, 0x4020, 0x8020, 0x0000, 0x0000, 0x0000,
};
static const uint16_t icon_puls[16] = {
    0x0000, 0x0000, 0x7e00, 0x4200, 0x4200, 0x4200, 0x4200, 0x4200,
    0x4200, 0x4200, 0x4200, 0x4200, 0x43fe, 0x0000, 0x0000, 0x0000,
};
static const uint16_t icon_ens[16] = {
    0x0000, 0x0410, 0x0c30, 0x1450, 0x2490, 0x4510, 0x0000, 0x0820,
    0x1860, 0x28a0, 0x4920, 0x8a20, 0x0000, 0x0000, 0x0000, 0x0000,
};
static const uint16_t icon_chord[16] = {
    0x0000, 0x01e0, 0x0120, 0x0120, 0x0120, 0x0720, 0x0f60, 0x0f20,
    0x06e0, 0x1ce0, 0x3c00, 0x3c00, 0x1800, 0x0000, 0x0000, 0x0000,
};
static const uint16_t icon_vo[16] = {
    0x0000, 0x07e0, 0x1818, 0x2004, 0x47e2, 0x4812, 0x53c2, 0x5002,
    0x4812, 0x47e2, 0x2004, 0x1818, 0x07e0, 0x0000, 0x0000, 0x0000,
};
static const uint16_t icon_nois[16] = {
    0x0000, 0x0100, 0x1120, 0x1524, 0x55a4, 0x55ac, 0xd5ad, 0x55ac,
    0x55a4, 0x1524, 0x1120, 0x0100, 0x0000, 0x0000, 0x0000, 0x0000,
};
static const uint16_t icon_psin[16] = {
    0x0000, 0x1c00, 0x2200, 0x4100, 0x8080, 0x0041, 0x1c22, 0x221c,
    0x4100, 0x8080, 0x0041, 0x0022, 0x001c, 0x0000, 0x0000, 0x0000,
};
static const uint16_t icon_macro[16] = {
    0x0000, 0x0180, 0x0240, 0x0420, 0x0810, 0x13c8, 0x2424, 0x4812,
    0x4812, 0x2424, 0x13c8, 0x0810, 0x0420, 0x0240, 0x0180, 0x0000,
};
static const uint16_t icon_sophie[16] = {
    0x0000, 0x0810, 0x0810, 0x1c38, 0x1c38, 0x3e7c, 0x3e7c, 0x7ffe,
    0x7ffe, 0x3e7c, 0x3e7c, 0x1c38, 0x1c38, 0x0810, 0x0810, 0x0000,
};

/* ---- Exported machine descriptors ---- */

const struct dnm_machine dnmono_saw    = { 10, "SAW",    icon_saw,    knobs_saw,    render_saw,    0, def_saw };
const struct dnm_machine dnmono_puls   = { 11, "PULSE",  icon_puls,   knobs_puls,   render_puls,   0, def_puls };
const struct dnm_machine dnmono_ens    = { 12, "ENS",    icon_ens,    knobs_ens,    render_ens,    0, def_ens };
const struct dnm_machine dnmono_chord  = { 13, "CHORD",  icon_chord,  knobs_chord,  render_chord,  0, def_chord };
const struct dnm_machine dnmono_vo     = { 14, "VO-6",   icon_vo,     knobs_vo,     render_vo,     0, def_vo };
const struct dnm_machine dnmono_nois   = { 15, "NOISE",  icon_nois,   knobs_nois,   render_nois,   0, def_nois };
const struct dnm_machine dnmono_psin   = { 16, "PSIN",   icon_psin,   knobs_psin,   render_psin,   0, def_psin };
const struct dnm_machine dnmono_macro  = { 18, "MACRO",  icon_macro,  knobs_macro,  render_macro,  0, def_macro };
const struct dnm_machine dnmono_sophie = { 19, "SOPHIE", icon_sophie, knobs_sophie, render_sophie, 0, def_sophie };
