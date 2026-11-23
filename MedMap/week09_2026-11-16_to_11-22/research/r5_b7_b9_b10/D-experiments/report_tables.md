# report_tables (자동 생성, [합성] 실험)

## 전체(손 사례·정답없음 제외)
| method | n | label_ok | state_ok | full_ok | wrong_confirm | hold_set_ok | gap_distinction_acc | ewas_ok | app_ok | rule_ok | F1_states | F2_states | F3 | F4_states | F5 | time_median_s | time_max_s | mem_peak_max_bytes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_mitplan_style | 1261 | 0.2181 | 0.272 | 0.2181 | 0.7288 | 0.3315 | 0.0 |  | 0.3299 | 0.7145 | 2612 | 297 | 0.4893 | 116 | 0 | 5.4e-05 | 0.001058 | 8840 |
| B_joint | 1261 | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 0.0 | 0 | 0 | 0.005418 | 0.186794 | 152641 |
| Bp_modular | 1261 | 0.9405 | 0.8945 | 0.8945 | 0.0 | 0.908 | 0.9017 | 0.9929 | 1.0 | 1.0 | 0 | 0 | 0.0 | 0 | 0 | 0.00759 | 16.074387 | 23183441 |
| C_naive | 1261 | 0.161 | 0.1451 | 0.1142 | 0.8858 | 0.268 | 0.0 |  | 0.3299 | 0.6376 | 2761 | 297 | 0.4893 | 0 | 0 | 1.7e-05 | 0.000157 | 7440 |
| V_exclude_variant | 1261 | 0.517 | 0.4195 | 0.4195 | 0.1689 | 0.6638 | 0.1823 | 0.7946 | 1.0 | 1.0 | 1678 | 0 | 0.0357 | 1530 | 0 | 0.008223 | 0.371383 | 336476 |

## 실험별 full_ok (라벨+상태별 조건 함수 일치)
| exp | A_mitplan_style | B_joint | Bp_modular | C_naive | V_exclude_variant |
|---|---|---|---|---|---|
| E1 | 1.0 | 1.0 | 1.0 | 0.53 | 1.0 |
| E10 | 0.0625 | 1.0 | 1.0 | 0.0375 | 1.0 |
| E2 | 0.6 | 1.0 | 1.0 | 0.31 | 1.0 |
| E3 | 0.48 | 1.0 | 1.0 | 0.27 | 0.48 |
| E4 | 0.0467 | 1.0 | 0.7933 | 0.02 | 0.1467 |
| E5 | 0.0792 | 1.0 | 0.7708 | 0.05 | 0.1458 |
| E6 | 0.05 | 1.0 | 0.9 | 0.05 | 0.2 |
| E7 | 0.1 | 1.0 | 0.9313 | 0.0 | 0.2313 |
| E8 | 0.0 | 1.0 | 0.8 | 0.0 | 0.05 |
| E9 | 0.1667 | 1.0 | 1.0 | 0.0833 | 1.0 |
| ENOGT | 0.0 | 1.0 | 0.6364 | 0.0 | 0.3636 |
| case | 0.3 | 1.0 | 0.8 | 0.1 | 0.8 |

## 실험별 label_ok
| exp | A_mitplan_style | B_joint | Bp_modular | C_naive | V_exclude_variant |
|---|---|---|---|---|---|
| E1 | 1.0 | 1.0 | 1.0 | 0.86 | 1.0 |
| E10 | 0.0625 | 1.0 | 1.0 | 0.05 | 1.0 |
| E2 | 0.6 | 1.0 | 1.0 | 0.42 | 1.0 |
| E3 | 0.48 | 1.0 | 1.0 | 0.36 | 0.48 |
| E4 | 0.0467 | 1.0 | 0.92 | 0.02 | 0.4067 |
| E5 | 0.0792 | 1.0 | 0.9083 | 0.05 | 0.3542 |
| E6 | 0.05 | 1.0 | 0.9 | 0.05 | 0.26 |
| E7 | 0.1 | 1.0 | 0.95 | 0.0 | 0.3438 |
| E8 | 0.0 | 1.0 | 0.8333 | 0.0 | 0.1167 |
| E9 | 0.1667 | 1.0 | 1.0 | 0.1667 | 1.0 |
| ENOGT | 0.0 | 1.0 | 0.7273 | 0.0 | 0.3636 |
| case | 0.3 | 1.0 | 0.9 | 0.1 | 0.8 |

