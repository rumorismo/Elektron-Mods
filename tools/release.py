#!/usr/bin/env python3
"""Generic Digitone release driver.

Links compiled .elemod mods into a versioned release folder under
firmware/releases/v1.44-<slug>-0.<num>/ and (optionally) prepares a
digiemu snapshot plus a run-<slug>.bat launcher for trying it.

Usage:
  python3 tools/release.py --slug 8tracks --num 8 --tag 1448 --preset 8tracks
  python3 tools/release.py --slug mymod --num 1 --tag 1449 \
      --mod core-dn1-4.1-os1.44.elemod --mod mymod-0.1-os1.44.elemod --emu

Method: docs/RELEASE_METHOD.md

Gates (refuse before/after linking): stock SHA-256 pin, flavor
required/forbidden module sets (--preset), version-tag uniqueness
across firmware/releases (active + archive), link.order/tables match
plus per-flavor ddr_spare/flash_headroom minimums.
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STOCK = os.path.join(ROOT, "firmware", "Digitone_and_Digitone_Keys_OS1.44.syx")
STOCK_SHA = "d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659"
ELEMODS = os.path.join(ROOT, "firmware", "elemods")
ELEKLOADER = os.path.join(ROOT, "tools", "elekloader")
DIGIEMU = os.path.join(ROOT, "tools", "digiemu")

PRESETS = {
    "8tracks": [
        "core-dn1-4.1-os1.44.elemod",
        "machines-0.2-os1.44.elemod",
        "dnmono-1.2-os1.44.elemod",
        "dnsine-1.1-os1.44.elemod",
        "dnthru-1.0-os1.44.elemod",
        "digihealth-1.1-os1.44.elemod",
        "tracks-1.4-os1.44.elemod",
    ],
}

# Flavor definitions: required/forbidden elemod id substrings (matched
# case-insensitively against the requested elemod file basenames), plus
# minimum memory/flash spare enforced against the linked .syx.json.
# The "forbidden" list is empty for 8tracks today; the structure exists
# so flavors like a pure-synth (no-FX) build can forbid modules later.
FLAVORS = {
    "8tracks": {
        "required": ["core", "machines", "dnmono", "dnsine", "dnthru",
                     "digihealth", "tracks"],
        "forbidden": [],
        "min_ddr_spare": 150000,
        "min_flash_headroom": 1500000,
    },
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def check_flavor(preset, mods):
    """Refuse when the final mod list violates the flavor definition."""
    flavor = FLAVORS.get(preset)
    if flavor is None:
        return
    bases = [os.path.basename(m).lower() for m in mods]
    for req in flavor.get("required", []):
        if not any(req.lower() in b for b in bases):
            die(f"flavor '{preset}' requires module id '{req}' "
                f"but it is missing from: {', '.join(bases)}")
    for fb in flavor.get("forbidden", []):
        hits = [b for b in bases if fb.lower() in b]
        if hits:
            die(f"flavor '{preset}' forbids module id '{fb}' "
                f"but it is present in: {', '.join(hits)}")


def find_tag_holders(tag):
    """Return release files (active + archive) already using version tag."""
    holders = []
    pat = os.path.join(ROOT, "firmware", "releases", "**", "*.syx.json")
    for path in glob.glob(pat, recursive=True):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        versions = set()
        if d.get("version") is not None:
            versions.add(str(d["version"]))
        out = d.get("output") or {}
        if isinstance(out, dict) and out.get("ele3_version") is not None:
            versions.add(str(out["ele3_version"]))
        if str(tag) in versions:
            holders.append(path)
    pat = os.path.join(ROOT, "firmware", "releases", "**", "README.md")
    for path in glob.glob(pat, recursive=True):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception:
            continue
        for m in re.finditer(r"\(tag\s+([^)]+)\)", text):
            if m.group(1).strip() == str(tag):
                holders.append(path)
                break
    return sorted(set(holders))


def gcc_version():
    """WSL ColdFire gcc version line; 'unknown' on any failure (never fatal)."""
    cmds = [
        ["m68k-linux-gnu-gcc", "--version"],
        ["wsl", "bash", "-c",
         "m68k-linux-gnu-gcc --version | head -n1"],
    ]
    for cmd in cmds:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=60)
        except Exception:
            continue
        lines = (r.stdout or "").strip().splitlines()
        if r.returncode == 0 and lines and lines[0].strip():
            return lines[0].strip()
    return "unknown"


def verify_link(out_json, mods, flavor):
    """Assert link.order/tables match the request and budgets hold."""
    try:
        with open(out_json, encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        die(f"cannot read link manifest {out_json}: {e}")
    link = d.get("link") or {}
    order = link.get("order") or []
    tables = link.get("tables") or {}
    layout = link.get("layout") or {}
    output = d.get("output") or {}
    bases = [os.path.basename(m).lower() for m in mods]
    order_ids = [str(e).split()[0].lower() for e in order]
    if len(order) != len(mods):
        die(f"link.order has {len(order)} entries but {len(mods)} mods "
            f"were requested (order={order_ids})")
    for oid in order_ids:
        if not any(oid in b for b in bases):
            die(f"link.order entry '{oid}' matches no requested mod "
                f"({', '.join(bases)})")
    if not isinstance(tables, dict) or not tables:
        die("link.tables is empty - patcher wrote no dispatch tables")
    if flavor is None:
        return
    ddr_spare = layout.get("ddr_spare")
    flash_headroom = output.get("flash_headroom")
    min_ddr = flavor.get("min_ddr_spare", 0)
    min_flash = flavor.get("min_flash_headroom", 0)
    if ddr_spare is None or flash_headroom is None:
        die("link manifest lacks ddr_spare/flash_headroom - cannot "
            "enforce budget")
    if ddr_spare < min_ddr:
        die(f"over budget: ddr_spare {ddr_spare} < minimum {min_ddr}")
    if flash_headroom < min_flash:
        die(f"over budget: flash_headroom {flash_headroom} < "
            f"minimum {min_flash}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slug", required=True, help="release flavor, e.g. 8tracks")
    ap.add_argument("--num", type=int, required=True, help="release iteration (0.N)")
    ap.add_argument("--tag", help="OS version tag shown on hardware, e.g. 1448 (default: 144<num>)")
    ap.add_argument("--preset", choices=sorted(PRESETS), help="known module set")
    ap.add_argument("--mod", action="append", default=[], dest="mods",
                    help="elemod file name in firmware/elemods (repeatable)")
    ap.add_argument("--emu", action="store_true",
                    help="also add to digiemu (snapshot) and write run-<slug>.bat")
    a = ap.parse_args()

    tag = a.tag or f"144{a.num}"
    name = f"{a.slug.title()}{a.num}"  # 8tracks -> 8Tracks8
    release_dir = os.path.join(ROOT, "firmware", "releases", f"v1.44-{a.slug}-0.{a.num}")
    out = os.path.join(release_dir, f"Digitone_OS1.44_{name}.syx")

    mods = (PRESETS.get(a.preset, []) if a.preset else []) + a.mods
    if not mods:
        die("no modules given (--preset and/or --mod)")
    if not os.path.exists(STOCK):
        die(f"stock syx missing: {STOCK}")
    if sha256(STOCK) != STOCK_SHA:
        die("stock hash mismatch - wrong/changed stock file")
    if a.num <= 0:
        die("--num must be >= 1")
    if a.preset in FLAVORS:
        check_flavor(a.preset, mods)
    flavor = FLAVORS.get(a.preset or a.slug)

    holders = find_tag_holders(tag)
    if holders:
        die(f"version tag {tag} already used by: "
            f"{', '.join(holders)}")

    paths = []
    for m in mods:
        p = m if os.path.isabs(m) else os.path.join(ELEMODS, m)
        if not os.path.exists(p):
            die(f"missing elemod: {p}")
        paths.append(p)

    os.makedirs(release_dir, exist_ok=True)
    args = [sys.executable, "-m", "elekloader.patch", "--stock", STOCK]
    for p in paths:
        args += ["--mod", p]
    args += ["--out", out, "--version", tag]
    print(f"Linking {len(paths)} elemods -> {out} (version {tag})")
    res = subprocess.run(args, cwd=ELEKLOADER)
    if res.returncode != 0:
        sys.exit(res.returncode)
    for ext in ("", ".json", ".map.json"):
        if not os.path.exists(out + ext):
            die(f"patcher did not write {out}{ext}")
    verify_link(out + ".json", mods, flavor)

    readme = os.path.join(release_dir, "README.md")
    if not os.path.exists(readme):
        mods_list = "\n".join(f"- `{m}`" for m in mods)
        today = datetime.date.today().isoformat()
        with open(readme, "w", newline="\n") as f:
            f.write(f"""# Digitone OS 1.44 - {name} (tag {tag})

