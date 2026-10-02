# EXP-SN-001 문헌 조사 (C1–C9) · 출처·라이선스 감사

- 작성 2026-10-02 · 범위: 흉통 진료지침·질환별 지침·라이선스. **질환 사실표(fact table) 작성 아님, DDXPlus 매핑 아님**
- 방법: 독립 조사 에이전트 3개(흉통 지침 / 질환별 지침 / 라이선스)가 WebSearch로 찾고 원문을 직접 읽었다(WebFetch 또는 PDF 텍스트 추출). 검색 snippet만 있는 근거는 제외했다.
- **검증 수준 주의**: 아래 인용·위치는 에이전트가 추출한 것이다. 사실 작성 단계의 VERIFIER B(K3)가 원문과 다시 대조하기 전까지는 **"agent-extracted, unverified"** 상태로 취급한다.

## 0. 공개 사항
1. **AI 열람**: 이번 조사는 AI(에이전트)가 ESC·NICE·AHA 등의 지침 원문을 읽는 방식으로 진행했다. 그런데 ESC는 TDM(텍스트·데이터 마이닝) 예외에서 빠지겠다고 밝혔고(opt-out), NICE는 AI 사용을 라이선스 범위 밖으로 둔다(§4). 연구 목적 열람이 이 조항에 걸리는지는 **확인 필요**다. 앞으로 AI가 지침 원문을 다시 읽거나 지식으로 쓰는 일은 §4의 허가 결정 뒤로 미룬다.
2. **정식판이 아닌 사본**: 출판사 사이트가 403을 내서 일부 PDF는 제3자 사이트에 올라온 사본을 읽었다(allinahealth.org, sochicar.cl, cbsmd.cn, scc.org.co, uniklinik-ulm.de). 정식판과의 대조는 K3에서 한다. 사본에서 읽었다고 사본 재배포를 허용한다는 뜻은 아니다.
3. **요약 경유**: ACG GERD 지침(S4b)과 NCCP 리뷰(S5b)는 원문 대신 도구가 만든 요약을 거쳐 확인했다. 검증 수준이 더 낮다.
4. 대한심장학회 흉통 지침은 찾지 못했다(확인 필요).

## 1. 출처표
| ID | 기관·문서 | 연도 | 유형·Tier | 지원 C | 접근 | 라이선스·재사용(§4) |
|---|---|---|---|---|---|---|
| G1 | AHA/ACC/ASE/CHEST/SAEM/SCCT/SCMR Guideline for the Evaluation and Diagnosis of Chest Pain (Gulati 외, Circulation 2021;144:e368) | 2021 | 진료지침 T1 | C1·C3·C5·C6·C7·C2 | 전문(사본) | LICENSE_UNCLEAR, 운영 사용 UNCLEAR |
| G2 | NICE CG95 Recent-onset chest pain of suspected cardiac origin | 2010, 갱신 2016-11 | 진료지침 T1 | C1·C3·C5·C7 | 전문(공식) | 해외 운영 사용 NO, AI 사용 NO, 허가 필요 |
| G3 | 2023 ESC Guidelines for the management of ACS + 보충자료 | 2023 | 진료지침 T1 | C1(mimics)·C5·C7 | 전문(사본) | 운영 사용 NO, 소프트웨어 사용 시 정식 라이선스 필요, TDM opt-out |
| G4 | ACEP Clinical Policy: Suspected NSTE-ACS | 2018 | 진료정책 T1 | (범위 한정) | 전문(공식) | 미감사 |
| S1 | 2019 ESC/ERS Guidelines on acute PE | 2019 | 진료지침 T1 | C2·C4 구조 | 전문(사본) | ESC 정책과 같음 |
| S2 | 2025 ESC Guidelines for myocarditis and pericarditis | 2025 | 진료지침 T1 | C2·C6 | 전문 | ESC 정책과 같음 |
| S3 | BTS Guideline for pleural disease (Thorax) | 2023 | 진료지침 T1 | (ACS 감별 없음) | 전문 | LICENSE_UNCLEAR |
| S4b | ACG Clinical Guideline for GERD (Am J Gastroenterol) | 2022 | 진료지침 T1 | C2 | PMC 저자원고, **요약 경유** | LICENSE_UNCLEAR |
| S5b | Li 외, Non-cardiac chest pain review (Gastroenterol Hepatol, PMC11523089) | 2024 | 서술 리뷰 T2 | C2 | **요약 경유** | 미감사 |
| S6 | Katerndahl, Panic & Plaques (J Am Board Fam Pract 2004;17:114) | 2004 | 체계적 리뷰 T2 | C2 | 전문 | 미감사 |
| S8 | ACC/AHA Guideline for aortic disease (JACC 2022;80:e223) | 2022 | 진료지침 T1 | C6 | 전문(사본) | LICENSE_UNCLEAR |
| S9 | WSES guidelines on esophageal emergencies (WJES 2019;14:26) | 2019 | 학회 지침 T1 | C6 | 전문 | 미감사 |
| S10 | 2021 ESC HF guidelines | 2021 | 진료지침 T1 | C6 | ACCESS_LIMITED | ESC 정책과 같음 |
| — | NICE CG113(불안·공황), 2024 ESC 대동맥 지침, 2026 AHA/ACC PE 지침 | — | — | — | 열람 실패 | — |