## 실험별 ewas_ok (∃w∀s)
| exp | A_mitplan_style | B_joint | Bp_modular | C_naive | V_exclude_variant |
|---|---|---|---|---|---|
| E1 |  | 1.0 | 1.0 |  | 1.0 |
| E10 |  | 1.0 | 0.9875 |  | 1.0 |
| E2 |  | 1.0 | 1.0 |  | 1.0 |
| E3 |  | 1.0 | 1.0 |  | 0.66 |
| E4 |  | 1.0 | 1.0 |  | 0.78 |
| E5 |  | 1.0 | 0.9917 |  | 0.7417 |
| E6 |  | 1.0 | 1.0 |  | 0.72 |
| E7 |  | 1.0 | 0.9812 |  | 0.6312 |
| E8 |  | 1.0 | 1.0 |  | 0.8167 |
| E9 |  | 1.0 | 1.0 |  | 1.0 |
| ENOGT |  | 1.0 | 0.7273 |  | 0.6364 |
| case |  | 1.0 | 0.8 |  | 0.8 |

## 실험별 wrong_confirm
| exp | A_mitplan_style | B_joint | Bp_modular | C_naive | V_exclude_variant |
|---|---|---|---|---|---|
| E1 | 0.0 | 0.0 | 0.0 | 0.47 | 0.0 |
| E10 | 0.9375 | 0.0 | 0.0 | 0.9625 | 0.0 |
| E2 | 0.4 | 0.0 | 0.0 | 0.69 | 0.0 |
| E3 | 0.52 | 0.0 | 0.0 | 0.73 | 0.34 |
| E4 | 0.8333 | 0.0 | 0.0 | 0.98 | 0.1533 |
| E5 | 0.8125 | 0.0 | 0.0 | 0.95 | 0.1917 |
| E6 | 0.9 | 0.0 | 0.0 | 0.95 | 0.26 |
| E7 | 0.8187 | 0.0 | 0.0 | 1.0 | 0.2437 |
| E8 | 1.0 | 0.0 | 0.0 | 1.0 | 0.25 |
| E9 | 0.8333 | 0.0 | 0.0 | 0.9167 | 0.0 |
| ENOGT | 1.0 | 0.0 | 0.0 | 1.0 | 0.3636 |
| case | 0.7 | 0.0 | 0.0 | 0.9 | 0.2 |

## 실험별 시간 중앙값(s)
| exp | A_mitplan_style | B_joint | Bp_modular | C_naive | V_exclude_variant |
|---|---|---|---|---|---|
| E1 | 4.4e-05 | 0.009431 | 0.007246 | 1.2e-05 | 0.009643 |
| E10 | 8.8e-05 | 0.044526 | 0.03619 | 2.6e-05 | 0.044599 |
| E2 | 4.4e-05 | 0.009549 | 0.007992 | 1.3e-05 | 0.010154 |
| E3 | 4.5e-05 | 0.003006 | 0.004596 | 1e-05 | 0.004713 |
| E4 | 5.4e-05 | 0.005207 | 0.008739 | 2.1e-05 | 0.00904 |
| E5 | 6.4e-05 | 0.004443 | 0.007368 | 2.7e-05 | 0.008217 |
| E6 | 5e-05 | 0.004568 | 0.007469 | 1.6e-05 | 0.005933 |
| E7 | 4.6e-05 | 0.003378 | 0.005938 | 1.7e-05 | 0.00493 |
| E8 | 0.000154 | 0.010152 | 0.025308 | 3.4e-05 | 0.028126 |
| E9 | 4.1e-05 | 0.011841 | 0.01144 | 1.8e-05 | 0.012129 |
| ENOGT | 6.7e-05 | 0.00473 | 0.008496 | 1.7e-05 | 0.007455 |
| case | 2.7e-05 | 0.005857 | 0.005703 | 1e-05 | 0.005845 |

