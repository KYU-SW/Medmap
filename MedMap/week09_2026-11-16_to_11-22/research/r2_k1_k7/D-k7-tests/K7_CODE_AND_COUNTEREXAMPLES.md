# K7 — 기존 MedMap 코드 점검과 독립 반례 실험 (SUBAGENT D, 2026-11-17)

판정: **MedMap 구현 결함 다수 재현 / 시간·승인·정정 모델 쪽은 기존 bitemporal + 승인 시점 방식으로 반례 전부 해결 → 이 범위에서 '새 연구 문제 없음'.** 남은 실패는 문장 해석(추출) 단계이며, 이는 기존 임상 NLP 과제(부정·불확실·주체·전언·시간표현 정규화)에 해당한다.

전제: 의료 전문가 정답 없음. 반례·정답·기준선 (d)(e) 구현을 모두 같은 작성자(D)가 만들었다. 반례는 MedMap 코드를 읽고 약점을 겨냥해 만든 것이므로 **아래 비율은 실제 오류 발생률이 아니다.**

---

## 1. 실제 확인한 코드 [직접 확인한 사실]

원본 경로 `~/medmap-team/MedMap/apps/web/src/` (해시 전체: `logs/source_sha256.txt`)

| 파일 | 줄 수 | SHA-256(앞 16자) | 확인한 핵심 위치 |
|---|---|---|---|
| research/doctorAB/encounterLink.ts | 182 | 6a0e6456b8bb01b9 | NeedsCheck 38행, patientCurrent 110행(마지막 기록값), correctedBy 112행, needsCheckOf 128~144행(136행 `same.every`), stateAsOf 147~167행(150행 availableAt, 154행 reviewedOnly 가 review 시각 미비교, 165행 patient=recordedAt 순), unknownsOf 172행 |
| research/doctorAB/clinicianStatement.ts | 175 | f6a3202ff428b6f8 | TestStatus 9행, FAMILY 67행, CONFIRMED 70행, RULED_OUT 71행, NOT_CONFIRMED 72행, NOT_DONE 76행, 첫 언급만 남기는 `seen` 135행, statementRecord availableAt=enteredAt 172행 |
| research/doctorAB/DoctorExplanationPanel.tsx | 174 | 466fd3f6f7e1df2e | 29행 patientId=`handoff:${recordGroup.id}`(인계 자료에 환자 식별 없음, 28행 주석이 인정), 39행 spokenAt=enteredAt=now, 47행 같은 후보의 이전 리뷰를 지우고 새 리뷰로 교체(리뷰 이력 미보존), 150~158행 '두 출처가 다르게 말한 것 — 확인 필요' |
| research/doctorAB/cases.ts | 236 | b76cdd46ebab6dd9 | PREREGISTRATION.md 기록 해시와 일치(기대값 무변경 확인). 12사례 |
| research/doctorAB/knowledgeRegistry.ts | 61 | 55f194800f13dbf8 | 3개 항목 모두 active:false, expertReviewed:false, 출처 미확보 |
| research/doctorAB/PREREGISTRATION.md | 7 | 605381f68b0a0af1 | '같은 사람이 기대값·구현 작성 → 독립 시험 아님' 명시 |
| research/doctorAB/doctorAB.test.ts | 189 | f4625061138f5f3f | 실행하지 않음(저장소 내 vitest 금지) — 하네스 방식만 참고 |
| intake/extractor.ts | 2311 | 30ff1905e6a5d7e8 | 증상 관찰을 **문장 위치 순**으로 정렬(2020행), '과거…현재 없음' 패턴만 과거/현재 2관찰로 분리(2000~2007행) |
| clinicalHandoff.ts | 492 | a99e59d69305c7bc | ClinicalHandoffV2 45행(환자 식별자 필드 없음), handoffRecords 484행 |
| handoffView.ts / handoffTransfer.ts / clinicalReviewContract.ts / qrCrypto.ts | 124/57/56/107 | 해시 로그 참조 | 존재 확인만. 이번 12위험 판정에 직접 쓰지 않음 |

## 2. 구현 완료 / 미구현 구분 [직접 확인한 사실]

