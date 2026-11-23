# REUSE_MAP — 이전 R5(결합 정식화) 코드 재사용 지도

- 작성: 2026-11-21, Agent B
- 원본은 읽기만 했고 수정하지 않았다. 복사본 위치: `baselines/agentB/reuse/` (쓰기 권한 제거, `SHA256_MANIFEST.txt` 15개 파일 모두 원본과 MATCH)
- 성격: 아래 함수는 **이전 R5에서 만든 기존 결합 계산**이다. 새 알고리즘이 아니다. 모든 규칙·수치는 [합성]이었다.
- 이번 확인 [코드]: 복사본을 import 해 손 사례 11건(case_A~K)을 돌렸다(stdout만, 결과 파일 없음). `run_B` 최종 라벨 11/11이 동결 정답과 일치했고, `ewas`는 B·B_milp·정답이 11/11 같았다. 사례당 0.004~0.069 s.

---

## 1. 복사본 목록

| 복사본 | 원본 | 역할 |
|---|---|---|
| `reuse/r5_D_experiments/methods/strong.py` | `~/medmap-integrated-b7-b9-b10-validation/D-experiments/methods/strong.py` | **방법 B**(결합 상태공간 + LP), B′(모듈 정확 결합), V(F4 대조군) |
| `reuse/r5_D_experiments/methods/b_milp.py` | 같은 폴더 `b_milp.py` | 방법 B의 단일 MILP 판(∃w∀s, CEGAR) |
| `reuse/r5_D_experiments/methods/weak.py` | 같은 폴더 `weak.py` | **MitPlan식 독자 구현 A**(원본 아님), 단순 파이프라인 C(결측=정상) |
| `reuse/r5_D_experiments/gen_instances.py` | `D-experiments/gen_instances.py` | 입력 스키마 예시, 손 사례 A~K(`hand_cases()`), 무작위 생성기 |
| `reuse/r5_D_experiments/ground_truth.py` | `D-experiments/ground_truth.py` | Fraction 정확 전수 열거 정답기(scipy 미사용) — 실제 사례 계산 검산용 |
| `reuse/r5_D_experiments/evaluate.py` | `D-experiments/evaluate.py` | 채점 규칙(F1~F5, full/state/hold) |
| `reuse/r5_D_experiments/frozen/SPEC.md`, `FREEZE_MANIFEST.json` | `D-experiments/frozen/` | 입력·라벨·금지 출력 사양(동결본) |
| `reuse/r5_C_formalization/integrated_model.py`, `integrated_spec_v1.json`, `hand_cases.py` | `C-formalization/` | P/K/Q 세 불확실성 그룹, 보류 원인(CLOSABLE_BY_P/Q/K), 중복·미확인 상호작용·출처 상충 표현 |
| `reuse/gate0_C_mdq/core.py`, `methods.py` | `~/medmap-gate0-parallel/C-mdq/` | 확인 질문 우선순위(VOI, EC2, minimax regret 질문, 최소 hitting set MILP, 결정나무) |

`evaluate.py`는 시작할 때 `frozen/` 해시를 검사하고 `inputs/instances.json`을 찾으므로 복사본 폴더에서 그대로 돌리면 실패한다(복사본에 `inputs/`·`ground_truth.json` 없음). 실제 사례에는 `run_*` 함수를 직접 부른다.

## 2. 호출 방법 (Python, `~/ai_env/bin/python -I -B`)

```python
import sys
R = "/home/<user>/medmap-original-b7-b9-clinical-validation/baselines/agentB/reuse"
sys.path.insert(0, R + "/r5_D_experiments/methods"); sys.path.insert(0, R + "/r5_D_experiments")
from strong import run_B, run_Bp, run_V      # numpy, scipy(HiGHS) 필요
from b_milp import run_Bmilp
from weak import run_A, run_C
from ground_truth import solve               # 정확 정답(Fraction)
out = run_B(inst)                             # inst = 아래 3절 스키마 dict
```

추가 패키지 없음(env.txt: python 3.12.3, numpy 2.1.2, scipy 1.17.1). `-B`를 주면 읽기 전용 폴더에 `__pycache__`를 만들려 하지 않는다.

## 3. 입력 스키마 (R5 D 인스턴스, `frozen/SPEC.md` 1절)

