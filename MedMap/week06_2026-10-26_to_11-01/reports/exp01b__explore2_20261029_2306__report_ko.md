# EXP-01b 판별력 개선 1차 평가(EXPLORATORY, DDXPlus TRAIN16 새 100명 — 임상 성능 아님)

- 프로토콜 고정 2026-10-29 23:06:48 · 무작위 기준 top1 25% · top3 75% · WD 제외 1위 33% · 동점은 비관/낙관 병기
- 정답·WD 일치 ≠ 의학적 적절성. 반박 관계·진단 규칙 없음. 4질환 폐쇄 집합. 수치는 rows.csv·summary.json 에서 생성.

## ALL
| 팔 | top1_pess | top1_opt | top3_pess | alt_first_pess | alt_first_opt | review_incl | review_random_expected | tie_rate | max_unique_share | used_codes_mean | pos_in_graph_mean | gap_C_mean_A | A_review_signal | A_gap_flag | A_old_any_unexplained |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OLD_GRADED | 20/100 (20%) | 74/100 (74%) | 90/100 (90%) | 27/100 (27%) | 79/100 (79%) | 81/100 (81%) | 0.64 | 64/100 (64%) | 0.36 | 4.39 | 4.14 | 0.96 | 1/100 (1%) | 65/100 (65%) | 65/100 (65%) |
| NEW_GRADED | 20/100 (20%) | 88/100 (88%) | 71/100 (71%) | 27/100 (27%) | 90/100 (90%) | 81/100 (81%) | 0.5933 | 73/100 (73%) | 0.27 | 4.96 | 4.71 | 1.2 | 1/100 (1%) | 65/100 (65%) | 65/100 (65%) |
| NEW_SPEC | 20/100 (20%) | 74/100 (74%) | 90/100 (90%) | 27/100 (27%) | 79/100 (79%) | 81/100 (81%) | 0.5933 | 64/100 (64%) | 0.36 | 4.96 | 4.71 | 1.2 | 1/100 (1%) | 65/100 (65%) | 65/100 (65%) |

## Pulmonary embolism
| 팔 | top1_pess | top1_opt | top3_pess | alt_first_pess | alt_first_opt | review_incl | review_random_expected | tie_rate | max_unique_share | used_codes_mean | pos_in_graph_mean | gap_C_mean_A | A_review_signal | A_gap_flag | A_old_any_unexplained |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OLD_GRADED | 0/25 (0%) | 0/25 (0%) | 16/25 (64%) | 5/25 (20%) | 5/25 (20%) | 24/25 (96%) | 0.6933 | 9/25 (36%) | 0.64 | 5.16 | 5.16 | 1.76 | 0/25 (0%) | 25/25 (100%) | 25/25 (100%) |
| NEW_GRADED | 0/25 (0%) | 14/25 (56%) | 16/25 (64%) | 5/25 (20%) | 16/25 (64%) | 24/25 (96%) | 0.6933 | 18/25 (72%) | 0.28 | 6.68 | 6.68 | 2.72 | 0/25 (0%) | 25/25 (100%) | 25/25 (100%) |
| NEW_SPEC | 0/25 (0%) | 0/25 (0%) | 16/25 (64%) | 5/25 (20%) | 5/25 (20%) | 24/25 (96%) | 0.6933 | 9/25 (36%) | 0.64 | 6.68 | 6.68 | 2.72 | 0/25 (0%) | 25/25 (100%) | 25/25 (100%) |
- PE 누락(조건 B, 25건): OLD_GRADED top3 밖 9 / WD 제외 1위 아님 20 / 추가 검토 후보 없음 1 · NEW_GRADED top3 밖 9 / WD 제외 1위 아님 20 / 추가 검토 후보 없음 1 · NEW_SPEC top3 밖 9 / WD 제외 1위 아님 20 / 추가 검토 후보 없음 1

## Pericarditis
| 팔 | top1_pess | top1_opt | top3_pess | alt_first_pess | alt_first_opt | review_incl | review_random_expected | tie_rate | max_unique_share | used_codes_mean | pos_in_graph_mean | gap_C_mean_A | A_review_signal | A_gap_flag | A_old_any_unexplained |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OLD_GRADED | 0/25 (0%) | 25/25 (100%) | 25/25 (100%) | 1/25 (4%) | 25/25 (100%) | 17/25 (68%) | 0.4533 | 25/25 (100%) | 0.0 | 3.96 | 3.96 | 1.48 | 0/25 (0%) | 25/25 (100%) | 25/25 (100%) |
| NEW_GRADED | 0/25 (0%) | 25/25 (100%) | 6/25 (24%) | 1/25 (4%) | 25/25 (100%) | 17/25 (68%) | 0.2667 | 25/25 (100%) | 0.0 | 4.72 | 4.72 | 1.48 | 0/25 (0%) | 25/25 (100%) | 25/25 (100%) |
| NEW_SPEC | 0/25 (0%) | 25/25 (100%) | 25/25 (100%) | 1/25 (4%) | 25/25 (100%) | 17/25 (68%) | 0.2667 | 25/25 (100%) | 0.0 | 4.72 | 4.72 | 1.48 | 0/25 (0%) | 25/25 (100%) | 25/25 (100%) |

