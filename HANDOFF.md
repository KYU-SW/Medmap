# MedMap 작업 인계 (HANDOFF)

작성일: 2026-10-01
브랜치: `feature/stt-rebuild`
마지막 커밋: `47d78ee` Expand pre-visit intake (이후 HANDOFF 갱신 커밋)

## 1. 프로젝트 개요

MedMap은 환자가 말한 증상과 시간에 따른 변화를 연결하고, 현재 진단과 중요한 정보가
서로 맞지 않는 부분을 다시 확인하도록 돕는 진단 안전망 프로젝트다.
(상세: README.md, PROJECT_BRIEF.txt)

## 2. 저장소와 올리는 방법 (2026-10-02부터)

이 프로젝트는 저장소 두 곳에 함께 올린다.

| 저장소 | 공개 | 위치 | 역할 |
|---|---|---|---|
| https://github.com/minu2246/MedMap | 비공개 | 저장소 전체 | 개인 저장소. 작업 원본 |
| https://github.com/KYU-SW/Medmap | **공개** | `Medmap_minwoo/` 폴더 | 팀 통합 저장소. 팀원 작업은 `MedMap/` 폴더 |

올리는 순서 (사용자가 커밋·push를 요청했을 때만):
1. `feature/stt-rebuild`에 커밋하고 `main`을 fast-forward로 맞춘 뒤 두 브랜치를 `origin`(개인)에 push한다.
2. `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync_team_repo.ps1`을 실행한다.
   - 개인 저장소 `main`을 커밋 이력째 팀 저장소 `main`의 `Medmap_minwoo/`로 넣는다(`git subtree`).
   - 팀 저장소 작업용 복사본은 `local-cache/team-repo/`에 둔다(Git 제외).
   - 로컬 `main`과 `origin/main`이 다르면 멈춘다.

주의:
- 팀 저장소는 공개라 올리는 순간 공개된다. 비밀번호·토큰·실제 환자 정보, PC 경로·내부 IP를 넣지 않는다.
  2026-10-02에 README, `scripts/setup_api.ps1`, `docs/MOBILE_TEST.md`의 사용자 경로와 내부 IP를 일반 표기로 바꿨다.
  예전 커밋에는 원래 값이 남아 있고, 커밋 작성자 이메일도 이력과 함께 공개된다(사용자가 이력 전체 공개를 선택).
- 팀원의 `MedMap/` 폴더는 건드리지 않는다.

## 2-1. Git 상태 (2026-10-01 확인)

- CLAUDE.md는 `291f13e`에서 커밋했다. HANDOFF.md와 AGENTS.md는 `22aae26`에서 커밋했다.
- 2026-10-01 작업(아래 4절 8~9번, 6절, 7절)은 `47d78ee`에서 커밋하고 push했다. 변경 파일:
  - 문서: `HANDOFF.md`, `docs/INTAKE_EXTRACTION.md`, `docs/PRIVACY.md`
  - API: `app/services/intake_extractor.py`, `app/schemas/intake.py`, `tests/test_intake.py`,
    `tests/test_intake_scenarios.py`, 새 파일 `tests/test_intake_expanded.py`
  - 웹: `package.json`, `pnpm-lock.yaml`, `src/App.tsx`, `src/styles.css`, `src/recordStorage.ts`,
    `src/recordGroups.ts`, `src/visitSummary.ts`, 새 파일 `src/symptomOptions.ts`, `src/backup.ts`,
    `src/testRecords.ts`, 테스트 `src/*.test.ts` 5개
- 2026-10-02: `feature/stt-rebuild`를 main에 fast-forward로 병합하고 원격 main에도 푸시했다(`7b989e5`).
  같은 날 `f5acbec`까지 다시 병합·푸시했다. main과 feature/stt-rebuild는 같은 커밋을 가리킨다.
