# Hybrid v2 Clinical Context & Assertion Safety Patch (P1)

회귀 확인 기록이다. 노출된 문장을 다시 돌린 결과라 독립 평가가 아니고, 임상 정확도가 아니다. 임상 확률·의심 여부는 실행 가정이다.

## 범위
- `hybrid2/`·`knowledge/evidence_relations.json`·`tests/test_pipeline.py`·기존 결과 무수정. 패치는 `hybrid2_p1/`, `knowledge/evidence_relations_p1.json`
- 원본과의 차이: `patches/safety_patch_p1.diff`
- 2차 결과 재현 시 기준선 일치: {'directions': True, 'abstain_reasons': True, 'outputs': True}

## 지침 확인(ESC 2019 공식 페이지, 자동 도구로 읽음, 일부 절 잘림 가능)
- D-dimer 배제 문구의 대상은 의심 PE 진단 알고리즘(Figure 5 제목, §4.4)
- 읽은 범위에서 치료 중·추적·재발 평가의 D-dimer 해석 문구 없음. 그래서 '금지'가 아니라 '적용 범위 밖'으로 처리

## 회귀 테스트
- test_pipeline on hybrid2_p1: Ran 48, failures 0, errors 0
- test_safety_patch_p1 on hybrid2_p1: Ran 44, failures 0, errors 0
- ALL_OK=True
- P1 변이 26종, 생존 []

## 수정 전후
### run2_exposed
| 항목 | 수정 전 | 수정 후 |
|---|---|---|
| 문장 / 문서 | 65 / 23 | 65 / 23 |
| 출력 단위 | 100 | 100 |
| 방향 | {'ABSTAIN': 92, 'UNCERTAIN': 1, 'NO_CLEAR_EFFECT': 4, 'SUPPORT': 2, 'WEAKEN': 1} | {'ABSTAIN': 92, 'UNCERTAIN': 1, 'NO_CLEAR_EFFECT': 4, 'SUPPORT': 2, 'NOT_APPLICABLE': 1} |
| 기권 / 전체 출력 | 92/100 | 92/100 |
| 개념 찾음 / 주석 언급 | 42/54 | 41/54 |
| 언급 상태 일치 / 비교한 언급 | 33/42 | 38/41 |
| 주석에 없는 개념 연결 | 5 | 5 |
| 관계 경로 찾음 / 주석 경로 | 7/10 | 7/10 |
| 잘못 적용된 WEAKEN / SUPPORT | 1 / 0 | 0 / 0 |
| 출처 완전성(기권 제외 출력) | 8/8 | 8/8 |
| 임상 단계 판정 출력 | {} | {'UNDER_TREATMENT': 1} |

바뀐 출력 9건:

- 1번 `PE`: NEGATED/ABSTAIN/EXTRACTOR_CONFLICT → PRESENT/ABSTAIN/AMBIGUOUS_CONCEPT
- 9번 `d-dimer`: ORDERED_NOT_RESULTED/ABSTAIN/NO_RESULT_YET → PRESENT/ABSTAIN/DDIMER_RESULT_NOT_STATED
- 12번 `PE`: UNCERTAIN/ABSTAIN/UNCERTAIN_REPORT → PURPOSE_OR_DIFFERENTIAL/ABSTAIN/TEST_PURPOSE_NOT_RESULT
- 22번 `Deep venous thrombosis`: PRESENT/ABSTAIN/DVT_NOT_PROXIMAL_ULTRASOUND_CONFIRMED → NEGATED/ABSTAIN/DVT_NOT_PROXIMAL_ULTRASOUND_CONFIRMED
- 22번 `DVT`: PRESENT/ABSTAIN/DVT_NOT_PROXIMAL_ULTRASOUND_CONFIRMED → NEGATED/ABSTAIN/DVT_NOT_PROXIMAL_ULTRASOUND_CONFIRMED
- 32번 `Pulmonary embolism`: PRESENT/ABSTAIN/DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE → NEGATED/ABSTAIN/DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE
- 43번 `computed tomography pulmonary angiography`: PRESENT/ABSTAIN/TEST_NAME_WITHOUT_RESULT → ORDERED_NOT_RESULTED/ABSTAIN/NO_RESULT_YET
- 43번 `CTPA`: PRESENT/ABSTAIN/TEST_NAME_WITHOUT_RESULT → ORDERED_NOT_RESULTED/ABSTAIN/NO_RESULT_YET
- 51번 `d-dimer`: PRESENT/WEAKEN/- → PRESENT/NOT_APPLICABLE/-

수정 후 남은 언급 상태 불일치: [(12, 'DDIMER', 'PRESENT', ['UNCERTAIN']), (12, 'CTPA_STUDY', 'PRESENT', ['UNCERTAIN', 'UNCERTAIN']), (14, 'CTPA_STUDY', 'PRESENT', ['HISTORICAL'])]

### run1_exposed
| 항목 | 수정 전 | 수정 후 |
|---|---|---|
| 문장 / 문서 | 57 / 13 | 57 / 13 |
| 출력 단위 | 82 | 82 |
| 방향 | {'ABSTAIN': 70, 'WEAKEN': 2, 'NO_CLEAR_EFFECT': 5, 'UNCERTAIN': 2, 'INSUFFICIENT_EVIDENCE': 3} | {'ABSTAIN': 70, 'WEAKEN': 2, 'NO_CLEAR_EFFECT': 5, 'UNCERTAIN': 2, 'INSUFFICIENT_EVIDENCE': 3} |
| 기권 / 전체 출력 | 70/82 | 70/82 |
| 개념 찾음 / 주석 언급 | 33/34 | 33/34 |
| 언급 상태 일치 / 비교한 언급 | 33/33 | 33/33 |
| 주석에 없는 개념 연결 | 0 | 0 |
| 관계 경로 찾음 / 주석 경로 | 10/12 | 10/12 |
| 잘못 적용된 WEAKEN / SUPPORT | 0 / 0 | 0 / 0 |
| 출처 완전성(기권 제외 출력) | 12/12 | 12/12 |
| 임상 단계 판정 출력 | {} | {} |

바뀐 출력 0건:


수정 후 남은 언급 상태 불일치: []

## 해결하지 않은 문제
- 검사법·판정 기준이 문장에 없어도 의심 평가 입력이면 WEAKEN 유지(uncertainty 에 표시). 기존 테스트가 이 동작을 요구함
- 진단 맥락 입력이 실행 가정이면 문장 신호 없는 정상 D-dimer 는 WEAKEN 유지
- 같은 범위 문제가 CTPA·관류 관계에 남음: 'Follow-up CTPA showed no PE', 'Perfusion scan was normal at follow-up' → WEAKEN. 범위 밖이라 미수정
- 절 전체에 걸리는 불확실 표현(12번 D-dimer·CTPA), 'previously' 오인(14번), v3b 충돌로 기권하는 음성 판독(7번)
- PE 약어·문서 내 약어 미해결, 약어 풀이의 CTPA 언급 자체는 개념 연결로 남음
- 재발 평가의 D-dimer 문구 미확인, 혈역학 불안정·입원·임신 조건 미구현
