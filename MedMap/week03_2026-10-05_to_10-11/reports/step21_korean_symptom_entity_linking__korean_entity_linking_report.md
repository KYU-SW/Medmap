# 한국어 환자 표현 → Canonical Symptom Entity Linking Pilot (STEP21)

- 작성 2026-10-08 · 브랜치 `research/symptom-ontology-expansion` · `exp/step21_korean_symptom_entity_linking/`
- **데이터는 전부 합성**: 평가 문장 274개는 Claude가 작성한 합성 표현이다(실제 환자 발화 아님). 정답 라벨도 Claude 판정(임상의 검수 없음).
- label space: STEP20 core symptom 87개(속성·수식어·노출 제외). pilot 은 그중 20개 concept. 부위·양상·시점은 별도 class 가 아니라 attribute.
- 수치는 **test split**(dev 에서 threshold 를 고른 뒤 고정 적용). 엔지니어링 gate 이며 임상 성능 기준이 아니다.

## 최종 판정

```
KOREAN_ENTITY_LINKING = NO_GO      (가장 나은 baseline: COMBINED)
DICTIONARY_BASELINE   = FAIL
FUZZY_BASELINE        = FAIL
LEARNED_LINKER_NEEDED = YES
NLU_NEEDED            = YES
Baseline 3 (local embedding) = NOT_EVALUATED
```

## 핵심 수치 (COMBINED, test)

| 항목 | 값 |
|---|---|
| canonical symptoms tested | 20 |
| utterances | 274 (dev 97 / test 177) |
| Tier A+B Top-1 | 37.4% |
| Recall@3 (Tier A+B) | 50.4% |
| Multi-label micro F1 (concept) | 43.3% |
| Negation accuracy (end-to-end, 전체 split) | 0.0% |
| Unknown rejection precision / recall | 13.2% / 64.7% |
| Auto-accept precision | n/a (자동 수락 0건) |
| Ask-confirmation rate | 53.1% |
| Abstention rate | 46.9% |

FUZZY·COMBINED threshold(dev 에서만 선택): T_high=1.01 · T_low=0.4 · T_multi=0.4. **T_high=1.01은 dev 에서 auto precision 95%를 넘는 점수 구간이 없어 자동 수락을 끈 상태**라는 뜻이다.

## baseline 비교 (test)

| baseline | gate | A+B Top-1 | A+B R@3 | A+B R@5 | A+B 새 표현 Top-1 | A+B 사전 표현 Top-1 | multi F1 | status F1 | auto P | auto | ask | abstain | unknown P/R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXACT | NO_GO | 11.3% | 12.2% | 12.2% | 0.0% | 92.9% | 30.5% | 23.3% | 82.0% | 22.0% | 0.0% | 78.0% | 10.1% / 82.3% |
| FUZZY | NO_GO | 33.9% | 48.7% | 54.8% | 29.7% | 64.3% | 39.7% | 32.5% | n/a | 0.0% | 49.7% | 50.3% | 12.4% / 64.7% |
| COMBINED | NO_GO | 37.4% | 50.4% | 56.5% | 29.7% | 92.9% | 43.3% | 34.4% | n/a | 0.0% | 53.1% | 46.9% | 13.2% / 64.7% |
| MAPPER(제품) | NO_GO | 27.8% | 28.7% | 28.7% | 21.8% | 71.4% | 41.1% | 40.3% | 77.6% | 32.8% | 0.0% | 67.2% | 14.3% / 100.0% |

Tier 별 Top-1 (test, 괄호는 정답 있는 문장 수):

| baseline | all | tier_A | tier_AB | tier_C | tier_AB_mapper_covered_concepts | tier_AB_mapper_uncovered_concepts | Tier D 거절(recall) |
|---|---|---|---|---|---|---|---|
| EXACT | 20.0% (n=160) | 13.5% (n=37) | 11.3% (n=115) | 42.2% (n=45) | 19.0% (n=58) | 3.5% (n=57) | 100.0% |
| FUZZY | 41.9% (n=160) | 43.2% (n=37) | 33.9% (n=115) | 62.2% (n=45) | 39.7% (n=58) | 28.1% (n=57) | 78.6% |
| COMBINED | 45.0% (n=160) | 46.0% (n=37) | 37.4% (n=115) | 64.4% (n=45) | 46.6% (n=58) | 28.1% (n=57) | 78.6% |
| MAPPER(제품) | 28.1% (n=160) | 32.4% (n=37) | 27.8% (n=115) | 28.9% (n=45) | 55.2% (n=58) | 0.0% (n=57) | 100.0% |

- MAPPER(제품 Natural Intake v1.2) 는 alias 가 있는 pilot concept 이 9/20 (cough, dyspnea, fatigue, fever, hemoptysis, nausea, pain, palpitations, swelling) 뿐이다. 나머지 concept 은 구조적으로 0%.

