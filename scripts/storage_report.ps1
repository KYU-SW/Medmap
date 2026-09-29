$ErrorActionPreference = 'Stop'
$medmapRoot = Split-Path -Parent $PSScriptRoot
$medmapTargets = @(
    @{ Name = 'MedMap repository'; Path = $medmapRoot },
    @{ Name = 'DDXPlus source data'; Path = Join-Path $medmapRoot 'data' },
    @{ Name = 'Python virtual environment'; Path = Join-Path $medmapRoot 'apps\api\.venv' },
    @{ Name = 'Frontend packages'; Path = Join-Path $medmapRoot 'apps\web\node_modules' },
    @{ Name = 'Model and package cache'; Path = Join-Path $medmapRoot 'local-cache' },
    @{ Name = 'Experiment runs'; Path = Join-Path $medmapRoot 'runs' },
    @{ Name = 'Model checkpoints'; Path = Join-Path $medmapRoot 'checkpoints' }
)

$medmapReport = foreach ($target in $medmapTargets) {
    if (Test-Path -LiteralPath $target.Path) {
        $bytes = (Get-ChildItem -LiteralPath $target.Path -File -Recurse -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
        [pscustomobject]@{
            Name = $target.Name
            SizeGB = [math]::Round(($bytes / 1GB), 3)
            Path = $target.Path
        }
    } else {
        [pscustomobject]@{ Name = $target.Name; SizeGB = 0; Path = $target.Path }
    }
}

$medmapReport | Format-Table -AutoSize
Write-Host 'Read-only report: no files were deleted.'
