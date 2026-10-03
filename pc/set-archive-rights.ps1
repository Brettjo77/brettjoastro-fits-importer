# set-archive-rights.ps1  —  the archive share's rights for 1.7.0 (decision D7)
#
# Run on the archive PC, in PowerShell opened as administrator. Without
# -Apply it only shows what it would do. It never deletes a file.
#
#   1. A test folder first (nothing else on the archive changes):
#        powershell -ExecutionPolicy Bypass -File .\set-archive-rights.ps1 -Scratch -Apply
#      then on the Mac, in Terminal:
#        /usr/local/bin/python3 ~/bin/astro-import.py --check-share-rights
#   2. Once the Mac says every answer is right, the archive itself:
#        powershell -ExecutionPolicy Bypass -File .\set-archive-rights.ps1 -Apply
#   3. To take the new rights off again:
#        powershell -ExecutionPolicy Bypass -File .\set-archive-rights.ps1 -Undo -Apply
#
# What it changes, for the share's user only (-ShareUser, 'astro' unless you
# name another; never a password), and nothing for anyone else:
#   - the archive tree: no Delete and no "Delete subfolders and files". The
#     share can still add new files and folders; the importer never writes
#     over an existing file.
#   - _verify itself: no new files, and no writing to the files there.
#   - _verify\mac and _verify\lock: Modify (the Mac's own log, requests, lock).
#   - _verify\pc: inheritance off (the rights there are kept, as its own),
#     then no writing and no deleting at all (spec P6).
# Before changing anything it saves today's rights of each folder it touches
# (and, for the archive, of every file under it) with icacls /save, into
# %LOCALAPPDATA%\Astro Import\rights-backup\, and prints how to put them back.

