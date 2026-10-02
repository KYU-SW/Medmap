# Copies this project's main branch into the team repository KYU-SW/Medmap
# under Medmap_minwoo/, leaving out the AI agent rules and notes that belong
# only in the personal repository. Each run adds one commit that lists the
# personal commits it brings in. Push main to minu2246/MedMap first.
$ErrorActionPreference = 'Stop'
$medmapRoot = Split-Path -Parent $PSScriptRoot
$teamRemote = 'https://github.com/KYU-SW/Medmap.git'
$teamPrefix = 'Medmap_minwoo'
$teamClone = Join-Path $medmapRoot 'local-cache\team-repo'
# Personal-repository only: AI agent rules, handoff notes and local admin docs.
$personalOnly = @(
    'AGENTS.md', 'CLAUDE.md', 'HANDOFF.md', 'PROJECT_BRIEF.txt',
    'TEAM_PROGRESS_REVIEW_2026-09-29.md', 'FILE_MANAGEMENT.md',
    'LOCAL_STORAGE_PLAN.md', 'SETUP_GIT_AUTH.ps1'
)

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

# The last personal commit already in the team repository: a Source-Commit trailer,
# or the second parent of an earlier git-subtree merge.
$lastSource = $null
$messages = & git -C $teamClone log -50 --format='%H %P%n%B%n@@end@@' -- $teamPrefix
$block = @()
foreach ($line in $messages + '@@end@@') {
    if ($line -ne '@@end@@') { $block += $line; continue }
    if ($block.Count -gt 0) {
        $trailer = $block | Select-String -Pattern '^Source-Commit:\s*([0-9a-f]{40})' | Select-Object -First 1
        $hashes = $block[0] -split ' '
        if ($trailer) { $lastSource = $trailer.Matches[0].Groups[1].Value }
        elseif ($hashes.Count -ge 3) { $lastSource = $hashes[2] }
        if ($lastSource) { break }
    }
    $block = @()
}

$archive = Join-Path $env:TEMP 'medmap-team-export.tar'
$excludes = $personalOnly | ForEach-Object { ":(exclude)$_" }
Invoke-MedMapGit -C $medmapRoot archive --format=tar "--output=$archive" main -- . @excludes
$target = Join-Path $teamClone $teamPrefix
if (Test-Path -LiteralPath $target) {
    Invoke-MedMapGit -C $teamClone rm -r -q --ignore-unmatch $teamPrefix
}
New-Item -ItemType Directory -Force -Path $target | Out-Null
& tar -xf $archive -C $target
if ($LASTEXITCODE -ne 0) { throw "tar failed (exit $LASTEXITCODE)." }
Remove-Item -LiteralPath $archive
Invoke-MedMapGit -C $teamClone add -A $teamPrefix

& git -C $teamClone diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "No changes for $teamPrefix ($localMain)."
    exit 0
}
$range = if ($lastSource) { "$lastSource..$localMain" } else { '-20' }
$included = & git -C $medmapRoot log --format='- %h %s' $range
$message = @(
    "Update $teamPrefix from minu2246/MedMap", '',
    'Personal commits included:', $included, '',
    "Source-Commit: $localMain"
) -join "`n"
$messageFile = Join-Path $env:TEMP 'medmap-team-commit.txt'
[IO.File]::WriteAllText($messageFile, $message, (New-Object Text.UTF8Encoding $false))
Invoke-MedMapGit -C $teamClone commit -q -F $messageFile
Remove-Item -LiteralPath $messageFile
Invoke-MedMapGit -C $teamClone push origin main
Write-Host "Pushed $teamPrefix ($localMain) to KYU-SW/Medmap main without personal-only files."