```json
{
  "id": "case_X", "exp": "case", "k": 3,
  "obs": ["U", "T", "F"],                 // 임상 이진 변수 c0..c_{k-1} 관측: T/F/U(미확인)
  "deps": [[0, 1]],                       // c0=1 -> c1=1
  "guidelines": [                          // 지침별 적용 조건과 선택지
    {"app": [[0, 1]], "options": [3, 4]}  // app = 리터럴 [변수, 값] 논리곱(빈 목록=항상), options[0]=1차 권고, 나머지=대체
  ],
  "actions": [                             // 행동 id = 리스트 위치. 지침 간 id 중복 금지
    {"id": 0, "effect": 2, "pills": 1, "visits": 0,
     "trial": [[50, 6], [70, 6], [50, 10], [70, 10]]}   // 시험 참가자 2차원 공변량 점(볼록 껍질), null = 근거 항목 없음
  ],
  "rules": [
    {"a": 1, "b": 3, "cond": [[0, 1]], "type": "conflict"},   // a,b 동시 실현 + cond 참이면 허용 불가
    {"a": 0, "b": 1, "cond": [], "type": "compatible"}         // 양립 진술(같은 쌍 conflict와 공존 시 NO_GROUND_TRUTH)
  ],
  "patient_cov": {"x0": 60, "x1_base": 3, "x1_delta": 5, "x1_var": 0},  // x(s)=(x0, x1_base + x1_delta*s[x1_var])
  "W": {"center": ["2/5", "3/10", "3/10"], "r": "1/5"},   // 기준 (효과, -알약, -방문) 가중치 상자 ∩ 단체, r=0 이면 점 선호
  "params": {}
}
```

- 계획 = 지침마다 선택지 1개. 계획 번호 = `itertools.product(options_0, options_1, ...)` 순서. `ewas`·`fsew`는 이 번호 목록이다.
- 공유 변수: `x1_var`가 미확인 변수이면 같은 숨은 임상 변수가 지침 적용·규칙 조건·근거 지지에 동시에 들어간다(R5에서 B′가 정보를 잃은 구조).

## 4. 출력 스키마

| 키 | 의미 | 값 |
|---|---|---|
| `final` | 최종 범주 | REAL_CONFLICT / CONVERGED / CONFIRMED_PLAN / PREFERENCE_DEPENDENT / EVIDENCE_SCOPE_INSUFFICIENT / KNOWLEDGE_GAP / CONDITIONAL_CONFLICT / CONDITIONAL_PLAN / INFO_HOLD / NO_GROUND_TRUTH |
| `per_state` | 미확인 변수 값별 조건 함수 | `{"c0=0": (kind, payload), ...}`, kind ∈ CONFLICT / KNOWLEDGE_GAP / EVIDENCE_GAP / CONFIRMED / PREF, payload = 실현 행동 집합 목록 |
| `ewas` | ∃w∀s: 하나의 선호로 모든 상태에서 최적인 계획 번호 | list |
| `fsew` | ∀s∃w | list (RNEC ⊆ EWAS ⊆ FSEW) |
| `app` | 지침 적용 3값 | CONFIRMED_APPLY / NOT_APPLY / CONDITIONAL_APPLY |
| `rules` | 규칙별 발동 3값(1차 권고 기준) | REAL / NONE / CONDITIONAL / N/A |
| `single_plan`, `excluded_out_of_support` | 채점용 표지 | bool |

`run_Bmilp`는 `dict(ewas, app, meta)`만 낸다(상태별 라벨 없음).

## 5. 함수별 재사용 지도

| 기능(B7/B9/B10) | 함수 (`strong.py`) | 근거 |
|---|---|---|
| 미확인 변수 상태 열거 + 의존성 | `_states(inst)` → `(U, S)` | 2^|U| 열거. R5에서 n=10 15.3 s |
| 지침 적용 3값, 규칙 실제/조건부 | `_components(inst, S, G)` | B7 실제/조건부 충돌, 적용 조건 미확인 |
| 모순 규칙(정답 없음) | `_contradiction(inst, S, G)` | |
| 근거 지지(볼록 껍질 LP) | `_in_hull_lp(points, p)`, `_cov(inst, s_val)` | B10 OK/OUT/NOENTRY |
| 상태별 허용 계획·기준 벡터 | `_state_core(inst, plans, G, s, ev_of, mode)` | 효과 미정의를 0으로 두지 않음 |
| 불완전 선호 필연/가능 최적 | `Wset.min_dot`, `Wset.max_tau`, `_prefs(vecs, Wv)` | B9: ∀w는 LP 최솟값, ∃w는 τ 최대화 LP |
| 상태 간 양화 | `_joint_queries(keys, info, plans, Wv)` | EWAS/FSEW/RNEC |
| 최종 범주 | `_final(per_state, rules, nogt)` | SPEC 5절 우선순위 |
| 전체 실행 | `run_B(inst)`; `run_Bp(inst)`; `run_V(inst)` | |
| 단일 MILP | `b_milp.Model(inst).ewas()`, `.app_status()`, `run_Bmilp(inst)` | n=20까지 n별 중앙값 0.29 s 이하(R5) |
| MitPlan식 A(독자 구현) | `weak.run_A(inst)`: 폐쇄 세계(U→0), 점 선호(W center), 근거 무시, 계획 1개 | 원본 아님 |
| 결측=정상 단순 | `weak.run_C(inst)` | 참고용 |
| 정확 정답 | `ground_truth.solve(inst)` | Fraction 정확, 실제 사례 검산용 |

