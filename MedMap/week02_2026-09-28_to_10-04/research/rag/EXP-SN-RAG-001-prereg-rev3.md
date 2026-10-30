# EXP-SN-RAG-001 사전등록 rev3 — Frozen Local Medical RAG 검색 평가 (Stage R)

- 작성 2026-10-02 · 브랜치 `research/safety-net-rag` · rev2(2161208a…)를 대체. RG 재심사 NEEDS_FIX(`.research-guardian/audits/EXP-SN-RAG-001/gate/20261002_152108_NEEDS_FIX.md`) 반영
- 원칙: 인터넷 검색형이 아님. **사전 승인·로컬 저장된 Frozen Corpus v0(18문서) 안에서만** 근거를 찾는 Offline Local RAG
- 상태: 사전등록(심사 전). 임베딩·BM25·색인·검색 구현·실행 0 · 모델 설치·다운로드 0 · 환자 데이터 0 · 검색 성능 숫자 0 · **HUMAN_AUDIT = PENDING**
- 범위: 검색만. WD 판정·대안 생성·다음 검사 생성·경고 생성 0. structured knowledge 혼합 0. 런타임 LLM 질의 재작성·번역 0

## 0. rev2 → rev3 변경 요약
| RG 지적(rev2) | rev3 조치 | 절 |
|---|---|---|
| 형식 교락(템플릿 기권·질문형만 응답으로 통과) | Primary 양성 = **SAFETY_NET_PRB_V1**: 같은 정답을 TEMPLATE·NATURAL_QUESTION 두 형식으로. G-R2 를 형식별로 각각 PASS 요구. τ 비퇴화 형식별 | §3.3, §8, §11 |
| 능력 지표가 문서 단위라 우연 수준 높음 | G-R2 = **구절 단위**(gold 단위 적중). 문서 단위는 "우연 초과" 조건. 무작위·자명 기준선 사전 계산·공개 | §10, §11, §12 |
| BM25 질의 변환 미정의 | BM25-PRE-v1 결정적 규칙, s = −bm25(), RRF 깊이 100 | §7 |
| 판정 우선순위·경계 계산 규칙 | 8단계 순서, 첫 비PASS 단계가 최종 판정, 연산자·정밀도·RNG·분위수 고정 | §11, §12 |
| CP 가 단일 구간 | CP = 군집 쌍대 bootstrap **그리고** Tango 쌍대 score 구간 | §11 |
| 사람 감사 기준·UNSURE·도구·ACS 0건 | **EVAL NE 99 전수** 감사 팩, 지침 동결, UNSURE→제외, 도구 v2(제목·절·앞뒤·표 머리글), 결과는 검색 전 동결 | §6 |
| PRB 정답이 같은 묶음 안에서만 | SN-PRB 정답 = **18문서 전체** 독립 검토(A ∩ X 일치 + B 판정), 관련 출처 복수 | §3.3 |
| PRB 범위(일반 질문 다수) | 기존 PRB-v0 → **GENERAL_RETRIEVAL_PRB_V0(secondary 진단용)**, 파일 변경 0 | §3.2 |
| 기타 | 문서 보기 v2(행 번호 = 단위 번호), 분할 파일 분리, 템플릿 라벨 번역 검증, 기계적 어휘 누출 판정 | §5, §8 |

## 1. 연구 질문
- **(Q1 안전, G-R1)** 근거가 없는 질의에서 억지 근거를 반환하지 않는가 — COVERAGE_ABSTENTION_SET_V0(사람 감사 확정분)
- **(Q2 안전망 능력, G-R2)** 안전망 질의(작업 진단 + 소견)에 근거가 있을 때, **기권 없이 상위 5 안에 정답 구절**을 가져오는가 — 두 질의 형식 각각에서 — SAFETY_NET_PRB_V1
- (Q3) 한국어 질의 → 영어 corpus 유지 · (Q4) 출처·결정성·오프라인 (G-R0) · (보조 G-R3) BM25 기준선 대비
- 두 세트는 섞어 한 숫자로 만들지 않음

