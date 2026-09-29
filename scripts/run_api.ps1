$ErrorActionPreference = 'Stop'
$medmapRoot = Split-Path -Parent $PSScriptRoot
$medmapApi = Join-Path $medmapRoot 'apps\api'
$medmapPython = Join-Path $medmapApi '.venv\Scripts\python.exe'
$env:MEDMAP_CACHE_DIR = Join-Path $medmapRoot 'local-cache'
$env:HF_HOME = Join-Path $env:MEDMAP_CACHE_DIR 'huggingface'

if (-not (Test-Path -LiteralPath $medmapPython)) {
    throw 'apps/api/.venv is missing. Run scripts/setup_api.ps1 first.'
}

$nvidiaRoot = Join-Path $medmapApi '.venv\Lib\site-packages\nvidia'
$nvidiaBins = @(
    (Join-Path $nvidiaRoot 'cublas\bin'),
    (Join-Path $nvidiaRoot 'cudnn\bin'),
    (Join-Path $nvidiaRoot 'cuda_nvrtc\bin')
) | Where-Object { Test-Path -LiteralPath $_ }

if ($nvidiaBins.Count -ge 2) {
    $env:PATH = (($nvidiaBins -join [IO.Path]::PathSeparator) + [IO.Path]::PathSeparator + $env:PATH)
    if (-not $env:MEDMAP_STT_DEVICE) { $env:MEDMAP_STT_DEVICE = 'cuda' }
    if (-not $env:MEDMAP_STT_COMPUTE_TYPE) { $env:MEDMAP_STT_COMPUTE_TYPE = 'float16' }
    Write-Host 'MedMap STT device: NVIDIA GPU (CUDA, float16)'
} else {
    if (-not $env:MEDMAP_STT_DEVICE) { $env:MEDMAP_STT_DEVICE = 'cpu' }
    if (-not $env:MEDMAP_STT_COMPUTE_TYPE) { $env:MEDMAP_STT_COMPUTE_TYPE = 'int8' }
    Write-Host 'MedMap STT device: CPU (int8)'
}

Push-Location $medmapApi
try {
    & $medmapPython -m uvicorn app.main:app
} finally {
    Pop-Location
}
