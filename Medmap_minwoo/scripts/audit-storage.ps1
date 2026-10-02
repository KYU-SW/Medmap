[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$marker = Join-Path $projectRoot '.project-root'

if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
    throw "Project marker is missing: $marker"
}

$projectName = (Get-Content -LiteralPath $marker -Raw).Trim()
if ($projectName -ne 'MedMap' -or (Split-Path $projectRoot -Leaf) -ne 'MedMap') {
    throw 'Safety check failed. Expected the MedMap project root.'
}

$files = Get-ChildItem -LiteralPath $projectRoot -Force -Recurse -File -ErrorAction SilentlyContinue
$totalBytes = ($files | Measure-Object -Property Length -Sum).Sum
if ($null -eq $totalBytes) { $totalBytes = 0 }

Write-Host "Project root: $projectRoot"
Write-Host "Total size: $([Math]::Round($totalBytes / 1MB, 2)) MB"

Get-ChildItem -LiteralPath $projectRoot -Force | ForEach-Object {
    $bytes = if ($_.PSIsContainer) {
        (Get-ChildItem -LiteralPath $_.FullName -Force -Recurse -File -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
    } else { $_.Length }
    if ($null -eq $bytes) { $bytes = 0 }
    [PSCustomObject]@{ Name = $_.Name; SizeMB = [Math]::Round($bytes / 1MB, 2); Path = $_.FullName }
} | Sort-Object SizeMB -Descending | Format-Table -AutoSize

Write-Host "`nExternal and remote resources recorded for this project:"
Get-Content -LiteralPath (Join-Path $projectRoot 'EXTERNAL_RESOURCES.json') -Raw
Write-Host "`nThis command only audits. It does not delete files."
