# Boot proof for Elektron-MODS releases (L1, snapshot-oracle).
# For each .syx: add to digiemu in an isolated --home temp dir, wait up to
# TimeoutSec for the first-run worker to write gui.snap (written only after
# the factory UI settles; failures leave gui.snap.rejected), exit 0 required,
# and logs/first-run.log must contain no fault strings.
# Also runs a negative test on a deliberately truncated syx (must fail, no snap).
# Binaries stay local: temp homes live under $env:TEMP, truncated copies too.
# Usage: powershell -ExecutionPolicy Bypass -File tests/boot-check.ps1
#   [-ExtraSyx <path>...] to also require a pass on additional builds.
param([int]$TimeoutSec = 300, [string[]]$ExtraSyx = @())
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
function Ok($m) { Write-Host "OK $m" }
function Fail($m) { Write-Host "FAIL $m"; exit 1 }

$digiemu = Join-Path $root "tools\digiemu"
$py = Join-Path $digiemu ".venv\Scripts\python.exe"
if (!(Test-Path $py)) { Fail "digiemu venv missing: $py" }
$stock = Join-Path $root "firmware\Digitone_and_Digitone_Keys_OS1.44.syx"
if (!(Test-Path $stock)) { Fail "missing $stock" }
foreach ($f in $ExtraSyx) { if (!(Test-Path $f)) { Fail "missing extra syx $f" } }

# Fault strings from emu/bootstrap.py + emu/portable.py (see docs/EMU_TESTING.md spike 3.1).
$FaultPatterns = @(
  'not settled after \d+M instructions',
  'NOT SETTLED after \d+M instructions',
  'no live user interface after \d+M',
  'first boot did not finish',
  'the \+Drive did not come up',
  'the first-boot job reports error',
  'stopped at 0x[0-9a-f]+ of',
  'sample volume is not mounted',
  'the DSP did not come up',
  'is not in the snapshot',
  'Traceback',
  'StepFailed',
  'was killed',
  'crashed',
  'exited multicall',
  'LOAD_FAILED',
  'INCOMPATIBLE'
)

function Test-LogClean($logPath) {
  if (!(Test-Path $logPath)) { Fail "missing log $logPath" }
  $hits = Select-String -Path $logPath -Pattern $FaultPatterns -AllMatches
  if ($hits) {
    foreach ($h in ($hits | Select-Object -First 10)) { Write-Host "  fault: $($h.Line.Trim())" }
    return $false
  }
  return $true
}

function Test-OneBoot($syx, $label) {
  Write-Host "--- boot: ${label} ---"
  $home_ = Join-Path ([System.IO.Path]::GetTempPath()) ("bootcheck-" + [System.IO.Path]::GetRandomFileName())
  New-Item -ItemType Directory $home_ | Out-Null
  try {
    $job = Start-Job -ScriptBlock {
      param($py, $digiemu, $home_, $syx)
      Set-Location $digiemu
      $o = & $py -m emu.portable --home $home_ --add $syx --yes 2>&1 | Out-String
      return @{ Exit = $LASTEXITCODE; Out = $o }
    } -ArgumentList $py, $digiemu, $home_, $syx
    $done = Wait-Job $job -Timeout $TimeoutSec
    if (!$done) {
      try { Stop-Job $job } catch {}
      Fail "${label}: worker still running after ${TimeoutSec}s (no settle)"
    }
    $res = Receive-Job $job
    Remove-Job $job -Force -ErrorAction SilentlyContinue
    $out = if ($res -is [hashtable]) { $res.Out } else { "$res" }
    $code = if ($res -is [hashtable]) { $res.Exit } else { -1 }
    if ($code -ne 0) {
      Write-Host ($out | Select-Object -Last 20 | Out-String)
      Fail "${label}: --add exit $code"
    }
    # Snapshot oracle: fresh gui.snap under the temp home (never resume.snap).
    $snaps = @(Get-ChildItem $home_ -Recurse -Filter "gui.snap" -ErrorAction SilentlyContinue |
      Where-Object { $_.LastWriteTime -gt (Get-Date).AddMinutes(-($TimeoutSec / 60 + 5)) })
    if ($snaps.Count -eq 0) { Fail "${label}: no fresh gui.snap within timeout" }
    $snap = $snaps | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    Ok "${label} snapshot $($snap.FullName.Substring($home_.Length + 1))"
    if (Test-Path (Join-Path $snap.Directory.FullName "gui.snap.rejected")) {
      Fail "${label}: gui.snap.rejected present (settle rejected)"
    }
    $log = @(Get-ChildItem $home_ -Recurse -Filter "first-run.log" -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1)
    if ($log.Count -eq 0) { Fail "${label}: missing first-run.log under temp home" }
    if (!(Test-LogClean $log.FullName)) { Fail "${label}: fault strings in first-run.log" }
    Ok "${label} clean log"
  } finally {
    Remove-Item $home_ -Recurse -Force -ErrorAction SilentlyContinue
  }
}

Test-OneBoot $stock "stock-1.44"
foreach ($x in $ExtraSyx) { Test-OneBoot $x ("extra-" + (Split-Path $x -Leaf)) }

# Negative: truncated copy must refuse (identify_release 'truncated or damaged'), no snap.
Write-Host "--- boot: truncated-negative ---"
$negHome = Join-Path ([System.IO.Path]::GetTempPath()) ("bootcheck-neg-" + [System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory $negHome | Out-Null
try {
  $trunc = Join-Path $negHome "truncated.syx"
  $bytes = [System.IO.File]::ReadAllBytes($stock)
  [System.IO.File]::WriteAllBytes($trunc, $bytes[0..(1MB - 1)])
  $p = Start-Process $py -ArgumentList @("-m", "emu.portable", "--home", $negHome, "--add", $trunc, "--yes") `
    -WorkingDirectory $digiemu -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $negHome "out.txt") -RedirectStandardError (Join-Path $negHome "err.txt")
  if (!$p.WaitForExit(120000)) { try { $p.Kill() } catch {}; Fail "truncated: worker hung" }
  $combined = ""
  foreach ($f in @((Join-Path $negHome "out.txt"), (Join-Path $negHome "err.txt"))) {
    if (Test-Path $f) { $combined += (Get-Content $f -Raw) + "`n" }
  }
  if ($p.ExitCode -eq 0) { Fail "truncated: --add exit 0 (should refuse)" }
  # digiemu refuses truncation with either "is truncated: it ends inside a
  # SysEx message" (identify path) or "is truncated or damaged: it holds N
  # data messages" (release path).
  if ($combined -notmatch 'truncated') {
    Write-Host ($combined | Select-Object -First 20)
    Fail "truncated: no truncation diagnostic in output"
  }
  $badSnaps = @(Get-ChildItem $negHome -Recurse -Filter "gui.snap" -ErrorAction SilentlyContinue)
  if ($badSnaps.Count -ne 0) { Fail "truncated: gui.snap written for damaged input" }
  Ok "truncated refused, no snapshot"
} finally {
  Remove-Item $negHome -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "BOOT-CHECK PASS"
