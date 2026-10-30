# EXP-01b 35회차 수정 전/후 비교(DEV1–8, TRAIN16 합성 환자, 성능 평가 아님)

- 이전 모듈: `/tmp/claude-1000/-home-<user>/a73172f3-dbf3-486c-934b-7ec1c0080609/scratchpad/pre35` · 이후 모듈: `/home/<user>/medmap-worktrees/main-ai/exp/exp01b_graph_engine` · 사례: `/home/<user>/medmap-worktrees/main-ai/exp/exp01b_graph_engine/outputs/dev_cases_20261029_1456/dev_cases.json` · 가상 WD 회전 ['Pericarditis', 'Pulmonary embolism', 'Myocarditis', 'Tuberculosis']
- 간선 수 136 → 130 · 노드 {'DISEASE': 4, 'FINDING': 114, 'RISK_FACTOR': 9, 'TEST': 11} → {'DISEASE': 4, 'FINDING': 97, 'RISK_FACTOR': 9, 'TEST': 11}
- 매핑이 바뀐 DDXPlus 근거 24개(아래 사례에 등장한 것만 사례별 표시)

## DEV1-row201242 — WD DX:Pericarditis
- 그래프에 연결된 양성 근거 6 → 6 (빠짐 [], 추가 []) · 그래프 내 음성 []
- 이 사례의 매핑 변경: E_34 NOT_ASSESSED[]→NO_KB_RELATION[]
- 순위(이전 = 묶음 수 기준 · 이후 = 임상 소견 묶음 → 전체 묶음):
  - 이전: Pulmonary embolism(3) > Tuberculosis(3) > Myocarditis(2) > Pericarditis(2)
  - 이후: Tuberculosis(3, 임상 3, 공출현만 0) > Pulmonary embolism(3, 임상 2, 공출현만 1) > Myocarditis(2, 임상 2, 공출현만 0) > Pericarditis(2, 임상 2, 공출현만 0)
  - 이후 묶음: Tuberculosis: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0002105}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Pulmonary embolism: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0002105}:DISMECH_NO_REF, {HP:0012531,HP:0100749}:HSDN_LITERATURE_COOCCURRENCE | Myocarditis: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Pericarditis: {HP:0002094}:DISMECH_NO_REF, {HP:0012531,HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT
- 설명 부족: [['HP:0002105', 'EXPLAINED_BY_OTHER'], ['HP:0007185', 'NARROWER_CONCEPT_LINKED'], ['HP:6000684', 'UNEXPLAINED_IN_GRAPH']] → [['HP:0002105', 'EXPLAINED_BY_OTHER'], ['HP:0007185', 'NARROWER_CONCEPT_LINKED'], ['HP:6000684', 'UNEXPLAINED_IN_GRAPH']]
- 판단 불가 근거 수: 15 → 15 · 충돌 지식: NO_KNOWLEDGE → NO_KNOWLEDGE
- 추가 검토 후보: ['DX:Myocarditis', 'DX:Pulmonary embolism', 'DX:Tuberculosis'] → ['DX:Myocarditis', 'DX:Pulmonary embolism', 'DX:Tuberculosis']
- 2단계 재계산 질환 4 → 4, 바뀐 경로 18 → 18

## DEV2-row778094 — WD DX:Pulmonary embolism
- 그래프에 연결된 양성 근거 6 → 6 (빠짐 [], 추가 []) · 그래프 내 음성 []
- 이 사례의 매핑 변경: E_34 NOT_ASSESSED[]→NO_KB_RELATION[]
- 순위(이전 = 묶음 수 기준 · 이후 = 임상 소견 묶음 → 전체 묶음):
  - 이전: Pulmonary embolism(3) > Tuberculosis(3) > Myocarditis(2) > Pericarditis(2)
  - 이후: Tuberculosis(3, 임상 3, 공출현만 0) > Pulmonary embolism(3, 임상 2, 공출현만 1) > Myocarditis(2, 임상 2, 공출현만 0) > Pericarditis(2, 임상 2, 공출현만 0)
  - 이후 묶음: Tuberculosis: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0002105}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Pulmonary embolism: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0002105}:DISMECH_NO_REF, {HP:0012531,HP:0100749}:HSDN_LITERATURE_COOCCURRENCE | Myocarditis: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Pericarditis: {HP:0002094}:DISMECH_NO_REF, {HP:0012531,HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT
- 설명 부족: [['HP:0007185', 'NARROWER_CONCEPT_LINKED'], ['HP:6000684', 'UNEXPLAINED_IN_GRAPH']] → [['HP:0007185', 'NARROWER_CONCEPT_LINKED'], ['HP:6000684', 'UNEXPLAINED_IN_GRAPH']]
- 판단 불가 근거 수: 26 → 26 · 충돌 지식: NO_KNOWLEDGE → NO_KNOWLEDGE
- 추가 검토 후보: ['DX:Pericarditis', 'DX:Pulmonary embolism'] → ['DX:Pericarditis', 'DX:Tuberculosis']
- 2단계 재계산 질환 4 → 4, 바뀐 경로 10 → 10

## DEV3-row1007063 — WD DX:Myocarditis
- 그래프에 연결된 양성 근거 3 → 2 (빠짐 ['HP:6000684'], 추가 []) · 그래프 내 음성 ['HP:6000684']
- 이 사례의 매핑 변경: E_0 NOT_ASSESSED[]→NO_KB_RELATION[]; E_3 NOT_ASSESSED[]→NO_KB_RELATION[]
- 순위(이전 = 묶음 수 기준 · 이후 = 임상 소견 묶음 → 전체 묶음):
  - 이전: Myocarditis(1) > Pericarditis(1) > Pulmonary embolism(1) > Tuberculosis(1)
  - 이후: Myocarditis(1, 임상 1, 공출현만 0) > Pericarditis(1, 임상 1, 공출현만 0) > Tuberculosis(1, 임상 1, 공출현만 0) > Pulmonary embolism(1, 임상 0, 공출현만 1)
  - 이후 묶음: Myocarditis: {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Pericarditis: {HP:0012531,HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Tuberculosis: {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Pulmonary embolism: {HP:0012531,HP:0100749}:HSDN_LITERATURE_COOCCURRENCE
- 설명 부족: [['HP:6000684', 'UNEXPLAINED_IN_GRAPH']] → []
- 판단 불가 근거 수: 22 → 21 · 충돌 지식: NO_KNOWLEDGE → NO_KNOWLEDGE
- 추가 검토 후보: ['DX:Pericarditis'] → ['DX:Pericarditis']
- 2단계 재계산 질환 0 → 0, 바뀐 경로 0 → 0

## DEV4-row268135 — WD DX:Tuberculosis
- 그래프에 연결된 양성 근거 5 → 5 (빠짐 [], 추가 []) · 그래프 내 음성 []
- 이 사례의 매핑 변경: E_0 NOT_ASSESSED[]→NO_KB_RELATION[]; E_3 NOT_ASSESSED[]→NO_KB_RELATION[]
- 순위(이전 = 묶음 수 기준 · 이후 = 임상 소견 묶음 → 전체 묶음):
  - 이전: Myocarditis(2) > Pericarditis(2) > Pulmonary embolism(2) > Tuberculosis(2)
  - 이후: Myocarditis(2, 임상 2, 공출현만 0) > Pericarditis(2, 임상 2, 공출현만 0) > Tuberculosis(2, 임상 2, 공출현만 0) > Pulmonary embolism(2, 임상 1, 공출현만 1)
  - 이후 묶음: Myocarditis: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Pericarditis: {HP:0002094}:DISMECH_NO_REF, {HP:0012531,HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Tuberculosis: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Pulmonary embolism: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0012531,HP:0100749}:HSDN_LITERATURE_COOCCURRENCE
- 설명 부족: [['HP:0001962', 'UNEXPLAINED_IN_GRAPH'], ['HP:6000684', 'UNEXPLAINED_IN_GRAPH']] → [['HP:0001962', 'UNEXPLAINED_IN_GRAPH'], ['HP:6000684', 'UNEXPLAINED_IN_GRAPH']]
- 판단 불가 근거 수: 16 → 16 · 충돌 지식: NO_KNOWLEDGE → NO_KNOWLEDGE
- 추가 검토 후보: [] → []
- 2단계 재계산 질환 4 → 4, 바뀐 경로 15 → 15

## DEV5-row838400 — WD DX:Pericarditis
- 그래프에 연결된 양성 근거 4 → 3 (빠짐 ['HP:6000684'], 추가 []) · 그래프 내 음성 ['HP:6000684']
- 이 사례의 매핑 변경: E_0 NOT_ASSESSED[]→NO_KB_RELATION[]
- 순위(이전 = 묶음 수 기준 · 이후 = 임상 소견 묶음 → 전체 묶음):
  - 이전: Myocarditis(2) > Pericarditis(2) > Pulmonary embolism(2) > Tuberculosis(2)
  - 이후: Myocarditis(2, 임상 2, 공출현만 0) > Pericarditis(2, 임상 2, 공출현만 0) > Tuberculosis(2, 임상 2, 공출현만 0) > Pulmonary embolism(2, 임상 1, 공출현만 1)
  - 이후 묶음: Myocarditis: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Pericarditis: {HP:0002094}:DISMECH_NO_REF, {HP:0012531,HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Tuberculosis: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Pulmonary embolism: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0012531,HP:0100749}:HSDN_LITERATURE_COOCCURRENCE
- 설명 부족: [['HP:6000684', 'UNEXPLAINED_IN_GRAPH']] → []
- 판단 불가 근거 수: 15 → 15 · 충돌 지식: NO_KNOWLEDGE → NO_KNOWLEDGE
- 추가 검토 후보: ['DX:Myocarditis', 'DX:Pulmonary embolism'] → ['DX:Myocarditis', 'DX:Pulmonary embolism']
- 2단계 재계산 질환 4 → 4, 바뀐 경로 8 → 8

## DEV6-row194181 — WD DX:Pulmonary embolism
- 그래프에 연결된 양성 근거 7 → 3 (빠짐 ['HP:0003326', 'HP:0012378', 'HP:0033834', 'HP:6000684'], 추가 []) · 그래프 내 음성 ['HP:6000684']
- 이 사례의 매핑 변경: E_0 NOT_ASSESSED[]→NO_KB_RELATION[]; E_175 EXACT['HP:0033834', 'HP:0012378', 'HP:0003326']→REVIEW[]
- 순위(이전 = 묶음 수 기준 · 이후 = 임상 소견 묶음 → 전체 묶음):
  - 이전: Tuberculosis(2) > Myocarditis(1) > Pericarditis(1) > Pulmonary embolism(1)
  - 이후: Myocarditis(1, 임상 1, 공출현만 0) > Pericarditis(1, 임상 1, 공출현만 0) > Tuberculosis(1, 임상 1, 공출현만 0) > Pulmonary embolism(1, 임상 0, 공출현만 1)
  - 이후 묶음: Myocarditis: {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Pericarditis: {HP:0012531,HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Tuberculosis: {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | Pulmonary embolism: {HP:0012531,HP:0100749}:HSDN_LITERATURE_COOCCURRENCE
- 설명 부족: [['HP:0001962', 'UNEXPLAINED_IN_GRAPH'], ['HP:0012378', 'EXPLAINED_BY_OTHER'], ['HP:0033834', 'UNEXPLAINED_IN_GRAPH'], ['HP:6000684', 'UNEXPLAINED_IN_GRAPH']] → [['HP:0001962', 'UNEXPLAINED_IN_GRAPH']]
- 판단 불가 근거 수: 30 → 30 · 충돌 지식: NO_KNOWLEDGE → NO_KNOWLEDGE
- 추가 검토 후보: ['DX:Pericarditis', 'DX:Tuberculosis'] → ['DX:Myocarditis', 'DX:Pericarditis', 'DX:Tuberculosis']
- 2단계 재계산 질환 4 → 4, 바뀐 경로 9 → 8

## DEV7-row91145 — WD DX:Myocarditis
- 그래프에 연결된 양성 근거 3 → 3 (빠짐 [], 추가 []) · 그래프 내 음성 []
- 이 사례의 매핑 변경: E_44 NOT_ASSESSED[]→NO_KB_RELATION[]
- 순위(이전 = 묶음 수 기준 · 이후 = 임상 소견 묶음 → 전체 묶음):
  - 이전: Tuberculosis(3) > Pulmonary embolism(2) > Myocarditis(1) > Pericarditis(1)
  - 이후: Tuberculosis(3, 임상 2, 공출현만 1) > Pulmonary embolism(2, 임상 1, 공출현만 1) > Myocarditis(1, 임상 1, 공출현만 0) > Pericarditis(1, 임상 1, 공출현만 0)
  - 이후 묶음: Tuberculosis: {HP:0001824}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0012735}:HSDN_LITERATURE_COOCCURRENCE | Pulmonary embolism: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0012735}:HSDN_LITERATURE_COOCCURRENCE | Myocarditis: {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT | Pericarditis: {HP:0002094}:DISMECH_NO_REF
- 설명 부족: [['HP:0001824', 'EXPLAINED_BY_OTHER'], ['HP:0012735', 'EXPLAINED_BY_OTHER']] → [['HP:0001824', 'EXPLAINED_BY_OTHER'], ['HP:0012735', 'EXPLAINED_BY_OTHER']]
- 판단 불가 근거 수: 22 → 21 · 충돌 지식: NO_KNOWLEDGE → NO_KNOWLEDGE
- 추가 검토 후보: ['DX:Pericarditis', 'DX:Pulmonary embolism', 'DX:Tuberculosis'] → ['DX:Pericarditis', 'DX:Pulmonary embolism', 'DX:Tuberculosis']
- 2단계 재계산 질환 4 → 4, 바뀐 경로 9 → 9

## DEV8-row185305 — WD DX:Tuberculosis
- 그래프에 연결된 양성 근거 5 → 5 (빠짐 [], 추가 []) · 그래프 내 음성 []
- 이 사례의 매핑 변경: E_2 NOT_ASSESSED[]→NO_KB_RELATION[]; E_44 NOT_ASSESSED[]→NO_KB_RELATION[]
- 순위(이전 = 묶음 수 기준 · 이후 = 임상 소견 묶음 → 전체 묶음):
  - 이전: Tuberculosis(5) > Pulmonary embolism(4) > Myocarditis(2) > Pericarditis(2)
  - 이후: Tuberculosis(5, 임상 4, 공출현만 1) > Pulmonary embolism(4, 임상 2, 공출현만 2) > Pericarditis(2, 임상 2, 공출현만 0) > Myocarditis(2, 임상 1, 공출현만 1)
  - 이후 묶음: Tuberculosis: {HP:0001824}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0001945}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0002105}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0012735}:HSDN_LITERATURE_COOCCURRENCE | Pulmonary embolism: {HP:0001945}:HSDN_LITERATURE_COOCCURRENCE, {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT, {HP:0002105}:DISMECH_NO_REF, {HP:0012735}:HSDN_LITERATURE_COOCCURRENCE | Pericarditis: {HP:0001945}:DISMECH_NO_REF, {HP:0002094}:DISMECH_NO_REF | Myocarditis: {HP:0001945}:HSDN_LITERATURE_COOCCURRENCE, {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT
- 설명 부족: [] → []
- 판단 불가 근거 수: 11 → 11 · 충돌 지식: NO_KNOWLEDGE → NO_KNOWLEDGE
- 추가 검토 후보: [] → []
- 2단계 재계산 질환 4 → 4, 바뀐 경로 17 → 17

## 매핑 변경 전체
| 근거 | 이전 | 이후 |
|---|---|---|
| E_0 | NOT_ASSESSED [] | NO_KB_RELATION [] |
| E_2 | NOT_ASSESSED [] | NO_KB_RELATION [] |
| E_3 | NOT_ASSESSED [] | NO_KB_RELATION [] |
| E_30 | EXACT ['HP:0003270', 'HP:6000319'] | REVIEW [] |
| E_34 | NOT_ASSESSED [] | NO_KB_RELATION [] |
| E_37 | NOT_ASSESSED [] | NO_KB_RELATION [] |
| E_44 | NOT_ASSESSED [] | NO_KB_RELATION [] |
| E_51 | EXACT ['HP:0002014'] | REVIEW [] |
| E_63 | EXACT ['HP:0001260'] | REVIEW [] |
| E_65 | EXACT ['HP:0002015'] | REVIEW [] |
| E_77 | EXACT ['HP:0033709', 'HP:0034777'] | REVIEW [] |
| E_93 | EXACT_BROADER ['HP:0003401'] | REVIEW [] |
| E_96 | EXACT_BROADER ['HP:0004324'] | REVIEW [] |
| E_156 | EXACT ['HP:0012799'] | REVIEW [] |
| E_157 | EXACT_BROADER ['HP:0003401'] | REVIEW [] |
| E_164 | EXACT_BROADER ['HP:0011675'] | EXACT_BROADER ['HP:0001962'] |
| E_167 | NOT_ASSESSED [] | NO_KB_RELATION [] |
| E_173 | EXACT_BROADER ['HP:0002020'] | REVIEW [] |
| E_175 | EXACT ['HP:0033834', 'HP:0012378', 'HP:0003326'] | REVIEW [] |
| E_211 | EXACT_BROADER ['HP:0002013'] | REVIEW [] |
| E_215 | EXACT_BROADER ['HP:0033793'] | REVIEW [] |
| E_216 | EXACT_BROADER ['HP:0025286'] | REVIEW [] |
| E_219 | EXACT ['HP:0025301'] | REVIEW [] |
| E_227 | NOT_ASSESSED [] | NO_KB_RELATION [] |