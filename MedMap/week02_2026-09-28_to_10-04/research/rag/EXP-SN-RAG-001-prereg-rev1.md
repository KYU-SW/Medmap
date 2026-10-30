# EXP-SN-RAG-001 사전등록 rev1 — Frozen Local Medical RAG 검색 평가 (Stage R)

- 작성 2026-10-02 · 브랜치 `research/safety-net-rag` · rev0(`EXP-SN-RAG-001-prereg-draft.md`)를 대체
- 상태: **사전등록 완성본(심사 전).** 임베딩·색인·검색 구현·실행 0 · 모델 설치·다운로드 0 · 환자 데이터 접근 0
- 범위: **검색만.** WD 판정·설명 안 되는 소견·대안 진단·다음 검사·의사 경고 생성 0. structured knowledge(EXP-SN-001) 점수와 혼합 0

## 1. 연구 질문
동결 corpus `rag-chestpain-v0`에서, 완전 로컬·오프라인 검색이 (작업 진단, 환자 소견) 질의에 대해
- (Q1) 근거가 없는 질의에서 억지 근거를 반환하지 않고 `UNKNOWN`을 내는가 — **주 질문**
- (Q2) 근거가 있는 질의에서 정답 출처·구절을 상위 k 안에 가져오는가
- (Q3) 한국어 질의 → 영어 corpus 검색이 영어 질의 대비 얼마나 유지되는가
- (Q4) 출처 추적·결정적 반복·오프라인 조건을 만족하는가

## 2. 동결 자산 (해시)
| 자산 | 경로 | SHA-256 |
|---|---|---|
| Corpus v0 manifest | `docs/research/rag/corpus/rag-chestpain-v0.manifest.yaml` | `40f0b0b507140de1c2408b72ceec996f2c9fe35fb292a59bb2bb6119de56a1af` |
| 원문 SHA256SUMS | `~/medmap_rag_corpus/rag-chestpain-v0/SHA256SUMS` | `4390cf6ad9f011ab446f0e72da0ce9c0eb59dd0bce133575189891cde6d3ee60` |
| addendum-01(승인·SRC-0014·그림 제외·색인 범위) | `corpus/rag-chestpain-v0.addendum-01.yaml` | `1bbdff0492fcd1763bf91397fe103e2013e41f0ecd3f0a6d2a47892a2244bd25` |
| addendum-02(뒷부분 제외 적용 방식) | `corpus/rag-chestpain-v0.addendum-02.yaml` | `b3646a4385c459f60dd2db0454ee7d7fa9e69c2a6606c5a55441954e1a78100f` |
| 정답 참조 단위 units-v1(2,487) | `~/medmap_rag_corpus/derived/rag-chestpain-v0.units-v1/units.jsonl` | `ee07292511f40a8be3f022cbad89c7f9149276632c9affe702cf62ca3131b8c2` |
| 질의 queries-v0(400) | `docs/research/rag/eval/queries-v0.jsonl` | `f2c4f03210182a514b4aa856d15b58aa5e330555dcabd83e17b214ec49ba367f` |
| 정답 프로토콜 | `eval/gt-protocol-v0.md` · amend-01 | `2aae64bc…3a196f97` · amend-01 `.sha256` 파일 |
| Author A 출력 5 | `eval/gt-work/authorA/A_FROZEN.sha256` | 파일별 SHA |
| Verifier B 출력 5 | `eval/gt-work/verifierB/B_FROZEN.sha256` | 파일별 SHA |
| **정답 gt-v0.1** | `eval/gt-v0.1.jsonl` | `fa359b2b272ab91c86393997219ef602959173dc465c178f14f0341c5b2dce37` |

- 라이선스: 18건 전부 CC BY(SRC-0014 = CC BY 버전 미기재, 연구 승인·제품 UNCONFIRMED). NC·ND·ESC 관련·불명 제외. 제품 배포 승인 아님
- 색인 제외: SRC-0015 `fig#F1`, SRC-0018 `fig#life-12-01606-f003`(그림·캡션). 색인 언어 영어(SRC-0001은 영어 번역 하위문서)
- 공백(채우지 않음): 안정형 협심증·GERD 자체 = COVERAGE_GAP

