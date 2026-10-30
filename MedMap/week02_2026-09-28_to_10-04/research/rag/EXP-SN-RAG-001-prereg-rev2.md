# EXP-SN-RAG-001 사전등록 rev2 — Frozen Local Medical RAG 검색 평가 (Stage R)

- 작성 2026-10-02 · 브랜치 `research/safety-net-rag` · rev1(`EXP-SN-RAG-001-prereg-rev1.md`, b25342e9…)을 대체. RG 1차 심사 NEEDS_FIX(`.research-guardian/audits/EXP-SN-RAG-001/gate/20261002_131455_NEEDS_FIX.md`) 반영본
- 상태: 사전등록(심사 전). 임베딩·색인·검색 구현·실행 0 · 모델 설치·다운로드 0 · 환자 데이터 0 · 검색 성능 숫자 0
- 범위: **검색만.** WD 판정·설명 안 되는 소견·대안 진단·다음 검사·의사 경고 생성 0. structured knowledge(EXP-SN-001) 점수와 혼합 0

## 0. rev1 → rev2 변경 요약 (NEEDS_FIX 6항 + 부수 지적)
| RG 지적 | rev2 조치 | 절 |
|---|---|---|
| 1 퇴화(늘 기권) 통과 | 별도 양성 벤치마크 PRB-v0(102 작성·89 채점) + **능력 Gate B**(end-to-end, 기권=실패) + τ 비퇴화 제약 | §3, §8, §11 |
| 2 CI가 판정에 무효 | Gate A·B 모두 **군집 bootstrap CI 경계 + Wilson 경계**로 판정, 판정 특성 표 공개 | §11, §12 |
| 3 채점·τ 정의 빈칸 | τ 알고리즘·조율 모집단·언어·동점·정규화·중립 처리 전부 명시 | §8, §10 |
| 4 NE 정답 오염 | 사람 감사 표본 40(해시 선택·동결), 범위·용도·판정 연결 고정 | §6 |
| 5 KO/EN 비동등 | 정본→영어→한국어 재번역 + 독립 동등성 검증(152쌍), COVERAGE 한국어 문구 v1 | §5 |
| 6 동결 증거 | 프롬프트 파일·SHA, git commit, freeze manifest | §14 |
| 기타 | 질의 군집 반영, 층별·관계별 보고, claim 범위, 기준선 공정성, DEV 코드 가드, 민감도 분석 | §9–§13 |

## 1. 연구 질문
동결 corpus `rag-chestpain-v0`에서 완전 로컬·오프라인 검색이
- **(Q1 안전)** 근거가 없는 질의에서 억지 근거를 반환하지 않는가 — COVERAGE_ABSTENTION_SET_V0
- **(Q2 능력)** 근거가 있는 질의에서 정답 출처를 기권 없이 상위 5 안에 가져오는가 — POSITIVE_RETRIEVAL_BENCHMARK_V0
- (Q3) 한국어 질의 → 영어 corpus 검색이 영어 질의 대비 유지되는가(검증된 동등 문구 기준)
- (Q4) 출처 추적·결정적 반복·오프라인을 만족하는가
- 두 세트는 **섞지 않고** 각각 판정한다

## 2. 동결 자산 (해시 정본 = freeze manifest `docs/research/rag/freeze/EXP-SN-RAG-001-freeze-rev2.yaml`)
| 자산 | SHA-256(앞 8) |
|---|---|
| corpus v0 manifest / SHA256SUMS | 40f0b0b5 / 4390cf6a |
| addendum-01 / addendum-02 | 1bbdff04 / b3646a43 |
| units-v1 (2,487) | ee072925 |
| COVERAGE: queries-v0 / gt-v0.1 / gt-protocol + amend-01 | f2c4f032 / fa359b2b / 2aae64bc + 파일 |
| COVERAGE 한국어 v1: coverage-xling-v1 | 1915371b |
| PRB: prb-protocol-v0 / amend-01 / prb-v0 | 496e4c46 / 137c7246 / 99fa0370 |
| 번역 쌍 pairs-final-v1 (152) | 61d8c35c |
| 사람 감사 표본 ne-audit-sample-v0 (40) | 2585c2a7 |
| 프롬프트 PRB·번역·C (`prb-work/prompts/PROMPTS.sha256`), gt-v0.1 프롬프트 복원본 | 파일 |

