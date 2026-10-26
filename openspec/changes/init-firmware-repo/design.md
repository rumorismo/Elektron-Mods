# Design

## Context

See proposal.md Why. Current state: D:\Elektron-MODS has openspec root but empty specs, duplicate release folders (`8 tracks`, `8 tracks - Copy*` x5, `v1.44-8tracks-0.7` identical 1781536-byte build 1447), firmware `.syx/.bin/.elemod` mixed with source, no `tests/`, no `.gitignore`, no `docs/REPO.md`. Constraints: elekloader AGENTS.md forbids committing firmware; stock OS 1.44 pin must stay verifiable; tracks-dn1 1.4 `trk_queue` doubles voice load which explains cracking and must be recorded but not fixed here.

## Goals / Non-Goals

**Goals:**
- Git-initialized repo that clones clean and builds reproducibly via elekloader + digiemu.
- Single canonical 8-track release with manifest.
- Minimal test harness that catches boot and voice-budget regressions.

**Non-Goals:**
- No fix for voice cracking (per-track steal, 2-voice cap, REL cutoff, eco mode) — separate change.
- No new synth machines, arp-to-midi, global-fx, or browser memory features.
- No Modwerk submission or catalog changes.

## Decisions

- Git at repo root with `main` as default, single initial commit after cleanup, so history starts from a known-good tree. Alternative of in-place `git init` with all dupes kept was rejected because clones would carry ~10MB+ of duplicate syx and confuse which 1447 is canonical.
- `.gitignore` at root ignoring `*.syx` (except documented stock pin exception via `!` rule or docs-only reference), `*.bin`, `*.elemod`, `*.map.json`, `emu snapshots`, `__pycache__`, `.uv/`, `.venv/`. Rejected tool-specific ignores only; need Elektron-specific rules per elekloader policy.
- Dedupe by keeping `v1.44-8tracks-0.7/` as canonical (has README + json + map), moving other `8 tracks*` copies and old `v1.44-synth-*` / `v1.44+-*` to `firmware/releases/archive/` for one release then delete after verification. Rejected immediate delete to allow hash-compare safety.
- `tests/` as thin Python + powershell wrappers around existing `python -m elekloader.sdk.build`, `elekloader.patch`, and `uv run python -m emu.portable --add` flows, not a new framework, to match docs/MODDING_GUIDE.md and EMULATOR_WORKFLOW.md.
- `docs/REPO.md` as index only, linking to ARCHITECTURE.md, MODDING_GUIDE.md, EMULATOR_WORKFLOW.md, VOICE_OPTIMIZATION.md, not duplicating them.

## Risks / Trade-offs

- [Risk] Deleting a release copy that user considers canonical → Mitigation: archive first, verify SHA-256 `9bf961db617369c61c36900b1789be23d78c024e0afc6f49a311bb356cd4410c` for 8Tracks7.syx before removal.
- [Risk] `.gitignore` hides a file user wanted (e.g., stock syx) → Mitigation: explicitly document stock pin path and keep hash check in tests; use `git status` check for firmware per elekloader Done criteria.
- [Risk] Scope creep into voice fix → Mitigation: record baseline in proposal + tasks as `KNOWN ISSUE`, defer code changes.

## Migration Plan

1. Backup tree, `git init -b main`, add `.gitignore`, `tests/`, `docs/REPO.md`.
2. Move dupes to `archive/`, verify canonical hashes, commit.
3. Verify `openspec validate` passes, `git status` shows no firmware.
4. Rollback: delete `.git/` if init is wrong; archive folder restores dupes.

## Open Questions

- Keep stock `.syx` tracked or git-lfs / external download? Default: tracked with pin since README already references it, revisit if repo size matters.
- Keep `v1.44-synth-*` and `v1.44+-*` long-term or archive only 8-track dupes?
