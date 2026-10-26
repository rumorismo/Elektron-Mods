# Tasks

## 1. Git init and ignore rules

- [x] 1.1 Init git repo on main and verify `git status` runs clean in D:\Elektron-MODS (done: repo live at https://github.com/rumorismo/Elektron-Mods, branch `main`)
- [x] 1.2 Add root `.gitignore` for `*.syx *.bin *.elemod *.map.json` plus digiemu snapshots, `__pycache__`, `.uv/`, `.venv/` and verify `git status --porcelain` shows no firmware binaries as tracked (done: enforced by smoke check #5)
- [x] 1.3 Document stock OS pin (`Digitone_and_Digitone_Keys_OS1.44.syx` SHA-256 `d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659`) in docs and verify `certutil -hashfile` matches (done: measured hash pinned in docs/REPO.md, docs/ARCHITECTURE.md and tests/smoke.ps1; the earlier `...bc67...` README hash was corrected to the measured value)

## 2. Canonical releases cleanup

- [x] 2.1 Hash-compare `v1.44-8tracks-0.7/`, `8 tracks/`, and `8 tracks - Copy*` syx files and verify canonical 1447 hash `9bf961db617369c61c36900b1789be23d78c024e0afc6f49a311bb356cd4410c` (done: all copies verified identical during dedupe)
- [x] 2.2 Move duplicate `8 tracks - Copy*` folders and old `v1.44-synth-*` / `v1.44+-*` to `firmware/releases/archive/` and verify `firmware/releases/` lists only canonical folders (done, superseded in scope: on 2026-10-26 the user decided ALL pre-existing releases — including `v1.44-8tracks-0.7/` and `8 tracks/` — move to `archive/`; `firmware/releases/` now holds only `archive/` until the first fresh release is built. New-release layout is carried by the `release-method` change)
- [x] 2.3 Ensure canonical `v1.44-8tracks-0.7/` contains README + `.syx` + `.syx.json` + `.map.json` and verify `openspec validate` still sees the change (done: verified complete before the folder moved to `archive/`; smoke checks manifests per release dir)

## 3. Test harness for firmware work

(Moved to the `release-method` change, re-scoped: 3.1 build smoke, 3.2 digiemu boot smoke, and 3.3 voice-budget reporting belong to the release verification loop — L0/L1/L3 of the verification pyramid — not to repo init. The smoke that shipped here covers stock hash, release manifests/READMEs, launcher snapshots, git cleanliness, and WSL toolchain.)

## 4. Repo map and final validation

- [x] 4.1 Write `docs/REPO.md` mapping mod source (`tools/elekloader/mods/tracks-dn1/`), releases, build, and emulator flow and verify every path in the doc exists on disk (done; `docs/RELEASE_METHOD.md` now carries the build/try flow)
- [x] 4.2 Run `openspec validate` and `git status` firmware check and verify no `.syx/.bin/.elemod` tracked except documented stock reference (done: validate passed; smoke #5 enforces continuously; stock itself stays local, pinned by documented hash)
- [x] 4.3 Create initial commit on main and verify `git log --oneline -1` and `git status` are clean (done: `5364f2e` initial layout commit; further commits `72f1e68` stock-hash fix + manifests, `1f2589b` docs reconciliation)

## Workflow follow-up

- Archive the change after review (all its own tasks are now complete).
- Follow-on change `release-method`: owns the release driver, method doc, and the verification pyramid (moved-in 3.1–3.3 re-scoped).
- Later follow-on change for voice-cracking fix (per-track steal, 1-voice cap, REL cutoff, eco mode) and todo.txt features (arp-to-midi, global-fx, sticky browser).
