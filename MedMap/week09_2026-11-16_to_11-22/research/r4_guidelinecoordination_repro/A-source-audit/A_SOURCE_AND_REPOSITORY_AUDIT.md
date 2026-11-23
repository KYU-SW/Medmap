# A. 논문·공개 저장소·라이선스 감사 (GuidelineCoordination)

- 작성: SUBAGENT A, 2026-11-18
- 태그: [원문으로 확인한 사실] [실제 실행해 확인한 결과] [연구 가설] [아직 검증하지 못한 사항]
- "실제 실행"은 읽기 전용 통계·산술 검산만 뜻한다(파이프라인 코드 실행, LLM 호출 없음).
- 출처 목록: `sources.csv` (S1–S10)

## 0. 판정 요약

| 항목 | 판정 |
|---|---|
| 논문 신원 | **확인됨**: arXiv 2604.17340 v1, Shiyao Xie·Jian Du (북경대) |
| 저장소가 논문의 공식 저장소인지 | **확인됨**: 논문 초록 아래에 이 저장소 URL이 적혀 있음 |
| 논문 평가 데이터 전부 공개 | **미통과**: 563개 규칙 파일 1개만 있음. 226쌍 관계 정답, 노이즈 테스트셋, 기준선 LLM 출력, 평가 스크립트 없음 |
| 코드만으로 재현 | **불가능**: 실행 진입점, 의존성 파일, `standard/` 용어집, 지침 원문, 프롬프트 외 설정 없음. LLM API 필요 |
| 80.1%·F1 0.861 재계산 | **불가능**: 교정 전 출력과 관계 정답이 공개되지 않음 |
| 코드 라이선스 | **LICENSE 파일 없음**: 기본 저작권 보유 상태. 재배포·수정 허락 없음 |

## 1. 논문 신원 검증

[원문으로 확인한 사실] (S1, S2, S3)
- 제목: *Neuro-Symbolic Resolution of Recommendation Conflicts in Multimorbidity Clinical Guidelines*
- 저자: Shiyao Xie, Jian Du (Jian Du가 교신저자 \*). 소속 2곳 표기: ① Peking University, National Institute of Health Data Science ② Peking University Health Science Center, Institute of Medical Technology. 저자별 소속 대응은 HTML·PDF에 표시되지 않음.
- arXiv: 2604.17340, **v1만 존재** (2026-04-19 09:22:17 UTC 제출, 24,254 KB). v2 없음(2026-11-18 기준).
- DOI: 10.48550/arXiv.2604.17340 (arXiv DOI). 학회 프로시딩 DOI는 찾지 못함.
- 분야: cs.CL. Comments: AAAI-40(2026) **Bridge Program on Logic & AI** 채택.
- 논문 라이선스: CC BY 4.0 (arXiv HTML 표기).
- Underline 강연 페이지: 같은 제목, AAAI 2026, 2026-01-20, 싱가포르 (S7, 요약 도구 경유).
- 이전 세션의 'Xie & Du 2026' = 이 논문. 일치.

[아직 검증하지 못한 사항]
- 브리지 프로그램 논문이 AAAI 공식 프로시딩에 실렸는지, 별도 DOI가 있는지.
- PDF 11쪽 = 본문 + 부록 A–D. 그림 3(세부 유형별 F1 레이더)과 그림 4(노이즈 0–8 F1 곡선)의 수치는 본문에 없음.

## 2. 원문 확인 수준

| 자료 | 수준 |
|---|---|
| arXiv HTML v1 | curl로 직접 받아 텍스트로 변환하고 grep으로 확인 (요약 도구 결과는 교차검증용으로만 사용) |
| arXiv PDF v1 | 직접 받아 PyMuPDF로 텍스트 추출. 핵심 수치 출현 확인 |
| 저장소 | 로컬 고정 사본을 전부 직접 읽음 (`rules_gold.json`은 python으로 통계) |
| AAAI 채택 | arXiv comments + Underline 페이지(2차) |

## 3. 저장소·commit

[원문으로 확인한 사실] (S4, S5)
- URL: https://github.com/Shiyaoa/GuidelineCoordination
- `git ls-remote` 결과 원격 `HEAD` = `refs/heads/main` = **deb4ae34bdb055f93301bd93ed640d8c77e0ee5e** → 로컬 고정 사본과 같음.
- commit 3개:

