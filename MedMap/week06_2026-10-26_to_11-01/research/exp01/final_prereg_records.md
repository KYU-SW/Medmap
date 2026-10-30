# FINAL 잠금 전 사전 기록 계산(자동 생성) — 성공 판정 아님

SELECT run `exp/main_ai/exp01_symptom_graph/outputs/select_20261028_1147`, τ=0.0001, FINAL n=102203, FINAL 중증 n=28420

| 비교 | 부분집합 | SELECT 기준 수준 | margin/기준 | SELECT Δ(기술) | 불일치율 d | FINAL 기대 SE | MDD80(α/6) | 검정력 참Δ=0 또는 MID(α/6) | (α) | 검정력 참Δ=SELECT(α/6) |
|---|---|---|---|---|---|---|---|---|---|---|
| H1 Top-5 PA−C | all | 0.81109 |  | +0.12508 | 0.16645 | 0.00128 | 0.00444 | 1.000 | 1.000 | 1.000 |
| H1 중증누락 PA−C | severe | 0.18831 | 0.027 | -0.15255 | 0.16451 | 0.00241 | 0.00837 | 0.288 | 0.547 | 1.000 |
| H2a Top-5 PB_REL−PA | all | 0.93617 | 0.005 | +0.00386 | 0.04305 | 0.00065 | 0.00226 | 1.000 | 1.000 | 1.000 |
| H2a 중증누락 PB_REL−PA | severe | 0.03577 | 0.140 | +0.00329 | 0.02716 | 0.00098 | 0.00340 | 0.993 | 0.999 | 0.187 |
| H2b 중증누락 PB−PB_REL | severe | 0.03906 | 0.128 | +0.00000 | 0.00000 | 0.00000 | 0.00000 | NA | NA | NA |
| H2b 잘못된분기 PB−PB_REL | all | 0.00000 |  | +0.00000 | 0.00000 | 0.00000 | 0.00000 | NA | NA | NA |
| H3a 중증누락 PC−PB @WD_MODEL_WRONG | severe | 0.03906 | 0.256 | +0.04392 | 0.08591 | 0.00174 | 0.00605 | 0.999 | 1.000 | 0.000 |
| H3a 잘못된분기 PC−PB @WD_MODEL_WRONG | all | 0.00000 |  | +0.00000 | 0.00000 | 0.00000 | 0.00000 | NA | NA | NA |
| H3c Top-5 PC−PB @WD_MODEL | all | 0.94000 | 0.005 | -0.03632 | 0.08613 | 0.00092 | 0.00319 | 0.998 | 1.000 | 0.000 |
| H3c 중증누락 PC−PB @WD_MODEL | severe | 0.03906 | 0.128 | +0.04392 | 0.08591 | 0.00174 | 0.00605 | 0.594 | 0.820 | 0.000 |
| H3c 잘못된분기 PC−PB @WD_MODEL | all | 0.00000 |  | +0.00000 | 0.00000 | 0.00000 | 0.00000 | NA | NA | NA |
| H3b 중증누락 PC−PB @RANDOM seed42 | severe | 0.03906 | 0.256 | +0.03741 | 0.06198 | 0.00148 | 0.00514 | 1.000 | 1.000 | 0.000 |
| H3b 잘못된분기 PC−PB @RANDOM seed42 | all | 0.00000 |  | +0.00000 | 0.00000 | 0.00000 | 0.00000 | NA | NA | NA |
| H3b 중증누락 PC−PB @RANDOM seed43 | severe | 0.03906 | 0.256 | +0.03650 | 0.06247 | 0.00148 | 0.00516 | 1.000 | 1.000 | 0.000 |
| H3b 잘못된분기 PC−PB @RANDOM seed43 | all | 0.00000 |  | +0.00000 | 0.00000 | 0.00000 | 0.00000 | NA | NA | NA |
| H3b 중증누락 PC−PB @RANDOM seed44 | severe | 0.03906 | 0.256 | +0.03762 | 0.06149 | 0.00147 | 0.00512 | 1.000 | 1.000 | 0.000 |
| H3b 잘못된분기 PC−PB @RANDOM seed44 | all | 0.00000 |  | +0.00000 | 0.00000 | 0.00000 | 0.00000 | NA | NA | NA |

