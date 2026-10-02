# ============================================================================================
# ARCHIVE — 1회성 이력 보존본. 다시 실행하지 말 것(실행하면 정본을 덮어쓴다).
# - 2026-09-26 medmap/data/terminology_ko.json 최초 생성에 실제로 쓴 스크립트. 이 헤더 주석을 제외하면
#   원본(sha256 9f5c52f4d79fc9969e005f5430b3bfd8dc01e8f3be640c7b6263ff5130a3718d)과 byte 동일, 로직 무수정.
# - 이후 편집 위치는 정본 medmap/data/terminology_ko.json 하나뿐이다(파생 파일은 scripts/export_web_terminology.py).
# - 번역 문자열은 전부 작성자가 직접 입력한 리터럴이다. MRCONSO/UMLS(KCD5·MDRKOR) 문자열을 읽거나 복사하지 않는다.
#   기존 한국어는 336463f 시점 question_labels_ko.json(질문 53·value 188·답 라벨)과 initial_evidence_ko.json(label_ko 96)에서 복사.
# - 절대경로 주의: 아래 R = Path('~/medmap-worktrees/korean-terminology') 는 작성 당시 worktree 경로다(수정하지 않음).
# - 이 스크립트 출력은 모든 질환의 umls_kor_crosscheck=null 이다. 현재 boolean 값은 이후 scripts/crosscheck_umls_kor.py --write 가 기록했다.
# - 재현 확인(2026-09-26): 336463f 입력 사본으로 임시 경로에서 실행한 결과 == 현재 정본(crosscheck 를 null 로 되돌린 뒤) → True.
# ============================================================================================
"""One-time seed of medmap/data/terminology_ko.json (canonical). After this, canonical is hand-edited."""
import json, pickle, sys
from pathlib import Path
R = Path('~/medmap-worktrees/korean-terminology')
ev = json.loads((R/'data/ddxplus/en/release_evidences.json').read_text())
ql = json.loads((R/'medmap/data/question_labels_ko.json').read_text())
ini = {i['evidence_id']: i['label_ko'] for i in json.loads((R/'medmap/data/initial_evidence_ko.json').read_text())['items']}
classes = [str(c) for c in pickle.load(open(R/'exp/step16b_next_information_validation/model_k3.pkl','rb')).classes_]

OK = lambda t: {"label_ko": t, "status": "ok", "source": "standard_term"}
def RV(draft, reason): return {"draft_ko": draft, "status": "review_needed", "source": "standard_term", "review_reason": reason}
D = {
 "Acute COPD exacerbation / infection": RV("만성 폐쇄성 폐질환 급성 악화/감염", "복합 class(악화 또는 감염을 한 class로 묶음) — 한국어 표시 범위를 사용자가 정해야 함"),
 "Acute dystonic reactions": OK("급성 근육긴장이상 반응"),
 "Acute laryngitis": OK("급성 후두염"),
 "Acute otitis media": OK("급성 중이염"),
 "Acute pulmonary edema": OK("급성 폐부종"),
 "Acute rhinosinusitis": OK("급성 비부비동염"),
 "Allergic sinusitis": RV("알레르기성 부비동염", "DDXPlus 명칭(sinusitis)과 한국 임상 용어(알레르기 비염/부비동염) 범위가 달라 한 용어로 정할 수 없음"),
 "Anaphylaxis": OK("아나필락시스"),
 "Anemia": OK("빈혈"),
 "Atrial fibrillation": OK("심방세동"),
 "Boerhaave": RV("부르하버 증후군(특발성 식도 파열)", "고유명 표기 변이(부르하버/보어하브/부르하베) — 표준 표기 결정 필요"),
 "Bronchiectasis": OK("기관지확장증"),
 "Bronchiolitis": OK("세기관지염"),
 "Bronchitis": OK("기관지염"),
 "Bronchospasm / acute asthma exacerbation": RV("기관지 연축/천식 급성 악화", "복합 class(기관지 연축 또는 천식 급성 악화) — 표시 범위 결정 필요"),
 "Chagas": OK("샤가스병"),
 "Chronic rhinosinusitis": OK("만성 비부비동염"),
 "Cluster headache": OK("군발 두통"),
 "Croup": OK("크루프"),
 "Ebola": OK("에볼라바이러스병"),
 "Epiglottitis": OK("후두개염"),
 "GERD": OK("위식도 역류질환"),
 "Guillain-Barré syndrome": OK("길랭-바레 증후군"),
 "HIV (initial infection)": OK("HIV 초기 감염"),
 "Influenza": OK("인플루엔자"),
 "Inguinal hernia": OK("서혜부 탈장"),
 "Larygospasm": OK("후두 연축"),
 "Localized edema": OK("국소 부종"),
 "Myasthenia gravis": OK("중증 근무력증"),
 "Myocarditis": OK("심근염"),
 "PSVT": OK("발작성 심실상성 빈맥"),
 "Pancreatic neoplasm": RV("췌장 신생물(종양)", "neoplasm 의 양성/악성 범위 불명 — '췌장암'으로 쓰면 의미 확대, '신생물'은 환자에게 생소"),
 "Panic attack": OK("공황 발작"),
 "Pericarditis": OK("심낭염"),
 "Pneumonia": OK("폐렴"),
 "Possible NSTEMI / STEMI": RV("급성 심근경색 가능성(NSTEMI/STEMI)", "불확실 표현(Possible) + 복합 class — 표시 문구 결정 필요"),
 "Pulmonary embolism": OK("폐색전증"),
 "Pulmonary neoplasm": RV("폐 신생물(종양)", "neoplasm 의 양성/악성 범위 불명 — '폐암'으로 쓰면 의미 확대"),
 "SLE": OK("전신 홍반성 루푸스"),
 "Sarcoidosis": OK("사르코이드증"),
 "Scombroid food poisoning": OK("스콤브로이드 식중독"),
 "Spontaneous pneumothorax": OK("자연 기흉"),
 "Spontaneous rib fracture": OK("자발성 갈비뼈 골절"),
 "Stable angina": OK("안정형 협심증"),
 "Tuberculosis": OK("결핵"),
 "URTI": OK("상기도 감염"),
 "Unstable angina": OK("불안정형 협심증"),
 "Viral pharyngitis": OK("바이러스 인두염"),
 "Whooping cough": OK("백일해"),
}
NOTES = {"Larygospasm": "모델 class 원문 오탈자(Laryngospasm). key 는 원문 유지", "URTI": "약어 풀어 씀(upper respiratory tract infection)",
         "GERD": "약어 풀어 씀", "PSVT": "약어 풀어 씀", "SLE": "약어 풀어 씀", "Boerhaave": None}
