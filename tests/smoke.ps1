# Smoke checks for Elektron-MODS repo (no hardware needed)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

function Ok($m) { Write-Host "OK $m" }
function Fail($m) { Write-Host "FAIL $m"; exit 1 }

# 1. Stock OS pin
$stock = Join-Path $root "firmware\Digitone_and_Digitone_Keys_OS1.44.syx"
if (!(Test-Path $stock)) { Fail "stock syx missing" }
$h = (certutil -hashfile $stock SHA256 | Select-String "^[0-9a-f]{64}$").ToString().Trim().ToLower()
if ($h -ne "d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659") { Fail "stock hash mismatch: $h" }
Ok "stock hash"

# 2. Per-release manifest checks: every ACTIVE release dir under
#    firmware/releases (everything except archive/) must ship
#    .syx + .syx.json + .map.json + README.md (binaries stay local; the
#    manifests are what CI and docs verify against).
$relroot = Join-Path $root "firmware\releases"
if (!(Test-Path (Join-Path $relroot "archive"))) { Fail "archive dir missing under firmware\releases" }
$active = @(Get-ChildItem $relroot -Directory | Where-Object { $_.Name -ne "archive" })
foreach ($d in $active) {
  $syx = Get-ChildItem $d.FullName -Filter *.syx | Select-Object -First 1
  if (!$syx) { Fail "no .syx in $($d.Name)" }
  foreach ($f in @("$($syx.Name).json", "$($syx.Name).map.json", "README.md")) {
    if (!(Test-Path (Join-Path $d.FullName $f))) { Fail "missing $($d.Name)\$f" }
  }
  # .syx.json must pin the measured stock sha256 (catches stub manifests
  # and builds linked against the wrong stock file)
  $j = Get-Content (Join-Path $d.FullName "$($syx.Name).json") -Raw | ConvertFrom-Json
  if ($j.stock.sha256 -ne "d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659") { Fail "stock pin wrong in $($d.Name)\$($syx.Name).json" }
  if (!($j.output.sha256 -match "^[0-9a-f]{64}$")) { Fail "bad output sha256 in $($d.Name)" }
  # README must be a real file, not a cut-off stub (final newline present)
  $bytes = [System.IO.File]::ReadAllBytes((Join-Path $d.FullName "README.md"))
  if ($bytes.Length -lt 256) { Fail "README too small (truncated?): $($d.Name)" }
  if ($bytes[-1] -ne 10) { Fail "README missing final newline (truncated?): $($d.Name)" }
}
if ($active.Count -eq 0) { Ok "no active releases yet (archive only)" }
else { Ok "release manifests ($($active.Count) dirs)" }

# 4. .bat snapshot check: every run-*.bat launcher must point at a firmware
#    snapshot folder that actually exists under tools/digiemu/portable.
$fwroot = Join-Path $root "tools\digiemu\portable\firmware"
$bats = Get-ChildItem (Join-Path $root "run-*.bat")
if ($bats.Count -eq 0) { Fail "no run-*.bat launchers found" }
foreach ($b in $bats) {
  $ids = Select-String -Path $b.FullName -Pattern 'portable\\firmware\\([A-Za-z0-9._-]+)' -AllMatches |
    ForEach-Object { $_.Matches } | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
  if ($b.Name -eq "run-emulator.bat") {
    if ($ids) { Fail "$($b.Name) should open the launcher, not a snapshot" }
    continue
  }
  if (!$ids) { Fail "$($b.Name) references no snapshot folder" }
  foreach ($id in $ids) {
    if (!(Test-Path (Join-Path $fwroot $id))) { Fail "$($b.Name) snapshot missing: portable\firmware\$id" }
  }
}
Ok ".bat snapshots ($($bats.Count) launchers)"

# 5. No firmware tracked
$tracked = git ls-files '*.syx' '*.bin' '*.elemod' '*.map.json' 2>$null
if ($tracked) { Fail "firmware tracked: $tracked" }
Ok "no firmware tracked"

# 6. WSL toolchain
wsl bash -c "which m68k-linux-gnu-gcc" | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "m68k toolchain missing in WSL" }
Ok "wsl toolchain"

Write-Host "SMOKE PASS"
