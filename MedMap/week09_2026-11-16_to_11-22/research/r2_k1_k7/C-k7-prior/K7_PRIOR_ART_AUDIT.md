# K7 선행연구·알고리즘 신규성 감사 (SUBAGENT C)

- 작성: 2026-11-17, 범위: K7(기록 의미·시간·출처·확인 상태 보존)과 예2(검사 결과 as-of 재현)
- 근거 수준 표기: 원문 / 초록 / 2차자료 / 서지만 / 미확인. 상세는 `sources.csv`(S01–S29)
- 태그: [직접 확인한 사실] [실제 실행한 실험 결과] [연구 가설] [아직 검증하지 못한 사항]

## 0. 판정 먼저

| 항목 | 판정 |
|---|---|
| K7 as-of 재현(예2)의 **알고리즘 신규성** | **NO-GO** |
| K7 **시스템·평가 연구**(시간·출처·확인 왜곡 오류 측정) | **CONDITIONAL**(평가 쪽 직접 경쟁 연구 조사 미완) |
| 핵심 근거 | 임상 DB 분야에 이미 **4차원 시간 모델**(valid / transaction / event / **availability time**)과 질의어 T4SQL이 있다(Combi·Montanari·Pozzi). "의료진이 알고 믿은 시점"을 따로 두는 축 = availability time. 환자 발화·입력 지연·정정이 들어간 **증상 예시**까지 저자 슬라이드에 있다 [직접 확인한 사실, S01 원문 슬라이드] |
| 실험 | 표준 SQL(sqlite) 술어만으로 예2의 모든 as-of 질의, 후향적 재해석, 승인 시점 누설, AT 자체 정정을 정확히 구분했다 [실제 실행한 실험 결과] |

---

## 1. 기존 알고리즘 설명

### 1-1. 시간축 대응표 (K7의 6개 시점 → 기존 개념)

| K7 시점 | 기존 개념 | 근거 |
|---|---|---|
| 사건 발생(증상이 실제로 있던 때) | valid time(VT). 시작이 불확실하면 valid-time indeterminacy | S07 초록, S01 |
| 발화(환자·의사가 말한 때) | event time(ET): 사실을 만든 실세계 사건의 발생 시각 | S01 원문 슬라이드 정의 "occurrence time of the real-world event that generates the fact" |
| 시스템 저장 | transaction time(TT), append-only | S01, S06 |
| 의료진 사용 가능 | **availability time(AT)**: "the time interval during which the fact is known and believed correct by the information system". 정보시스템에 의사가 포함된다고 명시 | S01 원문 슬라이드 |
| 추출 확인(의료진 승인) | 별도 사실(승인 이벤트)로 저장하고 그 자체에 AT/TT 부여. openEHR ATTESTATION, FHIR Provenance(occurred vs recorded)와 같은 구조 | S10 원문, S13 2차 |
| 정정 | TT 구간 닫기 + 새 행(이력 보존). AT 자체가 틀린 경우도 "새 데이터를 넣어 수정"한다고 슬라이드에 명시 → AT×TT로 추적 | S01 |

### 1-2. 분야별 요약

