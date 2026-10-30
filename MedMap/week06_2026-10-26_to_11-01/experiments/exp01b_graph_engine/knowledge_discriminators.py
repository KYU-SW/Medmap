"""4질환 판별 근거(38회차). 로컬 출처만: DisMech 구조화 항목·설명(commit eaa5fe99) + DisMech references_cache 의 PubMed 초록/본문.
진료지침 원문(2025 ESC 심근·심낭염, 2026 AHA/ACC PE 전문, WHO TB)은 로컬에 없음 — 다운로드는 사전 승인 대상이라 이번에 쓰지 않음.
원문을 옮기지 않고 관계만 독자적으로 구조화한다(인용은 짧은 근거 대조용). 인용이 캐시 텍스트와 일치하지 않거나 인용이 없으면
evidence_class 로 구분하고, 반박·배제처럼 영향이 큰 관계는 인용 확인이 안 되면 그래프에 적용하지 않는다(status NOT_APPLIED).

관계 유형(relation_type)
  DIAGNOSTIC_CRITERION  : 문헌에 기준으로 명시된 조건(예: 4 중 2) — RULE 노드
  DIAGNOSTIC_SUPPORT    : 문헌이 진단을 '지지' 한다고만 한 조건 — RULE 노드
  SCREENING_CRITERION   : 평가(검사)를 시작할 대상 기준 — 진단이 아님
  DISCRIMINATING_FEATURE: 감별에 쓰이는 특징 소견(지지 관계, 필수 아님)
  CONFIRMATORY_TEST     : 확인 검사 결과
  EXCLUSION_RULE        : 배제 규칙(반박) — 인용 확인 시에만 적용
"""
from __future__ import annotations

from graph_engine import MedGraph, Status
from knowledge_real_kg import DISMECH_COMMIT, disease_node_id, verify_quote

DM = f"DisMech {DISMECH_COMMIT[:8]}"
PE, PERI, MYO, TB = (disease_node_id(x) for x in ("Pulmonary embolism", "Pericarditis", "Myocarditis", "Tuberculosis"))

# 출처 확인용 인용(짧게) — verify_quote 로 캐시 텍스트와 대조
Q_PERI_CRIT = ("PMID:38804758", "Diagnosis of pericarditis requires at least two of the following criteria: new or worsening "
               "pericardial effusion, characteristic pleuritic chest pain, pericardial friction rub, or electrocardiographic changes")
Q_PERI_RUB = ("PMID:38804758", "Pericardial friction rubs are highly specific but transient, and they have been reported in 18% to 84% "
              "of patients with acute pericarditis.")
Q_MYO_CMR = ("PMID:30545455", "While having both a positive T2-based marker and a T1-based marker will increase specificity for "
             "diagnosing acute myocardial inflammation, having only one (i.e., T2-based OR T1-based) marker may still support a diagnosis")
Q_TB_COUGH = ("PMID:29196066", "There was no evidence that 1, 3, or 4 weeks’ duration were better predictors than cough lasting ≥ 2 "
              "weeks to screen for pulmonary TB.")
Q_TB_HIV = ("PMID:29196066", "In people living with HIV (PLWHIV), screening for fever, night sweats, hemoptysis, and/or weight loss "
            "in addition to cough (any World Health Organization [WHO]-endorsed symptom) increases the diagnostic sensitivity for TB.")

# 새 개념 노드(HPO 용어 없음 → 정의·출처 있는 별도 노드)
CONCEPTS = {
    "CONCEPT:chest_pain_relieved_sitting_forward": ("FINDING", "앞으로 숙이면 완화되는 흉통",
        f"{DM} Pericarditis.yaml phenotypes['Pericarditic chest pain'].description: 'relieved by sitting forward'"),
    "CONCEPT:characteristic_pericarditic_chest_pain": ("FINDING", "특징적 심낭염 흉통(임상의 판정)",
        f"{DM} Pericarditis.yaml: 'Sharp retrosternal or left precordial pain, worse lying flat and on inspiration, relieved by "
        f"sitting forward' — 구성 특징 중 몇 개가 필요한지 출처에 없음 → DDXPlus 로 자동 판정하지 않음"),
    "CONCEPT:pericarditis_ecg_change": ("FINDING", "심낭염 심전도 변화(광범위 ST 상승 또는 PR 하강)",
        f"{DM} Pericarditis.yaml diagnosis 'widespread ST-segment elevation or PR-segment depression'"),
    "CONCEPT:cmr_t2_marker": ("FINDING", "심장 MRI T2 기반 부종 지표 양성", "PMID:30545455(Lake Louise 개정 권고)"),
    "CONCEPT:cmr_t1_marker": ("FINDING", "심장 MRI T1 기반 손상 지표 양성", "PMID:30545455(Lake Louise 개정 권고)"),
    "CONCEPT:cough_ge_2_weeks": ("FINDING", "2주 이상 기침", "PMID:29196066 CHEST 2018"),
    "CONCEPT:hiv_infection": ("HISTORY", "HIV 감염(환자 보고)", "PMID:29196066 CHEST 2018 'people living with HIV'"),
    "CONCEPT:mtb_detected": ("FINDING", "결핵균 검출(Xpert MTB/RIF 또는 배양 양성)",
        f"{DM} Tuberculosis.yaml diagnosis 'Sputum Culture ... gold standard' · PMID:29196066"),
    "CONCEPT:ctpa_filling_defect": ("FINDING", "CT 폐동맥조영 충만 결손", f"{DM} Pulmonary_Embolism.yaml diagnosis 'CTPA ... filling defects'"),
}


