[CmdletBinding(SupportsShouldProcess)]
param([switch]$Execute)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$marker = Join-Path $projectRoot '.project-root'

if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { throw "Project marker is missing: $marker" }
$projectName = (Get-Content -LiteralPath $marker -Raw).Trim()
if ($projectName -ne 'MedMap' -or (Split-Path $projectRoot -Leaf) -ne 'MedMap') {
    throw 'Safety check failed. Expected the MedMap project root.'
}

$relativeTargets = @(
    '.venv',
    'apps\api\.venv',
    'apps\web\node_modules',
    'apps\web\dist',
    'local-cache',
    'data',
    'checkpoints',
    'runs'
)

$targets = foreach ($relativeTarget in $relativeTargets) {
    $candidate = Join-Path $projectRoot $relativeTarget
    if (Test-Path -LiteralPath $candidate) {
        $resolved = (Resolve-Path -LiteralPath $candidate).Path
        if (-not $resolved.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean a path outside the project: $resolved"
        }
        $resolved
    }
}

if (-not $Execute) {
    Write-Host 'Preview only. The following reproducible paths would be removed:'
    if ($targets.Count -eq 0) { Write-Host '(none found)' }
    $targets | ForEach-Object { Write-Host $_ }
    Write-Host "`nPrivate test audio and source files are not included."
    Write-Host 'Run again with -Execute only after reviewing this list.'
    exit 0
}

foreach ($target in $targets) {
    if ($PSCmdlet.ShouldProcess($target, 'Remove reproducible project data')) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

Write-Host 'Reproducible project data cleanup completed.'
Write-Host 'Review EXTERNAL_RESOURCES.json before deleting the project root.'
