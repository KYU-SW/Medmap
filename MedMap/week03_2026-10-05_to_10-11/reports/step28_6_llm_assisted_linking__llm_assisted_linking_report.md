# STEP28.6 — LLM-Assisted Korean-English Medical Concept Linking

- **STEP28_6_RESULT = LINKING_FEASIBLE** · 모드 = FULL(A+B) · PRODUCTION_READY = NO · 모든 대응·연결 = **SILVER(검증 전)** — 정확도·임상 안전성 주장 없음.
- 격리 작성: `claude -p --restricted --tools Read,Write`(작업 폴더 `~/medmap_step28_6_ws/`), 작성자 A = opus · B = sonnet. 격리 검사 = FAIL
  (세션별 위반: {"audit_c01": [], "author_A_c01": [], "author_A_c02": [], "author_A_c03": ["READ_NOT_ALLOWED:out/author_A_c03.tsv"], "author_A_c04": ["READ_NOT_ALLOWED:out/author_A_c04.tsv", "READ_NOT_ALLOWED:out/author_A_c04.tsv"], "author_A_c05": [], "author_A_c06": [], "author_B_c01": [], "author_B_c02": [], "author_B_c03": [], "author_B_c04": ["READ_NOT_ALLOWED:out/author_B_c04.tsv", "TOOL:Edit"], "author_B_c05": [], "author_B_c06": []}). LLM 에는 한국어 표현·지시문만 전송(모델 예측·77 목록·SNOMED/UMLS 문자열·MDRKOR 없음),
  감사자에게는 한국어 + HPO(공개) 이름·정의만.
- LLM 사용량(정가 환산, 청구액 아님): $4.885 · 호출 13 (`outputs/llm_usage.csv`). 승인 상한 $15.
- 판정 규칙: `scripts/build_report.py` 문서열. 연결·범주 규칙: `scripts/link_english_to_ontology.py`(작성 결과를 보기 전 고정).

## 1. 수치(Silver = STEP25 BERT-NER-KO 증상 span, 지금까지 작성된 입력 442/442)

| 항목 | 작성자 A | 작성자 B |
|---|---|---|
| 영어 의료 용어로 변환 | 432/442 | 438 |
| ontology 실제 ID 까지 연결(완전일치, 증상형) | 237 | 250 |
| 77 밖 신규 후보(입력 / 고유 concept) | 66 / 35 | 68 / 36 |
| 범주 | {"EXISTING_CANONICAL": 133, "EXISTING_COMPOSITE": 38, "NEW_ONTOLOGY_CANDIDATE": 66, "NON_SYMPTOM": 95, "UNCERTAIN": 49, "UNKNOWN": 61} | {"EXISTING_CANONICAL": 145, "EXISTING_COMPOSITE": 37, "NEW_ONTOLOGY_CANDIDATE": 68, "NON_SYMPTOM": 95, "UNCERTAIN": 42, "UNKNOWN": 55} |

최종(A·B 통합): {"categories": {"EXISTING_CANONICAL": 127, "EXISTING_COMPOSITE": 37, "NEW_ONTOLOGY_CANDIDATE": 61, "NON_SYMPTOM": 90, "UNCERTAIN": 78, "UNKNOWN": 49}, "agreement": {"AGREE": 349, "BOTH_UNKNOWN": 48, "CONFLICT": 25, "SINGLE": 20}, "grades": {"G3_SILVER_AUDITED": 40, "G2_SILVER_AGREED": 21, "G1_SINGLE_AUTHOR": 10, "REJECTED": 1}} · 신규 등급별 고유 concept: {"G3_SILVER_AUDITED": 22, "G2_SILVER_AGREED": 12, "G1_SINGLE_AUTHOR": 6, "REJECTED": 1}
한→영 연결률(같은 입력): STEP28.5 병렬 135/442 → STEP28.6 A 237/442
비증상 오매핑 위험(weak-non): {"A": 8, "B": 9, "final": 8, "n": 903, "step28_5_parallel_on_same_inputs": 49} · 작성자 충돌 29 · STEP28.5 와 기존 concept 이 다른 의미 충돌 4 · 구별 위반 0

## 2. 77 밖 신규 증상 후보(SILVER — NEW_ONTOLOGY_CANDIDATE, MODEL_SUPPORTED=False)

