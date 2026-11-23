# 검증 결과 — IMPLEMENTATION CHECK

임상 정확도가 아니다. 기준 표시는 세션 1인(비전문가)이라 정답률이 아니다. 사전 확률은 실행 확인용 가정.

## 합성 검사
- 테스트 48개, 결과 OK(입력 유형 1~12, 표현 5종, 시간 사례 포함)
- 변이 18종, 생존 []
- Temporal Consistency: 합성 사례에서 공개·정정·가설 변경이 기대와 일치, EXP-03 엔진 대조 일치(테스트 1건, 사례 1개)

## 처음 보는 공개 문장 1차(코드 동결 후 기준 먼저 고정, 1회)
- CC BY 증례 14건에서 추출, 파일 `outputs/public_linking_results_run1_frozen.json`
- 문장 57, 대상 개념 포함 26
- Concept Extraction/Linking Coverage(대상 개념 6종): 28/34 = 0.824
- 언급 상태가 주석과 일치: 28건 중 0.857
- Unsupported Mapping(주석에 없는 대상 개념 연결): 0
- Evidence Relation Coverage(주석상 관계 경로): 6/12 = 0.500, 주석에 없는 경로 4
- 출력 방향: {'ABSTAIN': 97, 'WEAKEN': 4, 'NO_CLEAR_EFFECT': 3, 'INSUFFICIENT_EVIDENCE': 4, 'UNCERTAIN': 1}
- 기권 사유: {'NO_VERIFIED_RELATION': 46, 'DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE': 10, 'AMBIGUOUS_CONCEPT': 15, 'ASSOCIATION_ONLY_NO_VERIFIED_DIRECTION': 5, 'TEST_NAME_WITHOUT_RESULT': 6, 'DVT_NOT_PROXIMAL_ULTRASOUND_CONFIRMED': 3, 'VALUE_WITHOUT_ASSAY_INTERPRETATION': 1, 'HISTORICAL_FINDING': 11}
- Provenance Completeness: 12/12
- 모호 처리 15, HPO 연결 62(그래프 안 8)
- 오류 유형: {'MISSED_CONCEPT': 6, 'MISSED_RELATION_PATH': 6, 'EXTRA_RELATION_PATH': 4, 'ASSERTION_DIFF': 4}
- **잘못된 약화: WEAKEN 4건 중 3건 [(13, 'PE-DDIMER-NORMAL'), (23, 'PE-DDIMER-NORMAL'), (53, 'PE-DDIMER-NORMAL')]** — 상승 D-dimer 를 같은 문장의 다른 'normal' 로 오판. 치명적 유형으로 기록

## 1차 후 수정(1차 문장으로 재평가하지 않음)
- D-dimer 해석 범위를 언급 주변으로 제한, 충돌 시 기권
- CT 검사명·복수형·하이픈 변형 추가, 수식어 HPO 제외, 'ruled out chronic' 부분 음성, 위험 점수·잠정 진단 불확실 처리, 검사명 부정 제외

## 처음 보는 공개 문장 2차(수정 후, 새 문서)
- 문장 65, 대상 개념 포함 46
- Concept Extraction/Linking Coverage(대상 개념 6종): 42/54 = 0.778
- 언급 상태가 주석과 일치: 42건 중 0.786
- Unsupported Mapping(주석에 없는 대상 개념 연결): 5
- Evidence Relation Coverage(주석상 관계 경로): 7/10 = 0.700, 주석에 없는 경로 1
- 출력 방향: {'ABSTAIN': 92, 'UNCERTAIN': 1, 'NO_CLEAR_EFFECT': 4, 'SUPPORT': 2, 'WEAKEN': 1}
- 기권 사유: {'TEST_NAME_WITHOUT_RESULT': 23, 'ASSOCIATION_ONLY_NO_VERIFIED_DIRECTION': 7, 'EXTRACTOR_CONFLICT': 2, 'AMBIGUOUS_CONCEPT': 19, 'NO_VERIFIED_RELATION': 12, 'DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE': 6, 'NO_RESULT_YET': 4, 'DDIMER_RESULT_NOT_STATED': 1, 'UNCERTAIN_REPORT': 1, 'HISTORICAL_FINDING': 4, 'VALUE_WITHOUT_ASSAY_INTERPRETATION': 5, 'DVT_NOT_PROXIMAL_ULTRASOUND_CONFIRMED': 4, 'FILLING_DEFECT_SITE_OR_STATE_UNCLEAR': 3, 'TEST_PURPOSE_NOT_RESULT': 1}
- Provenance Completeness: 8/8
- 모호 처리 19, HPO 연결 25(그래프 안 8)
- 오류 유형: {'ASSERTION_DIFF': 9, 'UNSUPPORTED_MAPPING': 5, 'MISSED_CONCEPT': 12, 'MISSED_RELATION_PATH': 3, 'EXTRA_RELATION_PATH': 1}

## 측정하지 않은 것
- Correct Concept Link Rate(전문가 기준 없음, 주석 일치만)
- 임상 판단 정확도, 전문가 일치, SCT 재평가(노출 자료)
- End-to-End Executable Coverage 는 관계 경로 커버리지와 합성 사례로 대신 보고