- 2026-10-02 합성어·구어 인식 확장, 주어 이어받기, 경고 증상 추가, 불확실·다른 사람·위험 증상 처리(아래 4절 10~12번)는
  `f5acbec`에서 커밋하고 push했다. 변경 파일:
  - API: `app/services/intake_extractor.py`, `app/schemas/intake.py`, `tests/test_intake.py`, `tests/test_intake_scenarios.py`,
    `tests/test_intake_expanded.py`, 새 파일 `tests/test_intake_red_flags.py`, `tests/test_intake_safety.py`
  - 웹: `src/App.tsx`, `src/styles.css`, `src/recordStorage.ts`, `src/symptomOptions.ts`, `src/symptomEpisodes.ts`,
    `src/timeline.ts`, `src/visitSummary.ts`, `src/backup.ts`, `src/backup.test.ts`, `src/symptomOptions.test.ts`, 새 파일 `src/safety.test.ts`
  - 문서: `docs/INTAKE_EXTRACTION.md`, `HANDOFF.md`
- 원격 저장소: https://github.com/minu2246/MedMap (비공개)

## 3. 구성

- `apps/api`: FastAPI 서버
  - `GET /health`
  - `POST /v1/stt/transcribe`: faster-whisper 1.2.1로 음성을 글자로 바꾼다.
    모델은 첫 요청 때 불러오고, NVIDIA 라이브러리가 있으면 GPU를 쓴다.
  - `POST .../intake/extract`: 규칙 기반으로 증상 정보를 뽑는다(`app/services/intake_extractor.py`).
- `apps/web`: React와 Vite 화면. 녹음, 텍스트 입력, 증상 확인, 기록 저장, 타임라인,
  진료 전 요약, PDF와 QR 공유를 제공한다.
  - `recordStorage.ts` 기록 저장(브라우저 IndexedDB) / `recordGroups.ts` 증상 그룹 / `symptomEpisodes.ts` 에피소드 묶음
  - `timeline.ts` 증상 변화 타임라인 / `visitSummary.ts` 진료 전 요약
  - `symptomOptions.ts` 지원 증상 목록, 횟수 기록 대상 / `backup.ts` 기록 백업 파일 만들기와 검증
- 루트의 `01_download.py`, `02_inspect.py`, `03_audit.py`: DDXPlus 다운로드, 구조 확인, 통계 감사 (연구 트랙)
- `scripts/`: 실행, 설치, 모바일 HTTPS, 임시 터널, 저장소 감사와 정리, 팀 저장소 올리기(`sync_team_repo.ps1`)용 PowerShell 스크립트

## 4. 지금까지 진행한 작업 (feature/stt-rebuild)

1. STT 1차 기능: 로컬 Whisper 연동, 브라우저 WebM 코덱 허용, 녹음 중 실시간 자막
2. 증상 추출 v1: 지원 증상 7개(두통, 발열, 기침, 호흡곤란, 가슴 답답함, 복통, 구토)
   - 있음과 없음, 확인되지 않음을 구분하고 원문 근거를 남긴다.
   - 시작 시점, 정도(반복 표현 포함), 복용약, 알레르기, 숫자 통증 점수를 뽑는다.
   - 시간과 정도는 가장 가까운 증상에만 연결한다.
   - 지원하지 않는 표현은 "자동으로 정리하지 못한 표현"으로 따로 보여준다.
3. 기록 기능: 사용자가 확인한 기록을 브라우저에 저장, 증상 그룹 분리와 삭제, 에피소드 묶음, 변화 타임라인
4. 증상 경과: 좋아짐, 나빠짐, 사라짐 표현 인식. 빈도는 구토에만 기록했다(2026-10-01부터 설사도 기록).
5. 진료 전 요약: PDF와 QR로 공유한다. 기록 그룹을 바꾸면 QR을 지운다.
6. 최근 수정: 같은 기록이 두 번 저장되거나 그룹 없이 저장되는 문제를 막았다(`f06d3cf`).
7. 개발 환경: HTTP 데스크톱 모드, 모바일 HTTPS, 원격 시험용 임시 터널, 저장소 감사와 정리 스크립트
8. 2026-10-01 증상 추출 확장 (상세: docs/INTAKE_EXTRACTION.md)
   - 지원 증상 7개 → 21개: 흉통, 인후통, 콧물, 코막힘, 가래, 오한, 근육통, 요통, 어지러움,
     메스꺼움, 설사, 변비, 발진, 피로 추가
   - 과거력(`medical_history`): 정해진 질환 이름 + 있다/진단/앓다, 수술 경험. 부정하면 제외
   - 발열에 체온(`38.5℃`) 기록, 횟수는 구토와 설사에 기록
   - 버그 수정: `열흘`·`해열제`·`열심히`를 발열로 잡던 문제, `하루 3번`의 `하루`를 시작 시점 `1일`로 잡던 문제
   - 미인식 표현을 문장 전체가 아니라 해당 부분만 보여준다
