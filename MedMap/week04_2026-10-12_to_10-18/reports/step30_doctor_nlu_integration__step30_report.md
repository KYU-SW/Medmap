# STEP30 — MedMap Clinical NLU ↔ Doctor 연구용 통합 결과

> 연구용 통합 시뮬레이션. 임상 정확도·안전성 검증 아님. 합성 문장, 평가 문장·규칙 작성자 동일, HUMAN_VERIFIED_GOLD = 0, PRODUCTION_READY = NO.
> 의사 확인은 dummy 시뮬레이터(confirmer = DUMMY_SIMULATOR) — 실제 의사 검증으로 세지 않음.

## 판정
- STEP30_RESULT = **REGRESSION**
- STEP31_READINESS = **NO_GO**
- PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0
- NLU_SCHEMA_VALIDITY = PASS(위반 0 · 사례 82 · NLU mention 138 · 필수 16필드 중 NLU 직접 13, 어댑터 생성 3)
- DOCTOR_ADAPTER_VALIDITY = PASS(packet item 138, 범주 {'A': 60, 'B': 6, 'C': 9, 'D': 15, 'E': 9, 'F': 10, 'G': 11, 'H': 18})
- RAW_PRESERVATION = PASS(G1 위반 0) · offset PASS(G2 위반 0)
- MODEL_INPUT_ISOLATION = PASS(자동 모델 입력 0 — applied=false 전 사례 · STAGE_A 59건은 표시만)
- SILVER_ISOLATION = PASS(위반 0)
- NEGATED_INPUT_VIOLATIONS = 0 · HISTORICAL_INPUT_VIOLATIONS = 0 · OTHER_PERSON_INPUT_VIOLATIONS = 0 · UNKNOWN_INPUT_VIOLATIONS = 0
- EVIDENCE_MAPPING_CONFLICTS = 0
- BLIND_WORKFLOW_VIOLATIONS = 2
- MULTI_SPAN_PRESERVATION = 복수 기대 사례 42 중 기대 구문이 서로 다른 item 에 대응 42
- END_TO_END_TESTS = 사례 82(노출 회귀 10 + 새 통합 72) 실행 · 단위 테스트 34개 PASS
- CPU_P95 = 74.544 ms(조건 A pilot274 전체 경로 NLU+검색+어댑터+직렬화, p50 33.866 ms)
- 재현성 = SHA_IDENTICAL 
- 판정 규칙 = data/prereg_gates.json(평가 전 고정, SHA 는 data/prereg_freeze.json)

## EXPLORATORY(공식 판정 아님) — G10 검사기 재확인
- 공식 G10 FAIL 원인 = 공식 G10 검사기의 금지 키 'candidates' 가 NLU 원본 mention 의 증상 concept 후보 키(R10 '손이 떨려' → HP:0001337)와 겹침 — 질환 정보 노출 아님. v2 검사기(질환 예측 키는 어댑터 필드에만, 49질환 코드 값은 전체 검사)를 주입 사례 4개로 먼저 확인(오판 0) 후 공식 산출물에 적용 → v2 G10 PASS(위반 0) → EXPLORATORY 판정 PARTIAL_FEASIBILITY · STEP31 CONDITIONAL_GO. 공식 판정은 바꾸지 않음. 교훈: 검사기 키 목록을 NLU 원본 스키마와 대조하지 않고 SHA 고정함 — 다음 단계는 검사기를 실제 NLU 출력 전체 키 목록과 먼저 대조.

## Integration Safety Gate
| 게이트 | 결과 | 위반 기록 수 |
|---|---|---|
| G1 | PASS | 0 |
| G2 | PASS | 0 |
| G3 | PASS | 0 |
| G4 | PASS | 0 |
| G5 | PASS | 0 |
| G6 | PASS | 0 |
| G7 | PASS | 0 |
| G8 | PASS | 0 |
| G9 | PASS | 0 |
| G10 | FAIL | 2 |
| G11 | PASS | 0 |
| G12 | PASS | 0 |
| G13 | PASS | 0 |
| G14 | PASS | 0 |
| G15 | PASS | 0 |
| UNIT_TESTS | PASS | 0 |

