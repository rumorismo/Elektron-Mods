#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/tools/digiemu"
export PYTHONPATH="$SCRIPT_DIR/tools/digiemu"
exec .venv/bin/python -m emu.portable --worker panel "$SCRIPT_DIR/tools/digiemu/portable/firmware/dn1-1490-38aa5ba5"
