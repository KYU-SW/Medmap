# EXP-SN-RAG-001 Research Guardian 사전등록 초안 계획 — rev0 (2026-10-02)

- **후속(2026-10-02)**: corpus v0 동결 완료, 사전등록 초안 = `EXP-SN-RAG-001-prereg-draft.md`. 아래 "RUN 후 C3" 순서는 사용자 지시로 변경(초안 §1-1 공개 사항)
- 상태: **계획만.** `rg.py`로 manifest 생성·`/rg-plan`·`/rg-gate` 실행 0. EXP-SN-001 gate·manifest 재사용 0
- 새 ID: `EXP-SN-RAG-001`(Stage R). Stage S는 별도 ID(예: `EXP-SN-RAG-002` 또는 K·R 공동 ID) — D-EVAL 결정 후

## 1. 등록 순서 (승인 후)
1. 사용자 승인: 출처 목록(C2)·D-LIC-ND·D-LIC-NC·B-AUTH-R
2. 이 브랜치에서 `/rg-plan EXP-SN-RAG-001` → `.research-guardian/experiments/EXP-SN-RAG-001/manifest.yaml`(EXP-SN-001 폴더 미변경 확인)
3. `/rg-gate EXP-SN-RAG-001` → RUN이 아니면 문제 목록만 보고
4. RUN 후에만 C3(원문 확보)~C6 및 Stage R 실행. protocol 변경 = `rg.py deviation`

## 2. manifest 필드 초안
| 필드 | 초안 값 |
|---|---|
| research_question | 승인·동결 흉통 corpus에서 로컬 오프라인 검색이 (WD, 소견) 질의에 관련 근거를 가져오고, 근거 없는 질의에 UNKNOWN을 내며, 출처 추적·결정성·오프라인 조건을 만족하는가 |
| hypothesis | H-R1 source recall@10 ≥ τ1 (95% CI 하한) · H-R2 unsupported retrieval rate ≤ τ2 · H-R3 provenance 100% · determinism 100% · offline 0 연결 — **τ1·τ2 미정(결과 전 고정)** |
| dataset | Approved corpus `corpus_version`(C6) + 평가 질의 집합(R-DEV/R-TEST). 환자 데이터 0 |
| unit_of_analysis | 질의 |
| split_strategy | 질의 ID 해시 salt(미정) → R-DEV / R-TEST |
| baseline | P1 lexical BM25 |
| proposed_method | P2 dense, P3 hybrid(RRF) — 구성 동결 후 |
| metrics | design §7.2 |
| statistical_test | 질의 단위 bootstrap 95% CI, 쌍대 비교(P3 vs P1) |
| blind | 질의 작성·gold 판정자는 검색 결과 순위 미열람(pooling 순서 무작위화) |
| leakage 점검 | 질의 집합이 DDXPlus 환자 행·STEP13B·평가 결과·시뮬레이터 질환→소견 정의에서 오지 않았음 |
| exclusions | 질의 제외는 사전 규칙만(예: 번역 실패), 사후 제외 금지 |
| claims_allowed | "이 corpus·이 질의 집합에서의 검색 성능" 한정. 임상 성능·오진 탐지 주장 금지 |

## 3. 예상 reviewer 지적 (사전 대응 후보)
- 질의·gold를 같은 사람이 만들면 순환 → 질의 작성자 ≠ 판정자
- corpus가 작으면 recall이 높게 나옴 → corpus 크기·질의당 관련 구절 수 보고, distractor 문서 포함 여부 결정
- unanswerable 질의 구성 방법이 결과를 좌우 → 구성 규칙 사전 고정
- 결정성은 같은 하드웨어 기준 → CPU·GPU 각각 보고

## 4. 이번에 하지 않은 것
manifest 파일 생성 · gate 실행 · 질의 작성 · gold 판정 · corpus 확보 · 임계값 결정
