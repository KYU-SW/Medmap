# C_INTEGRATED_PROBLEM_FORMALIZATION: B7+B9+B10 통합 문제의 수학적 정의 (SUBAGENT C)

- 작성: 2026-11-18 12:15 KST, 사양 파일 `integrated_spec_v1.json` 작성 시각: 2026-11-18 12:12 KST
- 모든 약·규칙·효과·조건은 **합성**이다. 의학적 정확성이나 치료 추천은 주장하지 않는다.
- 태그: [직접 원문 확인] [실제 코드 실행] [수학적 검토] [합성 실험] [연구 가설] [미검증]
- 아래 범주 구분(모든 상태에서 성립 / 일부 상태 / 정보 부족 / 지식 부족 / 전문가 판단)은 **새롭다고 주장하지 않는다**.

---

## 0. 판정

**핵심 질문: "B7, B9, B10의 변수와 제약을 하나의 기존 수학적 모형으로 표현할 수 있는가?" → 조건부 가능**

- [수학적 검토][실제 코드 실행] 표현 가능한 것: 임상 3값 상태, 의존성, 지침 적용 조건, 조합 처방, n항 hard 금기, 조건부 충돌, 중복, 미확인 상호작용, 부담 상한(미확정), 가중치 polytope, 효과 구간, 근거 상태(B10 다섯 구분).
  - 이 전부를 **양화(∀/∃) 선형 질의의 묶음** 하나로 쓸 수 있다.
  - 각 질의는 MILP 하나(AA, EE, ∃P∀rest)로 풀린다. ∃w∀s처럼 2단계 구조인 질의는 이산 ∀ 변수를 펼치거나(expansion) cutting plane을 쓰면 된다.
  - 구조적으로는 이전 JNP 정식화(3값 상태 × 가중치 polytope × 양화 플래그)에 다음을 붙인 것과 같다: 선택지를 조합 처방으로 확장, 효과를 구간으로, 근거 상태를 상태 의존 구간 매핑으로, 불확실성을 P/K/Q 세 그룹으로 나눔. **새 알고리즘이 아니다.**
- [실제 코드 실행][합성 실험] scipy milp(HiGHS) 단일 MILP와 전수 열거+LP(정답 기준)의 플래그를 대조했다. 불일치 0건:
  - 주 인스턴스 192건(2규범 × 32처방 × 3플래그)
  - 무작위 합성 인스턴스 90개의 8,640건
  - 손계산 사례 5/5 (AA=1 경로 포함)
- [수학적 검토] 효과 구간 처리: 가중치 w ≥ 0, 효용이 가산, 효과 구간이 (약, 기준)별로 독립된 상자일 때는 **양 끝값 대입이 정확**하다(§5.2 증명). 이 조건이 깨지면 다음과 같다.
  - 효과끼리 상관이 있는 경우: 효과 시나리오를 이산 변수로 두면 MILP로 정확히 풀린다. 연속 상관 집합이면 w·e 쌍선형 실행가능성 문제가 되는데, 이것은 이미 알려진 비볼록 QCQP 범주다.
- **표현할 수 없는 것** (계산 문제가 아니라 입력이나 규범이 없는 경우)
  1. ⊥: 효과의 구간 자체를 정할 근거가 없음 = **입력 부재**. 모형은 ⊥를 (−∞, +∞)로 두고 "판정 불가 + 원인 표시"까지만 할 수 있다. 값을 만들어내지 못한다.
  2. 규범 선택: 지지 영역 밖(OUT)이나 공개 근거로 판정 불가(PUB)인 경우를 넓은 구간으로 볼지 ⊥로 볼지, 중복을 금지로 볼지 → **전문가 판단(C)**. 모형은 두 규범을 모두 계산해 결과가 갈리는지만 보여준다.
  3. 실제 치료 효과(D 정답)와 지침 원문 인코딩의 충실도(B 정답)는 모형 밖이다.

---

## 1. 이전 결과와의 관계 (이름만 바꾼 재제안 금지 확인)