효율(H2b): SELECT GM 0.6013, FINAL 기대 SE(log) 0.00190, 검정력(참 GM=SELECT, α/6) 1.000

## 질환별 규칙(n≥100, (Δk)·50>n) — SELECT 실제 발동 + FINAL 귀무 하 발동 확률(정규 근사)

| 단계 | 질환 | n SELECT | n FINAL | SELECT 누락 old→new | SELECT 발동 | P(발동|귀무, FINAL) |
|---|---|---|---|---|---|---|
| PA vs C | Anaphylaxis | 2716 | 2818 | 0→5 | False | 0.0000 |
| PA vs C | Boerhaave | 1504 | 1471 | 638→0 | False | 0.1194 |
| PA vs C | Croup | 281 | 292 | 73→0 | False | 0.2513 |
| PA vs C | Ebola | 67 | 67 | 23→4 | False | 0.3793 |
| PA vs C | Epiglottitis | 1708 | 1769 | 703→130 | False | 0.0732 |
| PA vs C | Guillain-Barré syndrome | 2296 | 2303 | 299→0 | False | 0.0039 |
| PA vs C | Myocarditis | 1130 | 1098 | 432→136 | False | 0.0977 |
| PA vs C | PSVT | 1886 | 1828 | 476→4 | False | 0.0444 |
| PA vs C | Possible NSTEMI / STEMI | 2052 | 2154 | 911→236 | False | 0.0528 |
| PA vs C | Pulmonary embolism | 2748 | 2666 | 0→137 | True | 0.0000 |
| PA vs C | Spontaneous pneumothorax | 993 | 1037 | 287→49 | False | 0.1175 |
| PA vs C | Stable angina | 1650 | 1664 | 875→222 | False | 0.0973 |
| PA vs C | Unstable angina | 2099 | 2072 | 664→99 | False | 0.0397 |
| PB_REL vs PA | Acute pulmonary edema | 1900 | 1850 | 0→75 | True | 0.0000 |
| PB_REL vs PA | Anaphylaxis | 2716 | 2818 | 5→4 | False | 0.0000 |
| PB_REL vs PA | Croup | 281 | 292 | 0→5 | False | 0.0052 |
| PB_REL vs PA | Ebola | 67 | 67 | 4→9 | False | 0.2745 |
| PB_REL vs PA | Epiglottitis | 1708 | 1769 | 130→71 | False | 0.0008 |
| PB_REL vs PA | Myocarditis | 1130 | 1098 | 136→59 | False | 0.0056 |
| PB_REL vs PA | PSVT | 1886 | 1828 | 4→162 | True | 0.0016 |
| PB_REL vs PA | Possible NSTEMI / STEMI | 2052 | 2154 | 236→248 | False | 0.0000 |
| PB_REL vs PA | Pulmonary embolism | 2748 | 2666 | 137→104 | False | 0.0000 |
| PB_REL vs PA | Spontaneous pneumothorax | 993 | 1037 | 49→77 | True | 0.0001 |
| PB_REL vs PA | Stable angina | 1650 | 1664 | 222→245 | False | 0.0013 |
| PB_REL vs PA | Unstable angina | 2099 | 2072 | 99→57 | False | 0.0000 |
| PC vs PB @WD_MODEL_WRONG | Acute pulmonary edema | 1900 | 1850 | 75→46 | False | 0.0003 |
| PC vs PB @WD_MODEL_WRONG | Anaphylaxis | 2716 | 2818 | 4→162 | True | 0.0000 |
| PC vs PB @WD_MODEL_WRONG | Boerhaave | 1504 | 1471 | 0→136 | True | 0.0054 |
| PC vs PB @WD_MODEL_WRONG | Croup | 281 | 292 | 5→0 | False | 0.0052 |
| PC vs PB @WD_MODEL_WRONG | Ebola | 67 | 67 | 9→7 | False | 0.1717 |
| PC vs PB @WD_MODEL_WRONG | Epiglottitis | 1708 | 1769 | 71→153 | True | 0.0028 |
| PC vs PB @WD_MODEL_WRONG | Myocarditis | 1130 | 1098 | 59→171 | True | 0.0176 |
| PC vs PB @WD_MODEL_WRONG | PSVT | 1886 | 1828 | 162→444 | True | 0.0135 |
| PC vs PB @WD_MODEL_WRONG | Possible NSTEMI / STEMI | 2052 | 2154 | 248→355 | True | 0.0207 |
| PC vs PB @WD_MODEL_WRONG | Pulmonary embolism | 2748 | 2666 | 104→97 | False | 0.0000 |
| PC vs PB @WD_MODEL_WRONG | Spontaneous pneumothorax | 993 | 1037 | 77→366 | True | 0.1309 |
| PC vs PB @WD_MODEL_WRONG | Stable angina | 1650 | 1664 | 245→173 | False | 0.0336 |
| PC vs PB @WD_MODEL_WRONG | Unstable angina | 2099 | 2072 | 57→261 | True | 0.0046 |
| PC vs PB @WD_MODEL | Acute pulmonary edema | 1900 | 1850 | 75→46 | False | 0.0003 |
| PC vs PB @WD_MODEL | Anaphylaxis | 2716 | 2818 | 4→162 | True | 0.0000 |
| PC vs PB @WD_MODEL | Boerhaave | 1504 | 1471 | 0→136 | True | 0.0054 |
| PC vs PB @WD_MODEL | Croup | 281 | 292 | 5→0 | False | 0.0052 |
| PC vs PB @WD_MODEL | Ebola | 67 | 67 | 9→7 | False | 0.1717 |
| PC vs PB @WD_MODEL | Epiglottitis | 1708 | 1769 | 71→153 | True | 0.0028 |
| PC vs PB @WD_MODEL | Myocarditis | 1130 | 1098 | 59→171 | True | 0.0176 |
| PC vs PB @WD_MODEL | PSVT | 1886 | 1828 | 162→444 | True | 0.0135 |
| PC vs PB @WD_MODEL | Possible NSTEMI / STEMI | 2052 | 2154 | 248→355 | True | 0.0207 |
| PC vs PB @WD_MODEL | Pulmonary embolism | 2748 | 2666 | 104→97 | False | 0.0000 |
| PC vs PB @WD_MODEL | Spontaneous pneumothorax | 993 | 1037 | 77→366 | True | 0.1309 |
| PC vs PB @WD_MODEL | Stable angina | 1650 | 1664 | 245→173 | False | 0.0336 |
| PC vs PB @WD_MODEL | Unstable angina | 2099 | 2072 | 57→261 | True | 0.0046 |
| PC vs PB @RANDOM seed42 | Acute pulmonary edema | 1900 | 1850 | 75→88 | False | 0.0000 |
| PC vs PB @RANDOM seed42 | Anaphylaxis | 2716 | 2818 | 4→40 | False | 0.0000 |
| PC vs PB @RANDOM seed42 | Boerhaave | 1504 | 1471 | 0→178 | True | 0.0129 |
| PC vs PB @RANDOM seed42 | Croup | 281 | 292 | 5→8 | False | 0.0281 |
| PC vs PB @RANDOM seed42 | Ebola | 67 | 67 | 9→8 | False | 0.2745 |
| PC vs PB @RANDOM seed42 | Epiglottitis | 1708 | 1769 | 71→139 | True | 0.0007 |
| PC vs PB @RANDOM seed42 | Myocarditis | 1130 | 1098 | 59→165 | True | 0.0176 |
| PC vs PB @RANDOM seed42 | PSVT | 1886 | 1828 | 162→301 | True | 0.0021 |
| PC vs PB @RANDOM seed42 | Possible NSTEMI / STEMI | 2052 | 2154 | 248→310 | True | 0.0052 |
| PC vs PB @RANDOM seed42 | Pulmonary embolism | 2748 | 2666 | 104→211 | True | 0.0000 |
| PC vs PB @RANDOM seed42 | Spontaneous pneumothorax | 993 | 1037 | 77→268 | True | 0.0782 |
| PC vs PB @RANDOM seed42 | Stable angina | 1650 | 1664 | 245→263 | False | 0.0162 |
| PC vs PB @RANDOM seed42 | Unstable angina | 2099 | 2072 | 57→206 | True | 0.0009 |
| PC vs PB @RANDOM seed43 | Acute pulmonary edema | 1900 | 1850 | 75→87 | False | 0.0000 |
| PC vs PB @RANDOM seed43 | Anaphylaxis | 2716 | 2818 | 4→42 | False | 0.0000 |
| PC vs PB @RANDOM seed43 | Boerhaave | 1504 | 1471 | 0→196 | True | 0.0168 |
| PC vs PB @RANDOM seed43 | Croup | 281 | 292 | 5→6 | False | 0.0052 |
| PC vs PB @RANDOM seed43 | Ebola | 67 | 67 | 9→7 | False | 0.2514 |
| PC vs PB @RANDOM seed43 | Epiglottitis | 1708 | 1769 | 71→141 | True | 0.0013 |
| PC vs PB @RANDOM seed43 | Myocarditis | 1130 | 1098 | 59→172 | True | 0.0223 |
| PC vs PB @RANDOM seed43 | PSVT | 1886 | 1828 | 162→287 | True | 0.0019 |
| PC vs PB @RANDOM seed43 | Possible NSTEMI / STEMI | 2052 | 2154 | 248→292 | True | 0.0044 |
| PC vs PB @RANDOM seed43 | Pulmonary embolism | 2748 | 2666 | 104→196 | True | 0.0000 |
| PC vs PB @RANDOM seed43 | Spontaneous pneumothorax | 993 | 1037 | 77→276 | True | 0.0812 |
| PC vs PB @RANDOM seed43 | Stable angina | 1650 | 1664 | 245→253 | False | 0.0184 |
| PC vs PB @RANDOM seed43 | Unstable angina | 2099 | 2072 | 57→204 | True | 0.0005 |
| PC vs PB @RANDOM seed44 | Acute pulmonary edema | 1900 | 1850 | 75→82 | False | 0.0000 |
| PC vs PB @RANDOM seed44 | Anaphylaxis | 2716 | 2818 | 4→38 | False | 0.0000 |
| PC vs PB @RANDOM seed44 | Boerhaave | 1504 | 1471 | 0→206 | True | 0.0191 |
| PC vs PB @RANDOM seed44 | Croup | 281 | 292 | 5→6 | False | 0.0421 |
| PC vs PB @RANDOM seed44 | Ebola | 67 | 67 | 9→7 | False | 0.2514 |
| PC vs PB @RANDOM seed44 | Epiglottitis | 1708 | 1769 | 71→130 | True | 0.0007 |
| PC vs PB @RANDOM seed44 | Myocarditis | 1130 | 1098 | 59→180 | True | 0.0258 |
| PC vs PB @RANDOM seed44 | PSVT | 1886 | 1828 | 162→290 | True | 0.0011 |
| PC vs PB @RANDOM seed44 | Possible NSTEMI / STEMI | 2052 | 2154 | 248→298 | True | 0.0040 |
| PC vs PB @RANDOM seed44 | Pulmonary embolism | 2748 | 2666 | 104→197 | True | 0.0000 |
| PC vs PB @RANDOM seed44 | Spontaneous pneumothorax | 993 | 1037 | 77→271 | True | 0.0797 |
| PC vs PB @RANDOM seed44 | Stable angina | 1650 | 1664 | 245→286 | True | 0.0179 |
| PC vs PB @RANDOM seed44 | Unstable angina | 2099 | 2072 | 57→200 | True | 0.0012 |

(표에는 SELECT 발동·누락 변화가 있거나 귀무 발동 확률 >0.001 인 행만. 전체는 JSON.)