9. 2026-10-01 진료 전 화면 보완
   - 증상 직접 추가와 삭제(이름이 비면 저장 막음), 복용약·알레르기·과거력 직접 수정
   - 요약, PDF/QR 글, 저장 기록에 과거력 표시
   - 전체 기록 백업 파일(JSON) 내보내기와 가져오기. 같은 id 기록은 건너뛴다. 서버로 보내지 않는다.
10. 2026-10-02 합성어·구어 인식 확장 (상세: docs/INTAKE_EXTRACTION.md)
   - 지원 증상 21개 → 32개: 두근거림, 저림, 소화불량, 속쓰림, 식욕부진, 불면, 부종, 귀 통증, 눈 통증, 치통, 식은땀
   - `머리통증`·`허리 통증` 같은 부위+통증, `목감기`·`코감기`·`배탈`·`위경련`·`체했어요`, `숨이 가빠요`, `몸이 무거워요`
   - `살살`·`쿡쿡`·`욱신욱신`·`엄청` 같은 꾸밈말이 사이에 있어도 인식
   - 버그 수정: `두통약`·`기침약`·`설사약`·`변비약`을 증상 있음으로 잡던 문제
   - 미인식 경고 신호어 확대: `감기에 걸렸어요`, `아이가 아파요` 같은 말이 경고 없이 사라지지 않게 함
11. 2026-10-02 주어 이어받기와 경고 증상 확장 (상세: docs/INTAKE_EXTRACTION.md)
   - `가슴이 답답하고 아파요`처럼 주어 없는 뒷부분은 앞 절의 주어를 이어받아 흉통도 찾는다. `많이`, `지금은`은 주어로 보지 않는다
   - 지원 증상 32개 → 49개: 가려움, 시야 이상, 떨림, 이명, 코피, 객혈, 토혈, 혈변, 혈뇨, 배뇨통, 빈뇨, 기절, 마비, 말 어눌함, 쉰 목소리, 체중 감소, 경련
   - 피부 가려움은 발진에서 분리해 가려움으로 기록한다
   - 과거력: `위염으로 진단받았어요`처럼 목록 밖 병명도 기록. 녹내장, 대상포진 등 질환 이름 추가, `대상포진을 앓았어요`의 `을`도 인식
   - 버그 수정: 같은 증상이 문장에 두 번 나오면 두 번째 표현을 미인식으로 보여주던 문제
12. 2026-10-02 불확실한 말, 다른 사람 증상, 위험 증상 안내 (상세: docs/INTAKE_EXTRACTION.md)
   - 증상 상태에 `uncertain`(확실하지 않음) 추가. `잘 모르겠어요`, `같기도 하고` 등. 원인을 모르겠다는 말은 제외
   - `남편도 기침을 해요`, `엄마가 고혈압이 있어요`는 환자 증상·과거력이 아니라 `others_symptoms`로 분리. 화면에서 본인 증상으로 옮길 수 있음
   - 위험 증상(흉통, 객혈, 토혈, 혈변, 기절, 마비, 말 어눌함, 경련, 심한 호흡곤란·두통·복통)이 있으면 확인 화면과 요약에 119·응급실 안내
   - 마침표 없는 STT 문장도 `~요` 뒤와 `근데`·`그런데`·`그래서`에서 절을 나눈다
   - 버그 수정: `기침을 안 해요`·`설사를 안 했어요`(을/를 + 부정)를 있음으로 잡던 문제, `아이고 머리야`의 두통을 놓치던 문제

## 5. 실행 방법

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_api.ps1        # 처음 한 번
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_api.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_web_desktop.ps1  # http://127.0.0.1:5173
```

- 휴대폰 시험: docs/MOBILE_TEST.md, docs/TEMPORARY_REMOTE_TEST.md
- 모델, 가상환경, 캐시는 Git에서 제외한 `local-cache/`와 `apps/api/.venv`에 둔다. (LOCAL_STORAGE_PLAN.md)

## 6. 테스트 결과 (2026-10-01 실행)

### API 테스트: 통과

```powershell
cd apps\api
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

