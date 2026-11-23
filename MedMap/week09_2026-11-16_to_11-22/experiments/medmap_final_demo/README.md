# MedMap 근거 추적 시제품 (최종발표 시연용, 합성 환자)

의사가 지정한 진단 가설에 대해, 새 의료 근거의 출처·상태·이용 가능 시각·중복·정정을 검사하고 유효한 근거만 기존 연구 모델(EXP-MAI-006 D)에 넣어 근거별 연구용 점수를 내며, 과거 시점 재생과 변경 이력을 보여준다. 진단을 확정하지 않는다.

## 환경
- `~/ai_env`(Python 3.12, scikit-learn·numpy·pandas·joblib 기설치). 신규 패키지·외부 API·네트워크 없음.
- D 모델: EXP-MAI-008 봉인 저장본 `~/medmap_er_reason_ordinal_sealed/s1_20261113_01/models/fold0.joblib`(sha256 고정 대조). 다른 위치면 환경변수 `MEDMAP_D_MODEL_RUN_DIR`. 모델이 없으면 화면·출력이 MODEL_UNAVAILABLE 로 동작(가짜 점수 없음).

## 실행
```bash
cd ~/medmap-worktrees/main-ai/exp/medmap_final_demo
~/ai_env/bin/python -B -m unittest discover -s tests          # 자동 테스트(37개)
cd src
~/ai_env/bin/python -B server.py 8765 --compare 20261116_01       # 시연 화면 → 브라우저 http://127.0.0.1:8765/
~/ai_env/bin/python -B server.py 8765 --no-model            # 모델 없음 상황 시연
~/ai_env/bin/python -B run_compare.py <새 RUN_ID>            # 비교 실험(같은 RUN_ID 덮어쓰기 거부)
~/ai_env/bin/python -B run_demo.py <새 RUN_ID>               # 시연 단계 계산 저장
```
`?step=N`(1~7)으로 특정 단계를 바로 열 수 있다. 서버는 127.0.0.1 에만 연결된다.

## 실제 구현 기능(이번 실행에서 동작 확인)
- 추가 전용 사건 저장소와 수집 거부(잘못된 시각·필드 누락·잘못된 상태·빈 근거·자기 정정·같은 ID 다른 내용) — `medmap_demo/events.py`
- REPLAY(as_of): 도착·공개 시각 이중 필터, 계보별 유효 버전 선택, 중복·정정·취소·무효·출처·환자·가설 연결 검사와 사유 코드 — `medmap_demo/replay.py`
- 평가 보류와 0점 분리, 모델 없음 처리, 근거별 독립 연구용 점수, 변경 diff·결정론적 설명, 기록 제외 비교, 출처 그래프 — `medmap_demo/assess.py`
- 기존 D 모델 읽기 전용 연결(겹 0 고정, sha256 대조) — `medmap_demo/model_adapter.py`
- 시연 화면 4개 영역(환자·가설 / 시간순 근거 / 근거 상태와 연구용 점수 / 기술 검증) — `src/server.py`, `web/index.html`
- 비교 실험 BASE vs MEDMAP — `src/run_compare.py`

## 시연 절차
1. `server.py 8765 --compare 20261116_01` 실행 후 브라우저에서 http://127.0.0.1:8765/
2. '시연 자동 실행'(단계마다 4.5초) 또는 단계 버튼을 순서대로: 검사 요청 → 결과 대기 → D-dimer 결과 이용 가능 → CT 예비 판독 → 늦은 기록 도착 → CT 판독 정정 → 과거 시점 재생(CT 예비 판독 시점)
3. 각 단계에서 2번(도착한 기록·역할), 3번(사용·보류·제외와 사유, 연구용 점수, 이전 조회 대비 변화), 4번(미래 기록 차단·과거 재생 일치·순서 무관·보류 점수 없음 등 실제 계산 결과) 확인
4. 사용 근거 카드의 '이 기록 빼고 다시 계산'으로 기록 제외 비교(기술 검사)
5. `--no-model` 로 다시 띄워 MODEL_UNAVAILABLE 처리 확인

## 남은 제한 사항
- 합성 환자만. 실제 진료자료·임상 성능 NOT_EVALUATED.
- 비교 실험은 같은 작성자가 만든 생성기 정답과의 '규칙 해석 일치 검사' — 독립 정답 아님. BASE 는 흔한 구현 실수를 모아 의도적으로 약하게 정의한 기준선(효과 크기 아님).
- 생성기 밖 사유(CONFLICTING_VERSIONS, LINEAGE_INVALID(순환·이전 버전 누락·계보 간 정정), PATIENT_ID_CONFLICT, EVIDENCE_INVALID, NOT_LINKED_TO_HYPOTHESIS, NEWER_VERSION_NOT_YET_AVAILABLE, NEWER_VERSION_TIME_UNKNOWN)는 단위 테스트에서만 검증. 생성기 kind 는 LAB 단일.
- 조회는 경계 시각 집중 격자이고 같은 환자 조회끼리 독립이 아님. F(재생 불일치)=0 은 MEDMAP 이 도착 시각으로 먼저 거르므로 설계상 보장되는 값.
- D 모델(EXP-MAI-006, ER-REASON 학습, 원래 정확 일치 약 0.41)의 합성 영어 문장 점수는 의학적 타당성이 검증되지 않았다. CT 판독이 '폐색전증 없음'(예비, CT-R1) → '폐색전증과 일치'(정정, CT-R2)로 바뀌어 사용 버전이 바뀌었지만, D 모델 점수는 -2 → -2로 같았다.
- 지식그래프: 관계 8개 중 임상의 검증 0개(NO_VERIFIED_RELATION) → 그래프 관계로 판단을 만들지 않음.
- 가설 연결은 시나리오가 지정한 태그이며 엔진이 의학적으로 판정하지 않는다.
- 시연 화면 렌더링은 로컬 Chromium 헤드리스 스크린샷(1280·768·375 폭)으로 확인 — `outputs/screenshots_20261116_01/`(SHA256SUMS.txt). Playwright MCP 브라우저는 설치돼 있지 않음(다운로드 안 함).
- 문서: TECHNICAL_DESIGN.md(구조·재사용 목록), VALIDATION_RESULTS.md, FINAL_PRESENTATION_BRIEF.md, logs/FAILURE_LOG.md(실패·수정 기록)
