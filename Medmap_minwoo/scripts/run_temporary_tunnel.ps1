$ErrorActionPreference = 'Stop'

$medmapRoot = Split-Path -Parent $PSScriptRoot
$cloudflared = Join-Path $medmapRoot 'local-cache\tools\cloudflared.exe'

if (-not (Test-Path -LiteralPath $cloudflared)) {
    throw 'cloudflared.exe is missing from local-cache/tools.'
}

Write-Host 'Temporary public test tunnel. Use synthetic test sentences only.'
Write-Host 'Stop this process to close the public URL.'
& $cloudflared tunnel `
    --url 'http://127.0.0.1:5173' `
    --protocol http2
