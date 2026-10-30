# STEP27 — MedMap Safe Symptom Routing v2

- STEP27_RESULT = **PARTIAL_IMPROVEMENT** (G_N 제외 시 ROUTING_IMPROVED) · BEST_POLICY = **POLICY_D** · PRODUCTION_READY = **NO** · CANONICAL_ACCURACY_VALIDATED = NO · EXTERNAL_GOLD_AVAILABLE = NO · GPU_USED = NO
- 파라미터(DEV 선택): `{"B": {"t_strong": 0.85, "t_type": 0.7}, "D": {"d_conf": 0.5, "d_sim": 0.1}, "E": {"a": 0.0, "b": 0.95, "s": 0.6, "c": 0.3}}`
- 지표 성격: EXT = 외부 NER 범주 weak-label proxy(MedMap concept 정답 아님). Regression = 합성 FIXED_REGRESSION_TEST 109(blind 아님). EXT_EVAL 은 STEP25·26 에서 이미 예측을 본 데이터 → frozen retrospective evaluation. 임상 안전성 검증 아님.
- 기존 결과 재현: B4 8104행 불일치 0 · STEP26 상태 불일치 0 · label map 일치 · Linear 점수 재계산 차 0.0. POLICY_A 보고 집합 상태 = STEP26 predictions.csv 와 100% 일치(assert).

## 1. 판정 요약

| 항목 | 값 |
|---|---|
| FALSE_NON_RATE (EVAL weak-symptom → NON, n=248) | 0.0% (POLICY_A 10.5%) |
| WEAK_NEGATIVE_AUTO_ACCEPT_RATE (n=903) | 0.5% |
| SUPPORTED_AUTO_COVERAGE (regression) | 37.6% |
| REGRESSION_AUTO_PRECISION | 100.0% |
| UNKNOWN_RATE (EXT_EVAL 전체) | 13.3% |
| CPU p50 / p95 | 18.026 ms / 24.799 ms |
| 메모리(peak RSS) | 804.8 MiB (모델 적재 후 725.9 MiB) |

Gate: G_A PASS · G_B PASS · G_C PASS · G_D PASS · G_E PASS · G_F PASS · G_U PASS · G_N FAIL. 규칙은 `scripts/build_report.py` 문서열(G_N 은 EVAL 수치를 본 뒤 추가한 보수 조항 — 공개).

## 2. 정책 비교 — 보고 집합(EXT_EVAL · Regression · KMC, 선택에 미사용)

| 지표 | POLICY_A | POLICY_B | POLICY_C | POLICY_D | POLICY_E |
|---|---|---|---|---|---|
| Weak-symptom → NON (false NON) | 10.5% | 0.0% | 0.0% | 0.0% | 0.0% |
| Weak-symptom → UNKNOWN | 17.3% | 17.3% | 34.7% | 36.7% | 36.7% |
| Weak-symptom → UNCERTAIN | 54.8% | 65.3% | 47.6% | 45.6% | 43.5% |
| Weak-symptom → KNOWN 자동 수락 | 17.3% | 17.3% | 17.3% | 17.3% | 19.4% |
| Weak-non → KNOWN 자동 수락 | 0.5% | 0.5% | 0.5% | 0.5% | 1.0% |
| Weak-non → NON | 53.6% | 14.5% | 14.5% | 14.5% | 14.5% |
| Weak-non → UNKNOWN | 1.2% | 1.2% | 5.1% | 5.3% | 5.3% |
| Weak-non → UNCERTAIN | 44.6% | 83.7% | 79.7% | 79.5% | 79.1% |
| Weak-non 후보 표시율 | 3.9% | 9.9% | 9.9% | 4.9% | 4.4% |
| Weak-symptom 후보 표시율 | 17.3% | 19.8% | 19.8% | 16.5% | 14.5% |
| 후보 억제율(A 가 표시한 행 중) | 0.0% | 0.0% | 0.0% | 43.7% | 43.2% |
| 모델 불일치 자동 수락 수 | 0 | 0 | 0 | 0 | 0 |
| EXT UNKNOWN 비율 | 8.2% | 8.2% | 12.5% | 13.3% | 13.3% |
| EXT UNCERTAIN 비율 | 45.5% | 78.3% | 73.1% | 72.4% | 71.9% |
| Regression 자동 수락 precision | 100.0% | 100.0% | 100.0% | 100.0% | 98.0% |
| Regression 자동 수락 coverage | 37.6% | 37.6% | 37.6% | 37.6% | 46.8% |
| Regression 비자동 중 gold 표시 | 32 | 32 | 32 | 29 | 20 |
| Regression 비자동 중 gold 없는 표시 | 2 | 2 | 2 | 4 | 3 |
| Regression COMPLEX_INPUT 비율 | 0.0% | 0.0% | 14.7% | 14.7% | 14.7% |
| KMC 복합문 COMPLEX_INPUT 비율 | 0.0% | 0.0% | 97.3% | 97.3% | 97.3% |
| KMC 복합문 자동 수락 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

