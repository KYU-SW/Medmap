# STEP16B RESULT — NEXT INFORMATION ENGINE 검증 (2026-09-23)

## Validity
- split: TRAIN 1,025,602 → STEP16B_TRAIN 820,939 (80.04%) / STEP16B_HOLDOUT 204,663 (19.96%). key = sha256(row_index|AGE|SEX|PATHOLOGY|EVIDENCES), hex[:8]%10<2. split_key stream sha256 `da3bd6db…`
- preregistration SHA: MD `b9a28c58a730f72730598bb1fa5d2f953938a1c6a4e4f3b1404294d9214a5ab3` / RULES `f49dded9d307fa7a5af4689b902274cc2891c1ea47796013d92c913114dee3c5` (freeze 후 불변, 실행 시 재검증)
- original VALIDATION reads: 0 · TEST reads: 0 (코어 가드가 두 경로를 phase 무관 차단, read_log = release_evidences.json + release_train_patients 뿐)
- frozen changes: STEP16A 산출물 26개 SHA 전부 불변, 수정/삭제 0
- 공개 사항(deviation 기록): freeze 이후 본실행 전에 스모크 실행 1회(k3_s42, holdout 앞 1,000행 중 cohort 200명)를 수행해 지표를 미리 보았다. 규칙·제외질문·모집단·모델·임계는 이후 변경하지 않았고, 스모크 코호트는 본 SIM_COHORT의 부분집합이다. 산출물은 `_smoke_*`로 별도 보존.
- 구현 세부(사전등록 미고정): RANDOM draw의 환자별 난수는 (draw_seed, step) 1개 RNG에서 뽑은 균등난수 벡터로 배정.

## Data
- train N: 820,939 · holdout N: 204,663 · SIM_COHORT: 10,000명 (split key 오름차순 앞에서, 전 selector 공통)
- excluded questions: E_134, E_152 (view·pool 전부에서 제외)
- safe questions: 221 / 223 · 평균 SAFE_FULL_POOL 203.4 · 평균 SAFE_BINARY_POOL 201.1
- cohort 뷰: 초기 오답 47,386 / 초기 정답 42,614 (9 config = k3/5/10 × seed 42/43/44)

## Initial accuracy (HOLDOUT 전수 204,663 × 3 seed)
- k3: 0.4290 / 0.4289 / 0.4305 · k5: 0.4596 / 0.4595 / 0.4598 · k10: 0.5301 / 0.5304 / 0.5305 (pooled 0.4731)
- 참고: STEP16B_TRAIN train acc k3 0.4337 / k5 0.4643 / k10 0.5356

## RECOVERY@1Q (초기 오답 모집단 47,386 뷰 / 7,105 환자)
- RANDOM: 0.0529 · INTERNAL_IG: 0.4591
- IG − RANDOM: **+0.4062**, 95% CI [+0.3965, +0.4160] (환자 클러스터 bootstrap 1000, seed 42)

## RECOVERY@3Q
- RANDOM: 0.1249 · INTERNAL_IG: 0.8841 · IG − RANDOM +0.7592 [+0.7520, +0.7658]

## Correct→Wrong (초기 정답 42,614 뷰)
- RANDOM 1Q/3Q: 0.0309 / 0.0604
- INTERNAL_IG 1Q/3Q: 0.0255 / 0.0104

## Net accuracy change (cohort 전체, 초기 0.4735 대비)
- RANDOM: +0.0132 (1Q) / +0.0371 (3Q)
- INTERNAL_IG: +0.2296 (1Q) / +0.4605 (3Q)

## Binary-only sensitivity
- RANDOM: 0.0506 (1Q) / 0.1174 (3Q) · IG: 0.2477 (1Q) / 0.5704 (3Q)
- difference 1Q: **+0.1970** [+0.1893, +0.2043] · 3Q: +0.4529 [+0.4440, +0.4633] (방향 동일)

## Profile secondary (top1/top2가 pilot pair인 2,386 오답 뷰 / 922 환자)
- RECOVERY@1Q: 0.1345 (abstain 0.029) · RECOVERY@3Q: 0.2875 (abstain 0.386)
- Profile − RANDOM +0.0769 [+0.0527, +0.1028] · Profile − INTERNAL_IG −0.2171 [−0.2563, −0.1818] (참고용, 판정 기준 아님)

## Answer-semantics audit
- parent-positive missing value encountered: 0 (포함 질문에서 UNSAFE 상태 0회, IG 계수 단계 검사도 0)
- unsafe question access: 0 · repeated question: 0 · q1 pool identity violations: 0 · reveal calls 16,751,103
- hidden answer before selection: 0 (reveal은 chosen 확정 후에만 호출, 카운터 파일 저장)

## Verdict
**NEXT_INFORMATION_ENGINE_GO**
(IG > RANDOM ∧ paired 95% CI 하한 +0.3965 > 0 ∧ binary-only 방향 동일(+0.1970) ∧ IG 순 정확도 변화 +0.2296 ≥ 0)

## Conclusion
- 질문–답 의미를 안전한 V2 규칙(default 생성 금지, E_134/E_152 제외)으로 고치고 기존 VALIDATION을 전혀 열지 않은 새 20% holdout에서도, 내부 정보이득 기반 다음 정보 선택은 무작위 질문 선택보다 초기 오진을 크게 더 회복시켰다(1문항 0.459 vs 0.053).
- 효과는 categorical/multi 질문을 전부 제거한 binary-only 조건에서도 같은 방향으로 유지되어(+0.197), STEP16A에서 문제가 된 답변 의미 결함이 이 결론을 만든 원인이 아니다.
- IG는 회복을 늘리면서 초기 정답을 망치는 비율은 오히려 낮췄다(3문항 0.010 vs RANDOM 0.060) — 질문을 더 해도 손해가 누적되지 않는다.
- 외부 질환 프로필 기반 선택은 pilot pair 부분집합에서 RANDOM보다는 낫지만 IG보다 −0.217로 여전히 명확히 약하며, STEP16A의 `STOP_PROFILE_QUESTION_ENGINE` 판정을 뒤집을 근거는 없다.
- 한계: 이 결과는 DDXPlus 내부 통계로 만든 IG 테이블과 같은 시뮬레이터 위에서 얻은 것으로, 외부 임상 데이터 전이나 실제 문진 비용은 검증하지 않았다. TEST는 계속 봉인 상태다.