assert set(D) == set(classes), set(classes) ^ set(D)
diseases = {}
for c in classes:
    e = dict(D[c]); e["umls_kor_crosscheck"] = None
    if NOTES.get(c): e["note"] = NOTES[c]
    diseases[c] = e

S = {
 "E_0": "최근 바이러스 감염", "E_1": "귀 감염 항생제 복용", "E_2": "HIV 감염", "E_3": "심낭염 과거력", "E_4": "크루프 병력(본인·가족)",
 "E_5": "폐에 물이 찬 적 있음", "E_6": "만성 췌장염", "E_7": "부실한 식사", "E_8": "투석 중",
 "E_10": "소염진통제 복용", "E_11": "9개월 넘는 모유 수유", "E_12": "심한 음식 알레르기",
 "E_15": "최근 7일 내 항정신병약 복용", "E_16": "불안감", "E_17": "아시아계 혈통", "E_18": "낭포성 섬유증",
 "E_19": "갑상선 기능 항진증", "E_20": "류마티스 관절염", "E_21": "자연 기흉 과거력", "E_22": "심장 판막 질환",
 "E_24": "빈혈 진단 과거력", "E_25": "가족의 군발 두통", "E_26": "가족의 빈혈", "E_27": "성매개 감염 과거력",
 "E_28": "가족의 중증 근무력증", "E_29": "직계 가족의 정신 질환", "E_31": "중증 만성 폐쇄성 폐질환",
 "E_34": "치료 중인 암", "E_35": "커피·차 규칙적 섭취", "E_37": "전이암", "E_40": "백일해 환자 접촉",
 "E_41": "비슷한 증상자 접촉(2주 내)", "E_44": "스테로이드제 복용", "E_46": "지난 1년 천식 발작 2회 이상",
 "E_47": "크론병·궤양성 대장염", "E_48": "4명 이상과 함께 거주", "E_49": "어린이집 출입·근무",
 "E_54": "통증 양상", "E_55": "통증 부위", "E_56": "통증 강도", "E_57": "통증이 퍼지는 부위",
 "E_58": "통증 위치의 분명함", "E_59": "통증이 생긴 속도", "E_60": "에너지 음료 규칙적 섭취",
 "E_61": "정맥 주사 약물 사용", "E_62": "각성제 규칙적 복용", "E_69": "당뇨병", "E_70": "과체중",
 "E_71": "고콜레스테롤 또는 치료약 복용", "E_72": "지난 1년 만성 폐쇄성 폐질환 악화",
 "E_73": "에볼라 감염자 접촉(1개월 내)", "E_78": "과음·알코올 의존", "E_79": "흡연", "E_80": "우울증 진단 과거력",
 "E_81": "만성 불안", "E_86": "가족의 알레르기·꽃가루병·습진", "E_87": "가족의 천식", "E_95": "파킨슨병",
 "E_98": "열공 탈장", "E_99": "편두통 병력(본인·가족)", "E_100": "호르몬제 복용", "E_101": "지난 1년 천식으로 입원",
 "E_102": "고혈압 때문에 진료", "E_104": "고혈압 또는 혈압약 복용", "E_105": "심근경색 과거력 또는 협심증",
 "E_106": "심부전", "E_107": "뇌졸중 과거력", "E_108": "혈액 순환 문제", "E_109": "심부정맥 혈전증 과거력",
 "E_110": "3일 넘게 거동 못함(4주 내)", "E_113": "만성 신부전", "E_115": "여러 상대와 무방비 성관계(6개월 내)",
 "E_116": "2주 내 감기", "E_118": "폐렴 과거력", "E_119": "만성 부비동염 진단", "E_120": "코 물혹(폴립)",
 "E_121": "비중격 만곡", "E_123": "만성 폐쇄성 폐질환", "E_124": "천식 또는 기관지확장제 사용 과거력",
 "E_125": "위식도 역류 진단 과거력", "E_126": "간경변", "E_130": "발진 색깔", "E_131": "병변 껍질 벗겨짐",
 "E_132": "발진 부기 정도", "E_133": "발진 부위", "E_134": "발진 통증 강도", "E_135": "병변 크기 1cm 초과",
 "E_136": "가려움 정도", "E_137": "림프절 제거 수술 과거력", "E_138": "섬유근육통",
 "E_141": "12세 전 초경", "E_142": "어머니의 천식", "E_143": "주 4회 이상 규칙적 운동",
 "E_146": "신규 경구 항응고제 복용", "E_149": "칼슘 통로 차단제 복용", "E_152": "부종 부위",
 "E_153": "골다공증 치료 중", "E_158": "내분비·호르몬 질환 진단", "E_160": "조산 또는 출생 시 합병증",
 "E_165": "가족의 기흉", "E_167": "임신(가능성 포함)", "E_183": "농촌 거주", "E_184": "혈관 확장제 복용",
 "E_185": "머리 외상 과거력", "E_186": "폐쇄성 수면 무호흡 진단", "E_187": "붉은살 생선·스위스 치즈 섭취",
 "E_189": "HIV 양성 상대와 성관계(12개월 내)", "E_191": "과거 흡연", "E_195": "교외 거주", "E_196": "1개월 내 수술",
 "E_197": "단백질이 빠지는 신장 질환", "E_198": "농업 종사", "E_199": "건설업 종사", "E_200": "광업 종사",
 "E_204": "4주 내 해외여행", "E_207": "대도시 거주", "E_208": "저체중(BMI 18.5 미만)", "E_209": "예방접종 완료",
 "E_213": "최근 코막힘약·각성 성분 복용", "E_222": "매일 간접흡연", "E_223": "가족의 췌장암", "E_224": "가족의 폐암",
 "E_225": "50세 전 심혈관 질환 가족력", "E_226": "알레르기 체질", "E_227": "면역 저하",
}
SRV = {
 "E_139": ("심장 결손", "원문 'known heart defect' 가 선천성 기형만인지 후천 구조 이상까지인지 불명 — 짧은 표시명 범위 결정 필요"),
 "E_147": ("최근 병원에서 구역·흥분 등으로 주사 투약", "복합 조건(구역·초조·중독·공격행동 치료 + 정맥/근육 주사) — 축약 시 의미 손실 여부 검토 필요"),
}
short = {}
for e in sorted(ev, key=lambda x: int(x[2:])):
    if e in ini:
        short[e] = {"label_ko": ini[e], "status": "ok", "source": "initial_evidence_ko_user_reviewed"}
    elif e in SRV:
        d, r = SRV[e]; short[e] = {"draft_ko": d, "status": "review_needed", "source": "question_en_derived", "review_reason": r}
    else:
        src = "question_labels_ko_derived" if e in ql["questions"] else "question_en_derived"
        short[e] = {"label_ko": S.pop(e), "status": "ok", "source": src}
