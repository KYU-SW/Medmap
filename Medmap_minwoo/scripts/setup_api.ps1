$ErrorActionPreference = 'Stop'
$medmapRoot = Split-Path -Parent $PSScriptRoot
$medmapApi = Join-Path $medmapRoot 'apps\api'
$medmapRuntimePython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$medmapVenvPython = Join-Path $medmapApi '.venv\Scripts\python.exe'
$medmapCache = Join-Path $medmapRoot 'local-cache'

if (-not (Test-Path -LiteralPath $medmapRuntimePython)) {
    throw 'Codex Python was not found. Check the configured Python path.'
}

New-Item -ItemType Directory -Force -Path $medmapCache | Out-Null
$env:PIP_CACHE_DIR = Join-Path $medmapCache 'pip'
$env:HF_HOME = Join-Path $medmapCache 'huggingface'
$env:MEDMAP_CACHE_DIR = $medmapCache

if (-not (Test-Path -LiteralPath $medmapVenvPython)) {
    & $medmapRuntimePython -m venv (Join-Path $medmapApi '.venv')
}

& $medmapVenvPython -m pip install --upgrade pip
& $medmapVenvPython -m pip install -e "$medmapApi[dev]"
Write-Host 'MedMap API environment installed.' -ForegroundColor Green
Write-Host "Python environment: $(Join-Path $medmapApi '.venv')"
Write-Host "Project cache: $medmapCache"