## E5 결측 수준별 full_ok
| level | A_mitplan_style | B_joint | Bp_modular | C_naive | V_exclude_variant |
|---|---|---|---|---|---|
| 0 | 0.35 | 1.0 | 1.0 | 0.25 | 0.375 |
| 1 | 0.075 | 1.0 | 0.825 | 0.05 | 0.1 |
| 2 | 0.0 | 1.0 | 0.8 | 0.0 | 0.1 |
| 3 | 0.0 | 1.0 | 0.625 | 0.0 | 0.1 |
| 4 | 0.025 | 1.0 | 0.675 | 0.0 | 0.1 |
| 5 | 0.025 | 1.0 | 0.7 | 0.0 | 0.1 |

## E6 선호 범위 r 별 full_ok
| level | A_mitplan_style | B_joint | Bp_modular | C_naive | V_exclude_variant |
|---|---|---|---|---|---|
| 0 | 0.05 | 1.0 | 0.9 | 0.05 | 0.2 |
| 1/10 | 0.05 | 1.0 | 0.9 | 0.05 | 0.2 |
| 1/20 | 0.05 | 1.0 | 0.9 | 0.05 | 0.2 |
| 1/3 | 0.05 | 1.0 | 0.9 | 0.05 | 0.2 |
| 1/5 | 0.05 | 1.0 | 0.9 | 0.05 | 0.2 |

## E7 근거 정보 수준별 full_ok (0:항목100%/공유0, 1:90%/0, 2:90%/공유100%, 3:60%/공유100%)
| level | A_mitplan_style | B_joint | Bp_modular | C_naive | V_exclude_variant |
|---|---|---|---|---|---|
| 0 | 0.15 | 1.0 | 1.0 | 0.0 | 0.35 |
| 1 | 0.1 | 1.0 | 1.0 | 0.0 | 0.225 |
| 2 | 0.125 | 1.0 | 0.825 | 0.0 | 0.25 |
| 3 | 0.025 | 1.0 | 0.9 | 0.0 | 0.1 |

## E8 지침 수별 시간 중앙값(s)
| family | A_mitplan_style | B_joint | Bp_modular | C_naive | V_exclude_variant |
|---|---|---|---|---|---|
| G2 | 0.0001 | 0.0074 | 0.0095 | 0.0 | 0.0165 |
| G3 | 0.0001 | 0.0087 | 0.0469 | 0.0 | 0.0182 |
| G4 | 0.0002 | 0.0095 | 0.0114 | 0.0 | 0.0298 |
| G5 | 0.0005 | 0.0184 | 0.184 | 0.0 | 0.0421 |

## 정답 라벨 분포
| exp | CONDITIONAL_CONFLICT | CONDITIONAL_PLAN | CONFIRMED_PLAN | CONVERGED | EVIDENCE_SCOPE_INSUFFICIENT | INFO_HOLD | KNOWLEDGE_GAP | NO_GROUND_TRUTH | PREFERENCE_DEPENDENT | REAL_CONFLICT |
|---|---|---|---|---|---|---|---|---|---|---|
| E1 | 0 | 0 | 7 | 86 | 0 | 0 | 0 | 0 | 0 | 7 |
| E10 | 0 | 28 | 1 | 4 | 0 | 47 | 0 | 0 | 0 | 0 |
| E2 | 0 | 0 | 10 | 42 | 0 | 0 | 0 | 0 | 40 | 8 |
| E3 | 0 | 0 | 4 | 36 | 40 | 0 | 12 | 0 | 0 | 8 |
| E4 | 31 | 5 | 1 | 3 | 22 | 70 | 13 | 0 | 1 | 4 |
| E5 | 57 | 6 | 1 | 12 | 52 | 84 | 21 | 0 | 1 | 6 |
| E6 | 15 | 16 | 0 | 10 | 65 | 84 | 10 | 0 | 0 | 0 |
| E7 | 27 | 7 | 1 | 0 | 28 | 54 | 28 | 0 | 0 | 15 |
| E8 | 0 | 3 | 0 | 0 | 20 | 26 | 11 | 0 | 0 | 0 |
| E9 | 0 | 42 | 0 | 10 | 0 | 7 | 0 | 0 | 1 | 0 |
| ENOGT | 0 | 3 | 0 | 0 | 2 | 5 | 1 | 19 | 0 | 0 |
| case | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 |

