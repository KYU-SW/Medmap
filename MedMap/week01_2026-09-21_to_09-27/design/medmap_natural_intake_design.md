# MedMap Natural Intake 통합 설계 (v1, 2026-09-24) — 승인 대기

> **역사 문서(2026-10-02 표기)**: 작성 당시 계약 기록. 현재 제품 정본은 `PRODUCT.md`(v5 정렬). 이후 STT·자연어 intake·Doctor 화면·인계가 추가됐다.

(작성 당시) 구현 없음 — 이후 master `336463f`로 구현·병합. 이 문서 승인 전 API·UI·STT·매퍼 변경 금지, STEP17 미시작.

---

## 0. 계획 대비 점검

| 항목 | 계획(HANDOFF §24 순서) | 실제 | 판정 |
|---|---|---|---|
| ① 매퍼 코어 + 평가셋 | 숫자 먼저 | v1 FAIL → v1.1 blind v2 FAIL → v1.2 blind v3 **PASS**(P 0.963 / NEG P 0.958). fixture 3종 전부 소진, 재튜닝 없음 | 완료 |
| ② /intake/extract + 확인 UX | 다음 단계 | 이 문서(설계) | 진행 중 |
| ③ exact-k | ② 다음 | 이 문서에 포함 | 진행 중 |
| ④ STT · ⑤ 긴 선택지 | 뒤 | 이 문서에 위치만 | 계획대로 |
| ⑥ 임베딩 · ⑦ STEP17 | 마지막 | 미시작 | 계획대로 |

주의 3건(계획에서 벗어났거나 새로 확인된 것):

1. **Web UI 머지 결정이 아직 대기 중.** `feat/web-ui`(158d2f2)는 master 미머지, `feat/intake-mapper-v1`은 master에서 따로 분기. 이 설계는 `feat/web-ui`의 IntakeScreen을 교체하므로 **구현 전에 머지 순서부터 정해야 함**(권장: web-ui 육안 검수·머지 → intake 브랜치 rebase → 구현).
2. **현재 UI 주 증상 목록 41개 중 14개는 학습 데이터에서 initial evidence로 한 번도 나오지 않음**(TRAIN 1,025,602명 전수, INITIAL_EVIDENCE 고유값 96개).
   - 해당 14개: E_0, E_69, E_70, E_78, E_79, E_104, E_105, E_116, E_120, E_123, E_124, E_189, E_209, E_226 — 전부 과거력·생활습관
   - "당뇨가 있어요"를 주 증상으로 고르면 MODEL_k3가 본 적 없는 입력. 현재 `feat/web-ui`에 잠재된 결함
   - 41개 중 initial로 쓰인 27개가 TRAIN 환자의 71.2%를 덮음 → **나머지 28.8%의 주 증상은 현재 한국어 범위 밖**
3. **exact-k의 "추가 3개"는 학습 분포와 원래 다름.** STEP16B 사전등록 §4: 초기 evidence(항상 binary POSITIVE) 공개 후 **추가 k개는 적격 pool에서 순차 균등 무작위 추출**, 답은 실제 값(closed-world라 대부분 NEGATIVE).
   - 기존 "고정 3문항"도, 자연어로 말한 증상(스스로 고른 두드러진 양성)도 이 분포가 아님
   - 초기 정확도에 대한 영향은 **측정된 적 없음**. STEP16B가 검증한 것은 "무작위 k 뷰 이후 IG 질문 선택"뿐

인수인계 문서(HANDOFF v3)는 매퍼 v1~v1.2 작업을 아직 반영하지 않음 → 세션 종료 전 `/session-handoff` 필요.

---

## 1. 매퍼의 역할

- **보수적 후보 추출기**. 사용자가 확인한 항목만 PatientState에 들어감.
- NEGATIVE 후보는 `negative_policy.json` SAFE 23개에서만. UNSAFE 18개의 부정은 후보로 만들지 않음(UNASKED).
- 확인 화면에서 사용자가 POSITIVE 후보를 [없음]으로 바꾸는 것은 허용 — 사용자 본인의 답이므로 엔진 질문에 답한 것과 같은 지위.
- 확인 화면은 후보를 **추가하지 않음**. 빠진 정보는 bootstrap 질문이 채움.

## 2. 권장 흐름