1. **시간 DB(분야 6)**: VT/TT 이원 모델, `FOR SYSTEM_TIME AS OF`(SQL:2011, S08 서지), tritemporal의 decision time(Nascimento & Eich 1995, S04 서지; decision time ≤ TT 제약, SQL:2011엔 해당 절 없음, S05 2차), temporal generalization(관계 사이로 사실이 흐를 때 여러 TT, S06 초록) → "환자 기기 / MedMap 서버 / 의사" 각자의 인지 시점을 여러 TT/AT로 두는 구조와 같다 [연구 가설: 대응은 정의 수준].
2. **임상 다차원 시간(분야 6·12)**: Combi 등 4차원 모델 + T4SQL(CIKM 2007, S02 초록; CAiSE 2001, S03 서지). 슬라이드 예시: 9/15 외상, 10/1 두통 시작, 10/7 진찰, 10/10 입력, 10/15 환자가 "두통이 10/14에 멈췄다"고 말함, 외상 날짜 오입력을 10/20 발견·10/21 수정 → 행마다 VT, ETi, ETt, AT, TT [직접 확인한 사실, S01]. K7 예1·예2와 구조가 거의 같다.
3. **불확정 시간**: Dyreson & Snodgrass 1998 — 발생은 확실하나 시각이 불확실한 사건에 possible/definite 질의(S07 초록). "사흘 전부터"는 여기에 해당.
4. **출처·확인(분야 5·10)**: FHIR R5 Provenance `occurred[x]`(활동 시점)·`recorded`(기록 시점)·버전 지정 target, Provenance=생성 / AuditEvent=사용 [직접 확인한 사실, S10]. FHIR Condition `verificationStatus`(unconfirmed|provisional|differential|confirmed|refuted|entered-in-error), `recordedDate`; Condition 자체는 상태 이력이 아님 [직접 확인한 사실, S11]. 시간+provenance 결합은 K-relation 기반 snapshot semantics(Dignös 등 PVLDB 2019, S09 초록).
5. **증분 추론(분야 8·9)**: ATMS·DRed·provenance semiring·differential dataflow — 이번에 재확인 안 함(S28, 이전 Gate 0 2차자료 수준). K7 as-of 질의 자체에는 증분성이 필요 없어 판정에 영향 적음.
6. **누설·as-of 예측(분야 11)**: 예측 시점까지 사용 가능한 자료만 쓰기(일반 원칙), ICD 코드의 사후 입력·수정으로 인한 label leakage(S26 2차), landmarking(S25 서지). = AT/TT 기준 절단.
7. **NLP(분야 3·4)**: NegEx/ConText(부정·가정·과거·경험자, historical 판정은 표면 단서로 한계 — S18 초록), i2b2 2012·THYME(DocTimeRel, 사건-시간 관계 — S20·S21). 상대 시간 표현의 기준점 문제는 이 영역.
8. **요약 충실성(분야 1)**: Van Veen 2024(완전성·정확성·간결성 + 오류 분석, S14), Tang 2023(자동 지표 상관 약함, 오류 유형 정의, S15). 시간·출처 귀속 오류 범주의 유무는 원문 미열람 [아직 검증하지 못한 사항].
9. **환자 보고 vs 기록(분야 2)**: Pakhomov 2008 positive agreement 흉통 74 / 호흡곤란 70 / 기침 63(S17 초록).
10. **법적 감사(분야 12)**: 소송에서 EHR 감사 로그는 주로 "언제 열람"만 보여 주고 "무엇을 봤는지"는 대개 안 보인다는 실무 기사(S27 2차).

## 2. 직접 경쟁 논문 비교표

| 연구 | 문제 | 입력 | 출력 | 알고리즘 | 평가 | 한계(현재 연구 관점) | 원문 여부 |
|---|---|---|---|---|---|---|---|
| Combi·Montanari·Pozzi, T4SQL (CIKM 2007) + 강의 슬라이드 | 임상 사실의 다중 시간 의미 표현·질의 | VT·TT·ETi·ETt·AT가 달린 관계 | 차원별 current/sequenced/nonsequenced/next 의미의 질의 결과 | SQL 확장 질의어 | 확인 못 함 | 승인(확인)을 1급 사건으로 다루는지, 출처 종류(환자/의사/추출) 모델링은 슬라이드에 없음 | 슬라이드 원문 ○ / 논문 ✕(403) |
| Combi & Montanari, CAiSE 2001 | availability time 도입 | 동일 | 동일 | 데이터 모델 | 미확인 | 미확인 | 서지만 |
| Nascimento & Eich 1995 (decision time) | 결정 시점 축 | VT·TT·DT | tritemporal 질의 | 모델 | 미확인 | 의료 특화 아님 | 서지만 |
| Jensen & Snodgrass 1994 (TKDE) | VT/TT 관계 분류, 여러 TT | 시간 관계 | 특수화·일반화 분류 | 형식 분류 | — | 의료 아님 | 초록 |
| Dyreson & Snodgrass 1998 (TODS) | 불확정 valid time | 확률/구간 시각 | possible/definite 답 | SQL 확장·질의 처리 | 성능 | 상대 표현의 기준점 결정은 범위 밖 | 초록 |
| Dignös 등 2019 (PVLDB) | 시간 질의의 정확한 snapshot semantics | 구간 시점 multiset | 정확한 집계·차집합 | K-relation | 미들웨어 성능 | 의료·승인 없음 | 초록 |
| FHIR R5 Provenance / Condition | 생성 이력·확인 상태 표준 | 자원 버전 | Provenance 기록, verificationStatus | 표준 명세 | — | as-of 질의 의미 정의는 없음(버전 이력 `_at`은 TT 의미, 벤더별) | 원문 ○(일부) |
| ClinicalBench/EpiKG (arXiv 2026) | 다회 입원 질의응답에서 assertion 민감 검색 | MIMIC-IV 노트 | 사실별 assertion+temporality tag KG, QA | KG-RAG | 400문항, 의사 판정 | 초록상 as-of·정정 이력·출처 시점 없음 | 초록 |
| Zep/Graphiti (arXiv 2025) | LLM 기억의 bi-temporal KG | 대화 | 유효 구간·무효화가 달린 사실 | LLM 추출 + 이원 시간 | DMR, LongMemEval | 의료 아님, 승인 축 없음 | 초록/2차 |
| Van Veen 2024 / Tang 2023 | 임상 요약 품질 | 임상 텍스트 | 요약 + 의사 평가 | LLM 적응 | 독자 연구 | 시간·출처 귀속 오류를 따로 재는지 미확인 | 초록 |
| ConText / THYME / i2b2 2012 | 부정·시간 추출 | 임상 노트 | assertion, 시간 관계 | 규칙·지도학습 | 공개 코퍼스 | 환자 구어·한국어 아님 | 초록/서지 |