## 손 사례
| id | method | gt_final | m_final | label_ok | state_ok | full_ok | ewas_ok | F1_states | F2_states | F3 | F4_states |
|---|---|---|---|---|---|---|---|---|---|---|---|
| case_A | A_mitplan_style | REAL_CONFLICT | REAL_CONFLICT | 1 | 1 | 1 |  | 0 | 0 | 0 | 0 |
| case_A | B_joint | REAL_CONFLICT | REAL_CONFLICT | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_A | Bp_modular | REAL_CONFLICT | REAL_CONFLICT | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_A | C_naive | REAL_CONFLICT | CONVERGED | 0 | 0 | 0 |  | 0 | 0 | 0 | 0 |
| case_A | V_exclude_variant | REAL_CONFLICT | REAL_CONFLICT | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_B | A_mitplan_style | CONFIRMED_PLAN | CONFIRMED_PLAN | 1 | 1 | 1 |  | 0 | 0 | 0 | 0 |
| case_B | B_joint | CONFIRMED_PLAN | CONFIRMED_PLAN | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_B | Bp_modular | CONFIRMED_PLAN | CONFIRMED_PLAN | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_B | C_naive | CONFIRMED_PLAN | CONVERGED | 0 | 0 | 0 |  | 0 | 0 | 0 | 0 |
| case_B | V_exclude_variant | CONFIRMED_PLAN | CONFIRMED_PLAN | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_C | A_mitplan_style | CONDITIONAL_CONFLICT | CONVERGED | 0 | 0 | 0 |  | 0 | 0 | 1 | 0 |
| case_C | B_joint | CONDITIONAL_CONFLICT | CONDITIONAL_CONFLICT | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_C | Bp_modular | CONDITIONAL_CONFLICT | CONDITIONAL_CONFLICT | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_C | C_naive | CONDITIONAL_CONFLICT | CONVERGED | 0 | 0 | 0 |  | 0 | 0 | 1 | 0 |
| case_C | V_exclude_variant | CONDITIONAL_CONFLICT | CONDITIONAL_CONFLICT | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_D | A_mitplan_style | PREFERENCE_DEPENDENT | CONVERGED | 0 | 0 | 0 |  | 0 | 1 | 0 | 0 |
| case_D | B_joint | PREFERENCE_DEPENDENT | PREFERENCE_DEPENDENT | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_D | Bp_modular | PREFERENCE_DEPENDENT | PREFERENCE_DEPENDENT | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_D | C_naive | PREFERENCE_DEPENDENT | CONVERGED | 0 | 0 | 0 |  | 0 | 1 | 0 | 0 |
| case_D | V_exclude_variant | PREFERENCE_DEPENDENT | PREFERENCE_DEPENDENT | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_E | A_mitplan_style | EVIDENCE_SCOPE_INSUFFICIENT | CONVERGED | 0 | 0 | 0 |  | 1 | 0 | 0 | 0 |
| case_E | B_joint | EVIDENCE_SCOPE_INSUFFICIENT | EVIDENCE_SCOPE_INSUFFICIENT | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_E | Bp_modular | EVIDENCE_SCOPE_INSUFFICIENT | EVIDENCE_SCOPE_INSUFFICIENT | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_E | C_naive | EVIDENCE_SCOPE_INSUFFICIENT | CONVERGED | 0 | 0 | 0 |  | 1 | 0 | 0 | 0 |
| case_E | V_exclude_variant | EVIDENCE_SCOPE_INSUFFICIENT | CONVERGED | 0 | 0 | 0 | 0.0 | 1 | 0 | 0 | 1 |
| case_F | A_mitplan_style | KNOWLEDGE_GAP | CONVERGED | 0 | 0 | 0 |  | 1 | 0 | 0 | 0 |
| case_F | B_joint | KNOWLEDGE_GAP | KNOWLEDGE_GAP | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_F | Bp_modular | KNOWLEDGE_GAP | KNOWLEDGE_GAP | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_F | C_naive | KNOWLEDGE_GAP | CONVERGED | 0 | 0 | 0 |  | 1 | 0 | 0 | 0 |
| case_F | V_exclude_variant | KNOWLEDGE_GAP | CONVERGED | 0 | 0 | 0 | 0.0 | 1 | 0 | 0 | 0 |
| case_G | A_mitplan_style | CONDITIONAL_PLAN | CONVERGED | 0 | 1 | 0 |  | 0 | 0 | 1 | 0 |
| case_G | B_joint | CONDITIONAL_PLAN | CONDITIONAL_PLAN | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_G | Bp_modular | CONDITIONAL_PLAN | INFO_HOLD | 0 | 0 | 0 | 0.0 | 0 | 0 | 0 | 0 |
| case_G | C_naive | CONDITIONAL_PLAN | CONVERGED | 0 | 1 | 0 |  | 0 | 0 | 1 | 0 |
| case_G | V_exclude_variant | CONDITIONAL_PLAN | CONDITIONAL_PLAN | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_H | A_mitplan_style | INFO_HOLD | CONVERGED | 0 | 0 | 0 |  | 0 | 2 | 1 | 0 |
| case_H | B_joint | INFO_HOLD | INFO_HOLD | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_H | Bp_modular | INFO_HOLD | INFO_HOLD | 1 | 1 | 1 | 0.0 | 0 | 0 | 0 | 0 |
| case_H | C_naive | INFO_HOLD | CONVERGED | 0 | 0 | 0 |  | 0 | 2 | 1 | 0 |
| case_H | V_exclude_variant | INFO_HOLD | INFO_HOLD | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_I | A_mitplan_style | INFO_HOLD | CONVERGED | 0 | 0 | 0 |  | 0 | 2 | 1 | 0 |
| case_I | B_joint | INFO_HOLD | INFO_HOLD | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_I | Bp_modular | INFO_HOLD | INFO_HOLD | 1 | 0 | 0 | 1.0 | 0 | 0 | 0 | 0 |
| case_I | C_naive | INFO_HOLD | CONVERGED | 0 | 0 | 0 |  | 0 | 2 | 1 | 0 |
| case_I | V_exclude_variant | INFO_HOLD | INFO_HOLD | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_J | A_mitplan_style | NO_GROUND_TRUTH | REAL_CONFLICT | 0 | 1 | 0 |  | 0 | 0 | 0 | 0 |
| case_J | B_joint | NO_GROUND_TRUTH | NO_GROUND_TRUTH | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_J | Bp_modular | NO_GROUND_TRUTH | NO_GROUND_TRUTH | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_J | C_naive | NO_GROUND_TRUTH | CONVERGED | 0 | 0 | 0 |  | 0 | 0 | 0 | 0 |
| case_J | V_exclude_variant | NO_GROUND_TRUTH | NO_GROUND_TRUTH | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_K | A_mitplan_style | CONVERGED | CONVERGED | 1 | 1 | 1 |  | 0 | 0 | 0 | 0 |
| case_K | B_joint | CONVERGED | CONVERGED | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_K | Bp_modular | CONVERGED | CONVERGED | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| case_K | C_naive | CONVERGED | CONVERGED | 1 | 1 | 1 |  | 0 | 0 | 0 | 0 |
| case_K | V_exclude_variant | CONVERGED | CONVERGED | 1 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |

