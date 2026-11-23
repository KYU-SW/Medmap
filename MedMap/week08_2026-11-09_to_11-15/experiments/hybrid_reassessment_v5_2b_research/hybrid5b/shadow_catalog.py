"""PE_SHADOW_RESEARCH 카탈로그. v4 정규화 관계와 같은 형식(v4 Reasoner·DiseaseKG·FlatRuleTable 가 그대로 읽음)으로 만들지만,
실제 엔진 카탈로그(evidence_relations_p2.json)와 완전히 분리된 메모리 객체다. engine_active=false.
- 방향 라벨은 원문 확인 조건이 있는 관계만: CTPA 양성 SUPPORT, CTPA 음성 WEAKEN, D-dimer 정상 WEAKEN(3단계·2단계 경로), YEARS(별도 경로).
- 관류 정상·근위부 DVT·D-dimer 상승·충만 결손·과거력은 방향 없음(상태 라벨만).
- 혈역학 정책 A/B/C 와 확률 해석은 정책 매개변수로 분리(전문의 미결)."""
from __future__ import annotations

import json

from hybrid4 import logic as LG

from . import P0

A = LG.Atom
PHASE_GATES = [
    {"cond": [A("clinical_phase", ("CONFIRMED_PE", "UNDER_TREATMENT", "POST_TREATMENT_FOLLOWUP"))], "outcome": "NOT_APPLICABLE",
     "note": "의심 평가 알고리즘 범위 밖(치료·추적·확진 후). 과거 확진의 반증으로 쓰지 않음", "unknown_policy": "HOLD", "origin": "SHADOW(v4 정책 승계)"},
    {"cond": [A("clinical_phase", ("RECURRENCE_EVALUATION",))], "outcome": "UNCERTAIN", "note": "재발 평가 원문 없음(PE5-06)", "unknown_policy": "HOLD", "origin": "SHADOW(v4 정책 승계)"},
]
UNSTABLE_GATE = {"cond": [A("haemo_state", ("UNSTABLE",))], "outcome": "NOT_APPLICABLE", "note": "혈역학 불안정 → Figure 4 경로(Figure 5 관계 비적용)",
                 "unknown_policy": "BLOCK_ONLY_IF_TRUE", "origin": "SHADOW:ESC19_T4"}
CUTOFF = ("FIXED", "AGE_ADJUSTED", "STATED_REFERENCE")
HAEMO_POLICIES = ("A_LEGACY_BLOCK_ONLY_IF_UNSTABLE", "B_REQUIRE_DOCUMENTED_STABILITY", "C_PATH_SPECIFIC")
PRETEST_POLICIES = ("SHADOW_OUTCOME_INVARIANT", "LEGACY_ANY_CONFLICT_HOLD", "LATEST_BEFORE_TEST")
DEFAULT_POLICY = {"haemo": "C_PATH_SPECIFIC", "pretest": "SHADOW_OUTCOME_INVARIANT"}
FIG5 = {"SH-CTPA-POS", "SH-CTPA-NEG", "SH-DD-NORMAL", "SH-DD-YEARS"}                 # Figure 5 경로(안정 환자 대상)
LEGACY_MAP = {"PE-CTPA-POSITIVE": "SH-CTPA-POS", "PE-CTPA-NEGATIVE": "SH-CTPA-NEG", "PE-DDIMER-NORMAL": "SH-DD-NORMAL", "PE-DDIMER-ELEVATED": "SH-DD-ELEVATED",
              "PE-PERFUSION-NORMAL": "SH-PERF-NORMAL", "PE-PROXIMAL-DVT": "SH-PROX-DVT", "PE-FILLING-DEFECT": "SH-FILLING-DEFECT", "PE-HISTORY-VTE": "SH-HISTORY-VTE"}


def p0_quotes() -> dict:
    return json.loads((P0 / "knowledge/v5_2b_p0_relation_review.json").read_text())["quotes"]


def _src(*ids):
    q = p0_quotes()
    return [{"name": q[i]["source_document"], "location": q[i]["section"], "summary": i, "quote": q[i]["excerpt"][:300], "url": "",
             "access": q[i]["access"]} for i in ids]


def _haemo_required(rid: str, policy: str) -> list:
    if policy == "A_LEGACY_BLOCK_ONLY_IF_UNSTABLE":
        return []
    if policy == "B_REQUIRE_DOCUMENTED_STABILITY" or rid in FIG5:
        return [A("haemo_state", ("STABLE",))]
    return []


def _rel(rid, finding, rtype, s: LG.Structured, srcs, status, legacy, note):
    return {"relation_id": rid, "finding": finding, "result_state": f"STATE:{finding}", "test_node": "", "target_diagnosis": "DX:Pulmonary embolism",
            "relation_type": rtype, "structured": s, "applicability": note, "exceptions": "", "requires_context": [], "sources": _src(*srcs),
            "verification_status": "RESEARCH_ONLY_NOT_CLINICALLY_VALIDATED", "evidence_version": "v5_2b_research_shadow_1", "catalog_path": "MEMORY_ONLY(engine_active=false)",
            "shadow_status": status, "legacy_counterpart": legacy, "engine_active": False}


