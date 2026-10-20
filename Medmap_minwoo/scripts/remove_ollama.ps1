# Removes Ollama and everything the training-data generator left (HANDOFF 7-1, step 2).
# Without -Execute it only lists what would go. Run:  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\remove_ollama.ps1 [-Execute]
param([switch]$Execute)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$targets = @(
    (Join-Path $projectRoot 'local-cache\ollama'),          # EXAONE model (about 4.4 GB)
    (Join-Path $projectRoot 'local-cache\intake-train'),    # generated sentences and logs
    (Join-Path $env:USERPROFILE '.ollama'),                 # Ollama key and default model folder
    (Join-Path $env:LOCALAPPDATA 'Ollama'),                 # Ollama logs and app database
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\Ollama.lnk')  # starts Ollama at sign-in
) | Where-Object { Test-Path -LiteralPath $_ }

$installed = Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'Programs\Ollama')
if ($installed) { Write-Host 'Program: Ollama (winget uninstall Ollama.Ollama, about 2.8 GB)' }
foreach ($target in $targets) {
    $size = (Get-ChildItem -LiteralPath $target -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    Write-Host ('Remove:  {0} ({1:N2} GB)' -f $target, ($size / 1GB))
}
if (-not $Execute) { Write-Host 'Nothing removed. Add -Execute to remove the above.'; return }

Get-Process 'ollama', 'ollama app' -ErrorAction SilentlyContinue | Stop-Process -Force -Confirm:$false
if ($installed) { winget uninstall --id Ollama.Ollama -e --silent }
foreach ($target in $targets) { Remove-Item -LiteralPath $target -Recurse -Force -Confirm:$false -ErrorAction SilentlyContinue }
Write-Host 'Removed.'