- 위반 수(G3–G7)는 '자동 모델 입력 또는 STAGE_A 표시가 금지 속성에 붙은 경우'를 NLU 원본 속성으로 다시 센 값 + '전부 확인' dummy 정책에서 B·G·H·미지원·C·D·E·F 항목이 재분류 사유 없이 STAGE_B 가 된 경우.
- 자동 모델 입력은 구조상 0: 모든 사례 `model_input.applied=false`, 의사 확인 전 `stage_b`·`patient_state_delta` 비어 있음(G9).

## 성능(분모 명시)
### 새 통합 평가 72문장(INTEGRATION_NEW, 이전 단계 data 와 완전 일치 0 — 비교 문자열 42178개)
- 정상 증상 전달률 = 0.9474 (36/38) — 분모 = STAGE_A 기대 항목
- 불필요한 확인 요청률 = 0.0 (0/38) — 같은 분모에서 F 로 가거나 A 인데 STAGE_A 가 막힘
- 누락률 = 0.0106 (1/94) — 분모 = '없음' 허용이 아닌 기대 항목
- 잘못된 범주 표시율 = 0.0721 (8/111) — 분모 = 대응 item 이 있는 기대 항목
- 문맥(부정·과거·다른 사람) 보존율 = 1.0 (19/19)
- STAGE_A 표시 오류(기대 금지인데 STAGE_A + forbid 위반) = 5 · 범주 A 인데 기대 concept 와 다름 = 2
- 기대 구문과 겹치지 않는 추가 item(범주별) = {'G': 1, 'D': 2, 'E': 2, 'H': 4, 'A': 1, 'F': 1, 'C': 1} · 그중 STAGE_A = 1
### 노출 회귀 10문장(지시문 §11 — 독립 평가 아님)
- 기대 항목 15개 중 범주·STAGE_A·concept 모두 맞음 15 · 정상 전달률 1.0 (5/5) · STAGE_A 표시 오류 0

| 사례 | 문장 | item(범주, STAGE_A 대상) |
|---|---|---|
| R01 | 어제부터 코피가 나고 머리가 아파요. | '코피가 나'=B · '머리가 아파'=A(STAGE_A E_53) |
| R02 | 기침은 없는데 숨이 차요. | '기침은 없'=C · '숨이 차'=A(STAGE_A E_66) |
| R03 | 어제 열이 났어요 오늘은 괜찮아요. | '열이 났'=D |
| R04 | 엄마는 기침하고 저는 머리가 아파요. | '기침하'=E · '머리가 아파'=A(STAGE_A E_53) |
| R05 | 토했어요. | '토했'=D |
| R06 | 피를 토했어요. | '피를 토했'=D |
| R07 | 목이 아프고 숨이 차요. | '목이 아프'=A(STAGE_A E_97) · '숨이 차'=A(STAGE_A E_66) |
| R08 | 기침약을 먹었는데 기침이 계속 나요. | '기침약을 먹'=G · '기침이 계속 나'=A(STAGE_A E_201) |
| R09 | 심장 부분이요. | '심장 부분'=F |
| R10 | 손이 떨려요. | '손이 떨려'=B |

### 기대와 다른 범주(전체 세트)
| 사례 | 기대 구문 | 허용 범주 | 결과 범주 | concept | STAGE_A |
|---|---|---|---|---|---|
| N09 | 머리가 지끈거리 | A | H | - | False |
| N14 | 배는 하나도 안 아픈 | C | NONE | - | False |
| N30 | 당뇨 | G/NONE | H | - | False |
| N38 | 소화제 | G/NONE | H | - | False |
| N44 | 잠을 잘 못 자 | B/F/H | C | - | False |
| N55 | 더부룩 | A/F/B | H | - | False |
| N58 | 열이 받쳐 | G/H/F/NONE/C | A | fever | True |
| N61 | 아파 | A | H | - | False |
| N64 | 가슴 쪽이 이상 | F/H/NONE/G | A | palpitations | True |

### STAGE_A 금지 기대인데 STAGE_A 로 표시된 항목
| 사례 | 기대 구문 | 허용 범주 | 결과 범주 | concept | STAGE_A |
|---|---|---|---|---|---|
| N58 | 열이 받쳐 | G/H/F/NONE/C | A | fever | True |
| N64 | 가슴 쪽이 이상 | F/H/NONE/G | A | palpitations | True |

### 누락(대응 item 없음)
| 사례 | 기대 구문 | 허용 범주 | 결과 범주 | concept | STAGE_A |
|---|---|---|---|---|---|
| N14 | 배는 하나도 안 아픈 | C | NONE | - | False |

