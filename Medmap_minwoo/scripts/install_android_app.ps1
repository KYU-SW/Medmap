# Builds the MedMap Android app and installs it on a phone connected by USB (docs/ANDROID_APP.md).
# Speech is transcribed on the phone; the intake rules still run on this PC's API, reached through adb reverse.
$ErrorActionPreference = 'Stop'
$medmapRoot = Split-Path -Parent $PSScriptRoot
$webDirectory = Join-Path $medmapRoot 'apps\web'
$androidDirectory = Join-Path $webDirectory 'android'
$adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
$model = Join-Path $medmapRoot 'local-cache\whisper-cpp\models\ggml-large-v3-turbo-q5_0.bin'
$phoneModelDirectory = '/sdcard/Android/data/kr.medmap.app/files'
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'

function Invoke-Checked {
    param([string]$File, [string[]]$Arguments)
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$File $($Arguments -join ' ') failed (exit $LASTEXITCODE)." }
}

$devices = & $adb devices | Select-String -Pattern "\tdevice$"
if (-not $devices) { throw 'USB로 연결된 휴대폰이 없습니다. USB 디버깅을 켜고 연결 허용을 눌러 주세요.' }
if (-not (Test-Path -LiteralPath $model)) { throw "모델 파일이 없습니다: $model" }

Push-Location $webDirectory
try {
    Invoke-Checked corepack @('pnpm', 'run', 'build')
    Invoke-Checked corepack @('pnpm', 'exec', 'cap', 'sync', 'android')
} finally { Pop-Location }

Push-Location $androidDirectory
try {
    Invoke-Checked '.\gradlew.bat' @('assembleDebug', '--console=plain')
} finally { Pop-Location }

Invoke-Checked $adb @('install', '-r', (Join-Path $androidDirectory 'app\build\outputs\apk\debug\app-debug.apk'))

# The model (about 550MB) is copied once; skip it when the phone already has the same size.
$phoneSize = (& $adb shell stat -c %s "$phoneModelDirectory/$(Split-Path -Leaf $model)" 2>$null)
if ("$phoneSize".Trim() -ne "$((Get-Item -LiteralPath $model).Length)") {
    Invoke-Checked $adb @('shell', 'mkdir', '-p', $phoneModelDirectory)
    Invoke-Checked $adb @('push', $model, "$phoneModelDirectory/")
}

Invoke-Checked $adb @('reverse', 'tcp:8000', 'tcp:8000')
Write-Host '설치 완료. PC에서 scripts\run_api.ps1을 켜 두고 휴대폰에서 MedMap 앱을 여세요.'
