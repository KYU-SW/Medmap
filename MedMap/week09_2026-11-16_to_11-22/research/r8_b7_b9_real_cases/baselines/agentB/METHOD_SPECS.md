# METHOD_SPECS — 실제 사례 비교 실험용 방법 A~D 명세

- 작성: 2026-11-21, Agent B (강력한 기존 방법 담당)
- 실행 주체: 메인 에이전트. 이 문서는 실행하지 않은 명세다.
- 원칙
  - 원본 코드를 돌리지 못한 방법은 **"원본 미재현"**, 우리가 짠 것은 **"~식 독자 구현"**으로만 부른다.
  - B와 D는 **기존 방법의 결합**이다. 새 알고리즘으로 표현하지 않는다.
  - 모든 방법은 같은 사례 입력 JSON 하나를 받는다(1절). 어떤 방법도 다른 방법보다 많은 정보를 받지 않는다. 방법이 쓰지 못하는 필드는 그 방법이 "무시"하는 것으로 기록한다.

---

## 0. 판정 요약

| 슬롯 | 이름 | 원본/독자 | 실행 가능성 | 재사용 코드 |
|---|---|---|---|---|
| A | **MitPlan식 독자 구현 (원본 미재현)** | 독자 구현. MitPlan 원본 코드 비공개 | 가능(로컬, 수 ms) | `reuse/.../weak.py::run_A` |
| A′(선택) | ATLAS 공개 코드 동결 추론 | **원본 코드** 존재, LICENSE 없음 | 조건부: 클론·실행은 사용자 승인 후, 재배포 금지, 입력 스키마가 달라 변환 필요 | 없음(외부) |
| B | **R5 결합 정식화**(결합 상태공간 + LP, 단일 MILP 대조) + 기존 질문 우선순위 래퍼 | 이전 R5 코드(기존 결합 계산) | 가능 | `strong.py::run_B`, `b_milp.py::run_Bmilp`, `gate0_C_mdq` |
| C | **기존 개별 기능 순차 파이프라인**(규칙 엔진 → 선호 가중합 → 근거 표지) | 독자 구현(각 단계는 공개 방법의 일반 기능) | 가능(새 래퍼 필요) | `weak.py` 보조 함수, `strong.py::_in_hull_lp` |
| C′(대조) | R5 B′ 모듈 정확 결합 | 이전 R5 코드 | 가능 | `strong.py::run_Bp` |
| D | **MitPlan식 정당한 확장 독자 구현**(꼭짓점 재계획 + 시나리오 열거 + 근거 표지 보류 + 변수 고정 질문) | 독자 구현 | 가능(새 래퍼 필요) | `weak.py::run_A` 내부 로직 + `strong.py` 보조 함수 |

---

## 1. 공통 사례 입력 (case schema v0)

실제 사례 1건 = JSON 1개. R5 D 스키마(REUSE_MAP 3절)의 상위집합이다. `→D` 열은 R5 D 인스턴스로 내리는 규칙이다.