| concept | 영어(작성자) | 한국어 예 | 등급 | 검증기 판정 | 감사 |
|---|---|---|---|---|---|
| HP:0000421 | epistaxis | 코피가, 코피가, 코피나는것과는 | G3_SILVER_AUDITED | NEW_CONCEPT;NARROWER_THAN_EXISTING:EV:E_178 | {"HP:0000421": ["EXACT", "nosebleed equals epistaxis"]} |
| HP:0002354 | memory impairment | 기억저하, 기억저하, 건망증상 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0002354": ["EXACT", "memory decline equals memory impai |
| SCTID:83547004 | cold sweat | 식은 땀, 식은 땀, 식은땀이 | G2_SILVER_AGREED | NO_DEFINITION | {"SCTID:83547004": null} |
| HP:0001337 | tremor | 떨림, 떨림, 떨림은 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0001337": ["EXACT", "tremor"]} |
| HP:0008066 | blister | 물집이, 물집이, 물집은 | G2_SILVER_AGREED | NEW_CONCEPT;NARROWER_THAN_EXISTING:EV:E_129 | {"HP:0008066": ["NARROWER", "concept limited to bullae over  |
| SCTID:76067001 | sneezing | 재채기, 재채기 | G3_SILVER_AUDITED | NO_DEFINITION | {"SCTID:76067001": ["EXACT", "sneeze"]} |
| HP:0001257 | spasticity | 경축을 | G1_SINGLE_AUTHOR | NEW_CONCEPT | {"HP:0001257": ["EXACT", "경축 is Korean term for spasticity"] |
| HP:0002378 | hand tremor | 수전증, 수전증, 손떨림 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0002378": ["EXACT", "hand tremor"]} |
| SCTID:247342009 | foreign body sensation | 이물감, 이물감, 이물감은 | G2_SILVER_AGREED | NO_DEFINITION | {"SCTID:247342009": null} |
| HP:0100812 | halitosis | 입냄새의, 입냄새의, 입냄새가 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0100812": ["EXACT", "bad breath equals halitosis"]} |
| HP:0002354 | forgetfulness | 기억저하, 기억저하, 건망증상 | G2_SILVER_AGREED | NEW_CONCEPT | {"HP:0002354": ["BROADER", "memory impairment broader than e |
| HP:0002063 | rigidity | 경직, 경직, 경직을 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0002063": ["EXACT", "경직 corresponds to muscle rigidity" |
| HP:0033031 | high fever | 고열, 고열이 | G1_SINGLE_AUTHOR | NEW_CONCEPT;NARROWER_THAN_EXISTING:fever | {"HP:0033031": ["NARROWER", "hyperpyrexia requires 41.1C; 고열 |
| HP:0200034 | papule | 구진, 구진 | G3_SILVER_AUDITED | NEW_CONCEPT;NARROWER_THAN_EXISTING:EV:E_129 | {"HP:0200034": ["EXACT", "papule"]} |
| SCTID:55300003 | muscle cramp | 근육경련증상이, 근육경련현상일가능성이, 쥐가 | G1_SINGLE_AUTHOR | NO_DEFINITION;NARROWER_THAN_EXISTING:EV:E_193 | {"SCTID:55300003": null} |
| HP:0003750 | muscle fatigue | 근육피로도가, 근육피로도가 | REJECTED | NEW_CONCEPT | {"HP:0003750": ["RELATED_ONLY", "fatigue level is a measure, |
| HP:0031246 | dry cough | 마른기침의, 마른기침의 | G3_SILVER_AUDITED | NEW_CONCEPT;NARROWER_THAN_EXISTING:cough | {"HP:0031246": ["EXACT", "dry cough equals nonproductive cou |
| SCTID:719399007 | speech block | 말막힘이나 | G1_SINGLE_AUTHOR | NO_DEFINITION | {"SCTID:719399007": null} |
| HP:0025258 | neck stiffness | 목의 강직이, 목의 강직이 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0025258": ["EXACT", "neck stiffness equals stiff neck"] |
| HP:0001254 | lethargy | 무기력, 무기력 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0001254": ["EXACT", "listlessness equals lethargy"]} |
| SCTID:398032003 | loose stool | 묽은변을, 묽은변을 | G2_SILVER_AGREED | NO_DEFINITION | {"SCTID:398032003": null} |
| HP:0000988 | rash | 발진은, 발진은, 발진이 | G3_SILVER_AUDITED | NEW_CONCEPT;NARROWER_THAN_EXISTING:EV:E_129 | {"HP:0000988": ["EXACT", "rash"]} |
| HP:0001288 | gait disturbance | 보행장애, 보행장애 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0001288": ["EXACT", "gait disturbance"]} |
| HP:0100785 | insomnia | 불면, 불면 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0100785": ["EXACT", "insomnia"]} |
| SCTID:247347003 | discomfort | 불편감을, 불편감을 | G2_SILVER_AGREED | NO_DEFINITION | {"SCTID:247347003": null} |
| HP:0001649 | tachycardia | 빈맥증상과, 빈맥증상과 | G3_SILVER_AUDITED | NEW_CONCEPT;NARROWER_THAN_EXISTING:palpitations | {"HP:0001649": ["EXACT", "tachycardia"]} |
| SCTID:271587009 | stiffness | 뻐근한 증상이, 뻐근한 증상이, 뻐근함이 | G2_SILVER_AGREED | NO_DEFINITION | {"SCTID:271587009": null} |
| HP:0000858 | irregular menstruation | 생리불순, 생리불순 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0000858": ["EXACT", "irregular menstruation"]} |
| HP:0001123 | visual field abnormality | 시야 이상 | G1_SINGLE_AUTHOR | NO_DEFINITION | {"HP:0001123": null} |
| SCTID:247322000 | abnormal sensation | 어깨 이상 감각, 이상감각, 이상감각현상으로 | G1_SINGLE_AUTHOR | NO_DEFINITION | {"SCTID:247322000": null} |
| SCTID:366979004 | depressed mood | 우울, 우울, 우울감이나 | G3_SILVER_AUDITED | NO_DEFINITION | {"SCTID:366979004": ["EXACT", "depressed mood maps to pathol |
| SCTID:119416008 | epigastric discomfort | 윗배 불편감, 윗배 불편감 | G2_SILVER_AGREED | NO_DEFINITION | {"SCTID:119416008": null} |
| SCTID:42800007 | fine tremor | 잔떨림, 잔떨림 | G2_SILVER_AGREED | NO_DEFINITION | {"SCTID:42800007": null} |
| HP:0002329 | drowsiness | 졸리움, 졸리움, 졸리움이 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0002329": ["EXACT", "drowsiness"]} |
| SCTID:55300003 | muscle cramp | 근육경련증상이, 근육경련현상일가능성이, 쥐가 | G2_SILVER_AGREED | NO_DEFINITION;NARROWER_THAN_EXISTING:EV:E_193 | {"SCTID:55300003": null} |
| SCTID:62507009 | tingling | 찌릿찌릿한 증상이, 찌릿찌릿한 증상이 | G2_SILVER_AGREED | NO_DEFINITION;NARROWER_THAN_EXISTING:EV:E_177 | {"SCTID:62507009": null} |
| HP:0010780 | hyperacusis | 청각과민을, 청각과민을 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0010780": ["EXACT", "hyperacusis"]} |
| HP:0025267 | snoring | 코골이가, 코골이가 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0025267": ["EXACT", "snoring"]} |
| SCTID:271787007 | collapse | 허탈증상, 허탈증상 | G2_SILVER_AGREED | NO_DEFINITION | {"SCTID:271787007": null} |
| HP:0000738 | hallucination | 환각, 환각 | G3_SILVER_AUDITED | NEW_CONCEPT | {"HP:0000738": ["EXACT", "hallucinations"]} |
| HP:0034315 | chronic cough | 만성기침과, 만성기침과 | G3_SILVER_AUDITED | NEW_CONCEPT;NARROWER_THAN_EXISTING:cough | {"HP:0034315": ["EXACT", "chronic cough"]} |

## 3. 연결 실패 원인(Silver, 미해결)

{"SEMANTIC_TYPE_MISMATCH": 33, "ONTOLOGY_NO_EXACT_MATCH": 40, "AUTHOR_CONFLICT": 25, "SINGLE_AUTHOR_ONLY": 20, "LLM_NO_ENGLISH": 8, "AUDIT_REJECTED": 1} — `outputs/failure_analysis.csv`

## 4. 처리 시간

- LLM 작성(오프라인 단계): 230 행당 [111.6, 146.8, 188.8, 216.1, 108.5, 105.2, 70.6, 52.4, 53.1, 101.6, 77.4, 67.2] s
- 런타임(대응표 조회 + ontology 완전일치 + 검증, CPU, 조상 계산 메모 warm): p50 0.491 ms · p95 0.87 ms (n 300). 대응표에 있는 표현만 해당(조회+완전일치 검색+검증, 캐시 비움). 대응표에 없는 새 표현은 LLM 이 필요 — 병원 런타임 오프라인 원칙과 충돌

## 5. 변경 기록(공개)

- 연결·범주 규칙은 작성 결과를 보기 전에 고정했고 이후 바꾸지 않았다. 속도 측정용으로 (a) 유사 일치 개수 세기를 생략한 런타임 경로(판정 동일 확인 = True) (b) STEP28 검증기의 조상 계산 메모(STEP28 코드 무수정)를 추가했다.
- 주간 한도: 2026-10-11 02:34 KST 작성자 A c01 은 출력 완료 후 마지막 응답에서 한도 메시지, B c01 은 시작 즉시 한도(비용 0, `logs/authoring/failed_weekly_limit/` 보존). 해제 2026-10-15 01:00 KST.

## 6. 답(현재 모드 기준)

- 변환: 작성자 A 가 442 표현 중 432 개를 영어 의료 용어로 변환.
- ontology ID 연결: 증상형 237 개(완전일치만, 부분 일치는 연결로 안 셈).
- 77 밖 신규: 입력 66 · 고유 concept 35 (작성자 A 단독 = G1, 확정 아님).
- 코피: `코피가` → epistaxis → HP:0000421(77 밖, 기존 EV:E_178 '비정상 출혈·멍'의 하위로 기록) — 객혈·토혈로 바뀌지 않음. 단 단일 작성자·감사 전이라 SILVER G1.
- 위험: 작성자 충돌·감사 반려·의미 충돌·비증상 오매핑은 §1. B·감사가 없으면 '같은 오류' 여부를 볼 수 없다.
- 다음 조건: (1) 작성자 B·나머지 조각·HPO 감사 완료(G2·G3) (2) 사람 검토 Gold 소량으로 G3 후보의 실제 일치 확인 (3) 신규 concept 의 질환 모델 사용은 학습 데이터·재검증 전 금지 (4) 대응표 밖 새 표현은 LLM 이 필요 — 병원 오프라인 원칙상 사전 작성 대응표만 런타임 사용.

## 7. 완료 후 추가 확인(2026-10-11 03:10 KST 재개 완료 뒤 — 판정·규칙에 미사용, 탐색)

- 주간 한도는 사용자 확인대로 02:48 KST 재개 시 풀려 있었다. 작성 12회(A opus 6 · B sonnet 6) + HPO 감사 1회, 누적 정가 환산 $4.885(청구액 아님, 상한 $15). 결정적 단계 2회 재현 SHA 동일(`logs/det_sha{1,2}.txt`).
- 격리 검사 = **FAIL(사전 규칙 그대로)**: author_A_c03·A_c04·B_c04 가 **자기 출력 파일**을 다시 읽음(자기 검토), B_c04 는 자기 파일에 Edit 사용. 다른 작성자 파일 읽기·작업 폴더 밖 접근·CLAUDE.md/메모리 주입은 0 → 교차 오염 근거 없음. 등급은 낮추지도 올리지도 않고 그대로 기록.
- STEP28.6 이 신규로 둔 입력 중 STEP28.5 가 한국어 근거로 기존 concept 에 연결한 것 10 건(`outputs/new_vs_step28_5_existing.csv`): '떨림'(7) — STEP28.5 는 chills(오한)로 연결했으나 떨림 = tremor 이므로 STEP28.5 쪽 오류로 보임 · '묽은변'→loose stool(기존 diarrhea 와 사실상 중복 가능) · '무기력'→lethargy(기존 fatigue 와 겹칠 수 있음) · '마른기침'→dry cough(cough 하위, 신규 후보로 상위 연결 기록). → 영어 경로 단독은 '77 안 한국어 용어'를 신규로 오인할 수 있어, 런타임에는 한국어 기존 검색(STEP28.5 KO EXACT)을 먼저 두는 통합이 필요.
- 작성자 충돌 29(예: '저림' A=E_177 vs B=불확실, '경축' A=spasticity 신규 vs B=근육 경련 E_193), STEP28.5 와 기존 concept 이 다른 의미 충돌 4(근육통→E_175 vs pain 2, 저림 관련 2).