## 안정성
| exp | method | adjacent_pairs | unnecessary_change | insensitive |
|---|---|---|---|---|
| E5 | A_mitplan_style | 200 | 14 | 83 |
| E5 | B_joint | 200 | 0 | 0 |
| E5 | Bp_modular | 200 | 10 | 7 |
| E5 | C_naive | 200 | 0 | 131 |
| E5 | V_exclude_variant | 200 | 27 | 39 |
| E6 | A_mitplan_style | 160 | 0 | 3 |
| E6 | B_joint | 160 | 0 | 0 |
| E6 | Bp_modular | 160 | 0 | 0 |
| E6 | C_naive | 160 | 0 | 3 |
| E6 | V_exclude_variant | 160 | 6 | 0 |
| E7 | A_mitplan_style | 120 | 6 | 35 |
| E7 | B_joint | 120 | 0 | 0 |
| E7 | Bp_modular | 120 | 2 | 3 |
| E7 | C_naive | 120 | 0 | 50 |
| E7 | V_exclude_variant | 120 | 16 | 24 |

## B vs B' 차이 원인 집계
| cause | count |
|---|---|
| mixed_quantifier_EwAs_vs_AsEw | 2 |
| shared_variable_lost_in_module_combination | 135 |

## B vs B' 차이(실험별)
| exp | cause | count |
|---|---|---|
| E10 | mixed_quantifier_EwAs_vs_AsEw | 1 |
| E4 | shared_variable_lost_in_module_combination | 31 |
| E5 | shared_variable_lost_in_module_combination | 55 |
| E6 | shared_variable_lost_in_module_combination | 20 |
| E7 | shared_variable_lost_in_module_combination | 11 |
| E8 | shared_variable_lost_in_module_combination | 12 |
| ENOGT | shared_variable_lost_in_module_combination | 4 |
| case | mixed_quantifier_EwAs_vs_AsEw | 1 |
| case | shared_variable_lost_in_module_combination | 2 |