| 블록 | 필드 | 예(형식 예시일 뿐 의학 주장 아님) | →D 변환 |
|---|---|---|---|
| `patient.diseases` | 확정 진단 목록 + 출처·시점 | `[{"code":"T2DM","status":"confirmed","source":"problem_list","asof":"2026-10-01"}]` | 지침 `app`의 확정 리터럴로 접음 |
| `patient.labs` | 검사값, 단위, 측정·인지 시점, 출처 | `{"eGFR":{"value":28,"unit":"mL/min/1.73m2","measured":"2026-09-30","source":"lab"}}` | 임계값 이진 변수로 변환(예 `c_eGFR_lt30`), 값이 있으면 T/F |
| `patient.unknown_vars` | 미확인·상충 변수, 이진화 임계값, 확인 비용 | `[{"var":"K_gt_5_0","status":"U","ask_cost":1,"how":"혈청 칼륨 재측정"}, {"var":"HFrEF","status":"C","records":["T@echo2024","F@note2026"]}]` | `obs`=U. 상충 `C`는 D에 없으므로 U로 내리고 `notes`에 기록(C 정식화는 C 그대로) |
| `patient.deps` | 변수 간 논리 의존 | `[["c_eGFR_lt15","c_eGFR_lt30"]]` | `deps` |
| `guidelines[]` | 지침 id, 출처(문서·절·판·이용 허가), 적용 조건, 1차 권고·대체 선택지, 권고 강도 | `{"id":"G_HF","src":{"doc":"...","section":"...","license":"..."},"app":[["HFrEF",1]],"options":["A_mra","A_none"],"strength":"..."}` | `guidelines[].app/options`. 강도는 D에서 미사용(기록만) |
| `actions[]` | 행동 id, 이름, 부담 속성, 효과 표현, 근거 | `{"id":"A_mra","burden":{"pills":1,"visits":1,"monitoring":"K 측정"},"effect":{"point":2,"interval":[1,3]},"evidence":{...}}` | `effect`=point(D는 구간 미지원), `pills`/`visits` |
| `actions[].evidence` | 시험 참가 조건 상자, 공변량 정의, 공유 변수, B10 태그 | `{"trial":"FIDELIO-DKD","covariates":["age","K"],"box":{"K":[null,4.8]},"shared_var":"K_gt_5_0","E1":"MET|NOT_MET|UNK","E2":"IN|OUT|PUBLIC_UNRESOLVED","E3":"SUPPORTED|UNASSESSED","directnessMatch":"low|moderate|high|exact"}` 또는 `null`(근거 항목 없음) | 상자 꼭짓점 → `trial` 점 목록, `shared_var` → `patient_cov.x1_var`(1개만 가능, REUSE_MAP 8절) |
| `interactions[]` | 규칙 종류, 대상 행동, 조건, 출처, 지식 확실성 | `{"type":"conflict","a":"A_mra","b":"A_acei","cond":[["K_gt_5_0",1]],"src":"label §5","certainty":"known"}`; 종류 = conflict / conditional_conflict / compatible / duplicate / complementary / unknown_interaction | conflict(조건 포함)·compatible만 D로. duplicate·complementary·unknown_interaction은 C 정식화 입력으로 |
| `preferences` | 기준 목록, 부분 순서, 상·하한, 원문 진술 | `{"criteria":["benefit","pill_burden","visit_burden"],"order":[["visit_burden","pill_burden"]],"bounds":{"benefit":[0.2,0.6]},"statement":"걷기 유지가 최우선"}` | D는 중심±r 상자만 받음 → 부분 순서를 감싸는 최소 상자로 근사하면 **과보수**. 근사 여부를 출력에 기록. 정확 처리는 C 정식화 `W_matrices` |
| `meta` | 사례 id, 작성자, 정답 출처, 합성/실제 표지 | | |

**필수 기록**: 각 필드가 어느 방법에서 쓰였고 어느 방법에서 무시됐는지(`used_fields` 표).

**`clinical-cases/CASE_SCHEMA.md`(다른 에이전트 작성, 25항목)와의 대응** — 사례 원본은 그 스키마로 받고 아래처럼 내려 쓴다. 18~22번(정답 쪽 항목)은 방법 입력에 넣지 않는다(정답 누출 방지).

| CASE_SCHEMA 키 | case schema v0 |
|---|---|
| 5 comorbidities, 6 known_clinical | `patient.diseases`, `patient.labs` |
| 7 unknown_clinical | `patient.unknown_vars` |
| 8 applicable_guidelines, 9 conditional_recommendations | `guidelines[]` (`app`, `options`) |
| 10 potential_conflicts, 11 complementary_recommendations | `interactions[]` (conflict / conditional_conflict / duplicate / complementary) |
| 12 patient_goals, 13 confirmed_preferences, 14 unconfirmed_preferences | `preferences` (`order`, `bounds`, `statement`; 미확인 선호는 범위로) |
| 15 treatment_burden | `actions[].burden` |
| 16 applicable_evidence, 17 evidence_scope_limits | `actions[].evidence` |
| 18 decidable_now ~ 22 confirm_priority | **입력 아님** — 채점용 정답 |

## 2. 공통 출력