| 이전 결과 (읽기 전용) | 이번 정식화에서의 위치 |
|---|---|
| JNP (`B_JNP_REPORT.md`): 3값 임상 × W polytope, 다섯 양화, 5범주, MILP로 정확 | §4 최적성·플래그 정의가 JNP 정의를 그대로 확장한 것. 새 플래그 CLOSE_G는 JNP의 EA(∃s∀w)를 그룹 단위로 일반화한 것뿐임 |
| P* (`K1_PRIOR_ART_AUDIT.md`): 집계표 기반 4값 지지 판정, A_t ⊆ {Φ_t=1} | §3.8의 E2 상태 값(IN/OUT/PUBLIC_UNRESOLVED)을 **입력**으로 받음. P* 계산(집계표 LP)은 여기서 다시 하지 않음 |
| MDQ (`C_MDQ_REPORT.md`): 최소 확인 정보 = hitting set / 결정나무 | 이번 범위 밖. CLOSE_G는 "어느 그룹을 확인하면 닫힐 수 있는가"만 답하고, 최소 질문 집합은 다루지 않음 |
| 반례 문서 (`COUNTEREXAMPLES_AND_COMPUTATIONAL_GAPS.md`): n항 MILP, MUS, ε-constraint, 볼록 껍질 LP로 모두 해결 | n항 hard 규칙과 조합 처방은 같은 MILP 인코딩. 확실성 전파는 규범 선택이라는 결론(W3)과 같은 이유로 §3.10 규범 매개변수를 둠 |

---

## 2. 기호

- P: 환자 임상 변수, K: 지식 변수(미확인 상호작용 u, 효과 e), Q: 선호 변수(w, Bcap)
- X: 처방(약의 부분집합), x*: 판정 대상 처방
- S_P, S_K, S_Q: 각 그룹의 허용 값 집합

---

## 3. 정의 (임무 1–12)

### 3.1 환자 상태 변수
- s = (c_1..c_k) ∈ {0,1}^k. 확인된 값은 상수로 둔다.

### 3.2 미확인 임상 변수
- obs_i ∈ {T, F, U(미확인), C(출처 상충)}. U와 C는 둘 다 "0/1 모두 가능"으로 취급한다.
  - C를 U로 보는 것은 정의상 선택이다. 출처의 신뢰도에 가중치를 주지 않는다.
- provenance_i: 출처·확인 상태. 판정 계산에는 쓰지 않고 출력의 근거 표시에만 쓴다.
- 의존성: imp(a,b), excl(a,b)는 2-절이다.
- S_P = {s : obs와 일치하고 의존성을 만족}. S_P = ∅이면 DATA_CONFLICT.

### 3.3 지침 적용 조건
- app_g(s) = 리터럴의 논리곱. app_g(s)=1이면 처방 x는 cover_g의 약을 하나 이상 포함해야 한다(hard).
- 적용 지침을 모두 만족하는 적격 처방이 없는 상태는 지침 집합 수준의 실제 충돌로 출력한다(GUIDELINE_SET JOINTLY_UNSATISFIABLE).

### 3.4 선택지 / 권고 집합
- X = 약의 부분집합 전체(조합). MILP에서는 x ∈ {0,1}^n(AA 질의) 또는 명시 목록(EE, CLOSE 질의)으로 둔다.

### 3.5 권고 간 제약
- hard 규칙 (D, λ): D ⊆ x ∧ λ(s,u)이면 부적격. 선형식은 Σ_{i∈D} x_i + Σ lit(λ) ≤ |D|+|λ|−1. n항도 같은 꼴이다.
- 종류
  - CONTRAINDICATION: 단일 약 + 상태
  - CONFLICT: 쌍 + 상태 = 조건부 충돌
  - DUPLICATE: 같은 계열. 본 모형은 금지로 인코딩했고, 이것은 모델링 선택이다(C).
  - UNKNOWN_INTERACTION: 리터럴이 지식 변수 u. u=1 세계에서 금지.
