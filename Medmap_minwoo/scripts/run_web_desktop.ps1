$ErrorActionPreference = 'Stop'

$medmapRoot = Split-Path -Parent $PSScriptRoot
$webDirectory = Join-Path $medmapRoot 'apps\web'
$env:MEDMAP_USE_HTTPS = '0'

Write-Host 'Desktop URL: http://127.0.0.1:5173'

Push-Location $webDirectory
try {
    & corepack pnpm dev
} finally {
    Pop-Location
}
