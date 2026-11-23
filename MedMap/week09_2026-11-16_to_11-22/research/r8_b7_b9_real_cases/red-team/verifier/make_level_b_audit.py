#!/usr/bin/env python3
"""LEVEL B(지침 원문 정합성)·사례 사실·REF-R 반대 검토 결과를 csv 로 기록(검증자 작성).
원문 위치는 source-audit/raw_sources/va/*.txt 의 줄 번호(grep 확인), PPC = source-audit/raw_sources/ppc/s002.txt 줄 번호.
판정 코드: OK / TYPE_C(지침 해석 문제 후보) / ENC(인코딩 누락·불일치) / FACT(사례 사실 근거 문제)
REF 의견: 타당 / 논쟁가능-과도보류 / 논쟁가능-성급확정 / 논쟁가능-원인집합 — 모두 '전문가 검토 필요'(검증자는 임상 전문가 아님)
"""
import csv, json, os
ROOT = os.path.expanduser('~/medmap-original-b7-b9-clinical-validation')
inp = json.load(open(os.path.join(ROOT, 'experiments/inputs/cases_input_v1.json')))['cases']
ref = json.load(open(os.path.join(ROOT, 'evaluation/REF_R_v1.json')))['cases']

DM = 'VADOD-Diabetes-CPG_Final_508.txt'; CKD = 'CKD-CPG_2025-Guideline_final_20250509.txt'
HTN = 'HTN-CPG_2026-Guideline_final_20261027.txt'; OA = 'Osteoarthritis-CPG_2026-Guideline_final_20260618.txt'
SGLT_EGFR = (f'{DM} L4707 표 금기/주의 "eGFR <20–30 (see labeling)", L2962-2964 "safety if eGFR is at least 20"; '
             f'{CKD} L2923 "lowest eGFR for initiation of SGLT2i was 20"')
NSAID_SOFT = (f'{OA} L954 Sidebar1 "should generally be avoided in patients with or at risk for CVD, CKD"; '
              f'L7364 부록 I "Use with caution or avoid use of NSAIDs in ... renal impairment ... known CVD, patients receiving anticoagulants"')
CKD14_TXT = f'{CKD} L2751-2754 Rec14 "continuing therapy, unless there is drug intolerance or adverse event"; L7311 모듈 동일 문구'
HTN4_TXT = (f'{HTN} L1644-1646 Rec4 "<130 ... depending on patient characteristics and preferences"; '
            f'L1693-1695 "frailty ... orthostatic hypotension, and octogenarians/nonagenarians were excluded from clinical trials"')
DM25_TXT = f'{DM} L3147-3150 Rec25 "especially those 65 years and older ... if glycemic control can be achieved with other treatments"'

A = {}  # (case,item) -> (source, verdict, finding, fact, ref_opinion, impact)
def s(c, i, src, verdict, finding, fact, op, impact):
    A[(c, i)] = (src, verdict, finding, fact, op, impact)

s('CASE_01','I1', f'{DM} L2806 Rec21, L2885 Rec22; {CKD} L2862 Rec15', 'OK',
  'applies/contra 원문과 정합. eGFR 하한 미인코딩이나 CKD 3기라 영향 없음. CKD15 는 "ACEi/ARB 에 추가" 형식인데 환자 ACEi/ARB 미복용(DM21/22 로 독립 근거 있음)',
  'PPC L9: CKD Stage 3, CHF, DM2, 70+ 확인. SGLT2i 미복용(12/12 약 나열) 확인', '타당', '없음')
s('CASE_01','I2', DM25_TXT, 'TYPE_C',
  'applies 에 age_ge65 를 필수 조건으로 넣음(원문은 "especially", 필수 아님 → 조건 좁힘). "우선 선택"을 "기존 약 교체"로 확장한 해석',
  'nateglinide 복용·70+ 확인(PPC L9)', '타당(보류)', '없음(age_ge65=true)')
