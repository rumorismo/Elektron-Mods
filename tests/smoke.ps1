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

# 2. Per-release manifest checks: every versioned release dir must ship
#    .syx + .syx.json + .map.json + README.md (binaries stay local; the
#    manifests are what CI and docs verify against).
$releases = @(
  @{ dir = "firmware\releases\v1.44-8tracks-0.7"; syx = "Digitone_OS1.44_8Tracks7.syx" },
  @{ dir = "firmware\releases\v1.44-synth-0.1";  syx = "Digitone_OS1.44_Synth_0.1.syx" },
  @{ dir = "firmware\releases\v1.44-synth-0.2";  syx = "Digitone_OS1.44_Synth_0.2.syx" },
  @{ dir = "firmware\releases\v1.44+-0.1";       syx = "Digitone_OS1.44+_0.1.syx" },
  @{ dir = "firmware\releases\v1.44+-0.2";       syx = "Digitone_OS1.44+_0.2.syx" },
  @{ dir = "firmware\releases\8 tracks";         syx = "Digitone_OS1.44_8Tracks7.syx" }
)
foreach ($r in $releases) {
  $d = Join-Path $root $r.dir
  if (!(Test-Path $d)) { Fail "release dir missing: $($r.dir)" }
  foreach ($f in @($r.syx, "$($r.syx).json", "$($r.syx).map.json", "README.md")) {
    if (!(Test-Path (Join-Path $d $f))) { Fail "missing $($r.dir)\$f" }
  }
  # .syx.json must pin the measured stock sha256 (catches stub manifests
  # and builds linked against the wrong stock file)
  $j = Get-Content (Join-Path $d "$($r.syx).json") -Raw | ConvertFrom-Json
  if ($j.stock.sha256 -ne "d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659") { Fail "stock pin wrong in $($r.dir)\$($r.syx).json" }
  if (!($j.output.sha256 -match "^[0-9a-f]{64}$")) { Fail "bad output sha256 in $($r.dir)\$($r.syx).json" }
}
Ok "release manifests ($($releases.Count) dirs)"

# 3. Truncated-README check: release READMEs must be complete files, not
#    cut-off copies (non-trivial size, terminated by a final newline).
foreach ($r in $releases) {
  $p = Join-Path $root (Join-Path $r.dir "README.md")
  $bytes = [System.IO.File]::ReadAllBytes($p)
  if ($bytes.Length -lt 1024) { Fail "README too small (truncated?): $($r.dir)" }
  if ($bytes[-1] -ne 10) { Fail "README missing final newline (truncated?): $($r.dir)" }
}
Ok "release READMEs complete"

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