- 라이선스: 18건 전부 CC BY(SRC-0014 = 버전 미기재, 연구 승인·제품 UNCONFIRMED). NC·ND·ESC 관련·불명 제외. 제품 배포 승인 아님
- 색인 제외: SRC-0015 `fig#F1`, SRC-0018 `fig#life-12-01606-f003`(그림·캡션), 뒷부분 절(addendum-02). 영어만(SRC-0001 영어 번역 하위문서)
- 공백(채우지 않음): 안정형 협심증·GERD 자체 = COVERAGE_GAP. 새 출처는 `corpus/v1-candidates.md` 기록만

## 3. 두 평가 세트
### 3.1 COVERAGE_ABSTENTION_SET_V0 (= queries-v0 + gt-v0.1, **변경 0**)
- 질의 400(격자 WD10×소견35 = 350 + 범위 밖 대조 50), 분할 해시 60/40 → DEV 259 / EVAL 141 (rev1과 동일)
- 정답: DEV EP37·NE195(격자161+대조34)·UNSC27 / EVAL EP14·NE115(격자99+대조16)·UNSC12
- 역할: 근거 없음 처리(Q1)·기권·억지 근거 위험. EP 14는 능력 판정에 쓰지 않음
- 한국어 문구: 평가용은 **text_ko_v1**(§5). queries-v0 의 text_ko(v0)는 파일에 보존, 평가 미사용

### 3.2 POSITIVE_RETRIEVAL_BENCHMARK_V0 (PRB-v0, 신규)
- 작성: AUTHOR A(Sonnet 5, 묶음 5)가 corpus 원문만 읽고 "원문이 명시적으로 답하는" 임상 질문 102개(문서별 상한, 15 범주, 어휘 4단어 복사 금지, 근접 중복 금지)
- 검증: VERIFIER B(Opus 5.5) AGREE 79·DISAGREE 19·AMBIGUOUS 4, lexical_ok false 6
- 인용 한 칸 밀림 정정(amend-01): 원인 = 문서 보기 파일 1행 제목 → A가 행 번호를 단위 번호로 기록. B DISAGREE 중 인접 단위가 정답으로 지목된 17건만 새 검증자 C(Opus 5.5, 새 세션)가 정정 단위로 재판정 → AGREE·lexical_ok 15 반영
- 결과: 채점 가능 89 (DEV_POSITIVE 33 / **EVAL_POSITIVE 56**), UNSCORABLE 13(LEXICAL_LEAK 5, B AMBIGUOUS 4, B DISAGREE 2, 정정 실패 2)
- 분할(작성 전 고정): `int(sha256('ragPRB01split|'+pq_id)[:8],16)%100<40` → DEV_POSITIVE, 그 외 EVAL_POSITIVE
- EVAL_POSITIVE 56: 출처 17개(최대 SRC-0001 11 = 20%), 범주 15개 전부, 인용 정정 13(미정정 43)
- 관련성 의미: "해당 단위가 질문에 명시적으로 답함". gold 외 같은 묶음의 다른 답 단위 = 중립. **다른 묶음 문서의 답은 검토되지 않음 → 재현율 과소 방향**
- medical_review_status = UNREVIEWED (전 항목)

## 4. 질의 생성·입력 규칙
- 검색 시스템 입력 = **질의 문자열만**(COVERAGE text_en / text_ko_v1, PRB text_en / text_ko). ID·구조 필드 사용 금지
- 모든 질의·정답은 검색 시스템 부재 상태에서 작성(검색 결과·점수·순위·임베딩 열람 0)

