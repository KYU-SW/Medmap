# EXP-SN-RAG-001 사전등록 초안 rev0 — Frozen Local Medical RAG 검색 자체 평가 (Stage R)

- 작성 2026-10-02 · 브랜치 `research/safety-net-rag`
- 상태: **초안.** RG manifest 생성·`/rg-gate` 실행 0 · 임베딩·색인·검색 구현 0 · 질의 작성 0 · 판정 0 · 환자 데이터 접근 0
- 범위: **Stage R(검색 자체)만.** Safety-Net 가치(Stage S: B0·B1·K·R·K+R 비교)는 별도 사전등록
- `PROPOSED` = 결과 전 고정 제안값, 사용자 확인 필요 · `CONFIRM_NEEDED` = 미정

## 0. 주장 한계
- 주장 가능 범위: "동결 corpus `rag-chestpain-v0`와 이 질의 집합에서, 로컬 오프라인 검색이 근거를 가져오고 근거 없음을 표시하는 정도"
- 주장 금지: 임상 성능 · 오진 탐지 · 진단 정확도 · 제품 적합성 · 다른 corpus로의 일반화
- RAG는 근거 검색만. relation(지지/충돌) 판정·진단 문장 생성 0

## 1. 공개 사항
1. corpus를 사전등록·RG gate **전에** 동결(사용자 지시 2026-10-02). 평가 결과가 없는 상태에서의 동결이므로 사후 선택 편향 없음. design-draft와 prereg-plan의 "RUN 후 C3" 순서와 다름 → RG gate에서 deviation 메모로 제출
2. 출처 선택 시 에이전트와 메인 세션이 라이선스 블록·목차 제목을 열람. 본문 의학 내용은 열람 0. coverage 계산은 어휘 건수만
3. coverage 결과를 이미 봄(§1 coverage.md). 이 결과로 corpus를 바꾸지 않았음. 질의 구성 규칙은 coverage와 무관하게 격자로 고정(§3)
4. 승인 숫자 정정: 사용자 승인 메시지의 "19개" = 이전 보고의 집계 오류, 실제 목록 18건

## 2. Corpus (동결)
| 항목 | 값 |
|---|---|
| corpus_version | `rag-chestpain-v0` (문서 원문 수준 freeze, C5 미착수) |
| manifest | `docs/research/rag/corpus/rag-chestpain-v0.manifest.yaml` SHA-256 `40f0b0b507140de1c2408b72ceec996f2c9fe35fb292a59bb2bb6119de56a1af` |
| 원문 | `~/medmap_rag_corpus/rag-chestpain-v0/` 읽기 전용, SHA256SUMS SHA `4390cf6ad9f011ab446f0e72da0ce9c0eb59dd0bce133575189891cde6d3ee60` |
| 문서 | 18 (TIER1 6 · TIER2 12), 전부 CC BY 또는 CC BY 명시, XML `<permissions>` 재검사 통과 |
| C5 제외 | SRC-0015 `fig#F1` · SRC-0018 `fig#life-12-01606-f003`(제3자 저작물 표시) |
| 공백 | 안정형 협심증 · GERD 자체 = COVERAGE_GAP / 심낭염·심근염·NCCP·공황 = PARTIAL_WEAK |

- C5(chunk·색인) 파라미터는 R-DEV 실행 **전에** 고정하고 `rag-chestpain-v0-c5-<n>`으로 별도 해시. 문서 추가·삭제 = 새 corpus version + 새 사전등록

## 3. 질의 집합 (환자 데이터 0)
- **격자 설계**(corpus 내용을 보고 고르지 않음): WD × 소견
  - WD 10: ACS · 안정형 협심증 · PE · 심낭염 · 심근염 · 기흉 · GERD · 공황 · 급성 대동맥 증후군 · 식도 파열 (사용자 범위 + OOS)
  - 소견: EXP-SN-001 prereg §9 C7 관측 가능 항목(질문 사전 E_xx 문구, 질환 연결 없음) — 약 35개
  - 격자 ≈ 350 쌍 → `sha256("ragR01|"+pair_id)` 순서로 **200쌍 표본**(PROPOSED)
- **대조 질의(설계상 근거 없음)**: 흉통 범위 밖 WD(예: 중이염·방광염 등 49질환 중 비흉통군) × 같은 소견, 50개(PROPOSED). 목적 = 억지 근거 검사
- 질의 문장 = 결정적 템플릿(한국어·영어 각 1개). LLM 질의 재작성 0
- 금지: DDXPlus 환자 행 · STEP13B·STEP17A 사례 · 평가 결과 · 시뮬레이터 질환→소견 정의
- 분할: `sha256("ragR01split|"+query_id)` 앞 8자리 정수 %10 → 0–3 R-DEV · 4–9 R-TEST