- 보완: 쌍 효과 항 [L, U]를 별도 효과로 더한다.
- 안전 제약은 **벌점으로 섞지 않는다**. 부적격 처방은 어떤 선호로도 최선이 될 수 없다.

### 3.6 선호의 가능한 범위
- W = {w ≥ 0, Σw = 1, 서열 w_a ≥ w_b, lo_j ≤ w_j ≤ hi_j}. 환자의 부분 순서와 구간 진술을 다면체로 옮긴 것이다.
- 한 점으로 확정하지 않는다. lo = hi는 환자가 정확한 값을 말한 경우에만 쓴다.

### 3.7 치료 부담
- 부담 기준 v_burden(x) = −b(x)/5, b(x) = Σ pills_i x_i. 가중치 w_burden ∈ W로 효용에 들어간다.
- 부담 상한 Bcap ∈ S_Q. 환자가 확정하지 않았으면 여러 값으로 두고, 선호 그룹(Q)으로 양화한다.

### 3.8 근거 적용 범위 (B10 다섯 구분, 각각 별도 상태)
(선택지 i, 기준 j, 상태 s)마다 다음을 둔다.

| 상태 | 값 | 정의 |
|---|---|---|
| E1 참가 조건 충족 | MET / NOT_MET / NO_TRIAL | Φ_t(s) |
| E2 실제 참가자 중 유사자 | IN / OUT / PUBLIC_UNRESOLVED / NO_TRIAL | s가 지지 영역 A_t 안인가. PUBLIC_UNRESOLVED는 P*의 "공개 근거로 판정 불가" |
| E3 효과 일반화 근거 | SUPPORTED / UNASSESSED / INDIRECT / NO_TRIAL | 효과 수정인자·전이 근거 |
| E4 정보 부족으로 판정 불가 | YES / NO (환자 수준 파생) | E1–E3가 S_P 위에서 상태마다 다름 |
| E5 근거 자체 부족 | ALL / SOME / NO | T(r) = ∅ |

- [수학적 검토] A_t ⊆ {Φ_t = 1}이므로 E1=NOT_MET이면 E2≠IN이다. 반대로 E1=MET이어도 E2=IN은 **함의되지 않는다**(주 인스턴스 B1: E1=MET_ALL, E2=OUT_ALL).
- 효과 매핑(규범 표)
  - (E2=IN) → 근거 구간
  - OUT → [a,b](결과 척도 범위) 또는 ⊥
  - PUB → 넓힌 구간 또는 ⊥
  - NO_TRIAL → ⊥
  - OUT과 PUB의 처리는 §3.10 규범 매개변수가 정한다.

### 3.9 지식 부족 상태
- ⊥ = 효과 구간을 인정할 근거가 없음. **0이 아니다.** 의미는 (−∞, +∞)다.
- KNOWLEDGE_GAP_ALL_STATES: x*가 적격인 모든 P 상태에서 x* 자신의 효과에 ⊥가 있고, 그 기준의 max_{w∈W} w_j > 0.
- KNOWLEDGE_GAP_INFO_DEPENDENT: 일부 상태에서만 ⊥. 임상 정보를 확인하면 지식 부족이 사라질 수도 있다.
  - 부적격 상태의 ⊥는 판단에 쓰이지 않으므로 세지 않는다. 손계산 사례 HC2에서 이 정의를 바로잡았다.
- 미확인 상호작용(u)은 지식 변수다. "상호작용 없음"과 구별한다.

### 3.10 판단 보류 상태
- CLOSABLE_BY_G: 그룹 G의 불확실성만 해소하면 확정될 수 있는 세계가 있다(CLOSE_G 참). 출력 형식은 다음과 같다.
  - 단일 그룹: 'P', 'Q', 'K' (여럿이면 | 로 나열)
  - 단일 그룹으로 안 되면 쌍: 'PQ', 'PK', 'KQ'
  - 쌍으로도 안 되면 CLOSABLE_ONLY_BY_ALL
  - P = 환자 정보 확인, Q = 선호 확인, K = 의학 지식
