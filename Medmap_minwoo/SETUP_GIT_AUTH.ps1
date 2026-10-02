# Run in your normal Windows PowerShell, not a Codex sandbox terminal.
# Credentials are managed by Git Credential Manager, never written by this script.
$ErrorActionPreference = 'Stop'
$medmapRepo = $PSScriptRoot
$medmapGit = 'C:\Program Files\Git\cmd\git.exe'
$medmapRemote = 'https://github.com/minu2246/MedMap.git'

function Invoke-MedMapGit {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArguments)
    & $medmapGit -C $medmapRepo @GitArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed (exit $LASTEXITCODE). No files were deleted."
    }
}

try {
    $medmapIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    if ($medmapIdentity -match 'CodexSandbox') {
        throw 'Open Windows PowerShell from the Start menu and run this script there.'
    }
    if (-not (Test-Path -LiteralPath $medmapGit)) {
        throw 'Git for Windows was not found at C:\Program Files\Git\cmd\git.exe.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $medmapRepo '.git'))) {
        throw 'Run the script from the existing MedMap repository.'
    }

    # Trust only this exact checkout, which was created by a Codex sandbox account.
    $medmapSafePath = $medmapRepo.Replace('\', '/')
    $medmapSafePaths = @(& $medmapGit config --global --get-all safe.directory)
    if ($medmapSafePaths -notcontains $medmapSafePath) {
        & $medmapGit config --global --add safe.directory $medmapSafePath
        if ($LASTEXITCODE -ne 0) { throw 'Could not register this checkout as safe.' }
    }

    $medmapExistingRemote = Invoke-MedMapGit remote get-url origin
    if ($medmapExistingRemote -ne $medmapRemote) {
        throw 'The origin URL differs from the expected MedMap repository. Nothing was replaced.'
    }
    Invoke-MedMapGit config --local --replace-all credential.helper manager
    Invoke-MedMapGit config --local credential.credentialStore wincredman
    Invoke-MedMapGit config --local credential.interactive true
    Invoke-MedMapGit config --local http.sslBackend schannel

    Write-Host 'Complete GitHub login in the browser as minu2246.'
    Invoke-MedMapGit credential-manager github login --username minu2246 --browser
    Invoke-MedMapGit fetch origin

    # --quiet makes an unborn HEAD an expected exit code, not a stderr error
    # that Windows PowerShell 5.1 can promote to a terminating exception.
    & $medmapGit -C $medmapRepo rev-parse --verify --quiet HEAD
    if ($LASTEXITCODE -ne 0) {
        # Adopt the existing browser-created commit without modifying working files.
        Invoke-MedMapGit reset --mixed origin/main
    }
    Invoke-MedMapGit branch --set-upstream-to=origin/main main
    Invoke-MedMapGit pull --ff-only
    Invoke-MedMapGit push --dry-run origin main
    Invoke-MedMapGit status --short

    $medmapHead = Invoke-MedMapGit rev-parse HEAD
    @{ verified_at=(Get-Date -Format o); remote=$medmapRemote; head=$medmapHead;
       fetch='passed'; pull='passed'; push_dry_run='passed';
       note='Authentication checked; dry-run did not upload new commits.' } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $medmapRepo 'LOCAL_GIT_AUTH_STATUS.json') -Encoding utf8
    Write-Host 'SUCCESS: fetch, pull, and push dry-run passed. Local working files were preserved.' -ForegroundColor Green
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'Setup is incomplete. Share the error message only; never share a token or password.'
    exit 1
}