```
[1] 나이·성별
[2] 자유 입력(텍스트, 이후 마이크도 같은 입력칸으로)
[3] POST /v1/intake/extract → 후보(최대 5개 먼저 표시)
[4] 확인: 항목마다 [있음] [없음] [빼기]
[5] initial evidence 결정(§4)
[6] bootstrap: 부족분만 한 번에 한 문항(§5)
[7] POST /v1/session/start (initial 1 + additional 정확히 3) — 기존 계약 그대로
[8] 진단 후보 + IG 질문 1개씩(기존 ConsultScreen) — cache 적중 시 자동 반영(§7)
```

## 3. 추출 0개(v3 기준 44.1%)

- 정상 흐름. 문구: "말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요."
- "증상이 없습니다" 류 표현 금지.
- 41개 목록을 다시 펼치지 않음. **"가장 불편한 증상 하나"**만 고르게 함:
  - 대상: initial 가능 27개만
  - 표시: 한국어 라벨 검색창 + 자주 쓰는 8개 버튼(E_53 통증, E_66 숨참, E_201 기침, E_181 코막힘·콧물, E_91 열, E_129 피부, E_45 객혈, E_151 부기 — TRAIN initial 빈도순, 데이터로 고정)
  - 선택값이 initial evidence
- 목록에 없는 경우 [여기에 없어요]를 누르면: "현재 버전이 다루는 증상 범위 밖일 수 있어요" 안내 → **진단을 시작하지 않고 종료**(권장).
  - 이유: initial `null`은 API가 받지만 학습에 없던 형태
  - → **승인 필요 항목 A**

## 4. initial evidence 결정

시스템이 임상 중요도를 추정하지 않음.

| 확인된 POSITIVE 중 initial 가능(27개) 항목 수 | 처리 |
|---|---|
| 0 | §3의 "가장 불편한 증상 하나" 선택 |
| 1 | 그 항목을 initial로(추가 질문 없음) |
| 2 이상 | "이 중 가장 불편한 증상은 무엇인가요?" 한 번만 선택 |

- NEGATIVE, 과거력(14개)은 initial이 될 수 없음 → additional 후보로만.
- initial 가능 목록은 TRAIN INITIAL_EVIDENCE 집계로 만든 **고정 파일**(런타임 추론 없음, 원본 VALIDATION/TEST 미접근).

## 5. Bootstrap

`필요 수 = 3 − (initial을 뺀 확인 evidence 수)`, 0 미만이면 §6.

| 확인 total | initial | additional | bootstrap |
|---|---|---|---|
| 1 | 1 | 0 | 3 |
| 2 | 1 | 1 | 2 |
| 3 | 1 | 2 | 1 |
| 4 | 1 | 3 | 0 → 바로 start |
| 5+ | 1 | 3 | 0 → 나머지는 cache(§6·§7) |

선택 방식 비교:

| | A. 고정 순서(현행 승인안) | B. bootstrap 단계에서도 IG |
|---|---|---|
| 방식 | E_91→E_53→E_66, 예비 E_201→E_175→E_88. 이미 확인됐거나 initial인 항목은 건너뜀 | 현재 상태로 IG 최대 질문 |
| 검증 | 학습 분포(무작위 k)와 다름, 영향 미측정 | **STEP16B 범위 밖**(IG는 start 이후만 검증) |
| 결론 | **v1 채택** | 연구 후보 |

- 한 번에 한 문항, 기존 QuestionPanel 재사용. 답: [있음] [없음] [모름].
- 기존 계약상 "모름"은 UNKNOWN(학습에 없던 값) — 이미 승인된 현행 동작이며 미검증으로 기록.

## 6. 확인 5개 이상

v3 추출 분포에서 5개 이상은 0.6%(3/497), 4개는 0%. 확인은 추출을 넘지 않으므로(추가 불가) 상한도 같음. 단, v3는 복합 증상 문장을 의도적으로 늘린 fixture라 실제 비율은 미측정.

| | A. 사용자가 initial 1 + additional 3 직접 선택 | B. 발화 순서로 앞 3개, 나머지 cache | C. v1은 4개까지만 받음 |
|---|---|---|---|
| 장점 | 사용자 통제 명확 | 추가 화면 없음, 결정적, 버리는 정보 없음 | 가장 단순 |
| 단점 | 0.6% 사례에 선택 화면 추가, 사용자가 고른 3개도 학습 분포 아님 | 발화 순서도 학습 분포 아님 | 확인받은 정보를 버림(요구사항 위반) |
| exact-k | 충족 | 충족 | 충족 |

