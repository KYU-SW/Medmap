$ErrorActionPreference = 'Stop'
$medmapRoot = Split-Path -Parent $PSScriptRoot
$medmapWeb = Join-Path $medmapRoot 'apps\web'

Push-Location $medmapWeb
try {
    & 'C:\Program Files\nodejs\npm.cmd' run dev
} finally {
    Pop-Location
}
