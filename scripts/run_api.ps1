$ErrorActionPreference = 'Stop'
$medmapRoot = Split-Path -Parent $PSScriptRoot
$medmapApi = Join-Path $medmapRoot 'apps\api'
$medmapPython = Join-Path $medmapApi '.venv\Scripts\python.exe'
$env:MEDMAP_CACHE_DIR = Join-Path $medmapRoot 'local-cache'
$env:HF_HOME = Join-Path $env:MEDMAP_CACHE_DIR 'huggingface'

if (-not (Test-Path -LiteralPath $medmapPython)) {
    throw 'apps/api/.venv is missing. Run scripts/setup_api.ps1 first.'
}

Push-Location $medmapApi
try {
    & $medmapPython -m uvicorn app.main:app --reload
} finally {
    Pop-Location
}
