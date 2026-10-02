# STEP 15 — EVIDENCE-BASED DISEASE PROFILE PILOT (10질환) 2026-09-21

## 판정: **STEP15_PROFILE_PARTIAL_GO**

순서 준수: 외부 자료 수집 → fact 작성 → concept 연결·품질감사 → **PROFILE_FREEZE(SHA256)** → 그 후에만 DDXPlus 223 evidence 비교(`s15_post_freeze.py` 첫 줄에서 freeze SHA assert). TEST·AUROC·확률 생성 없음. Step 8~14 무수정.
**정직한 오염 고지**: 프로필 작성자(이 세션의 AI)는 Step 1~14에서 DDXPlus evidence 목록을 이미 본 상태다. 파일은 열지 않았고 모든 fact에 원문 짧은 인용(source_quote_short)을 붙여 출처 검증이 가능하게 했지만, 완전한 blind 작성은 아니다 → 49개 확장 시 작성자와 DDXPlus 분석자를 분리해야 한다.

## 1. Pilot 질환·출처
| DDXPlus 원명 | 정규화명 | 사용 출처 | 비고 |
|---|---|---|---|
| Acute rhinosinusitis | 〃 | MedlinePlus, CDC, AAO-HNS 2015 초록 | |
| Chronic rhinosinusitis | 〃 | 위 3개(급성 항목 내 만성 정의) | 전용 자료 없음(StatPearls 차단) |
| Acute laryngitis | 〃 | MedlinePlus **1개** | StatPearls 차단 |
| Viral pharyngitis | 〃 | CDC, MedlinePlus (IDSA 초록은 임상 내용 없어 미사용) | |
| Stable angina | 〃 | MedlinePlus(+Unstable 항목의 비교 문장) | |
| Unstable angina | 〃 | MedlinePlus **1개** | |
| HIV (initial infection) | Acute HIV infection | HIV.gov, NEJM(PMC OA) | NIH clinicalinfo 403, CDC 404 |
| Scombroid food poisoning | Scombroid poisoning | CDC Yellow Book, MedlinePlus | |
| Acute COPD exacerbation / infection | Acute COPD exacerbation | MedlinePlus ×2 | GOLD PMID 오류로 미확보 |
| PSVT | PSVT | MedlinePlus **1개** | ACC/AHA 2015 초록에 임상 내용 없음 |
시도 25 / 사용 15 / 차단·실패 9(NCBI Bookshelf reCAPTCHA 8, NIH clinicalinfo 403) / 미사용 1. **1순위(정부·학회 가이드라인) 본문을 실제로 확보한 질환은 4개**(CDC 3, AAO-HNS 초록 1), 나머지는 MedlinePlus(NLM 환자용, PUBLIC_DOMAIN) 의존. 라이선스: 공공 15, 저작권 참조 2, 미확인 8(미사용).

## 2. 외부 지식 (`01`, `02`, `03`)
- fact **150** (질환당 9~23, 평균 15.0), 출처 없는 fact 0, 인용 없는 fact 0. 범주: SYMPTOM 45·RISK_FACTOR 22·DISTINGUISHING 10·DURATION 9·SIGN 8·ONSET 6·RED_FLAG 6·TRIGGER 5·ASSOCIATED 5·기타.
- 정량 빈도는 출처에 있을 때만: "about two-thirds" (급성 HIV), 그 외 없음. 임의 확률 0.
- UMLS/SNOMED 연결: EXACT 125 / NOT_APPLICABLE 23(정의·속성 전용) / FAIL 2 (Exposure to tobacco smoke, Sinus tenderness). 복수 CUI 후보 30 → 검토.
- value-level fact(시간·위치·유발·완화·노출·과거력·가족력·약물 속성 보유): 질환당 4~16개, 합계 87.
- **알려진 결함**: 수기 TSV의 attribute 열 정렬이 일부 행에서 어긋남(예: 위험요인 fact에 `family_context`가 잘못 채워짐, Stable angina TRIGGER/RELIEVING fact의 trigger 열 일부 비어 있음). freeze 후 발견 → 수정하지 않고 review queue에 기록, **Step15_v2에서 교정**.

## 3. Coverage (`04`, `05`, `07`) — freeze 후 DDXPlus 비교
| 질환 | DDXPlus 관련 evidence | direct | attribute | partial | 없음 | BASIC(증상/징후) | VALUE-LEVEL(전체) | 기존 KG strict 관계 |
|---|---|---|---|---|---|---|---|---|
| Acute rhinosinusitis | 22 | 4 | 2 | 9 | 7 | 0.571 | 0.273 (partial 포함 0.682) | **0** |
| Chronic rhinosinusitis | 20 | 0 | 2 | 3 | 15 | 0.000 | 0.100 (0.250) | 0 |
| Acute laryngitis | 15 | 1 | 1 | 0 | 13 | 0.400 | 0.133 | 0 |
| Viral pharyngitis | 17 | 3 | 0 | 3 | 11 | 0.500 | 0.176 (0.353) | 25 |
| Stable angina | 20 | 1 | 6 | 8 | 5 | 0.250 | 0.350 (0.750) | 17 |
| Unstable angina | 24 | 2 | 0 | 10 | 12 | 0.143 | 0.083 (0.500) | 11 |
| HIV (initial) | 29 | 8 | 0 | 0 | 21 | 0.400 | 0.276 | 0 |
| Scombroid | 17 | 2 | 0 | 5 | 10 | 0.091 | 0.118 (0.412) | 0 |
| COPD exacerbation | 13 | 2 | 2 | 4 | 5 | 0.500 | 0.308 (0.615) | 0 |
| PSVT | 17 | 4 | 0 | 2 | 11 | 0.571 | 0.235 (0.353) | 0 |
- 기존 공개 KG(Step 13B strict)는 10질환 중 **3개**(Viral pharyngitis·Stable/Unstable angina)만 알았고 나머지 7개는 관계 0 → 프로필은 **10/10 질환에 지식 제공**(7개 신규).
- 그러나 DDXPlus evidence 수준 coverage는 낮다: direct+attribute 평균 0.21, partial 포함 0.43. 원인: (a) DDXPlus는 통증 부위·강도 값, 과거력, 노출 등 세부 질문이 많고 프로필은 그 세부를 다 담지 못함, (b) MedlinePlus 수준 자료의 증상 목록이 짧음, (c) 매칭이 CUI·이름 일치 기반이라 "Pain" ↔ "Chest pain" 같은 상위/하위는 partial로만 잡음.
- KG 대비: KG가 아는 3질환에선 KG(83 finding 기준 11~25 관계)가 evidence 수로는 더 많이 덮지만, 프로필은 value-level(시간·유발·완화·기간)을 추가로 제공.

