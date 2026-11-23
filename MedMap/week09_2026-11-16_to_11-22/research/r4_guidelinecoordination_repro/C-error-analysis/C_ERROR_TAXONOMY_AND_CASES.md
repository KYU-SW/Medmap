# SUBAGENT C — 실패 사례와 오류 원인 분석

- 대상 논문: "Neuro-Symbolic Resolution of Recommendation Conflicts in Multimorbidity Clinical Guidelines", Shiyao Xie, Jian Du, arXiv:2604.17340v1(2026-04-19 제출) [원문으로 확인한 사실]
- 대상 저장소: Shiyaoa/GuidelineCoordination, commit deb4ae34bdb055f93301bd93ed640d8c77e0ee5e (읽기 전용)
- 정답 파일 SHA256: 0de930e75b1174e8585e4b05e4cfd0667afe97c6341c034af961fa975e0ae317
- LLM 호출 없음, 유료 API 없음. 모든 실행은 2분 이내로 끝남, 로그는 `logs/`

## 0. 판정 요약

| 항목 | 판정 |
|---|---|
| 논문 오류 분석 추출 | 통과(범주·개수·비율·분모 추출 완료. 단, 논문 내부 수치 불일치 있음) |
| 공개 예측-정답 쌍으로 오류 직접 추출 | 불가능(예측 파일 미공개. 저장소에는 rules_gold.json 1개뿐) |
| rules_gold.json 정답 품질 감사 | 부분 통과(형식 문제·의미 문제 모두 관찰됨. 무작위 60건 중 실질 문제 14건, 23.3%) |
| 논문 Table 2 Intrinsic Conflict 예시의 해석 | 이의 있음(같은 지침의 같은 문장에서 나온 규칙 쌍. 아래 G01) |
| 충돌 탐지 재실행(Z3) | 불가능(predicates.json·terms.json·meds.json 미공개) |

## 1. 논문 원문의 오류 분석 [원문으로 확인한 사실]

HTML판(AAAI 양식)에는 절 번호가 없다. 위치는 절 제목으로만 적는다. (WebFetch 요약 도구가 "6.1"·"5.1"처럼 서로 다른 번호를 붙였으나 원본 HTML의 `ltx_tag`에는 절 번호가 없음 — [실제 실행해 확인한 결과])

### 1.1 Results > Evaluation of Formalization Accuracy

- 감사 방식: 임상의학·데이터과학을 함께 전공한 저자 1명(an expert author)이 파이프라인이 만든 Rule 객체 565개를 수동 감사
- 정답 기준: Strict Exact-Match. 형식화된 Predicate ID와 action(Permission, Subject)이 원문과 의미상 같아야 Correct. 부분 일치는 실패
- 결과: Formalization Accuracy 80.1%, "19.9% of cases required correction", 오류 111건
- 평가자 간 일치도: 보고 없음(평가자 1명)

| 원문 범주 | 원문 비율 | 원문 건수 | 원문 정의·예시(요약) | 대응 후보 유형 |
|---|---|---|---|---|
| Contextual Loss | 56.7% | 63 | 암묵적 진단 맥락 누락. 예: "Treatment for T2DM" 절의 권고에 `pred.has_t2dm`이 빠져 규칙이 지나치게 넓어짐 | 필수 조건 누락, 과대 적용 |
| Entity Grounding Failure | 19.6% | 23 | 약물 개체 환각·오분류. 예: gliflozin 간 혼동, 상품명을 RxNorm으로 연결 실패 | 용어 연결 오류 |
| Predicate Distortion | 12.6% | 14 | 없는 조건 환각, 중요한 제외 조건 누락, 수치 연산자 반전 | 지침에 없는 조건 추가, 예외 누락, 비교 연산자 오류 |
| Action Alignment Error | 8.1% | 9 | 권고 강도·방향 불일치. 예: "should be considered"를 Recommend로, Avoid와 Contraindicate 혼동 | 권고/근거 혼동 |

분모: 원문은 비율의 분모를 111(오류 건수)로 적었다.

### 1.2 원문 수치 재계산 [실제 실행해 확인한 결과]