## 5. 한국어/영어 동등성
- 정본 → 영어 → 한국어. PRB: 정본 = 영어 질문(A 작성), 한국어 = TRANSLATOR T(Sonnet 5, 별도 세션). COVERAGE: 영어 = DDXPlus question_en·질환명(변경 없음), 한국어 = T 재번역(UI 안내·괄호 설명 제거 규칙)
- EQUIVALENCE V(Opus 5.5, 별도 세션) 152쌍: 1차 SAME 146 · PARTIAL 6 → T 1회 수정 → V 재판정 SAME 5 · PARTIAL 1(PRB-B2-05, DEV_POSITIVE) → **최종 SAME 151 / 152**
- 교차 언어 분석 포함 = SAME_MEANING 만. PRB-B2-05 는 KO 분석 제외(EN 분석만)
- COVERAGE 한국어 질의 = "작업 진단: {질환 ko}. 환자 소견: {소견 ko}" — 400 전부 구성 문구 SAME. **템플릿 라벨 2개("작업 진단"/"Working diagnosis", "환자 소견"/"Patient finding")는 V 미검증(고정 대응, 공개)**
- 쌍 기록: canonical_id, english_text, korean_text, translation_status(T1/T2_REVISED), verifier_status, pair_hash
- 번역은 검색 결과 열람 전 동결. 이후 수정 금지

## 6. NO_EVIDENCE 정답 오염 사람 감사
- 표본: COVERAGE EVAL 격자 NE 99 → `sha256('ragAUD01|'+canonical_json({query_id}))` 오름차순 앞 **40** (WD 9·소견 26). `eval/audit/ne-audit-sample-v0.tsv` 동결
- 감사자: **사람**(사용자 또는 사용자가 지정한 사람). 의료인 검수 아님
- 보는 것: 질의(영어·한국어) · corpus 문서 보기 파일 · 위치 찾기 도구 `scripts/rag/audit_search.py`(키워드 정규식, 출력만) · 감사 시트. 보지 않는 것: A·B 결과, 검색 결과
- 판정 범위(일반인 가능 범위): 원문에 (WD, 소견) 관계 서술이 실제로 있는가 · 있다면 위치 · 명백한 누락. **임상 해석의 정오는 판정하지 않음 → medical_review_status = UNREVIEWED**
- 결과: NE_CONFIRMED / EVIDENCE_FOUND(unit id) / UNSURE → 오염률 = EVIDENCE_FOUND/40, Wilson 95% CI
- 시점: **EVAL 검색 실행 전 완료 필수**(DEV 진행은 무관). 미완료면 EVAL 실행 금지
- 용도: 정답(gt-v0.1)은 바꾸지 않음. (a) 오염률 보고 (b) EVIDENCE_FOUND 질의를 뺀 Gate A 민감도 (c) **오염률 Wilson 상한 > 0.20 이면 Gate A 결과에 `GT_UNRELIABLE` 표시 → 전체 판정 INCONCLUSIVE_GT**
- 현재 상태: 표본·시트·도구 동결, **감사 미실시**

## 7. 비교 검색 계열 (실행 전 후보만)
| 계열 | 후보 |
|---|---|
| Lexical | BM25(SQLite FTS5 `porter unicode61`, k1=1.2·b=0.75 고정) |
| Dense | bge-m3 · KURE-v1 · multilingual-e5-large (MIT, 로컬, trust_remote_code 불필요 — 카드 기준). 어느 것도 자동 채택 금지 |
| Hybrid | BM25 + Dense, RRF(k=60, 순위 결합) |
| Reranker(선택) | bge-reranker-v2-m3 — DEV 최상위 hybrid 1개에만 |
- 근거: 세 dense 모델 모두 "한국어 의료 질의 → 영어 문헌" 성능 근거 없음(bge-m3는 MKQA 교차 언어 평가 보고, KURE-v1은 한국어 의료 검색만, e5는 단일 언어만) → DEV 실측으로만 선택
- 정확 검색만(FAISS `IndexFlatIP` CPU 또는 동등). ANN 금지. 벡터는 빌드 시 1회 계산·저장·해시, 질의 임베딩 CPU fp32
- Chunking 후보: CH-UNIT(단위=chunk, 50단어 미만은 같은 절 다음 단위와 병합) · CH-SEC(같은 heading_path 단위를 순서대로, chunk 당 최대 공백 기준 300단어) · CH-WIN(문서별 단위 텍스트 연결 후 200단어 창, 겹침 50). 모든 후보에 색인 제외 규칙 적용
- 구성 격자: chunking 3 × (BM25 1 + Dense 3 + Hybrid 3) = 21 + reranker 1 = **최대 22**(추가 금지)

