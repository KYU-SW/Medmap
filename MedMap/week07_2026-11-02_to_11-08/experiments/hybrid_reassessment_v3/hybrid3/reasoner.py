"""기능 E·F·G: 그래프 경로로 찾은 검증 관계에 추출된 임상 맥락을 적용해 가설별 판단, 시간순 갱신, 의사용 설명.
P2 의 맥락 출처 규칙(normalize_context)·임상 단계(resolve)·가설 대상(target_check)·D-dimer 조건·관계 적용(apply)을 그대로 쓴다.
판단은 확률이 아니며 의사 확인 대상이다."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import concepts as CP, context as CX
from .concepts import CC_MOD as CC, EC_MOD as EC, P2, PS, RLX as RL
from .kg import EvidenceGraph

T1 = P2.T1
from hybrid.schema import AssertedBy, DataClass, DiagnosisAssertion, DxStatus, EvidenceItem, EvidenceKind, Polarity, Provenance, TestEvent  # noqa: E402

DIRECTIONAL = ("SUPPORT", "WEAKEN")
# 판단 보류 원인 분류. A 기록에 있으나 추출 못함, B 기록에 없음, C 충돌, D 지원하지 않는 개념, E 의학 근거 부족, NOT_A_GAP 근거가 아닌 것이 정상
REASON_CLASS = {"CONCEPT_NOT_SUPPORTED": "D", "SUSPICION_STATEMENT_USED_AS_CONTEXT": "NOT_A_GAP", "AMBIGUOUS_CONCEPT": "D", "HYPOTHESIS_NOT_IN_GRAPH": "D", "NO_GRAPH_NODE": "D", "NO_VERIFIED_GRAPH_RELATION": "E", "NO_VERIFIED_RELATION": "E",
                "ASSOCIATION_ONLY_NO_VERIFIED_DIRECTION": "E", "EXTRACTOR_CONFLICT": "C", "DDIMER_RESULT_CONFLICTING_TEXT": "C", "NO_RESULT_YET": "B", "TEST_NAME_WITHOUT_RESULT": "B",
                "DDIMER_RESULT_NOT_STATED": "B", "VALUE_WITHOUT_ASSAY_INTERPRETATION": "A", "DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE": "B", "UNCERTAIN_MENTION": "B",
                "UNCERTAIN_REPORT": "B", "PARTIAL_NEGATIVE_REPORT": "B", "FILLING_DEFECT_SITE_OR_STATE_UNCLEAR": "B", "DVT_NOT_PROXIMAL_ULTRASOUND_CONFIRMED": "B",
                "PERFUSION_RESULT_NOT_RELATED": "B", "TEST_PURPOSE_NOT_RESULT": "NOT_A_GAP", "OTHER_PERSON_NOT_PATIENT": "NOT_A_GAP", "CONDITIONAL_STATEMENT": "NOT_A_GAP",
                "HISTORICAL_FINDING": "NOT_A_GAP", "ABBREVIATION_DEFINITION_ONLY": "NOT_A_GAP", "HYPOTHESIS_NOT_USABLE": "NOT_A_GAP"}
CUES = {"pretest": r"probabilit|\bWells\b|\bGeneva\b|\bYEARS\b|gestalt|pre-?test|\bPE (?:un)?likely\b",
        "suspected": r"suspect|suspicion|concern|rule out|exclude|evaluat|investigat|work-?up",
        "ddimer_assay": r"\bassay\b|ELISA|immunoturbid|latex|\bFEU\b|point[- ]of[- ]care|sensitiv",
        "ddimer_cutoff": r"cut-?off|threshold|reference|normal range|<\s*\d|age-adjusted",
        "clinical_phase": r"follow-?up|anticoag|treat|recurr|diagnos|suspect|exclude|rule out",
        "level": r"segment|lobar|central|\bmain\b|saddle|proximal|distal|interlobar",
        "evidence_observed_at": r".", "hypothesis_target_time": r"."}
KO = {"SUPPORT": "지지", "WEAKEN": "약화", "NO_CLEAR_EFFECT": "명확한 방향 없음", "UNCERTAIN": "불확실", "INSUFFICIENT_EVIDENCE": "판단 정보 부족", "NOT_APPLICABLE": "적용 범위 밖", "ABSTAIN": "평가 보류"}
GAP_KO = {"A": "기록에 단서가 있으나 추출하지 못함", "B": "기록에 없음(의료진 확인 필요)", "C": "기록 간 충돌", "D": "지원하지 않는 개념", "E": "검증된 의학 관계 없음", "NOT_A_GAP": "근거가 아닌 진술(정상 보류)"}


@dataclass
class Doc:
    doc_id: str
    text: str
    doc_type: str = "NOTE"
    observed_at: float | None = None
    available_at: float | None = None
    supersedes: str | None = None
    author_role: str = "UNKNOWN"
    physician_confirmed: bool = False                                    # 메타데이터에 명시된 경우만 True


@dataclass
class Hypothesis:
    hyp_id: str
    label: str
    concept: str
    at: float
    status: DxStatus = DxStatus.WORKING_DIAGNOSIS
    episode_id: str = "E?"
    kind: str = "CURRENT_EVALUATION"                                     # CURRENT_EVALUATION / PAST_EPISODE / RECURRENCE
    target_time: float | None = None
    supersedes: str | None = None
    asserted_by: AssertedBy = AssertedBy.SIMULATED

    def assertion(self, case_id: str) -> DiagnosisAssertion:
        return DiagnosisAssertion(self.hyp_id, case_id, self.label, self.status, self.asserted_by, self.at, Provenance("hypothesis_event", self.hyp_id, DataClass.SYNTHETIC),
                                  concept_id=self.concept, supersedes=self.supersedes)


def _ctx_value(agg: dict, k: str):
    x = agg.get(k, {})
    return {"value": x["value"], "source": "RECORD"} if x.get("status") == "FOUND" else None


def classify_gaps(missing: list, reason: str, agg: dict, texts: str) -> list:
    out = []
    for k in missing:
        if agg.get(k, {}).get("status") == "CONFLICT":
            g = "C"
        elif k in CUES and re.search(CUES[k], texts, re.I) and k not in ("evidence_observed_at", "hypothesis_target_time"):
            g = "A"
        else:
            g = "B"
        out.append({"item": k, "class": g, "meaning": GAP_KO[g]})
    if reason:
        g = REASON_CLASS.get(reason, "E")
        out.append({"item": reason, "class": g, "meaning": GAP_KO[g]})
    return out


class Engine:
    def __init__(self, graph: EvidenceGraph | None = None):
        self.kg = graph or EvidenceGraph()

    def assess(self, rec: dict, hyp: Hypothesis, case_ctx: dict, agg: dict | None = None, texts: str = "") -> dict:
        agg = agg or {}
        h = hyp.assertion("c")
        norm = EC.normalize_context(case_ctx)
        ctx = norm["values"]
        fs = CP.finding_state(rec)
        node = self.kg.concept_node(rec["concept"]) if rec["concept"] else ""
        out = {"hypothesis": hyp.label, "hypothesis_status": hyp.status.value, "episode_id": hyp.episode_id, "hypothesis_kind": hyp.kind,
               "input_sentence": rec["sentence"], "char_span": rec["char_span"], "surface": rec["surface"], "concept": rec["concept"], "subtype": rec["subtype"],
               "concept_kind": rec["concept_kind"], "link_status": rec["link_status"], "role": rec["role"], "assertion": rec["assertion"], "assertion_cue": rec["cue"],
               "graph_node": node, "finding": fs.get("finding", ""), "direction": "ABSTAIN", "relation_id": "", "relation_type": "", "graph_path": [], "applicability": "",
               "conditions_used": {}, "sources": [], "uncertainty": [], "abstain_reason": "", "missing_context": [], "gaps": [], "context_provenance": norm["provenance"],
               "clinical_context": None, "test_conditions": None, "graph_context_edges": self.kg.base_context(node, hyp.concept) if node else [],
               "physician_confirmation_needed": True, "extractor_check": fs.get("v3b")}

        def stop(reason):
            if reason in ("UNCERTAIN_MENTION", "TEST_PURPOSE_NOT_RESULT") and rec["concept"] == "PE_DIAGNOSIS" and CX.R_SUSPECT.search(rec["sentence"]):
                reason = "SUSPICION_STATEMENT_USED_AS_CONTEXT"              # 의심·검사 목적 진술은 근거가 아니라 맥락
            out["abstain_reason"] = reason
            out["gaps"] = classify_gaps([], reason, agg, texts)
            return out
        if not h.usable_as_hypothesis():
            return stop("HYPOTHESIS_NOT_USABLE")
        if hyp.concept not in self.kg.nodes:
            return stop("HYPOTHESIS_NOT_IN_GRAPH")
        if "finding" not in fs:
            r = fs["reason"]
            if r == "NO_VERIFIED_RELATION" and out["graph_context_edges"]:
                r = "ASSOCIATION_ONLY_NO_VERIFIED_DIRECTION"
            return stop(r)
        paths = self.kg.evidence_paths(fs["finding"], hyp.concept)
        if not paths:
            return stop("NO_VERIFIED_GRAPH_RELATION")
        p = paths[0]
        e, rel = p["edge"], p["edge"]["relation"]
        c = dict(ctx)
        if "level" in fs:
            c["level"] = fs["level"]
        tgt = {"result": None}
        req = set(rel.get("requires_context", ()))
        if "clinical_phase" in req:
            cc = CC.resolve(rec["sentence"], h.status.value, ctx)
            tgt = EC.target_check(ctx, cc["phase"])
            cc["phase_after_target"] = tgt["phase"]
            out["clinical_context"] = cc
            c["clinical_phase"] = None if tgt["phase"] == CC.UNKNOWN else tgt["phase"]
        if rel["finding"] == "DDIMER_NORMAL":
            dd = EC.ddimer_conditions(rec["sentence"], ctx)
            out["test_conditions"] = dd
            c["ddimer_assay"], c["ddimer_cutoff"] = dd["assay"], dd["cutoff"]
        ex = self.kg.spec.get("exclusion_conditions", {})
        if rel["id"] in ex.get("relations", ()) and c.get("haemodynamic_instability") is True:
            res = {"direction": ex["direction"], "note": ex["note"], "missing_context": []}
        else:
            res = tgt["result"] or RL.apply(rel, c)
        out.update({"direction": res["direction"], "relation_id": rel["id"], "relation_type": e["relation_type"], "graph_path": p["path"], "applicability": e["clinical_context"],
                    "conditions_used": {k: c.get(k) for k in sorted(req | {"haemodynamic_instability"})}, "missing_context": res["missing_context"],
                    "uncertainty": [x for x in (res.get("note"), e.get("exceptions")) if x], "sources": [{**s, "verification": e["verification"]} for s in e["provenance"]],
                    "assumed_context_used": sorted(set(norm["assumed_keys"]) & (req | {"suspected"}))})
        if res["direction"] in ("INSUFFICIENT_EVIDENCE",):
            out["gaps"] = classify_gaps(res["missing_context"], "", agg, texts)
        elif res["direction"] == "UNCERTAIN":
            out["gaps"] = [{"item": rel["id"], "class": "E", "meaning": "관계가 이 맥락에서 방향을 정하지 않음"}]
        return out


def explain(r: dict) -> str:
    """구조화 템플릿 설명(LLM 없음)."""
    L = [f"[진단 가설] {r['hypothesis']} ({r['hypothesis_status']}, 에피소드 {r['episode_id']}, {r['hypothesis_kind']})",
         f"[근거 문장] \"{r['input_sentence'][:180]}\" (문서 {r.get('document', '-')}, 관찰 {r.get('observed_at', 'UNKNOWN')}, 이용 가능 {r.get('available_at', 'UNKNOWN')})",
         f"[연결 개념] '{r['surface']}' → {r['concept'] or '미연결'}{('/' + r['subtype']) if r['subtype'] else ''} [{r['concept_kind']}], 상태 {r['assertion']}, 그래프 노드 {r['graph_node'] or '없음'}",
         f"[판단] {r['direction']} ({KO.get(r['direction'], '')})"]
    if r["graph_path"]:
        L.append("[그래프 경로] " + " ".join(r["graph_path"]))
        L.append(f"[적용 조건] {r['applicability']} / 사용한 맥락 {r['conditions_used']}")
        L += [f"[출처] {s['name'][:60]} {s['location']}: \"{s['quote'][:140]}\"" for s in r["sources"]]
    if r["clinical_context"]:
        L.append(f"[임상 단계] {r['clinical_context']['phase_after_target']} (근거 {r['clinical_context']['basis']})")
    if r["uncertainty"]:
        L.append("[불확실] " + " / ".join(r["uncertainty"]))
    if r["gaps"]:
        L.append("[추가 확인 필요] " + "; ".join(f"{g['item']}: {g['meaning']}({g['class']})" for g in r["gaps"]))
    if r["abstain_reason"]:
        L.append(f"[보류 사유] {r['abstain_reason']}")
    L.append("[주의] 판단은 확률이 아니며 의사 확인 필요")
    return "\n".join(L)


class Case:
    """사례 1개: 문서·가설·검사 사건(추가만). as_of 시점에 이용 가능한 정보만으로 맥락 추출·판단. v1 시간 정책 사용."""

    def __init__(self, case_id: str, engine: Engine | None = None):
        self.case_id, self.engine = case_id, engine or Engine()
        self.docs, self.items, self.hyps, self.tests = {}, [], [], []

    def add_document(self, d: Doc):
        self.docs[d.doc_id] = d
        self.items.append(EvidenceItem(d.doc_id, self.case_id, EvidenceKind.OTHER, d.text, Provenance("document", d.doc_id, DataClass.SYNTHETIC), observed_at=d.observed_at,
                                       available_at=d.available_at, polarity=Polarity.UNKNOWN, supersedes=d.supersedes))

    def add_hypothesis(self, h: Hypothesis):
        self.hyps.append(h)

    def add_test_event(self, test_id, event, at):
        self.tests.append(TestEvent(test_id, self.case_id, event, at, Provenance("test_event", f"{test_id}:{event}", DataClass.SYNTHETIC)))

    def state(self, as_of: float, extra_ctx: dict | None = None) -> dict:
        vis = T1.visible_evidence(self.items, as_of)
        vdocs = [self.docs[i.evidence_id] for i in vis]
        facts = [f for d in vdocs for f in CX.extract_facts(d)]
        agg = CX.aggregate(facts, as_of)
        texts = " ".join(d.text for d in vdocs)
        active = {a.assertion_id for a in T1.diagnosis_state([h.assertion(self.case_id) for h in self.hyps], as_of)}
        results = []
        for h in [x for x in self.hyps if x.hyp_id in active]:
            for d in vdocs:
                abbr = {}
                for o in vdocs:                                            # 이 문서까지 공개된 문서의 약어 정의만
                    if o.available_at is not None and d.available_at is not None and o.available_at <= d.available_at:
                        abbr.update(CP.abbreviations(o.text))
                phase_sig = sorted({f["value"] for f in facts if f["key"] == "clinical_phase_signal" and f["doc_id"] != d.doc_id and f["available_time"] is not None
                                    and d.available_at is not None and f["available_time"] <= d.available_at})
                prior_pos = any(CP.finding_state(r).get("finding") == "CTPA_REPORTS_PE" for o in vdocs if o is not d and o.available_at is not None and d.available_at is not None
                                and o.available_at <= d.available_at for r in CP.extract(o.text, o.doc_type, abbr) if r["concept"] == "PE_DIAGNOSIS" and r["role"] == "MENTION")
                ctx = {k: v for k, v in ((k, _ctx_value(agg, k)) for k in ("pretest", "suspected", "ddimer_assay", "ddimer_cutoff")) if v}
                ctx.update({"case_phase_signals": phase_sig + (["CONFIRMED_PE"] if prior_pos and h.kind != "PAST_EPISODE" else []), "evidence_observed_at": d.observed_at,
                            "evidence_available_at": d.available_at, "haemodynamic_instability": agg["haemodynamic_instability"]["value"]})
                if h.kind != "CURRENT_EVALUATION":
                    ctx["hypothesis_target"] = {"diagnosis_episode_id": h.episode_id, "kind": h.kind, "hypothesis_target_time": h.target_time}
                ctx.update(extra_ctx or {})
                for rec in CP.extract(d.text, d.doc_type, abbr):
                    r = self.engine.assess(rec, h, ctx, agg, texts)
                    r.update({"document": d.doc_id, "observed_at": d.observed_at if d.observed_at is not None else "UNKNOWN",
                              "available_at": d.available_at if d.available_at is not None else "UNKNOWN", "as_of": as_of,
                              "physician_confirmation": "CONFIRMED_IN_METADATA" if d.physician_confirmed else "UNCONFIRMED"})
                    results.append(r)
        by = {}
        for h in [x for x in self.hyps if x.hyp_id in active]:
            rs = [r for r in results if r["episode_id"] == h.episode_id and r["hypothesis"] == h.label]
            by[f"{h.label}|{h.episode_id}"] = {"status": h.status.value, "kind": h.kind, "support": sorted({r["relation_id"] for r in rs if r["direction"] == "SUPPORT"}),
                                               "weaken": sorted({r["relation_id"] for r in rs if r["direction"] == "WEAKEN"}),
                                               "held": sorted({r["relation_id"] or r["abstain_reason"] for r in rs if r["direction"] not in DIRECTIONAL and (r["relation_id"] or r["gaps"])}),
                                               "review_candidate": any(r["direction"] == "WEAKEN" for r in rs)}
        return {"as_of": as_of, "visible_documents": [d.doc_id for d in vdocs], "context": {k: (v if k not in ("pretest", "suspected", "ddimer_assay", "ddimer_cutoff", "haemodynamic_instability") else {"value": v["value"], "status": v["status"], "from": [f["doc_id"] for f in v["facts"]]}) for k, v in agg.items() if k != "unmapped"},
                "unmapped_context": [{k: f[k] for k in ("key", "value", "certainty", "doc_id")} for f in agg["unmapped"]],
                "facts": facts, "hypotheses": by, "tests": {t: T1.test_status(self.tests, t, as_of).value for t in {x.test_id for x in self.tests}}, "results": results}


def analyze_text(text: str, doc_type: str = "NOTE") -> dict:
    """기능 A 단독 실행: 문장 → 사건별 구조(개념·종류·상태·목적·결과·시점·주체·위치) + 맥락 사실."""
    d = Doc("input", text, doc_type, None, 0.0)
    abbr = CP.abbreviations(text)
    ev = []
    for r in CP.extract(text, doc_type, abbr):
        fs = CP.finding_state(r)
        ev.append({"surface": r["surface"], "concept": r["concept"], "subtype": r["subtype"], "kind": r["concept_kind"], "assertion": r["assertion"], "cue": r["cue"],
                   "test_status": {"ORDERED_NOT_RESULTED": "ORDERED", "RESULT_PENDING": "PENDING"}.get(r["assertion"], "RESULT_OR_STATEMENT" if r["concept_kind"] in ("TEST", "FINDING", "FINDING_SUBTYPE") else ""),
                   "purpose": r["assertion"] == PS.PURPOSE,
                   "temporal": ("PAST" if r["assertion"] == PS.HISTORICAL or CX.R_REL_TIME.search(r["sentence"]) else "CURRENT_OR_UNSTATED") if r["concept_kind"] not in ("TREATMENT",) else "", "subject": "OTHER_PERSON" if r["assertion"] == PS.OTHER_PERSON else "PATIENT_OR_UNSTATED",
                   "result_state": fs.get("finding", ""), "result_reason": fs.get("reason", ""), "role": r["role"], "link_status": r["link_status"], "char_span": r["char_span"],
                   "treatment_status": CX.treatment_status(r) if r["concept_kind"] == "TREATMENT" else ""})
    return {"events": ev, "facts": CX.extract_facts(d), "abbreviations": abbr}
