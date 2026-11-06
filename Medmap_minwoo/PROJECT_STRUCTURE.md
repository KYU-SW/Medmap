# MedMap 프로젝트 구조

```text
MedMap/
├─ apps/
│  ├─ api/                     FastAPI 서버 (PC·브라우저 버전의 음성 변환, 녹음 측정·채점 스크립트)
│  │  ├─ app/
│  │  │  ├─ api/routes/        HTTP 요청을 받는 곳
│  │  │  ├─ schemas/           요청·응답 형식
│  │  │  └─ services/          Whisper 등 실제 처리 로직
│  │  └─ tests/                서버 테스트
│  └─ web/                     React 화면 (브라우저와 안드로이드 앱이 같은 화면을 씀)
│     ├─ src/                  화면, 기록 저장(IndexedDB), 요약·달력
│     │  └─ intake/            증상 정리: TypeScript 규칙(extractor.ts), 목록 밖 AI 제안(outsideSymptoms.ts·
│     │                        spanModel.ts·spanWindows.ts·aiAssist.ts), 토크나이저, 증상·부위 사전(vocabulary.json)
│     ├─ android/              Capacitor 안드로이드 앱: 폰 내장 인식 + whisper.cpp(JNI)
│     ├─ public/models/        AI 모델 어휘(spans-vocab.json)·해시(spans.onnx.sha256). 모델 파일 spans.onnx는 Git 제외
│     ├─ eval/                 평가 문장, 채점기(evaluate.ts, evaluate_outside.ts v1, evaluate_outside_v2.ts), 예측 파일
│     └─ train/                AI 학습 문장 생성·학습·ONNX 내보내기 (결과물은 local-cache에만, 공개 배포 안 함)
├─ docs/                       기능 정의, 개인정보 원칙, 안드로이드 앱, 휴대폰 시험 방법
├─ scripts/                    설치·실행·안드로이드 설치·팀 저장소 올리기 스크립트
├─ tests/fixtures/audio/       공유 가능한 테스트 음성 설명
├─ data/                       DDXPlus 원본, Git 제외
├─ local-cache/                모델·패키지·학습 자료·캐시, Git 제외
├─ runs/                       로컬 실행 결과, Git 제외
└─ 기존 DDXPlus 분석 파일
```

## 코드 분리 원칙

- 증상 정리 규칙의 원본은 TypeScript(`apps/web/src/intake/extractor.ts`)이고 화면(앱) 안에서 실행한다. 서버에는 없다.
- 목록 밖 증상 AI는 규칙 결과에 덧붙는 보조 기능이다. 모델 파일이 없거나 실행에 실패하면 규칙 결과만으로 동작하고,
  화면에 "AI 도우미를 사용할 수 없어 기본 규칙으로만 정리했어요"를 보여 준다.
- API는 PC·브라우저 버전에서 음성 파일을 받아 글자로만 바꾼다. 증상 추출과 진단은 STT에 넣지 않는다.
- 원본 음성과 변환 문장은 로그나 Git에 저장하지 않는다.

## 실행 환경별 흐름

- 안드로이드 앱: 녹음 → 폰 내장 인식(자막·첫 문장) + 폰 안 whisper 정밀 확인 → 앱 안 규칙 정리 → (모델이 있으면) 앱 안 AI 제안 → 환자 확인 → 기기 저장
- PC·브라우저: 녹음 → PC 서버 faster-whisper → 화면 안 규칙 정리 → (모델이 있으면) AI 제안 → 환자 확인 → 브라우저 저장

자세한 내용은 README의 "현재 할 수 있는 것", docs/STT_SPEC.md, docs/ANDROID_APP.md에 있다.
