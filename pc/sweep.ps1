# sweep.ps1  —  the PC's side of the Mac -> archive handshake (1.4.0). Read-only.
#
# Each importer's --ship copies frames into the archive and appends one line per
# file to its own _verify\shipped*.jsonl (Mac: shipped.jsonl; PC: shipped-pc.jsonl). This sweep re-hashes each of those files from E: in
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
# Every machine that ships writes its OWN log (the Mac: shipped.jsonl, the
# PC's importer: shipped-pc.jsonl — 1.5.0); the sweep reads them all.
$shippedLogs = @(Get-ChildItem -LiteralPath $v -Filter 'shipped*.jsonl' -File -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$verified = Join-Path $v 'verified.jsonl'
$problems = Join-Path $v 'problems.jsonl'
$status   = Join-Path $v 'status.json'
$log      = Join-Path $v ('sweep_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log')
$now = Get-Date -Format 'yyyy-MM-ddTHHmmss'

function ReadJsonl($path) {
    # shared read (ReadWrite): an importer appending right now must never be
    # locked out of its own log; a List, not +=, so big logs stay fast
    $out = New-Object System.Collections.Generic.List[object]
    if (Test-Path -LiteralPath $path) {
        $fs = [System.IO.File]::Open($path, 'Open', 'Read', 'ReadWrite')
        $sr = New-Object System.IO.StreamReader($fs, (New-Object System.Text.UTF8Encoding $false))
        try {
            while ($null -ne ($line = $sr.ReadLine())) {
                if ($line.Trim().Length -eq 0) { continue }
                try { $out.Add(($line | ConvertFrom-Json)) } catch { }
            }
        } finally { $sr.Close() }
    }
    return ,$out
}
function AppendJsonl($path, $obj) {
    # UTF-8 always (Windows PowerShell's Add-Content writes ANSI, which the
    # importer then cannot read back for a name like "Cœur")
    [System.IO.File]::AppendAllText($path, (($obj | ConvertTo-Json -Compress) + "`r`n"), (New-Object System.Text.UTF8Encoding $false))
}
$done = @{}
foreach ($r in (ReadJsonl $verified)) { if ($r.relpath -is [string]) { $done[$r.relpath.ToLowerInvariant()] = $true } }
$bad  = @{}
foreach ($r in (ReadJsonl $problems)) { if ($r.relpath -is [string]) { $bad[$r.relpath.ToLowerInvariant()] = $true } }
$sep = [System.IO.Path]::DirectorySeparatorChar
$rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/') + $sep
$todo = @()
$seen = @{}
$shippedRows = New-Object System.Collections.Generic.List[object]
foreach ($sl in $shippedLogs) { foreach ($x in (ReadJsonl $sl)) { $shippedRows.Add($x) } }
foreach ($r in $shippedRows) {
    # a malformed row never stops the sweep (it would stop EVERY sweep —
    # the logs are append-only)
    if (-not ($r.relpath -is [string]) -or $r.relpath.Length -eq 0) { continue }
    [int64]$chk = 0
    if (-not [int64]::TryParse([string]$r.size, [ref]$chk)) { continue }
    $k = $r.relpath.ToLowerInvariant()
    if ($done.ContainsKey($k) -or $bad.ContainsKey($k) -or $seen.ContainsKey($k)) { continue }
    $seen[$k] = $true; $todo += $r
}
$sha = [System.Security.Cryptography.SHA256]::Create()
$ok = 0; $fail = 0; $missing = 0; $i = 0
$lines = @("sweep $now  root=$Root  pending=$($todo.Count)")
foreach ($r in $todo) {
    $i++
    # a relpath must stay inside the archive ("..\" never walks out), and a
    # name Windows can't parse is a problem line, never the end of the sweep
    $p = $null; $full = $null
    try { $p = Join-Path $Root $r.relpath; $full = [System.IO.Path]::GetFullPath($p) } catch { $full = $null }
    if (-not $full -or -not $full.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        $fail++
        AppendJsonl $problems (@{relpath=$r.relpath; sha256=$r.sha256; size=$r.size; problem='outside archive'; at=$now})
        $lines += "OUTSIDE  $($r.relpath)"; continue
    }
    if (-not (Test-Path -LiteralPath $p)) {
        $missing++
        AppendJsonl $problems (@{relpath=$r.relpath; sha256=$r.sha256; size=$r.size; problem='missing'; at=$now})
        $lines += "MISSING  $($r.relpath)"; continue
    }
    [int64]$sz = 0
    [void][int64]::TryParse([string]$r.size, [ref]$sz)
    $fi = Get-Item -LiteralPath $p
    if ([int64]$fi.Length -ne $sz) {
        $fail++
        AppendJsonl $problems (@{relpath=$r.relpath; sha256=$r.sha256; size=$r.size; problem="size $($fi.Length)"; at=$now})
        $lines += "BADSIZE  $($r.relpath)"; continue
    }
    $fs = [System.IO.File]::Open($p, 'Open', 'Read', 'Read')
    try { $h = ($sha.ComputeHash($fs) | ForEach-Object { $_.ToString('x2') }) -join '' } finally { $fs.Close() }
    if ($r.sha256 -and $h -ne $r.sha256) {
        $fail++
        AppendJsonl $problems (@{relpath=$r.relpath; sha256=$r.sha256; found=$h; size=$r.size; problem='hash'; at=$now})
        $lines += "BADHASH  $($r.relpath)"; continue
    }
    $ok++
    AppendJsonl $verified (@{relpath=$r.relpath; sha256=$h; size=$sz; verifiedAt=$now})
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