- 결과: **260 passed, 1 warning** (2026-10-02 불확실·다른 사람 처리 후). 경고 증상 확장 후 242, 합성어 확장 후 192, 2026-10-01 확장 후 143, 그 전 99였다.
- 경고: `StarletteDeprecationWarning`. `starlette.testclient`에서 `httpx`를 쓰는 방식이 deprecated라는 내용이다. 테스트 결과에는 영향이 없다.
- 테스트 파일: `test_api.py`, `test_intake.py`, `test_intake_combinations.py`, `test_intake_scenarios.py`, `test_intake_expanded.py`
- 기존 테스트 2개를 고쳤다. "허리 통증, 어지러움, 설사, 발진은 지원하지 않는다"를 확인하던 테스트로,
  이제 지원하므로 손 저림, 눈 침침함, 두근거림처럼 아직 지원하지 않는 표현으로 바꿨다.

### 웹 빌드: 성공

```powershell
cd apps\web
corepack pnpm build   # 이 PC에는 pnpm이 PATH에 없어 corepack으로 pnpm 11.19.0을 실행했다
```

- 결과: **성공 (exit code 0)**. `tsc -b`와 vite v8.3.1 빌드를 모두 통과했다. 모듈 49개, JS 268.89 kB(gzip 84.80 kB).
- 빌드 결과물 `dist/`는 Git에서 제외되어 있다. 빌드 후 `git status`에 변경 사항이 없었다.
- 2026-10-01 화면 보완 후 다시 빌드: 성공. JS 275.22 kB(gzip 86.62 kB). 테스트 파일도 `tsc -b` 타입 검사 대상이다.

### 웹 단위 테스트: 통과 (2026-10-01 추가)

```powershell
cd apps\web
corepack pnpm test   # vitest run
```

- 결과: **6 files, 31 tests passed** (2026-10-02)
- 대상: `buildTimeline`, `buildSymptomEpisodes`, `buildVisitSummary`, `visitSummaryText`, `backup.ts`, `symptomOptions.ts`(위험 증상 판정 포함)
- 아직 자동 테스트하지 않은 것: `recordStorage.ts`(IndexedDB), `recordGroups.ts`(localStorage), `App.tsx` 화면

### PC 브라우저 수동 확인 (2026-10-01, Chrome, 텍스트 입력)

- 확인한 것: 새 증상 인식(인후통·발열 38.5℃·설사 하루 3회), 과거력 `고혈압`, 미인식 표현 `손이 저려요.`만 표시,
  증상 직접 추가, 이름이 비면 저장 차단, 알레르기 직접 수정, 저장 후 요약에 과거력 표시
- 시험용으로 만든 기록 묶음은 확인 후 삭제했다. 기존 기록 묶음은 건드리지 않았다.
- 확인하지 않은 것: 백업 내보내기/가져오기 버튼 실제 동작(파일 다운로드·선택 창이 필요해 단위 테스트로만 확인), 음성 입력, 휴대폰 화면

### PC 브라우저 수동 확인 (2026-10-02, Chrome, 텍스트 입력, 저장하지 않음)

- 문장 `어제부터 가슴이 답답하고 아파요 열이 있는 것 같기도 하고 잘 모르겠어요 남편도 기침을 해요`
  → 가슴 답답함·흉통 있음, 발열 확실하지 않음, 남편 기침은 따로 표시, 흉통 위험 증상 안내 표시
- `본인 증상으로 옮기기`를 누르면 기침이 환자 증상으로 옮겨지는 것을 확인했다.
- 진료 전 요약의 위험 증상 안내는 기존 기록 묶음의 심한 복통으로 표시되는 것을 확인했다.

### 실제 기기 확인 (기존 문서 기준, 이번에 다시 확인하지 않음)

- PC 브라우저: 실제 목소리 한국어 변환과 의료 테스트 문장 5개 인식을 확인했다. (PROJECT_STRUCTURE.md)
- iPhone Safari: 로컬 HTTPS, 마이크 녹음, 음성 변환을 확인했다. (PROJECT_STRUCTURE.md)
- 지원 증상 7개가 화면에서 구조화되는 것을 2026-09-30에 확인했다. (docs/INTAKE_EXTRACTION.md)
- Android Chrome: **아직 확인하지 않았다.**