## 3. 정책 비교 — DEV(선택에 사용, EXT_DEV 비증상 점수는 out-of-fold)

| 지표 | POLICY_A | POLICY_B | POLICY_C | POLICY_D | POLICY_E |
|---|---|---|---|---|---|
| Weak-symptom → NON (false NON) | 12.8% | 1.7% | 1.7% | 1.7% | 1.7% |
| Weak-symptom → UNKNOWN | 26.8% | 26.8% | 36.3% | 38.6% | 38.6% |
| Weak-symptom → UNCERTAIN | 54.8% | 65.9% | 56.4% | 54.2% | 52.0% |
| Weak-symptom → KNOWN 자동 수락 | 5.6% | 5.6% | 5.6% | 5.6% | 7.8% |
| Weak-non → KNOWN 자동 수락 | 0.1% | 0.1% | 0.1% | 0.1% | 0.4% |
| Weak-non → NON | 51.3% | 14.3% | 14.3% | 14.3% | 14.3% |
| Weak-non → UNKNOWN | 3.4% | 3.4% | 6.3% | 6.9% | 6.9% |
| Weak-non → UNCERTAIN | 45.2% | 82.2% | 78.9% | 78.4% | 78.1% |
| Weak-non 후보 표시율 | 5.3% | 10.1% | 10.1% | 6.6% | 6.2% |
| Weak-symptom 후보 표시율 | 16.8% | 18.4% | 18.4% | 16.2% | 14.0% |
| 후보 억제율(A 가 표시한 행 중) | 0.0% | 0.0% | 0.0% | 38.3% | 38.3% |
| 모델 불일치 자동 수락 수 | 0 | 0 | 0 | 0 | 0 |
| core dev 자동 precision | 0.9667 | 0.9667 | 0.9667 | 0.9667 | 0.9688 |
| core dev 자동 coverage | 0.5085 | 0.5085 | 0.5085 | 0.5085 | 0.5424 |
| core dev 비자동 중 gold 표시 | 13 | 13 | 13 | 13 | 11 |

DEV gate(BEST 선택 규칙, `evaluate_routing.py` 문서열):

| policy | DEV gate | 실패 항목 |
|---|---|---|
| POLICY_A | FAIL | WS_to_NON<=0.03 |
| POLICY_B | PASS | — |
| POLICY_C | PASS | — |
| POLICY_D | PASS | — |
| POLICY_E | PASS | — |

POLICY_E(B4 임계 변경, 탐색): fold 별 선택 CV core coverage 50.8% · precision 96.7% · WN auto 0.2% vs B4(DEV) coverage 50.8% → 채택 = False. 표의 POLICY_E 열은 보고용(BEST 후보 아님).

## 4. UNKNOWN ↔ NON 분리 (EXT_EVAL, weak label 대비)

| policy | UNKNOWN·WS | UNKNOWN·WN | UNKNOWN 중 WS 비율 | NON·WS | NON·WN | NON 중 WN 비율 |
|---|---|---|---|---|---|---|
| POLICY_A | 43 | 11 | 79.6% | 26 | 484 | 94.9% |
| POLICY_B | 43 | 11 | 79.6% | 0 | 131 | 100.0% |
| POLICY_C | 86 | 46 | 65.1% | 0 | 131 | 100.0% |
| POLICY_D | 91 | 48 | 65.5% | 0 | 131 | 100.0% |
| POLICY_E | 91 | 48 | 65.5% | 0 | 131 | 100.0% |

## 5. 후보 표시 (부적절 표시 proxy: weak-non 에 표시 · 최대 후보 유사도 < 0.2 · INT 에서 gold 미포함)

| set | A 표시 행 | A 중 proxy 해당 | A 표시 행 중 BEST 표시 | BEST proxy 해당 | BEST 가 새로 표시한 행(B 의 NON 완화 결과) | 그중 proxy 해당 |
|---|---|---|---|---|---|---|
| EXT_DEV | 209 | 138 | 129 | 74 | 60 | 49 |
| EXT_EVAL | 190 | 122 | 107 | 50 | 53 | 45 |
| INT_DEV_CORE | 14 | 6 | 14 | 8 | 0 | 0 |
| INT_REGRESSION_CORE | 34 | 11 | 33 | 10 | 0 | 0 |
| KMC_COMPLEX_STRESS | 18 | 15 | 12 | 9 | 0 | 0 |