| 검산 | 값 | 판정 |
|---|---|---|
| 범주 건수 합 63+23+14+9 | 109 | 111과 2건 차이 |
| 범주 비율 합 | 97.0% | 100% 아님 |
| 63/111, 14/111, 9/111 | 56.8%, 12.6%, 8.1% | 표기와 일치 |
| 23/111 | 20.7% | 표기 19.6%와 불일치(19.6%×111 = 21.8건, 약 22건) |
| 111/565 | 19.65% | 표기 19.9%와 불일치 |
| 1−0.801 = 19.9% → 565×0.199 | 112.4건 | 111건과 불일치 |
| 저장소 규칙 수 | 563 | 논문 565와 2건 차이(원인 확인 필요) |
| 초록 "90.6% of conflicts are Local" vs Table 2 | 2442/(2442+115+37)=94.1%, 2442/2667(전체 관계)=91.6% | 90.6%의 분모 확인 필요 |
| Table 1 contained_redundancy 54 vs Table 2 Contained Redundancy 57 | — | 집합이 다르면 문제 없음(Table 1은 표본 benchmark, Table 2는 전체 분석), 확인 필요 |

### 1.3 기타 원문 사실

- 충돌 F1 0.861(Table 3, "Ours", Conflict: P 0.826, R 0.898)은 "end-to-end performance of the automated agents without human correction"이라 명시(Baseline Comparison 절)
- Table 2(전체 관계 수 2442/115/37/57/16)는 "Following the manual correction of formalization errors" 이후의 curated dataset 기준(Consistency Analysis 절)
- Benchmark(Table 1, 226쌍)는 파이프라인 출력을 임상 전문가가 교정해 만든 것. 전문가 수·일치도는 보고 없음(Dataset Construction 절)
- 코드·데이터 링크: https://github.com/Shiyaoa/GuidelineCoordination (초록 아래)

## 2. 공개 예측·정답 쌍 여부