## 2. 동결 자산 (해시 정본 = `docs/research/rag/freeze/EXP-SN-RAG-001-freeze-rev3.yaml`)
corpus v0(40f0b0b5 / 4390cf6a) · addendum-01/02 · units-v1(ee072925) · 문서 보기 v2(SHA256SUMS 5f168b63) · COVERAGE queries-v0(f2c4f032)·gt-v0.1(fa359b2b)·coverage-xling-v1(1915371b) · GENERAL prb-v0(99fa0370) · **SN sn-v1(3ae942a9)** · 번역 쌍 pairs-final-v1(61d8c35c)·pairs-sn-final-v1(feca4c0d) · 무작위 기준선 random-baselines-v1 · 분할 파일 splits/ · 감사 팩 audit/v1 · BM25 불용어 bm25-stopwords-en-v1 · 프로토콜(gt·prb·sn + amend) · 프롬프트(SHA·시각) · 이 문서
- 라이선스: 18건 CC BY(SRC-0014 버전 미기재·연구 승인·제품 UNCONFIRMED). NC·ND·ESC 관련·불명 제외. 제품 배포 승인 아님. 새 문헌 추가 0(v1-candidates 기록만)

## 3. 평가 세트
### 3.1 COVERAGE_ABSTENTION_SET_V0 (변경 0) — G-R1
- queries-v0 400 · gt-v0.1 · 분할 DEV 259 / EVAL 141. G-R1 모집단 = EVAL 격자 NO_EVIDENCE 99 중 **사람 감사 CONFIRMED_NO_EVIDENCE**(§6). 대조 16 별도 보고
- 형식 = TEMPLATE 만(`Working diagnosis: … Patient finding: …`). **NATURAL_QUESTION 형식의 근거 없음 질의는 없음 → Q1 결론은 TEMPLATE 형식에 한정**(공개)
### 3.2 GENERAL_RETRIEVAL_PRB_V0 (= PRB-v0, 변경 0) — secondary 진단용
- 89 채점(DEV 33 / EVAL 56). 판정 미사용. 용도: 검색 전반·출처 다양성·회귀 확인. 한계: 정답이 작성 묶음 안에서만 검토됨
### 3.3 SAFETY_NET_PRB_V1 (신규, Primary) — G-R2
- 정의(sn-protocol-v1): 항목 = (작업 진단 WD ∈ 10, 환자 소견·상황, 안전망 범주 ∈ 11). 같은 항목을 두 형식으로 질의, 정답 공유
  - TEMPLATE = `Working diagnosis: {WD}. Patient finding: {finding}` (COVERAGE 와 같은 템플릿)
  - NATURAL_QUESTION = 임상의 질문 1문장(출처 지목·답 포함 금지)
- 작성 AUTHOR A(Sonnet 5, 묶음 5) 102 항목 → **corpus 전체 검토 X**(Opus 5.5, 묶음 5, 정답 미표시 상태로 모든 항목에 대해 자기 묶음 문서 전체 탐색, 230 행) → gold 확정 = A ∩ X(같은 문서 독립 일치), 엇갈린·묶음 밖 단위 385개는 **VERIFIER B**(Sonnet 5 새 세션, 제안자 미표시) 판정(AGREE 319·DISAGREE 35·AMBIGUOUS 31) → AGREE 만 gold, 나머지 중립. B 는 항목 적합성(안전망 범위·출처 지목·소견에 답 포함)도 판정
- 결과: 채점 97 (DEV_SN 36 / **EVAL_SN 61**), UNSCORABLE 5(전부 FINDING_CONTAINS_ANSWER)
- EVAL_SN 61: 관련 출처 수 1:17 · 2:25 · 3:14 · 4+:5 / WD 10 전부(PE 14, ACS 11, AAS 7, PTX 7, EOR 6, MYO 6, PER 5, GERD 2, SA 2, PAN 1) / 범주 11 전부 / 주 출처 15(SRC-0001 23 = 38%)
- 형식별 EVAL 채점 가능: TEMPLATE EN 61·KO 61 / NATURAL EN 55·KO 54 (NATURAL 어휘 누출 6, 번역 비동등 1 제외)
- 분할(작성 전 고정): `int(sha256('ragSN01split|'+sn_id)[:8],16)%100<40` → DEV_SN, 그 외 EVAL_SN, 두 형식 같은 분할
- **CORPUS_COVERAGE_LIMITATION**: 안정형 협심증·GERD·공황 항목 각 3(EVAL 2·2·1). corpus v0 가 이 범위를 거의 다루지 않음 — 보강하지 않고 결과로 보고
- 성격: Frozen Corpus Retrieval Ground Truth. medical_review_status = UNREVIEWED, human_clinical_validation = NONE