param(
    [string]$Root = 'E:\Astro Image Data',
    [string]$ShareUser = 'astro',
    [switch]$Scratch,
    [switch]$Apply,
    [switch]$Undo
)
$ErrorActionPreference = 'Stop'
function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Info($m) { Write-Host "  ->  $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "  !!  $m" -ForegroundColor Yellow }

Write-Host ""
Write-Host "Archive share rights (D7)$(if ($Scratch) { ' - test folder only' })$(if ($Undo) { ' - taking them off' })" -ForegroundColor White
Write-Host ""

if (-not (Test-Path -LiteralPath $Root -PathType Container)) { Warn "No archive folder at $Root (use -Root)."; exit 1 }

# the share's user, by its SID: it must be a local account that is neither you
# nor a group, or this would take Delete away from everyone
try {
    $sid = (New-Object System.Security.Principal.NTAccount($ShareUser)).Translate([System.Security.Principal.SecurityIdentifier]).Value
} catch { Warn "There is no account called '$ShareUser' on this PC (use -ShareUser)."; exit 1 }
$me = [System.Security.Principal.WindowsIdentity]::GetCurrent()
if ($sid -eq $me.User.Value) { Warn "'$ShareUser' is the account you are signed in with. Name the share's own user."; exit 1 }
$local = $null
try { $local = Get-LocalUser -ErrorAction Stop | Where-Object { $_.SID.Value -eq $sid } } catch { }
if (-not $local) { Warn "'$ShareUser' is not a local user account on this PC (a group, or a domain account). Not changing anything."; exit 1 }
$admins = $null
try {
    $admins = Get-LocalGroupMember -SID 'S-1-5-32-544' -ErrorAction Stop | Where-Object { $_.SID.Value -eq $sid }
} catch {
    # Windows can't list the group when it holds an account it no longer knows
    $admins = (& net.exe localgroup Administrators) -match ('^' + [regex]::Escape($ShareUser) + '$')
}
if ($admins) { Warn "'$ShareUser' is an administrator on this PC; the share's user should be an ordinary account. Not changing anything."; exit 1 }
Ok "Share user: $ShareUser ($sid)"

$isAdmin = (New-Object System.Security.Principal.WindowsPrincipal($me)).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
if ($Apply -and -not $isAdmin) { Warn "Open PowerShell as administrator for -Apply (right-click > Run as administrator)."; exit 1 }

# where: the archive itself, or the test folder laid out like it
if ($Scratch) {
    $tree = Join-Path $Root '_rights-check'
    $verify = Join-Path $tree '_verify'
} else {
    $tree = $Root
    $verify = Join-Path $Root '_verify'
}
$mac = Join-Path $verify 'mac'
$lock = Join-Path $verify 'lock'
$pc = Join-Path $verify 'pc'
$u = "*$sid"

# the icacls steps, in order; each one is shown before it runs
if ($Undo) {
    $steps = @(
        @{ Path = $tree;   Args = @('/remove:d', $u);                     Why = 'the archive tree: Delete back as it was' },
        @{ Path = $verify; Args = @('/remove:d', $u);                     Why = '_verify: writing back as it was' },
        @{ Path = $mac;    Args = @('/remove:g', $u);                     Why = '_verify\mac: the extra Modify off' },
        @{ Path = $lock;   Args = @('/remove:g', $u);                     Why = '_verify\lock: the extra Modify off' },
        @{ Path = $pc;     Args = @('/remove:d', $u);                     Why = '_verify\pc: writing back as it was' },
        @{ Path = $pc;     Args = @('/inheritance:e');                    Why = '_verify\pc: inheritance on again' }
    )
} else {
    $steps = @(
        @{ Path = $tree;   Args = @('/deny', "${u}:(OI)(CI)(DE,DC)");     Why = 'the archive tree: no Delete, no Delete subfolders and files' },
        @{ Path = $verify; Args = @('/deny', "${u}:(OI)(NP)(WD,AD,WEA,WA)"); Why = '_verify itself: no new files, no writing to its files' },
        @{ Path = $mac;    Args = @('/grant', "${u}:(OI)(CI)(M)");        Why = '_verify\mac: Modify (the Mac''s log, requests, lock checks)' },
        @{ Path = $lock;   Args = @('/grant', "${u}:(OI)(CI)(M)");        Why = '_verify\lock: Modify (the ship lock)' },
        @{ Path = $pc;     Args = @('/inheritance:d');                    Why = '_verify\pc: inheritance off, today''s rights kept as its own' },
        @{ Path = $pc;     Args = @('/deny', "${u}:(OI)(CI)(WD,AD,WEA,WA,DE,DC)"); Why = '_verify\pc: no writing, no deleting (P6)' }
    )
}
foreach ($s in $steps) { Info "$($s.Why)`n          icacls `"$($s.Path)`" $($s.Args -join ' ')" }
if (-not $Apply) {
    Write-Host ""
    Write-Host "Nothing changed. Add -Apply to do this (PowerShell as administrator)." -ForegroundColor White
    Write-Host ""
    exit 0
}

# the folders, and in the test folder the PC's own test files
foreach ($d in @($tree, $verify, $mac, (Join-Path $mac 'requests'), $lock, $pc)) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
if ($Scratch -and -not $Undo) {
    New-Item -ItemType Directory -Force -Path (Join-Path $tree 'tree') | Out-Null
    foreach ($f in @((Join-Path $tree 'tree\canary.fit'), (Join-Path $verify 'canary.jsonl'), (Join-Path $pc 'canary.json'))) {
        if (-not (Test-Path -LiteralPath $f)) { [System.IO.File]::WriteAllText($f, "rights check: made by the PC`r`n") }
    }
}

# today's rights first
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = Join-Path $env:LOCALAPPDATA "Astro Import\rights-backup\$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$restore = @()
$n = 0
foreach ($d in @($tree, $verify, $mac, $lock, $pc)) {
    $n++
    $file = Join-Path $backup ("folder-$n.acl")
    & icacls.exe $d /save $file /c | Out-Null
    if ($LASTEXITCODE -ne 0) { Warn "Could not save the rights of $d - nothing changed."; exit 1 }
    $restore += "icacls `"$(Split-Path -Parent $d)`" /restore `"$file`""
}
if (-not $Scratch -and -not $Undo) {
    Info "Saving the rights of every file under $tree (a minute or two)..."
    $all = Join-Path $backup 'archive-all.acl'
    & icacls.exe (Join-Path $tree '*') /save $all /t /c /q 2>$null | Out-Null
    $restore += "icacls `"$tree`" /restore `"$all`""
}
Ok "Today's rights saved in $backup"

foreach ($s in $steps) {
    & icacls.exe $s.Path @($s.Args) /q | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Warn "icacls stopped at: $($s.Why). Rights now are part-way; to put back what was there:"
        foreach ($r in $restore) { Warn "  $r" }
        exit 1
    }
    Ok $s.Why
}

Write-Host ""
foreach ($d in @($tree, $verify, $mac, $lock, $pc)) {
    Write-Host $d -ForegroundColor White
    & icacls.exe $d | Where-Object { $_ -match [regex]::Escape($ShareUser) -or $_ -match [regex]::Escape($sid) } | ForEach-Object { Write-Host "    $_" }
}
Write-Host ""
Write-Host "To put back exactly what was there before (PowerShell as administrator):" -ForegroundColor White
foreach ($r in $restore) { Write-Host "  $r" }
Write-Host ""
if ($Scratch -and -not $Undo) {
    Write-Host "Next, on the Mac (share mounted), in Terminal:" -ForegroundColor White
    Write-Host "  /usr/local/bin/python3 ~/bin/astro-import.py --check-share-rights"
    Write-Host "When you're done with it, delete $tree yourself."
} elseif (-not $Undo) {
    Write-Host "Next, on the Mac: ship as usual. The first ship's log line says if anything is refused." -ForegroundColor White
}
Write-Host ""