def build(policy: dict | None = None) -> list:
    pol = {**DEFAULT_POLICY, **(policy or {})}
    hp = pol["haemo"]
    out = []
    s = LG.Structured("SH-CTPA-POS", gates=[UNSTABLE_GATE, *PHASE_GATES,
                                            {"cond": [A("level", ("SUBSEGMENTAL",))], "outcome": "UNCERTAIN", "note": "단독 아분절 위양성 가능(핵심 메시지 4)", "unknown_policy": "HOLD", "origin": "SHADOW:ESC19_KM"}],
                      required=[A("clinical_phase", ("SUSPECTED_ACUTE_PE_EVALUATION",)), A("level", ("SEGMENTAL_OR_PROXIMAL",)), A("pretest", ("INTERMEDIATE", "HIGH")),
                                *_haemo_required("SH-CTPA-POS", hp)],
                      directional_outcome="SUPPORT",
                      fallbacks=[{"cond": [A("clinical_phase", ("SUSPECTED_ACUTE_PE_EVALUATION",)), A("pretest", ("LOW",))], "outcome": "UNCERTAIN",
                                  "note": "낮은 확률 양성 CTPA: Table 6 행 미확인 — 방향 보류"}])
    out.append(_rel("SH-CTPA-POS", "CTPA_REPORTS_PE", "SUPPORTS_HYPOTHESIS", s, ("ESC19_7.1.2.1", "ESC19_KM", "ESC19_T4"), "RESEARCH_DIRECTIONAL",
                    "PE-CTPA-POSITIVE", "혈역학 불안정 없는 PE 의심 환자"))
    s = LG.Structured("SH-CTPA-NEG", gates=[UNSTABLE_GATE, *PHASE_GATES,
                                            {"cond": [A("pretest", ("HIGH",))], "outcome": "UNCERTAIN", "note": "높은 확률 음성 CTPA: 추가 영상 고려(Fig 5 각주 e, §4.5)", "unknown_policy": "HOLD", "origin": "SHADOW:ESC19_F5e"}],
                      required=[A("clinical_phase", ("SUSPECTED_ACUTE_PE_EVALUATION",)), A("pretest", ("LOW", "INTERMEDIATE")), *_haemo_required("SH-CTPA-NEG", hp)],
                      directional_outcome="WEAKEN")
    out.append(_rel("SH-CTPA-NEG", "CTPA_NORMAL", "WEAKENS_HYPOTHESIS", s, ("ESC19_4.5", "ESC19_F5e", "ESC19_T4"), "RESEARCH_DIRECTIONAL", "PE-CTPA-NEGATIVE",
                    "혈역학 불안정 없는 PE 의심 환자, 낮음·중간 확률"))
    s = LG.Structured("SH-DD-NORMAL", gates=[UNSTABLE_GATE, *PHASE_GATES,
                                             {"cond": [A("pretest", ("HIGH",))], "outcome": "NOT_APPLICABLE", "note": "높은 확률에서는 측정하지 않음(§7.1.2.1)", "unknown_policy": "BLOCK_ONLY_IF_TRUE", "origin": "SHADOW:ESC19_7.1.2.1"},
                                             {"cond": [A("ddimer_assay", ("POINT_OF_CARE", "MODERATE_SENSITIVITY")), A("pretest", ("INTERMEDIATE",))], "outcome": "NOT_APPLICABLE",
                                              "note": "중등도 민감·현장 검사는 낮은 확률(또는 PE-unlikely)에서만(각주 b)", "unknown_policy": "BLOCK_ONLY_IF_TRUE", "origin": "SHADOW:ESC19_F5b"},
                                             {"cond": [A("inpatient", (True,))], "outcome": "UNCERTAIN", "note": "입원 환자 D-dimer 'limited use'(각주 b) — 제외/주의 미결(CRQ-02)", "unknown_policy": "BLOCK_ONLY_IF_TRUE", "origin": "SHADOW:ESC19_F5b"},
                                             {"cond": [A("pregnant", (True,))], "outcome": "UNCERTAIN", "note": "임신: D-dimer 상승·별도 경로(§9.2.1)", "unknown_policy": "BLOCK_ONLY_IF_TRUE", "origin": "SHADOW:ESC19_9.2"},
                                             {"cond": [A("anticoagulated", (True,))], "outcome": "UNCERTAIN", "note": "항응고 중 D-dimer 원문 NOT_FOUND", "unknown_policy": "BLOCK_ONLY_IF_TRUE", "origin": "SHADOW:ESC19_NF"}],
                      required=[A("clinical_phase", ("SUSPECTED_ACUTE_PE_EVALUATION",)), *_haemo_required("SH-DD-NORMAL", hp)],
                      alternatives=[[A("pretest", ("LOW", "INTERMEDIATE")), A("ddimer_assay", ("HIGH_SENSITIVITY",)), A("ddimer_cutoff", CUTOFF)],
                                    [A("pretest", ("LOW",)), A("ddimer_assay", ("MODERATE_SENSITIVITY", "POINT_OF_CARE")), A("ddimer_cutoff", CUTOFF)],
                                    [A("pretest_two_level", ("UNLIKELY",)), A("ddimer_assay", ("MODERATE_SENSITIVITY",)), A("ddimer_cutoff", CUTOFF)]],
                      directional_outcome="WEAKEN")
    out.append(_rel("SH-DD-NORMAL", "DDIMER_NORMAL", "WEAKENS_HYPOTHESIS", s, ("ESC19_7.1.2.1", "ESC19_F5b", "ESC19_9.2", "ESC19_NF"), "RESEARCH_DIRECTIONAL",
                    "PE-DDIMER-NORMAL", "확률 평가 후, 검사법·절단값·확률 조합별 경로"))
    for rid, finding, status, legacy, srcs, note in (
            ("SH-DD-ELEVATED", "DDIMER_ELEVATED", "NOT_DIRECTIONAL", "PE-DDIMER-ELEVATED", ("ESC19_7.1.2.1",), "D-dimer 상승은 확인에 쓰지 않음"),
            ("SH-PERF-NORMAL", "PERFUSION_SCAN_NORMAL", "INTERPRETATION_PENDING", "PE-PERFUSION-NORMAL", ("ESC19_4.6",), "'항응고 보류 안전'(관리 결과) → 배제 방향 변환 미확정"),
            ("SH-PROX-DVT", "PROXIMAL_DVT_ON_ULTRASOUND", "VTE_TREATMENT_SUFFICIENT_NON_DIRECTIONAL", "PE-PROXIMAL-DVT", ("ESC19_4.10",), "치료 결정 문구 — PE 진단 방향 아님"),
            ("SH-FILLING-DEFECT", "CTPA_FILLING_DEFECT_ONLY", "SOURCE_INCOMPLETE", "PE-FILLING-DEFECT", ("ESC19_NF",), "CTPA 충만 결손 정의 원문 미확인"),
            ("SH-HISTORY-VTE", "HISTORY_PE_OR_VTE", "NOT_DIRECTIONAL", "PE-HISTORY-VTE", ("ESC19_4.2",), "확률 점수 항목")):
        s = LG.Structured(rid, unconditional={"outcome": f"NO_DIRECTION:{status}", "note": note})
        out.append(_rel(rid, finding, "EVALUATES_HYPOTHESIS", s, srcs, status, legacy, note))
    return out