## 4. 입력 규칙
- 검색 입력 = 질의 문자열만(EN 또는 KO). ID·구조 필드 사용 금지. 런타임 LLM 재작성·번역·동의어 확장·corpus 유래 용어 확장 0
- 파이프라인: canonical query → 결정적 전처리(§7) → 검색

## 5. 한국어/영어 동등성
- GENERAL·COVERAGE: pairs-final-v1(152 중 151 SAME, PRB-B2-05 KO 제외)
- SN: pairs-sn-final-v1 206쌍 = 소견 102 + 질문 102 + **템플릿 라벨 2(이번에 검증, 둘 다 SAME)** → T1 SAME 204 · PARTIAL 2 → T 수정 → V 재판정 SAME 1 → **최종 SAME 205, NATURAL SN-B4-09 KO 제외**
- 질환명 KO = 기존 검증 쌍(COVW, SAME) 재사용. 번역은 검색 전 동결

## 6. NO_EVIDENCE 사람 감사 (전수)
- 대상: COVERAGE **EVAL 격자 NE 99 전부**(WD 10, ACS 5 포함). 팩 `docs/research/rag/eval/audit/v1/`: 시트(99행) · 지침(AUDIT_INSTRUCTIONS.md) · 진단 위치 지도 · 도구 `scripts/rag/audit_search_v2.py`(문서 제목·절·앞뒤 단위·표 제목·표 머리글 표시, **문서 순서·점수 없음**)
- 감사자: 사람(사용자 또는 지정인). **Claude 는 채우지 않음.** 의료 판단 아님 — 질문은 "corpus 안에 이 진단·소견 관계를 직접 말하는 문장이 있는가" 하나. medical_review_status = UNREVIEWED
- 판정: CONFIRMED_NO_EVIDENCE / EVIDENCE_FOUND(단위 ID) / UNSURE. 기준 = gt-protocol-v0 §2(관계 R1–R6, 명시 서술, 진단이 문장 또는 절 제목에)
- 처리(사전 고정): CONFIRMED → G-R1 모집단 · EVIDENCE_FOUND → 제외(정답 오염, 건수·Wilson CI 보고) · **UNSURE → 제외(UNSCORABLE)**. 정답 파일(gt-v0.1)은 수정하지 않고 감사 결과 파일로 필터
- 시점·봉인: **모든 검색 실행(DEV 포함) 전에 완료** → 결과 파일 SHA 를 freeze manifest 에 추가(rev3-audit 추가 커밋) → DEV 구성 선택 세션은 결과 내용을 열람하지 않음(SHA 만) → EVAL 채점 때 사용
- 현재: **PENDING**(팩 동결, 결과 없음)

## 7. 검색 후보와 BM25 전처리 (실행 전 후보만)
- Lexical: BM25 = SQLite FTS5(구현 시 로컬 FTS5 활성 확인, 없으면 deviation). 색인 토크나이저 `porter unicode61 remove_diacritics 2`. FTS5 bm25() 는 k1=1.2·b=0.75 고정
- **BM25-PRE-v1 (질의, 결정적)**: NFKC → 소문자 → 정규식 `[^\w]+`(유니코드 단어 문자 외) 를 공백으로 → 공백 분리 → `bm25-stopwords-en-v1`(Lucene 영어 33개) 제거 → 길이 1 토큰 제거 → 첫 등장 순서 유지 중복 제거 → 토큰 0개면 UNKNOWN → MATCH 문자열 = 각 토큰을 큰따옴표로 감싸 ` OR ` 결합 → 점수 s = −bm25() (클수록 관련) → 상위 100
- 한국어 질의도 같은 규칙. corpus 가 영어뿐이라 한국어 토큰은 구조적으로 일치하지 않고 라틴 토큰(ECG, D-dimer 등)만 일치 가능 → **Kiwi 등 한국어 형태소 분석 후보는 제외**(영어 corpus 에 효과 없음, 근거 공개)
- Dense: bge-m3 · KURE-v1 · multilingual-e5-large(e5 는 모델 카드 규정 접두어 `query: `/`passage: `만 추가). 질의 문자열 그대로. FAISS IndexFlatIP(CPU) exact
- Hybrid: BM25 상위 100 + Dense 상위 100 → RRF(k=60)
- Reranker(선택): bge-reranker-v2-m3, DEV 최상위 hybrid 1개에만
- Chunking: CH-UNIT / CH-SEC / CH-WIN (rev2 정의 그대로), 색인 제외 규칙 적용
- 구성 격자 최대 22(rev2 그대로)

