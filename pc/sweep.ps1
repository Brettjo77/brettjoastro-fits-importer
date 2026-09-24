# sweep.ps1  —  the PC's side of the Mac -> archive handshake (1.4.0). Read-only.
#
# The Mac's --ship copies frames into the archive and appends one line per file
# to _verify\shipped.jsonl. This sweep re-hashes each of those files from E: in
# a fresh process (not the SMB client's cache) and appends the ones that match
# to _verify\verified.jsonl, which the Mac reads on its next --ship to stamp the
# ledger. Mismatches go to _verify\problems.jsonl and are never silently
# retried. A status.json summarises the state for anything that wants to show
# it. Nothing is moved, renamed or deleted.
#
#   powershell -ExecutionPolicy Bypass -File .\sweep.ps1 [-Root "E:\Astro Image Data"]

param([string]$Root = 'E:\Astro Image Data')
$ErrorActionPreference = 'Stop'
$v = Join-Path $Root '_verify'
if (-not (Test-Path -LiteralPath $v)) { New-Item -ItemType Directory -Path $v | Out-Null }
$shipped  = Join-Path $v 'shipped.jsonl'
$verified = Join-Path $v 'verified.jsonl'
$problems = Join-Path $v 'problems.jsonl'
$status   = Join-Path $v 'status.json'
$log      = Join-Path $v ('sweep_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log')
$now = Get-Date -Format 'yyyy-MM-ddTHHmmss'

function ReadJsonl($path) {
    $out = @()
    if (Test-Path -LiteralPath $path) {
        foreach ($line in [System.IO.File]::ReadLines($path)) {
            if ($line.Trim().Length -eq 0) { continue }
            try { $out += ($line | ConvertFrom-Json) } catch { }
        }
    }
    return $out
}
$done = @{}
foreach ($r in (ReadJsonl $verified)) { $done[$r.relpath.ToLowerInvariant()] = $true }
$bad  = @{}
foreach ($r in (ReadJsonl $problems)) { $bad[$r.relpath.ToLowerInvariant()] = $true }
$todo = @()
$seen = @{}
foreach ($r in (ReadJsonl $shipped)) {
    $k = $r.relpath.ToLowerInvariant()
    if ($done.ContainsKey($k) -or $bad.ContainsKey($k) -or $seen.ContainsKey($k)) { continue }
    $seen[$k] = $true; $todo += $r
}
$sha = [System.Security.Cryptography.SHA256]::Create()
$ok = 0; $fail = 0; $missing = 0; $i = 0
$lines = @("sweep $now  root=$Root  pending=$($todo.Count)")
foreach ($r in $todo) {
    $i++
    $p = Join-Path $Root $r.relpath
    if (-not (Test-Path -LiteralPath $p)) {
        $missing++
        Add-Content -LiteralPath $problems -Value (@{relpath=$r.relpath; sha256=$r.sha256; size=$r.size; problem='missing'; at=$now} | ConvertTo-Json -Compress)
        $lines += "MISSING  $($r.relpath)"; continue
    }
    $fi = Get-Item -LiteralPath $p
    if ([int64]$fi.Length -ne [int64]$r.size) {
        $fail++
        Add-Content -LiteralPath $problems -Value (@{relpath=$r.relpath; sha256=$r.sha256; size=$r.size; problem="size $($fi.Length)"; at=$now} | ConvertTo-Json -Compress)
        $lines += "BADSIZE  $($r.relpath)"; continue
    }
    $fs = [System.IO.File]::Open($p, 'Open', 'Read', 'Read')
    try { $h = ($sha.ComputeHash($fs) | ForEach-Object { $_.ToString('x2') }) -join '' } finally { $fs.Close() }
    if ($r.sha256 -and $h -ne $r.sha256) {
        $fail++
        Add-Content -LiteralPath $problems -Value (@{relpath=$r.relpath; sha256=$r.sha256; found=$h; size=$r.size; problem='hash'; at=$now} | ConvertTo-Json -Compress)
        $lines += "BADHASH  $($r.relpath)"; continue
    }
    $ok++
    Add-Content -LiteralPath $verified -Value (@{relpath=$r.relpath; sha256=$h; size=$r.size; verifiedAt=$now} | ConvertTo-Json -Compress)
    if ($i % 200 -eq 0) { Write-Output "  $i / $($todo.Count)" }
}
$totalVerified = (ReadJsonl $verified).Count
$totalProblems = (ReadJsonl $problems).Count
$st = @{ sweptAt=$now; verifiedThisRun=$ok; failedThisRun=$fail; missingThisRun=$missing;
         pendingBefore=$todo.Count; totalVerified=$totalVerified; totalProblems=$totalProblems }
$st | ConvertTo-Json | Set-Content -LiteralPath $status -Encoding UTF8
$lines += "verified $ok   failed $fail   missing $missing   total verified $totalVerified   total problems $totalProblems"
$lines | Set-Content -LiteralPath $log -Encoding UTF8
$lines | Write-Output
if ($fail -gt 0 -or $missing -gt 0) { Write-Output "ATTENTION: see $problems" }
