# install-windows.ps1  —  BrettjoAstro FITS Importer for Windows 11 (1.5.0)
#
# The Windows counterpart of install-scripts.sh. Run it from the unzipped
# folder (double-click "Install on Windows.cmd", or in PowerShell):
#
#   powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
#
# No administrator rights needed. It:
#   1. finds Python 3 (python.org) and installs astropy for it if missing
#   2. copies the engine, panel and watcher to %LOCALAPPDATA%\BrettjoAstro\bin
#   3. writes a starter config.json (only if you have none) — the archive
#      E:\Astro Image Data is filled in when that folder exists
#   4. starts the camera watcher now and at every logon (Startup folder)
#   5. puts "Restart FITS Importer" on your Desktop
#   6. schedules the twice-daily ship (09:30, 21:30) when an archive is set
#   7. on the archive PC (1.7.0): the archive's _verify\pc, _verify\mac and
#      _verify\lock folders, the sweep at logon and 03:30, and every five
#      minutes the answer to what the Mac asks for - all in Python, as you
# Your ledger, config and backed-up frames are never touched.
# While the FITs Importer App is in charge here (1.5.3), only the files are
# updated: no watcher, Restart button or panel start (4, 5 and the start).

param([switch]$NoStart)
# 'Continue', not 'Stop': in Windows PowerShell 5.1 a native program writing
# to stderr (pip, a Python traceback) would otherwise abort the installer.
# Cmdlets that must succeed say -ErrorAction Stop themselves.
$ErrorActionPreference = 'Continue'
# read what Python prints as UTF-8 (a user folder like "Zoë" would otherwise
# arrive garbled from the console code page)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Info($m) { Write-Host "  ->  $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "  !!  $m" -ForegroundColor Yellow }
function Utf8NoBom($path, $text) {
    [System.IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding $false))
}

Write-Host ""
Write-Host "BrettjoAstro FITS Importer - Windows installer" -ForegroundColor White
Write-Host ""

# ── 1. Python ────────────────────────────────────────────────────────────────
Info "Looking for Python 3..."
$py = $null
foreach ($cand in @(@('py', '-3'), @('python'))) {
    try {
        $exe = $cand[0]; $rest = @($cand | Select-Object -Skip 1)
        $out = & $exe @rest -X utf8 -c "import sys; print(sys.executable); print(sys.version_info >= (3, 9))" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out -and $out[1] -eq 'True' -and $out[0] -notlike '*WindowsApps*') {
            $py = $out[0].Trim(); break
        }
    } catch { }
}
if (-not $py) {
    Warn "Python 3.9 or newer was not found."
    Warn "Install it from https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH'),"
    Warn "then run this installer again."
    exit 1
}
$pyw = Join-Path (Split-Path -Parent $py) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pyw)) { $pyw = $py }
Ok "Python: $py"

