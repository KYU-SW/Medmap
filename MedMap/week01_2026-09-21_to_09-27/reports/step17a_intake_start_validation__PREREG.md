# STEP17A — INTAKE START-STATE VALIDATION 사전등록 (2026-09-24)

작성 시점: 코드 실행 전. 이 문서는 split 생성 전에 SHA로 고정한다(`FREEZE.json` stage 1).

## 1. 연구 질문
STEP16B와 **같은 k3 학습 레시피**로 만든 모델에 Natural Intake 방식으로 구성한 시작 상태(R1~R3)를 넣어도, 무작위 시작 상태(R0) 대비 초기 진단 성능과 이후 IG 질문의 회복 이득이 유지되는가.

- PRIMARY: 새 dev에서 재학습한 recipe 모델 + 새 holdout. "현재 제품 MODEL_k3 자체"의 외부 검증이 아니라 **레시피의 일반화** 검증.
- SECONDARY: 제품 `model_k3.pkl` + STEP16B IG table로 같은 holdout 행을 평가. 이 행들은 제품 모델 학습에 쓰였으므로 **IN_SAMPLE_DESCRIPTIVE**. 판정에 쓰지 않는다.

## 2. 데이터와 가드
- 읽기: `release_train_patients`, `release_evidences.json`, STEP16B `01_split_manifest.json`·`model_k3.pkl`·`ig_table_step16b_train.npz`(secondary 전용).
- 금지(코어 가드 재사용, 위반 시 예외): 원본 `release_validate_patients`, `release_test_patients`, `release_conditions.json`.
- **STEP16B_HOLDOUT(204,663행)**: STEP16B 규칙(`sha256(row_index|AGE|SEX|PATHOLOGY|EVIDENCES)`, `int(hex[:8],16)%10<2`)으로 **소속만 계산하고 즉시 제거**. 제거 행 수 204,663과 `holdout_row_index_sha256` 일치를 assert. 이 행의 토큰·라벨은 어떤 계산에도 쓰지 않는다(reads = 0으로 기록, 정의: 소속 판정 외 사용 0).
- 선행 사실(STEP17A 이전, 제품 coverage 감사): 원본 TRAIN 전체의 INITIAL_EVIDENCE 열만 집계해 unique 96, 한국어 27개 coverage 0.7121을 얻었다. STEP17A 안의 coverage 재현은 **dev만**으로 한다.

## 3. Split (STEP16B_TRAIN 820,939행 내부)
- `key17 = sha256("step17a|" + split_key16).hexdigest()`
- `int(key17[:8],16) % 5 == 0` → **STEP17A_HOLDOUT**(≈20%), 그 외 → **STEP17A_DEV**
- manifest: 행 수, row_index 목록 SHA, key17 스트림 SHA. 생성 직후 `FREEZE.json`에 기록.
- holdout은 prepare·smoke에서 소속 판정 외 사용 금지. 최종 평가(`s17a_run.py --mode primary`)에서 처음 사용.

## 4. Recipe (STEP16B와 동일, dev만 사용)
- classes = dev PATHOLOGY 고유값 정렬(STEP16B classes 49개와 동일해야 함, assert).
- IG table: `s16b_core.fit_ig_table(sem, dev tokens, dev labels, classes, alpha=1.0)`.
- MODEL_k3: 각 dev 행에 `make_view(k=3, split="step17a_dev", seed=42, idx=row_index)` → `Encoder` → `LogisticRegression(C=1.0, solver=lbfgs, max_iter=300, random_state=42)`.
- 제외 질문 E_134·E_152, 답 의미 V2(default 생성 금지) 그대로.
- SPLIT_ID 추가(파일 수정 없이 런타임 등록): step17a_dev=21, step17a_holdout=22, step17a_smoke=93.