s('CASE_01','I3', f'{DM} L1867 Rec9, L1977 Rec10', 'TYPE_C',
  '원문은 개인화 목표만 제시. "강화=자가혈당 측정 증가 동반"은 인코더 가정(측정 부담 없는 강화 약도 있음) — 선호 충돌을 행동 정의로 만든 구조',
  '선호 "Not willing to check blood sugar more often" 원문 확인(PPC L9)', '타당(보류), 단 행동 정의 논쟁가능', '없음(현 인코딩 하)')
s('CASE_01','I4', f'{CKD} L3167 Rec19(투석 전 CKD 스타틴 "initiation")', 'TYPE_C',
  'Rec19 는 "시작" 권고 — "유지" 로 확장. 투석 여부 미인코딩(CKD3 이라 영향 없음). 경미',
  'pravachol 복용 확인', '타당', '없음')
s('CASE_01','I5', f'{CKD} L2608 Rec12', 'OK', 'HTN+UACR>30 → ACEi/ARB 정합', 'ACEi/ARB 미복용 확인(약 12/12 나열)', '타당', '없음')

s('CASE_02','I1', f'{CKD} L2321-2323 Rec9 "depending on patient values and preferences"', 'OK',
  'egfr_lt30 은 원문에 없는 대리 조건(신부전 접근)이나 합리적. 선호 충돌 → SDM 은 원문 문구와 정합',
  'PPC L23: Stage 4 CKD, 90+, ADL 도움, "Doesn\'t wish to see more specialists" 확인. high_comorb_low_func=true 는 추론(근거 있음). 이미 신장내과 진료 중인지 원문 없음 → "more specialists" 해당 여부 확인 필요',
  '논쟁가능-성급확정(이미 신장내과 진료 중이면 충돌 아님)', '가능')
s('CASE_02','I2', f'{CKD} L2318 Rec8', 'OK', '조건 없는 SDM 권고 — 정합', 'CKD 4기 확인', '타당', '없음')
s('CASE_02','I3', CKD14_TXT, 'TYPE_C',
  '"unless intolerance" 를 확인해야 닫히는 조건(acei_intol 미확인→보류)으로 처리. 원문 문형은 기본 지속 + 예외(반증) 조건으로도 읽힘 — 두 해석 모두 가능. 칼륨 미확인만으로 보류는 과도할 수 있음',
  'lisinopril 복용 확인. 검사값 없음(원문)', '논쟁가능-과도보류(전문가 검토 필요)', '가능(HOLD→APPLY)')
s('CASE_02','I4', SGLT_EGFR, 'TYPE_C',
  'CKD 4기(eGFR 15–29)인데 VA 표의 eGFR 하한(20–30, 라벨 참조)·근거 하한 20 을 인코딩하지 않음 → "eGFR≥20?" 확인 질문이 B 질문·REF required 모두에서 빠짐. 인슐린 병용 시 DKA 주의(CKD L2915-2916)도 미반영',
  'insulin 복용 확인', '타당(보류), 단 원인 변수 누락', '라벨 없음/질문 집합 영향')
s('CASE_02','I5', DM25_TXT, 'TYPE_C', 'age_ge65 필수화(원문 "especially"). 기존 insulin "교체"로 확장. eGFR<30 이라 대체약 제한', '90+ 확인', '타당(보류)', '없음')

s('CASE_03','I1', HTN4_TXT + f'; {CKD} L2550 Rec11', 'TYPE_C',
  'orthostatic 을 절대 금기(contra)로 둠 — 원문은 "임상시험 제외군"(근거 적용범위) + "환자 특성·선호에 따라". 80+ (octogenarian) 근거 범위(K) 미인코딩',
  'PPC L10: 80+, "Would like to decrease blood pressure medications", 아침 어지럼 확인', '논쟁가능-원인집합(P 외 K 가능)', '원인 집합')