- [실제 실행해 확인한 결과] 저장소 파일은 README, .gitignore, rules_gold.json, pipeline/*.py 뿐이다. 파이프라인 원출력(교정 전 565규칙), 226쌍 benchmark 라벨, LLM 기준선 응답, predicates.json/terms.json/meds.json(`standard/`, `gen/`)이 없다.
- 따라서 "시스템 출력 vs 정답" 오류는 직접 추출할 수 없다. 아래 사례는 세 종류로 나눈다.
  - PAPER_REPORTED(P01~P05): 논문이 서술한 범주·예시. 개별 사례 재현 불가
  - GOLD_OBSERVED(G01~G13), GOLD_SAMPLE60(S##): 공개된 정답 파일 자체에서 관찰한 문제. 시스템 출력이 아니라 정답 라벨 문제(원인 E) 후보
  - 가설 사례는 따로 만들지 않았다. 정답에서 관찰한 패턴이 파이프라인 출력에도 있었을 것이라는 추정은 [연구 가설]로 표시
- [아직 검증하지 못한 사항] rules_gold.json이 "수동 교정 후" 규칙 집합인지 여부. 파일명(gold)과 Table 2 설명으로 보아 교정본으로 추정되나, 저장소에 설명이 없다(README "待补充").

## 3. rules_gold.json 정답 품질 감사

코드: `code/gold_audit.py`, `code/gold_audit_extra.py`, `code/gold_audit_purpose.py`, `code/build_cases.py`

### 3.1 기본 분포 [실제 실행해 확인한 결과]

| 항목 | 값 |
|---|---|
| 규칙 수 / 고유 id | 563 / 563 |
| permission | recommend 147, allow 114, avoid 85, contraindicate 53, caution 35, consider 25, continue 22, reduce_dose 21, stop 21, require 18, start_low_dose 9, increase_dose 6, max_dose_limit 6, titrate 1 |
| 고유 술어 | 394개, 그중 1회만 쓰인 술어 237개(60.2%) |
| OR 포함 condition | 124건, NOT 포함 12건, 단일 술어 145건 |
| AND·OR 혼합인데 괄호 없음 | 0건 |
| 술어 종류(이름 기준) | 자유형식 140, 숫자 포함(기타) 90, has_ 82, on_ 41, 수치 임계값 이산화(`egfr_lt_30` 형) 31, 수치 구간(`egfr_30_to_45` 형) 8 |
| 이름에 논리어 포함 술어(`_or_`, `_with_`, `not_` 등) | 28개(예: `ckd_with_egfr_lt_15_or_dialysis`, `has_ascvd_or_high_risk`) |
| 출처 문자열 | 14종(빈 문자열 3건, 같은 공식 문서로 보이는 "(2023版)" 35건과 "(2023)" 29건이 분리) — 논문은 12개 지침 |
| recommendation_grade / evidence_level가 "None" | 437(77.6%) / 426(75.7%) |
| 빈 subjects | 6건, subjects가 문자열 'nan' 1건, 빈 label 20건, requirements에 `pred.*` 혼입 15건 |

### 3.2 술어 이름 일관성 [실제 실행해 확인한 결과]

- 이름 유사 쌍 102개(`gold_audit_similar_predicates.csv`). 접두어만 다른 동일 핵심어 15쌍: `ckd_stage_3a`(23) vs `has_ckd_stage_3a`(2), `has_hf` vs `history_hf`, `has_t1dm` vs `t1dm`, `pregnant` vs `is_pregnant`, `is_elderly` vs `elderly` 등
- 오타: `has_servere_liver_impairment`(1건)
- 간기능 저하 개념에 23개 이름(`gold_audit_synonym_groups.csv`), 혈당 조절 불충분 개념에 22개 이름, CKD/신기능 저하에 `has_ckd`(75)·`has_renal_insufficiency`(36)·`has_renal_impairment`(4)·`renal_impairment`(1)·`ckd_adult`(8)
- 연산자만 다른 쌍: `creatinine_max_gt_309` vs `creatinine_max_ge_309`, `potassium_max_gt_5_5` vs `ge_5_5`, `egfr_lt_60` vs `egfr_le_60`. 원문 대조 결과 각각 원문의 ">"·"达(이르다)"·"≤"를 따른 것이라 비교 연산자 오류는 아님
- 구간 경계 표기 불일치: `egfr_45_to_59`(2) vs `egfr_45_to_60`(8)
- [아직 검증하지 못한 사항] 술어 의미는 미공개 predicates.json의 `formal_definition`(analyzer.py L138-L154, L657-L663)이 정한다. 이름이 달라도 정의가 같은 변수를 쓰면 Z3에서는 동치가 될 수 있다. 정의 파일 없이는 "같은 개념 다른 이름"이 실제로 관계 누락을 만드는지 판정할 수 없다.

### 3.3 약물 ID 일관성과 평가 코드 [실제 실행해 확인한 결과]

- 같은 계열에 서로 다른 ID: `med.class.sglt2`(154) vs `med.class.sglt2i`(10), `med.class.glp1`(19) vs `med.class.glp1ra`(4), `med.class.bb`(4) vs `med.class.beta_blocker`(2), `med.insulin`(4) vs `med.class.insulin`(8)
- [원문으로 확인한 사실] `pipeline/analyzer.py` L417-L439는 subjects를 문자열 집합 교집합으로만 비교한다. 계열(class)과 개별 약물의 포함 관계는 없다.
- 영향(어휘 수준, 조건 무시): 전체 158,203 규칙 쌍 중 subjects가 정확히 겹치는 쌍 16,598, 계열을 한쪽만 확장하면 41,427(2.50배). action이 상충하는 쌍은 6,875 → 17,627. 즉 원본 코드는 `med.class.sglt2` 금지와 `med.dapagliflozin` 권고 같은 쌍을 처음부터 비교하지 않는다. [연구 가설] 이 때문에 Local/Implication Conflict 수와 재현율이 계열 표현에 따라 달라질 수 있다.
- id 약물명과 subject 불일치 5건: `rule.linagliptin_*` 4건의 subject가 `med.ruigeliptin`(瑞格列汀), `rule.vildagliptin_renal_insufficiency_all_stages`의 subject가 `med.kaogelieting`(考格列汀). subject는 원문과 맞지만 병음 기반 비표준 ID

### 3.4 수치·시간·부정·예외 표현

- 수치 [실제 실행해 확인한 결과]: eGFR·혈칼륨·UACR 등은 모두 술어 이름으로 이산화(`egfr_lt_30`, `egfr_30_to_45`, `potassium_max_gt_5_5`). 원문에 있는 임계값이 condition에 없는 규칙 18건(휴리스틱). 원문 대조 결과 대부분은 한 문장을 여러 규칙으로 나눈 결과(예: 아카보스 "4期患者中eGFR<25者禁用"은 별도 규칙 `rule.acarbose_ckd_4_egfr_lt_25_contraindicate`로 존재)였고, 단위 오류는 관찰되지 않음
- 시간 [실제 실행해 확인한 결과]: 원문에 시간·시점 표현(术前·期间·起始后 2周 등)이 있는데 condition에 시간 관련 술어가 없는 규칙 41건(휴리스틱, 거짓 양성 포함). [원문으로 확인한 사실] `z3env.py` L49-L52는 Duration·Assess 연산자를 "暂不支持"(아직 지원 안 함)로 두어 시간 조건은 Z3 비교 대상이 아니다
- 개시/지속 구분: "不推荐起始…但正在使用…可继续" 형 문장이 개시 금지 규칙과 지속 허용 규칙으로 나뉠 때, 개시 금지 쪽에 `NOT pred.on_X`가 없는 사례 관찰(G01, G02, S43)
- 부정·예외: NOT 사용 12건. 원문에 除外·除非·但 등이 있는데 NOT이 없는 규칙 22건(휴리스틱). "除非有禁忌证或不能耐受" 같은 암묵적 예외는 대부분 미표현(S09)

### 3.5 permission과 원문 양상어 [실제 실행해 확인한 결과]

- 원문 "禁用/禁忌"인데 permission avoid: 21건. 이 중 다수는 원문 자체가 "不建议使用或禁用"(권하지 않거나 금지)라는 이중 표현 → 원문 모호(F)
- 원문 "不建议/不推荐"만 있는데 contraindicate: 2건
- 같은 condition·subjects에 다른 permission 9쌍(`gold_audit_duplicates.csv`). 예: `rule.t1dm_avoid_sglt2i`(avoid) vs `rule.t1dm_contraindicate_sglt2`(contraindicate), 같은 출처의 서로 다른 문장
- recommendation_grade "III"인데 permission allow·continue·recommend 4건(G13). 해당 지침의 III 정의는 확인 필요

### 3.6 중복 [실제 실행해 확인한 결과]

- condition·subjects·permission 완전 동일 4그룹(12규칙). 예: `has_t2dm AND has_ckd → recommend med.class.sglt2` 5건(5개 출처). 출처가 다르면 정당한 Complete Redundancy
- 같은 출처·같은 quote 안의 완전 동일: `rule.dapagliflozin_egfr_lt_25_continue`와 `rule.dapagliflozin_egfr_lt_25_avoid_initiation`. 후자는 id·label이 "개시 금지"인데 내용은 continue 규칙 복제(G02)
- 같은 quote에서 여러 규칙 70그룹. 문장 분할 자체는 정상

### 3.7 condition 문자열이 같은데 action이 상충하는 쌍 [실제 실행해 확인한 결과]

- analyzer.py의 permission 범주(L371-L374)를 그대로 써서 계산. 문자열이 같은 condition(AND 순서 정규화)에 subjects가 겹치고 action이 상충하는 쌍: 1쌍
- 그 1쌍이 `rule.ckd_egfr_lt_15_or_dialysis_continue_sglt2`(continue) vs `rule.ckd_egfr_lt_15_or_dialysis_stop_sglt2`(stop)이며, 같은 지침의 같은 문장에서 나왔다(G01)
- 논문 Table 2의 Intrinsic Conflict 대표 예시 "If eGFR or Dialysis Continue SGLT2i / If eGFR or Dialysis Stop SGLT2i"와 내용이 같다. 논문은 이를 "Evidence Contradiction … likely reflecting differences in guideline versions or evidence interpretation"이라 설명하지만, 정답 파일상 두 규칙의 출처는 한 문장 "对于eGFR<15…或透析的CKD患者，应停用SGLT2i，但若已使用SGLT2i可继续维持使用至透析或肾移植"이다. [연구 가설] 지침 간 근거 충돌이 아니라 한 문장 안의 예외(신규 사용자 중지 vs 기존 사용자 지속)를 형식화하며 생긴 충돌일 가능성이 높다. 원문 자체도 "应停用"과 "可继续"가 한 문장에 있어 모호하다(F).
- Intrinsic Conflict 37쌍 전체는 Z3 의미 동치 기준이라 문자열 비교로는 확인할 수 없다(predicates.json 필요). [아직 검증하지 못한 사항]

### 3.8 원문 대조 무작위 표본(60건)

- 사전 설정: 무작위 60건, `random.Random(20261118).sample(range(563), 60)`, 정답 순서 인덱스 기준. 표본 결과를 본 뒤 표본을 바꾸지 않음
- 판독자: SUBAGENT C 1명(임상 전문가 아님). 판정 기준: quote에 있는 조건·대상·강도가 condition·subjects·permission에 반영됐는지. 같은 quote의 다른 규칙이 보완하면 OK
- 결과 [실제 실행해 확인한 결과(판독)] / 해석은 [연구 가설]

| 판정 | 건수 | 비율(분모 60) | Wilson 95% CI |
|---|---|---|---|
| OK | 36 | 60.0% | — |
| ISSUE(실질 문제) | 14 | 23.3% | 14.4%–35.4% |
| MINOR(경미·형식) | 8 | 13.3% | — |
| AMBIGUOUS(원문 모호) | 2 | 3.3% | — |
| ISSUE+MINOR+AMBIGUOUS | 24 | 40.0% | 28.6%–52.6% |

- 주의: 이 23.3%를 논문의 오류율 19.9%와 직접 비교하면 안 된다. 기준(논문: 파이프라인 출력 vs 원문, 엄격 일치 / 여기: 정답 파일 vs 원문, 단일 비전문가), 판독자, 대상이 모두 다르다.

## 4. 오류 유형 분류(실제 관찰된 것만)

### 4.1 표본 60건 기준 유형별 개수(한 규칙에 여러 유형 가능, 중복 분류 13건)

| 유형 | 건수 | 60건 대비 | 문제 24건 대비 |
|---|---|---|---|
| T02 과대 적용 | 7 | 11.7% | 29.2% |
| T01 필수 조건 누락 | 6 | 10.0% | 25.0% |
| T07 용어 연결 오류 | 6 | 10.0% | 25.0% |
| T13 지침에 없는 조건 추가 | 5 | 8.3% | 20.8% |
| T17 논리 표현 불완전 | 5 | 8.3% | 20.8% |
| T03 과소 적용 | 4 | 6.7% | 16.7% |
| T08 시간 조건 누락 | 3 | 5.0% | 12.5% |
| T06 예외 누락 | 1 | 1.7% | 4.2% |
| T12 권고/근거 혼동 | 1 | 1.7% | 4.2% |
| T04 AND/OR, T05 부정, T09 비교 연산자, T10 단위, T11 환자 조건 혼합, T14 충돌 유형 오분류, T15 중복 vs 충돌, T16 근거 부족을 충돌로, T18 의학 지식 부족 | 0 | 0% | 0% |

표본 밖에서 관찰한 유형: T14 충돌 유형 오분류(G01), T15 중복 vs 충돌 혼동(G02, G08), T12(G02, G08, G11, G13). T04·T05·T09·T10·T11·T16·T18은 관찰되지 않음(T09 후보 3쌍은 원문 대조 결과 정상).

### 4.2 원인(A~G) — 표본의 문제 24건, 주 원인 1개 기준

| 원인 | 건수 | 비율(분모 24) | 대표 |
|---|---|---|---|
| B 논리 표현 부족 | 10 | 41.7% | 병용(FDC·"联合")을 subjects 집합으로 표현(S05, S07, S40), monitor 어휘 없음(S27), "评估后使用" 표현 불가(S38) |
| C 변환 과정 | 9 | 37.5% | 맥락 누락(S12, S31, S60), on_<약> 추가(S04, S16), ID 변형(S34) |
| F 원문 모호 | 3 | 12.5% | "不建议使用或禁用"(S33), "对于…使用X"(S18, S26) |
| D 의학지식 부족 | 1 | 4.2% | GDMT 범위(S01) |
| UNKNOWN | 1 | 4.2% | 지침 절 맥락 확인 필요(S32) |
| A 모델 이해 / E 정답 라벨 / G 평가 프로그램 | 0 | 0% | 표본 판정은 정답 자체가 대상이라 A는 주 원인에서 제외 |

표본 밖 체계적 관찰(G01~G13, 13건) 주 원인: E 정답 라벨 문제 6건(G02, G03, G10, G11, G12, G13), C 변환 과정 3건(G05, G06, G07), F 원문 모호 2건(G01, G08), G 평가 프로그램 1건(G04), B 논리 표현 부족 1건(G09). 전체 42건 중 중복 분류(유형 2개 이상 또는 보조 원인 있음) 32건.

## 5. 핵심 사례

전체 42건은 `error_cases.csv` (열: 사례 ID, 원본 참조, 정답, 시스템 출력, 잘못된 부분, 오류 유형, 처리 단계, 근거 위치, 재현 여부, 기존 기술로 수정 가능성, 전문가 검토 필요성, 원인, 중복 분류).

| ID | 참조 | 잘못된 부분 | 유형 | 원인 | 재현 | 전문가 |
|---|---|---|---|---|---|---|
| G01 | rule.ckd_egfr_lt_15_or_dialysis_continue_sglt2 / _stop_sglt2 | 한 문장의 예외 구조가 같은 집단 continue/stop으로 → 논문 Table 2 Intrinsic 예시와 동일, 논문은 지침 간 근거 차이로 해석 | T06;T08;T14 | F(+C) | Y | Y |
| G02 | rule.dapagliflozin_egfr_lt_25_avoid_initiation | id·label "개시 금지", 내용은 continue 복제 → 개시 금지 규칙 소실, 거짓 완전 중복 | T12;T15;T08 | E(+C) | Y | N |
| G04 | med.class.sglt2 vs med.class.sglt2i 외; analyzer.py L417-L439 | subjects 정확일치 비교 → 계열·변형 ID 간 관계 미탐지(겹침 쌍 2.50배 차이) | T07;T03 | G(+C) | Y | N |
| G06 | rule.ckd_4_5_gliclazide_avoid 외 신기능 관련 16건 | 원문에 없는 `pred.on_<같은 약>` 추가, 같은 출처의 다른 약 규칙과 표현 불일치 | T13;T03 | C(+F) | Y | 부분 |
| G07 | gold_audit_glycemic_purpose.csv 34건 | "进行血糖控制"(혈당 목적) 한정어 누락. SGLT2 계열 제한 규칙 9건 | T01;T02 | C(+A) | Y | Y |
| S05 | rule.contrast_imaging_avoid_sglt2_metformin_fdc | "二甲双胍或其与SGLT2i的FDC" → [sglt2, metformin], SGLT2i 단독에도 적용. 같은 quote의 S25는 [metformin]만 | T07;T02;T08 | B(+C) | Y | N |
| S12 | rule.t2dm_renal_egfr_30_to_45_dapagliflozin_avoid | "以改善血糖控制" 누락 → 신장 보호 목적 사용까지 avoid | T01;T02 | C(+A) | Y | Y |
| S31 | rule.recommend_add_finerenone_to_sglt2i | "心肾风险仍需进一步管理" 누락 → 모든 SGLT2i 사용자에게 recommend | T01;T02 | C(+A) | Y | Y |
| S38 | rule.t2dm_ckd_other_meds_assess_hypoglycemia_risk | "使用SGLT2i前建议评估低血糖风险"를 SGLT2i recommend로, "特别是"를 필수 조건으로 | T12;T13;T03 | B(+C) | Y | Y |
| S43 | rule.hf_ckd_egfr_lt_20_empagliflozin_not_recommended | "不建议开始使用"(개시만) → avoid, 개시/지속 구분 소실 | T08;T02 | B(+C) | Y | N |
| S60 | rule.t2dm_ckd_intolerant_acei_arb_use_sglt2 | id에 t2dm_ckd가 있으나 condition에 없음 → 논문 Contextual Loss와 같은 형태 | T01;T02 | C(+A) | Y | N |

추가: id·label에 있는 질환 맥락(t2dm/ckd/hf 등)이 condition에 없는 규칙 17건(`gold_audit_rule_checks.csv`, check=id_context_absent_in_condition). 원문에도 맥락이 없는 경우(절 제목에만 있음)가 섞여 있어 [연구 가설] 수준의 Contextual Loss 대리 지표다.

## 6. 해석과 한계

- [연구 가설] 논문이 가장 흔하다고 한 Contextual Loss(56.7%)와 같은 형태가 "교정 후 정답"으로 추정되는 파일에도 남아 있다(S12, S31, S60, G07). 정답에 남은 맥락 누락은 Table 2의 Local Conflict 2,442쌍 같은 수치를 키울 수 있다(조건이 넓어지면 교집합이 늘어남). 크기는 predicates.json 없이 계산 불가
- [연구 가설] 병용 요법을 subjects 집합으로 쓰는 표현(models.py "联合用药包含多个ID")과 analyzer의 교집합 비교가 만나면, 병용 금지 규칙이 단일 약 규칙과 충돌로 잡힌다(S05, S07, S40). 논리 표현 부족(B)이 평가 결과로 이어지는 경로
- [연구 가설] 논문 Table 2 Intrinsic Conflict 대표 예시는 지침 간 근거 충돌이 아니라 형식화 산물일 가능성(G01). 37쌍 중 비슷한 경우가 몇 개인지는 확인 필요
- 한계: 표본 판독자 1명·비전문가, 임상 판단(S01 GDMT 범위, S32 대상 집단) 확인 필요. 휴리스틱 플래그(시간 41건, 예외 22건, 임계값 18건)에는 거짓 양성이 있다. 정답을 수정하지 않았고 모든 사례는 이의 후보다

## 7. 산출물

| 파일 | 내용 |
|---|---|
| `error_cases.csv` | 사례 42건(P 5, G 13, S 24) |
| `error_type_counts_sample60.csv`, `sample60_stats.json` | 유형·원인 집계, 판정 비율, Wilson CI |
| `gold_audit_sample60_raw.csv`, `gold_audit_sample60_annotated.csv` | seed 20261118 무작위 60건과 판정 |
| `gold_audit_rules.csv` | 563규칙 전체 + 휴리스틱 플래그 |
| `gold_audit_predicates.csv`, `gold_audit_similar_predicates.csv`, `gold_audit_synonym_groups.csv` | 술어 인벤토리·유사 쌍·동의어 후보 |
| `gold_audit_meds.csv`, `gold_audit_med_id_variants.csv` | 약물 ID 분포·변형 |
| `gold_audit_duplicates.csv`, `gold_audit_lexical_intrinsic_conflicts.csv` | 중복·문자열 동일 condition 상충 쌍 |
| `gold_audit_rule_checks.csv` | 빈 필드·nan·id-permission 불일치·on_<약> 패턴·맥락 누락 대리 지표 |
| `gold_audit_glycemic_purpose.csv` | 혈당 목적 한정어 검사 |
| `gold_audit_grade_by_permission.csv`, `gold_audit_sources_in_gold.csv` | 등급×permission, 출처 문자열 |
| `gold_audit_summary.json`, `gold_audit_extra_summary.json` | 요약 수치 |
| `sources.csv`, `sources_raw/` | 출처 목록, arXiv HTML 사본(SHA256 기록) |
| `code/*.py`, `logs/*.log` | 감사 코드와 실행 로그(run1~ 실패·수정 이력 포함) |

코드 수정 이력(검증 스크립트 자체 점검): `gold_audit.py` 시간 조건 정규식이 "pred."의 "pre"에 걸려 시간 플래그가 0건이던 버그 수정(run3·run4), `gold_audit_extra.py` 계열 확장이 개별약끼리 class를 거쳐 거짓으로 겹치던 버그 수정(run2). 최종 수치는 수정 후 값이다.
