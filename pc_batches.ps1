# PC.7 conversion batches (armor plan M2 batch / PC leg), on branch `pc`
# pre-merge: per-run pinned --basetemp + immediate ilog pull (EM.5 lesson).
# Bars: GT-C9 >=4/5 (false-completion half of its residual; baseline ~2/3),
# GT-P5b >=4/5 (the captured conversion case), GT-P5a/GT-P2a hold (locks),
# GT-C10 x2 hold (no-regression edge).
param([string]$OutRoot = "results\pc_batches_2026-07-18")
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force $OutRoot | Out-Null
$jobs = @(
    @{tag = "gt_c9";  file = "tests/pillar1/test_notes10.py";     k = "gt_c9";  runs = 5},
    @{tag = "gt_p5b"; file = "tests/pillar1/test_corrections.py"; k = "gt_p5b"; runs = 5},
    @{tag = "gt_p5a"; file = "tests/pillar1/test_corrections.py"; k = "gt_p5a"; runs = 5},
    @{tag = "gt_p2a"; file = "tests/pillar1/test_corrections.py"; k = "gt_p2a"; runs = 5},
    @{tag = "gt_c10"; file = "tests/pillar1/test_notes10.py";     k = "gt_c10"; runs = 2}
)
foreach ($j in $jobs) {
    foreach ($i in 1..$j.runs) {
        $tag = "$($j.tag)_r$i"
        $tmp = Join-Path $OutRoot "$tag\tmp"
        New-Item -ItemType Directory -Force $tmp | Out-Null
        Write-Output "=== $tag start $(Get-Date -Format HH:mm:ss) ==="
        py -3 -m pytest $j.file -k $j.k -m model --basetemp=$tmp -q 2>&1 |
            Tee-Object -FilePath (Join-Path $OutRoot "$tag\pytest.log")
        Get-ChildItem $tmp -Recurse -Include "*.jsonl" -ErrorAction SilentlyContinue |
            ForEach-Object {
                Copy-Item $_.FullName (Join-Path $OutRoot ("$tag\" + $_.Name)) -Force
            }
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 20
    }
}
Write-Output "=== batches complete $(Get-Date -Format HH:mm:ss) ==="
