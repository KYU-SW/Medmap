# MedMap v4 — Patient Evidence Graph & Conditional Clinical Reasoning(PE)

A 기능 구현 완료 / B 기술 검증 완료(합성 사례) / C 임상 성능 NOT_EVALUATED.

## 구성
- `hybrid4/logic.py`: 4값 AND/OR/NOT, P2 카탈로그 → EXCLUSION GATE·REQUIRED·ALTERNATIVE·FALLBACK 분리, decide
- `hybrid4/graphs.py`: 정규화 관계 원본(그래프·평면표 공용), 질환 그래프 A, 환자 증거그래프 B(에피소드·기록·증거·사실·검사 사건·정정·AI 후보)
- `hybrid4/reason.py`: A·B 연결 추론, 공용 평가 함수 evaluate_one, 근거 종합(합산 없음), 미설명 소견 상태, 재검토 트리
- `hybrid4/flat.py`: 평면 규칙표 기준선(같은 관계·연관·질환 범위·평가 함수·출력)

## 우선순위 처리
- EXCLUSION GATE(카탈로그의 방향 규칙 앞 비방향 규칙): TRUE → 그 결과, UNKNOWN/CONFLICT → 방향 판단 보류(HOLD)
- v3 덧층 혈역학 불안정 제외는 카탈로그 필수 조건이 아니라 BLOCK_ONLY_IF_TRUE(명시된 경우만 차단, 부족 정보로 세지 않음) — 전문가 검토 필요
- REQUIRED(방향 경로 공통) AND, ALTERNATIVE(경로별) OR. 카탈로그의 OR 관계: ['PE-DDIMER-NORMAL']
- FALLBACK(방향 규칙 뒤 비방향 규칙): 방향 경로가 TRUE 가 아닐 때만
- 값이 모두 확정된 조합에서 P2 apply 와 v4 decide 결과 동일(테스트 CatalogConversion)

## 보존
- v4 코드 첫 파일 시각: 2026-11-06 11:55
- v3 종료(V3_REPORT) 이후 v1·v2·v3·EXP-01b·EXP-03 변경 파일 수: 0
- v3 종료 이후 v4 외 exp 변경 파일 수: 0
- v2 원본·P1·P2 시작 해시: 28/28 일치
- 1차 동결 사본: 5/5 일치
- v3 테스트: OK
- v2 테스트 전체: Ran 124 tests in 2.588s OK
- git commit: 없음

## TEST A 검증 관계 비활성화
- A_disable_PE-CTPA-POSITIVE: 바뀐 출력 4, 모두 해당 관계 의존 True
- A_disable_PE-CTPA-NEGATIVE: 바뀐 출력 7, 모두 해당 관계 의존 True
- A_disable_PE-DDIMER-NORMAL: 바뀐 출력 4, 모두 해당 관계 의존 True

## TEST B 환자 증거 제거: 사라진 항목 {'h1|EV:u1:0|TEST_NAME_WITHOUT_RESULT': 'ABSTAIN', 'h1|EV:u1:1|PE-PROXIMAL-DVT': 'SUPPORT'}, 다른 항목 변화 {}

## TEST C 에피소드 변경
- r2_in_E2: {'E0': [], 'E2': [['UNCERTAIN', 'PE-CTPA-NEGATIVE', 'EXCLUSION_GATE_TRUE']]}
- r2_relinked_E0: {'E0': [['NOT_APPLICABLE', 'PE-CTPA-NEGATIVE', 'EPISODE_TARGET_GATE']], 'E2': []}
- u1_unresolved: [{'evidence_id': 'EV:u1:0', 'surface': 'pulmonary embolism', 'source_record_id': 'u1'}]
- u1_relinked_E2: {'E0': [], 'E2': [['UNCERTAIN', 'PE-CTPA-NEGATIVE', 'EXCLUSION_GATE_TRUE']]}

## TEST D·E 그래프 vs 평면 규칙표
- 판단 항목 61, 방향 일치 61, 항목 키 동일 True, 조건 추적·출처·부족 정보 동일 True
- 조건 구조 동일: True
- 공정성 조정(개발 중 발견): 처음엔 평면표에 기존 그래프의 표시용 연관·질환 범위가 없어 보류 사유 라벨 6건이 달랐음 → 같은 목록을 평면표에도 제공 후 완전 일치
- 실행 시간(전체 사례 1회, 5회 평균): 그래프 0.002s, 평면 0.0018s
- 코드 줄 수: {'logic': 224, 'graphs': 307, 'reason': 235, 'flat': 34}
- 관계 수정 지점: 둘 다 P2 카탈로그 1곳(normalized_relations 에서 파생)