## 2. 항목별 근거 요약 (위치는 원문 기준, unverified)

### C1·C6 생명을 위협하는 흉통 원인(cannot-miss)
- G1 §2.1(e377): "life-threatening conditions such as ACS, aortic dissection, and PE, as well as nonvascular syndromes (eg, esophageal rupture, tension pneumothorax)"
- G1 §2.2(e380): "Life-threatening causes … include, but are not limited to, ACS, PE, aortic dissection, and esophageal rupture"
- G1 §4 서두(e387–388):
  - "potentially life-threatening (emergency)": ACS, 급성 대동맥 증후군, PE, 전격성 심근염
  - "immediately life-threatening" 비심혈관 원인: 식도 파열, 긴장성 기흉, 겸상적혈구 흉부 위기
- G2 1.2.2.8: "First consider those that are life-threatening such as pulmonary embolism, aortic dissection or pneumonia"
- G3 Table S5: ACS를 흉내 낼 수 있는 질환(mimics)을 나열. 심근염·심낭염, 빈맥, 급성 심부전, PE, (긴장성) 기흉, 대동맥 박리, 식도염·역류, 불안장애 등. **긴급도 표시는 없음**
- S8: 급성 대동맥 증후군은 "life-threatening", 사망률 시간당 1–2 %. S9: 식도 파열은 "life-threatening", 초기 양상에 "no specific patterns"

### C3 위험·긴급도 표현 (원문 용어 유지)
- G1: 원인 일반은 "life-threatening/emergency" 대 "Nonemergency causes"(§4). ACS가 의심되는 환자만 저·중·고위험으로 나누며, 그 기준은 심전도·트로포닌·CDP 점수다(§4.1).
- G2: 의뢰 긴급도 "as an emergency" / "urgent same-day assessment"(1.2.1.7–8). MI 위험 high·moderate·low는 "validated tool"로 판정한다.
- G3: NSTE-ACS의 "very high-risk criteria"(§5.2.2)는 혈역학 불안정 등 진찰·검사 소견이다.
- **결론**: 병력만으로 정하는 HIGH/LOW 질환 등급은 출처에 없다. 출처가 쓰는 범주는 G1 §4의 **"life-threatening (emergency)" 대 "nonemergency"**다.

