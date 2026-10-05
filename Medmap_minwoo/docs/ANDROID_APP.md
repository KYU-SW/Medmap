# 안드로이드 앱 (폰 안 음성 인식 시험판)

지금 웹 화면을 Capacitor로 감싼 안드로이드 앱이다. 녹음한 음성은 **휴대폰 안의 whisper.cpp**(압축 turbo 모델)가 글자로 바꾸고,
음성은 휴대폰 밖으로 나가지 않는다. 증상 정리 규칙은 아직 Python이라 PC의 API를 USB(`adb reverse`)로 부른다.
iOS는 Mac이 있어야 빌드할 수 있어 아직 만들지 않았다.

## 구성

- `apps/web/capacitor.config.json`, `apps/web/android/`: Capacitor 8 안드로이드 프로젝트
- `android/app/src/main/cpp/`: whisper.cpp v1.9.4를 빌드 때 받아 앱에 넣는 CMake 설정과 JNI 코드. 64비트 ARM 폰만, 항상 최적화 빌드
- `android/app/src/main/java/kr/medmap/app/WhisperPlugin.java`: 웹 화면에서 부르는 `Whisper.transcribe` / `Whisper.status`
- `apps/web/src/phoneStt.ts`: 앱 안에서는 녹음 종료 후 16kHz 음성을 플러그인으로 넘기고, 증상 정리는 `http://localhost:8000`으로 보낸다
- 모델 파일(약 550MB)은 APK에 넣지 않고 `/sdcard/Android/data/kr.medmap.app/files/`에 adb로 한 번 복사한다

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

## 남은 일

- 실제 폰에서 정확도·속도 측정(녹음 길이 대비 변환 시간)
- 증상 정리 규칙을 TypeScript로 옮겨 PC 없이 동작하게 하기
- 모델을 앱이 처음 실행될 때 받게 할지, 다른 방법으로 넣을지 정하기