### 범주 A 인데 기대 concept 와 다름
| 사례 | 기대 구문 | 허용 범주 | 결과 범주 | concept | STAGE_A |
|---|---|---|---|---|---|
| N56 | 가슴이 답답 | F/A/B/H | A | palpitations | True |
| N59 | 피가 섞인 기침 | A/F | A | cough | True |

## 처리 시간·메모리(CPU, OMP 4, GPU 미사용)
- 조건 A(저부하, load 2.12) pilot 274: NLU(core3) p95 73.71 ms · 검색 계층 p95 11.587 ms · 통합 어댑터 p95 0.205 ms · JSON 직렬화 p95 0.105 ms · 전체 p50 33.866 / p95 74.544 ms
- 조건 B(이 스크립트의 CPU 바쁜 루프 2개, load 2.68) 전체 p50 33.912 / p95 80.583 ms
- 초기 로딩 7171.5 ms · RSS 로딩 뒤 1292.6 MiB · 최대(VmHWM) 1349.8 MiB
- STEP29.3 조건 A pilot274 R2 analyze p95 52.6 ms(다른 시점·부하 — 같은 날 다른 시각 측정이라 직접 비교는 참고만). 병원 운영 성능 검증 아님.

## 기존 evidence 연결(§7)
- 기존 77 concept 중 변환 규칙 허용 71 · 변환 안 함 6(EV:E_131, EV:E_136, decreased_appetite, fatigue, limb_weakness, vomiting)
- inventory 가 가리키는 evidence 87개 / 카탈로그 223개 중 양성 변환 대상 71개(1 evidence = 1 concept, 충돌 0)
- 통증 부위(E_55)·성상·강도 같은 값 질문은 변환하지 않음(의사 확인 필요). 신규·하위 SILVER concept 은 관련 evidence 가 있어도 변환 안 함(코피 → E_178 금지).
- 변환표는 엔지니어링 초안 — validation_status = ENGINEERING_DRAFT_UNVERIFIED(의사 검증 0).