## 4. 질환쌍 판별 (`06`, 프로필 fact만 사용)
- **Acute vs Chronic rhinosinusitis**: 기간 ≤4주 vs >12주, 급성은 "감기 후 7~10일 악화"·"10일 초과 지속"·"호전 후 악화" 시간 fact; 만성은 "증상 동일하나 더 경미·12주 초과"+객관적 염증 확인+비용종 확인. → **기간·진행 속성으로 원리적 구별 가능** (DDXPlus엔 기간 질문이 없어 evidence 수준에선 여전히 불가).
- **Stable vs Unstable angina**: 안정=운동·스트레스 유발, 1~15분, 휴식·NTG로 완화, 패턴 불변, 오전 호발 / 불안정=휴식 시 발생, >15~20분, NTG 무반응, crescendo, 급성 발생, 혈압 저하·호흡곤란 동반. → **유발·기간·완화·진행 4축 모두 구별 가능**, DDXPlus의 E_14(휴식 시 흉통)·E_13(진행)이 attribute 수준으로 대응.
- **Acute laryngitis vs Viral pharyngitis**: 공통 발열·경부 림프절; 후두염 고유=쉰목소리·음성 남용·GERD·URI 동반; 인두염 고유=연하통·결막염·콧물·근육통, GAS 음성. 단 CDC는 쉰목소리를 "바이러스성 인두통의 징후"로도 들어 **쉰목소리 하나로는 분리 불가**, 연하통·결막염 조합이 필요.
- 새로 구별 가능해진 pair: 3/3 (프로필 수준). Step 14 기준 미해결이던 급/만성 부비동염·후두염/인두염이 시간·동반증상 속성으로 표현 가능해짐 — 단 DDXPlus 질문에 해당 속성(기간)이 없으면 실험에선 쓸 수 없음.

## 5. 검토 큐 (`08`): 85 fact (질환당 8.5) — 다중 출처 표현 차이, 급/만성 경계, 숫자 범위, 복수 CUI, 위험요인/원인 경계, 진단 기준 vs 흔한 특징 + 위 열 정렬 결함.

## 6. 49개 확장 추정 (`09`, 실측 기반)
질환당 출처 1.9, fact 15.0, 개념 연결 12.5, 검토 8.5. 파일 타임스탬프 기준 수집→freeze 0.2 h(질환당 ~1분)이지만 이는 **AI 보조 추출 시간**이고 검수 2분/fact 가정 시 질환당 0.28 h. 49개: fact ≈735, 검토 ≈416, 작성 ≈1 h + 검토 ≈14 h. 단 이 속도는 MedlinePlus급 자료 기준이며, 1순위 가이드라인 본문(StatPearls·학회)을 확보하려면 접근 차단 해결(수동 다운로드) 시간이 별도로 필요하고, 작성자-DDXPlus 분리 원칙상 사람이 작성·검수해야 실제 시간은 훨씬 커진다.

## 7. 판정 근거
- GO 요소: 10/10 source 확보·프로필 구축 성공, value-level fact 87개 실존, 기존 KG 0이던 7질환에 지식 생성, 상위 오답쌍 3개가 시간·유발·기간 속성으로 구별 가능, 검토량 감당 가능(85).
- 제한: 1순위 가이드라인 본문 확보 4/10(대부분 환자용 MedlinePlus), 질환당 출처 1.9(1개인 질환 3), DDXPlus evidence coverage 낮음(direct+attribute 0.21), 프로필 attribute 열 정렬 결함, 작성자 blind 미충족, 급/만성 판별 속성(기간)이 DDXPlus 질문에 없음.
→ **PARTIAL_GO**: 방식은 성립하고 KG 대비 실질적 value-level 정보를 주지만, 자료 등급·blind 작성·표 정합성을 고친 v2로 재검증 후 확장해야 한다.

## 8. Research Guardian 자체 점검(§21)
1 DDXPlus 파일 미참조(단 작성자 사전 지식 오염 고지) 2 freeze 후 수정 0(assert) 3 출처 없는 fact 0 4 임의 확률 0 5 출처-인용 대응: 각 fact에 인용 보유(전수 인간 검증은 review queue) 6 중복 fact: (disease,concept,relation) 중복 0 7 동일 출처 이중계산: 소스 수는 sid unique로 집계 8 저작권: 인용은 문장 단위 짧은 발췌, 원문 통째 저장 없음(raw는 로컬 보존만, 재배포 안 함) 9 10질환 포함 ✔ 10 Step 8~14 무수정 ✔