| SHA | 날짜(+0800) | 내용 |
|---|---|---|
| efd6ec204910d00422acd22a635698bbec0bfc68 | 2025-12-06 17:29 | `rules_gold.json`만 업로드 (11,690줄) |
| 01047e3a924eda6cc78e4d77f9091a6e4f6bdd14 | 2025-12-26 10:25 | `pipeline/` 14개 파일 + README + .gitignore (6,233줄) |
| deb4ae34bdb055f93301bd93ed640d8c77e0ee5e | 2025-12-26 10:26 | merge |

- GitHub API: created 2025-12-06, 마지막 push 2025-12-26, `license: null`, release 없음, 설명 없음, star 2, fork 1개(2026-07 생성, 같은 commit의 사본).
- 시간 순서: 저장소 공개(2025-12) → AAAI 발표(2026-01-20) → arXiv(2026-04-19). arXiv 이후 저장소 갱신 없음.
- `pipeline/` 파일은 **12개 .py + `__init__.py` = 13개**. README 1개를 더하면 commit 01047e3의 파일 수 14. 메인이 적은 "14개 .py"는 실제로 .py 13개.

[아직 검증하지 못한 사항]
- 같은 저자의 다른 저장소 `conflict_reasoning`(2024-12), `guideline2action`(2026-09)이 관련 코드나 데이터를 담고 있는지. 이번 범위 밖이라 열지 않음.

## 4. 코드 구조 (직접 읽음, 실행 안 함)

| 파일 | 줄 | 역할 |
|---|---|---|
| `__init__.py` | 251 | 공개 API 재노출. 사용 예시(`create_pipeline`, `pipeline.run([...])`, `save_to_gen`) docstring |
| `config.py` | 78 | `LLMConfig`: base_url `https://openrouter.ai/api/v1`, model `deepseek/deepseek-v3.1-terminus`, temperature 0.1, max_tokens 16384. `PathConfig`: `standard/`, `gen/`. `MatchConfig`: 퍼지 임계값 80/80/70/90. 환경변수 `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` |
| `graph.py` | 1381 | LangGraph 워크플로와 **프롬프트 전부**: RECOMMENDATION(권고 추출, 중국어), TERMS, MED_TERMS, PREDICATES(영어), RULES(중국어). 노드: 권고 추출 → LSH 클러스터 → 클러스터별 용어/약물/술어/규칙 추출. 술어 ID 조립(`assemble_predicate`) |
| `graph_api.py` | 590 | 단계별 실행 API, `ClinicalGuidelinePipeline`, 비동기 클러스터 fan-out, `cluster_cache.json` → `gen/` 저장, `create_pipeline()` |
| `models.py` | 407 | Pydantic 모델: Term, MedicationTerm, Predicates, Action, Provenance, ClinicalRule, Permission(14종) 열거형, OperatorType(Has/On/HistoryOf/Assess/Risk/Stage/Value/Duration/Delta) |
| `processors.py` | 262 | rapidfuzz `token_sort_ratio`로 LLM 출력 용어를 로컬 표준 용어집(`standard/*.json`)에 맞춤 |
| `standard_library.py` | 110 | `standard/terms.json`, `meds.json`, `predicates.json` 로드(없으면 경고 후 빈 리스트) |
| `lsh_cluster.py` | 223 | 3-gram shingle + MinHash LSH + union-find 클러스터링 |
| `z3env.py` | 542 | 술어 `formal_definition` 문자열 → Z3 식(제한된 `eval`), 동치/함의/상호배제 검사 |
| `analyzer.py` | 1710 | PredicateAnalyzer(술어 격자), ActionAnalyzer(conflict/disagreement/independent), RuleAnalyzer, ConflictResolver(LSH·bucket 후보 필터, `max_pairs=10000`, 전이 폐포), 보고서 출력. 입력 `gen/rules.json` + `gen/predicates.json` |
| `io_utils.py` | 554 | `gen/` 저장·로드, 실패 작업 로그 |
| `rate_limiter.py` | 64 | asyncio 동시성·속도 제한 |

