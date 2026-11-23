# MedMap 근거 추적 시제품 — 기술 설계

합성 환자 전용 연구용 시제품. 진단을 확정하지 않는다. 의사가 지정한 진단 가설에 대해 어떤 근거가 언제 이용 가능해졌고, 무엇을 쓰고 무엇을 뺐는지, 그에 따라 연구용 모델 점수가 어떻게 달라졌는지를 추적한다.

## 1. 구조

```
수신 기록(dict) ─► events.EventStore(추가 전용, 수집 검증) ─► replay.replay(case, as_of)
                                                              │  계보별 유효 버전 선택 + 사유 코드
                                                              ▼
                                   assess.assess(replay, DModel) ─► 근거별 독립 연구용 점수 / NOT_ASSESSED / MODEL_UNAVAILABLE
                                                              │
                         assess.diff · counterfactual · provenance_graph ─► src/server.py(127.0.0.1) ─► web/index.html
```

| 모듈 | 역할 |
|---|---|
| `medmap_demo/events.py` | 사건 모델(Event), 시각 파싱(시간대 필수), 수집 거부 코드, 추가 전용 저장소·거부 로그 |
| `medmap_demo/replay.py` | REPLAY(as_of), 계보 해석, 중복·정정·취소·무효·출처·환자·가설 연결 검사 |
| `medmap_demo/assess.py` | 연구용 점수, 결정론적 설명문, 변경 diff, 반사실(기록 제외) 비교, 출처 그래프 |
| `medmap_demo/model_adapter.py` | 기존 D 모델 읽기 전용 추론 어댑터(sha256 대조) |
| `medmap_demo/naive.py` | 비교용 단순 처리 BASE(의도적 약화, 문서 공개) |
| `medmap_demo/scenarios.py` | 시연 환자 SYN-001, 비교 실험 생성기(템플릿 11종 + 정답 시간표) |
| `src/run_compare.py` · `run_demo.py` · `server.py` | 비교 실험, 시연 계산, 시연 서버 |

## 2. 사건 모델

시각 세 가지를 분리한다(모두 시간대 포함 ISO 8601, 모르면 None — 임의로 채우지 않음).

| 시각 | 뜻 |
|---|---|
| `observed_at` | 검사·관찰이 실제로 일어난 시각(검체 채취 등) |
| `available_at` | 원천 시스템(검사실·판독·장비)이 결과를 공개한 시각. 의사 열람 시각이 아님 |
| `recorded_at` | 이 기록이 MedMap 에 도착한 시각(필수) |

- 결과 상태 `status`: ORDERED / PENDING / AVAILABLE / CORRECTED / CANCELLED / INVALID.
- 중복·정정은 상태와 분리: `lineage_id`(같은 검사 자료의 계보) + `prev_version_id`(대체하는 이전 버전). 추가 전용이라 이전 기록을 고치지 않고, 정정 관계는 조회 때 역방향으로 계산한다.
- 수집 거부(기록은 남김): INVALID_TIME(시간대 없음·파싱 실패·가용<관찰), MISSING_FIELD, INVALID_STATUS, INVALID_KIND, EMPTY_EVIDENCE, CORRECTION_WITHOUT_PREVIOUS, CORRECTION_CYCLE(자기 참조), DUPLICATE_EVENT_ID(같은 ID 다른 내용), UNKNOWN_FIELD. 같은 ID 같은 내용 재전송은 무시(IGNORED_IDEMPOTENT_RESEND).

## 3. 시간순 재생 REPLAY(as_of)

1. `recorded_at ≤ as_of` 인 기록만 '그 시점 시스템이 알던 기록'. 나중에 도착한 기록은 존재 자체를 모름(건수만 감사용).
2. 이 환자 ID 이거나 이 환자 수신 묶음(feed)에 들어온 기록을 계보별로 모은다. 같은 계보에 환자 ID 가 둘 이상이면 PATIENT_ID_CONFLICT, 묶음에 섞인 다른 환자 계보는 PATIENT_MISMATCH.
3. 정정 사슬 검사는 기존 `hybrid521.lineage`(v5-2A.1)를 그대로 호출 — 순환·이전 버전 누락·다른 계보를 가리키는 정정이면 LINEAGE_INVALID.
4. 결과 버전 중 `available_at ≤ as_of` 만 후보. 시각 모름은 TIME_UNKNOWN, 아직 공개 전은 EVIDENCE_NOT_YET_AVAILABLE.
5. 같은 계보 안 같은 내용 재전송은 DUPLICATE 역할(정본 1개). 정정 연결 없는 서로 다른 버전은 CONFLICTING_VERSIONS.
6. 머리 버전 1개: INVALID → 제외, 출처 없음 → SOURCE_UNKNOWN 보류, 가설 연결 태그 없음 → 제외, 이 버전을 대체하는 새 버전의 시각을 모르면 NEWER_VERSION_TIME_UNKNOWN 보류, 아니면 USABLE.
7. 결과 없음: 공개 전 > 시각 모름 > PENDING > ORDERED 순으로 사유.
8. 계보가 다른데 같은 자료(내용 지문 = 환자·종류·항목·관찰 시각·정규화 문장·출처): 먼저 이용 가능해진 것(동점이면 먼저 도착, 그다음 ID) 하나만 USABLE, 나머지 DUPLICATE_EVIDENCE. 다른 계보에서 이미 정정으로 대체된 버전과 같은 자료면 DUPLICATE_OF_SUPERSEDED_VERSION.
9. 모든 반복은 정렬된 키로 수행 → 같은 입력·같은 조회 시각이면 같은 결과, 입력 순서와 무관.

