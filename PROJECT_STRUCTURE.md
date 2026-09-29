# MedMap 프로젝트 구조

```text
MedMap/
├─ apps/
│  ├─ api/                 FastAPI 서버
│  │  ├─ app/
│  │  │  ├─ api/routes/    HTTP 요청을 받는 곳
│  │  │  ├─ schemas/       요청·응답 형식
│  │  │  └─ services/      Whisper 등 실제 처리 로직
│  │  └─ tests/            서버 테스트
│  └─ web/                 React 웹 화면
│     └─ src/
├─ docs/                   기능 정의와 개인정보 원칙
├─ scripts/                개발 실행 스크립트
├─ tests/fixtures/audio/   공유 가능한 테스트 음성 설명
├─ data/                   DDXPlus 원본, Git 제외
└─ 기존 DDXPlus 분석 파일
```

## 코드 분리 원칙

- 웹 화면은 녹음하고 결과를 보여준다.
- API는 음성 파일을 받고 결과를 반환한다.
- STT 서비스는 음성을 글자로만 바꾼다.
- 증상 추출과 진단은 STT 서비스에 넣지 않는다.
- 원본 음성과 변환 문장은 로그나 Git에 저장하지 않는다.

## 현재 단계

`feature/stt-rebuild` 브랜치에 새 구조를 만들었다. 현재 API의 `/health`는 동작하도록 작성했고,
`/v1/stt/transcribe`는 계약만 마련한 상태다. Whisper 구현 전까지는 501 응답을 반환한다.
웹 화면도 구조 확인용 시작 화면이며 녹음 기능은 다음 단계에서 구현한다.
