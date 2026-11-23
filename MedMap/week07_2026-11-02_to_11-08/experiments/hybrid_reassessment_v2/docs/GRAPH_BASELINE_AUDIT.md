# 기존 그래프 실제 구성과 138·94 차이

근거: `graph_audit.py` 실행(`outputs/graph_audit.json`), 보관 코드 `archive/exp01b_pre35_modules`, 기록 `real_demo_*/kg_meta.json`. 원본 무수정.

## 결론
138과 94 는 같은 그래프의 전처리 차이가 아니라, **코드 버전과 호출 인자가 다른 실행 스냅샷**이다. 추가로 현재 94 노드 그래프의 **간선 수가 우연히 138** 이어 혼동을 키웠다.

| 스냅샷 | 코드 | `extra_hp_nodes` | discriminators | 노드 | 간선 |
|---|---|---|---|---|---|
| 34회차 기록 | pre35 보관본 | 매핑 사용 HP 68개 | 없음 | **138** | 136 (재현 일치) |
| 35회차 기록 | explore1 보관본 | 매핑 사용 HP 51개 | 없음 | 121 | 130 (재현 일치) |
| 현재 코드 | 현재 | 매핑 사용 HP 55개 | 없음 | 122 | 130 |
| 현재 코드 | 현재 | 없음 | 없음 | 78 | 114 |
| 현재 코드 | 현재 | 없음 | 있음 | 91 | 138 |
| **EXP-03·Hybrid 실행** | 현재 | 3개 | 있음 | **94** | **138** |

## 변화 내용
- 138→121: 35회차 매핑 정리로 질환 간선이 없는 소견 노드와 IS_A 간선 감소(FINDING 114→97, IS_A 29→24), SUGGESTS 1개 감소(85→84).
- pre35 대비 현재(매핑 사용 기준): 옛 그래프에만 있는 노드 17개, 새 그래프에만 있는 노드 1개(`HP:6000840`). 목록은 JSON.
- 94 는 DDXPlus 매핑 노드를 넣지 않아 소견 노드가 적고, discriminators 로 RULE 4·PART_OF 13·GATES 1 이 더해짐.

## 현재 실행 그래프(94 노드, 138 간선)
- 종류: DISEASE 4, FINDING 65, RISK_FACTOR 9, TEST 11, HISTORY 1, RULE 4.
- 관계: SUGGESTS 92, PART_OF 13, IS_A 10, RISK_FACTOR_FOR 9, EVALUATES 11, DIFFERENTIAL_OF 2, GATES 1.
- PE 로 들어오는 간선 37(SUGGESTS 30, RISK_FACTOR_FOR 3, EVALUATES 3, DIFFERENTIAL_OF 1). 그중 HSDN 공출현 표시 17.
- 약화 간선 0. 메타 기록도 `ARGUES_AGAINST: 실제 출처 없음`.

## 의학적 신뢰성 판단
- SUGGESTS 는 HSDN 공출현과 DisMech(AI 큐레이션)가 섞여 있어 방향 근거로 쓰지 않는다. v2 는 ASSOCIATED_WITH 로 표시만 한다.
- `CONCEPT:ctpa_filling_defect → PE` 는 `quote_check=NO_QUOTE`. 근거 확인 전 지지로 쓰지 않는다.
- 그래프를 병합하지 않았고, 파일을 고치지 않았다.
