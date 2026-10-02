# STEP 14 — VALUE/CONTEXT EVIDENCE RECOVERY AUDIT (2026-09-21)

TEST 미사용(재계산 0회). TRAIN 통계(`cond_token_logp.npz`) + VALIDATION 분석. Step 8~13B 무수정. git commit 21ff2aa (이 단계에서 저장소 초기화), PROVENANCE.md에 입력·출력 SHA256·환경·버전 기록.

## 판정: **STEP14_RECOVERY_PARTIAL_GO**

## Q1. 제외된 140개는 무엇인가 (`01`, `02`, `02b`)
223 = 기존 usable 83 + 제외 140 (파일 재계산, ID 중복 없음). 제외 140의 구성:
| 유형 | n | 값 유형 | validate 환자당 기대 토큰 수 |
|---|---|---|---|
| MEDICAL_HISTORY (과거력·현병력: 천식·고혈압·COPD·HIV…) | 52 | binary | 1.51 |
| LIFESTYLE(거주·직업·음주·흡연…) + RISK_FACTOR + EXPOSURE + DEMOGRAPHIC + TRAVEL | 31 | binary(여행 1 categorical) | 2.38 |
| FAMILY_HISTORY | 13 | binary | 0.20 |
| MEDICATION | 11 | binary | 0.22 |
| SYMPTOM/SIGN인데 HPO 없음(Chest pain at rest, Paroxysmal cough, Expiratory wheeze, Vaginal discharge…) + 병변 속성 | 16 | binary 12·categorical 3·multi 1 | 2.63 |
| **ANATOMICAL_LOCATION** (통증 부위 E_55·방사 E_57·병변 E_133·부종 E_152, 165개 값) | 4 | multi-choice | **5.60** |
| SEVERITY (통증 강도·정확도·가려움·병변 크기·부종) | 5 | 0~10 ordinal | 2.21 |
| TEMPORAL (발생 속도 E_59, 진행 E_13) | 2 | ordinal/binary | 0.83 |
| PROCEDURE·PREGNANCY | 6 | binary | 0.11 |
환자당 노출 토큰 ~20개 중 **15.7개가 제외군**, 4.5개만 기존 usable. 제외군의 정보량이 기존 83개의 3.5배.

## Q2. 기존 S2 성능 기여 (`03_validation_ablation.csv`, VALIDATION k3, seed 3개 평균; 개발 분석이지 최종 성능 아님)
| 조건 | AUROC | Δ vs FINDING_ONLY | 제거 시 Δ vs ALL |
|---|---|---|---|
| ALL (전체 evidence) | **0.917** | +0.250 | — |
| FINDING_ONLY (83) | 0.668 | 0 | −0.250 |
| +LOCATION (4개, 부위 값) | **0.749** | **+0.082** | −0.084 |
| +MEDICAL_HISTORY (52) | 0.715 | +0.048 | −0.041 |
| +EXCLUDED_SYMPTOM_SIGN (16) | 0.710 | +0.042 | −0.041 |
| +RISK/EXPOSURE (31) | 0.708 | +0.040 | −0.034 |
| +SEVERITY (5) | 0.684 | +0.017 | −0.012 |
| +TEMPORAL (2) | 0.676 | +0.008 | −0.005 |
| +MEDICATION (11) | 0.677 | +0.009 | −0.006 |
| +FAMILY_HISTORY (13) | 0.674 | +0.007 | −0.004 |
| +VALUE_LEVEL_ALL (139) | 0.917 | +0.250 | 0 |
k5/k10/all에서도 순위 동일(LOCATION > MEDICAL_HISTORY ≈ 제외 증상 ≈ 위험요인 > 나머지). **어느 한 범주도 단독으로 회복시키지 못하고** 합쳐야 0.917. 가장 큰 단일 기여는 통증 **부위 값**(evidence 4개, 환자당 5.6 토큰).
개별 판별력(`04`): TRAIN P(f|d) 표준편차·특이도 비율 상위는 부위 값 토큰(E_55_@_V_*), 과거력(E_123 COPD, E_116 감기), 병변 속성 값. "많이 등장"(Pain 80%)과 "판별"(상위 오답쌍 |log ratio|)을 분리해 기록.