## 7. 남은 작업과 주의점 (STT 재구축 트랙)

- [ ] Android Chrome에서 실제 확인
- [x] 웹 자동 테스트 1차: Vitest 5.0.3을 도입하고 순수 함수 테스트 13개를 추가했다. (2026-10-01)
- [ ] 웹 테스트 확장: `recordGroups.ts`, `recordStorage.ts`(jsdom 또는 fake-indexeddb 필요), 화면 테스트
- [x] `apps/web/package.json`의 `latest` 버전을 지금 설치된 버전으로 고정했다. (2026-10-01)
      react/react-dom/@types 19.3.0, @vitejs/plugin-react 6.1.1, typescript 7.0.2, vite 8.3.1. lockfile은 specifier만 바뀌었다.
- [x] docs/INTAKE_EXTRACTION.md의 저장 설명을 IndexedDB 저장 기준으로 고쳤다. (2026-10-01)
- 주의: `apps/web/node_modules`는 `local-cache/pnpm-store`와 연결되어 있다. pnpm 기본 store와 경로가 달라
  `pnpm add/install`에서 `ERR_PNPM_UNEXPECTED_STORE`가 나면 `--store-dir ../../local-cache/pnpm-store`를 붙인다.
- [ ] 기록은 브라우저에만 있다(백업 파일로 옮길 수는 있음). 서버나 PatientState 연동과 진단 엔진은 아직 없다.
      서버 저장은 docs/PRIVACY.md 원칙(서버에 보관하지 않음)을 바꿔야 하므로 사용자 결정이 필요하다.
- [ ] 백업 내보내기/가져오기를 실제 브라우저에서 한 번 눌러 확인
- [ ] 증상 추출 남은 한계 (2026-10-02 기준)
      - 규칙 기반이라 49개 목록에 없는 증상은 확인 요청으로만 보여준다(혀 통증, 입안 헐음, 발가락 통증 등).
      - 띄어쓰기 없이 주어가 생략된 긴 문장(`가슴이답답하고아파요`)은 앞 절 주어 이어받기를 하지 않는다.
      - 과거력은 정해진 질환 이름이나 `OO 진단을 받았어요` 형태만 인식한다.
      - 주어를 이어받아 찾은 증상(`가슴이 답답하고 아파요`의 흉통)은 앞 절의 시작 시점(`어제부터`)을 물려받지 않는다.
      - 위험 증상 기준은 일반적인 응급 신호를 참고해 정한 것으로, 의료진 검토를 받지 않았다.
      - 해결함: 주어 없이 이어지는 뒷부분(`가슴이 답답하고 아파요` → 가슴 답답함 + 흉통), 경고 증상 17개 추가,
        `위염으로 진단받았어요` 같은 목록 밖 병명 기록
- 진료 중/후 기능은 **보류**한다(사용자 결정, 2026-10-02). 구현 방식을 팀원과 아직 합의하지 않았고, 진료 전 단계를 먼저 완성한다.
  2026-10-02에 DDXPlus 기반 설계 초안(`apps/api/app/knowledge/catalog.py`)을 만들다가 중단하고 삭제했다.
- [ ] 테스트의 `StarletteDeprecationWarning` 정리 여부 검토
- [x] `feature/stt-rebuild`를 main에 병합했다 (2026-10-02, fast-forward). 팀원 코드 통합 방식은 아직 정하지 않았다.

## 8. 팀원 코드베이스 통합 트랙

상세: TEAM_PROGRESS_REVIEW_2026-09-29.md

- 팀원은 별도 코드베이스에서 DDXPlus 진단 엔진, Information Gain 기반 다음 질문, PatientState와 세션 API,
  한국어 mapper, Whisper STT, Clinical Summary, HTTPS 데모 등을 구현했다고 보고했다.
  팀원 보고의 마지막 master 병합 커밋은 `ebc854f`다.
- 이 코드는 공용 저장소에서 **아직 확인하지 못했다.** 그래서 구현 내용과 테스트 수치(backend 244, frontend 217 등)는
  **팀원 보고 상태**로만 다룬다.
