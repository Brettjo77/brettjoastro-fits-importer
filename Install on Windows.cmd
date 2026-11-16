@echo off
rem BrettjoAstro FITS Importer - double-click to install or update on Windows.
rem Started from a PowerShell 7 window, Windows PowerShell would inherit its module
rem path and lose some of its own commands (1.10.1): let it work out its own.
set "PSModulePath="
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-windows.ps1"
echo.
pause