def _cls(q):
    """인용 확인 결과 → evidence_class (등급은 graph_engine.GRADE)."""
    if q is None:
        return "DISMECH_NO_REF", "NO_QUOTE"
    r = verify_quote({"reference": q[0], "snippet": q[1]})
    return ("LITERATURE_QUOTE_IN_TEXT" if r == "FOUND" else "DISMECH_PMID_QUOTE_UNVERIFIED"), r


def relations() -> list:
    """판별 관계 표(그래프 적용 여부 포함). 모든 행이 보고서 표로 나간다."""
    R = []

    def add(**kw):
        cls, q = _cls(kw.pop("quote", None))
        R.append({"evidence_class": cls, "quote_check": q, **kw})

    add(id="PERI-CRIT-2of4", disease=PERI, relation_type="DIAGNOSTIC_CRITERION", op="ATLEAST:2",
        leaves=["CONCEPT:characteristic_pericarditic_chest_pain", "HP:0034788", "CONCEPT:pericarditis_ecg_change", "HP:0001698"],
        condition="급성 심낭염 의심 환자(성인), 4 특징 중 2 이상. 단일 특징 필수 아님",
        source=f"{DM} Pericarditis.yaml diagnosis[0] + {Q_PERI_CRIT[0]}", quote=Q_PERI_CRIT,
        limitation="삼출은 '새로 생기거나 악화' 조건이나 HPO 노드는 '심낭 삼출' 일반", ddx="흉통 특징만 부분 관측, 마찰음·심전도·삼출은 검사/진찰 → 미검사",
        status="APPLIED")
    add(id="PERI-RUB-NEG-UNINFORMATIVE", disease=PERI, relation_type="DISCRIMINATING_FEATURE", leaves=["HP:0034788"],
        condition="마찰음 음성 1회는 정보 없음(일시적·자세 의존)", source=f"{DM} Pericarditis.yaml phenotypes['Pericardial friction rub'] + {Q_PERI_RUB[0]}",
        quote=Q_PERI_RUB, limitation="민감도 18–84%", ddx="진찰 소견 → 미검사", status="APPLIED")
    add(id="PERI-POSITIONAL", disease=PERI, relation_type="DISCRIMINATING_FEATURE", leaves=["CONCEPT:chest_pain_relieved_sitting_forward"],
        condition="흉통이 있을 때(흉통 복합 + E_33)", source=f"{DM} Pericarditis.yaml phenotypes['Pericarditic chest pain'].description",
        quote=None, limitation="AI 큐레이션 설명 문장, 직접 인용 근거 없음 — 등급 DISMECH_NO_REF", ddx="E_33 + E_53 + E_55 흉부", status="APPLIED")
    add(id="MYO-CMR-BOTH", disease=MYO, relation_type="DIAGNOSTIC_CRITERION", op="AND",
        leaves=["CONCEPT:cmr_t2_marker", "CONCEPT:cmr_t1_marker"], condition="급성 심근 염증 의심, 심장 MRI 시행",
        source=f"{DM} Myocarditis.yaml diagnosis['Cardiac Magnetic Resonance'] + {Q_MYO_CMR[0]}", quote=Q_MYO_CMR,
        limitation="특이도 증가(확정 아님), 조직 확진은 심내막 생검", ddx="검사 → 미검사", status="APPLIED")
    add(id="MYO-CMR-ANY", disease=MYO, relation_type="DIAGNOSTIC_SUPPORT", op="OR",
        leaves=["CONCEPT:cmr_t2_marker", "CONCEPT:cmr_t1_marker"], condition="위와 같음, 지표 하나만 양성",
        source=f"{Q_MYO_CMR[0]}", quote=Q_MYO_CMR, limitation="'may still support' — 약한 지지", ddx="검사 → 미검사", status="APPLIED")
    add(id="PE-CTPA", disease=PE, relation_type="CONFIRMATORY_TEST", leaves=["CONCEPT:ctpa_filling_defect"],
        condition="PE 의심 시 1차 확인 검사", source=f"{DM} Pulmonary_Embolism.yaml diagnosis[0]", quote=None,
        limitation="AI 큐레이션 설명, 인용 근거 없음", ddx="검사 → 미검사", status="APPLIED")
    add(id="PE-DDIMER-EXCLUDE", disease=PE, relation_type="EXCLUSION_RULE", op="AND",
        leaves=["(낮은 임상 확률)", "(D-dimer 음성)"], condition="임상 확률 낮을 때 D-dimer 음성 → 배제",
        source=f"{DM} Pulmonary_Embolism.yaml diagnosis['D-dimer with pretest probability assessment'](인용 없음)",
        quote=None, limitation="로컬 2026 지침 초록(PMID:41712898)에 D-dimer 문구 없음 — 출처 미확인", ddx="검사 → 미검사",
        status="NOT_APPLIED(배제 규칙은 인용 확인 시에만)")
    add(id="TB-COUGH-2W", disease=TB, relation_type="SCREENING_CRITERION", leaves=["CONCEPT:cough_ge_2_weeks"],
        condition="결핵 선별(평가 시작) 기준 — 진단 아님. CHEST 는 고위험·HIV 등에서는 기간 무관 선별도 제안",
        source=f"{Q_TB_COUGH[0]} CHEST 2018", quote=Q_TB_COUGH, limitation="유병률 환경에 따라 다름, 기침 기간은 DDXPlus 에 없음",
        ddx="기침(E_201)은 있으나 기간 없음 → 미기록", status="APPLIED")
    add(id="TB-HIV-SYMPTOM-SCREEN", disease=TB, relation_type="SCREENING_CRITERION", op="OR", gate=["CONCEPT:hiv_infection"],
        leaves=["HP:0012735", "HP:0001945", "HP:0030166", "HP:0002105", "HP:0001824"],
        condition="HIV 감염자에서 WHO 증상(기침·발열·야간 발한·객혈·체중감소) 중 하나 → 결핵 평가 대상",
        source=f"{Q_TB_HIV[0]} CHEST 2018", quote=Q_TB_HIV, limitation="선별 민감도 증가 서술 — 진단 확정 아님",
        ddx="E_2(HIV)·E_201·E_91·E_45·E_162 관측 가능, 야간 발한은 정확 대응 질문 없음", status="APPLIED")
    add(id="TB-MTB-DETECTED", disease=TB, relation_type="CONFIRMATORY_TEST", leaves=["CONCEPT:mtb_detected"],
        condition="객담 Xpert·배양", source=f"{DM} Tuberculosis.yaml diagnosis['Sputum Culture']", quote=None,
        limitation="AI 큐레이션 설명('gold standard'), 인용 근거 없음", ddx="검사 → 미검사", status="APPLIED")
    return R