[원문으로 확인한 사실] 평가 관련 코드 없음: `grep`으로 eval/metric/precision/recall/F1/gold/benchmark/GPT/Gemini/Qwen/noise 검색 → 해당 없음(`eval`은 z3env의 식 파싱뿐). `if __name__ == "__main__"` 진입점 없음.

### 4-1. 분류 규칙 (논문 부록 A와 비교)
[원문으로 확인한 사실] `analyzer.py:_determine_overall_relation`
- 행동 독립 → others
- 조건 동치 + 행동 동치/충돌/불일치 → complete_redundancy / intrinsic_conflict / intrinsic_disagreement
- 조건 함의 + 동치/충돌/불일치 → contained_redundancy / implication_conflict / implication_disagreement
- 조건 교차 + 충돌 → local_conflict
- **조건 관계 UNKNOWN(Z3 판정 실패) + 행동 충돌 → 역시 local_conflict**로 분류 ("May need manual review" 메시지)
- `analyze_rules(focus_on="conflicts")`는 disagreement 두 종류도 conflict 묶음에 포함

[연구 가설] 표 2의 Local Conflict 2,442쌍에는 Z3가 조건 관계를 판정하지 못한 쌍이 섞였을 수 있다. 논문은 이 규칙을 언급하지 않는다. 확인하려면 파이프라인 출력(`predicates.json`)이 필요하다.

## 5. 실제 평가 데이터

### 5-1. 공개된 것: `rules_gold.json` 1개
[실제 실행해 확인한 결과] (python 읽기 전용 통계)
- 형식: JSON 리스트 **563건**, 모든 항목이 `id, label, condition, action, provenance` 5개 필드. id 중복 없음.
- `provenance`: 항목마다 1개. 필드 `source, quote, recommendation_grade, evidence_level`. quote 고유값 456개(같은 quote에서 여러 규칙 분리). quote 총 30,303자, 최장 178자.
- source 문자열 14종 = 실제 지침 **12종** + 같은 공동합의 표기 변형 1쌍("…专家共识（2023版）" 35건 / "…（2023）" 29건) + 빈 문자열 3건.
- 빈 label 20건. source 빈 값 3건.
- permission 분포: recommend 147, allow 114, avoid 85, contraindicate 53, caution 35, consider 25, continue 22, reduce_dose 21, stop 21, require 18, start_low_dose 9, increase_dose 6, max_dose_limit 6, titrate 1 (14종, 부록 D와 같음).
- condition 안 술어 고유 394개, 모두 `pred.has_ckd`, `pred.egfr_lt_15` 같은 **자유 snake_case 이름**. 술어 정의(`formal_definition`)는 파일 어디에도 없음.
- 약물(subjects) 고유 77개. SGLT2i 외 약도 포함(glibenclamide, ω-3 지방산, semaglutide, finerenone 등).

### 5-2. 정답 라벨 파일 여부
| 논문이 쓴 평가 자료 | 공개 여부 |
|---|---|
| 지침 12개 원문(입력 텍스트) | **없음** (출처 제목만 provenance에 있음) |
| 규칙 형식화 평가: 교정 전 565개 파이프라인 출력 | **없음** |
| 규칙 형식화 평가: 사람 교정 정답 | 부분. `rules_gold.json` 563개가 교정본일 가능성 [연구 가설], 파일에 교정 여부·오류 표시 없음 |
| 술어 정의(`predicates.json`)·용어집(`standard/`) | **없음** → gold 규칙만으로 Z3 분석 불가 |
| 226쌍 관계 정답(표 1) | **없음** |
| RAG 노이즈 테스트셋(고립 규칙 0–8개 주입) | **없음** |
| 기준선 LLM 프롬프트·출력 | **없음** |
| 평가 스크립트 | **없음** |
| 표 2 전체 관계 목록(2,442/115/37/57/16) | **없음** |

## 6. 규칙 변환 평가 vs 권고 관계 평가 (논문 정의)