## TEST F 출처 추적: {'graph': {'directional': 8, 'complete': 8, 'graph_chain': 8}, 'flat': {'directional': 8, 'complete': 8, 'graph_chain': 0}}

## v3 대비 출력 차이(같은 사례)
- 차이 10건, 원인 {'EPISODE_LINK_POLICY': 7, 'WD_POLICY': 3}
  - C08_past_vs_recurrence E0 u1 `pulmonary embolism` v3 NOT_APPLICABLE → v4 None : EPISODE_LINK_POLICY: 기록이 이 가설의 에피소드에 연결되지 않음(다른 에피소드 또는 UNRESOLVED)
  - C08_past_vs_recurrence E0 n2 `dyspnea` v3 ABSTAIN → v4 None : EPISODE_LINK_POLICY: 기록이 이 가설의 에피소드에 연결되지 않음(다른 에피소드 또는 UNRESOLVED)
  - C08_past_vs_recurrence E0 n2 `recurrent pulmonary embolism` v3 ABSTAIN → v4 None : EPISODE_LINK_POLICY: 기록이 이 가설의 에피소드에 연결되지 않음(다른 에피소드 또는 UNRESOLVED)
  - C08_past_vs_recurrence E0 r2 `pulmonary embolism` v3 NOT_APPLICABLE → v4 None : EPISODE_LINK_POLICY: 기록이 이 가설의 에피소드에 연결되지 않음(다른 에피소드 또는 UNRESOLVED)
  - C08_past_vs_recurrence E2 n0 `Pulmonary embolism` v3 ABSTAIN → v4 None : EPISODE_LINK_POLICY: 기록이 이 가설의 에피소드에 연결되지 않음(다른 에피소드 또는 UNRESOLVED)
  - C08_past_vs_recurrence E2 n0 `anticoagulation` v3 ABSTAIN → v4 None : EPISODE_LINK_POLICY: 기록이 이 가설의 에피소드에 연결되지 않음(다른 에피소드 또는 UNRESOLVED)
  - C08_past_vs_recurrence E2 u1 `pulmonary embolism` v3 NOT_APPLICABLE → v4 None : EPISODE_LINK_POLICY: 기록이 이 가설의 에피소드에 연결되지 않음(다른 에피소드 또는 UNRESOLVED)
  - C15_working_dx_vs_ai_candidate E1 n1 `Pleuritic chest pain` v3 ABSTAIN → v4 None : WD_POLICY: 의사 미확인 가설은 v4 에서 평가 안 함
  - C15_working_dx_vs_ai_candidate E1 n1 `Pulmonary embolism` v3 ABSTAIN → v4 None : WD_POLICY: 의사 미확인 가설은 v4 에서 평가 안 함
  - C15_working_dx_vs_ai_candidate E1 r1 `pulmonary embolism` v3 ABSTAIN → v4 None : WD_POLICY: 의사 미확인 가설은 v4 에서 평가 안 함