## 3. 질의 생성 규칙 (corpus 내용 미참조, 결정적)
- 격자 350 = WD 10(ACS·안정형 협심증·PE·심낭염·심근염·자연 기흉·GERD·공황·급성 대동맥 증후군·Boerhaave) × 소견 35(EXP-SN-001 prereg §9 C7 관측 가능 항목). 표본 추출 없음(전부)
- 대조 50 = 흉통 범위 밖 DDXPlus 질환 39개 중 `sha256('ragR01ctrlwd|'+name)` 앞 5개(COPD 급성 악화·급성 후두염·사르코이드증·급성 중이염·SLE) × 질환별 `sha256('ragR01ctrlf|'+name+'|'+E)` 앞 10개 소견
- 문구: 영어 = DDXPlus `question_en`(CC BY) · 한국어 = MedMap `terminology_ko.json` `evidence_questions`(status ok) · 질환명 = terminology_ko(급성 대동맥 증후군만 수기 고정)
  - `text_en` = "Working diagnosis: {WD_en}. Patient finding: {question_en}"
  - `text_ko` = "작업 진단: {WD_ko}. 환자 소견: {question_ko}"
- 검색 시스템 입력 = **질의 문자열만**(text_en 또는 text_ko). wd_id·finding_id 등 구조 필드 사용 금지(교차 언어 평가 무력화 방지)
- 미열람: `release_conditions.json` · 환자 행 · corpus 본문 · 검색 결과

## 4. DEV / EVAL 분할
- `int(sha256('ragR01split|'+query_id)[:8],16) % 100 < 60` → DEV, 나머지 → EVAL (60/40, 정답 작성 전 고정)
- 60/40 근거: DEV는 구성 선택에 충분, EVAL 비중은 70/30보다 크게(소표본 대비)
- 결과(정답 기준 채점 가능 수):

| | EVIDENCE_PRESENT | NO_EVIDENCE(격자+대조) | UNSCORABLE |
|---|---|---|---|
| DEV (259) | 37 | 195 (161+34) | 27 |
| EVAL (141) | **14** | 115 (99+16) | 12 |

## 5. 정답 작성·검증 (요지, 정본 = gt-protocol-v0 + amend-01)
- AUTHOR A = Claude Sonnet 5, 문서 묶음 5개, 문서를 처음부터 순서대로 읽는 단위 중심 방식, 관계 R1–R6 명시 서술만
- VERIFIER B = Claude Opus 5.5(다른 모델, 독립 세션), A 행마다 AGREE/DISAGREE/AMBIGUOUS + 문서 전체 재독으로 MISSED
- 둘 다 검색 결과·환자 데이터·EXP-SN-001 평가 결과·분할 정보 미열람(지시로 제한)
- 합치기: A 상태 = B 상태 → scorable, 불일치·AMBIGUOUS → UNSCORABLE. EVIDENCE_PRESENT 인데 합의된 위치(AGREE 단위) 0 → UNSCORABLE(NO_AGREED_LOCATION, amend-01)
- gold = AGREE 단위·출처. disputed(DISAGREE·AMBIGUOUS·MISSED) 단위·출처 = **중립**(검색되어도 정답·오답 아님 — 순위 목록에서 제거 후 채점)
- A 187행 → B: AGREE 107 · DISAGREE 34 · AMBIGUOUS 46 · MISSED 63 (묶음 합계)
- 민감도 분석(사전 고정): strict = A 행 전부 AGREE·MISSED 0 인 질의만(EVAL EP 7, NE 115)
- 한계: NO_EVIDENCE 는 두 판정자가 모두 놓친 근거가 있으면 실제로는 근거가 있는 질의일 수 있음(B 의 MISSED 63건 = A 단독 재현율이 낮았음) → URR 이 과대 추정될 수 있는 방향. 보고 시 명시
- **NO_EVIDENCE 의미**: "corpus v0 안에 이 (WD, 소견) 관계를 명시한 단위가 A·B 합의로 없음". 의학적으로 관계가 없다는 뜻 아님