### 6-1. 규칙 변환(형식화) 정확도 — §5.1 "Evaluation of Formalization Accuracy"
[원문으로 확인한 사실]
- 평가자: "An expert author with dual expertise in clinical medicine and data science" **1명**(저자 본인). 평가자 간 일치도 보고 없음.
- 대상: 파이프라인이 만든 **565개 Rule 객체**.
- 기준: "Strict Exact-Match" — 형식화된 술어 ID와 행동(Permission, Subject)이 원문 provenance와 **의미상 동일**해야 정답. 부분 일치는 실패.
  - 이름은 exact-match지만 실제 판단은 사람의 의미 동일성 판정. 문자열 일치 지표가 아님. requirements 필드는 기준에 없음.
- 결과: Formalization Accuracy **80.1%**, 교정 필요 **19.9%**, 오류 **111건**.
- 오류 분류: Contextual Loss 56.7%(63), Entity Grounding Failure 19.6%(23), Predicate Distortion 12.6%(14), Action Alignment Error 8.1%(9).
- 결론부: "80% accuracy in zero-shot translation".

[실제 실행해 확인한 결과] 산술 검산
- 111/565 = **19.6%**, 454/565 = **80.4%** → 논문의 80.1%/19.9%와 맞지 않음.
- 오류 111건, 80.1%, 19.9%가 모두 맞는 분모는 557–559 (예: 447/558 = 80.1%, 111/558 = 19.9%).
- 오류 유형 합 63+23+14+9 = **109** ≠ 111. 23/111 = 20.7% (논문 19.6%). 63/111=56.8%, 14/111=12.6%, 9/111=8.1%는 맞음.

[연구 가설] 실제 분모는 565가 아닐 수 있다(약 558, 예: 판정 불가 7건 제외). 이 가설은 563과도 맞지 않는다. 원자료 없이는 검증할 수 없다.

### 6-2. 관계 탐지 평가 — §4.2 Gold Standard + 표 1 + §5.3 표 3
[원문으로 확인한 사실]
- Gold Standard: 파이프라인 출력에서 만들고 "Clinical experts"가 후보 규칙쌍을 검토해 오분류 교정. 전문가 수·자격·일치도 **미공개**. 희귀 관계는 전부 유지, 흔한 관계는 down-sampling, "관계 없음" 음성 표본 추가.
- 표 1 (226쌍): Conflict 97 (local_conflict 20, implication_conflict_or_disagreement 40, intrinsic_conflict_or_disagreement 37), Redundancy 69 (complete 15, contained 54), None 60. → **Conflict 클래스에 disagreement(같은 범주 강도 차이)가 포함됨**.
- 표 3 Conflict 행: Ours P 0.826 / R 0.898 / **F1 0.861**. Redundancy 행: Ours 0.689 / 0.775 / 0.729.
- 기준선: DeepSeek-v3.1, Qwen-Max, Gemini-2.5-pro, GPT-5 (본문 §5.3은 "three"라고 쓰고 Qwen-Max를 빠뜨림). Conflict 재현율 0.082 / 0.093 / 0.144 / 0.186, F1 0.148 / 0.165 / 0.224 / 0.298.
- "Ours"는 "end-to-end performance of the automated agents without human correction".
- F1의 공식 정의, 평균 방식(micro/macro), 노이즈 수준(0개인지), 평가 단위는 **본문에 명시 없음**.

[실제 실행해 확인한 결과] 표 3 역산 (3자리 반올림 일치하는 정수 TP 검색)
- 기준선 4개는 모두 분모 Conflict = 97, Redundancy = 69에서 정수 TP가 나옴 (예: GPT-5 Conflict 18/97 = 0.186, 정밀도 18/24 = 0.75; DeepSeek Redundancy 53/69 = 0.768).
- **"Ours"는 97·69 분모에서 정수 TP가 나오지 않음** (0.898×97 = 87.1, 0.775×69 = 53.5). 정밀도·재현율이 동시에 맞는 최소 분모는 Conflict 127, Redundancy 40.
- F1 = 2PR/(P+R) 검산은 모두 맞음(Ours Conflict 0.860→0.861, 반올림 차이).

[연구 가설] "Ours"는 기준선과 다른 표본 집합이나 다른 집계(세부 유형 macro 평균, 노이즈 수준 평균 등)로 계산되었을 수 있다. 그렇다면 표 3의 직접 비교는 같은 조건 비교가 아닐 수 있다. 원자료가 공개되기 전에는 결론 보류.