s('CASE_03','I3', NSAID_SOFT, 'TYPE_C',
  '"generally be avoided"(상대적 회피)·부록 "use with caution or avoid" 를 확정 금기(NOT_APPLY)로 처리 — 원문보다 강한 해석. 단 CKD3+CVA+clopidogrel+80+ 로 결론 자체는 방어 가능',
  'CVA(cvd=true)·CKD 3기 확인(PPC L10)', '논쟁가능-성급확정(전문가 검토 필요)', '가능(NOT_APPLY→HOLD/SDM)')
s('CASE_03','I4', f'{CKD} L3167 Rec19', 'TYPE_C',
  'Rec19 원문에 없는 statin_intol 금기를 인코더가 추가(합리적이나 CKD14 의 원문 예외조항 처리와 비대칭)',
  'on_statin=false: 약 10/10 나열에 스타틴 없음 확인', '타당(보류)', '없음')

s('CASE_04','I1', f'{OA} L956 "NSAIDs ... should be avoided in patients with eGFR <30"', 'OK',
  '"generally" 없는 회피 문구 → 금기 처리 정합. applies="True"(관절염 유형 무관)는 I3 와 비일관이나 결과 영향 없음',
  'CKD 4기 확인. 환자 선호 "Limit use of NSAIDs"(PPC L16) 미인코딩', '타당', '없음')
s('CASE_04','I2', f'{OA} L1142 Rec11; L956; {CKD} L7375 "Avoid NSAID use, including OTC and prescription (oral/topical), if possible"', 'TYPE_C',
  'K 변수(국소 NSAID 가 eGFR<30 회피에 포함되는지)는 같은 VA 묶음의 CKD CPG 원문이 "oral/topical 포함 가능하면 회피"로 답함 → 코퍼스 안에서 닫히는 질문을 K(지식 공백)로 만든 것. 선호 "Limit use of NSAIDs" 미인코딩',
  'knee_oa 미확인(관절염 유형 미기재) 확인', '논쟁가능-과도보류(NOT_APPLY 가능, 전문가 검토 필요)', '가능(HOLD[P,K]→NOT_APPLY)')
s('CASE_04','I3', f'{OA} L1148 Rec12', 'OK', '정합', '관절염 유형 미기재 확인', '타당(보류)', '없음')
s('CASE_04','I4', SGLT_EGFR, 'TYPE_C', 'CKD 4기인데 eGFR 하한 미인코딩(CASE_02 I4 와 동일). 당뇨 유형 미기재 → dm_type2 변수 타당', '"DM"(유형 없음) 확인', '타당(보류), 원인 변수 누락', '질문 집합 영향')
s('CASE_04','I5', CKD14_TXT, 'TYPE_C', 'CASE_02 I3 와 동일 쟁점', 'lisinopril 복용 확인', '논쟁가능-과도보류(전문가 검토 필요)', '가능(HOLD→APPLY)')
s('CASE_04','I6', HTN4_TXT, 'ENC', 'contra=False — CASE_03/06/07 의 같은 행동은 orthostatic 금기를 둠(인코딩 비일관). 80+ 근거 범위 미인코딩', '선호 "Increase in blood pressure medications" 확인(PPC L16)', '타당(보류)', '없음')

s('CASE_05','I1', f'{CKD} L3167 Rec19', 'TYPE_C', '"시작" 권고를 "감량 용법 유지"로 확장(경미)', 'PPC L18: simvastatin 주3회 감량·근육통 감소 확인(사실상 스타틴 불내성 정보)', '타당', '없음')
s('CASE_05','I2', f'{DM} L3075 Rec24', 'OK', '정합(ckd=true 로 충족, cvd 값 무관)', 'CKD 2기 확인', '타당(보류)', '없음')
s('CASE_05','I3', f'{DM} L2885; {CKD} L2862', 'OK', '정합(CKD2, eGFR 하한 무관)', '확인', '타당(보류)', '없음')
s('CASE_05','I4', f'{CKD} L7307 "Metformin can be used if eGFR >30"', 'OK', '정합', 'metformin 복용·CKD2 확인', '타당', '없음')
s('CASE_05','I5', NSAID_SOFT, 'TYPE_C',
  '상대적 회피를 확정 금기로 처리(CASE_03 I3 와 동일). cvd=true 근거가 대동맥판 협착 — NSAID 위험 맥락의 "CVD"에 해당하는지 논쟁가능하나 ckd=true 와 "at risk for CVD"(70+, DM, HTN, HLD)로 결론은 불변',
  'aortic stenosis·CKD 2기 확인(PPC L18). cvd 분류는 논쟁가능', '논쟁가능-성급확정(전문가 검토 필요)', '가능')