구현됨
- 의사 설명 원문 보존, 후보마다 근거 절(evidence) 보존, documentVerified:false 고정.
- 다른 환자·다른 에피소드 **설명**은 patientId/episodeId 필드로 연결 거부(개발 사례 X01).
- 설명의 availableAt(=enteredAt) 기준 as-of 필터(stateAsOf 150행).
- 정정 설명은 원래 설명을 지우지 않고 correctedBy 로 표시.
- 환자 기록의 같은 증상 여러 관찰 보존(이름으로 병합하지 않음).
- 출처 간 차이는 '확인 필요'로만 표시, '서로 다른 시점일 수 있음' 문구 포함(모순 단정 안 함).
- 의사 확인 목록은 accepted/edited 후보만.

미구현(코드에 없음)
- 리뷰(승인·수정·거절)의 시점 처리: Review.reviewedAt 은 저장되지만 stateAsOf 에서 쓰이지 않음.
- 정정(correctionOf)의 의미 반영: stateAsOf·needsCheck 어디에서도 correctionOf 를 쓰지 않음(표시용 correctedBy 만).
- 사건 시점(valid time): 환자 증상의 onset/onset_date 는 저장만 되고 현재 상태·as-of 계산에 쓰이지 않음.
- 인계 자료(handoff)의 환자 식별 검증: 형식에 환자 식별자가 없음.
- 리뷰 이력: 패널은 같은 후보의 새 리뷰가 이전 리뷰를 대체.
- 전언(누가 누구에게 들은 말인지) 표지 없음.
- knowledgeRegistry 는 비활성 후보 목록뿐(판단 로직 없음).

## 3. 재현된 오류 [실제 실행한 실험 결과]

(c)=MedMap 복사본. 위험=사전 정한 '위험 값'과 일치, 놓침=허용 값도 위험 값도 아님.

| 위험 | 반례 | MedMap 결과 | 기대 | 판정 | 원인(코드) | 분류 |
|---|---|---|---|---|---|---|
| 1 | N01.q1 11-10 설명, 11-15 승인 → 11-12 시점 reviewedOnly | 폐렴 suspected | 없음 | 위험 | 154행: review 시각 미비교 | 구현 결함 |
| 1 | N02.q1 11-15 수정(확진으로) → 11-12 시점 | confirmed_by_clinician | suspected | 위험 | 160~162행 edit 소급 | 구현 결함 |
| 1 | N03.q1 11-15 거절 → 11-12 시점(미거절 보기) | 없음 | suspected | 놓침 | 154행 거절 소급 | 구현 결함 |
| 2 | N04 "결핵으로 진단됐었는데 재검사에서 결핵이 아닌 것으로 확인됐습니다." | confirmed, 언급 1개 | ruled_out, 2개 | 위험 | 135행 첫 절만 | 구현 결함(설계 주석상 의도된 단순화) |
| 2 | N05 "조직검사 결과를 기다리는 중이었는데 오늘 병리 결과가 나왔습니다." | pending, 1개 | resulted, 2개 | 위험 | 135행 | 구현 결함 |
| 3 | N06 09:00 "열은 없어요" → 12:00 입력 "지난주에 열이 났었어요" | 현재 present, 13:00 as-of present | absent | 위험 | 110·165행 기록 시각 순, onset 미사용 | 구현 결함 |
| 4 | N08 확인 전 후보로 생긴 '확인 필요' 항목 | 리뷰 상태 필드 없음 | 확인 전 표시 | 놓침 | NeedsCheck 타입 38행 | 구현 한계(부분) |
| 5 | N09.q1 "CT를 찍지 않으면 정확히 알 수 없습니다." | not_done | 미정 | 위험 | 76행 NOT_DONE 이 조건문에 일치 | 구현 결함 |
| 6 | N10.q1 "폐선암으로 확진된 것은 아닙니다." | ruled_out | 미확진(unknown 등) | 위험 | 72행 NOT_CONFIRMED 미일치 → 71행 '아닙니다' | 구현 결함 |
| 6 | N10.q2 "폐렴이 확진됐다고 하기는 어렵습니다." | confirmed | 미확진 | 위험 | 70행 '확진' 단독 일치 | 구현 결함 |
| 6 | N10.q4 "폐렴은 아니고 결핵이 의심됩니다." 중 폐렴 | mentioned_only | ruled_out | 놓침 | RULED_OUT 어휘 부족 | 구현 한계 |
| 7 | N11.q1 "조직형은 선암으로 확인됐습니다." | subject=family, mentioned_only | patient, confirmed | 위험 | 67행 FAMILY 의 '형'이 '조직형' 부분 일치 | 구현 결함 |
| 7 | N11.q3 "형태상 폐선암이 의심됩니다." | family, mentioned_only | patient, suspected | 위험 | 67행 '형태' 부분 일치 | 구현 결함 |
| 7 | N11.q5 "어머니 말씀으로는 환자분이 작년에 결핵 진단을 받으셨다고 합니다." | family | patient | 위험 | 전달자(어머니)와 주체(환자) 미구분 | 구현 한계 |
| 8 | N12.q1 다른 환자의 인계 자료(같은 기록 묶음 id `existing-records`) | 연결 수락 | 거부/경고 | 위험 | handoff 에 환자 식별 없음(패널 28행 주석이 인정) | 설계 한계(시스템) |
| 8 | N12.q2 "옆 병상 환자분은 결핵으로 확진됐습니다." | subject=patient, confirmed | 타인 | 위험 | FAMILY 외 타인 표현 없음 | 구현 결함 |
| 9 | N13.q2 철회형 정정("앞의 설명은 잘못 입력한 것입니다", correctionOf=s1) 후 | 폐렴 suspected 유지 | 없음/철회 | 위험 | correctionOf 미사용 | 구현 결함 |
| 10/11 | N14 11-11 설명 "열이 있다고 하셨습니다" vs 11-10 기록 '열 있음'(당시 일치), 11-16 기록 '열 없음' | '확인 필요' 표시 | 표시 안 함 | 놓침(오탐) | 136행이 설명 시점 이후 기록까지 비교 | 구현 결함(경미, 문구는 보수적) |
| 12 | N16 "환자분이 다른 병원 CT에서 결절이 있었다고 하셨습니다." | CT resulted (출처 clinician_reported) | 전언 표지 | 위험 | 전언 표지 없음 | 구현 한계 |