## 3. 현재 연구(MedMap K7)와 중복

- [직접 확인한 사실] `encounterLink.ts` `stateAsOf`는 `availableAt <= at`로 의사 진술을 자르고 환자 기록은 `recordedAt <= at`로 자른다 = availability/transaction time 기준 "current" 질의. Combi의 AT 축과 같은 개념.
- [직접 확인한 사실] `PatientEvent.source`, `clinicallyVerified: false`, `TestStatus`, 리뷰 상태(candidate/accepted/edited/rejected) = provenance + verificationStatus 계열.
- [직접 확인한 사실] `NeedsCheck`의 "서로 다른 시점일 수 있음" = 시간 변화 vs 모순 구분(K4). Allen 구간 관계 + 규칙으로 환원(이전 Gate 0 E 판정과 같음).
- **중복 결론**: K7의 시간·출처 데이터 구조는 기존 4차원 시간 모델 + provenance 표준의 부분집합이다.

### 3-1. 코드에서 발견한 반례(D 담당에 전달)

- [직접 확인한 사실] `stateAsOf(..., {reviewedOnly: true})`는 `candidate.review === "accepted" | "edited"`만 보고 **`reviewedAt <= at`을 확인하지 않는다**(encounterLink.ts 147–160행). `edited` 값도 시점과 무관하게 적용한다.
- [직접 확인한 사실] `doctorAB.test.ts` 106–114행은 모든 후보를 `reviewedAt: 2026-11-16T23:00Z`로 승인한 뒤, `cases.ts` 104–107행의 기대값 "as-of 2026-11-12 → 폐선암: suspected, 병리검사: pending"을 `reviewedOnly: true`로 검사한다. 즉 시험이 **11/16 승인을 11/12 판단에 소급 적용하는 동작을 정답으로 고정**하고 있다. 이것이 과제 예2가 금지한 바로 그 누설이다.
- [연구 가설] 설계 의도가 "오늘 승인된 것만 과거 시점 재생에 쓴다(후향 검토 화면)"일 수 있다. 그렇다면 함수 설명("What was known at a moment")과 맞지 않으므로 둘 중 하나를 고쳐야 한다. 의도 확인 필요.

## 4. 기존 기술로 해결 가능한 문제

[실제 실행한 실험 결과] `exp/asof_bitemporal_demo.py`(sqlite3, 합성 장난감 자료, 실행 1초 미만). 로그: `logs/asof_bitemporal_demo_*_v2.log`(첫 실행 로그는 기본 TT 값을 `INF`로 둔 내 코드 오류로 결과가 전부 비어 있었음 — 기록으로 남김).