## 사례 요약(그래프 모드)
- C01_single_positive@5.0 h1(E1, 사용 True): ['r1:PE-CTPA-POSITIVE=SUPPORT']
- C02_single_negative@5.0 h1(E1, 사용 True): ['r1:PE-CTPA-NEGATIVE=WEAKEN']
- C03_multiple_evidence@5.0 h1(E1, 사용 True): ['u1:PE-PROXIMAL-DVT=SUPPORT', 'l1:PE-DDIMER-ELEVATED=NO_CLEAR_EFFECT', 'r1:PE-CTPA-NEGATIVE=WEAKEN']
- C04_and_partly_unknown@5.0 h1(E1, 사용 True): ['r1:PE-CTPA-NEGATIVE=INSUFFICIENT_EVIDENCE']
- C05_and_explicit_false@2.0 h1(E1, 사용 True): ['l1:PE-DDIMER-NORMAL=NOT_APPLICABLE']
- C05b_required_false_fallback@5.0 h1(E1, 사용 True): ['r1:PE-CTPA-POSITIVE=UNCERTAIN']
- C06a_or_path_intermediate_elisa@2.0 h1(E1, 사용 True): ['l1:PE-DDIMER-NORMAL=WEAKEN']
- C06b_or_path_low_moderate@2.0 h1(E1, 사용 True): ['l1:PE-DDIMER-NORMAL=WEAKEN']
- C06c_or_gate_intermediate_moderate@2.0 h1(E1, 사용 True): ['l1:PE-DDIMER-NORMAL=NOT_APPLICABLE']
- C07_conflicting_records@5.0 h1(E1, 사용 True): ['r1:PE-CTPA-NEGATIVE=INSUFFICIENT_EVIDENCE']
- C08_past_vs_recurrence@203.0 h0(E0, 사용 True): 방향 관련 항목 없음 / 미해결 연결 ['u1']
- C08_past_vs_recurrence@203.0 h3(E2, 사용 True): ['r2:PE-CTPA-NEGATIVE=UNCERTAIN'] / 미해결 연결 ['u1']
- C09_post_treatment_followup@95.0 h0(E0, 사용 True): ['r9:PE-CTPA-NEGATIVE=NOT_APPLICABLE', 'p9:PE-PERFUSION-NORMAL=NOT_APPLICABLE']
- C10_delayed_result@1.5 h1(E1, 사용 True): 방향 관련 항목 없음
- C10_delayed_result@3.0 h1(E1, 사용 True): 방향 관련 항목 없음
- C10_delayed_result@4.0 h1(E1, 사용 True): ['r1:PE-CTPA-POSITIVE=SUPPORT']
- C11_correction@6.9 h1(E1, 사용 True): ['r1:PE-CTPA-POSITIVE=SUPPORT']
- C11_correction@7.0 h1(E1, 사용 True): ['r2:PE-CTPA-NEGATIVE=WEAKEN']
- C12_unsupported@4.0 h1(E1, 사용 True): 방향 관련 항목 없음
- C12_unsupported@4.0 h2(E1, 사용 True): 방향 관련 항목 없음
- C15_working_dx_vs_ai_candidate@5.0 h5(E1, 사용 True): 방향 관련 항목 없음
- C15_working_dx_vs_ai_candidate@5.0 h6(E1, 사용 False): 방향 관련 항목 없음

## 재검토 트리 예(C03, 섹션 요약)
```
{"working_diagnosis": "Pulmonary embolism", "hypothesis_id": "h1", "status": "WORKING_DIAGNOSIS", "physician_confirmed": true, "diagnosis_episode": {"episode_id": "E1", "kind": "CURRENT_EVALUATION"}, "as_of": 5.0, "mode": "graph", "supporting": 1, "weakening": 1, "uncertain_or_no_clear_effect": 1, "not_applicable": 0, "held_insufficient": 0, "unexplained_findings": 5, "conflicts": 0, "missing_information": 2, "unresolved_episode_evidence": 0, "ai_diagnosis_candidates_unconfirmed": 0, "medical_sources_used": 5}
{"evidence_id": "EV:r1:0", "sentence": "No evidence of pulmonary embolism.", "relation_id": "PE-CTPA-NEGATIVE", "graph_path": ["TEST:Pulmonary_Embolism:0", "STATE:CTPA_NORMAL", "REL:PE-CTPA-NEGATIVE", "WEAKENS_HYPOTHESIS", "DX:Pulmonary embolism"], "direction": "WEAKEN", "available_time": 4.0}
{"op": "AND", "value": "TRUE", "children": [{"key": "clinical_phase", "allowed": ["SUSPECTED_ACUTE_PE_EVALUATION"], "value": "TRUE", "observed": "SUSPECTED_ACUTE_PE_EVALUATION", "sources": ["n1:suspected"]}, {"key": "pretest", "allowed": ["LOW", "INTERMEDIATE"], "value": "TRUE", "observed": "INTERMEDIATE", "sources": ["n1:pretest"]}]}
```

## 그래프의 실제 기여와 한계
- 판단·조건 추적·출처: 같은 지식을 준 평면 규칙표와 완전히 같음. 의학적 판단 이점 없음
- 그래프에서만 자연스럽게 된 것: 증거→원본 기록→정정 기록 간선 순회, 에피소드→기록·증거·사실 순회, 관계→조건 요구·출처 노드 조회. 평면표도 ID 조인으로 같은 결과를 낼 수 있음(이번 비교에서 그렇게 함)
- 단점: 코드 양(graphs.py) 증가, 원본 MedGraph 의 고정 종류 목록 때문에 별도 그래프 클래스 필요

## 미구현·한계
- 증분 갱신 없음(as_of 마다 재계산). 확률·가중치 없음(의도). 에피소드 자동 연결은 메타데이터·단일 에피소드·명시 문구만
- TRUE 경로의 충돌 의존 검사는 현재 원자 구조에서 구조적으로 발생하지 않음(TRUE 인 AND 는 CONFLICT 자식을 가질 수 없음). 방어 코드로만 존재
- 미설명 소견 분류에 검사명 언급(TEST_NAME_WITHOUT_RESULT)이 섞임
- 관계 8개·조건 모두 전문의 검토 없음