assert not S, S
questions = {e: {"text_ko": t, "status": "ok", "source": "question_labels_ko_v1"} for e, t in ql["questions"].items()}
values = {c: {"label_ko": t, "status": "ok", "source": "question_labels_ko_v1"} for c, t in ql["values"].items()}
V = {"V_0": "북아프리카", "V_1": "서아프리카", "V_2": "남아프리카", "V_3": "중앙아메리카", "V_4": "북아메리카",
     "V_5": "남아메리카", "V_6": "아시아", "V_7": "동남아시아", "V_8": "카리브해", "V_9": "유럽", "V_13": "오세아니아"}
for c, t in V.items():
    assert c not in values
    values[c] = {"label_ko": t, "status": "ok", "source": "question_en_derived"}
doc = {
 "schema": "medmap.terminology_ko/1",
 "version": "1.0.0",
 "note": "한국어 표시 용어 단일 정본(presentation only). key = 내부 ID(모델 질환 class·E_*·V_*) 그대로. status ok 만 label_ko/text_ko, review_needed 는 draft_ko 만(화면 미사용). 런타임 번역·LLM 없음. question_labels_ko.json·initial_evidence_ko.json 의 용어 필드와 medmap-web/src/generated/terminology_ko.json 은 scripts/export_web_terminology.py 가 여기서 생성한다(직접 편집 금지). umls_kor_crosscheck 는 로컬 UMLS KCD5/MDRKOR 대조 결과 boolean 만(문자열 비저장, scripts/crosscheck_umls_kor.py).",
 "answer_labels": {"unknown_choice_label": ql["unknown_choice_label"], "yes_label": ql["yes_label"], "no_label": ql["no_label"]},
 "diseases": diseases, "evidence_short": short, "evidence_questions": questions, "values": values,
}
(R/'medmap/data/terminology_ko.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
print(len(diseases), len(short), len(questions), len(values))
