# Tasks

## 1. Git init and ignore rules

- [ ] 1.1 Init git repo on main and verify `git status` runs clean in D:\Elektron-MODS
- [ ] 1.2 Add root `.gitignore` for `*.syx *.bin *.elemod *.map.json` plus digiemu snapshots, `__pycache__`, `.uv/`, `.venv/` and verify `git status --porcelain` shows no firmware binaries as tracked
- [ ] 1.3 Document stock OS pin (`Digitone_and_Digitone_Keys_OS1.44.syx` SHA-256 `d4f200d04484333d82822db7744e6484d0def8f2bc67b7752bd55ee2fb780cc13c9659`) in docs and verify `certutil -hashfile` matches

## 2. Canonical releases cleanup

- [ ] 2.1 Hash-compare `v1.44-8tracks-0.7/`, `8 tracks/`, and `8 tracks - Copy*` syx files and verify canonical 1447 hash `9bf961db617369c61c36900b1789be23d78c024e0afc6f49a311bb356cd4410c`
- [ ] 2.2 Move duplicate `8 tracks - Copy*` folders and old `v1.44-synth-*` / `v1.44+-*` to `firmware/releases/archive/` and verify `firmware/releases/` lists only canonical folders
- [ ] 2.3 Ensure canonical `v1.44-8tracks-0.7/` contains README + `.syx` + `.syx.json` + `.map.json` and verify `openspec validate` still sees the change

## 3. Test harness for firmware work

- [ ] 3.1 Add `tests/` with elekloader build smoke check (`python -m elekloader.sdk.build` + `elekloader.patch` against stock) and verify it fails on bad stock hash
- [ ] 3.2 Add digiemu boot smoke check (`uv run python -m emu.portable --add` for stock and 8-track) and verify both reach factory UI snapshot path
- [ ] 3.3 Add voice-budget report check referencing VOICE_OPTIMIZATION ~22k-tick headroom and tracks 1.4 `trk_queue` doubling as KNOWN ISSUE and verify report runs without hardware

## 4. Repo map and final validation

- [ ] 4.1 Write `docs/REPO.md` mapping mod source (`tools/elekloader/mods/tracks-dn1/`), releases, build, and emulator flow and verify every path in the doc exists on disk
- [ ] 4.2 Run `openspec validate` and `git status` firmware check and verify no `.syx/.bin/.elemod` tracked except documented stock reference
- [ ] 4.3 Create initial commit on main and verify `git log --oneline -1` and `git status` are clean

## Workflow follow-up

- Archive the change after review.
- Follow-on change for voice-cracking fix (per-track steal, 2-voice cap, REL cutoff, eco mode) and todo.txt features (arp-to-midi, global-fx, sticky browser).
