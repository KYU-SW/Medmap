# 사례 구조화 스키마 (프롬프트 5절 25항목)

각 사례 = JSON 1개 (`clinical-cases/structured/CASE_xx.json`). 원문 근거 없는 칸 = `"UNKNOWN"` 또는 `"NOT_EVALUATED"`.

| # | 키 | 내용 |
|---|---|---|
| 1 | case_id | |
| 2 | source | URL/DOI/PMCID, 접근일 |
| 3 | source_license | 라이선스 원문 문구 |
| 4 | case_type | REAL_WITH_PREF / REAL_NO_PREF / GUIDELINE_VIGNETTE / SYNTHETIC_STRESS |
| 5 | comorbidities | |
| 6 | known_clinical | 원문에 있는 값(값·단위·원문 위치) |
| 7 | unknown_clinical | 지침 적용에 필요하지만 원문에 없는 값 |
| 8 | applicable_guidelines | 지침명·판·절 |
| 9 | conditional_recommendations | 적용 조건 + 조건 변수 |
| 10 | potential_conflicts | 실제/조건부 |
| 11 | complementary_recommendations | 보완·중복 |
| 12 | patient_goals | 원문 |
| 13 | confirmed_preferences | 원문 |
| 14 | unconfirmed_preferences | |
| 15 | treatment_burden | |
| 16 | applicable_evidence | 시험·근거 |
| 17 | evidence_scope_limits | B10 |
| 18 | decidable_now | |
| 19 | must_not_decide_now | |
| 20 | decision_changing_conditions | |
| 21 | info_to_confirm | |
| 22 | confirm_priority | 근거(판단 변화 여부·비용·부담) |
| 23 | per_judgement_sources | |
| 24 | gold_level | A/B/C/D 각각 AVAILABLE / RESEARCHER_ONLY / NOT_AVAILABLE |
| 25 | expert_review_needed | |

추가: `b7_b9_interaction` — 선호 변화 시 (a) 적용 권고 집합 변화 (b) 우선순위만 변화 (c) 보류 조건 변화 중 무엇인지. `b10_split` — 근거 부족 vs 선호 미확인 원인 분리.
