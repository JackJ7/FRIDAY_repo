# FRIDAY regression suite — PowerShell wrapper.
#   .\run_suite.ps1            # full overnight run (both pillars)
#   .\run_suite.ps1 -Quick     # code-only smoke (~2 min, no model)
# Prevents the machine from sleeping during a full run, then restores the setting.
param([switch]$Quick)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not $Quick) {
    Write-Host "Disabling sleep for the overnight run..." -ForegroundColor Cyan
    $prev = (powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String "Current AC").ToString()
    powercfg /change standby-timeout-ac 0
    Write-Host "NOTE: quit FRIDAY from the tray first so the suite has the GPU to itself." -ForegroundColor Yellow
}

if ($Quick) {
    python run_suite.py --quick
} else {
    python run_suite.py
    Write-Host "Restoring sleep timeout to 30 min (adjust if you had a custom value)." -ForegroundColor Cyan
    powercfg /change standby-timeout-ac 30
}
