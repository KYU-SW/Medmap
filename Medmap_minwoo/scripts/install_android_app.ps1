# Builds the MedMap Android app and installs it on a phone connected by USB (docs/ANDROID_APP.md).
# Speech is transcribed and read into symptoms on the phone itself: no PC server is needed once installed.
$ErrorActionPreference = 'Stop'
$medmapRoot = Split-Path -Parent $PSScriptRoot
$webDirectory = Join-Path $medmapRoot 'apps\web'
$androidDirectory = Join-Path $webDirectory 'android'
$adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
$model = Join-Path $medmapRoot 'local-cache\whisper-cpp\models\ggml-large-v3-turbo-q8_0.bin'
$captionModel = Join-Path $medmapRoot 'local-cache\whisper-cpp\models\ggml-base-q8_0.bin'
$phoneModelDirectory = '/sdcard/Android/data/kr.medmap.app/files'
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'

function Invoke-Checked {
    param([string]$File, [string[]]$Arguments)
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$File $($Arguments -join ' ') failed (exit $LASTEXITCODE)." }
}

$devices = & $adb devices | Select-String -Pattern "\tdevice$"
if (-not $devices) { throw 'USB로 연결된 휴대폰이 없습니다. USB 디버깅을 켜고 연결 허용을 눌러 주세요.' }
foreach ($file in @($model, $captionModel)) {
    if (-not (Test-Path -LiteralPath $file)) { throw "모델 파일이 없습니다: $file" }
}

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

# The models are copied once; a file the phone already has at the same size is skipped.
# turbo (about 870MB) writes the transcript; base (about 80MB) shows the rough caption while recording.
foreach ($file in @($model, $captionModel)) {
    # stat fails while the file is missing; in Windows PowerShell that stderr would stop the script under 'Stop'.
    $ErrorActionPreference = 'Continue'
    $phoneSize = (& $adb shell stat -c %s "$phoneModelDirectory/$(Split-Path -Leaf $file)" 2>$null)
    $ErrorActionPreference = 'Stop'
    if ("$phoneSize".Trim() -ne "$((Get-Item -LiteralPath $file).Length)") {
        Invoke-Checked $adb @('shell', 'mkdir', '-p', $phoneModelDirectory)
        Invoke-Checked $adb @('push', $file, "$phoneModelDirectory/")
    }
}

Write-Host '설치 완료. 휴대폰에서 MedMap 앱을 여세요. PC와 USB를 빼도 됩니다.'