- EXPERT_JUDGMENT_REQUIRED: 규범 NORM_A(OUT→[a,b], PUB→넓힌 구간)와 NORM_B(OUT, PUB → ⊥)의 범주가 다름. 두 결과를 모두 출력한다.

### 3.11 출력 가능한 판단 (우선순위 순서)
1. DATA_CONFLICT
2. HARD_EXCLUDED
3. KNOWLEDGE_GAP_ALL_STATES
4. KNOWLEDGE_GAP_INFO_DEPENDENT
5. ALWAYS_BEST (AA)
6. NEVER_BEST (¬EE)
7. CLOSABLE_BY_⟨G⟩
8. CLOSABLE_ONLY_BY_ALL
9. 위 결과가 규범마다 다르면 EXPERT_JUDGMENT_REQUIRED

쌍 수준 B7 출력: ACTUAL_CONFLICT_ALL_STATES, CONDITIONAL_CONFLICT_INFO_DEPENDENT, UNDETERMINED_KNOWLEDGE, NOT_TRIGGERED, DUPLICATE, COMPLEMENT_CERTAIN, COMPLEMENT_POSSIBLE. 세부 정의는 사양 파일을 따른다.

### 3.12 출력하면 안 되는 허위 확정 판단
1. ⊥를 0으로 두고 낸 확정
2. 구간을 점 추정으로 바꿔 낸 확정
3. U/C를 F로 가정(closed world)해 낸 확정 또는 제외
4. W가 한 점이 아닌데 한 점으로 낸 "최선"
5. 미확인 상호작용을 "상호작용 없음"으로 출력
6. E1=MET에서 E2=IN을 추론
7. 쌍별 충돌이 없다는 이유로 조합이 안전하다고 판정
8. EE만 성립하는데 "최선"이라고 출력
9. 지식 부족과 정보 부족을 서로 바꿔 출력
10. 규범 의존 결과를 한 규범의 결과로 단정

---

## 4. 통합 질의 (양화)

- opt(x*; s,u,Bcap,e,w) ⇔ feasible(x*) ∧ ∀x ∈ X: feasible(x) ⇒ Σ_j w_j v_j(x*) ≥ Σ_j w_j v_j(x)
  - v_j(x) = Σ_{i∈x} e_ij(s) + 보완 항, 부담 기준은 −b(x)/5
- 플래그
  - AA = ∀P∀K∀Q opt
  - EE = ∃P∃K∃Q opt
  - CLOSE_G = ∃G ∀(나머지) opt
  - 여기서 e는 K 그룹에, w와 Bcap은 Q 그룹에 속한다.
- [수학적 검토] CLOSE_G는 JNP의 EA(∃s∀w)·EwAs(∃w∀s)를 세 그룹으로 일반화한 것이다. 성질:
  - AA ⇒ CLOSE_G ⇒ CLOSE_{G∪H} ⇒ EE
  - CLOSE_{PKQ} = EE

---

## 5. MILP 표현 (구체화)

### 5.1 인코딩
- 임상 변수: 이진 s. T/F는 경계를 [1,1] 또는 [0,0]으로 고정. 의존성은 s_a ≤ s_b, s_a + s_b ≤ 1.
- 지식 u: 이진. Bcap: one-hot 선택자 σ. 제약 Σ pills_i x_i ≤ Σ o·σ_o.
- 규칙·적용 조건: 리터럴 논리곱의 지시변수 z = AND(lits)를 정확하게 선형화한다. z ≤ lit, z ≥ Σlit − (n−1).
- 상태 의존 효과: e_ij(s) = Σ_r val_r · ind_r(s). ind_r은 분할(첫 일치) 규칙의 AND 지시변수다.
- w × (이진) 곱: McCormick 선형화. w ∈ [0,1]이고 상대가 이진이면 정확하다.
- 경쟁 처방이 이진 변수 x인 AA 질의: x_i ∧ ind_r을 다시 AND로 만든 뒤 w와 곱한다.
- 질의별 형태
  - AA: (a) ∃n: x* 부적격 (MILP 실행가능성), (b) max_{n,w,x} U(x) − U(x*) ≤ 0. 단일 MILP 두 개.
  - EE: ∃(n,w). 명시된 경쟁 처방마다 f_x(n)(적격 지시) ⇒ Δ_x · w ≥ 0 (big-M). 단일 MILP.
  - CLOSE_P (∃P ∀K∀Bcap ∀w):
    - ∀K, ∀Bcap: 이산 값마다 제약 사본을 만든다(expansion).
    - ∀w: LP 쌍대로 바꾼다. min_{w∈W} c(s)·w ≥ 0 ⇔ ∃λ, μ ≥ 0: λ + h·μ ≥ 0, λ + (Gᵀμ)_j ≤ c_j(s).
    - 그러면 단일 MILP가 된다.
  - 남은 CLOSE_G(∃w∀s 형)는 JNP와 같이 결합 LP 또는 cutting plane으로 푼다. 이번 MILP 구현에는 넣지 않았고 brute로만 계산했다 [미검증: MILP 구현].

