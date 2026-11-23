"""합성 실험 사례(그룹 A~T + U 비방향·확장). 전체 데카르트곱 대신 동등 분할·경계값 대표 사례.
기대값(Shadow 판단 토큰)은 실행 전에 고정한다(2026-11-09). 토큰: SUPPORT / WEAKEN / HOLD(INSUFFICIENT·UNCERTAIN) / NA(NOT_APPLICABLE) / NODIR(방향 없음 상태) / NONE(판단 없음).
basis: SOURCE_SUPPORTED_EXPECTATION / RESEARCHER_INTERPRETATION / CLINICIAN_REVIEW_REQUIRED / UNKNOWN. 문헌 기대값도 임상 정답이 아니다."""
from __future__ import annotations

from hybrid4.graphs import Doc, Episode
from hybrid52.hypotheses import HypothesisSpec
from hybrid522.graphs import PatientGraph522

S_, R_, C_, U_ = "SOURCE_SUPPORTED_EXPECTATION", "RESEARCHER_INTERPRETATION", "CLINICIAN_REVIEW_REQUIRED", "UNKNOWN"
SUS = "Pulmonary embolism is suspected."
ST = " The patient is hemodynamically stable."
UNST = " The patient is hemodynamically unstable."
NEG = "IMPRESSION: No evidence of pulmonary embolism."
POS = "IMPRESSION: Acute pulmonary embolism in the right lower lobe segmental arteries."
SUBSEG = "IMPRESSION: Isolated subsegmental pulmonary embolism."
DD_HS = "D-dimer measured by ELISA was normal, below the age-adjusted cut-off."
DD_MOD = "Moderately sensitive D-dimer was normal, below the fixed cut-off."
DD_NOASSAY = "D-dimer was normal."
DD_HS_NOCUT = "D-dimer measured by ELISA was normal."
DD_HSPHRASE = "D-dimer was normal (350 ng/mL, high-sensitivity assay, fixed cut-off 500)."
DD_ELEV = "Laboratory testing revealed an elevated D-dimer (4365 ng/mL)."
PERF = "Perfusion scan was normal."
DVT = "Compression ultrasound shows femoral deep vein thrombosis."


def PRE(level, tool="the Wells score"):
    return f"Clinical probability was assessed as {level} using {tool}."


def case(cid, group, records, expect, as_of=10.0, eps=(("E1", "CURRENT_EVALUATION"),), hyp_ep="E1", p0=None, expect_cmp=None, policy=None, tests=(), note=""):
    """records: (rid, text, doc_type, observed, available, episode|None, meta dict). expect: {shadow_relation_id: (tokens, basis)}."""
    return {"case_id": cid, "group": group, "records": records, "expect": expect, "as_of": as_of, "episodes": eps, "hyp_episode": hyp_ep, "p0_scenario": p0,
            "expect_comparison": expect_cmp, "policy": policy, "tests": tests, "note": note}


def R(rid, text, avail, dt=None, ep=None, **meta):
    return (rid, text, dt or ("CTPA_REPORT" if text.startswith("IMPRESSION") else "LAB" if "D-dimer" in text and not text.startswith(("Pulm", "Clin")) else "NOTE"),
            avail - 0.5, avail, ep, meta)


def base(pre=None, stab=ST, tool="the Wells score"):
    return R("n1", SUS + (" " + PRE(pre, tool) if pre else "") + (stab or ""), 1.0)


