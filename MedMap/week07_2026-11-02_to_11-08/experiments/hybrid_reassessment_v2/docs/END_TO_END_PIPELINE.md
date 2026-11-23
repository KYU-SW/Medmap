# End-to-End 경로 (`hybrid2/pipeline.py`, `demo_end_to_end.py`)

```
문서 텍스트 → split_clauses(구역·문장·절)
 → find_mentions / find_ambiguous(개념 연결)
 → classify_assertion(언급 상태)
 → codes·graph_node(표준·그래프 연결)
 → finding_state(관계 조회 키, v3b 대조)
 → relations.lookup(가설별 검증 관계)
 → relations.apply(맥락 확인)
 → assess_record(방향·출처·기권 사유)
 → CaseTimeline.state(as_of 공개, 정정, 가설 이력, 검사 상태)
```

## 재사용 방식
- Hybrid v1 `temporal`·`schema` import, EXP-03 `reassess.graph()`(EXP-01b 그래프 읽기), `ct_bridge.classify`(v3b). 원본 무수정.
- 그래프 간선은 `graph_edges_shown` 으로 표시만, `used_for_direction=false`.

## 실행 예(합성, `outputs/end_to_end_trace.json`)
가설 PE, 사전 확률 중간(입력값).
| T | 공개 문서 | 검사 상태 | 지지 | 약화 | 재검토 후보 |
|---|---|---|---|---|---|
| 0.5 | 없음 | NOT_ORDERED | - | - | 아니오 |
| 1 | 주문 메모 | ORDERED | - | - | 아니오 |
| 2 | 주문 메모 | PENDING | - | - | 아니오 |
| 4 | 음성 판독 | RESULT_AVAILABLE | - | PE-CTPA-NEGATIVE | 예 |
| 7 | 정정 판독(양성) | RESULT_AVAILABLE | PE-CTPA-POSITIVE | - | 아니오 |
정정은 T=7 부터 적용되고 T=4 결과를 소급 변경하지 않는다. 같은 흐름을 EXP-03 엔진과 대조하는 테스트가 있다.

## 출력 필드
입력 문장, 표현, 개념, 표준 코드, 그래프 노드, 언급 상태, 가설, 방향, 판단 가능 여부, 관계 ID·종류, 출처(인용 포함), 적용 범위, 불확실성, 기권 사유, 부족 맥락, 관찰·이용 가능 시각, 의사 확인 필요. 확률·점수 없음.
