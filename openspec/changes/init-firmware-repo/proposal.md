# Proposal

## Why

D:\Elektron-MODS holds working 8-track firmware (v1.44-8tracks-0.7 / tracks 1.4) plus docs, modules, and tools, but it is not a usable repo: no git, 6 duplicate `8 tracks - Copy*` release folders, firmware binaries mixed with source, no test place, and voice cracking (Bank B overload) with no reproduction path.

## What Changes

- Init git repo in D:\Elektron-MODS with main branch and clean initial commit.
- Add root `.gitignore` covering Elektron firmware derived files: `*.syx`, `*.bin`, `*.elemod`, `*.map.json`, digiemu snapshots / +Drive images, `__pycache__`, `.uv/`, `.venv/`.
- Dedupe `firmware/releases/`: keep canonical `v1.44-8tracks-0.7/` + `8 tracks/` (identical 1781536-byte build 1447), archive or remove `8 tracks - Copy*` and `v1.44-synth-*` / `v1.44+-*` into `firmware/releases/archive/` or delete per user choice.
- Keep stock `Digitone_and_Digitone_Keys_OS1.44.syx` tracked with SHA-256 pin `d4f200d04484333d82822db7744e6484d0def8f2bc67b7752bd55ee2fb780cc13c9659`; document that all other `.syx` are build outputs, not source.
- Add `tests/` layout for mod build + emulator smoke checks (stock boot, 8-track boot, voice-budget check).
- Add `docs/REPO.md` short map: where source lives (`tools/elekloader/mods/tracks-dn1/`), where releases go, how to build with elekloader, how to test in digiemu.
- Record voice-cracking baseline (tracks 1.4 `trk_queue` background-bank doubling + dnmono/dnsine load exceeding ~22k tick headroom) as known issue, not fixed in this change.

## Capabilities

### New Capabilities
- `firmware-repo`: canonical repo layout, ignore rules, release conventions, and test entry points for all Digitone firmware modifications hosted here.

### Modified Capabilities
- None.

## Impact

- Affects repo root, `firmware/releases/`, `openspec/`, new `tests/`, new `docs/REPO.md`.
- No firmware logic changes; no hardware flash behavior changes in this change.
- Unblocks follow-on changes: voice-budget fix (per-track steal, 2-voice cap, REL cutoff, eco mode), arp-to-midi / global-fx / sticky browser from todo.txt.