## 최종 보고 질문(§19)
1. **NLU 결과를 Doctor 용 데이터로 정상 변환할 수 있는가?** — 구조 변환은 가능: 사례 82, NLU mention 138개가 packet item 으로 빠짐없이 옮겨졌고(스키마 위반 0) NLU 원본은 item 마다 그대로 보존. 필수 필드 중 mapping_status·provenance·uncertainty_reason 은 NLU 에 없어 어댑터가 만든다. 내용 정확도는 NLU 품질에 묶임(아래 11).
2. **기존 77 증상과 신규 SILVER 를 구별해 표시하는가?** — 범주 A(기존 지원) 60 · B(새 표준 후보) 6. B 는 '새로운 표준 증상 후보(모델 미사용)' 칸에 따로 표시되고 STAGE_A·STAGE_B 모두 될 수 없음(G3 PASS).
3. **부정 증상은 모델 입력에서 격리되는가?** — 예(위반 0). 범주 C 9건은 STAGE_A 0, '없음 확인'을 해도 음성 evidence 로 바꾸지 않음. 의사가 '있음'으로 바꾸려면 재분류 사유가 필요(변이 확인 중 NLU 가 ABSENT 를 eligible·NEGATIVE 로 주는 것을 발견해 STAGE_A 에 양성 조건 추가).
4. **과거·해소 증상은 현재 양성과 분리되는가?** — 예(위반 0). 범주 D 15건, 사건 시점·해소 상태를 그대로 표시. 다만 '토했어요'처럼 과거형 단독 문장도 D 가 되므로 진료 당일 현재 증상인지는 의사가 확인해야 함.
5. **가족 증상이 환자 증상으로 잘못 쓰이지 않는가?** — 자동 입력 위반 0. 범주 E 9건. 주체가 MULTIPLE 이면 F(확인 필요)로 보냄. NLU 가 주체를 놓친 경우는 범주가 A 로 표시될 수 있음(11 참고).
6. **UNKNOWN·UNCERTAIN 은 어떻게 표시되는가?** — '추가 확인 필요' 칸(F 10 · H 18)에 원문 위치와 사유(가드·부위만·확실성 낮음 등)와 함께 표시, STAGE_A 불가(위반 0).
7. **기존 223 evidence 와 연결 가능한 증상은?** — 77 concept 중 71개가 evidence 71개(카탈로그 223개 중)로 양성 1:1 변환 가능. 나머지는 일반형 질문이 없거나 값 질문.
8. **의사 확인 이전에 자동 모델 입력이 발생하는가?** — 아니오. 모든 사례 applied=false, 자동 입력 0(G9 PASS). STAGE_A 59건은 표시만.
9. **블라인드 working diagnosis 흐름이 유지되는가?** — 제품 doctor_view 를 in-process 로 호출한 시뮬레이션에서 위반 2(사례 82): working diagnosis 입력 전 질환 후보·다음 질문 LOCKED, 확인 단계가 working diagnosis 를 바꾸지 않음, 공개 단계 모델 입력 = STAGE_B 확인 evidence 만. 연구 packet·Preview 에 질환 이름·점수·순위 없음.
10. **확인 전후 차이를 추적할 수 있는가?** — 예. apply_decisions 가 항목별 confirmation 변경과 patient_state_delta 추가를 diff(확인자·순서 포함)로 남기고 입력 packet 은 바꾸지 않음. Preview F 칸에 표시.
11. **기존 NLU 오류가 화면·모델 입력에 주는 영향** — 자동 모델 입력에는 영향 없음(입력 자체가 없음). 화면에는 그대로 전파: 기대와 다른 범주 9건, STAGE_A 금지 기대인데 STAGE_A 표시 2건, 누락 1건, concept 다름 2건(전체 세트). 의사가 STAGE_A 를 그대로 확인하면 잘못된 입력이 될 수 있으므로 STAGE_B 는 원문 대조 확인이 전제. '전부 확인' 오클릭 시나리오에서도 B·G·H·C·D·E·F 는 막힘(item 138 중 STAGE_B 59).
12. **제품을 수정하지 않고 전체 흐름을 재현했는가?** — 예(G11 PASS): master 977877f 그대로, 제품 파일 322개·연구 원본 858개 SHA 동일, 서버 PID 동일({'5190': '29556', '8020': '65085', '8010': '29554'}). 재현 2회 = SHA_IDENTICAL.
13. **실제 제품 연결을 위해 필요한 변경** — docs/step31_handoff.md: (a) Doctor 화면에 'AI 추출 후보' 영역과 항목별 확인 UI(있음·없음·보류 + 재분류 사유) (b) 확인 결과를 PatientState 로 넣는 경로 — 현재 세션은 exact-k 시작 계약이 있어 추가 관측을 넣으면 model_context_match 가 깨짐(제품 정책 결정 필요) (c) 변환표의 의사 검토 (d) 서버 측 NLU 실행 위치·메모리(RSS 1292.6 MiB) (e) 실제 ASR 전사문 평가 (f) 음성 evidence 정책.
14. **STEP31 연구용 제품 연동 실험을 시작할 수 있는가?** — 공식 NO_GO(G10 검사기 오탐으로 REGRESSION). EXPLORATORY 재확인 기준 CONDITIONAL_GO — 다만 NLU 의미 오류가 STAGE_A 표시로 전파되는 문제(11)가 남아 있어 그대로 진행하기보다 사용자 결정 필요. 사용자 승인 전 시작하지 않음.

## 보호·라이선스
- G11 PASS · G12 PASS(검사 파일 28, 제한 ID 값 207개 대조, 일치 0, 네트워크 import 0). 외부 LLM·API·다운로드·설치·재학습 없음. commit/push 없음.
- 제품: master 977877f · 서버 상태만 확인 {'5190': '29556', '8020': '65085', '8010': '29554'}.
- 단위 테스트 34개 PASS — 변이 확인 기록 logs/mutation_check_20261014.md.

## 한계
- 합성 문장만, 평가 문장·기대값·규칙 작성자가 같음(Claude 세션) — 사람 검증 0. 노출 회귀 10문장은 독립 평가 아님.
- 기대값의 허용 범주는 작성자 판단(예: '목이 아프고'를 인후통·통증 모두 허용). 실제 ASR 전사문 미평가.
- dummy 확인 정책 2개만 시험(STAGE_A 만 확인 / 전부 확인). 실제 의사 행동·UI 사용성은 미검증.
- 변환표(77 concept → evidence)는 질문 원문 기준 엔지니어링 초안 — 의사 검증 0.