s('CASE_06','I1', '해당 VA AF 지침 없음(NO_STRUCTURABLE_AF_GUIDELINE)', 'OK', '근거 공백(K)+출혈 감수 선호(Q) 처리 타당', '원문 Table 2 의료진 인용·"not sure how many 90-year-olds" 확인(CASE_06.json)', '타당', '없음')
s('CASE_06','I2', NSAID_SOFT, 'TYPE_C',
  'cvd=true 근거가 심방세동 — "CVD" 해당 논쟁가능. 다만 부록 I 의 "patients receiving anticoagulants"(warfarin)·과거 Celebrex 어지럼으로 결론은 견고. 상대적 회피의 확정 금기화는 동일 쟁점',
  'PPC L6: AF, warfarin, "Fearful of trying new medications ... Celebrex made me dizzy" 확인', '타당(결론), 근거 경로 논쟁가능', '없음')
s('CASE_06','I3', f'{OA} L951-952 "maximum of 4 g/day should never be exceeded"; L7341 부록 "Consider lower total daily doses (e.g., 2–3 g) in elderly"', 'TYPE_C',
  '"4 g 상한 안내"는 원문 정합이나 같은 지침이 고령자에서 2–3 g 를 제시 — 90+ 환자에 4 g 기준 안내는 원문 일부만 반영(경미)', '"Tylenol helps ... not sure how much I can take" 확인', '타당', '없음')
s('CASE_06','I4', HTN4_TXT, 'ENC',
  '90+ (nonagenarian)는 원문상 시험 제외군 → 근거 범위(K) 미인코딩. 같은 사례 I1 은 90세 근거 공백을 K 로 처리 — 비일관. HTN4 "선호에 따라"인데 선호 변수 없음(낙상 공포 기록 있음)',
  '90+, 균형·낙상 공포 확인', '논쟁가능-원인집합(HOLD[P]→HOLD[P,K])', '원인 집합')

s('CASE_07','I1', f'{DM} L1867/L1977 Rec9-10; {CKD} L7298-7306', 'FACT',
  '"혈당강하 치료 강도 낮춤" 적용의 전제 on_glucose_lowering=true 가 원문으로 뒷받침되지 않음',
  'PMC10359101 Table 2(약국 16종·집 28종 전체 약물 대조표)에 혈당강하제 행이 없음, 본문 "non-insulin dependent type 2 diabetes (HbA1c 5.2%)" — 무약물 조절 가능성. CASE_07.json 도 "혈당강하제 이름 확인 필요"로 기록. 근거 없는 known 값', '논쟁가능-성급확정(사실 근거 부족)', '가능(APPLY→HOLD 또는 NOT_APPLY)')
s('CASE_07','I2', f'{DM} L2806; {CKD} L2862', 'ENC',
  '정합. 단 확인된 선호 q_fewer_meds(약 단순화 동의)가 어느 항목에도 연결되지 않음(새 약 추가와 잠재 충돌). 라벨은 보류로 불변',
  'Table 2 에 SGLT2i 없음 확인. "agreed ... to simplify her medications, including discarding expired or duplicate medications" — 일반적 "약 줄이기" 선호로 확장한 것도 해석', '타당(보류)', '없음')
s('CASE_07','I3', HTN4_TXT, 'FACT',
  'sbp_ge130=true 는 급성기 1회 169/60. 같은 원문 Table 2 는 irbesartan 중단 사유로 "blood pressure at goal with amlodipine and carvedilol" 기재 → 반대 증거 존재. 허약(CFS 6) 근거 범위(K) 미인코딩',
  '169/60·GCS 11 확인, "blood pressure at goal" 문구 확인(PMC10359101)', '논쟁가능(보류 유지 가능, NOT_APPLY 도 가능)', '가능')