## 6. R5 C 정식화에서 가져올 것 (`r5_C_formalization/integrated_model.py`)

| 기능 | 함수/필드 | D 스키마에 없는 이유와 쓰임 |
|---|---|---|
| 출처 상충 관측 `C` | `MAIN["obs"]`, `clinical_states()` | D는 T/F/U만. 실제 기록 상충(예: 칼륨 기록 2개)에 필요 |
| 규칙 종류 CONTRAINDICATION / CONFLICT / DUPLICATE / UNKNOWN_INTERACTION | `MAIN["rules"]`, `feasible()` | D는 conflict/compatible만. **B7 중복**과 **지식 미확인 상호작용**(K 그룹) 표현 |
| 보완(시너지) | `MAIN["synergy"]` | B7 상호 보완 |
| 부담 상한 불명 | `bcap_options`, `feasible()` | B9 치료 부담 상한이 2 또는 3처럼 불명 |
| 선호 부분 순서 | `W_matrices()` (`order`, `lo`, `hi`) | D는 중심±r 상자만. 실제 선호 진술("걷기 > 약 개수")은 부분 순서 |
| B10 다섯 구분 태그 | `effects[...]` 의 `E1/E2/E3`, `OUT/PUB/NONE`, `NORMS` | 참가 조건 충족 / 유사 참가자 / 일반화 근거 / 판정 불가 / 근거 없음 |
| 보류 원인 | `judge()`, `categorize()` → `CLOSABLE_BY_P|Q|K`, `KNOWLEDGE_GAP_ALL_STATES` 등 | 무엇으로 닫히는 보류인지(임상 정보/선호/지식) |
| MILP 판 | `milp_AA()`, `milp_exists()` | AA·EE·CLOSE_P만 구현(R5 한계) |

C 정식화 입력은 D와 다른 dict(`MAIN` 형식, 약 = 문자열, 계획 = 약 부분집합 전체)다. 두 스키마는 R5에서 통합되지 않았다.

## 7. 확인 질문 우선순위 (`gate0_C_mdq/`)

R5 B는 질문 순위를 내지 않는다. 기존 정보 획득 정책은 Gate0 C에 있다.

| 함수 | 내용 |
|---|---|
| `core.GridModel(inst)` | 가설 = (임상 세계, 선호 격자점). `tests`= 임상 질문(`kind='clin'`, items, cost) / 선호 질문(`kind='pref'`, j, k, rho) |
| `methods.hitting_set_milp(M)` | 결론이 다른 원자 쌍을 모두 구분하는 최소 비용 질문 집합(일괄) |
| `methods.build_tree(M, choose)` + `pol_ec2()`, `pol_voi()`, `pol_regret()`, `pol_greedy_count` | 적응형 질문 순서(결정나무) |
| `methods.eval_tree`, `tree_metrics` | 평균·최악 질문 수/비용 |

주의: `GridModel`은 선택지 점수 = base + delta·s 형식이고 지침 상호작용·근거 지지를 직접 표현하지 않는다. R5 B와 연결하려면 어댑터가 필요하다(METHOD_SPECS 4·5절의 "변수 고정 재실행" 방식이 가장 단순). 선호 가설을 격자로 근사하므로 정확한 W polytope와 다르다.

## 8. 실제 사례 투입 시 알려진 제약 (코드 확인)

1. 공변량은 2차원, 공유 변수는 `x1_var` 하나뿐이다. eGFR과 칼륨처럼 두 숨은 변수가 각각 다른 시험 경계를 정하면 `_cov`/`b_milp.Model.bad`를 확장해야 한다(새 파일에서 복사 후 수정, 원본 수정 금지).
2. 시험 지지 영역은 점 목록의 볼록 껍질이다. 시험 참가 조건 상자(예: eGFR ≥ 20, K⁺ ≤ 5.0)를 넣으려면 상자 꼭짓점을 점으로 넣는다. 실제 참가자 분포(IPD)는 없다.
3. 규칙 종류가 conflict/compatible뿐이다(중복·보완·미확인 상호작용은 C 정식화 쪽).
4. 기준은 (효과, −알약, −방문) 3개로 고정이다. 주사 빈도·검사 부담 같은 실제 부담 속성은 `pills`/`visits` 자리에 매핑하거나 기준 수를 늘려야 한다.
5. 효과 수치는 단일 값(`effect`)이다. 효과 구간은 C 정식화(`IV`, L, U)에만 있다.
6. 상태 열거는 미확인 변수 수에 지수적이다(B_milp는 ∃w∀s만 대체).

## 9. 원본 무수정 확인

- 복사는 `cp -p`만 사용했다. 원본 경로에 쓰기·이동·삭제 없음.
- `reuse/SHA256_MANIFEST.txt`에 복사본·원본 해시 대조(15/15 MATCH)를 남겼다.