## 8. DEV 선택 알고리즘 (결과 전 고정)
1. 점수: 원래 순위(중립 필터 이전) 1위 점수. BM25 = −bm25(), Dense = cosine, Hybrid = 융합 1위 chunk 의 dense cosine, Reranker = 1위 reranker 점수. 질의 간 정규화 없음. **검색 점수는 float64 를 소수 6자리 반올림해 저장·비교**(결정성 보장용 고정 규칙)
2. 검색 순위 동점: (점수 내림차순, chunk_id 오름차순)
3. τ 조율 모집단(DEV, KO→EN): 양성 = DEV_SN TEMPLATE KO 적격 + DEV_SN NATURAL KO 적격 + COVERAGE DEV EP 37(TEMPLATE) / 음성 = COVERAGE DEV **격자** NE 161(TEMPLATE). 대조·UNSCORABLE·GENERAL 제외
4. τ 후보 = 모집단 점수 고유값 ∪ {최댓값 + 1e-6}. EVIDENCE_FOUND ⟺ s ≥ τ
5. **비퇴화 제약(형식별)**: TPR_TEMPLATE(DEV_SN TEMPLATE + COVERAGE DEV EP) ≥ 0.50 **그리고** TPR_NATURAL(DEV_SN NATURAL) ≥ 0.50 인 τ 만 후보. 없으면 그 구성 선택 불가
6. 목적: 0.5·(macro TPR + TNR) 최대, macro TPR = (TPR_TEMPLATE + TPR_NATURAL)/2. 동점 → 가장 높은 τ
7. KO→EN τ 를 EN→EN 에 공유(EN 전용 τ 는 탐색적)
8. 구성 J = 0.5·mean_format(passage_hit@5_e2e, DEV_SN KO) + 0.5·(1 − URR(COVERAGE DEV 격자 NE KO))
9. 선택 가능 구성 중 J ≥ maxJ − 0.01 → 구성요소 적은 쪽 → DEV p95 → 구성 ID 사전순. 선택 구성 DEV J 는 성능으로 보고 안 함
10. BM25 기준선(G-R3): 같은 chunking, 같은 알고리즘을 DEV **EN→EN** 모집단에 적용한 τ. 비퇴화 τ 가 없으면 G-R3 은 기술 통계로 강등(사전 고정)
11. 코드 가드: DEV 단계 코드는 `eval/splits/*-dev.jsonl` 만 열고, EVAL 파일·감사 결과 경로 접근 시 중단(assert)

## 9. EVAL (1회)
- 사전 조건: G-R0 시험 통과 · 사람 감사 완료·동결 · pipeline_config SHA 동결
- `*-eval.jsonl` 로 KO·EN 각 1회 + 같은 chunking BM25 EN→EN. 이후 변경 = deviation + exploratory

## 10. 채점 정의
- chunk 분류: gold 단위와 1자 이상 겹치면 gold chunk(gold 우선) · 중립 단위와만 겹치면 순위에서 제거 · 그 외 비관련
- 순위 지표(능력, 기권 무관): Source Recall@1/5/10 = 상위 k 에 관련 출처(relevant_source_ids 중 하나)의 gold chunk / Passage Recall@5/10 = gold 단위 중 상위 k 가 덮는 비율 평균 / passage_hit@k = 상위 k 에 gold chunk ≥ 1 / MRR@10 = 첫 gold chunk 순위 역수
- e2e 지표(기권 반영): passage_hit@5_e2e = EVIDENCE_FOUND **그리고** 상위 5 에 gold chunk / source_hit@5_e2e = EVIDENCE_FOUND 그리고 상위 5 에 관련 출처 chunk / evidence-present response rate
- URR = NE 질의 중 EVIDENCE_FOUND 비율 · false evidence rate = EP 질의 중 EVIDENCE_FOUND 이면서 상위 5 에 gold chunk 없음 · 기권 균형 정확도 = COVERAGE 단독(EVAL EP 14 + 감사 확정 NE) 과 SN+COVERAGE 형식별로 따로(유병률 의존 단순 정확도는 해석 안 함)
- Provenance(G-R0): source_id 정확성 · heading_path·문자 범위로 원문 재구성 = chunk 텍스트(해시) · passage 가 정규화 원문의 부분 문자열 — 각 100%
- 재현성(G-R0): 같은 입력 5회 + 프로세스 재시작 3회 → 순위·chunk_id 동일, 저장 점수(6자리) 동일
- 오프라인(G-R0): `unshare -rn` 차단 실행 성공 + 외부 연결 시도 0 + 양성 대조(같은 환경에서 외부 연결 코드 실패 확인)
- 성능(기술): 지연 p50/p95(cold·warm), 최대 RSS, VRAM, 장치

