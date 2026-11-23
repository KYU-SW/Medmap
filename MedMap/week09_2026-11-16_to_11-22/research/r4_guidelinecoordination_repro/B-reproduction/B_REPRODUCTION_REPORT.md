# B_REPRODUCTION_REPORT — GuidelineCoordination 기존 알고리즘 실제 재현 (SUBAGENT B)

작성일 2026-11-18. 원본 commit `deb4ae34bdb055f93301bd93ed640d8c77e0ee5e` (Merge branch 'main' of https://github.com/Shiyaoa/GuidelineCoordination). 원본 무수정, 사본 `src_copy/`에서 실행(코드 diff 없음).

태그: [원문] = 원문(코드·논문)으로 확인한 사실, [실행] = 실제 실행해 확인한 결과, [가설] = 연구 가설, [미검증] = 아직 검증하지 못한 사항.

## 0. 판정 요약

| 실험 | 판정 | 근거 |
|---|---|---|
| 실험1 지침 문장 → 규칙 변환 (Formalization Accuracy 80.1%) | **NOT_RUN** | LLM(OpenRouter, 유료) 필수, 과금 승인 없음. 원문 지침 텍스트·LLM 출력·전문가 감사표도 저장소에 없음 |
| 실험2-a 충돌 탐지 F1 0.861 (226쌍 벤치마크) | **NOT_RUN** (계산 불가) | 226쌍 정답 라벨, predicates.json, 평가 스크립트 미공개. 논문 "Ours"는 LLM 추출 규칙 기반(사람 보정 없음) |
| 실험2-b 전체 코퍼스 관계 수 (논문 Table 2) | **PARTIAL_REPRODUCED** | 원본 analyzer를 gold 규칙에 실제 실행. 원본 그대로(predicates 없음)는 함의 계열 0건 → 불일치. 추가 변형(술어 = 독립 원자)에서만 Table 2와 근사 |

## 1. 실행 방법·진입점 [원문]

- README 사용법 "待补充"(미작성). 실행 스크립트·CLI·`__main__`·requirements·LICENSE 없음.
- 진입점 후보 2개.
  - `pipeline.create_pipeline(api_key, model).run(texts)`: LLM 추출(실험1). `graph.py` `_get_default_llm`/`_create_llm` → `langchain_openai.ChatOpenAI(base_url="https://openrouter.ai/api/v1", model="deepseek/deepseek-v3.1-terminus")`. `config.py` 가 환경변수 `LLM_API_KEY` 를 읽음.
  - `pipeline.analyzer.analyze_knowledge_base(gen_dir)`: Z3 관계 판정(실험2). `gen/rules.json` + `gen/predicates.json` 필요. 둘 다 저장소에 없음(`gen/`, `standard/` 디렉터리 부재).
- `pipeline/__init__.py` 가 `graph`(langgraph, langchain_core) 를 무조건 import → analyzer만 쓰려 해도 LLM 패키지가 필요한 구조. 본 재현은 `__init__` 을 건너뛰는 로더로 회피(원본 파일 무수정).
- 외부 접근 정적 분석: 네트워크 경로는 `graph.py` ChatOpenAI 2곳(그리고 이를 부르는 `graph_api.py`)뿐. `analyzer.py`/`z3env.py`/`lsh_cluster.py`/`models.py` 는 네트워크 없음. 파일 I/O: `RuleAnalyzer.__init__` 이 **현재 작업 디렉터리** 의 `gen/predicate_relations.json` 을 있으면 읽음(경로 하드코딩).
- 보안 참고: `z3env.expr()` 가 formal_definition 문자열을 `eval()` (builtins 제거) 로 해석. LLM 생성 술어를 그대로 eval 하는 구조.
- 원본 평가 명령: 없음. 226쌍 벤치마크, LLM 기준선(DeepSeek/Qwen/Gemini/GPT-5) 프롬프트·스크립트 모두 없음.

## 2. 환경 [실행]

- 별도 venv `B-reproduction/.venv` (Python 3.12.3). 설치: `z3-solver==5.4.1.0`, `pydantic==2.14.3` (+의존성). 전체 목록 `env.txt`. `~/ai_env` 미사용.
- LLM 패키지(langchain*, langgraph, openai, httpx) 미설치. 실행 스크립트가 socket 연결을 차단하고 해당 모듈 미로딩을 assert.
- CPU 단일 프로세스, GPU 미사용.

## 3. 데이터 (rules_gold.json) [실행]

`results/rules_gold_stats.json`

| 항목 | 값 |
|---|---|
| 규칙 수 / 고유 id | 563 / 563 |
| 필드 | id, label, condition, action{subjects, permission, requirements}, provenance[1개] |
| permission 분포 | recommend 147, allow 114, avoid 85, contraindicate 53, caution 35, consider 25, continue 22, reduce_dose 21, stop 21, require 18, start_low_dose 9, increase_dose 6, max_dose_limit 6, titrate 1 |
| source 문자열 | 14종 = 명명 지침 13 + 빈 문자열(3규칙). 13 중 2개는 같은 공식(二甲双胍 联合 SGLT2i 专家共识 "2023版" 35규칙 / "2023" 29규칙)의 표기 차이 → 실질 12개 지침 [가설: 논문 "12 guidelines"와 대응] |
| 참조 술어 수 | 394 (정의 `formal_definition` 은 파일에 없음, 0건) |
| OR/NOT 포함 condition | 130 |
| 빈 condition | 0 |
| 고유 subject(약물) | 77 |
| bucket_id(LSH 버킷) | 0건 → 원본 bucket 필터는 작동 안 함 |

논문 대조 [원문, arXiv 2604.17340 HTML]: 전문가가 감사한 규칙 수 565, 정확도 80.1%(111 오류; 111/565 = 19.6%로 19.9%와 불일치 — 논문 내부 불일치). rules_gold 563 ≠ 565. [가설] rules_gold 는 전문가 보정 후 "curated dataset" (논문 5.2 "manual correction of formalization errors" 후 solver 실행). [미검증] 563/565 차이 2건의 정체.

### 실험1 판정: NOT_RUN
LLM 호출 없이는 변환 불가. 변환 결과(LLM 원출력)와 감사표가 없어 rules_gold 를 정답으로 둔 정확도 계산도 불가.

## 4. 실험2 — 원본 analyzer 실제 실행 [실행]

실행기 `scripts/run_exp2.py` → 원본 `ConflictResolver(rules, predicates).generate_report()` + `export_report()` 를 그대로 호출. 판정 로직(ActionAnalyzer 권한 분류, RuleAnalyzer 조건 관계, LSH 후보, 전이 폐포)은 원본 코드.

### 4.1 핵심 제약
predicates.json 미공개 → `predicates=[]` 로 실행하면 `_expand_condition` 이 모든 술어에서 None → Z3 경로가 **한 번도 실행되지 않음**. 조건 관계는 "condition 문자열이 같으면 EQUIVALENT, 아니면 UNKNOWN" 뿐. UNKNOWN + 행동 충돌은 원본 규칙상 `local_conflict` 로 분류(analyzer.py `_determine_overall_relation`).
→ 이를 보완하는 **추가 변형(원본 아님)** `atom`: 394개 술어를 각각 독립 Bool 원자 `$ Has(atom.X) $` 로 합성해 넣음. 술어 간 의미 관계(예: eGFR<30 ⇒ eGFR<45)는 반영 못 하고 condition 의 AND/OR/NOT 구조만 Z3 로 판정.

### 4.2 결과 (규칙 쌍 수)

| 관계 | 논문 Table 2 [원문] | faithful_lsh (원본 기본값) | faithful_exhaustive | atom_lsh [추가] | atom_exhaustive [추가] |
|---|---|---|---|---|---|
| local_conflict | 2,442 | 2,602 | 6,865 | 2,523 | 6,779 |
| implication conflict (+disagreement) | 115 | 0 + 0 = 0 | 0 | 41 + 75 = 116 | 70 + 123 = 193 |
| intrinsic conflict (+disagreement) | 37 | 1 + 33 = 34 | 1 + 33 = 34 | 1 + 35 = 36 | 1 + 35 = 36 |
| contained_redundancy | 57 | 0 | 0 | 48 | 73 |
| complete_redundancy | 16 | 11 | 11 | 15 | 15 |
| others | - | 9,050 | 151,293 | 8,859 | 151,107 |
| 판정한 쌍(전이 폐포 포함) | - | 11,697 | 158,203 | 11,597 | 158,203 |
| LSH 후보 쌍 | - | 5,907 / 158,203 (96.3% 감소) | - | 5,907 | - |
| 실행 시간 | - | 4.7 s | 0.8 s | 66.5 s | 255.2 s |

[가설] 논문 Table 2 의 "Implication Conflict 115", "Intrinsic Conflict 37" 은 conflict + disagreement 합산으로 보임(atom_lsh 116/36 과 대응). 논문 본문이 정의를 명시하지 않음 [미검증].

local 비율: 논문 abstract 90.6%. Table 2 로 계산하면 2,442/2,667 = 91.6%(전 관계 대비) 또는 2,442/2,594 = 94.1%(충돌 계열 대비) — 논문 내부 불일치 [원문 기반 계산]. 본 실행: faithful_lsh 2,602/2,647 = 98.3%(충돌+중복 대비), atom_lsh 2,523/2,738 = 92.1%(충돌+중복 대비), 2,523/2,675 = 94.3%(충돌 계열 대비).

### 4.3 관찰 [실행]
1. **원본 그대로는 함의 계열을 못 냄**: predicates 정의가 없으면 implication_* / contained_redundancy 가 0. 논문 Table 2 재현에 predicates.json 이 필수.
2. **local_conflict 과다 판정 구조**: 조건 관계 UNKNOWN 이어도 행동이 충돌하면 local_conflict. faithful 에서 local_conflict 2,602건 전부가 condition_relation=unknown. 즉 "같은 약물에 금지 vs 허용" 이면 조건 겹침 확인 없이 충돌.
3. **결과 수의 대부분이 전이 폐포에서 나옴**: faithful_lsh 비-others 2,647쌍 중 1,968쌍(74%)이 LSH 후보가 아니라 `_apply_transitive_closure`(같은 관계 라벨의 연결 성분 내 모든 쌍 재판정)로 추가됨. atom_lsh 는 2,738 중 1,972(72%). 보고 수치가 LSH 파라미터·폐포 단계에 크게 의존.
4. LSH 후보 축소 후 local_conflict 2,602 vs 전 쌍 6,865 → 원본 기본 파이프라인은 전 쌍 대비 충돌 쌍의 약 38%만 보고(faithful 기준).
5. 유일한 intrinsic_conflict: `rule.ckd_egfr_lt_15_or_dialysis_continue_sglt2`(continue) vs `rule.ckd_egfr_lt_15_or_dialysis_stop_sglt2`(stop), 같은 condition. 모든 모드에서 동일.
6. 결정성: faithful_lsh 재실행(`results/rerun_check/`, `logs/exp2_faithful_lsh_rerun.log`) 결과 쌍 집합·관계 라벨·요약 수치는 완전히 동일. 바이트 단위 차이는 `recommendation` 문자열 안의 subjects 집합 출력 순서와 원본 report JSON 의 나열 순서뿐(Python 문자열 hash 무작위화 때문, PYTHONHASHSEED 미고정). MinHash 는 md5 기반이라 후보 결정적.

### 4.4 atom_exhaustive [추가 변형]
전 쌍 158,203 판정, 255.2 s, rc=0 (`logs/exp2_atom_exhaustive.log`, 완료 파일 `logs/exp2_atom_exhaustive.done`). 충돌 계열 7,008쌍(local 6,779 = 96.7%), 중복 88쌍. condition 관계: intersect 150,372 / p_implies_q 1,628 / q_implies_p 1,509 / equivalent 481 / mutex 300 / unknown 3,913. LSH+폐포(atom_lsh) 대비 local_conflict 의 37%(2,523/6,779), contained_redundancy 의 66%(48/73), implication 계열의 60%(116/193)만 기본 파이프라인이 보고.

### 4.5 F1 0.861
226쌍 정답 미공개 → 계산 불가. 논문 Table 1 분포 [원문]: 226 = Conflict 97(local 20, implication 40, intrinsic 37) + Redundancy 69(complete 15, contained 54) + None 60. Table 3 "Ours" Conflict P/R/F1 = 0.826/0.898/0.861, Redundancy 0.689/0.775/0.729. 0.861 은 Conflict 범주 F1(전체 F1 아님).

## 5. 결과 파일

- `results/exp2_<mode>_pairs.csv` (mode ∈ faithful_lsh, faithful_exhaustive, atom_lsh, atom_exhaustive): 원본 analyzer 가 판정한 모든 쌍(others 포함). 충돌 쌍만 쓰려면 `is_conflict_family==1`.
- `results/exp2_<mode>_summary.json`: 수치·시간·버전.
- `results/exp2_<mode>_upstream_report.json`: 원본 `export_report()` 그대로의 JSON(관계별 쌍 + provenance + 제안).
- `results/rules_gold_stats.json`.

### CSV 열 정의
| 열 | 의미 |
|---|---|
| mode | 실행 모드 |
| rule_a, rule_b | 규칙 id (rules_gold.json `id`). 순서는 원본이 낸 그대로(방향 의미: p_implies_q 는 rule_a 조건 ⇒ rule_b 조건) |
| overall_relation | 원본 `RuleRelation` 값: complete_redundancy, contained_redundancy, intrinsic_conflict, intrinsic_disagreement, implication_conflict, implication_disagreement, local_conflict, others |
| condition_relation | 원본 `PredicateRelation`: equivalent, p_implies_q, q_implies_p, mutex, intersect, unknown |
| action_relation | 원본 `ActionRelation`: equivalent, conflict, disagreement, independent |
| is_conflict_family | 1 = 원본 `analyze_rules(focus_on="conflicts")` 집합(local/intrinsic/implication conflict + intrinsic/implication disagreement) |
| is_strict_conflict | 1 = *_conflict 3종만(disagreement 제외) |
| is_redundancy | 1 = complete/contained redundancy |
| subjects_overlap | 두 규칙 action.subjects 교집합, `|` 구분 |
| permission_a, permission_b | action.permission |
| condition_a, condition_b | condition 원문 |
| source_a, source_b, same_source | provenance[0].source 및 동일 여부(1/0) |
| in_lsh_candidates | 1 = LSH 후보에서 판정, 0 = 전이 폐포로 추가 판정, 빈칸 = exhaustive 모드 |
| recommendation | 원본이 생성한 설명 문자열 |

## 6. 남은 일 / 미검증
- [미검증] predicates.json(394 술어 formal_definition), gen/predicate_relations.json, 226쌍 라벨을 저자에게서 받으면 faithful 모드로 Table 2·F1 직접 재현 가능.
- [미검증] 실험1 은 과금 승인 시에만(OpenRouter deepseek-v3.1-terminus) 실행 가능.
- [미검증] 논문 "Ours" 는 LLM 추출 규칙(보정 전) 기준이라 gold 규칙 결과와 직접 비교 대상이 다름.