Built {today} with tools/release.py against stock OS 1.44
(SHA-256 `{STOCK_SHA}`).

Output SHA-256: `{sha256(out)}`

Toolchain: `{gcc_version()}`

## Modules
{mods_list}

## Verification
- emu boot: untested {today}
- hardware: untested

## Release notes
Known issue: 1-voice cap — simultaneous custom-machine voices may cause
audio cracking under load; see docs/VOICE_OPTIMIZATION.md.

## Try in emulator
Run `run-{a.slug}.bat` at the repo root (first run: build with `--emu`).

## Flash
Hold [FUNC] while powering on, press [TRIG 4] (MIDI upgrade), send
`{os.path.basename(out)}` with Elektron Transfer.
""")
        print(f"Wrote {readme}")
    else:
        print(f"README kept: {readme}")

    if a.emu:
        py = os.path.join(DIGIEMU, ".venv", "Scripts", "python.exe")
        if not os.path.exists(py):
            die(f"digiemu venv missing: {py}")
        res = subprocess.run([py, "-m", "emu.portable", "--add", out], cwd=DIGIEMU)
        if res.returncode != 0:
            sys.exit(res.returncode)
        snaps = sorted(glob.glob(os.path.join(DIGIEMU, "portable", "firmware", f"dn1-{tag}-*")),
                       key=os.path.getmtime)
        if not snaps:
            die(f"no snapshot dir dn1-{tag}-* found after --add")
        snap = os.path.basename(snaps[-1])
        bat = os.path.join(ROOT, f"run-{a.slug}.bat")
        with open(bat, "w", newline="\r\n") as f:
            f.write(
                '@echo off\n'
                f'title Digitone MK1 {name} (tag {tag})\n'
                'cd /d "%~dp0tools\\digiemu"\n'
                'set "PYTHONPATH=%~dp0tools\\digiemu"\n'
                f'".venv\\Scripts\\python.exe" -m emu.portable --worker panel '
                f'"%~dp0tools\\digiemu\\portable\\firmware\\{snap}"\n'
                'pause\n'
            )
        print(f"Wrote {bat} (snapshot {snap})")

    print("Release ready:")
    print(" -", out)
    print(" -", out + ".json")
    print(" -", readme)


if __name__ == "__main__":
    main()
