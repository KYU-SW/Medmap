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
- (기기 내장 인식이 없을 때) 녹음 중 자막: 1.5초마다 작은 모델(`ggml-base-q8_0.bin`, 약 80MB, 같은 폴더)로 지금까지의 녹음을 대략 변환해 보여 준다.
  녹음 종료 후 결과는 turbo로 전체를 다시 변환한 것이다. 자막 모델이 없으면 자막 없이 녹음만 한다.
- 녹음 앞뒤의 조용한 부분은 잘라서 변환한다. 조용한 부분을 넣으면 모델이 없는 말을 지어낸다(`감사합니다.`, `맨날 그러냐`).

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

## 자동 측정 (폰 화면을 누르지 않고)

디버그 앱은 USB로 웹 화면에 접속할 수 있어, PC의 WAV 파일로 앱 안의 변환을 직접 부를 수 있다.
폰은 잠금 해제 상태여야 한다(뒤로 가면 Android가 느린 코어로 옮긴다).

cd apps\api
cd apps\api
.\.venv\Scripts\python.exe -m scripts.bench_phone_stt <16kHz 모노 wav...>            # 최종 변환 시간·결과
.\.venv\Scripts\python.exe -m scripts.bench_phone_stt <wav...> --caption              # 1.5초씩 늘려 가며 자막도
```

- 2026-10-06 결과(녹음 8~10초 3개): 자막 0.1~0.9초(대부분 0.1~0.4초), 최종 6.3~6.7초, 최종 결과는 기존과 같음.
  자막은 단어가 자주 틀린다(`구구수시고`, `타이리인`) — 미리보기 용도다.
- 빠른 코어 고정: Android 13 앱은 cpufreq를 못 읽어 `/proc/cpuinfo`의 CPU part로 느린 코어(A55·Kryo Silver 등)를 빼고
  나머지에 고정한다. 고정 안 하면 4스레드가 느린 코어에 섞여 encoder가 10초 이상 걸리기도 했다(PC에서 명령줄로 잰 값).
- 버린 방법: 말을 쉬는 곳에서 구절로 끊어 turbo로 미리 변환 — 짧은 구절은 문맥이 없어 `복통`을 `폭통`으로 적었고,
  최소 15초 계산 범위 때문에 구절마다 5초가 걸려 짧은 녹음은 빨라지지 않았다.

## 기기 내장 인식 + turbo 검증 (2026-10-06, 하이브리드)

노트20에 Android 기기 내 한국어 인식(`createOnDeviceSpeechRecognizer`, 언어팩 `ko-KR` 설치됨)이 있다.
일반 SpeechRecognizer와 달리 서버로 보내지 않는 API이고, 비행기 모드(인터넷 차단 확인)에서 같은 결과가 나왔다.

- 흐름: 앱이 마이크를 한 번만 녹음 → 같은 음성을 기기 인식기(`DeviceSttPlugin` start/push/stop, Android 13의
  `EXTRA_AUDIO_SOURCE`, 구간 세션)와 turbo에 넘긴다. 녹음 중 자막과 종료 직후 문장은 기기 인식기 결과.
  turbo는 뒤에서 같은 음성을 변환하고, "다음: 증상 정리하기"를 누를 때 두 문장을 증상 정리 규칙에 넣어
  증상(있음/없음·시작 시점)·약·알레르기가 다르면 두 문장을 보여 주고 고르게 한다(`transcriptCheck.ts`).
  같으면 묻지 않는다. 환자가 고친 문장은 검증·교체하지 않는다. 임시 자막은 기록으로 저장하지 않는다.
- 기기에 한국어 오프라인 인식이 없으면(Android 13 미만, 언어팩 없음) 이전 방식(base 자막 + turbo)으로 자동 전환.
- 측정(녹음 8개를 말 속도로 입력, 노트20): 첫 자막 0.6~2.6초, 자막 4초 녹음에 약 20번 갱신,
  **녹음 종료 후 확정 0.02~0.10초**(turbo만 쓸 때 약 5~6초, 17초 녹음은 12.5초). 긴 녹음에서도 늘지 않음.
- 정확도(turbo 결과와 비교, 사람이 확인한 정답 아님): 8개 중 6개는 증상 정리가 같거나 더 좋음
  (`페니실린` 알레르기·`구토 3회`·`타이레놀`을 turbo보다 정확히). 2개는 `쿡쿡`→`크고`/`구구`, `복통`→`폭통`으로
  **복통을 놓침** — 그래서 turbo 검증을 유지한다. 같은 녹음에서도 실행마다 결과가 조금 달랐다(`크고`/`구구`).
- 시험 도구: `apps/api/scripts/bench_device_stt.py <wav...> [--live]` (`--live`는 앱과 같은 start/push/stop 방식)
- 아직: 실제 마이크 시험, 사람이 확인한 정답 기준 평가, 다른 기종(언어팩 유무), 확인 요청이 얼마나 자주 뜨는지

## 비교 후 버린 것: 한국어 스트리밍 Zipformer (sherpa-onnx, 2026-10-06)

`sherpa-onnx-streaming-zipformer-korean-2024-06-16`(KsponSpeech 969시간, 모델 카드에 라이선스 표기 없음 —
배포하려면 데이터 이용 조건 확인 필요). PC에서 같은 녹음 8개로 비교: 매우 빠르지만(17초 녹음 0.6초, PC)
`열이`→`여리`, `구토`→`국토`, `알레르기`→`난리`, `쿡쿡 쑤시고`→`크구쓰시고` 등으로 8개 중 5개에서 turbo가 잡은
증상·알레르기·시작 시점을 놓쳤고 띄어쓰기를 하지 않는다. 자막용도 이미 있는 것보다 낫지 않아 폰 측정 전에 중단.

## 더 빠르게 하려고 시험했지만 쓰지 않은 것 (2026-10-06, 녹음 8개·노트20 실측)

| 방법 | 결과 |
|---|---|
| 더 작은 모델 medium·small (q8_0) | turbo와 증상 정리가 같은 녹음 medium 4/8, small 2/8(`복통`·`두통`·`코막힘` 놓침). medium은 PC에서 약 25%만 빠름 |
| 받아 적기 greedy(후보 1개) | 7/8, 17초 녹음에서 같은 문장 반복. 짧은 녹음은 거의 안 빨라짐 |
| 말이 멈추면 전체를 미리 turbo로 변환 | 이득은 멈춘 뒤 버튼까지 1~2초뿐. whisper.cpp가 encoder 중에는 중단 신호를 확인하지 않아(취소에 5.3초) 다시 말을 이으면 최대 약 5초 더 느려짐. 자막과 동시에 돌면 turbo 6.3→9.4초 |
| 폰 NPU(Qualcomm AI Hub Whisper turbo) | 스냅드래곤 888(갤럭시 S21) 이상만 대상, 노트20(865)은 대상 아님 |

→ 노트20에서 turbo 정확도를 지키는 한 녹음 종료 후 약 5~6초가 바닥이다. 대신 녹음 중 자막과 녹음 종료 후 진행 막대로 기다림을 줄여 보이게 했다.

## GPU 시험 방법 (2026-10-06, 실패 기록)

명령줄 whisper.cpp를 Vulkan으로 빌드해 `adb shell`에서 돌렸다. 필요한 것: NDK의 `shader-tools/.../glslc.exe`,
Khronos Vulkan-Headers(`vulkan.hpp`), SPIRV-Headers(CMake 설치본), MSVC(셰이더 생성기 빌드), `ANDROID_PLATFORM=android-28`
(Vulkan 1.1 함수). Windows 경로 길이 제한 때문에 빌드 폴더는 짧은 경로(`%TEMP%\mmvk`)에 둔다.
결과: GPU는 인식(`Adreno (TM) 650 … fp16: 1`)하지만 모델 로드 중 Segmentation fault.

## 남은 일

- **더 빠르게**(사용자 요청 2026-10-06): 빠른 코어 고정은 했다. 녹음 종료 후 약 6초 중 encoder가 약 5초.
  폰 GPU(Vulkan)는 노트20(Adreno 650)에서 **모델을 올리는 단계에서 매번 죽는다**(turbo q8_0·q4_0, base, flash attention 끔 모두).
  남은 후보는 Hexagon NPU(Qualcomm 전용 도구, 엔진 교체 수준의 큰 작업). 최신 Adreno 7xx는 OpenCL 경로가 따로 있다
- 자막·진행 막대를 실제 마이크 녹음으로 확인(자동 측정은 녹음 파일로 흉내 낸 것)
- 다른 폰에서 속도 측정: CPU(특히 큰 코어 세대·개수)에 따라 크게 달라진다. 최신 폰은 NPU 경로도 검토

- 증상 정리 규칙을 TypeScript로 옮겨 PC 없이 동작하게 하기
- 모델을 앱이 처음 실행될 때 받게 할지, 다른 방법으로 넣을지 정하기
