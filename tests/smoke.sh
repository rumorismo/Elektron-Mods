#!/usr/bin/env bash
# Smoke checks for Elektron-MODS repo (no hardware needed) - Linux port of tests/smoke.ps1.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

STOCK_SHA="d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659"

ok() { echo "OK $1"; }
fail() { echo "FAIL $1"; exit 1; }

# 1. Stock OS pin
stock="$ROOT/firmware/Digitone_and_Digitone_Keys_OS1.44.syx"
[ -f "$stock" ] || fail "stock syx missing"
h="$(sha256sum "$stock" | awk '{print $1}' | tr 'A-Z' 'a-z')"
[ "$h" = "$STOCK_SHA" ] || fail "stock hash mismatch: $h"
ok "stock hash"

# 2. Per-release manifest checks: every ACTIVE release dir under
#    firmware/releases (everything except archive/) must ship
#    .syx + .syx.json + .map.json + README.md.
relroot="$ROOT/firmware/releases"
[ -d "$relroot/archive" ] || fail "archive dir missing under firmware/releases"
active=()
for d in "$relroot"/*/; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  [ "$name" = "archive" ] && continue
  active+=("$d")
done
for d in ${active[@]+"${active[@]}"}; do
  name="$(basename "$d")"
  syx="$(find "$d" -maxdepth 1 -name '*.syx' -print | head -n 1 || true)"
  [ -n "$syx" ] || fail "no .syx in $name"
  base="$(basename "$syx")"
  for f in "$base.json" "$base.map.json" "README.md"; do
    [ -f "$d/$f" ] || fail "missing $name/$f"
  done
  # .syx.json must pin the measured stock sha256 and carry a 64-hex output sha256.
  json_ok="$(python3 -c '
import json, re, sys
j = json.load(open(sys.argv[1]))
stock = (j.get("stock") or {}).get("sha256", "")
out = (j.get("output") or {}).get("sha256", "")
ok = stock == sys.argv[2] and re.fullmatch(r"[0-9a-f]{64}", out or "") is not None
print("yes" if ok else "no")
' "$d/$base.json" "$STOCK_SHA")"
  [ "$json_ok" = "yes" ] || fail "bad sha256 pins in $name/$base.json (want stock=$STOCK_SHA, output=64hex)"
  # README must be a real file, not a cut-off stub (final newline present).
  size="$(stat -c%s "$d/README.md")"
  [ "$size" -ge 256 ] || fail "README too small (truncated?): $name"
  last="$(tail -c 1 "$d/README.md" | od -An -tu1 | tr -d ' \n')"
  [ "$last" = "10" ] || fail "README missing final newline (truncated?): $name"
done
if [ "${#active[@]}" -eq 0 ]; then
  ok "no active releases yet (archive only)"
else
  ok "release manifests (${#active[@]} dirs)"
fi

# 3. Snapshot check: every run-*.sh and run-*.bat launcher that references a
#    firmware snapshot must point at one that exists under tools/digiemu/portable.
fwroot="$ROOT/tools/digiemu/portable/firmware"
shopt -s nullglob
launchers=( "$ROOT"/run-*.sh "$ROOT"/run-*.bat )
shopt -u nullglob
[ "${#launchers[@]}" -gt 0 ] || fail "no run-* launchers found"
for b in "${launchers[@]}"; do
  bn="$(basename "$b")"
  # Accept both portable/firmware/<id> and portable\firmware\<id>.
  ids="$(grep -oE 'portable[/\\]+firmware[/\\]+[A-Za-z0-9._-]+' "$b" 2>/dev/null \
    | sed -E 's|.*firmware[/\\]+||' | sort -u || true)"
  case "$bn" in
    run-emulator.*)
      [ -z "$ids" ] || fail "$bn should open the launcher, not a snapshot"
      ;;
    *)
      [ -n "$ids" ] || fail "$bn references no snapshot folder"
      while IFS= read -r id; do
        [ -n "$id" ] || continue
        [ -d "$fwroot/$id" ] || fail "$bn snapshot missing: portable/firmware/$id"
      done <<< "$ids"
      ;;
  esac
done
ok "snapshots (${#launchers[@]} launchers)"

# 4. No firmware tracked
tracked="$(git -C "$ROOT" ls-files '*.syx' '*.bin' '*.elemod' '*.map.json' 2>/dev/null || true)"
[ -z "$tracked" ] || fail "firmware tracked: $tracked"
ok "no firmware tracked"

# 5. Toolchain
command -v m68k-linux-gnu-gcc >/dev/null 2>&1 || fail "m68k toolchain missing (m68k-linux-gnu-gcc not on PATH)"
ok "toolchain"

echo "SMOKE PASS"