### 5.2 효과 구간의 양 끝값 대입 정확성 (증명) [수학적 검토]
- 고정된 (s, u, Bcap, w)와 경쟁 처방 x에 대해 차이는 다음과 같다.
  - Δ_x = Σ_j w_j [Σ_{i∈x*∖x} e_ij − Σ_{i∈x∖x*} e_ij] + (보완 항 차) + (부담 차)
  - 두 처방에 공통인 약의 효과는 상쇄된다.
- w ≥ 0이므로 Δ_x는 다음과 같이 움직인다.
  - i ∈ x*에 대해 e_ij의 비감소 함수 (x∖x*에는 나타나지 않음)
  - i ∉ x*에 대해 비증가 함수
- 따라서 e⁻ = (i∈x*이면 L, 아니면 U)는 **모든 w와 모든 경쟁자 x에 대해 동시에** Δ_x를 최소화한다. e⁺는 동시에 최대화한다. 보완 항도 같다(쌍 ⊆ x*이면 L, 아니면 U).
- opt는 경쟁자에 대한 Δ_x ≥ 0의 논리곱이고 e는 독립 상자다. 그러므로 어떤 양화 순서(∀e∃w, ∃w∀e 등)에서도 ∀e는 e⁻로, ∃e는 e⁺로 정확히 바뀐다.
  - 예: ∀e∃w: e⁻에서 성립하는 w는 모든 e에서도 성립한다.
- 성립 조건: (i) w ≥ 0, (ii) 가산 효용, (iii) 효과 구간이 서로 독립인 상자, (iv) 구간이 처방 선택에 의존하지 않음
  - 상호작용이 효과를 바꾸면 그 조합을 별도 효과 항으로 둔다.
- 깨지는 경우
  - 공통 효과 수정인자 때문에 효과들이 같이 움직이는 경우: 시나리오 이산 변수 → MILP(정확)
  - 연속 결합 집합: Σ w_j e_j가 쌍선형 → ∀ 판정은 (W 꼭짓점 × E 꼭짓점)으로 충분(양쪽이 각각 선형). ∃ "모든 경쟁자에 동시에" 판정은 비볼록 쌍선형 실행가능성(공간 분기한정)이 된다. 알려진 범주다. 이번에는 실행하지 않았다 [미검증].

### 5.3 ⊥의 MILP 처리
- 구현: ⊥ = [−M, +M], M = 10. 효용 범위는 약 ±1이다.
- 엄밀한 의미는 M → ∞ 극한이다.
  - 경쟁자의 ⊥는 ∀ 판정을 막는다(max w_j > 0이면).
  - ∃ 판정은 막지 않는다.
  - x* 자신의 ⊥는 플래그와 상관없이 KNOWLEDGE_GAP으로 분류한다.
- [실제 코드 실행] M=10과 M=1000 비교(17개 인스턴스 × 2규범, 1,088 처방): 범주 차이 0. 플래그 차이 1건은 x* 자신에 ⊥가 있는 처방이었고, 그 플래그는 범주 판정에 쓰이지 않는다(`logs/m_stability_*.log`).
- 정리: 모형은 ⊥를 **"판정 불가 + 어떤 지식이 없는지"** 로만 내보낸다. ⊥에서 값을 만들어내지 않는다 = 입력 부재.

