# Smoke checks for Elektron-MODS repo (no hardware needed)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

function Ok($m) { Write-Host "OK $m" }
function Fail($m) { Write-Host "FAIL $m"; exit 1 }

# 1. Stock OS pin
$stock = Join-Path $root "firmware\Digitone_and_Digitone_Keys_OS1.44.syx"
if (!(Test-Path $stock)) { Fail "stock syx missing" }
$h = (certutil -hashfile $stock SHA256 | Select-String "^[0-9a-f]{64}$").ToString().Trim().ToLower()
if ($h -ne "d4f200d04484333d82822db7744e6484d0def8f2bc67b7752bd55ee2fb780cc13c9659") { Fail "stock hash mismatch: $h" }
Ok "stock hash"

# 2. Canonical release manifest
$canon = Join-Path $root "firmware\releases\v1.44-8tracks-0.7\Digitone_OS1.44_8Tracks7.syx.json"
if (!(Test-Path $canon)) { Fail "canonical manifest missing" }
Ok "canonical manifest"

# 3. No firmware tracked
$tracked = git ls-files '*.syx' '*.bin' '*.elemod' '*.map.json' 2>$null
if ($tracked) { Fail "firmware tracked: $tracked" }
Ok "no firmware tracked"

# 4. WSL toolchain
wsl bash -c "which m68k-linux-gnu-gcc" | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "m68k toolchain missing in WSL" }
Ok "wsl toolchain"

Write-Host "SMOKE PASS"