## 6. 원문 보존 검사(BEST, 전 8104행)

source_text 손실 0 · raw_expression 누락 0 · UNKNOWN 인데 canonical 있음 0 · UNKNOWN 인데 후보 표시 0 · NON 인데 canonical/후보 0 · COMPLEX 자동 수락 0. 상태 분포 {"UNCERTAIN": 4621, "UNKNOWN_SYMPTOM": 899, "NON_SYMPTOM": 704, "KNOWN_SYMPTOM": 173, "COMPLEX_INPUT": 1707}.

## 7. 대표 사례(탐색적 — 이 세션은 STEP26 §4 우선 사례를 본 뒤 어휘 단서를 작성, 지표·임계값에 미사용)

데이터 안(표현 포함 행, A → BEST 상태 분포):

| 표현 | 행 | POLICY_A | POLICY_D |
|---|---|---|---|
| 결핵 | 33 | UNCERTAIN 22; NON_SYMPTOM 11 | UNCERTAIN 16; COMPLEX_INPUT 16; NON_SYMPTOM 1 |
| 고혈압 | 46 | UNCERTAIN 33; NON_SYMPTOM 13 | COMPLEX_INPUT 29; UNCERTAIN 13; NON_SYMPTOM 4 |
| 기침이 | 50 | UNCERTAIN 44; KNOWN_SYMPTOM 4; UNKNOWN_SYMPTOM 2 | COMPLEX_INPUT 44; KNOWN_SYMPTOM 4; UNKNOWN_SYMPTOM 2 |
| 숨이차 | 27 | UNCERTAIN 25; KNOWN_SYMPTOM 2 | COMPLEX_INPUT 24; KNOWN_SYMPTOM 2; UNCERTAIN 1 |
| 열이나 | 26 | UNCERTAIN 25; KNOWN_SYMPTOM 1 | COMPLEX_INPUT 25; KNOWN_SYMPTOM 1 |
| 코피 | 8 | UNCERTAIN 7; UNKNOWN_SYMPTOM 1 | UNCERTAIN 4; COMPLEX_INPUT 3; UNKNOWN_SYMPTOM 1 |
| 토했 | 4 | KNOWN_SYMPTOM 2; UNCERTAIN 1; UNKNOWN_SYMPTOM 1 | KNOWN_SYMPTOM 2; UNCERTAIN 1; UNKNOWN_SYMPTOM 1 |

데이터 밖 smoke:

| 입력 | status | decision | 표시 후보 | reason |
|---|---|---|---|---|
| 고혈압 | UNCERTAIN | ASK_CONFIRMATION | — | MODEL_DISAGREE_TYPE_UNCLEAR;MODEL_DISAGREEMENT |
| 결핵 | UNCERTAIN | ASK_CONFIRMATION | — | MODEL_DISAGREE_TYPE_UNCLEAR;MODEL_DISAGREEMENT |
| 코피가 나요 | UNCERTAIN | ASK_CONFIRMATION | hemoptysis | AGREE_BELOW_AUTO_THRESHOLD;CANDIDATE_SUPPRESSED:2 |
| 숨이 차요 | KNOWN_SYMPTOM | AUTO_ACCEPT | dyspnea | AUTO_RULE:B4 |
| 기침이 나요 | KNOWN_SYMPTOM | AUTO_ACCEPT | cough | AUTO_RULE:B4 |
| 토했어요 | KNOWN_SYMPTOM | AUTO_ACCEPT | vomiting | AUTO_RULE:B4 |
| 열이 나요 | KNOWN_SYMPTOM | AUTO_ACCEPT | fever | AUTO_RULE:B4 |

## 8. SILVER_CANDIDATE 442 (`data/external_silver_candidates.csv`, 사람 검증 아님)

n 442 · 분할 {"EXT_EVAL": 248, "EXT_DEV": 179, "NOT_IN_STEP26_UNITS(train-exact/conflict 제외 단위 → live 계산)": 15} · STEP27 상태 {"KNOWN_SYMPTOM": 54, "UNKNOWN_SYMPTOM": 163, "UNCERTAIN": 221, "NON_SYMPTOM": 3, "COMPLEX_INPUT": 1}. STEP28 기계 분류 {"ONTOLOGY_SEARCH_CANDIDATE": 211, "SYNONYM_GAP_CANDIDATE": 14, "TYPE_UNCLEAR_REVIEW": 163}(`outputs/step28_candidates.csv`).