### C5 "red flag"
- G1·G2·G4: "red flag"라는 용어 없음. G1은 "life-threatening", "emergency", "high-risk features", "Specific clues"(Table 4)를 쓴다.
- G3: 일반인 대상 문장 하나(p17) "red flag symptoms such as prolonged chest pain (>15 min) and/or recurrent pain within 1 h"
- S2 Table 16: 심낭염의 "high-risk features or red flags"
- **결론**: red flag 목록을 새로 만들지 않는다. 출처 용어(emergency evaluation·high-risk features 등)를 그 출처 범위에서만 쓴다.

### C7 흉통 병력 항목
- G1 §2.1: "1) nature; 2) onset and duration; 3) location and radiation; 4) precipitating factors; 5) relieving factors; and 6) associated symptoms" + 심혈관 위험인자(권고 1). Table 3 "Chest Pain Characteristics and Corresponding Causes"
- G2 1.3.2.1: 부위, 방사, 강도, 지속시간, 빈도, 유발·완화 요인, 동반 증상, 위험인자. 1.2.1.3: 15분을 넘는 통증 등
- G3 보충 §3.1.1: quality, location, radiation, provoking and relieving factors + 위험인자

### C2·C4 병력만으로 되는 것과 안 되는 것
- G1 §1.4.2: "The diagnosis of ischemia may require data beyond history alone"
- G1 §2.3: 도착 10분 안에 심전도, 가능한 한 빨리 트로포닌. "An initial normal ECG does not exclude ACS"
- G1 §4.3.1: 위장관 증상은 "not sufficiently specific to be fully diagnostic"
- G1 §4.3: 불안·공황은 "diagnoses of exclusion"
- G2 1.2.2.5: "Do not exclude an ACS when people have a normal resting 12-lead ECG". 1.3.3.5: 협심증 가능성을 낮추는 병력 특징이 있음
- G3 보충 p6: "diagnostic performance of chest pain characteristics is limited"
- S1 §4.1: PE의 임상 징후는 "non-specific". 중심성 PE는 협심증 양상을 보여 ACS·대동맥 박리와 감별이 필요하다. D-dimer·CTPA·검사 전 확률을 쓴다.
- S2 §5.11: "ACS is the main differential diagnosis"(심근염·심낭염 증후군). 관상동맥 CT·조영술, CMR이 필요하다. §4.5에 심낭염의 감별 목록(ACS, HF, 흉막염 동반 폐렴, PE, COPD, 혈관염)
- S4b: GERD 흉통은 "indistinguishable from cardiac pain", 심장 평가가 먼저다. S6: 흉통 특성으로 공황과 CAD를 "do not accurately distinguish"

## 3. 후보 감별쌍 (PROPOSED — 최종 포함은 결정하지 않음)
| pair_id | A | B | 출처 | 출처가 밝힌 이유 | history_discriminable | biomarker_or_test_dependent | research_scope_status | review_status |
|---|---|---|---|---|---|---|---|---|
| P1 | ACS | GERD/비심장성 흉통 | G1 §4.3.1, S4b, S5b | 흉통이 심장성과 구별 불가 | partial | yes(심장 배제가 먼저) | candidate | unreviewed |
| P2 | ACS | PE | S1 §4.1·§7.1.1, G1 | 중심성 PE의 협심증 양상 흉통 | partial | yes(D-dimer·CTPA) | candidate | unreviewed |
| P3 | ACS | 심낭염(·심근염) | S2 §5.11·§4.5, G1 Table 3 | 증상·트로포닌·심전도 중첩 | partial | yes(관상동맥 영상·CMR) | candidate | unreviewed |
| P4 | ACS | 기흉 | G1 §4·Table 4 | 긴장성 기흉은 생명 위협 원인 | UNKNOWN | yes(흉부 X선) | candidate | unreviewed |
| P5 | ACS | 공황/불안 | S6, G1 §4.3.2 | 흉통 특성으로 구별 불가, 공존 가능 | no/partial | yes(허혈 배제가 전제) | candidate(제외 우선 검토) | unreviewed |
| P6 | 안정형 협심증 | 불안정형 협심증/ACS | G1 §2.3.1·Table 3 | 안정 시 발생은 보통 ACS | partial | yes(심전도·트로포닌) | candidate | unreviewed |
| P8 | 심낭염 | PE | S2 §4.5 | 감별 대상으로 명시 | UNKNOWN | UNKNOWN | candidate | unreviewed |
| P9 | ACS·PE | 급성 대동맥 증후군 | S1, G1, S8 | 협심증 양상 흉통, 생명 위협 | partial | yes(CT) | **OOS**(DDXPlus에 없음) | unreviewed |
| P10 | 대동맥 박리 | 식도 파열 | S9 | CT로 감별 | no | yes | **OOS** | unreviewed |
| P11 | 심낭염 | 흉막염 동반 폐렴 | S2 §4.5 | 명시적 감별 | UNKNOWN | UNKNOWN | candidate(폐렴은 49질환에 있음) | unreviewed |
| P7 | PE | 기흉 | 직접 비교한 출처 없음 | — | UNKNOWN | UNKNOWN | 근거 없음 → 제외 | — |