### 6-3. 90.6% Local
[원문으로 확인한 사실] 초록과 결론에만 나옴. 이를 도출하는 표나 절은 없음.
[실제 실행해 확인한 결과] 표 2 기준 2442/(2442+115+37) = **94.1%**. 표 1 기준 20/97 = 20.6%. 어느 쪽에서도 90.6%가 나오지 않음.

### 6-4. 기타 내부 불일치 [원문으로 확인한 사실]
- 표 1(표본) vs 표 2(전체): contained 54 vs 57, complete 15 vs 16, local 20 vs 2,442. 표본 수가 모두 전체 이하라 **모순은 아님**. 단 표 1의 implication 40은 disagreement 포함이라 표 2의 implication conflict 115와 직접 비교 불가.
- 결론의 "Recall < 18%" vs 표 3 GPT-5 재현율 0.186. 본문 §5.3 "0.08–0.18".
- §4.1의 corpus는 "SGLT2i에만 초점"이라고 했으나, gold 규칙에는 SGLT2i 외 약이 다수 있음.

## 7. 평가 규칙이 프롬프트 작성에 쓰였는지
[실제 실행해 확인한 결과]
- gold 규칙 id 563개 중 프롬프트(graph.py, models.py)에 나오는 것은 **0개**.
- 프롬프트 예시의 술어 ID 형식(`pred.Has.cond.hf`, `pred.Value.meas.egfr.ge.20`)과 gold의 술어 형식(`pred.has_hf`, `pred.egfr_lt_15`)은 **전혀 다름** → gold와 겹치는 술어 0개.
- 프롬프트 예시 "恩格列净…eGFR≥20 HF/CKD"와 비슷한 내용의 quote는 gold에 있음(恩格列净 포함 44건, eGFR≥20 포함 3건). 도메인이 같아 생긴 우연인지 개발 중 참고했는지는 판정 불가.

[원문으로 확인한 사실] 논문은 프롬프트를 싣지 않았고, 평가 자료를 프롬프트 개발에 썼는지 언급하지 않음(개발/평가 분할 서술 없음).

[연구 가설] gold의 술어 이름 형식이 현재 코드의 출력 형식과 다르므로, **gold는 현재 공개 코드보다 이전 버전 파이프라인 출력에서 만들어졌을 가능성**이 크다. 그러면 공개 코드로 다시 돌린 출력을 gold와 바로 exact-match 비교할 수 없고, 술어 대응표가 따로 필요하다.

## 8. 563 vs 565
[원문으로 확인한 사실] 논문은 565만 언급(§5.1). 563이라는 수는 논문에 없음. 저장소 README도 파일 설명 없음.
[연구 가설] 가능한 원인: (a) 교정 중 규칙 2개 삭제·병합, (b) 중복 제거, (c) 다른 시점 출력. 빈 label 20건·빈 source 3건이 있어 교정이 완전히 끝난 파일이 아닐 수도 있다.
[아직 검증하지 못한 사항] 어느 원인인지. 저자 문의 외에는 확인 경로 없음.

## 9. README vs 코드 / 논문 vs 코드 차이

### 9-1. README vs 코드
[원문으로 확인한 사실] README(중국어 23줄)는 `pipeline/` 11개 모듈 이름과 한 줄 설명만 있고 "使用说明 待补充…(사용 설명 추후 보충)". `rules_gold.json` 설명 없음. 나열된 모듈은 실제 파일과 일치(`__init__.py` 제외).