사후 관찰(결과를 본 뒤 추가, 채점 제외) — `logs/posthoc_extractor_check.log`
- "오늘은 열이 없는데 지난주에는 열이 났었어요." → 관찰 1개(absent)만 남고 **과거 '지난주 발열' 관찰이 사라짐**. 순서를 바꾼 "지난주에는 열이 났었는데 오늘은 없어요." 는 2개 관찰 보존. 현재 상태(N07)는 맞지만 과거 사실이 소실됨 → extractor 구현 한계.
- "지난주" 는 onset 문자열만 있고 onset_date=null (어제는 날짜로 환산됨).

## 4. 재현되지 않은 위험 (MedMap 이 정확히 처리) [실제 실행한 실험 결과]

- 위험 3 (한 기록 안 현재 상태): N07 현재=absent 정답(단 위 사후 관찰처럼 과거 관찰 소실).
- 위험 4 (확정 처리): 확인 전 후보는 '의사 확인 정보' 목록에 들어가지 않음(N08.q2).
- 위험 5: "다음 주에 할 예정" → result_uncertain, "찍었는데 결과는 아직이에요" → result_uncertain (둘 다 위험 값 아님, 정밀도는 낮음).
- 위험 6: "결핵 가능성을 배제할 수는 없습니다" → suspected 정답, "결핵이 의심됩니다" 정답.
- 위험 7 (환자 기록 쪽): "어머니가 기침을 해요. 저는 기침 없어요." → 환자 기침 absent 정답.
- 위험 9 (원본 보존): 정정 후에도 원래 설명 원문·후보 보존(N13.q3).
- 위험 10 ('무조건 오류' 판정): 재현 안 됨. needsCheck 문구는 항상 '확인 필요'·'서로 다른 시점일 수 있음'(N08·N14 q2=false).
- 위험 11 (늦게 입력된 설명): availableAt 기준으로 11-12 시점에서 제외, 11-17 시점에 포함(N15 정답).
- 위험 12 (출처 분리): stateAsOf 결과에서 환자 기록과 의사 설명이 별도 키로 분리(N16.q2).
- 복사본 동등성: 원본 개발 사례 12건 12/12 일치(`logs/vendor_sanity_20261117_202330.log`).