## 5. 시작 상태 조건 (모두 initial = 데이터의 INITIAL_EVIDENCE, 답은 실제 기록에서 복원)
seed S ∈ {42, 43, 44}. 조건별 RNG = `default_rng([SPLIT_ID, seed, row_index, cond_code])`, R0은 `make_view` 원래 RNG.

- **R0 TRAIN-LIKE RANDOM** — `make_view(k=3)` 그대로.
- **R1 POSITIVE-HEAVY**(cond 101)
  - POS pool = 환자 기록의 binary 증거 중 safe이고 initial이 아닌 것. binary child는 없음(확인 완료).
  - qnum 오름차순 정렬 뒤 RNG permutation, 앞에서 최대 3개를 공개(모두 POSITIVE).
  - 3개 미만이면 부족분은 R0 선택 규칙으로 채움: 같은 RNG로, 현재 적격 pool(top-level safe 미공개 + 공개된 POS 부모의 safe child)에서 순차 균등 추출.
- **R2 FIXED-BOOTSTRAP**
  - 순서 `E_91 → E_53 → E_66`, 예비 `E_201 → E_175 → E_88`.
  - initial이거나 이미 공개된 항목은 건너뛰고 앞에서부터 3개를 공개(실제 답).
  - 3개를 못 채우면 `INVALID_START`로 해당 조건에서 제외하고 개수 보고(구조상 0 예상).
- **R3 HYBRID**(cond 103)
  - pool = 환자 기록의 binary POSITIVE ∩ **MAPPER_SUPPORTED_41** − initial.
  - R1과 같은 정렬·permutation으로 최대 3개, 부족분만 R2 순서로 채움(공개 항목 건너뜀). 못 채우면 `INVALID_START`.
- **R3-MASK**(cond 113, 보조, gate 아님)
  - R3 pool의 각 항목을 `u < 0.6834`일 때만 유지(blind v3 POSITIVE recall, 증상별 recall은 모른다고 가정). 이후는 R3와 같음.
  - 실제 발화 분포라는 주장 금지.

MAPPER_SUPPORTED_41(매퍼 v1.2 freeze 2372e2f):
`E_0 E_9 E_33 E_45 E_50 E_53 E_66 E_69 E_70 E_77 E_78 E_79 E_88 E_89 E_91 E_104 E_105 E_112 E_116 E_120 E_123 E_124 E_129 E_148 E_151 E_155 E_169 E_175 E_181 E_182 E_189 E_194 E_201 E_209 E_212 E_214 E_216 E_218 E_220 E_221 E_226`

KO27(한국어 initial 가능, product-coverage sensitivity 전용) = MAPPER_SUPPORTED_41 − {E_0, E_69, E_70, E_78, E_79, E_104, E_105, E_116, E_120, E_123, E_124, E_189, E_209, E_226}

## 6. Cohort
- **HO_ALL**: STEP17A_HOLDOUT 전 행(TRAIN의 initial은 전부 binary, 모두 유효). 초기 지표·gate A·D1.
- **HO_KO27**: HO_ALL 중 INITIAL_EVIDENCE ∈ KO27. 보조 보고만.
- **SIM**: HO_ALL을 key17 오름차순으로 정렬한 앞 10,000명. IG 시뮬레이션·gate B·C.

## 7. 지표
- 초기(조건×seed 뷰, 환자별 seed 평균):
  - top1 accuracy, top3 accuracy
  - log loss = mean(−ln max(p_truth, 1e−15))
  - truth rank 평균·중앙값
- 비교: R3−R0(primary). R1−R0, R2−R0, R3MASK−R0는 보조.
- 시작 이후(SIM, 조건별): STEP16B와 동일한 selector
  - `RANDOM`: 50 draw, seeds 1000–1049, 뷰별 draw 평균
  - `INTERNAL_IG`: argmax IG, 동점은 `round(ig,12)`에서 pool 첫 항목
  - pool = SAFE_FULL_POOL(미질문 ∧ 적격 ∧ 제외 질문 아님)
  - 3문항 순차, 선택 확정 후에만 답 공개, 모델 재학습 없음