### 9-2. 논문 vs 코드
| 논문 서술 | 코드 실제 | 판정 |
|---|---|---|
| Recommendation Extractor가 4범주(Risk Assessment / Pharmacological / Non-pharmacological / Other) 분류 후 약물만 사용 (§3.1) | RECOMMENDATION_PROMPT가 처음부터 약물 치료 권고만 추출. 4범주 분류 없음 | 부분 불일치 |
| LSH로 의미 클러스터 | `lsh_cluster.py` MinHash LSH | 일치 |
| Entity Agent가 SNOMED CT·LOINC·RxNorm에 외부 검색 도구로 매핑, HL7 FHIR 준수 (§3.2) | SNOMED/LOINC/RxNorm/FHIR 문자열 0건. rapidfuzz로 로컬 `standard/*.json`에 퍼지 매칭(파일 미공개) | **불일치** |
| Predicate Agent 연산자 9종(부록 C) | `OperatorType` 9종 동일 | 일치 |
| Rule Agent·행동 어휘 14종(부록 D) | `Permission` 14종 + RULES_PROMPT 표 | 일치 |
| Z3 기반 관계 분류(부록 A) | `z3env.py`, `analyzer.py` | 일치. 단 UNKNOWN+충돌→local 규칙은 논문에 없음 |
| DeepSeek-V3.1 사용(§4.1) | 기본값 `deepseek/deepseek-v3.1-terminus` (OpenRouter) | 대체로 일치(Terminus 변형 여부는 논문에 없음) |
| 기준선 LLM 비교, RAG 노이즈 실험(§4.2, §5.3) | 코드 없음 | 미공개 |
| "Code and datasets are available" / "open-source the first … dataset" | 규칙 563개만 공개 | 과대 표기 |

## 10. 실행 환경·의존성
[원문으로 확인한 사실] import 추출(외부 패키지):
- `langgraph` (StateGraph, START, END, Send, add_messages)
- `langchain_core` (HumanMessage, SystemMessage, AnyMessage)
- `langchain_openai` (ChatOpenAI → OpenRouter)
- `pydantic` (BaseModel, Field, `root_validator(pre=False, skip_on_failure=True)` — v1 스타일. v2에서는 deprecated 경고와 함께 동작할 것으로 보임 [아직 검증하지 못한 사항])
- `z3` (z3-solver)
- `rapidfuzz`
- 표준 라이브러리: asyncio, json, os, re, pathlib, dataclasses, typing, collections, hashlib, functools, enum, datetime, time, operator
- `requirements.txt`, `pyproject.toml`, 버전 고정, Python 버전 명시 **모두 없음**.
- `langgraph.constants.Send`는 최신 langgraph에서 위치가 바뀌었을 수 있음 [아직 검증하지 못한 사항].
- 외부 호출: OpenRouter API(유료, `LLM_API_KEY`). 파이프라인 실행은 곧 과금 대상 → 사용자 승인 없이는 실행 불가.

## 11. 라이선스·이용 조건
- [원문으로 확인한 사실] 저장소에 LICENSE 파일 없음, GitHub API `license: null`.
  - 의미: 오픈소스 라이선스가 부여되지 않아 저작권자가 모든 권리를 보유한다. GitHub 이용약관상 GitHub 안에서 보기·fork는 허용되지만, 코드 복제·수정·재배포·논문 부록 게재 권리는 주어지지 않는다. 내부 재현 목적의 읽기·로컬 실행은 회색 지대로, 결과물에 코드를 포함해 공개하려면 저자 허락이 필요하다.
- [원문으로 확인한 사실] 논문 자체는 CC BY 4.0. 이는 논문 PDF·HTML에만 적용되며 저장소 코드·데이터에는 적용되지 않는다.
- [원문으로 확인한 사실] `rules_gold.json`의 `quote`는 중국 지침·전문가 공동합의(중화의학회 계열 학술지 게재본으로 보임) 원문 문장 563건(고유 456건, 총 30,303자)을 인용한다. 이 원문 저작권은 각 지침 발행처·학술지에 있으며 저장소 작성자가 재배포 권한을 줄 수 없다.
- [아직 검증하지 못한 사항] 각 지침의 게재 학술지와 그 이용 조건. 짧은 인용이 중국·한국 저작권법상 공정이용 범위인지.
- 권고: 재현 산출물에는 quote 원문 대신 규칙 id·해시만 공개하고, 코드와 데이터는 재배포하지 않는다. 필요하면 저자에게 라이선스 추가를 문의한다.

## 12. 이전 보고와의 불일치 표

