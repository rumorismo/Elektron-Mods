#!/usr/bin/env bash
# Boot proof for Elektron-MODS releases (L1, snapshot-oracle) - Linux port of tests/boot-check.ps1.
# For each .syx: add to digiemu in an isolated --home temp dir, wait up to
# TIMEOUT_SEC for the first-run worker to write gui.snap (written only after
# the factory UI settles; failures leave gui.snap.rejected), exit 0 required,
# and logs/first-run.log must contain no fault strings.
# Also runs a negative test on a deliberately truncated syx (must fail, no snap).
# Usage: bash tests/boot-check.sh [--extra-syx <path>]... [--timeout-sec <n>]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TIMEOUT_SEC=300
EXTRA_SYX=()
while [ $# -gt 0 ]; do
  case "$1" in
    --extra-syx)
      [ $# -ge 2 ] || { echo "FAIL --extra-syx needs a path"; exit 1; }
      p="$2"
      case "$p" in
        /*) ;;
        *) p="$(cd "$(dirname "$p")" && printf '%s/%s' "$(pwd)" "$(basename "$p")")" \
             || { echo "FAIL cannot resolve path: $2"; exit 1; } ;;
      esac
      EXTRA_SYX+=("$p"); shift 2
      ;;
    --timeout-sec)
      [ $# -ge 2 ] || { echo "FAIL --timeout-sec needs a value"; exit 1; }
      TIMEOUT_SEC="$2"; shift 2
      ;;
    -h|--help)
      echo "Usage: boot-check.sh [--extra-syx <path>]... [--timeout-sec <n>]"
      exit 0
      ;;
    *)
      echo "FAIL unknown arg: $1"; exit 1
      ;;
  esac
done

ok() { echo "OK $1"; }
fail() { echo "FAIL $1"; exit 1; }

DIGIEMU="$ROOT/tools/digiemu"
PY="$DIGIEMU/.venv/bin/python"
[ -x "$PY" ] || fail "digiemu venv missing: $PY"
STOCK="$ROOT/firmware/Digitone_and_Digitone_Keys_OS1.44.syx"
[ -f "$STOCK" ] || fail "missing $STOCK"
for f in ${EXTRA_SYX[@]+"${EXTRA_SYX[@]}"}; do
  [ -f "$f" ] || fail "missing extra syx $f"
done

# Fault strings from emu/bootstrap.py + emu/portable.py (see docs/EMU_TESTING.md spike 3.1).
FAULT_PATTERNS=(
  'not settled after [0-9]+M instructions'
  'NOT SETTLED after [0-9]+M instructions'
  'no live user interface after [0-9]+M'
  'first boot did not finish'
  'the \+Drive did not come up'
  'the first-boot job reports error'
  'stopped at 0x[0-9a-f]+ of'
  'sample volume is not mounted'
  'the DSP did not come up'
  'is not in the snapshot'
  'Traceback'
  'StepFailed'
  'was killed'
  'crashed'
  'exited multicall'
  'LOAD_FAILED'
  'INCOMPATIBLE'
)
fault_regex="$(IFS='|'; echo "${FAULT_PATTERNS[*]}")"

log_clean() {
  local log="$1"
  [ -f "$log" ] || fail "missing log $log"
  local hits
  hits="$(grep -E -a "$fault_regex" "$log" | head -n 10 || true)"
  if [ -n "$hits" ]; then
    echo "$hits" | sed 's/^/  fault: /'
    return 1
  fi
  return 0
}

test_one_boot() {
  local syx="$1" label="$2"
  echo "--- boot: $label ---"
  local home
  home="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap "rm -rf '$home'" RETURN
  local out code
  set +e
  out="$(cd "$DIGIEMU" && timeout "$TIMEOUT_SEC" "$PY" -m emu.portable --home "$home" --add "$syx" --yes 2>&1)"
  code=$?
  set -e
  if [ "$code" -eq 124 ]; then
    echo "$out" | tail -n 20
    fail "$label: worker still running after ${TIMEOUT_SEC}s (no settle)"
  fi
  if [ "$code" -ne 0 ]; then
    echo "$out" | tail -n 20
    fail "$label: --add exit $code"
  fi
  # Snapshot oracle: fresh gui.snap under the temp home (never resume.snap).
  local mins=$(( TIMEOUT_SEC / 60 + 5 ))
  local snaps
  snaps="$(find "$home" -name 'gui.snap' -mmin "-$mins" 2>/dev/null || true)"
  [ -n "$snaps" ] || fail "$label: no fresh gui.snap within timeout"
  local snap
  snap="$(find "$home" -name 'gui.snap' -mmin "-$mins" -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -n 1 | cut -d' ' -f2-)"
  ok "$label snapshot ${snap#"$home"/}"
  if [ -f "$(dirname "$snap")/gui.snap.rejected" ]; then
    fail "$label: gui.snap.rejected present (settle rejected)"
  fi
  local log
  log="$(find "$home" -name 'first-run.log' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -n 1 | cut -d' ' -f2- || true)"
  [ -n "$log" ] || fail "$label: missing first-run.log under temp home"
  log_clean "$log" || fail "$label: fault strings in first-run.log"
  ok "$label clean log"
  rm -rf "$home"
  trap - RETURN
}

test_one_boot "$STOCK" "stock-1.44"
for x in ${EXTRA_SYX[@]+"${EXTRA_SYX[@]}"}; do
  test_one_boot "$x" "extra-$(basename "$x")"
done

# Negative: truncated copy must refuse (identify_release 'truncated or damaged'), no snap.
echo "--- boot: truncated-negative ---"
NEG_HOME="$(mktemp -d)"
trap 'rm -rf "$NEG_HOME"' EXIT
TRUNC="$NEG_HOME/truncated.syx"
head -c 1048576 "$STOCK" > "$TRUNC"
set +e
NEG_OUT="$(cd "$DIGIEMU" && timeout 120 "$PY" -m emu.portable --home "$NEG_HOME" --add "$TRUNC" --yes 2>&1)"
NEG_CODE=$?
set -e
[ "$NEG_CODE" -eq 124 ] && fail "truncated: worker hung"
[ "$NEG_CODE" -ne 0 ] || fail "truncated: --add exit 0 (should refuse)"
echo "$NEG_OUT" | grep -qi 'truncated' || { echo "$NEG_OUT" | head -n 20; fail "truncated: no truncation diagnostic in output"; }
BAD_SNAPS="$(find "$NEG_HOME" -name 'gui.snap' 2>/dev/null || true)"
[ -z "$BAD_SNAPS" ] || fail "truncated: gui.snap written for damaged input"
ok "truncated refused, no snapshot"
rm -rf "$NEG_HOME"
trap - EXIT

echo "BOOT-CHECK PASS"