## 8. DEV 선택 알고리즘 (결과 전 고정)
1. **점수**: 질의마다 원래 순위(중립 필터 이전)의 1위 점수 s. BM25 = BM25 점수, Dense = cosine, Hybrid = RRF 융합 1위 chunk 의 dense cosine, Reranker = 1위 reranker 점수. 질의 간 정규화 없음. 소수 6자리 반올림
2. **검색 순위 동점**: (점수 내림차순, chunk_id 오름차순)
3. **τ 조율 모집단(DEV, KO→EN 만)**: 양성 = DEV_POSITIVE scorable(33, PRB-B2-05 제외 32) ∪ COVERAGE DEV EP(37) / 음성 = COVERAGE DEV **격자** NE(161). **대조 질의 34 제외**, UNSCORABLE 제외
4. **τ 후보**: 조율 모집단 s 의 고유값 ∪ {최댓값 + 1e-6}. 판정 EVIDENCE_FOUND ⟺ s ≥ τ
5. **선택**: 균형 정확도 0.5·(TPR+TNR) 최대. 동점 → **가장 높은 τ**(보수적)
6. **비퇴화 제약**: 선택 τ 에서 DEV 양성 TPR ≥ 0.50. 만족하는 τ 가 없으면 그 구성은 **선택 불가**
7. **언어**: KO→EN 에서 정한 τ 를 EN→EN 에도 **공유**. EN 전용 τ 는 탐색적 민감도로만 보고
8. **구성 목적함수** J = 0.5·SR@5_e2e(DEV_POSITIVE, KO→EN) + 0.5·(1 − URR(COVERAGE DEV 격자 NE, KO→EN)), 각 구성의 τ 적용
9. **구성 선택**: 선택 가능 구성 중 J ≥ maxJ − 0.01 집합 → 구성요소 수 적은 쪽 → DEV p95 지연 낮은 쪽 → 구성 ID 사전순
10. 선택 구성 + τ → `pipeline_config.yaml` SHA 동결 → EVAL 1회. 선택 구성의 DEV J 는 성능 수치로 보고하지 않음
11. **기준선 BM25(EVAL 비교용)**: 같은 chunking. EN→EN 비교에는 같은 알고리즘을 **DEV EN→EN 모집단**에 적용한 τ_BM25,EN. 선택에 사용 안 함
12. **코드 가드**: DEV 단계 코드는 `split ∈ {DEV, DEV_POSITIVE}` 행만 로드하고 assert. EVAL 정답 파일 접근 금지(`/rg-verify` 점검 항목)

## 9. EVAL (1회)
- 동결 파이프라인으로 COVERAGE EVAL 141·PRB EVAL 63(채점 56)을 KO·EN 각각 1회 실행. 같은 chunking BM25(EN τ_BM25,EN)도 함께
- 사전 조건: 사람 감사(§6) 완료
- EVAL 결과 열람 후 파이프라인·τ·chunk·질의·정답·번역 변경 = deviation + exploratory. confirmatory 재평가는 새 질의·정답 버전 필요

