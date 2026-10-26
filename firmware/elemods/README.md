# `firmware/elemods/` — curated module registry

This directory holds only the **current** version of each compiled `.elemod`
the release driver (`tools/release.py`) links. Superseded versions live in
`archive/` (local only, never linked). Binaries are gitignored; this index is
committed so the link-by-filename contract stays navigable.

## Linkable modules

| `.elemod` | version | source home |
|---|---|---|
| `core-dn1-4.1-os1.44.elemod` | 4.1 | `tools/elekloader/mods/core-dn1` |
| `digihalo-0.2-os1.44.elemod` | 0.2 | `tools/elekloader/mods/digihalo-dn1` |
| `digihealth-1.1-os1.44.elemod` | 1.1 | unknown — no local source dir (external upstream) |
| `digihoard-0.2-os1.44.elemod` | 0.2 | `tools/elekloader/mods/digihoard-dn1` |
| `digiprism-0.2-os1.44.elemod` | 0.2 | `tools/elekloader/mods/digiprism-dn1` |
| `digireel-0.2-os1.44.elemod` | 0.2 | `tools/elekloader/mods/digireel-dn1` |
| `digiswarm-0.2-os1.44.elemod` | 0.2 | `tools/elekloader/mods/digiswarm-dn1` |
| `digitide-0.2-os1.44.elemod` | 0.2 | `tools/elekloader/mods/digitide-dn1` |
| `digitriad-0.2-os1.44.elemod` | 0.2 | `tools/elekloader/mods/digitriad-dn1` |
| `dnmono-1.2-os1.44.elemod` | 1.2 | `modules/dn-monomachine` |
| `dnsine-1.1-os1.44.elemod` | 1.1 | unknown — legacy split, no current source dir |
| `dnthru-1.0-os1.44.elemod` | 1.0 | unknown — legacy, no current source dir |
| `fxkit-0.1-os1.44.elemod` | 0.1 | `tools/elekloader/mods/fxkit-dn1` |
| `machines-0.2-os1.44.elemod` | 0.2 | `tools/elekloader/mods/machines-dn1` |
| `tracks-1.4-os1.44.elemod` | 1.4 | `tools/elekloader/mods/tracks-dn1` |

## `archive/` (stale, never linked)

- `tracks-1.0-os1.44.elemod` through `tracks-1.3-os1.44.elemod` — superseded by tracks 1.4
- `tracks-1.4.elemod` — non-`-os1.44` stray, superseded by `tracks-1.4-os1.44.elemod`

New ported modules are born as buildable mods in `modules/dn-<name>/`
(see `docs/RELEASE_METHOD.md` step 1); their compiled output is copied here.
Reference/upstream sources in `modules/digi1_mods/`, `modules/digisophie/`,
`modules/digitables/` are never edited.
