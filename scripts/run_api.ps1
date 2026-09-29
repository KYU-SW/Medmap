$ErrorActionPreference = 'Stop'
$medmapRoot = Split-Path -Parent $PSScriptRoot
$medmapApi = Join-Path $medmapRoot 'apps\api'
$medmapPython = Join-Path $medmapApi '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $medmapPython)) {
    throw 'apps/api/.venv가 없습니다. API 폴더에서 Python 가상환경과 패키지를 먼저 설치하세요.'
}

Push-Location $medmapApi
try {
    & $medmapPython -m uvicorn app.main:app --reload
} finally {
    Pop-Location
}