## 6. 비교 검색 계열 (DEV에서 선택, EVAL에서 변경 금지)
| 계열 | 후보 | 비고 |
|---|---|---|
| A. Lexical | BM25(SQLite FTS5, `porter unicode61`, k1=1.2·b=0.75 고정) | KO→EN은 어휘 불일치로 바닥 성능 예상 — 그대로 보고(번역 단계 추가 금지) |
| B. Dense | D1 BAAI/bge-m3 · D2 nlpai-lab/KURE-v1 · D3 intfloat/multilingual-e5-large | 전부 MIT·로컬·trust_remote_code 불필요(카드 기준). KURE-v1 자동 채택 금지 |
| C. Hybrid | BM25 + D_i, RRF(k=60, 정수 순위 결합) | |
| (선택) Reranker | bge-reranker-v2-m3 (Apache-2.0) — DEV 최고 hybrid 1개에만 시험 | |

- Dense 후보 근거(모델 카드, 2026-10-02 확인): bge-m3 = MKQA 교차 언어(비영어 질의→영어 문서) 평가 보고, 한국어 개별 수치 미확인 · KURE-v1 = 한국어·의료 공중보건 검색 평가, **한국어→영어 평가 없음** · e5-large = 언어별 단일 언어 평가만, 최대 512 토큰. **세 모델 모두 한국어 의료 질의→영어 문헌 성능 근거 없음 → DEV 실측으로만 선택**
- 정확 검색만: FAISS `IndexFlatIP`(CPU) 또는 동등 exact. ANN 사용 금지(18문서 규모)
- 벡터는 빌드 시 1회 계산·저장·해시. 질의 임베딩 CPU fp32. 동점 = (score desc, chunk_id asc)

## 7. Chunking 후보 (DEV에서 1개 선택)
| ID | 규칙 |
|---|---|
| CH-UNIT | units-v1 단위 = chunk(문단·표 행·캡션), 50단어 미만 단위는 같은 절 다음 단위와 병합 |
| CH-SEC | 같은 heading_path 단위를 순서대로 묶되 chunk 당 최대 공백 기준 300단어 |
| CH-WIN | 문서별 단위 텍스트 연결 후 공백 단어 200 창·겹침 50 |

- 모든 후보에 addendum 제외 규칙 적용(제3자 그림·캡션, 뒷부분 절). chunk ↔ 정답 단위 대응 = 문자 범위 겹침(chunk가 gold 단위 텍스트를 1자 이상 포함)

## 8. DEV 선택 규칙 (결과 전 고정)
- 구성 격자: chunking 3 × 검색 7(BM25 · D1–D3 · H1–H3) = 21 + reranker 1 = **최대 22 구성**(추가 금지)
- 구성별 `UNKNOWN` 임계 τ: BM25 = 1위 BM25 점수, Dense = 1위 cosine, Hybrid = 융합 1위 chunk의 dense cosine. DEV KO→EN에서 균형 정확도(EP=근거 반환, NE=UNKNOWN) 최대 τ(후보 = DEV 점수 분위 1%~99%, 1% 간격)
- 목적함수 J = 0.5·SR@5(EP) + 0.5·(1 − URR(NE)), **DEV KO→EN** 기준, UNSCORABLE 제외
- 동점(|ΔJ| < 0.01): 구성요소 적은 쪽 → DEV 지연 p95 낮은 쪽 → 구성 ID 사전순
- 선택 구성 + τ 를 해시로 동결(`pipeline_config_sha256`) → EVAL 1회. DEV 결과로 지표·임계·주 질문 변경 금지

## 9. EVAL (1회)
- 동결 파이프라인으로 EVAL 141 질의를 KO·EN 각각 1회 실행 → 채점 → `/rg-verify`(다른 세션)
- 비교군: 같은 chunking의 BM25를 EVAL에서 함께 실행(기준선 보고용, 선택에 사용 안 함)
- EVAL 결과를 본 뒤 파이프라인·τ·chunk·질의·정답 변경 = deviation + exploratory, confirmatory 재평가는 새 질의·정답 버전 필요

