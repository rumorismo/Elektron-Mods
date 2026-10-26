# Digitone MK1 Voice & Performance Optimization Guide

This document preserves the architecture details, voice lifecycle contracts, and optimization techniques for custom synthesis machines on the **Elektron Digitone MK1** and **Digitone Keys** (using `core-dn1` and `machines-dn1`).

---

## 1. Dual-CPU Hardware Architecture & Timing Budget

The Digitone MK1 audio subsystem runs across two ColdFire processors:
* **CPU #2 (DSP ColdFire)**: Renders the stock 8-voice 4-operator FM synthesis engine in firmware `section_2_DSP.bin`. Every 667 µs, an eDMA transfer (channel 47) copies the 8 rendered voice blocks (32 samples each, signed Q1.31) across the 128 KB Dual-Port Shared RAM to CPU #1 SRAM at `0x80004110` (`fw_voices`).
* **CPU #1 (Main OS ColdFire MCF5441x)**: Runs FreeRTOS, UI tasks, OLED display, sequencer, MIDI, USB, and the **Audio Interrupt (`vector 191`)** at 1,500 Hz (every 666.7 µs).

### The 667 µs Audio Block Budget (at 132 MHz / 88,000 DTIM0 Bus Clock Ticks)

| Subsystem on CPU #1 | Share of Block | Cycles / Ticks | Description |
| :--- | :---: | :---: | :--- |
| **Stock Voice Filters** | ~7.9% | ~7,000 ticks | 8 multimode resonant filters (LP/HP/BP) + base-width filters. |
| **Stock Voice Mix & Overdrive** | ~2.3% | ~2,000 ticks | Voice summing, pan, and analog overdrive modeling. |
| **Stock Master FX** | ~31.9% | ~28,000 ticks | Chorus, Delay, Reverb, and Master Drive. |
| **Stock Render Overhead** | ~14.5% | ~13,000 ticks | Interrupt entry/exit, eDMA sync, smoother glide targets. |
| **Stock Total Render Load** | **~56.6%** | **~50,000 ticks** | Baseline load before any custom mod code runs. |
| **FreeRTOS UI & Sequencer Tasks** | **~18–20%** | **~16,000 ticks** | Front panel buttons, encoders, OLED redraw, MIDI dispatch. |
| **Available Headroom for Custom Mods** | **~23–25%** | **~22,000 ticks** | Safe ceiling for `ev_render_voices` / `dnm_render`. |

> [!CAUTION]
> If custom machine rendering on CPU #1 exceeds **~25% of the block** (~22,000 `DTCN0` ticks), total CPU load crosses **85–100%**. At this point, the 1,500 Hz audio interrupt starves the lower-priority FreeRTOS UI task and sequencer, causing severe button/encoder latency, display lag, and audio buffer underruns.

---

## 2. Key Pitfalls & Root Causes of CPU Spikes

### A. The "Zombie" FM Voice Leak
* **Mechanism**: Digitone's `ev_voice_on` (`dnm_voice_on`) fires for *every* note on *every* voice (`0..7`), including tracks running stock `FM`. `dnm_voice_on` sets `vs[v].stage = ATK` and `vs[v].v.gate = 1`.
* **The Bug**: If `dnm_render` checks `if (id <= 0) continue;` before processing `fw_gate_off`, the single-block note release event is missed for FM voices. The envelope never transitions to `REL` or `OFF`.
* **The Symptom**: When any track is switched from `FM` to a custom machine, `core_sound_set` updates the sound slots on voices that previously played that track. Those voices wake up with `stage = ATK/SUS` and `gate = 1` permanently stuck, rendering up to **8 simultaneous voices at 100% sustain forever even while idle**.
* **The Rule**: Always clear `vs[v].stage = OFF; vs[v].level = 0; vs[v].v.gate = 0; vs[v].v.fresh = 0;` whenever a voice is on `FM` (`id <= 0`) or when a track's machine is changed in `machines_pick`.

### B. Unbounded Voice Stacking from Digitone's Round-Robin Allocator
* Digitone MK1 has 8 polyphonic voice slots rotated round-robin across tracks.
* Even when playing monophonic melodies on a custom machine track, sequential notes occupy new voices while previous notes are still in their `REL` release stage.
* With typical release times (`REL = 64..110`, lasting 0.9s to 3s), all 8 voices become active simultaneously.
* Running 8 simultaneous voices of heavy engines (Plaits `MACRO`, `SOPHIE`, `ENS`, `CHORD`, `VO-6`) requires >120% CPU on CPU #1.

---

## 3. Mandatory Best Practices for Sound Management

### 1. Enforce Per-Track Voice Stealing (Newest-Wins)
Custom Monomachine and Digitakt engines expect 1 voice per track:
```c
/* Track newer active voices on the same track */
for (w = 0; w < VOICES; w++) {
    if (w != v && mach[w] && (vs[w].stage != OFF || vs[w].level != 0) &&
        (int32_t)(vs[w].birth - vs[v].birth) > 0) {
        if (vs[w].v.track == vs[v].v.track)
            newer_track++;
    }
}
/* When a newer note triggers on the same track, retire the older voice */
if (newer_track >= 1) {
    vs[v].stage = OFF;
    vs[v].level = 0;
    vs[v].v.gate = 0;
}
```

### 2. Cap Total Global Modded Voices to 1 (current shipped behavior)

> **Current truth (Release 0.2, October 2026): the engine enforces a strict
> 1-voice monophonic budget (`newer_all >= 1`)** in
> `tools/elekloader/mods/machines-dn1/machines.c`, matching the 0.2 release
> notes (`firmware/releases/v1.44-synth-0.2/README.md`,
> `firmware/releases/v1.44+-0.2/README.md`). One software voice costs
> ~22,000 ticks; two concurrent voices cost ~44,000, pushing total load to
> ~94,000 ticks (>105% overrun). (The older `newer_all >= 2` 2-voice guidance
> was pre-0.2 and no longer ships.)
Because stock processing occupies 56.6% of CPU #1, render at most **1 custom
voice at a time across all 4 tracks**:
```c
if (newer_all >= 1) {
    vs[v].stage = OFF;
    vs[v].level = 0;
    vs[v].v.gate = 0;
}
```
This guarantees that custom synthesis never consumes more than ~10% of CPU #1
(one voice ≈ 22,000 ticks ≈ 25% of the block worst-case, retired immediately
on the next note-on by `dnm_voice_on` stealing), keeping total CPU under ~75%
under all playing conditions. (Pre-0.2 code used `newer_all >= 2`; do not
revert to 2 without re-measuring the ~94k-tick overrun documented above.)

### 3. Clean Envelope Cutoff
Do not let exponential or slow linear release tails compute down to `-90 dB` (1/32768):
```c
case REL:
    l1 -= dnm_rate[amp(voice, S_REL)];
    if (l1 <= 64) {   /* Cut off below -54 dB */
        l1 = 0;
        vs[voice].stage = OFF;
    }
    break;
```

### 4. Use Eco Mode for Heavy Synthesis Models
* For complex engines like Mutable Instruments Plaits (`MACRO`), set `digimono_eco = 1`.
* In `macro.c`, `digimono_eco = 1` switches 2OP FM from 4x oversampling to 2x oversampling, and particle models from 6 particles to 4 particles, cutting render time by 50% with negligible perceptual difference.
