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
├─ local-cache/            Whisper·패키지 캐시, Git 제외
├─ runs/                   로컬 실행 결과, Git 제외
└─ 기존 DDXPlus 분석 파일
```

## 코드 분리 원칙

- 웹 화면은 녹음하고 결과를 보여준다.
- API는 음성 파일을 받고 결과를 반환한다.
- STT 서비스는 음성을 글자로만 바꾼다.
- 증상 추출과 진단은 STT 서비스에 넣지 않는다.
- 원본 음성과 변환 문장은 로그나 Git에 저장하지 않는다.

## 현재 단계

`feature/stt-rebuild` 브랜치에서 STT 1차 기능을 구현했다. API의 `/health`와
`/v1/stt/transcribe`가 동작하며, Whisper 모델은 실제 요청이 들어올 때 불러온다.
웹 화면에서는 녹음 시작·종료, 변환 요청, 결과 수정, 오류 확인이 가능하다.

자동 검사에서는 서버 요청 형식과 웹 빌드를 확인했다. 실제 사람 목소리의 한국어 변환과
휴대폰 브라우저 확인은 아직 남아 있다.
