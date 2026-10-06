# 안드로이드 앱 (폰 안 음성 인식 시험판)

지금 웹 화면을 Capacitor로 감싼 안드로이드 앱이다. 녹음한 음성은 **휴대폰 안의 whisper.cpp**(turbo 모델, q8_0 압축)가 글자로 바꾸고,
음성은 휴대폰 밖으로 나가지 않는다. 증상 정리 규칙은 아직 Python이라 PC의 API를 USB(`adb reverse`)로 부른다.
iOS는 Mac이 있어야 빌드할 수 있어 아직 만들지 않았다.

## 구성

- `apps/web/capacitor.config.json`, `apps/web/android/`: Capacitor 8 안드로이드 프로젝트
- `android/app/src/main/cpp/`: whisper.cpp v1.9.4를 빌드 때 받아 앱에 넣는 CMake 설정과 JNI 코드. 64비트 ARM 폰만, 항상 최적화 빌드,
  ARMv8.2 명령(dotprod·fp16) 사용 — 이 명령이 없는 아주 오래된 폰에서는 앱이 꺼진다(배포 전에 다시 볼 것)
- `android/app/src/main/java/kr/medmap/app/WhisperPlugin.java`: 웹 화면에서 부르는 `Whisper.transcribe` / `Whisper.status`
- `apps/web/src/phoneStt.ts`: 앱 안에서는 녹음 종료 후 16kHz 음성을 플러그인으로 넘기고, 증상 정리는 `http://localhost:8000`으로 보낸다
- 모델 파일 `ggml-large-v3-turbo-q8_0.bin`(약 870MB, Hugging Face `ggerganov/whisper.cpp`에서 받거나 원본에서 변환)은 APK에 넣지 않고
  `/sdcard/Android/data/kr.medmap.app/files/`에 adb로 한 번 복사한다. 그 폴더에 q8_0 → q4_0 → q5_0 순서로 먼저 있는 파일을 쓴다

## 처음 준비 (한 번)

1. Android Studio → SDK Manager → SDK Tools에서 **NDK (Side by side)**, **CMake** 설치
2. 휴대폰 **개발자 옵션** 켜기: 설정 → 휴대전화 정보 → 소프트웨어 정보 → **빌드 번호**를 7번 누른다
3. 설정 → 개발자 옵션 → **USB 디버깅** 켜기
4. USB로 PC에 연결하고 휴대폰에 뜨는 **USB 디버깅 허용**을 누른다

## 설치와 실행

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_android_app.ps1   # 빌드 → 설치 → 모델 복사 → adb reverse
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_api.ps1               # 증상 정리용 PC 서버
```

- 앱을 열고 `음성으로 기록` → 마이크 권한 허용 → 말하기 → `녹음 종료`. 변환이 끝나면 화면 위에 휴대폰 변환 시간이 나온다.
- 첫 변환은 모델을 불러오느라 더 걸린다(시간도 따로 표시).
- USB를 다시 꽂으면 `adb reverse`가 풀린다. 증상 정리가 안 되면 `adb reverse tcp:8000 tcp:8000`을 다시 실행한다.
- 녹음 중 실시간 자막은 앱에서는 끈다(폰에서는 모델을 반복 실행하기에 너무 느림).

## 속도 (2026-10-06, 갤럭시 노트20 · 스냅드래곤 865, 같은 문장으로 측정)

| 설정 | 녹음 4초 | 녹음 7~8초 |
|---|---|---|
| q5_0, 30초 전체 계산 | 38~62초 | 50초 |
| q5_0, 계산 범위 줄임 | 17.4초 | 18.7초 |
| q4_0, 계산 범위 줄임 | 5.1초 | 5.9초 |
| **q8_0, 계산 범위 줄임 (기본)** | **5.7초** | **6.2초** |

- 시간의 거의 전부가 encoder(음성을 읽는 부분)다. 받아 적기(decoder)는 1초 미만.
- Whisper는 짧게 말해도 30초 분량을 계산한다. `audio_ctx`로 녹음 길이 + 5초(최소 15초)만 계산한다.
  10초까지 줄이면 PC 비교에서 단어가 바뀌었다(`쿡쿡` → `구구`).
- q4_0·q8_0은 whisper.cpp의 ARM 전용 고속 경로(repack)를 타고, q5_0은 타지 못한다(로그 `repack tensor with q4_0_4x4`).
- 정확도(PC, 녹음 3개): q4_0은 `복통`을 `폭통`으로 적어 복통을 놓쳤고, q8_0은 증상 단어를 모두 맞혔다 → q8_0을 기본으로.
- `whisper.cpp` 타이밍은 logcat 태그 `whisper`로 나온다: `adb logcat -s whisper:I`
- 모델 변환: `local-cache/whisper-cpp/src-v1.9.4/build-win/bin/whisper-quantize.exe <원본> <출력> q8_0`
  (Visual Studio 2022 C++ 도구와 SDK의 CMake로 빌드)

## 남은 일

- **더 빠르게**(사용자 요청 2026-10-06): 스레드 수·큰 코어 지정, GPU(Vulkan) 시험, 녹음 중 미리 계산 등
- **실시간 자막**(사용자 요청 2026-10-06): 지금 앱은 녹음이 끝난 뒤 한 번만 변환한다

- 증상 정리 규칙을 TypeScript로 옮겨 PC 없이 동작하게 하기
- 모델을 앱이 처음 실행될 때 받게 할지, 다른 방법으로 넣을지 정하기