## 4. 정답(gold) 판정
- pooling: 비교 시스템 S1·S2·S3(§5) 상위 10 합집합 구절
- 판정: 구절마다 `relevant / partially_relevant / not_relevant` + 정보 종류(`history / exam / ecg / lab / imaging / measurement / other`)
- answerable = relevant 구절 ≥1. unanswerable = pool 안에 relevant 0(격자 질의) + 대조 질의 전체
- 판정자 = **CONFIRM_NEEDED(B-AUTH-R)**. 조건: 질의 작성자 ≠ 판정자, 시스템 이름·순위 미표시(pool 순서 무작위), 20% 이중 판정 → kappa 보고
- 작업량 추정: 250 질의 × pool 최대 30 ≈ 7,500 판정(상한). 실제는 중복 제거 후 감소

## 5. 비교 시스템 (구성은 C5 동결 시 고정)
| ID | 구성 | 역할 |
|---|---|---|
| S1 | SQLite FTS5 BM25 | 기준선 |
| S2 | S1 + 로컬 dense(1순위 KURE-v1, CPU 사전 계산) + FAISS exact + RRF | 주 시스템 |
| S3 | S2 + bge-reranker-v2-m3 | ablation |

- 모델·라이브러리 버전·가중치 SHA는 설치 승인(D-INSTALL) 후 manifest에 기록
- 근거 없음 출력 `UNKNOWN` 임계 τ_abstain은 R-DEV에서만 고정

## 6. Endpoint
| 구분 | 지표 | 기준(PROPOSED) |
|---|---|---|
| **Primary 1** | S2 source recall@10 (R-TEST answerable) | 점추정 ≥ 0.80, 95% CI 하한 ≥ 0.70 |
| **Primary 2** | S2 unsupported retrieval rate (R-TEST unanswerable: `EVIDENCE_FOUND` 비율) | 점추정 ≤ 0.20, 95% CI 상한 ≤ 0.30 |
| Gate | provenance accuracy(반환 구절 = 원문 오프셋 바이트 일치 + chunk 해시) | 100% |
| Gate | determinism(같은 질의 5회 + 프로세스 재시작 3회, 순위·점수 동일) | 100% |
| Gate | offline(`unshare -rn` 실행 성공 + 외부 연결 시도 0, 양성 대조 실패 확인) | 통과 |
| Secondary | passage recall@10 · nDCG@10 · MRR · abstention precision/recall · 정보 종류별 recall · 범위별 recall · 한국어 vs 영어 질의 차 · S2−S1·S3−S2 쌍대 차 · 지연 p50/p95(CPU/GPU, warm/cold) | 기술 통계 |

- 판정: Primary 1·2와 Gate 전부 통과 → `RAG_RETRIEVAL_GO`(Stage S 사전등록 진행 가능). 하나라도 실패 → `NO_GO` 또는 `PARTIAL`(실패 항목 명시)
- COVERAGE_GAP 범위(안정형 협심증·GERD) 질의는 answerable 비율이 낮을 것으로 예상 — 범위별 보고, 판정 제외 아님

## 7. 통계
- 단위 = 질의. bootstrap 10,000회(질의 단위 재표집), seed 20261002, percentile 95% CI
- 쌍대 비교(S2 vs S1 등) = 같은 질의 차이의 bootstrap. 다중 비교는 secondary라 보정 없이 기술만
- 최소 표본(PROPOSED): R-TEST answerable ≥ 100, unanswerable ≥ 50. 미달 시 판정 보류(`INSUFFICIENT_N`), 질의 추가는 새 salt로만

## 8. 제외·결측
- 사전 규칙만: 템플릿 생성 실패 · 판정자 판정 불가(`cannot_judge`) → 제외 수 보고
- 사후 제외 0 · 실패 run 삭제 0 · 결과 본 뒤 τ·k·fusion·chunk 변경 = deviation 기록 + exploratory

## 9. 실행 순서 (각 단계 사용자 승인)
1. 사용자 확인: PROPOSED 값 · B-AUTH-R · D-INSTALL
2. `/rg-plan EXP-SN-RAG-001` → `/rg-gate` (EXP-SN-001 기록 미변경 확인)
3. RUN 후: 전용 venv·모델 다운로드 → 해시 기록 → C5 chunk·색인 동결
4. 질의 생성(격자·템플릿) 동결 → pooling → 판정 → gold 동결
5. R-DEV: τ_abstain·k 고정 → R-TEST 1회 → `/rg-verify`(실행 세션과 다른 검증자)

## 10. 미결정
| ID | 내용 |
|---|---|
| B-AUTH-R | gold 판정자 |
| D-INSTALL | venv·모델·라이브러리 설치 승인 |
| P-VAL | §6 기준값 · §3 표본 수 · §7 최소 n |
| D-GAP | 안정형 협심증·GERD 공백을 v1 corpus에서 보강할지(v0는 보강 금지) |