## 11. Gate 와 판정 순서
### 11.1 Gate 정의
| Gate | 지표·모집단 | PASS | FAIL | 구간 |
|---|---|---|---|---|
| **G-R0** 신뢰성 | provenance 3종·재현성·오프라인 | 모두 100% / 성공 | 하나라도 미달 | 없음(전수 판정) |
| **G-R1** 근거 없음 안전 | URR, COVERAGE EVAL 격자 NE 중 사람 감사 CONFIRMED, KO→EN | 두 상한 ≤ 0.20 | 두 하한 > 0.20 | Wilson + 소견(finding_id) 군집 bootstrap |
| **G-R2a** 전체 능력 | passage_hit@5_e2e, EVAL_SN 두 형식 합침(항목당 TEMPLATE·NATURAL 각 1관측), KO→EN | 두 하한 ≥ 0.50 | 두 상한 < 0.50 | Wilson(관측 단위) + **항목(sn_id) 군집** bootstrap |
| **G-R2b** TEMPLATE 능력 | passage_hit@5_e2e, EVAL_SN TEMPLATE KO 적격 | Wilson 하한 ≥ 0.50 | Wilson 상한 < 0.50 | Wilson(항목 = 독립 단위) |
| **G-R2c** NATURAL 능력 | 같음, NATURAL KO 적격 | Wilson 하한 ≥ 0.50 | Wilson 상한 < 0.50 | Wilson |
| **G-R2d** 우연 초과(문서 단위) | source_hit@5_e2e, 형식별 KO 적격 | 각 형식 Wilson 하한 > 그 형식 무작위 기대값(random_unit_source_hit@5: TEMPLATE 0.6607 · NATURAL 0.6583) | 각 형식 Wilson 상한 ≤ 기대값 | Wilson |
| **G-R2e** 출처 집중 견고성 | passage_hit@5_e2e, 두 형식 합침, 주 출처 ≠ SRC-0001 항목만(38) | 점추정 ≥ 0.50 | 점추정 < 0.50 | 없음(점추정 조건, 사전 고정) |
| G-R3 기준선 비교(보조) | CP-1: passage_hit@5_e2e(선택 KO→EN) − (BM25 EN→EN), EVAL_SN 두 형식 합침 / CP-2: URR 차, G-R1 모집단 | CP-1 두 하한 > −0.10 / CP-2 두 상한 ≤ +0.05 | — | 항목(CP-1)·소견(CP-2) 군집 쌍대 bootstrap + Tango 쌍대 score 95% |
- 늘 기권: passage_hit e2e = 0 → G-R2 FAIL. 늘 응답: URR ≈ 1 → G-R1 FAIL
- 구간을 둘 쓰는 이유: Wilson = 독립 가정 표집 불확실성, 군집 bootstrap = 같은 소견/항목을 공유하는 의존. **둘 다 충족해야 PASS**(보수적). G-R2b·c·d 는 단위가 항목 하나뿐이라 군집 = 독립 → Wilson 만
### 11.2 판정 순서 (첫 비PASS 단계가 최종 판정, 이후 단계도 보고하되 상쇄 불가)
1. G-R0 → 미달 = **FAIL**
2. 최소 표본·사전 조건 → 미달 = **INSUFFICIENT_EVIDENCE**: 사람 감사 완료 · G-R1 CONFIRMED ≥ 80 · EVAL_SN 채점 항목 ≥ 40 · 형식별 KO 적격 ≥ 30(TEMPLATE·NATURAL 각각) · 비SRC-0001 항목 ≥ 30(현재 TEMPLATE 38 · NATURAL 34)
3. G-R1 → FAIL = **FAIL**, 판정 불가 = **INCONCLUSIVE**
4. G-R2a → 같은 방식
5. G-R2b, G-R2c (둘 다 PASS 필요)
6. G-R2d, G-R2e
7. 1–6 모두 PASS → **PASS**. G-R3 결과는 수식어로만: PASS_WITH_BASELINE_ADVANTAGE(CP-1·CP-2 모두 충족) / PASS_NO_BASELINE_ADVANTAGE
8. 최종 표기 ∈ {PASS, FAIL, INSUFFICIENT_EVIDENCE, INCONCLUSIVE} + 단계별 결과 전부
### 11.3 임계값 (PROVISIONAL_METHOD_THRESHOLD — 연구 방법 임계, 임상 검증 안전 기준 아님, 제품 임계 아님, 사용자 승인 2026-10-02)
| 값 | 적용 | 형태 | 이유 | 무작위·자명 대비 |
|---|---|---|---|---|
| 0.20 | G-R1 URR | 두 상한 ≤ (n=99 Wilson 기준 억지 근거 11건 이하) | 근거 없는 질문 5개 중 1개 넘게 억지 근거를 내면 근거 채널을 의사 검토 자료로 쓰기 어려움(과제 판단) | 늘 응답 1.0, 늘 기권 0(G-R2 에서 차단) |
| 0.50 | G-R2a·b·c passage_hit@5_e2e | 하한 ≥ | 답이 있는 안전망 질문의 과반에서 기권 없이 정답 구절 | 무작위 단위 passage_hit@5 기대 0.009, 늘 기권 0 |
| 0.6607 / 0.6583 | G-R2d source_hit@5_e2e (TEMPLATE / NATURAL) | 하한 > | 문서 단위 우연 기대값(형식별 EVAL 적격 항목, 단위 균등 추출) | 최빈 출처(SRC-0001) 0.574, 무작위 문서 0.495 |
| 0.50 | G-R2e | 점추정 ≥ | SRC-0001 의존 견고성 | — |
| −0.10 / +0.05 | G-R3 CP-1 / CP-2 | 하한 > / 상한 ≤ | 한국어 의미 검색이 영어 어휘 검색보다 10%p 넘게 나쁘지 않고, 억지 근거를 5%p 넘게 늘리지 않음 | — |
- 근거가 약함 → 모두 PROVISIONAL_METHOD_THRESHOLD. 결과 열람 후 변경 금지

