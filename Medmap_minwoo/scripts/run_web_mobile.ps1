$ErrorActionPreference = 'Stop'

$medmapRoot = Split-Path -Parent $PSScriptRoot
$webDirectory = Join-Path $medmapRoot 'apps\web'
$accessFile = Join-Path $medmapRoot 'local-cache\mobile-https\mobile-access.json'

if (-not (Test-Path -LiteralPath $accessFile)) {
    throw 'Mobile HTTPS is not prepared. Run scripts/setup_mobile_https.ps1 first.'
}

$access = Get-Content -LiteralPath $accessFile -Raw | ConvertFrom-Json
Write-Host "Open on the phone: $($access.mobile_url)"
Write-Host 'Use only non-sensitive test sentences during development.'

Push-Location $webDirectory
try {
    & corepack pnpm dev
} finally {
    Pop-Location
}