## 부정 · 시점 · 다른 사람 (전체 split, mention 단위)

| baseline | 부정 개념 검출 | 부정 status 정확(검출 중) | 부정 end-to-end | 과거 개념 검출 | 과거 end-to-end | 타인 증상 누출 | n(부정/과거/타인) |
|---|---|---|---|---|---|---|---|
| EXACT | 33.3% | 0.0% | 0.0% | 19.1% | 0.0% | 46.2% | 21/21/13 |
| FUZZY | 52.4% | 0.0% | 0.0% | 33.3% | 0.0% | 46.2% | 21/21/13 |
| COMBINED | 61.9% | 0.0% | 0.0% | 38.1% | 0.0% | 61.5% | 21/21/13 |
| MAPPER(제품) | 28.6% | 100.0% | 28.6% | 4.8% | 0.0% | 0.0% | 21/21/13 |

EXACT·FUZZY·COMBINED 는 status 를 항상 present 로 내므로 부정·과거 status 정확도가 0 이다(규칙을 덧붙여 올리지 않았다). MAPPER 는 부정 scope 규칙이 있어 검출한 부정은 맞히지만 검출 자체가 낮고, 과거 시점은 처리하지 않는다.

## 1. 잘 되는 한국어 표현 사례 (test, 사전에 없는 새 표현, COMBINED 가 1순위로 맞히고 확인 질문으로 넘긴 것)

| 문장 | 정답 | COMBINED top3 | 정책 | MAPPER |
|---|---|---|---|---|
| 계단 조금만 올라가도 숨이 너무 차요 | dyspnea | dyspnea;EV:E_172;EV:E_75 | ASK_CONFIRMATION | dyspnea |
| 숨이 벅차요 | dyspnea | dyspnea;EV:E_75;EV:E_23 | ASK_CONFIRMATION | (없음) |
| 숨이 가빠요 | dyspnea | dyspnea;EV:E_75;EV:E_23 | ASK_CONFIRMATION | dyspnea |
| 누우면 숨이 더 차서 앉아서 자요 | dyspnea | dyspnea;EV:E_75;EV:E_23 | ASK_CONFIRMATION | (없음) |
| 자다가 숨이 막혀서 깼어요 | dyspnea | dyspnea;EV:E_75;EV:E_128 | ASK_CONFIRMATION | dyspnea |
| 아침마다 속이 울렁거리고 구역감이 있어요 | nausea | nausea;palpitations;EV:E_112 | ASK_CONFIRMATION | nausea |
| 정신을 잃고 쓰러졌어요 | loc | loc;EV:E_82;EV:E_43 | ASK_CONFIRMATION | (없음) |
| 심장이 막 두근두근거려요 | palpitations | palpitations;EV:E_75;dyspnea | ASK_CONFIRMATION | palpitations |
| 맥박이 불규칙하게 뛰는 것 같아요 | palpitations | palpitations;EV:E_127;EV:E_170 | ASK_CONFIRMATION | (없음) |
| 손가락이 부어서 반지가 안 빠져요 | swelling | swelling;EV:E_30 | ASK_CONFIRMATION | swelling |

MAPPER 가 새 표현을 맞힌 예:

| 문장 | 정답 | MAPPER |
|---|---|---|
| 머리가 아파요 | pain | pain |
| 배가 아파요 | pain | pain |
| 머리가 지끈지끈해요 | pain | pain |
| 머리는 안 아픈데 배가 아파요 | pain | pain |
| 계단 조금만 올라가도 숨이 너무 차요 | dyspnea | dyspnea |
| 숨이 가빠요 | dyspnea | dyspnea |
| 자다가 숨이 막혀서 깼어요 | dyspnea | dyspnea |
| 조금만 걸어도 헉헉거려요 | dyspnea | dyspnea |

## 2. 실패 사례 (test, COMBINED — 분류별 첫 예)