| 출력 | 형식 | 비고 |
|---|---|---|
| `final` | R5 D 10범주(REUSE_MAP 4절) | 확정 = CONVERGED / CONFIRMED_PLAN / CONDITIONAL_PLAN 중 상태별 확정 |
| `per_state` | 미확인 변수 값별 (kind, payload) | 상태 개념 없는 방법은 모든 상태에 같은 값 |
| `decisions[]` | 행동별 `CONFIRM` / `HOLD` / `EXCLUDE` + 이유 | |
| `hold_reason` | `P`(임상 정보로 닫힘) / `Q`(선호로 닫힘) / `K`(지식 부족, 질문으로 안 닫힘) / 조합 | C 정식화 `categorize` 어휘 |
| `interaction_class[]` | 규칙별 REAL / CONDITIONAL / NONE / DUPLICATE / COMPLEMENTARY / UNKNOWN_KNOWLEDGE / APPLICABILITY_UNCONFIRMED | `app`=CONDITIONAL_APPLY인 지침이 걸린 규칙은 APPLICABILITY_UNCONFIRMED 병기 |
| `evidence_status[]` | 행동×상태별 OK / OUT / NOENTRY (+ B10 태그 전달) | OUT ≠ 금기(F4) |
| `questions[]` | 순위, 변수, 비용, 닫는 보류 수, 방법(`fix_and_rerun`/`hitting_set`/`ec2`/`voi`/`none`) | 방법이 질문을 내지 못하면 빈 목록 + `not_supported` |
| `forbidden_flags` | F1~F5 자체 점검(SPEC 6절) | 채점은 메인이 정답 대비 |
| `ewas`, `fsew` | 계획 목록 | 지원 방법만 |

---

## 3. 방법 A — MitPlan식 독자 구현 (원본 미재현)

- **근거**: MitPlan 2.0 저자 기술 보고서 [원문] p.3–4(가중합, 점 선호=비용), p.9(실행 1회 계획 1개), p.21 Fig 15(`patientValue` 점 값).
- **원본 상태**: 공식 코드 비공개(R5 GitHub 검색, 보고서는 PDDL 조각만). OPTIC 계획기 자체 사용·라이선스는 확인 필요. 따라서 **원본 실행 아님**.
- **구현**: `weak.py::run_A` 그대로.
  1. 폐쇄 세계: 미확인 U → 0(거짓). PDDL 초기 상태의 일반 가정이며 MitPlan 원문 근거는 아님(원문은 미확인 처리 언급 없음).
  2. 1차 권고 결합에서 상호작용 탐지.
  3. 수정 연산자 = 지침별 대체 선택지 교체(모든 조합 탐색).
  4. 점 선호 W center 가중 비용 최소 계획 1개.
  5. 근거: 효과가 있으면 사용, `trial=null`이면 효과 0.
- **입력에서 쓰는 것**: guidelines, actions(effect/pills/visits), interactions(conflict), W center. **무시**: unknown 상태(→0), deps, 선호 부분 순서·범위, evidence, B10 태그.
- **출력**: `final` ∈ {CONVERGED, CONFIRMED_PLAN, REAL_CONFLICT}, 계획 1개, `questions=[]`(not_supported), hold 없음.
- **표기 의무**: 결과표에 "MitPlan식 독자 구현(원본 미재현)". A의 실패를 MitPlan 실패로 일반화하지 않는다.
- **공정성 점검**: R5에서 A는 E1(B7만)에서 정답 1.0이었다. 실제 사례에서도 B7만 있는 사례에서 A가 맞는지 먼저 확인해 구현이 약하지 않은지 본다.

### A′ (선택) — ATLAS 공개 코드 동결 추론

- 코드: `github.com/HKUSTGZ-ML4Health-Lab/ATLAS`(HEAD 160dd376). GitHub API license=None → **재배포 금지**, `upstream/`에 받지 않았다.
- `CODE_APPENDIX/02_FROZEN_INFERENCE/scripts/run_final.py`는 `frozen_rules.json` + `UnifiedOrchestratorAgent`를 부르는 순수 Python으로 보인다(일부 파일 import 확인, 전체 미확인). LLM 기준선 러너는 별도 폴더.
- 입력 스키마가 ATLAS 고유(조건·약·노인 위험 요소)다. 선호·부담·근거 적용 범위 필드가 없다.
- 쓰임: **정보 부족 보류(e)와 질문 우선순위(f)의 원본 비교 대상**. B7+B9 전체 비교 대상은 아님.
- 실행 전 사용자 승인 필요(외부 코드 실행, 라이선스 불명). 승인 없으면 "원본 실행 보류"로 표시.

## 4. 방법 B — R5 결합 정식화 (기존 결합 계산)