def years_relation(policy: dict | None = None):
    """YEARS: 3단계 확률을 쓰지 않는 별도 경로(각주 c). D-dimer 수치·단위·YEARS 항목 수에서 계산한 years_rule_out 을 사용. KG 조회 없이 공용 함수로 평가."""
    pol = {**DEFAULT_POLICY, **(policy or {})}
    s = LG.Structured("SH-DD-YEARS", gates=[UNSTABLE_GATE, *PHASE_GATES,
                                            {"cond": [A("pregnant", (True,))], "outcome": "UNCERTAIN", "note": "임신 적응 YEARS 는 별도(§9.2.1) — 일반 YEARS 적용 보류", "unknown_policy": "BLOCK_ONLY_IF_TRUE", "origin": "SHADOW:ESC19_9.2"}],
                      required=[A("clinical_phase", ("SUSPECTED_ACUTE_PE_EVALUATION",)), A("years_rule_out", (True,)), *_haemo_required("SH-DD-YEARS", pol["haemo"])],
                      directional_outcome="WEAKEN",
                      fallbacks=[{"cond": [A("years_rule_out", (False,))], "outcome": "NOT_APPLICABLE", "note": "YEARS 배제 기준 미충족 — 방향 없음(다음 검사 경로)"}])
    return _rel("SH-DD-YEARS", "DDIMER_YEARS_EVALUATION", "WEAKENS_HYPOTHESIS", s, ("ESC19_F5c", "ESC19_9.2"), "RESEARCH_DIRECTIONAL", None,
                "YEARS 항목 수 + D-dimer(µg/L) 기준 — 3단계 확률 불필요")


def catalog_rows(policy: dict | None = None) -> list:
    rows = []
    for r in build(policy) + [years_relation(policy)]:
        rows.append({k: r[k] for k in ("relation_id", "finding", "relation_type", "shadow_status", "legacy_counterpart", "engine_active", "applicability", "verification_status")}
                    | {"conditions": r["structured"].to_dict(), "sources": r["sources"], "labels": ["RESEARCH_ONLY", "NOT_CLINICALLY_VALIDATED", "ENGINE_ACTIVE_FALSE"]})
    return rows