---

## 6. 실행 결과 [실제 코드 실행][합성 실험]

### 6.1 주 인스턴스 (`results/main_*.csv`, `logs/run_main_v2fix_*.log`)
- 입력
  - |S_P| = 3: ckd = U, hk = C, 의존성 hk → ckd
  - |S_K| = 2: u_B1S 미확인
  - Bcap ∈ {2, 3}, 처방 32개
- 범주: HARD_EXCLUDED 20, KNOWLEDGE_GAP_INFO_DEPENDENT 4, EXPERT_JUDGMENT_REQUIRED 5, CLOSABLE_ONLY_BY_ALL 2, CLOSABLE_BY_PQ 1
- B7 쌍 상태
  - R1(A1 금기, ckd): CONDITIONAL_CONFLICT_INFO_DEPENDENT
  - R2(A2+B1, hk): CONDITIONAL_CONFLICT_INFO_DEPENDENT
  - R3: DUPLICATE
  - R4(B1+S): UNDETERMINED_KNOWLEDGE
  - A1+B2 보완: COMPLEMENT_POSSIBLE
  - 지침 집합: SATISFIABLE_ALL
- B10 (`main_b10_evidence_status.csv`)
  - B1: E1=MET_ALL이지만 E2=OUT_ALL → 참가 조건 충족 ≠ 근거 적용 사례
  - S/benB: E5=SOME, ⊥=SOME
  - A2: E2 = INFO_DEPENDENT{IN | PUBLIC_UNRESOLVED}
- MILP 대 전수 열거: 192건 중 불일치 0
- 단순 기준선의 허위 확정 (정답이 비확정인데 ALWAYS/NEVER/HARD를 출력한 수, 처방 32개 중)

| 기준선 | 범주 변경 | 허위 확정 |
|---|---|---|
| ⊥ := 0 | 9 | **6** |
| closed world (U/C→F) | 12 | 1 |
| 효과 점 추정 | 7 | 2 |
| 가중치 한 점 | 6 | 0 |
| 미확인 상호작용 = 없음 | 5 | 0 |
| E1=MET ⇒ 근거 적용 | 5 | 0 |
| Bcap = 3 가정 | 5 | 0 |

- 범주 변경이 있어도 허위 확정 0인 기준선은 비확정 범주끼리만 바뀐 것이다. 예: CLOSABLE ↔ EXPERT, 원인 표시 오류.
- 표본은 인스턴스 하나다. 빈도로 일반화하지 않는다(D 실험의 몫).

### 6.2 손계산 사례 (`hand_cases.py`, 기대값은 실행 전에 작성)
- HC1 A1+B1: ALWAYS_BEST. AA=1인 경우 MILP 일치.
- HC1 S: NEVER_BEST.
- HC2 A1+B1: 두 규범 모두 CLOSABLE_BY_P.
- HC3 A1+B1: KNOWLEDGE_GAP_ALL_STATES.
- 5/5 OK. HC3에 ⊥ := 0을 적용하면 NEVER_BEST가 나온다 → 허위 확정.

### 6.3 변형 V2 (`results/v2_plan_judgments.csv`)
- age75 = U, S의 ⊥를 간접 근거 구간으로 바꿈. |S_P| = 6.
- 나온 범주: CLOSABLE_BY_PQ|PK|KQ, CLOSABLE_BY_KQ, CLOSABLE_BY_PQ, CLOSABLE_ONLY_BY_ALL, EXPERT_JUDGMENT_REQUIRED

### 6.4 무작위 합성 (`results/random_milp_vs_brute.csv`, `logs/run_validate100_fix_*.log`)
- seed 20261118, 100개 생성. S_P = ∅인 10개는 DATA_CONFLICT. 나머지 90개 × 32처방 × 3플래그 = 8,640건, **불일치 0**. 소요 33.8초.
- 양성 플래그 수(최종 CSV): AA 0, EE 794, CLOSE_P 2. 2,880행 모두 일치.
  - **AA=1 검증은 손계산 HC1에만 의존**하고, CLOSE_P 양성도 적다 → 한계.