## 12. 수치 계산 규칙
- 내부 계산 float64 전 정밀도. 표시만 반올림. **임계 비교는 반올림 전 값**. 연산자: ≤·≥·<·> 는 §11 표 그대로
- Wilson: z = 1.959963984540054, 양측 95%
- 군집 bootstrap: **10,000회**(rev2 2,000 → 변경. 이유: 경계 근처 Monte Carlo 오차 축소, 통계 심사 권고, 계산 비용 무시 가능). percentile, `numpy.quantile(method='linear')` 2.5%·97.5%. RNG = `numpy.random.default_rng(seed)`(PCG64), seed = 20261002 + k (k: G-R1=1, G-R2a=2, CP-1=7, CP-2=8, 민감도 = 101 부터 순서). 군집 ID 사전순 배열에서 복원 추출, 통계량 = 추출 군집 성공 합 / 관측 합
- Tango 쌍대 score 95%: 쌍대 이진 차(불일치 쌍 b·c 와 n), 표준 Tango(1998) 식. b = c = 0 이면 구간 [0,0]로 두고 bootstrap 결과와 함께 보고
- 빈 층·분모 0: 해당 Gate = INSUFFICIENT_EVIDENCE. NaN 발생 시 그 지표 INSUFFICIENT_EVIDENCE(대체값 없음)
- 소표본·층별 지표(n<10 또는 COVERAGE EP 14): Wilson 만, 기술 통계, 결론 금지
- 모든 EVAL 구간 = DEV 에서 선택된 파이프라인에 조건부
- 다중성: PASS 는 모든 Gate 동시 충족(교집합 — 보정 불필요). FAIL 은 여러 Gate 중 하나로 성립 → 거짓 FAIL 확률은 Gate 수만큼 누적(공개). G-R3 각 비교 단측 α = 0.025, 가족 오류율 통제 없음
- 판정 특성(이항, 군집 미반영, z 위 값): G-R1 n=99 PASS ⟺ 억지 근거 ≤ 11건(참 URR 0.10 → P(PASS) 0.71) · G-R2b n=61 PASS ⟺ ≥ 39건(참 0.60→0.31, 0.65→0.63, 0.70→0.88, 0.80→1.00) · G-R2c n=54 PASS ⟺ ≥ 35건(0.60→0.28, 0.70→0.84) · G-R2d n=61 PASS ⟺ ≥ 48건(참 0.80→0.67, 0.85→0.93), n=54 ⟺ ≥ 43건(0.80→0.61, 0.85→0.90). G-R1 의 실제 n 은 감사 CONFIRMED 수로 바뀌므로 그때 같은 식으로 재계산(규칙 고정, 값만 갱신)