- **v1 권장: B.** initial은 §4대로 사용자가 고르고, 나머지를 발화 순서대로 앞 3개 additional, 그 외는 cache.
- 화면에 "나머지 N개도 기록해 두었고, 관련 질문이 나오면 반영합니다" 표시(조용히 버리지 않음).
- **장기: STEP17 variable-evidence**(§13).

## 7. Confirmed cache

- 정의: 사용자가 확인했지만 MODEL_k3 start 입력에 아직 넣지 못한 binary evidence 답.
- 저장: **PatientState·세션 JSON에 넣지 않음**(넣으면 n_additional이 바뀌어 exact-k가 깨짐).
  - 클라이언트 `sessionStorage` 별도 키 1개에 `{evidence_id, status}`만. 원문 텍스트는 넣지 않음
  - 세션 복원 실패 시 같이 폐기
- 사용 규칙:
  1. 엔진이 `next_question.question_id`로 **실제로 제안한** ID가 cache에 있을 때만 사용
  2. "앞서 말씀하신 내용을 반영합니다" 안내 후, 기존 `POST /v1/session/answer`로 그 답을 제출(API 무변경, 409 규칙 그대로)
  3. 제안되지 않은 ID는 절대 미리 제출하지 않음. posterior를 직접 건드리지 않음
  4. 이 자동 반영도 질문 예산(`MEDMAP_MAX_QUESTIONS`, 기본 3) 1개를 씀 — 숨기지 않음
- 기대 효과는 작음(5+ 0.6%). 구현 우선순위 낮음.

## 8. STT

- 흐름 맨 앞에만 붙음: 마이크 → `/v1/stt/transcribe` → 전사문을 **같은 입력칸**에 채움 → 사용자가 고칠 수 있음 → 같은 `/intake/extract` → 같은 확인 화면.
- 텍스트와 음성의 intake 로직은 하나.
- whisper-large-v3-turbo(HF 캐시 보유) + 기존 `stt/stt_whisper.py`(PyAV 디코드). 오디오는 메모리에서만 처리.

## 9. 긴 선택지(start 이후 IG 질문)

| 선택지 수 | UI |
|---|---|
| ≤ 10 | 버튼/리스트 |
| 11–30 | 검색 + 필터 |
| 31–100 | 검색 우선 + 그룹 |
| > 100 (E_55·E_57·E_133 부위 165개) | 검색 + 계층 그룹(부위 → 좌우) + 대표 항목 |

- value ID·엔진 계약 무변경. 165개 한국어 라벨은 모두 있음(188 중).
- 계층 그룹 매핑은 새 정적 파일(수기 작성)이라 검수 필요.

## 10. API 추가(설계만)

`POST /v1/intake/extract`
- 입력 `{ "text": "..." }`(길이 상한 예: 1,000자, 초과 422)
- 출력 `{ "candidates": [{evidence_id, status, label_ko, matched_text, initial_eligible}], "mapper_version": "v1.2" }`
- PatientState·세션 무관, 서버 무상태, 원문 로그 저장 금지.
- confidence·alias_id는 응답에서 제외.

`POST /v1/stt/transcribe`
- 입력: 오디오(multipart, 길이·크기 상한)
- 출력: `{ "text": "..." }`만. 디스크·외부 전송 없음, 모델은 첫 호출 때 로드.

기존 `/v1/session/start` · `/answer` · `/resume` 계약 **무변경**. `/health`에 매퍼 버전 필드 추가만 검토.

## 11. UI 구성

- 재사용: StartScreen, CandidatePanel, QuestionPanel(+ChoiceButton), Notice, SummaryScreen, AppHeader, 오류·health 처리, 변화 표현
- 교체: IntakeScreen(41개 선택 + 고정 3문항 폼) → 아래 순서형 화면
- 추가:
  - FreeTextInput
  - VoiceInput(placeholder)
  - EvidenceConfirmation(최대 5개, 나머지 "추가로 확인된 정보 N개" 접기)
  - InitialPicker(0개·다수일 때, 27개 한정 검색 + 대표 8개)
  - BootstrapQuestion(QuestionPanel 재사용, 한 문항씩)
- 기존 UI 금지 규칙 유지(챗봇 말풍선·그래프·MEDMAP 코드·IG bits 노출 금지). 문구는 "말씀하신 내용에서 다음 항목을 확인했어요".

## 12. UX 접근 3안