- 산출: Recovery@1Q·@3Q(초기 오답 뷰), Correct→Wrong@1Q·@3Q(초기 정답 뷰)
- Bootstrap: 환자 cluster, 1000회, seed 42, 벡터화(np.unique + bincount). paired(같은 환자·뷰). 95% percentile CI.

## 8. Gate (primary만, 결과를 본 뒤 변경 금지)
- **A START-STATE NON-INFERIORITY**: HO_ALL에서 R3 − R0 top3 accuracy 차이의 95% CI 하한 > −0.05
- **B IG BENEFIT RETAINED**: SIM·R3 초기 오답 뷰에서 IG − RANDOM Recovery@1Q의 95% CI 하한 > +0.10
- **C CORRECT CASE SAFETY**: SIM·R3 초기 정답 뷰에서 IG − RANDOM Correct→Wrong@3Q의 95% CI 상한 ≤ 0
- **D1 START COMPLETION**: HO_ALL에서 R3로 exact-k(추가 정확히 3개)를 완성한 뷰 비율 ≥ 0.95
- D2 한국어 coverage: 보고만, gate 아님.
- 판정:
  - A ∧ B ∧ C ∧ D1 → **NATURAL_INTAKE_K3_GO**
  - 하나라도 FAIL → **NATURAL_INTAKE_K3_NO_GO**
  - secondary 결과는 판정을 뒤집지 못함.

## 9. Fixed bootstrap 감사(dev만, gate 아님, 순서 변경 금지)
E_91·E_53·E_66(+예비 3개)에 대해 다음을 보고한다.
- dev 답 분포(POS/NEG. binary라 VALUE·NA 해당 없음, missing 0 확인)
- initial과 같은 비율
- parent/gate 여부
- 질환 판별력: 상호정보량 I(answer; disease) bits, dev 경험 prior 사용
- P(POS|d) 상위 5개 질환

## 10. Coverage 감사(dev만, gate 아님)
- dev INITIAL_EVIDENCE: unique 수, KO27 coverage
- 빈도순으로 한국어 미지원 initial을 추가할 때 80/90/95/99% 도달에 필요한 추가 개수와 ID·빈도

## 11. Smoke
- dev 부분집합 200명(dev를 key17 내림차순으로 정렬한 앞 200명).
- 제품 model_k3 + STEP16B IG table로 평가 함수 전체를 실행(조건 5개 × seed 3 × selector 51).
- 목적은 코드 동작·시간·RAM 확인뿐. 산출물은 `_smoke_` 접두사, 지표 해석 금지.
- **holdout 미사용.**

## 12. Freeze 절차
1. stage 1(split 생성 전): PREREG.md SHA → `FREEZE.json`
2. prepare 후: split manifest SHA를 `FREEZE.json`에 추가(holdout 미사용)
3. smoke 통과 후, recipe 모델·IG table 생성 뒤 stage 2 `FREEZE_ARTIFACTS.json`
   - 모델·IG table·manifest·코드 전체 SHA
   - FREEZE.json SHA
4. `s17a_run.py`는 두 파일의 SHA를 모두 검증한 뒤에만 holdout을 연다.

smoke에서 코드 버그를 고치면 stage 2 전까지는 허용하되, `AMENDMENTS.md`에 기록한다(규칙·gate·cohort 변경은 불가).

## 13. Invalid 조건
다음 중 하나라도 해당하면 결과를 invalid로 보존하고 새 사전등록으로 넘어간다.
- 원본 VALIDATION·TEST·conditions 접근
- STEP16B_HOLDOUT 행의 토큰·라벨 사용
- STEP17A_HOLDOUT을 학습·IG·smoke에 사용
- freeze SHA 불일치
- UNSAFE 답 상태 발생
- 선택 전 hidden answer 접근
- 결과를 본 뒤 규칙·gate·cohort·fallback 변경