## 13. 사전 고정 보고·민감도 (판정 미사용)
- G-R1 층별(WD 공백/약한 범위/근거 범위, WD별), 대조 질의 URR, 감사 EVIDENCE_FOUND·UNSURE 수, UNSURE 를 NE 로 넣은 URR
- G-R2: 출처(primary_source_id) 군집·WD 군집 bootstrap, 범주별·WD별·관련 출처 수별 passage_hit, EN→EN, 어휘 최장 일치 길이별(TEMPLATE 공변량)
- 형식별 DEV·EVAL 1위 점수 분포(TEMPLATE / NATURAL / COVERAGE NE)
- GENERAL_RETRIEVAL_PRB_V0 전 지표(기술), COVERAGE EP 14(기술)

## 14. 한계·공개
1. 정답·검토·검증·번역·동등성 판정이 모두 Claude 계열(Sonnet 5 / Opus 5.5). 사람·기관 독립 검증 아님. medical_review_status = UNREVIEWED, human_clinical_validation = NONE. 이것은 임상 진실 벤치마크가 아니라 Frozen Corpus 검색 정답
2. 열람 제한은 지시로만 강제. 프롬프트는 실행 전 파일 저장·SHA·시각 기록(`*/prompts/PROMPTS.sha256`, `PROMPTS.timestamps`). rev2 의 "실행 전 SHA" 표현은 부정확(PRB SHA 파일은 실행 후 재생성) — 정정
3. 메인 세션이 본 것: 정답 상태·분포·판정 분포·무작위 기준선(검색 결과 아님). 이를 보고 정한 것: G-R2 군집 = 항목(주 출처 유효 군집 5.5), G-R2e 추가, G-R2d 기준값
4. 안전망 항목은 A 가 원문을 읽고 작성(독해식) → 표현이 정답 구절에 가까울 수 있음(검색에 유리한 방향). NATURAL 은 기계적 누출 판정으로 일부 차단, TEMPLATE 은 공변량 보고
5. G-R1 은 TEMPLATE 형식 근거 없음 질의만 → NATURAL 형식 안전성 미검증
6. SN EVAL 의 SRC-0001 집중(38%) — G-R2e 로 일부 대응
7. corpus 범위 한계(안정형 협심증·GERD·공황) = CORPUS_COVERAGE_LIMITATION
8. GENERAL PRB 의 묶음 내 정답 한계·인용 정정 13건(rev2 공개 유지)
9. 편향 방향: 보수적(PASS 어렵게) = NE 정답 오염(감사로 제거), 중립 단위 처리 / 반보수적(PASS 쉽게) = 독해식 작성, 명시적 답만 있는 항목, gold 일치 요구로 어려운 항목 탈락
10. units-v1 manifest 의 storage_root 문구 오기(units-v0 경로 표기) — 해시는 units-v1 과 일치, 파일 미수정(공개)
11. gt-v0.1 프롬프트 복원본 → RG lock 후 `rg.py deviation` 으로도 기록 예정

## 15. Claim 범위
- 허용: "동결 corpus v0 에서, 안전망 질의 두 형식(사전 작성)과 근거 없음 템플릿 질의에 대해 선택된 로컬 오프라인 검색이 보인 구절 단위 근거 반환·억지 근거 억제"
- 금지: 임상 성능·안전성·오진 탐지, 새 WD·corpus·실제 의사 입력 일반화, NATURAL 형식 안전성, "NO_EVIDENCE = 의학적 무관"

## 16. 실행 순서 (각 단계 사용자 승인)
1. RG 재심사 → RUN 아니면 중단
2. **사람 감사 99 완료 → 결과 SHA 동결(추가 커밋)**
3. D-INSTALL 승인 → 설치·가중치 SHA → G-R0 오프라인 시험 → chunk·색인 → DEV 22 구성 → 선택·동결
4. EVAL 1회 → 채점 → `/rg-verify`(다른 세션)

## 17. 미결정
D-INSTALL(설치) · D-AUDIT 실행(사용자) · (승인됨) D-THR = PROVISIONAL_METHOD_THRESHOLD