## 9. 누수·노출

- 선택: EXT_DEV + INT_DEV_CORE 59 만. EXT_EVAL·Regression 109·KMC 는 1회 적용. EXT_DEV 비증상 점수는 STEP26 재료·fold 로 다시 만든 out-of-fold 값(STEP26 full 분류기는 EXT_DEV in-sample).
- 어휘 단서(NON_TYPE_CUE·SYMPTOM_CUE)는 일반 형태 규칙으로 작성, 개별 사례 표현(고혈압·결핵·코피) 미포함. 다만 STEP26 §4 우선 사례 16 표현을 본 상태에서 작성 → 해당 표현 결과는 탐색적. STEP26 HELD_OUT weak-symptom→NON 26건 목록은 보지 않았다.
- 판정 조항 G_N 은 EVAL 수치를 본 뒤 추가(보수 방향). 정책·임계값은 EVAL 을 본 뒤 바꾸지 않았다.
- Regression 109 는 STEP21–26 에서 여러 번 분석된 고정 집합 — blind 아님.

## 10. 핵심 질문 답

1. **false NON 개선**: EVAL weak-symptom→NON 10.5% → 0.0%(n=248). DEV(out-of-fold) 12.8% → 1.7%. 대가: weak-non→NON 53.6% → 14.5%, weak-non→UNCERTAIN 44.6% → 79.5%. 질환명(예: 고혈압·결핵 포함 행)도 NON 에서 UNCERTAIN 으로 이동(§7).
2. **UNKNOWN ↔ NON 구분**: 안정적이지 않다. NON 판정은 거의 weak-non 에만 남았지만(§4), 비증상 대부분을 NON 으로 보내지 못하고 UNCERTAIN 으로 미룬다. DEV 에서 weak-symptom→NON ≤ 3% 를 지키며 얻을 수 있는 최대 weak-non→NON 이 14.3% 였다 — 현재 문자 TF-IDF 비증상 점수의 분리력 한계. UNKNOWN 중 weak-non 비율은 §4 표.
3. **원문 보존**: 전 행 손실 0(§6). UNKNOWN 에 canonical·표시 후보 0, NON 에도 canonical 0. 실험용 구조이며 PatientState 미변경.
4. **부적절 후보 감소**: A 가 표시한 EVAL 190행 중 proxy 해당 122 → BEST 50, 그러나 B 의 NON 완화로 새로 표시된 53행 중 45행이 proxy 해당. weak-non 후보 표시율 3.9% → 4.9%. '코피가 나요' smoke 는 hemoptysis 1개가 여전히 표시됨(§7) — 의미 연결 검증은 해결되지 않았다.
5. **지원 증상 자동 처리**: B4 그대로 → regression coverage 37.6%, precision 100.0%(A 와 동일). regression 비자동 행의 gold 표시 32 → 29. 임계 변경(POLICY_E)은 DEV CV 에서 채택 조건 미달.
6. **재학습 없는 한계**: (a) 비증상 점수가 질환명과 증상 단편을 문자 수준으로만 구분 → NON 을 보수적으로 하면 질환명 인식이 무너짐 (b) 77 개 밖 증상(코피 등)은 KoE·Linear 가 가장 가까운 지원 concept 에 높은 확률을 주므로, 확률·문자 유사도만으로 '의미가 다르다'를 판단할 수 없음 (c) COMPLEX 판정이 정규식이라 regression 지원 증상 문장 14.7% 를 COMPLEX 로 보냄 (d) 짧은 명사형 지원 증상 용어(외부의 두통·구토·발열·객혈 등)가 B4 를 통과하지 못해 UNKNOWN/UNCERTAIN 에 남음(`docs/step28_handoff.md` 주의) (e) 정확도 수치는 합성 regression·weak label 에만 근거.
7. **STEP28**: (1) 77 밖 concept 검색(HPO/SNOMED/UMLS)으로 UNKNOWN 표현에 '지원 안 됨'의 적극적 근거 제공 (2) 질환·약물·검사 사전(라이선스 확인된 용어집)으로 NON 의 적극적 근거 제공 (3) 후보 표시 전 concept 정의 수준 의미 검증 (4) 사람 라벨 Gold(누가·어떻게는 사용자 결정). `docs/step28_handoff.md`.