## 10. 채점 정의
- chunk 분류: gold 단위와 1자 이상 겹치면 **gold chunk(gold 우선)**. gold 없이 중립(disputed·neutral) 단위와만 겹치면 **중립 chunk → 순위에서 제거 후 채점**. 나머지 = 비관련
- 순위 지표(능력, 기권 무관): Source Recall@1/5/10(상위 k 에 gold 출처 chunk), Passage Recall@5/10(gold 단위 덮인 비율 평균), MRR@10, relevant passage hit rate@5
- end-to-end 지표(기권 반영): SR@5_e2e = EVIDENCE_FOUND 이고 상위 5 에 gold 출처 chunk / evidence-present response rate = EP 질의 중 EVIDENCE_FOUND
- URR(unsupported retrieval rate) = NE 질의 중 EVIDENCE_FOUND 비율
- false evidence rate = EP 질의 중 EVIDENCE_FOUND 이면서 상위 5(중립 제거 후)에 gold chunk 없음
- 기권 균형 정확도 = 0.5·(PRB EVAL EP 근거 반환율 + COVERAGE EVAL 격자 NE 기권율). 단순 정확도는 유병률 의존 → 해석 금지
- Provenance: source_id 정확성 · 반환 heading_path·문자 범위로 원문 재구성 = chunk 텍스트(해시) · 반환 passage 가 정규화 원문의 부분 문자열
- 재현성: 같은 입력 5회 + 프로세스 재시작 3회, 순위·chunk_id 동일·점수 차 ≤ 1e-6
- 성능: 지연 p50/p95(cold·warm 분리), 최대 RSS, VRAM, 장치
- 배포: `unshare -rn` 네트워크 차단 실행 성공 + 외부 연결 시도 0 + 양성 대조(같은 환경에서 외부 연결 코드 실패 확인)
- 교차 언어: (EN→EN) − (KO→EN) 쌍대 차, 상위 5 출처·chunk Jaccard, 상태 일치율. 순위 지표와 기권 지표의 해석 분리

## 11. 판정 (Gate 와 비교 기준)
### 11.1 Hard requirement (과제 요구, 고정)
provenance 3종 100% · 재현성 100% · 오프라인 PASS. 하나라도 실패 → **NO_GO**
### 11.2 비교 기준 (confirmatory, 우선 보고)
- **CP-1 능력 비열등**: PRB EVAL, 선택 파이프라인 KO→EN SR@5_e2e − BM25 EN→EN SR@5_e2e. 출처 군집 쌍대 bootstrap 95% CI 하한 > **−0.10** → "한국어 입력 파이프라인이 영어 어휘 검색보다 10%p 넘게 나쁘지 않음"
- **CP-2 안전 비열등**: COVERAGE EVAL 격자 NE, 선택 파이프라인 KO→EN URR − BM25 EN→EN URR. 소견 군집 쌍대 bootstrap 95% CI 상한 ≤ **+0.05**
- 여백 0.10·0.05 = PROVISIONAL(문헌 근거 없음, 과제 판단)
### 11.3 절대 Gate (PROVISIONAL)
- **Gate A 안전**: COVERAGE EVAL 격자 NE(n=99) KO→EN URR. PASS ⟺ 소견 군집 bootstrap 95% 상한 ≤ 0.20 **그리고** Wilson 상한 ≤ 0.20. FAIL ⟺ 두 하한 모두 > 0.20. 그 외 INCONCLUSIVE
- **Gate B 능력**: PRB EVAL scorable(n=56) KO→EN SR@5_e2e(기권 = 실패). PASS ⟺ 출처 군집 bootstrap 95% 하한 ≥ 0.50 **그리고** Wilson 하한 ≥ 0.50. FAIL ⟺ 두 상한 모두 < 0.50
- 늘 기권하는 시스템: SR@5_e2e = 0 → Gate B FAIL(비퇴화 보장). 늘 근거를 내는 시스템: URR ≈ 1 → Gate A FAIL
- 임계 의미: T_A 0.20 = "근거 없는 질문 5개 중 1개 넘게 억지 근거를 내지 않음", T_B 0.50 = "답이 있는 질문의 과반에서 기권 없이 상위 5 안에 정답 출처". **둘 다 문헌 근거 없는 PROVISIONAL**
### 11.4 전체 판정
| 판정 | 조건 |
|---|---|
| INSUFFICIENT_EVIDENCE | PRB EVAL scorable(교차 언어 포함) < 40 또는 COVERAGE EVAL 격자 NE < 80 (현재 56 · 99 → 충족) |
| INCONCLUSIVE_GT | 사람 감사 오염률 Wilson 상한 > 0.20 |
| NO_GO | Hard 실패 또는 Gate A FAIL 또는 Gate B FAIL |
| PROVISIONAL_PASS | Hard 통과 + Gate A PASS + Gate B PASS |
| INCONCLUSIVE | 그 외 |
- CP-1·CP-2 는 판정과 함께 보고. "구조가 어휘 검색 대비 가치 있음" 주장은 CP-1·CP-2 둘 다 충족 시만
- **PROVISIONAL_PASS 도 confirmatory GO 아님**(임계가 PROVISIONAL). 제품 통합은 별도 결정