상태 세 가지: USABLE(AI 입력), HELD(지금은 판단 보류 — 나중에 바뀔 수 있음), EXCLUDED(근거로 쓰지 않음).

## 4. 판단 보류 ≠ 0점

- 전문의 점수 0 = '진단 가능성 변화 없음'. 판단 보류 = '지금 판단하기 어려움'.
- HELD·EXCLUDED 근거에는 점수를 만들지 않는다(`NOT_ASSESSED` + 사유, score 키 없음). 모델이 없으면 `MODEL_UNAVAILABLE`. 가짜 점수 없음.
- 모델 확률로 불확실성 임계값을 만들지 않았다(검증된 임계값 없음). 보류는 근거 유효성으로만 정한다.

## 5. 기존 AI 연결(D 모델)

- 모델: EXP-MAI-006 의 D(진단 후보 + 같은 칸 근거 문장 → 열별 TF-IDF 1~2gram → 다항 로지스틱, −2..+2). EXP-MAI-008 에서 겹별로 저장했고 006 예측과 782행 건별 일치(REPRODUCED_EXACT)를 확인한 파일.
- 사전 고정: 겹 0 하나(번호 순 첫 겹 — 성능 보고 선택 아님). 다섯 겹 결합·출력 비교 선택 없음.
- 불러오기 전 sha256 을 EXP-MAI-008 기록값과 대조(고정값 없거나 불일치면 불러오지 않음). 점수 클래스 순서·입력 열 순서 확인. `predict_proba` 만 호출, 모델·변환기 무수정.
- 근거 하나 × 진단 가설 하나 = 평가 항목 하나. 점수를 합산·평균·순위화하지 않는다.
- 모델 파일의 TF-IDF 어휘에는 ER-REASON 원문 1~2gram 이 들어 있다 → 봉인 위치에만 두고, 특징어·계수 표시나 파일 복사(저장소·web·outputs·ZIP)를 하지 않는다. `*.joblib` 은 로컬 git exclude.

## 6. 변경 추적·반사실·출처 그래프

- `diff(이전, 현재)`: 계보별 NEW_RECORD / VERSION_CHANGED / BECAME_USABLE / NO_LONGER_USABLE / STATUS_CHANGED / NOT_PRESENT_NOW 와 사유 코드에서 만든 결정론적 설명.
- `counterfactual(기록 제외)`: 그 기록을 뺐을 때 시스템 출력 차이(기술 검사). 임상 판단의 원인이라는 주장 아님.
- `provenance_graph`: 기존 v4 그래프 컨테이너(`hybrid4.graphs.Graph`)로 환자–계보–기록–정정–AI 입력 간선 구성. 다른 환자 기록은 환자 근거가 아니라 수신 묶음 간선(RECEIVED_IN_FEED).
- 지식그래프: `graph_change.kg_relation_status()` 로 검증 상태만 표시. 검증된 방향 관계가 없으므로 그래프 관계로 판단을 만들지 않는다.

## 7. 기존 기능 재사용

| 기존 코드 | 재사용 방식 | 비고 |
|---|---|---|
| `exp/hybrid_reassessment_v5_2a1/hybrid521/lineage.py` (`declarations`, `resolve`) | 정정 사슬 순환·누락 검사 그대로 호출 | 읽기 전용 import |
| `exp/hybrid_reassessment_v4/hybrid4/graphs.py` (`Graph`) | 출처 그래프 컨테이너 | 읽기 전용 import |
| `exp/medmap_graph_shift_pilot/src/graph_change.py` (`kg_relation_status`) | 지식그래프 관계 검증 상태 표시 | 읽기 전용 import |
| EXP-MAI-008 봉인 `models/fold0.joblib` | D 모델 추론 | sha256 대조, 수정 없음 |
| `exp/medmap_er_reason_ordinal/src/or_model.py` | joblib 안 클래스 해석용 경로만 | 호출 없음 |
| `medmap-web/src/doctor/fonts/wanted-sans` · 의사 화면 색 토큰 | 시연 화면 폰트·색 | 서버가 읽기 전용으로 제공 |
| `graph_change.visible/flat_state` | 재사용 안 함 | 정수 분 시각·단일 encounter·recorded_at 개념 없음 → 새 엔진에 같은 원칙(가용 시각·정정 순서)만 반영 |
| `medmap-web`(React/Vite) | 재사용 안 함 | 이 worktree 에 node_modules 없음, 패키지 설치 금지 → 표준 라이브러리 서버 + 단일 HTML |

## 8. 기존 방식과 다른 구현 요소(이번에 실제로 만든 것)

1. 이용 가능 시점 기반 진단 가설 평가: 기록 도착(recorded_at)과 결과 공개(available_at)를 모두 만족한 버전만 AI 입력. 과거 시점 재생이 그 당시 시스템 상태와 같음을 매 조회 계산.
2. 중복·정정을 반영하는 추적 가능한 증거 관리: 추가 전용 저장, 계보·버전, 계보 간 재전송 판정, 정정 전 내용 재전송 차단, 모든 제외·보류에 사유 코드.
3. AI 점수와 입력 유효성 검증의 분리: 엔진이 먼저 USABLE 을 정하고 모델은 그 근거만 받음. 보류는 점수가 아니라 사유.

기존 의료 AI 들이 이런 기능을 제공하지 않는다고 주장하지 않으며, 새로운 학문적 알고리즘을 증명했다고 주장하지 않는다.