- **핵심 관찰**: 출처상 **병력만으로 완전히 구별되는 쌍(history_discriminable = yes)은 하나도 없다.** 확인된 쌍은 모두 partial이거나 UNKNOWN 또는 no이고, 거의 모든 쌍이 검사에 의존한다. 이 관찰은 연구 질문의 기대치와 abstention 설계(prereg §3.5)에 직접 반영한다.

## 4. 라이선스·재사용 감사 (공식 정책 문구 기준, 법률 판단 아님)
| 출처 | 저작권자·라이선스 | 연구 인용 | SW/AI 반영 | 재배포 | production_allowed | research_only | permission_needed | 정책 페이지 |
|---|---|---|---|---|---|---|---|---|
| G1·S8 AHA/ACC(Circulation/JACC) | Circulation판 미확인, JACC판 Elsevier user license | JACC판: 비상업 열람·TDM 허용 | LICENSE_UNCLEAR | JACC판 재배포·각색 불가 | UNCLEAR | YES | UNCLEAR | elsevier.com/open-access/userlicense/1.0 (AHA 정책 페이지는 403) |
| G2·CG113 NICE | NICE UK Open Content Licence(영국 내) | 해외는 "개인 연구·학습" 예외만 허용 | **NO**(AI 사용은 라이선스 범위 밖) | 해외는 유료 라이선스 | NO | YES | YES | nice.org.uk/reusing-our-content/nice-uk-open-content-licence |
| G3·S1·S2·S10 ESC | © ESC, All rights reserved | 개인·교육 목적 | **NO**(정식 라이선스 필요, 연구 목적은 조건부 무료 가능) | 서면 허가 필요 | NO | YES | YES | escardio.org "ESC Guidelines Licensing for AI, LLMs, and CDS Tools" |
| S3 BTS | 미확인 | UNCLEAR | UNCLEAR | BTS 웹 콘텐츠는 동의 없이 불가 | UNCLEAR | YES | UNCLEAR | brit-thoracic.org.uk/terms-and-conditions |
| S4b ACG | 미확인 | PMC 저자원고는 TDM·공정이용 문구 | UNCLEAR | UNCLEAR | UNCLEAR | YES | UNCLEAR | (출판사 페이지 402) |
| APA 공황 지침 | APA | 미국 저작권법 107·108조 범위 | **NO**(서면 허가 없이 AI·ML 입력 금지) | 불가 | NO | YES | YES | psychiatry.org clinical-practice-guidelines |
| G4·S5b·S6·S9 | 미감사 | — | — | — | UNCLEAR | YES | UNCLEAR | 다음 단계 |

- **결론**: 소프트웨어·AI 사용을 명시적으로 허락한 출처는 **하나도 없다**. 구조화한 사실을 실험 소프트웨어에 넣는 것, 그리고 LLM이 원문을 읽고 사실을 추출하는 것(C10)은 **허가 결정 전에는 BLOCKED**다.