## 12. 통계
- 단위 = 질의. 비율 CI = Wilson(판정) + 군집 bootstrap percentile(판정)
- 군집 bootstrap: **2,000회**, seed 20261002, 군집을 복원 추출 후 풀링 비율. 쌍대 차는 같은 군집 재추출에서 차 계산
- 1차 군집: COVERAGE = **finding_id**(EVAL 격자 NE 34 군집) · PRB = **source_id**(EVAL 17 군집)
  - PRB 를 finding 으로 묶지 않는 이유: PRB 소견 개념은 거의 질의마다 다름(EVAL 55 개념/56 질의) → 군집 효과 없음. 같은 출처 질의끼리 같은 passage 를 공유 → 주 의존 구조
- 민감도(사전 고정, 판정 비사용): COVERAGE wd_id 군집 · WD×소견 two-way · PRB finding_concept 군집
- 판정 특성(이항 근사, 군집 효과 미반영 → 실제는 더 보수적):
  - Gate A n=99: PASS ⟺ 억지 근거 ≤ 11건. 참 URR 0.08→P(PASS) 0.90, 0.10→0.71, 0.12→0.47, 0.15→0.17
  - Gate B n=56: PASS ⟺ 36건 이상(0.643), FAIL ⟺ 20건 이하. 참 0.50→P(PASS) 0.02, 0.60→0.30, 0.65→0.60, 0.70→0.86, 0.80→1.00
- 최소 표본 근거: n=40, p=0.75 Wilson 반폭 0.13, 설계효과 1.5 가정 0.16. n=30 은 0.15/0.19 → 판정 불가 수준
- 다중 비교: 판정 대상은 Gate A·B·CP-1·CP-2 (각자 사전 기준). 나머지는 기술 통계, 보정 없음, 유의성 주장 금지

## 13. 사전 고정 보고·민감도
- Gate A 층별 URR: NE 하위유형 WD 공백(SA·GERD, 20) / 약한 범위(PER·MYO·PAN, 35) / 근거 있는 범위(44) · WD 별(n 작으면 개수만)
- 대조 질의 URR(EVAL 16) 별도 — Gate A 미포함(쉬운 음성)
- COVERAGE UNSCORABLE 12 를 NE 로 넣은 URR(n=111) · 사람 감사 EVIDENCE_FOUND 제외 URR
- PRB: 인용 정정 13 제외(n=43) · 범주별·관계 유형별 SR@5 · 출처 Tier 분포 · 반환 출처 집중도
- COVERAGE EP 14(능력 보조, 기술 통계만)
- 선택 구성의 EN 전용 τ 결과(탐색적)

## 14. 동결·변경 규칙
- 모든 자산 SHA → `docs/research/rag/freeze/EXP-SN-RAG-001-freeze-rev2.yaml`(git commit SHA 포함) → RG lock
- 변경 = 새 버전 + `rg.py deviation` + 재심사. v0 평가 끝나기 전 corpus 변경 0
- 프롬프트: PRB·번역·C 는 실행 전 파일 저장·SHA. gt-v0.1(COVERAGE)은 복원본(바이트 동일성 미보장, 공개)