s('CASE_08','I1', f'{CKD} L7384-7386 SADMANS', 'OK', '정합(후향적 시점)', '구토·설사 4일간 약 지속 확인', '타당', '없음')
s('CASE_08','I2', f'{DM} L4707-4710 "Increased risk for DKA"(주의); {CKD} L2917-2920 "holding SGLT2i during ... critical illness ... with reinitiation of SGLT2i treatment after an acute event has passed"', 'TYPE_C',
  'prior_edka 를 확정 금기로 둠 — VA 원문은 DKA 를 주의사항으로만 적고, 급성기 후 재개를 언급. 영구 금기는 사례 저자 Discussion 의 판단이지 VA 원문이 아님',
  'EDKA·MALA 병력, 실제 결정(SGLT2i 영구 중단) 확인', '논쟁가능-성급확정(HOLD[K] 가능, 전문가 검토 필요)', '가능(NOT_APPLY→HOLD)')
s('CASE_08','I3', f'{DM} L2987 Rec23', 'OK', 'SGLT2i 부적합 → GLP-1 RA 정합(I2 판단에 종속)', '실제 GLP-1 RA 전환 확인', '타당', '없음')
s('CASE_08','I4', f'{CKD} L7307 ">30"; {DM} L4643-4646 "do not initiate if eGFR <45"; {CKD} L7155 AKI 시 metformin 중단', 'TYPE_C',
  '재개(=재시작)에 CKD 모듈 >30 만 적용, DM 표의 "eGFR<45 에서 시작 금지" 미반영. egfr_gt30=true 는 기저 eGFR 48 기준이며 AKI 회복 후 eGFR 은 원문 미기재 → P 불확실성 누락. 이 항목이 B 대 D 차이의 유일한 원천',
  '기저 eGFR 48, 입원 Cr 801 µmol/L, 9일 후 "신기능 회복"(수치 없음) 확인', '논쟁가능-원인집합(HOLD[K]→HOLD[P,K])', '원인 집합(D 의 WC 해석에 직접 영향)')
s('CASE_08','I5', DM25_TXT, 'OK', '나이 조건 없이 인코딩 — 원문과 정합(단 CASE_01/02/10 과 비일관)', '58세 확인', '타당(보류)', '없음')

s('CASE_09','I1', f'{CKD} L2318 Rec8, L2321 Rec9', 'OK', '정합', 'CKD 3기·87세·기능 악화 확인', '타당', '없음')
s('CASE_09','I2', f'{DM} L2806 Rec21; {CKD} L7154 Box22 "Consider trial of holding ... SGLT2i"', 'ENC',
  '다른 모든 SGLT2i 항목과 달리 sglt2_contra(현재 사용·금기) 변수를 넣지 않음. 원문에 약물 목록 자체가 없음(CASE_09.json info_not_in_source) → P 미확인이 실재. 동시 AKI 에서 Box22 는 SGLT2i 보류를 고려하라 함. REF acceptable_confirm 에는 sglt2_contra 가 있으나 입력 변수에는 없음(불일치). 이 누락이 B 대 C 차이의 유일한 원천',
  'HFrEF EF 20–25%, 약물 목록 없음 확인', '논쟁가능-원인집합(HOLD[Q]→HOLD[P,Q])', '원인 집합(C 의 WC 해석에 직접 영향)')
s('CASE_09','I3', f'{CKD} L7135-7156 Box16-22(Box22 는 체액·폐색·사구체 질환 배제 후 도달)', 'TYPE_C',
  'Box22 선행 조건(Box16 체액 상태 등) 생략. HF 악화·양측 흉수로 체액 과다 가능성 — 이뇨제 보류 확정은 알고리즘상 성급할 수 있음',
  '신기능 악화로 이뇨제 중단(실제) 확인', '논쟁가능-성급확정(전문가 검토 필요)', '가능')