CASES = [
    # A 일반 적용
    case("A01", "A", [base("low"), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"WEAKEN"}, S_)}, p0="A_LOW"),
    case("A02", "A", [base("intermediate"), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"WEAKEN"}, S_)}, p0="B_INTERMEDIATE"),
    case("A03", "A", [base("intermediate"), R("r1", POS, 5)], {"SH-CTPA-POS": ({"SUPPORT"}, S_)}, p0="B_INTERMEDIATE"),
    case("A04", "A", [base("high"), R("r1", POS, 5)], {"SH-CTPA-POS": ({"SUPPORT"}, S_)}, p0="C_HIGH"),
    case("A05", "A", [base("low"), R("l1", DD_HS, 2)], {"SH-DD-NORMAL": ({"WEAKEN"}, S_)}, p0="A_LOW"),
    case("A06", "A", [base("intermediate"), R("l1", DD_HS, 2)], {"SH-DD-NORMAL": ({"WEAKEN"}, S_)}, p0="B_INTERMEDIATE"),
    case("A07", "A", [base("low"), R("l1", DD_MOD, 2)], {"SH-DD-NORMAL": ({"WEAKEN"}, S_)}),
    case("A08", "A", [base("high"), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"HOLD"}, S_)}, p0="C_HIGH"),
    case("A09", "A", [base("high"), R("l1", DD_HS, 2)], {"SH-DD-NORMAL": ({"NA"}, S_)}, p0="C_HIGH"),
    case("A10", "A", [base("intermediate"), R("l1", DD_MOD, 2)], {"SH-DD-NORMAL": ({"NA"}, S_)}),
    case("A11", "A", [base("low"), R("r1", POS, 5)], {"SH-CTPA-POS": ({"HOLD"}, U_)}, p0="A_LOW"),
    case("A12", "A", [base("intermediate"), R("r1", SUBSEG, 5)], {"SH-CTPA-POS": ({"HOLD", "NONE"}, S_)}),
    # B 확률 미기록
    case("B01", "B", [base(None), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"HOLD"}, S_)}, p0="D_NOT_RECORDED"),
    case("B02", "B", [base(None), R("l1", DD_HS, 2)], {"SH-DD-NORMAL": ({"HOLD"}, S_)}, p0="D_NOT_RECORDED"),
    case("B03", "B", [base(None), R("r1", POS, 5)], {"SH-CTPA-POS": ({"HOLD"}, S_)}, p0="D_NOT_RECORDED"),
    # C 같은 시각 충돌
    case("C01", "C", [base("low"), R("n2", PRE("high"), 1.0), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"HOLD"}, R_)}, p0="E_LOW_HIGH_SAME_TIME"),
    case("C02", "C", [base("low"), R("n2", PRE("high"), 1.0), R("l1", DD_HS, 2)], {"SH-DD-NORMAL": ({"HOLD", "NA"}, R_)}, p0="E_LOW_HIGH_SAME_TIME"),
    case("C03", "C", [base("low"), R("n2", PRE("intermediate"), 1.0), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"WEAKEN"}, R_)}),
    # D 다른 도구
    case("D01", "D", [base("low", tool="the revised Geneva score"), R("n2", PRE("intermediate"), 1.0), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"WEAKEN"}, R_)},
         p0="H_DIFFERENT_TOOLS", expect_cmp="LEGACY_MORE_CONSERVATIVE"),
    case("D02", "D", [base("low", tool="the revised Geneva score"), R("n2", PRE("intermediate"), 1.0), R("l1", DD_HS, 2)], {"SH-DD-NORMAL": ({"WEAKEN"}, R_)},
         p0="H_DIFFERENT_TOOLS", expect_cmp="LEGACY_MORE_CONSERVATIVE"),
    case("D03", "D", [base("low", tool="the revised Geneva score"), R("n2", PRE("intermediate"), 1.0), R("r1", POS, 5)], {"SH-CTPA-POS": ({"HOLD"}, R_)}, p0="H_DIFFERENT_TOOLS"),
    # E 시간에 따른 재평가
    case("E01", "E", [base("low"), R("n2", PRE("high"), 3.0), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"HOLD"}, C_)}, p0="F_CHANGED_OVER_TIME"),
    case("E02", "E", [base("low"), R("n2", PRE("intermediate"), 3.0), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"WEAKEN"}, R_)}),
    case("E03", "E", [base("low"), R("n2", PRE("high"), 3.0), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"HOLD"}, R_)}, policy={"pretest": "LATEST_BEFORE_TEST"},
         note="민감도 분석 정책: 최신 평가(HIGH) → 음성 CTPA UNCERTAIN"),
    # F 혈역학 미기록
    case("F01", "F", [base("low", stab=None), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"HOLD"}, C_)}, p0="S1_STABILITY_NOT_RECORDED_LOW", expect_cmp="SHADOW_MORE_CONSERVATIVE"),
    case("F02", "F", [base("low", stab=None), R("l1", DD_HS, 2)], {"SH-DD-NORMAL": ({"HOLD"}, C_)}, p0="S1_STABILITY_NOT_RECORDED_LOW", expect_cmp="SHADOW_MORE_CONSERVATIVE"),
    case("F03", "F", [base("low", stab=" Blood pressure 82/50 mmHg despite fluids; norepinephrine was started."), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"HOLD"}, R_)},
         note="활력징후만 — Table 4 행 구조 미확정이라 판정하지 않음"),
    case("F04", "F", [base("low", stab=None), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"WEAKEN"}, R_)}, policy={"haemo": "A_LEGACY_BLOCK_ONLY_IF_UNSTABLE"},
         note="정책 A(레거시) 민감도 분석"),
    # G 불안정
    case("G01", "G", [base("low", stab=UNST), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"NA"}, S_)}, p0="S2_UNSTABLE_LOW"),
    case("G02", "G", [base("low", stab=" Cardiac arrest occurred and CPR was performed."), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"NA"}, S_)}),
    # H 검사법 미확인
    case("H01", "H", [base("low"), R("l1", DD_NOASSAY, 2)], {"SH-DD-NORMAL": ({"HOLD"}, S_)}),
    case("H02", "H", [base("intermediate"), R("l1", DD_HSPHRASE, 2)], {"SH-DD-NORMAL": ({"WEAKEN"}, R_)}, expect_cmp="LEGACY_MORE_CONSERVATIVE",
         note="'high-sensitivity assay' 명시 문구 연구용 매핑(v3 미추출)"),
    # I 기준값 미확인
    case("I01", "I", [base("low"), R("l1", DD_HS_NOCUT, 2)], {"SH-DD-NORMAL": ({"HOLD"}, S_)}),
    # J YEARS
    case("J01", "J", [base(None), R("l1", "D-dimer was 800 µg/L. No YEARS items were present.", 2)], {"SH-DD-YEARS": ({"WEAKEN"}, S_)}, expect_cmp="LEGACY_MORE_CONSERVATIVE"),
    case("J02", "J", [base(None), R("l1", "D-dimer was 800 µg/L. One YEARS item was present.", 2)], {"SH-DD-YEARS": ({"NA"}, S_)}),
    case("J03", "J", [base(None), R("l1", "D-dimer was 420 µg/L. One YEARS item was present.", 2)], {"SH-DD-YEARS": ({"WEAKEN"}, S_)}),
    case("J04", "J", [base(None), R("l1", "D-dimer was 800. No YEARS items were present.", 2)], {"SH-DD-YEARS": ({"HOLD"}, S_)}),
    case("J05", "J", [base(None), R("n2", "She is 32 weeks pregnant.", 1.0), R("l1", "D-dimer was 800 µg/L. No YEARS items were present.", 2)], {"SH-DD-YEARS": ({"HOLD"}, C_)}),
    case("J06", "J", [base(None, stab=None), R("l1", "D-dimer was 800 µg/L. No YEARS items were present.", 2)], {"SH-DD-YEARS": ({"HOLD"}, C_)}),
    # K 과거 확진 / L 치료·추적
    case("K01", "K", [R("n1", "Pleuritic chest pain. Pulmonary embolism was confirmed according to the outside note." + ST, 1.0), R("r1", NEG, 5)],
         {"SH-CTPA-NEG": ({"NA", "HOLD", "NONE"}, R_)}),
    case("L01", "L", [R("n1", "Pulmonary embolism was diagnosed one month ago and she is currently receiving apixaban." + ST, 1.0),
                      R("r1", "Follow-up CTPA after three months of anticoagulation showed no pulmonary embolism.", 5, dt="CTPA_REPORT")],
         {"SH-CTPA-NEG": ({"NA", "HOLD", "NONE"}, R_)}),
    case("L02", "L", [R("n1", "Pulmonary embolism was diagnosed one month ago and she is currently receiving apixaban." + ST, 1.0), R("l1", DD_HS, 2)],
         {"SH-DD-NORMAL": ({"NA", "HOLD", "NONE"}, R_)}),
    # M 다른 에피소드
    case("M01", "M", [R("n0", PRE("high"), 0.2, ep="E0"), R("n1", SUS + " " + PRE("low") + ST, 1.0, ep="E2"), R("r1", NEG, 5, ep="E2")],
         {"SH-CTPA-NEG": ({"WEAKEN"}, R_)}, eps=(("E0", "PAST_EPISODE"), ("E2", "CURRENT_EVALUATION")), hyp_ep="E2", p0="G_OTHER_EPISODE_HIGH"),
    case("M02", "M", [R("r0", NEG, 0.5, ep="E0"), R("n1", SUS + " " + PRE("low") + ST, 1.0, ep="E2")],
         {"SH-CTPA-NEG": ({"NONE"}, R_)}, eps=(("E0", "PAST_EPISODE"), ("E2", "CURRENT_EVALUATION")), hyp_ep="E2"),
    # N 주문만 / O 공개 전
    case("N01", "N", [base("low"), R("o1", "CTPA was ordered.", 2)], {"SH-CTPA-NEG": ({"NONE"}, S_), "SH-CTPA-POS": ({"NONE"}, S_)},
         tests=(("ctpa", "CTPA", "ORDER", 2.0),)),
    case("O01", "O", [base("low"), R("r1", NEG, 12)], {"SH-CTPA-NEG": ({"NONE"}, S_)}, as_of=10.0),
    case("O02", "O", [base("low"), R("r1", NEG, 12)], {"SH-CTPA-NEG": ({"WEAKEN"}, S_)}, as_of=13.0),
    # U 비방향·확장
    case("U01", "U", [base("low"), R("p1", PERF, 2)], {"SH-PERF-NORMAL": ({"NODIR"}, R_)}, expect_cmp="SOURCE_INCOMPLETE"),
    case("U02", "U", [base("low"), R("u1", DVT, 2)], {"SH-PROX-DVT": ({"NODIR"}, R_)}, expect_cmp="SEMANTIC_REVIEW_REQUIRED"),
    case("U03", "U", [base("low"), R("l1", DD_ELEV, 2)], {"SH-DD-ELEVATED": ({"NODIR"}, S_)}),
    case("U04", "U", [R("n1", SUS + " " + PRE("low") + " History of pulmonary embolism." + ST, 1.0)], {"SH-HISTORY-VTE": ({"NODIR", "NONE"}, S_)}),
    case("U05", "U", [R("n1", SUS + " PE was considered unlikely according to the Wells score." + ST, 1.0), R("l1", DD_MOD, 2)], {"SH-DD-NORMAL": ({"WEAKEN"}, R_)},
         p0="T1_TWO_LEVEL_UNLIKELY", expect_cmp="LEGACY_MORE_CONSERVATIVE"),
    case("U06", "U", [R("n1", SUS + " PE was considered unlikely according to the Wells score." + ST, 1.0), R("r1", NEG, 5)], {"SH-CTPA-NEG": ({"HOLD"}, C_)},
         p0="T1_TWO_LEVEL_UNLIKELY"),
    case("U07", "U", [base("low"), R("n2", "The patient has been hospitalized for 5 days.", 1.0), R("l1", DD_HS, 2)], {"SH-DD-NORMAL": ({"HOLD"}, C_)},
         expect_cmp="SHADOW_MORE_CONSERVATIVE"),
    case("U08", "U", [base("low"), R("n2", "She is 32 weeks pregnant.", 1.0), R("l1", DD_HS, 2)], {"SH-DD-NORMAL": ({"HOLD"}, C_)}, expect_cmp="SHADOW_MORE_CONSERVATIVE"),
]
# Z: v5-2B-P0 조건 진리표 33행 중 대응 사례가 없던 9행(2026-11-09 추가). 기대값 = P0 후보 판단(사전 등록) 그대로.
CASES += [
    case("Z01", "Z", [base("low"), R("n2", PRE("high"), 1.0), R("r1", POS, 5)], {"SH-CTPA-POS": ({"HOLD"}, R_)}, p0="E_LOW_HIGH_SAME_TIME"),
    case("Z02", "Z", [base("low"), R("n2", PRE("high"), 3.0), R("r1", POS, 5)], {"SH-CTPA-POS": ({"HOLD"}, C_)}, p0="F_CHANGED_OVER_TIME"),
    case("Z03", "Z", [base("low"), R("n2", PRE("high"), 3.0), R("l1", DD_HS, 4)], {"SH-DD-NORMAL": ({"HOLD"}, C_)}, p0="F_CHANGED_OVER_TIME"),
    case("Z04", "Z", [R("n0", PRE("high"), 0.2, ep="E0"), R("n1", SUS + " " + PRE("low") + ST, 1.0, ep="E2"), R("r1", POS, 5, ep="E2")],
         {"SH-CTPA-POS": ({"HOLD"}, U_)}, eps=(("E0", "PAST_EPISODE"), ("E2", "CURRENT_EVALUATION")), hyp_ep="E2", p0="G_OTHER_EPISODE_HIGH"),
    case("Z05", "Z", [R("n0", PRE("high"), 0.2, ep="E0"), R("n1", SUS + " " + PRE("low") + ST, 1.0, ep="E2"), R("l1", DD_HS, 2, ep="E2")],
         {"SH-DD-NORMAL": ({"WEAKEN"}, R_)}, eps=(("E0", "PAST_EPISODE"), ("E2", "CURRENT_EVALUATION")), hyp_ep="E2", p0="G_OTHER_EPISODE_HIGH"),
    case("Z06", "Z", [R("n1", SUS + " PE was considered unlikely according to the Wells score." + ST, 1.0), R("r1", POS, 5)], {"SH-CTPA-POS": ({"HOLD"}, C_)},
         p0="T1_TWO_LEVEL_UNLIKELY"),
    case("Z07", "Z", [base("low", stab=None), R("r1", POS, 5)], {"SH-CTPA-POS": ({"HOLD"}, C_)}, p0="S1_STABILITY_NOT_RECORDED_LOW"),
    case("Z08", "Z", [base("low", stab=UNST), R("r1", POS, 5)], {"SH-CTPA-POS": ({"NA"}, S_)}, p0="S2_UNSTABLE_LOW"),
    case("Z09", "Z", [base("low", stab=UNST), R("l1", DD_HS, 2)], {"SH-DD-NORMAL": ({"NA"}, S_)}, p0="S2_UNSTABLE_LOW"),
]


def build_pg(c: dict) -> PatientGraph522:
    p = PatientGraph522(f"SYN5B-{c['case_id']}")
    for e, k in c["episodes"]:
        p.add_episode(Episode(e, k))
    p.add_hypothesis_spec(HypothesisSpec("h_pe", "DX:Pulmonary embolism", c["hyp_episode"], "PHYSICIAN_WORKING_DIAGNOSIS"))
    for rid, text, dt, obs, av, ep, meta in c["records"]:
        p.add_record52(Doc(rid, text, dt, obs, av, supersedes=meta.get("supersedes")), ep, meta.get("event"), tuple(meta.get("derived_from", ())))
    for tid, kind, ev, at in c["tests"]:
        p.add_test_order(tid, kind, ev, at, c["hyp_episode"])
    return p


def token(direction: str | None) -> str:
    if direction is None:
        return "NONE"
    if direction in ("SUPPORT", "WEAKEN"):
        return direction
    if direction == "NOT_APPLICABLE":
        return "NA"
    if direction.startswith("NO_DIRECTION"):
        return "NODIR"
    return "HOLD"