| | 1. 설명 → 확인 → 부족분 질문 (권장) | 2. 주 증상 먼저 선택 + 선택형 자유 입력 | 3. 대화형 한 문장씩 |
|---|---|---|---|
| flow | 자유 입력 → 후보 확인 → initial 선택(필요 시) → bootstrap 1개씩 → start | 주 증상 1개 선택(27개) → "더 말씀하실 게 있나요?" 자유 입력 → 후보 확인 → bootstrap → start | 한 번에 한 문장 입력 → 매번 추출·확인 → 3개 찰 때까지 반복 |
| 장점 | 목표 UX("설명한다→확인한다→부족분만")와 일치, 입력 1회 | initial이 항상 유효, 0개 추출 영향 적음 | 부족분을 자연어로 채움 |
| 단점 | 0개 추출 44%는 InitialPicker 한 단계 추가 | 사용자가 먼저 목록을 봄(목표와 반대), 입력 2회 | 턴 수 증가, 채팅 UI 금지 규칙과 충돌, 추출률 낮아 반복 많음 |
| exact-k | bootstrap 1~3 | 같음 | 자연어 반복 + bootstrap |
| 0개 추출 | InitialPicker | 이미 initial 있음 → bootstrap 3 | 재입력 요청 반복 |
| 5+ 확인 | 발화 순서 3 + cache | 같음 | 같음 |
| STT | 첫 입력칸 | 두 번째 입력칸 | 매 턴 |

**권장: 1안.**

## 13. exact-k 판단

v3(497문장, 설계된 fixture) 추출 개수 기준으로, start까지 필요한 bootstrap 수를 추정:

| 추출 | 비율 | 필요 bootstrap(추출 전부 확인되고 그중 1개가 initial일 때) |
|---|---|---|
| 0 | 44.1% | InitialPicker 1 + bootstrap 3 |
| 1 | 41.9% | 3 (그 1개가 NEGATIVE·과거력이면 InitialPicker + 2) |
| 2 | 9.3% | 2 |
| 3 | 4.2% | 1 |
| 4 | 0.0% | 0 |
| 5+ | 0.6% | 0 + cache |

- 사용자 86.0%(0·1개)는 어차피 bootstrap 3문항 → 병목은 exact-k 초과가 아니라 **추출 부족**(recall 0.61, 복합 증상 45문장 중 4개 이상 추출 3문장 vs gold 11문장).
- 초과(5+) 사례는 0.6% → cache로 감당.
- **판단: A(v1 bootstrap으로 감당 가능) + B(장기 variable-evidence 연구 필요).**
  - 장기가 필요한 이유는 초과 처리가 아니라 두 가지:
    1. 학습 분포(무작위 k)와 실제 입력(두드러진 양성 + 고정 bootstrap)의 불일치가 미측정
    2. 86%에게 3문항을 강제하는 구조
- C(즉시 STEP17) 아님.

## 14. 비용·개인정보

- 비용 0원: 매퍼는 로컬 regex, STT는 로컬 whisper(설치 완료), 유료 API·외부 LLM 없음.
- 원문·오디오 저장 없음. 전사문과 matched_text는 확인 화면에만 표시, 세션 JSON·cache에는 넣지 않음.
- STT VRAM +1.6GB(첫 호출 시 로드).

## 15. 구현 순서(승인 후)

0. `feat/web-ui` 육안 검수·머지 결정 → intake 브랜치 rebase
1. initial 가능 27개 고정 파일(현행 UI 결함도 해소)
2. `/v1/intake/extract` + 테스트
3. IntakeScreen 교체(텍스트) + EvidenceConfirmation + InitialPicker + BootstrapQuestion
4. cache
5. 긴 선택지 UI
6. STT

## 16. 나중에 할 연구(새 split + 새 사전등록 필요)

- 추가 evidence가 "무작위 k"가 아니라 "두드러진 양성 + 고정 bootstrap"일 때 초기 정확도 변화(시뮬레이션 가능, STEP16B_HOLDOUT 재사용 금지)
- STEP17 variable-evidence 모델
- bootstrap 단계 IG
- UNKNOWN 답 처리
- 실제 사용자 발화 분포에서 매퍼 recall·추출 개수
- 임베딩 후보 검색(확인 전제)

## 17. 승인 필요 항목

- A. 목록 밖 주 증상일 때 진단을 시작하지 않고 종료(권장) vs initial `null`로 시작
- B. 5+ 확인 시 발화 순서 3개 + cache(권장)
- C. bootstrap 고정 순서 유지(권장)
- D. 구현 순서 0번(web-ui 머지 먼저)
- E. UX 1안