| 이전 보고 내용 | 출처 | 이번 확인 | 판정 |
|---|---|---|---|
| 논문 arXiv 2604.17340 '추정' | 메인 | v1 원문 확인, 저자 Xie·Du | 확정 |
| "데이터·코드 공개 링크 없음 [원문으로 확인: arXiv abs]" | 이전 C (S9) | 논문 본문 초록 바로 아래에 GitHub 링크 있음(HTML·PDF 모두). abs 페이지에는 없음 | **이전 보고 오류**. 단 공개된 데이터는 일부뿐 |
| "전문가 수정 gold set" | 이전 C | 규칙 감사는 저자 1명. 규칙쌍 검토는 "Clinical experts"(인원 미상) | 부분 정정 |
| 형식화 오류 19.9%(111/565) | 이전 B (S8) | 논문 표기는 맞으나 111/565 = 19.6%. 논문 내부 산술 불일치 | 인용은 맞음, 수치 자체가 불일치 |
| 규칙 변환 정확도 80.1% | 메인 | §5.1 확인. 454/565 = 80.4%와 불일치. 지표 = 저자 1명의 의미 동일성 판정(술어 ID + permission + subject) | 수치 확인, 정의 보완 |
| LLM 충돌 재현율 0.08–0.19 | 이전 B | 표 3: 0.082–0.186 (본문 "0.08–0.18", 결론 "<18%") | 표 기준 맞음 |
| F1 약 0.861 | 메인 | 표 3 Conflict, Ours. Conflict 클래스에 disagreement 포함. 분모 97과 정합 안 됨 | 수치 확인, 조건 불명 |
| 565 규칙 변환 | 메인 | 565는 감사 대상 수. 공개 파일은 563 | 차이 원인 미상 |
| 226 권고 관계 사례 | 메인 | 표 1 확인. 정답 파일 미공개 | 확인 불가 |
| 12개 지침 | 메인 | 논문 §4.1·부록 B, gold source 12종과 일치 | 일치. 부록 B의 노인의학회 지침은 gold source 제목에서 찾지 못함 [아직 검증하지 못한 사항] |
| pipeline/ 14개 .py | 메인 | .py 13개(`__init__` 포함) + README = commit 내 14개 | 경미한 정정 |
| commit 3개(12-06, 12-26) | 메인 | 일치 | 일치 |
| 90.6% Local | 논문 초록 | 표 2로는 94.1%, 표 1로는 20.6% | 출처 불명 |

## 13. 재현에 필요한 조건

1. **규칙 형식화 80.1% 재현**: ① 지침 12개 원문(저작권 확인 후 확보) ② 교정 전 파이프라인 출력 565건 또는 같은 코드 버전 ③ 술어 정의·`standard/` 용어집 ④ 판정 기준서 ⑤ 독립 평가자 2명 이상(일치도 보고). ①–③이 없으면 같은 수치를 재계산할 수 없다. `rules_gold.json`은 "정답 후보"로만 쓸 수 있다.
2. **F1 0.861 재현**: 226쌍 관계 정답, 각 쌍의 규칙 id, 노이즈 주입 표본, "Ours" 평가 집합과 집계 방식, 기준선 프롬프트. 모두 미공개 → 저자 문의 필요.
3. **gold 규칙만으로 Z3 관계 분석**: 술어 394개의 `formal_definition`이 없어 그대로는 불가. 술어 이름(`pred.egfr_lt_15` 등)에서 정의를 재구성하는 방법은 가능하지만 재구성 자체가 새 변수가 된다 [연구 가설].
4. **코드 실행**: 의존성 버전 추정, `standard/` 빈 상태로 시작, OpenRouter 유료 API(과금 승인 필요), 실행 스크립트 작성 필요. LLM 출력 비결정성 때문에 같은 규칙 집합이 나온다는 보장 없음.
5. **공개 재배포**: 코드 LICENSE 없음, 지침 인용문 저작권 별개 → 재현 결과 공개 시 원문 quote·코드 포함 금지.

## 14. 출처
- arXiv abs: https://arxiv.org/abs/2604.17340
- arXiv HTML v1: https://arxiv.org/html/2604.17340v1
- arXiv PDF v1: https://arxiv.org/pdf/2604.17340v1
- 저장소: https://github.com/Shiyaoa/GuidelineCoordination (commit deb4ae34bdb055f93301bd93ed640d8c77e0ee5e)
- GitHub API: https://api.github.com/repos/Shiyaoa/GuidelineCoordination
- Underline AAAI 2026: https://underline.io/lecture/144580
- 상세 해시·접근 방식: `sources.csv`