def add_discriminators(g: MedGraph, meta: dict) -> None:
    """APPLIED 관계만 그래프에 추가. 새 HP 노드는 이미 그래프에 있을 때만 사용(없으면 추가하지 않고 기록)."""
    for nid, (kind, label, src) in CONCEPTS.items():
        g.add_node(nid, kind, label, "REAL", src)
    for st in ("HP:0012251", "HP:0031594"):                         # ST 상승·PR 하강 → 심전도 변화 개념(정의상 '또는')
        if st in g.nodes:
            g.add_edge(st, "IS_A", "CONCEPT:pericarditis_ecg_change", "REAL",
                       f"{DM} Pericarditis.yaml diagnosis 'widespread ST-segment elevation or PR-segment depression'(정의)",
                       evidence_class="DISMECH_DEFINITION", role="CONCEPT_DEFINITION")
    meta.setdefault("discriminators", [])
    for r in relations():
        row = {k: v for k, v in r.items()}
        meta["discriminators"].append(row)
        if r["status"] != "APPLIED":
            continue
        miss = [n for n in r["leaves"] + r.get("gate", []) if n not in g.nodes]
        if miss:
            row["status"] = f"NOT_APPLIED(노드 없음 {miss})"
            continue
        src = f"{r['source']} · quote_check={r['quote_check']} · 조건: {r['condition']} · 제한: {r['limitation']}"
        if "op" in r:                                                # 규칙 노드
            rid = f"RULE:{r['id']}"
            g.add_node(rid, "RULE", f"{r['id']}({r['relation_type']})", "REAL", src, op=r["op"], gate_op="AND",
                       rule_type=r["relation_type"])
            for n in r["leaves"]:
                spec = {"negative_uninformative": True} if n == "HP:0034788" else {}
                g.add_edge(n, "PART_OF", rid, "REAL", src, **spec)
            for n in r.get("gate", []):
                g.add_edge(n, "GATES", rid, "REAL", src)
            g.add_edge(rid, "SUGGESTS", r["disease"], "REAL", src, evidence_class=r["evidence_class"], role=r["relation_type"])
        elif r["id"] == "PERI-RUB-NEG-UNINFORMATIVE":
            continue                                                 # 규칙 잎 spec(negative_uninformative)으로 반영
        else:
            for n in r["leaves"]:
                g.add_edge(n, "SUGGESTS", r["disease"], "REAL", src, evidence_class=r["evidence_class"], role=r["relation_type"])
