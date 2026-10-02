# STEP16B 사전등록 — NEXT INFORMATION ENGINE 검증 (작성 2026-09-23, 성능 확인 전)

## 0. 위치·승인
- 디렉터리: `exp/step16b_next_information_validation/` (STEP16A 파일 수정·삭제 금지)
- 승인: 사용자 지시(2026-09-23) §19 A~F. 기존 DDXPlus `release_validate_patients`·`release_test_patients` 접근 영구 금지 — 코드 가드 `STEP16B_INVALID_SPLIT_ACCESS`가 두 경로를 차단한다(phase 무관).
- STEP16A 보존 판정: `VALID_UNDER_PREREG_V1` BUT `ANSWER_SEMANTICS_SENSITIVITY_UNRESOLVED`.

## 1. 연구 질문
Primary: 수정된 안전한 질문–답 규칙에서, 내부 정보이득(INTERNAL_IG) 기반 다음 정보 선택이 무작위 질문 선택(RANDOM)보다 초기 오진을 더 많이 회복시키는가.
- 외부 질환 프로필의 우월성 검증이 아니다. PROFILE_FACT_ONLY는 참고용 Secondary이며 성공/실패 판정에 쓰지 않는다.

## 2. 데이터와 분할 (성능 확인 전 고정)
- 원천: `data/ddxplus/en/release_train_patients` (1,025,602행) **만** 사용.
- 행 식별자: 0-based 행 번호 + 내용. split key = `sha256(f"{row_index}|{AGE}|{SEX}|{PATHOLOGY}|{EVIDENCES}")`.
- 배정: `int(hexdigest[:8], 16) % 10 < 2` → **STEP16B_HOLDOUT(20%)**, 그 외 → **STEP16B_TRAIN(80%)**.
- HOLDOUT은 분리 직후 잠금: 모델 학습·IG 통계·규칙 결정에 일절 사용하지 않는다. 1회 평가만.
- 원본 파일 SHA256을 `00_input_integrity.json`에 기록한다.

## 3. 질문–답 의미 (V2, STEP16A V1 수정)
- Binary: 토큰 존재 → POSITIVE, 부재 → NEGATIVE (closed-world; TRAIN 전수 감사 malformed 0).
- 부모 있는 categorical/multi:
  - parent UNASKED → 질문 불가(후보 아님)
  - parent NEGATIVE → 질문 불가 / N/A
  - parent POSITIVE + explicit child value token → 해당 value
  - parent POSITIVE + child token 없음 → **default 생성 금지**, `UNSAFE` 상태. 인코더·IG에서 예외로 즉시 실패(조용한 통과 금지).
- 부모 없는 categorical/multi(E_204): token 없음 → `UNSAFE`(TRAIN 전수 absent 0건).
- 정의 파일의 parent-child는 실행 시 재도출한다(하드코딩 대조): E_53→E_54~59, E_129→E_130~136, E_151→E_152 (14쌍, 전부 C/M).

## 4. 제외 질문 (결과 확인 후 재투입 금지)
TRAIN 전수 감사(2026-09-23, VALIDATION/TEST 미접근)에서 parent-positive + child-missing이 관측된 질문:
- `E_134` 11,538건 / `E_152` 150건
→ Primary·Secondary 전부에서 **후보 pool과 partial-view 샘플링에서 완전 제외**. 나머지 12개 gated child는 missing 0건이며 visible parent == POSITIVE일 때만 후보가 된다(hidden parent answer 사용 금지).

## 5. Partial view 프로토콜
- k ∈ {3, 5, 10}. INITIAL_EVIDENCE(항상 binary POS) 먼저 공개, 이후 k회 순차 균등 샘플.
- 초기 evidence는 추가 k개 샘플 후보에서 제외. 질문 중복 0. 제외 질문 2개는 후보에서 제거.
- 부모 조건 child는 부모가 POSITIVE로 공개된 뒤에만 후보에 추가된다(visible state만 사용).
- RNG key = (SPLIT_ID, seed, row_index), SPLIT_ID = {step16b_train: 11, step16b_holdout: 12}. TRAIN 뷰 seed 42, HOLDOUT 뷰 seeds 42/43/44.

## 6. 진단 모델 (STEP16A 모델 재사용 금지)
- LogisticRegression(C=1.0, solver=lbfgs, max_iter=300, random_state=42), 클래스 = PATHOLOGY.
- `MODEL_k3/k5/k10` 각각 STEP16B_TRAIN 80%의 해당 k 뷰로만 학습. 평가 성능을 본 뒤 하이퍼파라미터 변경 금지. 질문 추가 후에도 같은 모델 재사용(재학습 금지).
- 인코딩: `Q::<e>::POS/NEG`, `Q::<e>::VALUE::<v>`, `Q::<e>::NA`, `AGE_<decade>`, `SEX_<M/F>`. UNASKED = 열 없음.

