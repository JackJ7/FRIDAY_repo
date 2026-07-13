# Stop FRIDAY from launching on login.
# Run:  powershell -ExecutionPolicy Bypass -File scripts\disable_autostart.ps1

Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" `
                    -Name "FRIDAY" -ErrorAction SilentlyContinue
Write-Host "FRIDAY autostart removed."