- 다음 할 일(검토 문서 Phase 0~1):
  - [x] 팀원 저장소 확인 (2026-10-02): https://github.com/KYU-SW/Medmap (공개, main 1개, 커밋 2개 `4f69e8b`·`87a0cf8`).
        원본 개발 저장소 이력(`08cbbd3`, `fb2d7f0`)은 들어 있지 않다. 코드는 `MedMap/code/`. 테스트 수치(백엔드 404, 프런트 293)는 README 기준이며 직접 실행하지 않았다.
  - [ ] 실행 및 테스트 명령 확보
  - [ ] STEP16B/17A 재현 자료 확보
  - [ ] 공용 저장소에 통합 브랜치 생성
  - [ ] 전체 테스트를 한 번 다시 실행
- 현재 `feature/stt-rebuild`의 STT와 증상 추출은 팀원 구현과 기능이 겹친다. 통합할 때 무엇을 남길지 결정해야 한다.

## 9. DDXPlus 연구 트랙

상세: README.md, RESULTS.md, 04_partial_observation_design.md, TEAM_PROGRESS_REVIEW_2026-09-29.md

- 완료: DDXPlus 영문 v2 공식 파일 5개 다운로드와 MD5 검증(`01_download.py`), 구조 확인(`02_inspect.py`),
  전체 통계와 split 중복 감사(`03_audit.py`), 부분 관찰 실험 설계 문서
- 원본 데이터는 `data/`에 있고 Git에서 제외되어 있다.
- 미완료 (검토 문서 Phase 3, 캡스톤 연구 핵심):
  - [ ] 자연 발생 working diagnosis의 correct/incorrect 구성
  - [ ] 현재 진단의 불일치 탐지기
  - [ ] 낮은 오경보율에서의 오류 탐지율
  - [ ] DDXPlus와 독립적인 외부 의료지식 매핑
- 지금 보류한 항목: Galaxy Watch / Health Connect, 실제 의료데이터와 임상 검증, 증거함 전체 구현,
  완전한 회복 모드, 복잡한 의사용 대시보드

## 10. 개인정보 원칙

docs/PRIVACY.md 원문 기준:

- 음성은 요청을 처리하는 동안만 사용한다.
- 원본 음성을 데이터베이스, 로그, Git 저장소에 저장하지 않는다.
- 변환된 문장도 사용자가 확인하기 전에는 환자 기록에 저장하지 않는다.
- 사용자가 확인한 기록은 현재 브라우저의 IndexedDB에만 저장하고 서버로 보내 보관하지 않는다.
- 다른 브라우저나 기기에는 기록이 자동 동기화되지 않는다.
- 사용자는 저장된 개별 기록을 화면에서 삭제할 수 있다.
- 파일명, 오류 종류, 처리 시간처럼 내용이 없는 운영 정보만 기록한다.
- 개발용 테스트 음성에는 실제 환자 정보나 개인식별정보를 넣지 않는다.
- 실제 배포 전에 보관 기간, 접근 권한, 삭제 방식과 사용자 동의 문구를 별도로 검토한다.

## 11. 참고 문서

README.md · PROJECT_STRUCTURE.md · docs/STT_SPEC.md · docs/INTAKE_EXTRACTION.md · docs/PRIVACY.md ·
docs/MOBILE_TEST.md · docs/TEMPORARY_REMOTE_TEST.md · LOCAL_STORAGE_PLAN.md · FILE_MANAGEMENT.md ·
RESULTS.md · 04_partial_observation_design.md · TEAM_PROGRESS_REVIEW_2026-09-29.md

## 12. AI 작업 규칙

- 작업을 시작할 때 HANDOFF.md와 `git status`를 먼저 확인한다.
- HANDOFF.md와 실제 코드나 Git 상태가 다르면 실제 코드와 Git을 따른다.
- 작업을 마칠 때 변경한 파일, 한 일, 테스트 결과, 남은 작업을 HANDOFF.md에 갱신한다.
- 끝내지 못한 작업을 완료했다고 기록하지 않는다.
- 사용자가 요청하지 않으면 `git commit`과 `git push`를 하지 않는다.
- 프로젝트 원본, 데이터, 설정 파일을 마음대로 삭제하지 않는다.
- 정리나 삭제가 필요하면 삭제할 후보를 먼저 사용자에게 보여주고, 승인을 받은 뒤 삭제한다.