- **근거**: R5 D Baseline B·B_milp. 합성 1,261건 동결 정답과 full 일치 1.0, 잘못된 확정 0 [코드][합성]. 이번 복사본 손 사례 11/11 일치 [코드].
- **구성**(모두 기존 기법): 상태 열거(시나리오) × W polytope LP(필연/가능 최적, ROR·minimax regret 계열) × 볼록 껍질 LP 근거 지지(Trial Score·positivity 계열) × ∃w∀s 결합 LP 또는 MILP+CEGAR.
- **실행**: `run_B(inst_D)` 주 결과, `run_Bmilp(inst_D)` 로 `ewas` 대조. 사례가 C 정식화 필드(중복, 미확인 상호작용, 부담 상한, 부분 순서, 출처 상충)를 쓰면 `r5_C_formalization/integrated_model.py` 의 `categorize()` 를 병행하고, 두 결과를 따로 보고한다(통합 스키마 없음).
- **질문 우선순위 래퍼 B-Q** (기존 기법: 결정 관련 변수 검사 = ATLAS·Gate0 C의 "결정을 바꿀 때만 묻기", 새 알고리즘 아님):
  1. `final`이 보류 계열(INFO_HOLD, CONDITIONAL_*, PREFERENCE_DEPENDENT)이면 미확인 변수 v마다 `obs[v]`를 T, F로 고정한 사본 2개에 `run_B`.
  2. 두 결과 중 하나라도 보류가 풀리거나 `final`/`per_state`가 바뀌면 v는 결정 관련.
  3. 순위: (i) 두 답 모두에서 보류가 닫히는 변수 우선 (ii) 닫히는 상태 수 (iii) `ask_cost` 낮은 순. 동률이면 변수 이름 순(결정적).
  4. 변수 여러 개를 함께 물어야만 닫히는 경우: `gate0_C_mdq/methods.py::hitting_set_milp` 로 최소 비용 집합을 별도 보고(GridModel 어댑터 필요; 어댑터 미구현이면 "다변수 질문 미지원"으로 표시).
  5. `hold_reason`: v 고정으로 닫히면 P. W를 점으로 줄여야 닫히면 Q(C 정식화 `judge(G=("Q",))`). 어떤 고정에도 EVIDENCE_GAP/KNOWLEDGE_GAP이 남으면 K → 질문 목록에 넣지 않는다.
- **입력에서 쓰는 것**: 1절 전 필드(D 변환 + C 정식화 병행). **알려진 제약**: REUSE_MAP 8절(공유 변수 1개, 2차원 공변량, 기준 3개, 점 효과).
- **출력**: 2절 전체. `questions` 방법 = `fix_and_rerun`(+`hitting_set` 선택).

## 5. 방법 C — 기존 개별 기능 순차 파이프라인 (독자 구현)

각 단계는 공개된 개별 기능의 일반 형태다. 단계 사이에 상태·선호 범위를 넘기지 않는 것이 이 방법의 정의다.

1. **지침 규칙 엔진**(GoCom·Xie&Du식 3값 규칙 평가): 각 지침 `app`, 각 규칙 `cond`를 Kleene 3값으로 평가. 결과 T/F/UNKNOWN.
   - UNKNOWN 적용 조건 지침은 "적용 조건 미확인"으로 표시하되 **1차 권고는 포함**(GoCom처럼 실행을 멈추지 않음; 멈춤 변형은 C-stop으로 따로 보고 가능).
   - 규칙 T → 그 조합 제외. 규칙 UNKNOWN → 제외하지 않고 경고 표시(Xie&Du 코드의 local_conflict처럼 경고만).
2. **선호 가중합**(MitPlan·Fdez-Olivares식 점 가중치): W center로 허용 조합 효용 최대 1개 선택. 부담은 pills/visits 기준으로 포함.
3. **근거 표지**(Trial Score·FHIR directnessMatch식 후처리): 선택된 계획의 각 행동에 대해, 관측된 값만으로 `_in_hull_lp`(미확인 공변량은 관측값 없음 → "판정 불가" 표지). 표지만 붙이고 계획을 바꾸지 않는다.
4. **출력 규칙**: 경고·판정 불가 표지가 하나도 없으면 확정(CONVERGED/CONFIRMED_PLAN). 1단계 UNKNOWN 경고가 있으면 INFO_HOLD, 3단계 OUT이면 EVIDENCE_SCOPE_INSUFFICIENT, NOENTRY면 KNOWLEDGE_GAP. 우선순위: 규칙 실제 충돌로 허용 조합 없음 > NOENTRY > OUT > UNKNOWN 경고.
5. **질문**: 1단계에서 UNKNOWN을 만든 변수를 등장 순서대로 나열(우선순위 계산 없음, `method="listing"`).
- **재사용**: `weak.py::_sat`, `_realized`; `strong.py::_in_hull_lp`, `_cov`. 새 래퍼 파일은 메인이 실행 단계에서 작성(사용자 검토 대상).
- **무시하는 것**: 상태 간 상관(공유 변수), 선호 범위·부분 순서, ∃w∀s, B10 태그 중 E1/E2 구분.
- **C′ 대조**: `run_Bp`(R5 B′: 모듈별 정확 계산 후 결합). 단계별로는 정확하지만 공유 변수 상관을 버린다(R5 E4 0.793). C와 함께 보고하면 "순차 연결의 손실"과 "정확 모듈 결합의 손실"을 분리할 수 있다.

