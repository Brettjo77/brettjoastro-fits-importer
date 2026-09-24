# install_sweep.ps1  —  run once on the archive PC (no administrator rights needed).
# Registers the sweep as a scheduled task: at every logon and daily at 03:30,
# running as you, so the archive's verification keeps up with the Mac's
# shipping without anyone remembering to run it.
#
#   powershell -ExecutionPolicy Bypass -File .\install_sweep.ps1

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $here 'sweep.ps1'
if (-not (Test-Path -LiteralPath $script)) { throw "sweep.ps1 not found next to this installer" }
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$t1 = New-ScheduledTaskTrigger -AtLogOn
$t2 = New-ScheduledTaskTrigger -Daily -At 03:30
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable:$false -ExecutionTimeLimit (New-TimeSpan -Hours 6) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'Astro archive sweep' -Action $action -Trigger @($t1, $t2) -Settings $settings -Principal $principal -Force | Out-Null
Write-Output "Registered 'Astro archive sweep' (at logon and daily 03:30). Run it now with:"
Write-Output "  Start-ScheduledTask -TaskName 'Astro archive sweep'"