## B_milp 대조
n=1271, ewas_ok=1271, app_ok=1271, 비어있지 않은 정답 EWAS=434, 시간 중앙값=0.0138s 최대=0.2220s

## E8b 확장성(미확인 변수 수)
| n_unknown | t_milp_med | t_B_enum_med | t_gt_med | B_agree | gt_agree_milp |
|---|---|---|---|---|---|
| 2.0 | 0.2654 | 0.0533 | 0.0922 | 3.0 | 3.0 |
| 4.0 | 0.062 | 0.5468 | 0.16 | 3.0 | 3.0 |
| 6.0 | 0.1923 | 0.9235 | 1.1645 | 3.0 | 3.0 |
| 8.0 | 0.1494 | 2.9654 | 3.8341 | 3.0 | 3.0 |
| 10.0 | 0.2471 | 15.2853 | 31.1724 | 3.0 | 3.0 |
| 12.0 | 0.1843 |  |  | 0.0 | 0.0 |
| 14.0 | 0.1612 |  |  | 0.0 | 0.0 |
| 16.0 | 0.0926 |  |  | 0.0 | 0.0 |
| 20.0 | 0.2848 |  |  | 0.0 | 0.0 |

## 상황 분류
- 1_A_fails_B_succeeds: 993
- 2_B_and_Bp_both_fail: 0
- 2b_B_fails_any: 0
- 4_knowledge_gap_truth: 97
- 5_no_ground_truth: 20
- Bp_fails_B_succeeds: 137
- no_ground_truth_method_outputs: {'A_mitplan_style': {'REAL_CONFLICT': 3, 'CONVERGED': 12, 'CONFIRMED_PLAN': 5}, 'B_joint': {'NO_GROUND_TRUTH': 20}, 'Bp_modular': {'NO_GROUND_TRUTH': 20}, 'C_naive': {'CONVERGED': 20}, 'V_exclude_variant': {'NO_GROUND_TRUTH': 20}}