## 7. Internal IG 통계
- P(a|d) = (count(d,a)+α)/(Σ_a count(d,a)+α|A_q|), α = 1.0, log base 2. **STEP16B_TRAIN 80% 전수 record에서만** 계산(HOLDOUT 사용 금지).
- 상태 계수는 §3 규칙과 동일: binary POS/NEG, C/M은 값 토큰, 부모 음성이고 토큰 없음 → NA. gated child의 NA = n_d − (토큰 있는 환자) − (parent-positive missing). 포함 질문의 parent-positive missing은 0이어야 하며 0이 아니면 `STEP16B_INVALID_ANSWER_SEMANTICS`로 중단(STEP16A의 `NA = n_d − parent_pos` 계수 방식은 부모 음성+토큰 존재 케이스를 이중계수하므로 여기서 수정).
- IG(q) = H(post) − Σ_a P(a)·H(post_a), post_a ∝ post·P(a|d). 동점 → evidence 번호 오름차순.

## 8. 후보 pool
- `SAFE_FULL_POOL` = 미질문 ∧ 현재 visible state에서 질문 가능(부모 POS) ∧ E_134/E_152 아님.
- `SAFE_BINARY_POOL` = SAFE_FULL_POOL ∩ data_type == "B" (Secondary 민감도).
- 질환별 symptom 목록(`release_conditions.json`)으로 후보를 제한하지 않는다(파일 자체 차단).
- RANDOM과 INTERNAL_IG는 같은 patient/view/step에서 **동일한 pool 객체**를 받는다(코드 동일 경로, step1 pool 동일성 assert).

## 9. 평가 코호트
- 초기 정확도·truth rank 등 기술통계: HOLDOUT 전수.
- 시뮬레이션(질문 선택·재예측): 계산량 상한 때문에 **SIM_COHORT = HOLDOUT을 split key hex 오름차순 정렬해 앞에서 10,000명**(모든 selector·모든 config 동일 집합, 성능 확인 전 고정). 초기 오답/정답 모두 시뮬레이션한다.
- 모집단: `primary_wrong` = SIM_COHORT ∩ 초기 top1 ≠ truth ∩ SAFE_FULL_POOL 비어있지 않음. `harm` = 동일 조건 ∩ 초기 top1 == truth.

## 10. Selector
Primary: `RANDOM`(50 draw, seeds 1000~1049, 환자×뷰 평균 후 paired), `INTERNAL_IG`(argmax IG).
Secondary: `PROFILE_FACT_ONLY`(STEP16A `04b_pair_contrast_table_primary.csv` 규칙 재사용, SAFE_FULL_POOL 위에서 priority 최대·동점 evidence 번호, priority>0 없으면 ABSTAIN; top1/top2가 pilot pair인 사례에 한해 집계), `BINARY_ONLY_RANDOM`(10 draw, seeds 1000~1009), `BINARY_ONLY_IG`.
- selector 입력은 (visible, posterior, top, pool, seed)뿐. truth·hidden token 키 금지(assert).
- reveal은 선택이 확정된 뒤에만 호출(카운터를 `10_*.json`에 **저장**한다 — STEP16A 카운터 유실 재발 방지).

## 11. 엔드포인트
- Primary: `RECOVERY@1Q` = 질문 1개 후 top1 == truth 비율(초기 오답 모집단), 비교 = `INTERNAL_IG − RANDOM`, 동일 환자/뷰 paired.
- Secondary: `RECOVERY@3Q`(순차 3문항), `CORRECT_TO_WRONG@1Q/@3Q`(초기 정답 모집단), 초기/질문 후 정확도, truth rank 평균·중앙값, top3 포함률, 순이익(net accuracy change), abstain율, 평균 질문 수, binary-only 민감도, profile 참고값.
- Bootstrap: 1000회, seed 42, **환자 단위 cluster**(같은 환자의 k3/k5/k10·seed 42/43/44 뷰는 한 묶음), 벡터화 구현(np.unique + bincount). 보고: IG−RANDOM, BINARY_IG−BINARY_RANDOM.

## 12. 성공 판정 (사전 고정, 새 임계값 신설 금지)
- `NEXT_INFORMATION_ENGINE_GO`: IG RECOVERY@1Q > RANDOM RECOVERY@1Q ∧ paired 95% CI 하한 > 0 ∧ binary-only에서도 차이 방향 동일(점추정 > 0) ∧ IG의 순 정확도 변화 ≥ 0.
- `NEXT_INFORMATION_ENGINE_PARTIAL_GO`: CI 하한 > 0 이지만 binary-only 방향이 유지되지 않거나 IG 순 정확도 변화 < 0.
- `NEXT_INFORMATION_ENGINE_NO_GO`: CI가 0을 포함하거나 IG ≤ RANDOM.
- `INVALID`: 아래 무효 조건 중 하나라도 해당.

## 13. 무효(INVALID) 조건
원본 VALIDATION/TEST 접근 1회 이상 · HOLDOUT이 학습/IG/규칙 결정에 사용됨 · 사전등록 SHA 불일치 또는 실행 후 수정 · `UNSAFE` 상태가 포함 질문에서 1회 이상 발생 · 선택 전 hidden answer 접근 · RANDOM과 IG의 step1 pool 불일치 · 중복 질문 발생 · 결과를 본 뒤 규칙/제외질문/모집단 변경.

## 14. 산출물
`00_*`(사전등록·SHA·입력 무결성) · `01_split_manifest.json` · `02_holdout_initial_predictions.csv` · `03_case_eligibility.csv` · `05_question1_results.csv` · `06_question3_results.csv` · `07_selector_metrics.csv` · `08_paired_bootstrap.csv` · `10_audit.json` · `11_error_case_examples.csv` · `12_summary.json` · `PROVENANCE.md` · `STEP16B_REPORT.md`.