## 10. 지표 (정의)
| # | 지표 | 정의 |
|---|---|---|
| 1–3 | Source Recall@1/5/10 | EP 질의 중 상위 k chunk(중립 제거 후)의 출처에 gold source ≥1 |
| 4 | Passage Recall@k (k=5,10) | 질의별 gold 단위 중 상위 k chunk가 덮는 비율의 평균 |
| 5 | MRR@10 | 첫 gold-source chunk 순위의 역수 |
| 6 | Relevant passage hit rate@5 | 상위 5에 gold 단위 덮는 chunk ≥1 인 EP 질의 비율 |
| 7 | **Unsupported retrieval rate (URR)** | NE 질의 중 시스템이 EVIDENCE_FOUND(τ 이상)를 낸 비율 |
| 8 | False evidence rate | EP 질의 중 EVIDENCE_FOUND 이면서 상위 5에 gold·disputed 단위가 하나도 없는 비율 |
| 9 | Abstention accuracy | scorable 전체에서 상태(근거/UNKNOWN) 정답 비율 + 균형 정확도 |
| 10 | source_id 정확성 | 반환 chunk의 source_id = chunk 텍스트가 실제 속한 문서 |
| 11 | section/chunk provenance 일치 | 반환 heading_path·문자 범위로 units-v1 원문 재구성 = chunk 텍스트(해시 일치) |
| 12 | 원문 존재 비율 | 반환 passage가 정규화 원문의 부분 문자열인 비율 |
| 13 | 반복 일치 | 같은 입력 5회: 순위·chunk_id 동일, 점수 차 ≤1e-6 |
| 14 | 결정적 재현 | 프로세스 재시작 3회 + 동결 색인 재로드: 13과 같은 기준 |
| 15–18 | 지연 p50/p95(cold·warm 분리) · 최대 RSS · VRAM · 장치(CPU/GPU) | |
| 19 | 외부 연결 | `unshare -rn` 네트워크 차단 실행 + 연결 시도 기록 0, 양성 대조(같은 환경에서 외부 연결 코드가 실패) |
| 20 | 오프라인 부팅·실행 | 차단 환경에서 색인 로드·질의 전 과정 성공 |
| X1 | 교차 언어 차 | 지표 1–9의 (EN→EN) − (KO→EN) 쌍대 차 |
| X2 | 교차 언어 일관성 | 같은 질의 KO·EN 상위 5 출처 집합 Jaccard 평균 · 상위 5 chunk Jaccard · 상태(근거/UNKNOWN) 일치율 |

## 11. 주 endpoint 와 임계 정책
- **Gate(과제 요구, 고정)**: 지표 10·11·12 = 100% · 13·14 = 100% · 19 = 0 · 20 = 성공. 하나라도 실패 → `NO_GO`
- **PE-1 (확인적 후보)**: EVAL KO→EN URR, **격자 NO_EVIDENCE 질의만(n=99)**. 대조 질의(n=16, 범위 밖 질환 — 쉬운 음성)는 별도 보고하고 PE-1에 넣지 않음. 임계 **PROVISIONAL**: 점추정 ≤ 0.20 이고 95% CI 상한 ≤ 0.30
- **PE-2 (사전 선언된 표본 부족, 기술 통계)**: EVAL KO→EN Source Recall@5(n=14). PROVISIONAL 참고치 ≥ 0.70. **n<30 이므로 판정에 쓰지 않고 `RECALL_INCONCLUSIVE_N`으로 보고**
- 임계 근거: 이 과제(한국어 소견→영어 지침 근거 검색)에 대한 문헌 기준 없음 → 과제 요구(안전망 근거로 쓰려면 근거 없음 상황의 억지 근거가 낮아야 함)로 정한 PROVISIONAL 값. DEV 결과 확인 후 변경 금지
- 판정 범주: `GATES_FAIL → NO_GO` · gate 통과 + PE-1 충족 → `ABSTENTION_PROVISIONAL_PASS` · PE-1 CI 하한 > 0.30 → `ABSTENTION_FAIL` · 그 외 → `INCONCLUSIVE` · PE-2는 항상 `RECALL_INCONCLUSIVE_N`(v0)
- **v0 결과만으로 "검색 성능 GO" 선언 불가**(재현율 표본 부족). 재현율 확인적 평가는 질의 확장 버전(queries-v1·gt-v1, 새 사전등록) 필요 — 사용자 결정 `D-N`

