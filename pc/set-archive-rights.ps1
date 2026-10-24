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
#   - _verify\mac and _verify\lock: Modify inside them (the Mac's own log,
#     requests, lock), but the two folders themselves can't be deleted.
#   - _verify\pc: inheritance off (the rights there are kept, as its own),
#     then no writing and no deleting at all (spec P6).
# Before changing anything it saves today's rights of each folder it touches
# (and, for the archive, of every file under it) with icacls /save, into
# %LOCALAPPDATA%\Astro Import\rights-backup\, and prints how to put them back.
# It also says if the share itself gives that user Full Control: with it,
# the user could change the rights on the frames it filed (it owns them).
# The importer needs only Change.

param(
    [string]$Root = 'E:\Astro Image Data',
    [string]$ShareUser = 'astro',
    [switch]$Scratch,
    [switch]$Apply,
    [switch]$Undo
)
$ErrorActionPreference = 'Stop'
if ($Root.Length -gt 3) { $Root = $Root.TrimEnd('\') }   # a trailing \ breaks icacls' quoting
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
    # Windows can't list the group when it holds an account it no longer knows;
    # the group's own name, which depends on Windows' language, comes from its SID
    $group = (New-Object System.Security.Principal.SecurityIdentifier('S-1-5-32-544')).Translate([System.Security.Principal.NTAccount]).Value.Split('\')[-1]
    $admins = (& net.exe localgroup $group) -match ('^' + [regex]::Escape($ShareUser) + '$')
}
if ($admins) { Warn "'$ShareUser' is an administrator on this PC; the share's user should be an ordinary account. Not changing anything."; exit 1 }
Ok "Share user: $ShareUser ($sid)"

$isAdmin = (New-Object System.Security.Principal.WindowsPrincipal($me)).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
if ($Apply -and -not $isAdmin) { Warn "Open PowerShell as administrator for -Apply (right-click > Run as administrator)."; exit 1 }

# What the share itself allows. With Full Control there, the share's user
# could change the rights on the frames it filed (it owns them) and so undo
# this; Change is all the importer needs. Said, never changed here.
if (-not $Undo -and $isAdmin) {
    try {
        $wide = @{ $sid = $ShareUser; 'S-1-1-0' = 'Everyone'; 'S-1-5-11' = 'Authenticated Users'; 'S-1-5-32-545' = 'Users' }
        $full = @()
        $shares = Get-SmbShare -ErrorAction Stop | Where-Object {
            $_.Path -and ($Root + '\').StartsWith($_.Path.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase) }
        foreach ($sh in $shares) {
            foreach ($a in (Get-SmbShareAccess -Name $sh.Name -ErrorAction Stop)) {
                if ("$($a.AccessControlType)" -ne 'Allow' -or "$($a.AccessRight)" -ne 'Full') { continue }
                $asid = ''
                try { $asid = (New-Object System.Security.Principal.NTAccount($a.AccountName)).Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { }
                if ($wide.ContainsKey($asid)) { $full += [pscustomobject]@{ Share = $sh.Name; Account = $a.AccountName; Sid = $asid } }
            }
        }
        if ($full) {
            Warn "The share gives Full Control to: $(($full | ForEach-Object { "$($_.Account) on $($_.Share)" }) -join ', ')."
            Warn "With that, the share's user could change the rights on the frames it filed and undo this."
            Warn "The importer needs only Change. To set that for the share's user (PowerShell as administrator):"
            foreach ($f in ($full | Where-Object { $_.Sid -eq $sid })) {
                Warn "  Revoke-SmbShareAccess -Name '$($f.Share)' -AccountName '$($f.Account)' -Force"
                Warn "  Grant-SmbShareAccess -Name '$($f.Share)' -AccountName '$($f.Account)' -AccessRight Change -Force"
            }
            if ($full | Where-Object { $_.Sid -ne $sid }) {
                Warn "  and give Everyone, Authenticated Users or Users no more than Change on that share"
                Warn "  (check first that nothing else you use relies on Full Control there)."
            }
        } else {
            Ok "The share gives '$ShareUser' no more than Change"
        }
    } catch { Warn "Couldn't read the share's own permissions ($($_.Exception.Message))." }
}

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
        @{ Path = $mac;    Args = @('/remove:g', $u);                     Why = '_verify\mac: the extra rights off' },
        @{ Path = $lock;   Args = @('/remove:g', $u);                     Why = '_verify\lock: the extra rights off' },
        @{ Path = $pc;     Args = @('/remove:d', $u);                     Why = '_verify\pc: writing back as it was' },
        @{ Path = $pc;     Args = @('/inheritance:e');                    Why = '_verify\pc: inheritance on again' }
    )
} else {
    $steps = @(
        @{ Path = $tree;   Args = @('/deny', "${u}:(OI)(CI)(DE,DC)");     Why = 'the archive tree: no Delete, no Delete subfolders and files' },
        @{ Path = $verify; Args = @('/deny', "${u}:(OI)(NP)(WD,AD,WEA,WA)"); Why = '_verify itself: no new files, no writing to its files' },
        # Modify on everything inside (inherit-only), and on the folder itself
        # only list and add: a /deny there would also strip Delete from the grant
        @{ Path = $mac;    Args = @('/grant', "${u}:(OI)(CI)(IO)(M)");    Why = '_verify\mac: Modify on everything inside (the Mac''s log, requests, checks)' },
        @{ Path = $mac;    Args = @('/grant', "${u}:(RD,REA,RA,RC,S,X,WD,AD,WEA,WA)"); Why = '_verify\mac itself: list it and add to it, never delete it' },
        @{ Path = $lock;   Args = @('/grant', "${u}:(OI)(CI)(IO)(M)");    Why = '_verify\lock: Modify on everything inside (the ship lock)' },
        @{ Path = $lock;   Args = @('/grant', "${u}:(RD,REA,RA,RC,S,X,WD,AD,WEA,WA)"); Why = '_verify\lock itself: list it and add to it, never delete it' },
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
    # Windows PowerShell 5.1 stops a script on a program's error line once its
    # errors are redirected, and icacls prints one for each file it can't
    # read: so this one call runs under Continue, and its exit code decides
    $ErrorActionPreference = 'Continue'
    $said = & icacls.exe (Join-Path $tree '*') /save $all /t /c /q 2>&1
    $rc = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($rc -ne 0) {
        Warn "Some files' rights couldn't be saved (icacls: $(@($said | Select-Object -Last 1) -join ' '))."
        Warn "The five folders' rights are saved, and only those are changed here; carrying on."
    }
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
if (-not $Scratch -and -not $Undo) {
    # a folder that doesn't take rights from above doesn't get the new rule
    $alone = Get-ChildItem -LiteralPath $tree -Directory -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { -not $_.FullName.StartsWith($pc, [System.StringComparison]::OrdinalIgnoreCase) } |
        Where-Object { try { (Get-Acl -LiteralPath $_.FullName).AreAccessRulesProtected } catch { $false } } |
        Select-Object -First 20
    if ($alone) {
        Warn "These folders don't take rights from above, so the new rule doesn't reach them:"
        foreach ($d in $alone) { Warn "  $($d.FullName)" }
        Warn "Turn inheritance on for them (Properties > Security > Advanced), or tell Claude."
    } else {
        Ok "Every folder in the archive takes the new rule"
    }
}
Write-Host ""
if ($Undo) {
    Write-Host "This took off what -Apply added. Today's -Apply printed the exact way back as well (icacls /restore)." -ForegroundColor White
}
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