& $py -c "import astropy" 2>$null
if ($LASTEXITCODE -ne 0) {
    Info "Installing astropy (the FITS reader) for this Python..."
    & $py -m pip install --user --disable-pip-version-check astropy
    if ($LASTEXITCODE -ne 0) { Warn "pip could not install astropy - run this in Terminal (PowerShell):  & `"$py`" -m pip install --user astropy"; exit 1 }
}
Ok "astropy is installed"

# ── 2. Files ─────────────────────────────────────────────────────────────────
$bin = Join-Path $env:LOCALAPPDATA 'BrettjoAstro\bin'
New-Item -ItemType Directory -Force -Path $bin -ErrorAction Stop | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $bin 'pc') -ErrorAction Stop | Out-Null

foreach ($f in @('astro-import.py', 'astro-app.py', 'astro-watch.py', 'selftest.py')) {
    $src = Join-Path $here $f
    if (-not (Test-Path -LiteralPath $src)) { Warn "Missing from the package: $f"; exit 1 }
    Copy-Item -LiteralPath $src -Destination $bin -Force -ErrorAction Stop
}
foreach ($f in @('set-archive-rights.ps1')) {
    $src = Join-Path $here "pc\$f"
    if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $bin 'pc') -Force }
}
# sweep.ps1 retired in 1.7.0: the sweep is Python now (--sweep)
foreach ($f in @('sweep.ps1', 'install_sweep.ps1')) {
    $old = Join-Path $bin "pc\$f"
    if (Test-Path -LiteralPath $old) { Rename-Item -LiteralPath $old -NewName "$f.retired-$(Get-Date -Format 'yyyyMMdd_HHmmss')" -ErrorAction SilentlyContinue }
}
Ok "Engine, panel and watcher copied to $bin"

# Who is in charge here, the web version or the FITs Importer App (1.5.3)?
# While the app is, only files are updated: it runs its own watcher and panel.
# >>> app-owner check (test_v2 runs this block on its own on Windows, with a fake engine)
$owner = & $py -X utf8 "$bin\astro-import.py" --app-owner 2>$null
$ownerRc = $LASTEXITCODE
$appOwns = $ownerRc -eq 0 -and "$owner" -like 'app *'
if ($appOwns) {
    Info "The FITs Importer App is in charge here ($($owner -replace '^app ')): files updated only - no watcher, panel or Restart button"
} elseif ($ownerRc -eq 2 -and "$owner" -like 'stale *') {
    # the app was removed without handing back: the web version takes over again
    $archived = & $py -X utf8 "$bin\astro-import.py" --app-owner --archive-stale 2>$null
    if ($LASTEXITCODE -eq 0) {
        Ok "The FITs Importer App is gone: the web version is back in charge ($archived)"
    } else {
        Warn "The FITs Importer App is gone, but its record could not be set aside - the web version runs anyway"
    }
}
# <<< app-owner check

# stop a running panel / watcher so the new build is picked up: only the web
# version's own (bin\), never the app's
if (-not $appOwns) {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -and $_.CommandLine -match ([regex]::Escape("$env:LOCALAPPDATA\BrettjoAstro\bin\") + 'astro-(app|watch)\.py') } |
        ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; Info "Stopped the running $($_.Name) ($($_.ProcessId))" } catch { } }
}

# ── 3. Config (never overwritten) ────────────────────────────────────────────
$state = Join-Path $env:LOCALAPPDATA 'Astro Import'
New-Item -ItemType Directory -Force -Path $state -ErrorAction Stop | Out-Null
$cfg = Join-Path $state 'config.json'
$archive = 'E:\Astro Image Data'
if (-not (Test-Path -LiteralPath $cfg)) {
    $c = [ordered]@{ '//' = 'BrettjoAstro FITS Importer (Windows). Edit freely; see config.example.json for every setting.' }
    if (Test-Path -LiteralPath $archive) {
        $c['ASTRO_ARCHIVE_MOUNT'] = $archive
        $c['ASTRO_ARCHIVE_LABEL'] = $archive
    }
    Utf8NoBom $cfg ($c | ConvertTo-Json)
    Ok "Starter config written: $cfg"
} else {
    Ok "Config kept: $cfg"
}
$archiveSet = $false
try {
    $cj = Get-Content -LiteralPath $cfg -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($cj.ASTRO_ARCHIVE_MOUNT -and (Test-Path -LiteralPath $cj.ASTRO_ARCHIVE_MOUNT)) { $archiveSet = $true; $archive = $cj.ASTRO_ARCHIVE_MOUNT }
} catch { Warn "config.json does not parse - check it: $cfg" }

# ── 4. Watcher at logon (Startup folder shortcut — no admin needed) ──────────
$wsh = New-Object -ComObject WScript.Shell
$startup = [Environment]::GetFolderPath('Startup')
$lnk = $wsh.CreateShortcut((Join-Path $startup 'BrettjoAstro FITS Importer watcher.lnk'))
$lnk.TargetPath = $pyw
$lnk.Arguments = "-X utf8 `"$bin\astro-watch.py`""
$lnk.WorkingDirectory = $bin
$lnk.Description = 'Opens the FITS Importer when a Seestar or ASIAir is plugged in'
if (-not $appOwns) {
    $lnk.Save()
    Ok "Camera watcher starts at every logon"
}

# ── 5. Desktop restart button ────────────────────────────────────────────────
$desktop = [Environment]::GetFolderPath('Desktop')
$restart = @"
@echo off
rem BrettjoAstro FITS Importer - restart the control panel (Windows)
rem app-owner check: begin
"$py" -X utf8 "%LOCALAPPDATA%\BrettjoAstro\bin\astro-import.py" --app-owner >nul 2>&1
if %errorlevel% equ 0 (
    echo The FITs Importer App is in charge here: open it instead. You can close this window.
    timeout /t 8 >nul
    exit /b 0
)
rem app-owner check: end
echo Restarting the FITS Importer panel...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { `$_.Name -match '^pythonw?\.exe$' -and `$_.CommandLine -match ([regex]::Escape(`$env:LOCALAPPDATA + '\BrettjoAstro\bin\') + 'astro-app\.py') } | ForEach-Object { Stop-Process -Id `$_.ProcessId -Force }"
timeout /t 1 /nobreak >nul
start "" "$pyw" -X utf8 "%LOCALAPPDATA%\BrettjoAstro\bin\astro-app.py" --no-browser
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8765"
echo Done - the panel is open in your browser. You can close this window.
"@
# cmd.exe reads batch files in the OEM code page — write it that way, so a
# Python path with an accented user name survives
$oem = [System.Text.Encoding]::GetEncoding([System.Globalization.CultureInfo]::CurrentCulture.TextInfo.OEMCodePage)
if (-not $appOwns) {
    [System.IO.File]::WriteAllText((Join-Path $desktop 'Restart FITS Importer.cmd'), ($restart -replace "`r?`n", "`r`n"), $oem)
    Ok "Restart FITS Importer is on your Desktop"
}

# ── 6. Twice-daily ship (only with an archive) ───────────────────────────────
$shipTask = 'BrettjoAstro FITS Importer ship'
if ($archiveSet) {
    try {
        $act = New-ScheduledTaskAction -Execute $pyw -Argument "-X utf8 `"$bin\astro-import.py`" --ship" -WorkingDirectory $bin
        # half an hour after the Mac's 09:00 / 21:00: the two never race
        # (the archive's ship lock would stop that anyway)
        $t1 = New-ScheduledTaskTrigger -Daily -At 09:30
        $t2 = New-ScheduledTaskTrigger -Daily -At 21:30
        $set = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 6) -MultipleInstances IgnoreNew
        $pri = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
        Register-ScheduledTask -TaskName $shipTask -Action $act -Trigger @($t1, $t2) -Settings $set -Principal $pri -Force -ErrorAction Stop | Out-Null
        Ok "Ship scheduled at 09:30 and 21:30 (files verified frames into $archive)"
    } catch {
        Warn "Could not schedule the ship ($($_.Exception.Message)). Imports still ship straight after each import."
    }
} else {
    Info "No archive folder configured - skipping the ship schedule (optional; see PC-SYNC.md)."
}

# ── 7. The archive PC's own jobs (1.7.0): Python, as you ────────────────────
# "Astro archive sweep" (logon and 03:30) checks every shipped frame from this
# disk, sets aside copies a ship never finished, lists the archive and hashes
# new files. "Astro sync requests" (every 5 minutes) answers what the Mac asks
# for and keeps the heartbeat that tells it this PC is awake. Registering the
# sweep under its old name replaces the old sweep.ps1 task; the old script
# files are left where they are (they are yours to delete).
if ($archiveSet) {
    $made = $true
    foreach ($d in @('_verify\pc', '_verify\mac\requests', '_verify\lock', '_Quarantine\ship-incomplete')) {
        try { New-Item -ItemType Directory -Force -Path (Join-Path $archive $d) -ErrorAction Stop | Out-Null }
        catch { $made = $false; Warn "Could not create $archive\$d ($($_.Exception.Message))" }
    }
    if ($made) { Ok "The archive's _verify\pc, _verify\mac and _verify\lock folders are in place" }
    $me = "$env:USERDOMAIN\$env:USERNAME"
    $pri = New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Limited
    try {
        $act = New-ScheduledTaskAction -Execute $pyw -Argument "-X utf8 `"$bin\astro-import.py`" --pc-nightly" -WorkingDirectory $bin
        $t1 = New-ScheduledTaskTrigger -AtLogOn -User $me
        $t2 = New-ScheduledTaskTrigger -Daily -At 03:30
        $set = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 8) -MultipleInstances IgnoreNew
        Register-ScheduledTask -TaskName 'Astro archive sweep' -Action $act -Trigger @($t1, $t2) -Settings $set -Principal $pri -Force -ErrorAction Stop | Out-Null
        Ok "Archive sweep at logon and 03:30 (Python: sweep, list the archive, hash new files)"
    } catch {
        Warn "Could not set up the 'Astro archive sweep' task ($($_.Exception.Message))."
        Warn "If an older one was set up from an administrator prompt, open PowerShell as administrator, run:"
        Warn "  Unregister-ScheduledTask -TaskName 'Astro archive sweep' -Confirm:`$false"
        Warn "then run this installer again."
    }
    try {
        $act = New-ScheduledTaskAction -Execute $pyw -Argument "-X utf8 `"$bin\astro-import.py`" --pc-tick" -WorkingDirectory $bin
        # every 5 minutes, all day, every day: a daily trigger that repeats
        $t = New-ScheduledTaskTrigger -Daily -At 00:00
        $t.Repetition = (New-ScheduledTaskTrigger -Once -At 00:00 -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
        $t1 = New-ScheduledTaskTrigger -AtLogOn -User $me
        # light work, so it runs on a UPS's battery too: the Mac keeps seeing the heartbeat
        $set = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName 'Astro sync requests' -Action $act -Trigger @($t, $t1) -Settings $set -Principal $pri -Force -ErrorAction Stop | Out-Null
        Ok "Sync requests answered every 5 minutes (the Mac sees this PC is awake)"
    } catch {
        Warn "Could not set up the 'Astro sync requests' task ($($_.Exception.Message))."
    }
}

# ── 8. Start ─────────────────────────────────────────────────────────────────
if (-not $NoStart -and -not $appOwns) {
    Start-Process -FilePath $pyw -ArgumentList @('-X', 'utf8', "`"$bin\astro-watch.py`"") -WorkingDirectory $bin -WindowStyle Hidden
    Start-Process -FilePath $pyw -ArgumentList @('-X', 'utf8', "`"$bin\astro-app.py`"", '--no-browser') -WorkingDirectory $bin -WindowStyle Hidden
    Start-Sleep -Seconds 2
    Start-Process 'http://127.0.0.1:8765'
    Ok "Watcher and panel started"
}

$ver = & $py -X utf8 "$bin\astro-import.py" --version 2>$null
Write-Host ""
Write-Host "All done: $ver" -ForegroundColor Green
Write-Host ""
if (-not $appOwns) {
    Write-Host "Next:" -ForegroundColor White
    Write-Host "  1. Plug in your Seestar or ASIAir - the panel opens by itself (http://127.0.0.1:8765)."
    Write-Host "  2. Tick what you want and press Import. The first import starts this PC's ledger."
    Write-Host "  3. Check the install any time (in Terminal):  & `"$py`" -X utf8 `"$bin\selftest.py`""
} else {
    Write-Host "Open the FITs Importer App to import: it handles the cameras on this PC." -ForegroundColor White
}
Write-Host ""
Write-Host "Frames go to $env:USERPROFILE\Documents\Astro (your C: workbench); the ledger lives in $state."
if ($archiveSet) { Write-Host "Verified frames are filed into the archive at $archive." }
Write-Host ""
