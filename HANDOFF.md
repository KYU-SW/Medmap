# MedMap 작업 인계 (HANDOFF)

작성일: 2026-10-01
브랜치: `feature/stt-rebuild`
마지막 커밋: `22aae26` Add AI handoff and agent instructions

## 1. 프로젝트 개요

MedMap은 환자가 말한 증상과 시간에 따른 변화를 연결하고, 현재 진단과 중요한 정보가
서로 맞지 않는 부분을 다시 확인하도록 돕는 진단 안전망 프로젝트다.
(상세: README.md, PROJECT_BRIEF.txt)

## 2. Git 상태 (2026-10-01 확인)

- 현재 브랜치 `feature/stt-rebuild`는 `origin/feature/stt-rebuild`와 같다(마지막 커밋 `22aae26`).
- HANDOFF.md와 AGENTS.md는 `22aae26`에서 커밋했다.
- 2026-10-01: Claude Code용 작업 규칙 파일 `CLAUDE.md`를 추가하고 이 HANDOFF.md의 Git 상태를 갱신했다.
  이 두 변경은 아직 커밋하지 않았다.
- main(`1feda4b`, 2026-09-28)보다 커밋 46개 앞서 있다. 아직 main에 병합하지 않았다.
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
- 루트의 `01_download.py`, `02_inspect.py`, `03_audit.py`: DDXPlus 다운로드, 구조 확인, 통계 감사 (연구 트랙)
- `scripts/`: 실행, 설치, 모바일 HTTPS, 임시 터널, 저장소 감사와 정리용 PowerShell 스크립트

## 4. 지금까지 진행한 작업 (feature/stt-rebuild)

1. STT 1차 기능: 로컬 Whisper 연동, 브라우저 WebM 코덱 허용, 녹음 중 실시간 자막
2. 증상 추출 v1: 지원 증상 7개(두통, 발열, 기침, 호흡곤란, 가슴 답답함, 복통, 구토)
   - 있음과 없음, 확인되지 않음을 구분하고 원문 근거를 남긴다.
   - 시작 시점, 정도(반복 표현 포함), 복용약, 알레르기, 숫자 통증 점수를 뽑는다.
   - 시간과 정도는 가장 가까운 증상에만 연결한다.
   - 지원하지 않는 표현은 "자동으로 정리하지 못한 표현"으로 따로 보여준다.
3. 기록 기능: 사용자가 확인한 기록을 브라우저에 저장, 증상 그룹 분리와 삭제, 에피소드 묶음, 변화 타임라인
4. 증상 경과: 좋아짐, 나빠짐, 사라짐 표현 인식. 빈도는 구토에만 기록한다.
5. 진료 전 요약: PDF와 QR로 공유한다. 기록 그룹을 바꾸면 QR을 지운다.
6. 최근 수정: 같은 기록이 두 번 저장되거나 그룹 없이 저장되는 문제를 막았다(`f06d3cf`).
7. 개발 환경: HTTP 데스크톱 모드, 모바일 HTTPS, 원격 시험용 임시 터널, 저장소 감사와 정리 스크립트

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

- 결과: **99 passed, 1 warning (0.48s)**
- 경고: `StarletteDeprecationWarning`. `starlette.testclient`에서 `httpx`를 쓰는 방식이 deprecated라는 내용이다. 테스트 결과에는 영향이 없다.
- 테스트 파일: `test_api.py`, `test_intake.py`, `test_intake_combinations.py`, `test_intake_scenarios.py`

### 웹 빌드: 성공

```powershell
cd apps\web
corepack pnpm build   # 이 PC에는 pnpm이 PATH에 없어 corepack으로 pnpm 11.19.0을 실행했다
```

- 결과: **성공 (exit code 0)**. `tsc -b`와 vite v8.3.1 빌드를 모두 통과했다. 모듈 49개, JS 268.89 kB(gzip 84.80 kB).
- 빌드 결과물 `dist/`는 Git에서 제외되어 있다. 빌드 후 `git status`에 변경 사항이 없었다.
- 웹 자동 테스트는 아직 없다. 빌드에서는 타입 검사와 번들 생성만 확인한다.

### 실제 기기 확인 (기존 문서 기준, 이번에 다시 확인하지 않음)

- PC 브라우저: 실제 목소리 한국어 변환과 의료 테스트 문장 5개 인식을 확인했다. (PROJECT_STRUCTURE.md)
- iPhone Safari: 로컬 HTTPS, 마이크 녹음, 음성 변환을 확인했다. (PROJECT_STRUCTURE.md)
- 지원 증상 7개가 화면에서 구조화되는 것을 2026-09-30에 확인했다. (docs/INTAKE_EXTRACTION.md)
- Android Chrome: **아직 확인하지 않았다.**

## 7. 남은 작업과 주의점 (STT 재구축 트랙)

- [ ] Android Chrome에서 실제 확인
- [ ] 웹 자동 테스트 추가
- [ ] `apps/web/package.json`의 react, vite, typescript 버전이 `latest`라 재현성이 낮다.
- [ ] docs/INTAKE_EXTRACTION.md에는 "확인 버튼을 눌러도 아직 서버나 PatientState에 저장하지 않는다"고 적혀 있다.
      지금은 확인한 기록을 브라우저 IndexedDB에 저장하므로(docs/PRIVACY.md) 문서를 고쳐야 한다.
- [ ] 기록은 브라우저에만 있다. 서버나 PatientState 연동과 진단 엔진은 아직 없다.
- [ ] 테스트의 `StarletteDeprecationWarning` 정리 여부 검토
- [ ] `feature/stt-rebuild`를 main에 언제 병합할지 결정

## 8. 팀원 코드베이스 통합 트랙

상세: TEAM_PROGRESS_REVIEW_2026-09-29.md

- 팀원은 별도 코드베이스에서 DDXPlus 진단 엔진, Information Gain 기반 다음 질문, PatientState와 세션 API,
  한국어 mapper, Whisper STT, Clinical Summary, HTTPS 데모 등을 구현했다고 보고했다.
  팀원 보고의 마지막 master 병합 커밋은 `ebc854f`다.
- 이 코드는 공용 저장소에서 **아직 확인하지 못했다.** 그래서 구현 내용과 테스트 수치(backend 244, frontend 217 등)는
  **팀원 보고 상태**로만 다룬다.
- 다음 할 일(검토 문서 Phase 0~1):
  - [ ] 팀원 저장소 URL, 브랜치, 커밋 확인
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
