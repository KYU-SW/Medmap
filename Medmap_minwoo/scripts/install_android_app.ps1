# Builds the MedMap Android app and installs it on a phone connected by USB (docs/ANDROID_APP.md).
# Speech is transcribed and read into symptoms on the phone itself: no PC server is needed once installed.
#   -Release    the build must carry the AI symptom model: stop unless spans.onnx is there and matches spans.onnx.sha256
#   -CheckOnly  the same check as -Release, then stop (no phone needed); exits with an error when the check fails
param([switch]$Release, [switch]$CheckOnly)
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

# The AI symptom model (apps/web/train/export_onnx.py) is not in Git. Without it the app still reads symptoms with
# the rules and says on the review screen that the AI could not be used.
$spanModel = Join-Path $webDirectory 'public\models\spans.onnx'
$spanHash = "$spanModel.sha256"
if ($Release -or $CheckOnly) {
    # Strict: no model, no recorded hash, or a different hash all stop here with an error (exit code 1).
    if (-not (Test-Path -LiteralPath $spanModel)) { throw "AI 모델 파일이 없습니다: $spanModel (apps/web/train/export_onnx.py로 만든 뒤 다시 실행하세요)" }
    if (-not (Test-Path -LiteralPath $spanHash)) { throw "AI 모델 해시 파일이 없습니다: $spanHash" }
    $expected = (Get-Content -LiteralPath $spanHash -Raw).Trim().Split()[0].ToLower()
    $actual = (Get-FileHash -LiteralPath $spanModel -Algorithm SHA256).Hash.ToLower()
    if ($expected -ne $actual) { throw "AI 모델 SHA-256이 기록과 다릅니다. 기록: $expected / 실제: $actual" }
    Write-Host "AI 모델 확인: $actual"
    if ($CheckOnly) { exit 0 }
} elseif (-not (Test-Path -LiteralPath $spanModel)) {
    Write-Warning 'AI 모델 파일(spans.onnx)이 없습니다. 규칙만으로 정리하는 개발용 앱이 설치됩니다(확인 화면에 "AI 도우미를 사용할 수 없어요" 표시).'
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
