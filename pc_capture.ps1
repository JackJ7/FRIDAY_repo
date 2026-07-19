# PC.5 capture driver (armor plan M2 batch / PC leg): run each new golden
# x5 on BASELINE code, one pytest per run with its own pinned --basetemp so
# the sandbox interaction logs can be pulled immediately (the EM.5 lesson).
# Usage: powershell -File pc_capture.ps1 [-Cases gt_p5a,gt_p5b,gt_p2a] [-Runs 5]
param(
    [string[]]$Cases = @("gt_p5a", "gt_p5b", "gt_p2a"),
    [int]$Runs = 5,
    [string]$OutRoot = "results\pc_capture_2026-07-18"
)
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force $OutRoot | Out-Null
foreach ($case in $Cases) {
    foreach ($i in 1..$Runs) {
        $tag = "${case}_r$i"
        $tmp = Join-Path $OutRoot "$tag\tmp"
        New-Item -ItemType Directory -Force $tmp | Out-Null
        Write-Output "=== $tag start $(Get-Date -Format HH:mm:ss) ==="
        py -3 -m pytest "tests/pillar1/test_corrections.py" -k $case -m model `
            --basetemp=$tmp -q 2>&1 |
            Tee-Object -FilePath (Join-Path $OutRoot "$tag\pytest.log")
        # Pull the sandbox ilogs NOW, before any later run can rotate them.
        Get-ChildItem $tmp -Recurse -Include "*.jsonl" -ErrorAction SilentlyContinue |
            ForEach-Object {
                Copy-Item $_.FullName (Join-Path $OutRoot ("$tag\" + $_.Name)) -Force
            }
        # The tmp sandbox tree is bulky and served its purpose once ilogs are out.
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 20   # minute-spacing lite between model runs
    }
}
Write-Output "=== capture complete $(Get-Date -Format HH:mm:ss) ==="