| 문장 | 정답 | COMBINED top3 | 정책 | 분류 |
|---|---|---|---|---|
| 머리가 아파요 | pain | dizziness;EV:E_82;EV:E_202 | ABSTAIN | site_confusion |
| 허리가 끊어질 것 같아요 | pain | EV:E_82;EV:E_111;nausea | ABSTAIN | lexical_false_match |
| 호흡이 딸려요 | dyspnea |  | ABSTAIN | colloquial_expression |
| 그저께까지 열이 났는데 지금은 내렸어요 | fever | fever;EV:E_174;EV:E_162 | ASK_CONFIRMATION | temporal_failure |
| 엄마는 열이 있는데 저는 기침만 해요 | cough | cough;fever;vomiting | ASK_CONFIRMATION | other_person_failure |
| 열은 안 나요 | fever | fever;EV:E_111;EV:E_75 | ASK_CONFIRMATION | negation_failure |
| 기침하고 콧물도 나요 | EV:E_181;cough | cough;EV:E_181;EV:E_182 | ASK_CONFIRMATION | multi_symptom_failure |
| 남편이 기침을 심하게 해서 저도 옮았을까 걱정돼요 | (none) | cough;EV:E_170;vomiting | ASK_CONFIRMATION | unknown_forced_mapping;other_person_failure |
| 기칭이 계속 나요 | cough | fatigue;fever;EV:E_111 | ABSTAIN | spelling_variation |
| 헛구역질만 계속 나요 | vomiting | nausea;fatigue;vomiting | ASK_CONFIRMATION | overly_broad_or_specific |
| 물만 마셔도 다 토해요 | vomiting |  | ABSTAIN | synonym_unseen |
| 장염 걸린 것처럼 화장실을 들락날락해요 | diarrhea | EV:E_140;EV:E_171;EV:E_194 | ABSTAIN | disease_symptom_confusion;lexical_false_match |

MAPPER 가 **잘못 자동 수락**한 예:

| 문장 | 정답 | MAPPER 예측 | 분류 |
|---|---|---|---|
| 목이 간질간질하면서 기침이 나요 | cough | EV:E_169:present;cough:present | lexical_false_match |
| 감기 나은 뒤로 기침은 멎었어요 | cough | cough:present | temporal_failure |
| 속이 메스껍고 어지러워요 | dizziness;nausea | nausea:present | multi_symptom_failure |
| 아침부터 세 번이나 토했어요 | vomiting | nausea:present | overly_broad_or_specific |
| 먹은 걸 다 게워냈어요 | vomiting | nausea:present | overly_broad_or_specific |
| 헛구역질만 계속 나요 | vomiting | nausea:present | overly_broad_or_specific |
| 물만 마셔도 다 토해요 | vomiting | nausea:present | overly_broad_or_specific |
| 토하지는 않았어요 | vomiting | nausea:absent | negation_failure;overly_broad_or_specific |

- "토했어요 → nausea": 제품 매퍼에는 구토(E_211) alias 가 없고, DDXPlus E_148 질문("메스껍거나 토할 것 같은가요")에 '토'가 걸려 오심으로 들어간다. 구토 보고가 오심으로 자동 저장되는 구조적 오류다.
- "목이 따가워요 → pain": DDXPlus 에서는 인후통(E_97)과 통증+부위(E_53+인두)가 둘 다 가능한 표현이라, 정답 정의에 따라 오답이 아닐 수도 있다(라벨 공간 자체의 중복).

## 실패 분류 (test, 문장 1개에 여러 분류 가능)

| category | EXACT | FUZZY | COMBINED | MAPPER(제품) |
|---|---|---|---|---|
| colloquial_expression | 65 | 7 | 7 | 51 |
| disease_symptom_confusion | 0 | 1 | 1 | 0 |
| lexical_false_match | 3 | 68 | 64 | 4 |
| multi_symptom_failure | 18 | 17 | 18 | 16 |
| negation_failure | 12 | 12 | 12 | 9 |
| other_person_failure | 6 | 4 | 6 | 0 |
| overly_broad_or_specific | 1 | 4 | 4 | 7 |
| site_confusion | 0 | 9 | 9 | 2 |
| spelling_variation | 3 | 3 | 2 | 3 |
| synonym_unseen | 56 | 2 | 2 | 48 |
| temporal_failure | 3 | 3 | 4 | 1 |
| unknown_forced_mapping | 3 | 6 | 6 | 0 |

## 3. 현재 dictionary 의 한계

- 사전(294개 표현, 77개 concept)은 **화면 라벨과 질문문**뿐이다. 환자가 실제로 쓰는 활용형("어지러워요", "숨이 벅차요", "토했어요")이 없다.
- test A+B 중 사전 표현이 그대로 들어 있는 문장은 Top-1 92.9% 이지만, 새 표현은 0.0% 이다 — 사전 방식은 **암기만 되고 일반화가 안 된다**.
- 라벨에서 잘라낸 짧은 조각이 다른 증상으로 오탐을 만든다: "누런 가래가 나오는 기침" → '누런'(누런 콧물 E_182), "얼굴이 부석부석해요" → '얼굴'(얼굴 근육 경련·근력 약화). 다른 사람 문장("남편이 기침을…", "할머니가 숨이 차신대요")과 가정 문장("열이 나면 어떻게 해야 하나요")도 그대로 자동 수락된다(`exact_predictions.csv`).

## 4. fuzzy matching 의 한계