예2 모델: f1(11/11 병리 pending, 즉시 승인), f2(의사 진술 "결과 나옴", ET=11/15, VT 시작 ∈ [11/11, 11/15] 불확정), 승인 a2(AT=11/16). 11/18에 "의사는 실제로 11/14에 들었다"는 감사 결과로 f2의 AT를 11/14로 정정(TT 이력 보존).

| 질의 | 결과 | 해석 |
|---|---|---|
| as-was AT=11/12, 승인도 AT 기준 | pending | 정답 |
| as-was AT=11/15, 승인도 AT 기준 | pending | 11/15 진술은 있으나 미승인 → 사실로 안 씀 |
| as-was AT=11/15, **현재 승인 상태** 사용 | resulted | **누설**(MedMap `stateAsOf` 방식과 같은 동작) |
| as-was AT=11/16, 승인 AT 기준 | resulted | 정답 |
| AT=11/14 판단을 DB 상태 TT=11/17에서 재현 | pending | 정정 전 시스템이 믿던 것 |
| AT=11/14 판단을 DB 상태 TT=11/19에서 재현 | resulted | 정정 후 "의사가 11/14에 이미 알았다"로 바뀜 |
| **후향적 재해석**: 현재 지식으로 VT=11/12 상태 | possibly resulted | 나중 정보로 과거 상태를 다시 추정(VT 보정). 당시 판단 재구성과 다른 질의 |

예1: "사흘 전부터 숨이 찼고 지금은 좀 나아졌지만…"(발화 11/10, 입력 11/12) → 발화 시점 기준 onset 11/07, TT 기준으로 잘못 계산하면 11/09. as-was 11/10 상태 "present(improving, not resolved)" vs 요약 "현재 호흡곤란 없음" → 불일치 검출.

결론:
- 예2의 "as-of 11/12 당시 지식" 질의는 **AT(또는 TT) 절단 + 승인 사건의 AT 절단 + TT 슬라이스**만으로 정확히 풀린다. 새 연산 불필요.
- **후향적 재해석 ≠ 당시 판단 재구성**의 구분은 "현재 TT에서 VT 질의" vs "AT/TT로 자른 뒤 질의"로 기존 모델이 이미 구분한다(Combi 슬라이드의 4축, Jensen·Snodgrass VT/TT 직교성).
- VT/TT 이원 모델만으로는 "의사는 11/14에 알았는데 DB 입력은 11/15"를 표현 못 한다 → 그래서 AT가 있다. 이 반례는 기존 4차원 모델이 이미 해결한 것이지 새 문제가 아니다.
- 불확정 발생 시점 → Dyreson·Snodgrass possible/definite. 승인·정정 → provenance/attestation 표준.

## 5. 해결 여부 미확인 문제

1. [아직 검증하지 못한 사항] T4SQL 논문 원문이 **승인(확인) 사건을 사실과 연결된 1급 시간 객체**로 다루는지, 출처 유형별(환자 발화 / 의사 진술 / 자동 추출) 신뢰 정책을 질의 의미에 넣는지. 슬라이드에는 없음 — "없음"으로 단정하지 않는다.
2. [아직 검증하지 못한 사항] 요약·인계물(파생 산출물)의 **as-of 누설률**이나 **시간·상태 왜곡률**을 직접 측정한 임상 연구. 이번 검색 범위에서 못 찾았으나 Van Veen·Tang 원문 오류 범주를 안 읽었으므로 미해결이라 주장하지 않는다.
3. [아직 검증하지 못한 사항] 환자 구어(한국어) 상대 시간·호전 표현("좀 나아졌지만 완전히는 아님")의 정규화 성능. 영어 임상 노트 코퍼스(THYME, i2b2)는 있으나 한국어 환자 발화 자료는 확인 못 함 — 자료 공백이지 알고리즘 공백 아님.
4. [아직 검증하지 못한 사항] MED-HALT, Clinical TempEval 2015–2017 서지·내용(이번 검색에서 확인 안 함).
5. [아직 검증하지 못한 사항] 한국 의료법상 전자의무기록 수정 이력 보존 요건 — 조사 안 함.

## 6. 실제로 필요한 새 계산 문제(있다면)

후보를 정식화해 보았으나 모두 기존 방법으로 환원된다.