## 15. Claim 범위
- 허용: "동결 corpus v0(18문서), queries-v0 격자·PRB-v0 질문 형식에서, 선택된 로컬 오프라인 검색의 근거 없음 처리·검색 능력·교차 언어 차이"
- 금지: 임상 성능·오진 탐지·안전성 · 새 WD·소견·corpus·실제 의사 입력으로 일반화 · "NO_EVIDENCE = 의학적으로 관계 없음"
- 관련성 정의 한계: COVERAGE 는 (WD, 소견 주제) 관계 명시 여부(값·극성 없음, R2 반대 근거 거의 없음 → 안전망의 대안 진단 근거 검색은 범위 밖). PRB 는 문서가 명시적으로 답하는 질문
- EVAL 은 같은 격자·같은 corpus 안의 보류 질의 — 외부 검증 아님

## 16. 공개 사항
1. 정답 작성·검증·번역·동등성 판정이 모두 Claude 계열(Sonnet 5 / Opus 5.5). 독립 맥락·독립 프롬프트·검색 결과 비공개를 적용해도 **사람·기관 수준의 독립 검증 아님**. B 는 A 결과를 보고 판정한 검증 관계
2. 열람 제한은 지시로만 강제(도구 차단 아님)
3. 메인 세션이 본 것: COVERAGE·PRB 정답 상태별 개수·WD/출처/범주 분포·불일치 유형·B 판정 분포(검색 결과 아님). 이를 보고 정한 것: gt amend-01(위치 합의 없음 → UNSCORABLE), PRB amend-01(인용 한 칸 밀림 정정 절차), PRB 군집 = source_id, 최소 n 40, PE-2 기술 통계화(rev1), 대조 질의를 PE-1·τ 조율에서 제외
4. 인용 한 칸 밀림은 메인 세션이 만든 문서 보기 파일 형식(1행 제목) 때문. COVERAGE 세트(gt-v0.1)에도 같은 원인의 DISAGREE·MISSED 가 있었을 가능성 — 사용자 지시로 COVERAGE 정답은 변경하지 않음(그 결과 일부 질의가 UNSCORABLE·중립 처리됨)
5. 사람 감사 도구 시험 실행 1회(키워드 "pericard"+"lean", 결과 0 단위)
6. corpus 동결이 사전등록보다 먼저(사용자 지시) · units-v0 REJECTED → units-v1 · gt-v0 SUPERSEDED → gt-v0.1
7. A 의 "확인용 검색" 허용(gt-protocol §3) → 어휘 일치 편향 가능
8. SRC-0010 원문 내부 모순(PR 분절 하강 빈도) — B 지적, AGREE 유지. 출처 품질 ≠ 관련성
9. SRC-0001 = 브라질 지침 영어 번역(국내 진료 맥락 아님). corpus manifest 의 reuse_status 와 addendum-01 production UNCONFIRMED 표기 차이 → addendum 이 정본
10. COVERAGE 템플릿 라벨 번역 미검증 · terminology_ko(v0 문구) 번역 주체·검수 기록 없음 → v1 문구로 대체

## 17. 실행 순서 (각 단계 사용자 승인)
1. 이 사전등록 + freeze manifest → `/rg-gate EXP-SN-RAG-001` → RUN 아니면 중단
2. 사용자 승인: D-INSTALL(venv·모델 3·reranker), 사람 감사 실시
3. 설치·가중치 SHA → 오프라인 검사 → chunk 3종·색인 → DEV 22 구성 → 선택·동결
4. 사람 감사 완료 확인 → EVAL 1회 → 채점 → `/rg-verify`(다른 세션)

## 18. 미결정
| ID | 내용 |
|---|---|
| D-INSTALL | 모델·라이브러리 다운로드·설치 |
| D-AUDIT | 사람 감사 실시 주체·일정 |
| D-THR | PROVISIONAL 값(T_A 0.20, T_B 0.50, CP 여백 0.10/0.05) 승인 |
