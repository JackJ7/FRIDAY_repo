# Make FRIDAY launch on login (current user only; no admin needed).
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File scripts\enable_autostart.ps1

$root = Split-Path -Parent $PSScriptRoot          # the FRIDAY folder
$pythonw = Join-Path (Split-Path (Get-Command python).Source) "pythonw.exe"
$launcher = Join-Path $root "friday_app.py"

# pythonw.exe = python without a console window; FRIDAY lives in the tray.
$command = "`"$pythonw`" `"$launcher`""
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" `
                 -Name "FRIDAY" -Value $command

Write-Host "FRIDAY will now start on login:"
Write-Host "  $command"
Write-Host "Undo with: scripts\disable_autostart.ps1"