## Q3. 구조화·표준 연결 시 외부 coverage/reachability (`07`, `09`, `10`, `11`, `12`)
- 확장 eligibility: **FULL 83 / PARTIAL 25 / STRUCTURED_ONLY 114 / UNUSABLE 1**. PARTIAL = base concept(CUI)은 있으나 HPO 없거나 위치·강도 속성이 붙은 증상(예: 부위 값 → base=Pain + location, SNOMED body structure 매핑 PENDING). STRUCTURED_ONLY = 과거력·가족력·약물·노출·생활·인구·시간(환자 기록엔 저장, 현재 disease-finding KB엔 관계 없음).
- 환자당 evaluable(외부 KB에 개념이 있는 노출 소견): k3 **1.19 → 1.68**, k5 1.51→2.32, k10 2.15→3.78 (`11`). 노출 usable 1.54→3.05.
- 질환 coverage(관련 evidence 중 strict 관계 존재): usable 대비 0.378→(PARTIAL 포함 분모 확대로) 하락, 전체 관련 evidence 대비 0.14→0.16. **외부 KB가 아는 질환 수 32 → 32 (변화 없음)**.
- reachable ceiling(VALIDATION 오답, k3): **22.7% → 24.9%** (+2.2p), k5 23.3→25.8, k10 26.3→29.1, all 11.5→11.5. unreachable의 주원인은 그대로 wd/truth가 외부 KB에 없음(k3: wd unknown 4,926 / truth unknown 6,568).
- 상위 오답쌍(`05`, `12`, VALIDATION k3 실측): ① Acute↔Chronic rhinosinusitis 1,320 — DDXPlus 정의 차이 evidence 2개(Fever, Immunization status), TRAIN log-ratio>1 토큰 10개 중 9개가 제외군(통증 강도 값 등) — 두 질환 모두 strict KB에 없음 ② Acute laryngitis↔Viral pharyngitis 1,229 — 차이 6개, 강한 토큰 19개 중 16개 제외군(Hoarseness E_212·감기 병력 E_116·부위 값) — 후두염 KB 없음 ③ Unstable↔Stable angina 1,043 — 차이 4개(Progressive E_13, Chest pain at rest E_14, Nausea, Hyperhidrosis), 확장 후 4개 구별 정보 표현 가능, **둘 다 strict KB 보유** → 새 구조로 원리적 구별 가능해진 유일한 상위 쌍 ④~⑩ NSTEMI/STEMI↔Stable angina, URTI↔Viral pharyngitis, Viral pharyngitis↔Acute otitis media, HIV↔Influenza, Influenza↔URTI, Bronchitis↔URTI — 구별 정보는 제외군(통증 성격·부위 값, 피부 병변 속성, COPD 병력)에 있으나 한쪽 질환이 KB에 없음.

## 사람 검토 (`08_manual_review_queue.csv`): 161개 (MANUAL_REQUIRED 104 · AUTO_REVIEW_REQUIRED 56 · UNMAPPABLE 1), AUTO_HIGH_CONFIDENCE 62. 우선: 복합 AND/OR·가족관계·시간조건·부위·값 범위·약물·위험요인. AI 의미표는 검색 보조이며 정답 아님.

## 판정 근거
- GO 요소: 제외 evidence의 S2 기여가 결정적(0.668→0.917), 그중 부위 값(+0.08)·과거력·제외 증상·위험요인은 base concept+attribute/context로 **구조화 가능**(FULL+PARTIAL 108, STRUCTURED 114), 환자당 usable 정보 2배.
- NO_GO 요소: 외부 KB 측 병목은 그대로 — 아는 질환 32/49 불변, reachability +2p, 상위 오답쌍 10개 중 9개가 한쪽 질환 미보유. 부위·강도·시간 속성에 대응하는 **질환 지식이 외부 자원에 없다**(HPO/HSDN 등은 "복통"까지만).
→ **PARTIAL_GO**: value/context 구조화는 제품(환자 기록·A′·추가질문)과 내부 verifier에는 가치가 크지만, 외부 verifier의 reachability 문제는 해결하지 못한다.

## 검증
evidence 223 ✔ · 83+140=223 ✔ · ID 중복 없음 ✔ · taxonomy 누락 0 ✔ · TEST 평가 0회·TEST 기반 매핑 변경 0 ✔ · TRAIN 통계/VALIDATION 분석 분리 ✔ · 복합 evidence concept_2 보존 ✔ · 값/시간/위치는 attribute 필드로 분리(단일 CUI 축약 없음) ✔ · 매핑 실패=unknown(negative 아님) ✔ · Step 8~13B 무수정 ✔ · NaN/inf 없음 ✔ · 행수·SHA256 PROVENANCE.md ✔