## 5. 독립 반례

- 입력: `cases/cases_v1.json` (16사례, 40질의, 합성 문장, cases.ts 문장 재사용 없음)
- 정답: `expected/expected_v1.json` — **2026-11-17T20:21:25+09:00 실행 전 작성**, SHA-256 99c10390…(`expected/WRITTEN_AT.txt`). 질의마다 expected / acceptable / dangerous 세트.
- 실행 전 가설: `expected/PREDICTIONS_ABOUT_MEDMAP.md` — 예측 13개 항목 중 N07(현재 상태 덮어씀 예상)만 빗나감, 나머지 예측 방향 일치.
- 정답 정정: 없음(`expected/CORRECTIONS.md`, 해석 여지 4건 기록).
- 하네스 버그 1건 수정(v1→v2, (d)(e)의 patient_current 질의만 영향, (c) 값 불변).

## 6. 기준선 비교 표 [실제 실행한 실험 결과]

방법: (a) 단순 문자열·이름 비교(시간·승인·주체 개념 없음) (b) 시간순 마지막 값(CRUD 현재값, 이력 없음) (c) MedMap 복사본 (d) bitemporal: 사건 시점(valid)+입력 시점(transaction), 정정=원래 행 닫기, 승인은 시점 없는 현재 속성 (e) (d)+승인·수정·거절을 각자 입력 시점을 가진 사건으로 + 확인 상태를 결과에 실음.
(b)(d)(e)는 (c)와 **같은 MedMap 추출 결과**를 입력으로 쓴다 → 추출 단계 질의에서는 (c)와 같은 값.

### 6-1. 층위별 (허용/전체, 괄호=위험 값) — `results_by_layer.csv`

| 층위 | n | (a) | (b) | (c) MedMap | (d) | (e) | (d) 사전 | (e) 사전 |
|---|---|---|---|---|---|---|---|---|
| T 시간·승인·정정 | 19 | 7 (9) | 9 (7) | 11 (5) | 13 (4) | 17 (2) | 15 (2) | **19 (0)** |
| X 문장 해석(추출) | 20 | 12 (8) | 5 (10) | 5 (10) | 5 (10) | 5 (10) | 5 (10) | 5 (10) |
| I 인계 자료 환자 식별 | 1 | 0 (1) | 0 (1) | 0 (1) | 0 (1) | 0 (1) | 0 (1) | 0 (1) |
| 합계 | 40 | 19 (18) | 14 (18) | 16 (16) | 18 (15) | 22 (13) | 20 (13) | 24 (11) |

'사전' = 민감도 분석(사후 추가): 사건 시점에 상대시간 사전(어제/그저께/N일 전/지난주)을 적용. (e)가 T층에서 남긴 실패 2건(N06 q1·q2)은 시간 모델이 아니라 "지난주" 의 날짜 환산(onset_date=null) 부재 때문이며, 사전 적용 시 해결.

### 6-2. 지표별 (허용/전체, 괄호=위험) — `results_by_metric.csv`, `results_by_metric_validtime_lexicon.csv`

| 지표 | (a) | (b) | (c) | (d) | (e) |
|---|---|---|---|---|---|
| 원문 의미 보존 (16) | 9 (7) | 5 (6) | 5 (6) | 5 (6) | 5 (6) |
| 증상 상태 정확성 (4) | 1 (3) | 2 (2) | 2 (2) | 2 (2) → 사전 4 (0) | 2 (2) → 사전 4 (0) |
| 시점별 사실 재현 (5) | 3 (1) | 5 (0) | 5 (0) | 5 (0) | 5 (0) |
| 당시 사용 가능 정보만 복원 (4) | 2 (2) | 0 (3) | 1 (2) | 1 (2) | 4 (0) |
| 확인 전 정보 확정 처리 (2) | 0 (1) | 1 (0) | 1 (0) | 1 (0) | 2 (0) |
| 정정 반영·원본 보존 (2) | 1 (1) | 1 (1) | 1 (1) | 2 (0) | 2 (0) |
| 환자·주체 혼합 (5) | 3 (2) | 0 (5) | 0 (5) | 0 (5) | 0 (5) |
| 잘못된 충돌 탐지 (2) | 0 (1) | 0 (1) | 1 (0) | 2 (0) | 2 (0) |