## Myocarditis
| 팔 | top1_pess | top1_opt | top3_pess | alt_first_pess | alt_first_opt | review_incl | review_random_expected | tie_rate | max_unique_share | used_codes_mean | pos_in_graph_mean | gap_C_mean_A | A_review_signal | A_gap_flag | A_old_any_unexplained |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OLD_GRADED | 0/25 (0%) | 24/25 (96%) | 24/25 (96%) | 0/25 (0%) | 24/25 (96%) | 16/25 (64%) | 0.5467 | 25/25 (100%) | 0.0 | 4.92 | 3.92 | 0.6 | 1/25 (4%) | 15/25 (60%) | 15/25 (60%) |
| NEW_GRADED | 0/25 (0%) | 24/25 (96%) | 24/25 (96%) | 0/25 (0%) | 24/25 (96%) | 16/25 (64%) | 0.5467 | 25/25 (100%) | 0.0 | 4.92 | 3.92 | 0.6 | 1/25 (4%) | 15/25 (60%) | 15/25 (60%) |
| NEW_SPEC | 0/25 (0%) | 24/25 (96%) | 24/25 (96%) | 0/25 (0%) | 24/25 (96%) | 16/25 (64%) | 0.5467 | 25/25 (100%) | 0.0 | 4.92 | 3.92 | 0.6 | 1/25 (4%) | 15/25 (60%) | 15/25 (60%) |

## Tuberculosis
| 팔 | top1_pess | top1_opt | top3_pess | alt_first_pess | alt_first_opt | review_incl | review_random_expected | tie_rate | max_unique_share | used_codes_mean | pos_in_graph_mean | gap_C_mean_A | A_review_signal | A_gap_flag | A_old_any_unexplained |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OLD_GRADED | 20/25 (80%) | 25/25 (100%) | 25/25 (100%) | 21/25 (84%) | 25/25 (100%) | 24/25 (96%) | 0.8667 | 5/25 (20%) | 0.8 | 3.52 | 3.52 | 0.0 | 0/25 (0%) | 0/25 (0%) | 0/25 (0%) |
| NEW_GRADED | 20/25 (80%) | 25/25 (100%) | 25/25 (100%) | 21/25 (84%) | 25/25 (100%) | 24/25 (96%) | 0.8667 | 5/25 (20%) | 0.8 | 3.52 | 3.52 | 0.0 | 0/25 (0%) | 0/25 (0%) | 0/25 (0%) |
| NEW_SPEC | 20/25 (80%) | 25/25 (100%) | 25/25 (100%) | 21/25 (84%) | 25/25 (100%) | 24/25 (96%) | 0.8667 | 5/25 (20%) | 0.8 | 3.52 | 3.52 | 0.0 | 0/25 (0%) | 0/25 (0%) | 0/25 (0%) |

## 1위 분포(조건 무관, 환자별)

- OLD_GRADED: {'TIE2': 8, 'TIE3': 56, 'UNIQUE:Tuberculosis': 36}
- NEW_GRADED: {'TIE2': 17, 'TIE3': 32, 'TIE4': 24, 'UNIQUE:Tuberculosis': 27}
- NEW_SPEC: {'TIE2': 8, 'TIE3': 56, 'UNIQUE:Tuberculosis': 36}

## 지식원 풍부도(질환별 SUGGESTS 간선 수)
- OLD {'Myocarditis': {'dismech': 12, 'hsdn': 8}, 'Pericarditis': {'dismech': 11, 'hsdn': 6}, 'Pulmonary embolism': {'dismech': 12, 'hsdn': 17}, 'Tuberculosis': {'dismech': 10, 'hsdn': 8}}
- NEW {'Myocarditis': {'dismech': 12, 'hsdn': 8}, 'Pericarditis': {'dismech': 11, 'hsdn': 6}, 'Pulmonary embolism': {'dismech': 12, 'hsdn': 17}, 'Tuberculosis': {'dismech': 10, 'hsdn': 8}}