| 후보 | 정식화 | 환원 대상 | 판정 |
|---|---|---|---|
| (a) 파생 산출물(요약·판단)의 as-of 정합성 | 산출물 d의 lineage L(d)에 대해 ∀x∈L(d): AT(x) ≤ t_d ∧ ∃승인 a(x): AT(a) ≤ t_d | lineage/provenance + 시간 절단(K-relation 시간 질의, S09) | 새 문제 아님 [연구 가설] |
| (b) 주체별 인지 시점(환자·MedMap·의사) | 사실마다 AT_agent 벡터, 질의 시 주체 지정 | temporal generalization(여러 TT), 다중 AT | 새 문제 아님 [연구 가설] |
| (c) 요약 문장 ↔ 구조화 상태 함의 판정 | 상태 어휘의 순서·포함 관계(present-improving ⊄ absent) + possible/definite | 어휘 설계 + NLI/충실성 평가 | 계산보다 **어휘·루브릭 설계** 문제 |
| (d) 상대 시간 기준점 | "사흘 전"의 기준 = 발화 ET, TT 아님 | DocTimeRel/시간 정규화 | 새 문제 아님 |

- 작은 반례로 확인한 기존 방법의 한계는 **VT/TT 이원 모델**의 한계(AT 부재)와 **구현 실수**(현재 승인 상태 소급, MedMap 코드)뿐이며, 둘 다 기존 4차원 모델·표준 술어로 해결된다 [실제 실행한 실험 결과].
- 수학적으로 새로운 계산 문제는 **찾지 못했다**. "새 문제가 없다"의 증명은 아님(탐색 결과).

## 7. 신규성 판정

| 대상 | 판정 | 이유 |
|---|---|---|
| bitemporal + 확인 시점 + provenance로 as-of 판단 재구성 | **NO-GO** | 임상용 4차원 시간 모델(AT 포함)과 질의어가 이미 있음(S01·S02). 표준 SQL 술어로 예2 전부 해결(실험) |
| tri-/multi-temporal 자체 | **NO-GO** | decision time(1995), availability/event time(2001·2007) 선행 |
| 후향적 재해석 vs 당시 판단 재구성 구분 | **NO-GO**(개념) | VT 질의 vs AT/TT 절단 질의로 기존 구분 |
| K7 시스템·평가 연구(요약·인계에서 시간·상태·출처·확인 왜곡과 as-of 누설을 측정) | **CONDITIONAL** | 알고리즘 기여 없음. 평가 지표·오류 분류의 신규성은 요약 충실성 연구 원문 오류 범주 확인 후 결정 |

이전 Gate 0의 "선택적 재평가 NO-GO"와 일관된다. 이번 감사는 근거를 일부 원문 수준(S01 저자 슬라이드, S10·S11 FHIR 명세, MedMap 코드)으로 올렸다.

## 8. 독립 평가가 필요한 항목

1. T4SQL(CIKM 2007)·CAiSE 2001 원문과 Combi·Keravnou·Shahar(2010) "Temporal clinical databases" 장 열람 — 승인 사건·출처 모델링 범위 확인(5-1).
2. D(코드 반례): `stateAsOf`의 `reviewedOnly` 의미와 `doctorAB.test.ts` 6번 시험 기대값이 소급 승인 누설을 고정하는지 독립 판정(3-1).
3. Van Veen 2024·Tang 2023 원문의 오류 분류에 시간·출처·확인 상태 범주가 있는지 — K7 평가 연구 신규성의 핵심.
4. MED-HALT, Clinical TempEval, NegEx 서지 확인.
5. E(반론): "AT 축을 환자 앱·의사·서버로 나눈 다주체 모델이 기존 temporal generalization을 넘는가" 반론 검토 — 본 감사는 정의 수준 환원만 했다.
6. 지도교수 확인: K7을 알고리즘 연구 아닌 시스템·평가 연구로 진행할지.

## 부록: 산출물

- `/home/<user>/medmap-gate0-followup/C-k7-prior/K7_PRIOR_ART_AUDIT.md`(이 문서)
- `/home/<user>/medmap-gate0-followup/C-k7-prior/sources.csv`
- `/home/<user>/medmap-gate0-followup/C-k7-prior/exp/asof_bitemporal_demo.py`
- `/home/<user>/medmap-gate0-followup/C-k7-prior/logs/`(v1 = 내 코드 오류로 빈 결과, v2 = 수정 후 결과)