해석 주의
- (a)가 '원문 의미 보존'에서 (c)보다 높은 것은 반례를 MedMap 정규식의 약점을 겨냥해 골랐기 때문이다(선택 효과). (a)가 일반적으로 낫다는 뜻이 아니다. (a)는 시간 층에서 가장 나쁘다.
- 소표본(층당 19~20 질의), 단일 작성자 정답. 통계적 비교 아님.

## 7. 실행 로그 경로

- `logs/git_status_before.txt`, `logs/git_status_after.txt` — 원본 저장소 상태(작업 전후)
- `logs/source_sha256.txt`, `logs/vendor_sha256_after_import_fix.txt`
- `logs/vendor_sanity_20261117_202330.log` — 복사본 동등성 12/12
- `logs/run_20261117_202330.log` — v1(하네스 버그 포함), `logs/run_v1_before_harness_fix.ts.txt`
- `logs/run_v2_extracted_20261117_202408.log`, `logs/run_v2_lexicon_20261117_202408.log` — 본 결과
- `logs/medmap_raw.json` — 사례별 MedMap 원출력(후보·환자 이벤트·needsCheck)
- `logs/posthoc_extractor_check.log` — 사후 관찰
- 결과 CSV: `results_queries*.csv`, `results_by_metric*.csv`, `results_by_risk*.csv`, `results_by_layer.csv`
- 명령: `RUN_COMMANDS.md`

## 8. 기술적 신규성 관점 결론

[실제 실행한 실험 결과]
- 시간·승인·정정 층(위험 1·3·4·9·10·11): 표준 bitemporal(사건 시점+입력 시점, 정정=행 닫기)에 승인 사건의 입력 시점을 추가한 (e)가 이 반례 19질의를 모두 해결(사건 시점 날짜 환산 포함 시). MedMap 은 같은 질의에서 11/19, 위험 5건.
- 따라서 이 범위의 실패는 **MedMap 구현 결함**이며, 학술적 미해결 문제의 근거가 아니다. **이 범위에서는 새 연구 문제 없음.**

[연구 가설 / 아직 검증하지 못한 사항]
- 추출 층(위험 2·5·6·7·12, 위험 8의 문장 속 타인): bitemporal 은 해결 범위 밖. 대응하는 기존 연구 범주는 임상 문장의 부정·불확실·주체(experiencer)·시간성 판정(NegEx/ConText 계열, i2b2 2010 assertion, 2012 temporal 과제 등)과 전언·출처 귀속이다. 이 계열 기존 방법을 **이번에 구현·실행하지 않았다.** 한국어 의사 구두 설명에서 이들 방법이 충분한지는 확인 필요(선행연구는 SUBAGENT C 담당).
- 상대시간 정규화("지난주")는 기존 시간표현 정규화(TIMEX 계열) 과제. 이번 사전은 4개 표현짜리 장난감이며 일반 성능 근거 아님.
- 인계 자료 환자 식별(위험 8, N12.q1): 시간 모델·NLP 어느 쪽도 아닌 시스템 설계 문제(환자 식별자·서명된 결속). 학술 문제 아님.
- (d)(e)를 반례 작성자 본인이 구현했으므로 기준선이 반례에 유리하게 맞춰졌을 가능성 배제 불가. 독립 구현(예: 기존 bitemporal DB 의 as-of 질의)으로 재확인하지 않았다.

## 9. 기존 MedMap 수정 여부 [직접 확인한 사실]

- 수정 없음. `git -C ~/medmap-team/MedMap status --short` 작업 전(20:16:54)·후 출력 **동일**(M 7개, ?? 9개 — 원래 사용자 미커밋 상태 그대로).
- 대상 원본 15개 파일 SHA-256 작업 전후 동일. 실행 후 `find -newer` 로 저장소 안 새로 바뀐 파일 없음 확인(.git·node_modules 제외).
- 저장소 안에서 vitest·npm·pnpm·git 쓰기 명령 실행 없음. cases.ts 기대값 무변경. 보류 작업(MM2/MM2F 의사 화면 이전 자료 잔류 검증, 휴대폰 2대 QR 시험) 손대지 않음.