- 문자 유사도는 의미가 아니라 글자 겹침을 본다: "가슴이 아파요" → 1순위 '목이 아픈가요?'(인후통)·2순위 '가슴 두근거림', "땅이 흔들리는 느낌이에요" → 1순위 '삼킬 때 걸리는 느낌'(`fuzzy_predictions.csv`).
- 정답이 상위 3개 안에 들어오는 비율(A+B R@3 48.7%)도 확인 UX 에 쓰기엔 낮다.
- dev 에서 자동 수락해도 될 만큼 정확한 점수 구간이 없었다(T_high 미설정) → fuzzy 는 "확인 질문 후보 생성"으로만 쓸 수 있고 자동 매핑에는 못 쓴다.

## 5. 학습형 entity linker 가 필요한가 — YES

- 규칙: 어떤 baseline 도 test A+B **새 표현** Top-1 ≥ 90%를 넘지 못하면 YES. 실제 최고치 29.7%.
- 다만 이 pilot 만으로 "학습형 모델이 해결한다"는 증거는 없다. 사전을 환자 표현으로 보강했을 때(alias 확장)와 학습형 linker 를 **같은 test 로 비교**해야 결정할 수 있다.
- 로컬 모델: xlm-roberta-base 뿐(문장 유사도 학습 없음) → Baseline 3 NOT_EVALUATED. SapBERT·sentence-transformers 는 지시대로 설치하지 않았다.

## 6. NLU 가 별도로 필요한가 — YES

- 개념 찾기와 별개로 **부정·과거·다른 사람·복수 증상**이 따로 무너진다. 사전·fuzzy 는 구조상 status 를 낼 수 없고, 제품 매퍼도 과거 시점과 검출률이 낮다.
- 다른 사람 증상 누출: EXACT 46.2%, COMBINED 61.5%. 환자 PatientState 에 가족의 증상이 들어가는 위험.
- 필요한 문장 이해 단위(향후 dialogue/NLU 요구사항): mention 별 status(present/absent/historical/uncertain), subject(환자/타인), 복수 mention 분리, attribute 연결.

## 7. MedMap 환자 UX 적용

- **지금 단계에서 자동 매핑을 넓히면 안 된다.** 자동 수락 precision 이 95%에 못 미친다(EXACT 82.0%, MAPPER 77.6%).
- 가능한 형태: 자유 문장 → 상위 3개 후보를 **환자에게 한 번 확인**("숨이 차신 건가요?"). COMBINED 의 ASK 구간에서 정답이 상위 3개에 든 비율 81.8% — 확인 UX 를 쓰더라도 후보 품질이 먼저 올라가야 한다.
- 부정·과거·타인 문장은 확인 질문에서 status 를 따로 묻는 설계가 필요하다(“지금도 그런가요?”, “본인 증상인가요?”).

## 21절 — canonical schema 연결

- 예: “어제 밤부터 왼쪽 가슴이 쥐어짜듯 아파요” → concept `pain`, attributes `{"pain": {"site": "left chest", "onset": "last night", "quality": "squeezing"}}`
- gold attribute 값 90개 중 80개가 초안 스키마 필드(site·onset·quality·severity·aggravating_factors·temporal_pattern·position·context 등)에 들어간다.
- 들어가지 않는 키: amount, color, content, pitting, productive, sputum_color → 증상별 전용 attribute(가래 색·객혈 양·토사물 내용·함요부종 등)가 필요하다. 초안 스키마에 `concept_specific: {}` 칸을 추가하는 수정을 제안(이번엔 문서만, production 무변경).
- 이번 baseline 은 attribute 추출을 하지 않았다(개념 연결만 평가).

## 8. 다음 실험

가장 먼저 하나: **같은 test 로 "환자 표현 alias 보강 사전" vs "학습형 multilingual linker(SapBERT-XLMR 등)"를 비교**한다.
alias 보강은 dev 표현만 보고 만들고 test 는 그대로 봉인해야 한다. 학습형 linker 는 모델 다운로드 승인이 필요하다(이번엔 하지 않음).
NLU(부정·시점·화자)는 개념 연결과 별도 트랙으로 둔다.

## 한계

- 평가 문장·정답 모두 Claude 작성 합성 데이터라 실제 환자 말투·오타·방언 분포를 대표하지 않는다. 숫자는 baseline 간 **상대 비교**로만 쓴다.
- test 177문장(A+B 115문장)으로 작아서 1문장이 약 1%p 를 움직인다.
- 제품 매퍼는 다른 blind set 으로 이미 평가된 모듈이며, 이번 test 와 질문 범위(binary evidence 41개)가 달라 절대 성능 비교가 아니다.

## 재현

```bash
bash exp/step21_korean_symptom_entity_linking/run_all.sh     # 1분 이내, 2회 실행 SHA256 동일 확인(logs/sha1.txt, sha2.txt)
~/ai_env/bin/python exp/step21_korean_symptom_entity_linking/scripts/build_report.py
```