## 6. 방법 D — MitPlan식 정당한 확장 (독자 구현)

MitPlan 2.0 보고서가 스스로 열어 둔 확장(p.3 "weights can be adjusted", p.9 "alternative plans by changing the objective function")과 PDDL 계획의 표준 우회(초기 상태 시나리오 반복)를 붙인 것이다. 새 알고리즘이 아니다.

1. **시나리오 열거**: 미확인 변수의 일관 상태 s마다 A의 계획 탐색을 따로 실행(폐쇄 세계 대신 s를 초기 상태로).
2. **꼭짓점 재계획**: W의 각 꼭짓점 w_j(부분 순서 polytope면 꼭짓점 열거)마다 가중합 최적 계획을 다시 구함. 모든 꼭짓점에서 같은 계획 → 상태 s에서 필연 최적(CONFIRMED). 다르면 PREF(payload = 꼭짓점 최적 계획 합집합).
   - 알려진 한계 [수학, R5 B-prior-art §6-1]: 꼭짓점 최적 합집합은 가능 최적 집합의 **부분집합**일 수 있다(내부 영역에서만 최적인 계획 누락). D는 이를 보완하지 않는다(보완하면 B와 같아짐). 이 차이를 PREF payload 불일치로 측정.
3. **근거 표지 보류**: 각 s에서 계획 행동의 근거 상태를 `_in_hull_lp`로 판정. NOENTRY → KNOWLEDGE_GAP, OUT → EVIDENCE_GAP(제외하지 않음, F4 금지).
4. **보류 결합**: 상태별 라벨을 `_final()`(R5 SPEC 5절)로 묶는다. 상태 간 ∃w∀s 결합 LP는 하지 않고, 모든 상태 필연 최적의 교집합만 `rnec`로 낸다(`ewas` 미지원 표시).
5. **질문**: B-Q와 같은 변수 고정 재실행을 D 자신의 파이프라인으로 수행(`fix_and_rerun`).
- **재사용**: `weak.py::run_A`의 탐색·비용 로직을 상태·가중치 인자로 바꾼 사본, `strong.py::_states`, `_in_hull_lp`, `_final`. 원본 수정 금지, 새 파일은 메인이 작성(사용자 검토 대상).
- **B와의 예상 차이**(측정 대상, 결론 아님): ① 가능 최적 누락 ② ∃w∀s 혼합 양화(R5 case_H 유형) ③ 계산량(상태 × 꼭짓점 재계획). 공유 변수 상관은 D가 상태별로 근거를 판정하므로 보존된다.

---

## 7. 비교 시 고정 조건과 보고 항목

| 항목 | 규칙 |
|---|---|
| 같은 입력 | 1절 JSON 하나 → 방법별 변환기. 변환 손실(부분 순서 → 상자 근사 등)을 방법별로 기록 |
| 정답 | 실제 사례 정답 출처를 분리: 수학적 정답(`ground_truth.solve`), 지침 원문 일치(임상의), 전문가 판단. 수학적 정답만으로 임상 타당성 주장 금지 |
| 지표 | full 일치, 잘못된 확정, **불필요 보류율**, 정보 부족 vs 근거 부족 구분, 질문 정확도(정답 결정 관련 변수와의 일치), 질문 수·비용, 금지 출력 F1~F5 |
| 범위 민감도 | W 반경·부분 순서 해석, OUT를 구간으로 볼지 ⊥로 볼지(C 정식화 NORM_A/B) 두 설정 모두 보고 |
| 명명 | A = "MitPlan식 독자 구현(원본 미재현)", D = "MitPlan식 확장 독자 구현", B = "이전 R5 결합 정식화(기존 결합)". A′는 실행했을 때만 "ATLAS 원본 코드 실행" |
| 실행 | 사례당 수 초 이내 예상(R5 손 사례 0.004–0.07 s). 미확인 변수 10개 이상이면 B 상태 열거가 길어짐(R5 n=10 15.3 s) → 백그라운드 규칙 적용 |