- 범주 분포: HARD_EXCLUDED 1982, KNOWLEDGE_GAP_INFO 287, KNOWLEDGE_GAP_ALL 185, CLOSABLE_ONLY_BY_ALL 173, CLOSABLE_BY_KQ 87, NEVER_BEST 68 등. 분포가 치우쳐 있다.

---

## 7. 정답 종류

| 출력 | A 수학 | B 지침 원문 | C 전문가 | D 실제 효과 |
|---|---|---|---|---|
| 플래그 AA/EE/CLOSE_G | brute = MILP로 검증 가능 | 규칙 인코딩 충실도에 의존 | — | 검증 불가 |
| HARD_EXCLUDED, 쌍 B7 상태 | 가능 | **필요**(규칙이 원문과 같은가) | 중복을 금지로 볼지 | — |
| B10 E1 | 가능 | 시험 기준 원문 필요 | — | — |
| B10 E2 / E3 | P*·LP 결과를 입력으로 받는 경우만 | 시험 Table 1 원문 | — | IPD 필요 |
| KNOWLEDGE_GAP | 정의상 가능 | — | ⊥로 볼지의 규범 | — |
| EXPERT_JUDGMENT_REQUIRED | 규범 간 차이 계산은 가능 | — | **필요** | — |
| "최선 처방이 실제로 환자에게 낫다" | — | — | — | **모형 밖** |

---

## 8. D 실험용 사양
- `integrated_spec_v1.json`(2026-11-18 12:12 KST)에 입력 스키마, B10 상태, ⊥ 의미, 범주 우선순위, 허위 확정 목록, 채점 규칙을 적었다.
  - 채점 규칙: false_certain, unnecessary_withholding, gap_misattribution, category_changed
- 정답 기준 구현: `integrated_model.py`의 `categorize`(두 규범으로 실행)

---

## 9. 한계
- 모든 입력은 합성이고 규모가 작다: 약 5개, 처방 32개, |S_P| ≤ 8. 실제 규모의 확장성은 측정하지 않았다 [미검증].
  - 이전 JNP 결과로는 nU 20까지 MILP가 평탄했다.
- MILP는 AA, EE, CLOSE_P만 구현했다. 나머지 CLOSE_G는 brute만 있다.
- 효과 상관(비독립 상자)은 증명상의 분기만 적었고 실행하지 않았다.
- 규범은 두 개만 비교했다. 실제 전문가 규범 공간은 더 넓다.
- "제외로 닫힘"(∃G∀rest ¬opt)은 정의만 가능하고 구현하지 않았다.
- C(출처 상충)를 U와 같게 취급했다. 출처 신뢰도 모형은 넣지 않았다.
- 범주 구분과 정식화는 기존 MCDA(ROR/SMAA), QCSP/2QBF, certain answer, positivity, 부분 식별 틀의 결합이다. 새 계산 문제가 아니다 [수학적 검토].
  - 선행연구에 같은 통합 정식화가 있는지는 B(선행) 서브에이전트가 확인할 일이다 [미검증].

## 10. 파일
- `integrated_model.py`: 모형, 전수 열거 정답, MILP
- `run_main.py`, `run_validate.py`, `hand_cases.py`, `m_stability_check.py`
- `integrated_spec_v1.json`
- `results/`: main_plan_judgments, main_b7_pair_status, main_b10_evidence_status, main_naive_false_certainty, main_milp_vs_brute, v2_plan_judgments, random_milp_vs_brute (csv)
- `logs/`
  - 수정 전 실행 로그 `run_main_20261118_1206.log`, `run_validate*_1207.log`는 gap 정의를 수정하기 전 것이다. 기록용으로 남겨 두었다.
  - 최종 로그: `run_main_v2fix_*`, `run_validate100_fix_*`, `hand_cases_*`, `m_stability_*`