## 12. 통계
- 단위 = 질의. 비율 95% CI = Wilson(주) + 질의 단위 bootstrap 10,000(seed 20261002, percentile, 보조)
- 쌍대 차(KO vs EN, 선택 구성 vs BM25) = 같은 질의 차의 bootstrap. secondary는 다중 비교 보정 없이 기술만
- 최소 표본: 판정용 n ≥ 30(EP·NE 각각). 미달 지표는 판정 제외

## 13. 오프라인 요구
- 런타임: 외부 API 0 · 클라우드 벡터 DB 0 · Hugging Face 런타임 fetch 0 · telemetry 0 · 런타임 모델 다운로드 0
- 환경: `HF_HUB_OFFLINE=1`·`TRANSFORMERS_OFFLINE=1`·`HF_DATASETS_OFFLINE=1`·`HF_HUB_DISABLE_TELEMETRY=1`·`DO_NOT_TRACK=1`, 로컬 경로 로드, `trust_remote_code=False`
- 설치(빌드 시점, 사용자 승인 후): 전용 venv(`~/ai_env` 변경 금지) · 가중치 SHA 기록 · 새 의존성 import 시 외부 연결 검사(onnxruntime 사례)
- master `release_offline_check.sh` 수정 금지 → RAG 전용 오프라인 검사 스크립트를 이 브랜치에

## 14. 동결·변경 규칙
- corpus·addendum·units·질의·정답·프로토콜·이 문서 = SHA 동결. 변경 = 새 버전 + `rg.py deviation` + 재심사
- v0 평가 끝나기 전 corpus 변경 0, 새 출처는 `corpus/v1-candidates.md`에 기록만
- EVAL 결과 열람 후 변경 = exploratory

## 15. 공개 사항
1. 정답은 LLM(두 모델)이 작성·검증. 임상 전문가 검수 아님. 열람 제한은 지시로만 강제
2. 메인 세션은 정답 상태별 개수·WD별 분포·불일치 유형을 봄(검색 결과 아님). 이를 보고 바꾼 것: amend-01(NO_AGREED_LOCATION → UNSCORABLE), PE-2를 기술 통계로 지정, 최소 n 규칙. 분할·질의·정답 내용은 변경 0
3. units-v0 = REJECTED(뒷부분 절 포함) → units-v1. gt-v0 = SUPERSEDED → gt-v0.1. 둘 다 정답 내용 변경 없이 규칙 적용만
4. Author A 1번 묶음은 단위 ID 한 칸 밀림을 스스로 수정했다고 보고. 3번 묶음 B는 A의 단위 한 칸 밀림 8건을 DISAGREE 처리 → 해당 질의는 MISSED로 UNSCORABLE 또는 중립 처리
5. 코퍼스 coverage(어휘 기반)는 질의 생성 전에 이미 계산·공개
6. Corpus 동결이 사전등록보다 먼저(사용자 지시, 결과 없음)

## 16. 실행 순서 (각 단계 사용자 승인)
1. 이 사전등록으로 `/rg-gate EXP-SN-RAG-001` → RUN 아니면 중단
2. 사용자 승인: D-INSTALL(venv·모델 3개·reranker 다운로드), D-N
3. 설치·가중치 SHA → 오프라인 검사 → chunk 3종 생성·해시 → 색인 → DEV 22 구성 → 선택·동결
4. EVAL 1회 → 채점 → `/rg-verify`

## 17. 미결정
| ID | 내용 |
|---|---|
| D-INSTALL | 모델·라이브러리 다운로드·설치 승인 |
| D-N | EVAL EP 14 → 재현율 확인적 평가를 위해 질의 확장(queries-v1·gt-v1) 여부 |
| D-THR | PROVISIONAL 임계(PE-1 ≤0.20/≤0.30) 승인 |
