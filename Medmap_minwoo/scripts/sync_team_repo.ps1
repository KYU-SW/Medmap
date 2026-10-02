# Copies this project's main branch, with its full history, into the team
# repository KYU-SW/Medmap under Medmap_minwoo/. Push main to the personal
# repository (minu2246/MedMap) first; this script only reads the local main.
$ErrorActionPreference = 'Stop'
$medmapRoot = Split-Path -Parent $PSScriptRoot
$teamRemote = 'https://github.com/KYU-SW/Medmap.git'
$teamPrefix = 'Medmap_minwoo'
$teamClone = Join-Path $medmapRoot 'local-cache\team-repo'

function Invoke-MedMapGit {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArguments)
    & git @GitArguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArguments -join ' ') failed (exit $LASTEXITCODE)."
    }
}

$localMain = (& git -C $medmapRoot rev-parse main).Trim()
$pushedMain = (& git -C $medmapRoot rev-parse origin/main).Trim()
if ($localMain -ne $pushedMain) {
    throw 'Local main differs from origin/main. Push main to minu2246/MedMap first.'
}

if (-not (Test-Path -LiteralPath (Join-Path $teamClone '.git'))) {
    Invoke-MedMapGit clone $teamRemote $teamClone
}
# Commit as the same author as the personal repository.
foreach ($setting in 'user.name', 'user.email') {
    $value = & git -C $medmapRoot config --get $setting
    if ($value) { Invoke-MedMapGit -C $teamClone config $setting $value.Trim() }
}
Invoke-MedMapGit -C $teamClone checkout main
Invoke-MedMapGit -C $teamClone pull --ff-only origin main

if (Test-Path -LiteralPath (Join-Path $teamClone $teamPrefix)) {
    Invoke-MedMapGit -C $teamClone subtree pull "--prefix=$teamPrefix" $medmapRoot main `
        -m "Update $teamPrefix from minu2246/MedMap"
} else {
    Invoke-MedMapGit -C $teamClone subtree add "--prefix=$teamPrefix" $medmapRoot main
}
Invoke-MedMapGit -C $teamClone push origin main
Write-Host "Pushed $teamPrefix ($localMain) to KYU-SW/Medmap main."