s('CASE_10','I1', DM25_TXT, 'ENC',
  'applies 에 "다른 치료로 조절 가능(alt_glycemic_ok)" 조건 없음 — CASE_01/02/08 의 DM25 항목과 비일관. 저혈당 경향으로 결론은 강함',
  '82세·장시간형 SU·저혈당 경향·실제 중단 확인', '논쟁가능(경미)', '가능(경미)')
s('CASE_10','I2', f'{DM} L4643-4645 "may continue at reduced dose"; {CKD} L7384 SADMANS', 'OK', '정합(감량 뉘앙스는 행동명에 없음)', 'eGFR 43·섭취 저하·실제 감량 확인', '타당(보류)', '없음')
s('CASE_10','I3', f'{DM} L4643 "Contraindicated eGFR <30"', 'OK', '정합', 'eGFR 18 확인', '타당', '없음')
s('CASE_10','I4', SGLT_EGFR, 'TYPE_C',
  '시점 미지정 + eGFR 하한 미인코딩. 시점 2(eGFR 18)이면 근거 하한 20 미만. 시점 1(eGFR 43)이면 현 REF 와 동일. 원문 "stage 2" vs eGFR 43 내부 불일치(ckd=true 는 어느 쪽이든 성립)',
  'eGFR 43→18 확인', '논쟁가능(시점 모호)', '시점에 따라 가능')

for i in ['I1','I2','I3','I4']:
    s('CASE_12', i, 'MGCDS Case 2 저자 기대안(가상)', 'OK',
      '저자 기대안을 그대로 인코딩·REF 로 사용 → 정의상 일치(독립 검증 아님). I2 는 aspirin 복용 환자에 "warfarin 대신 DOAC" 문구, eGFR 35 DOAC 용량 조건 미기재(정보 공백)', 'CASE_12.json 확인(가상 사례)', '타당(저자 기대안 기준)', '없음')
for i in ['I1','I2']:
    s('CASE_13', i, 'MGCDS Case 1 저자 대안(가상)', 'OK', '저자 대안 공통 요소', 'CASE_13.json 확인', '타당', '없음')
s('CASE_13','I3', 'MGCDS Case 1 저자 대안 3개 중 Option 1', 'TYPE_C',
  '저자는 선택지 3개를 제시. CASE_13.json 자체가 "환자 선호 없음 → Option 선택 불가, 무엇을 먼저 물을지가 질문"이라 기록 — 그런데 REF 는 APPLY 확정, 입력에 선호 변수 없음',
  '선호 없음 확인', '논쟁가능-성급확정(HOLD[Q] 가능)', '가능(APPLY→HOLD)')

rows = []
for c, case in inp.items():
    for i, it in case['items'].items():
        src, ver, fnd, fact, op, imp = A[(c, i)]
        rows.append({'case_id': c, 'item': i, 'case_type': case['case_type'], 'action': it['action'], 'rules': '|'.join(it['rules']),
                     'enc_applies': it['applies'], 'enc_contra': it['contra'], 'enc_prefs': json.dumps(it['prefs'], ensure_ascii=False),
                     'source_text_location': src, 'level_b_verdict': ver, 'finding': fnd, 'case_fact_check': fact,
                     'ref_label': ref[c]['items'][i][0] + ('[' + '+'.join(ref[c]['items'][i][1]) + ']' if ref[c]['items'][i][1] else ''),
                     'ref_opinion': op, 'possible_label_impact': imp,
                     'expert_review_needed': 'Y' if ver != 'OK' or '논쟁' in op else 'N'})
assert len(rows) == 50
with open(os.path.join(ROOT, 'red-team/verifier/level_b_audit.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
from collections import Counter
print(Counter(r['level_b_verdict'] for r in rows), Counter(r['expert_review_needed'] for r in rows))
print(sum(1 for r in rows if r['possible_label_impact'].startswith('가능')))
