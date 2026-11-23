"""실제 실행 경로: 문장 → 언급 → 개념 연결 → 온톨로지·그래프 조회 → 관계 검증 → 맥락 확인 → 판단 → 시간 상태 → 출처 출력.
v1(공통 시간 정책)·EXP-01b 그래프·EXP-02 v3b 는 읽기 전용 호출. 확률 없음. 판단은 의사 확인 대상이다."""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from . import clinical_context as CC, evidence_conditions as EC, lexicon as LX, parser as PS, relations as RL

EXP = Path(os.environ.get("HYBRID_EXP_ROOT") or Path(__file__).resolve().parents[2])
for _p in (EXP / "hybrid_reassessment_v1", EXP / "exp03_reassessment"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from hybrid import temporal as T1  # noqa: E402
from hybrid.schema import AssertedBy, DataClass, DiagnosisAssertion, DxStatus, EvidenceItem, EvidenceKind, Polarity, Provenance, TestEvent  # noqa: E402

ABSTAIN = "ABSTAIN"
CATALOG = RL.load()
R_LEVEL_SUB = re.compile(r"\bsub-?segmental\b", re.I)
R_LEVEL_PROX = re.compile(r"\b(segmental|lobar|interlobar|main|central|saddle|proximal|bilateral pulmonary artery|right pulmonary artery|left pulmonary artery|massive)\b", re.I)
R_PARTIAL = re.compile(r"\b(central|proximal|main|lobar|large|chronic)\b", re.I)
R_DD_NORMAL = re.compile(r"\b(normal|negative|not elevated|within normal limits|unremarkable)\b", re.I)
R_DD_HIGH = re.compile(r"\b(elevated|positive|raised|high|increased)\b", re.I)
R_NUMBER = re.compile(r"\d")
R_PROX_VEIN = re.compile(r"\b(femoral|popliteal|proximal|iliac)\b", re.I)
R_DIST_VEIN = re.compile(r"\b(distal|calf|peroneal|tibial|soleal|gastrocnemius)\b", re.I)
R_NORMAL = re.compile(r"\b(normal|negative|no perfusion defects?)\b", re.I)
HX_SUPPORTED = {"PE_DIAGNOSIS", "DVT"}


def _dd_window(t: str, surface: str) -> str:
    """D-dimer 언급 앞 3단어 + 뒤로 다음 쉼표·'and' 전까지(괄호 안 기준 범위 제외)."""
    i = t.lower().find(surface.lower())
    pre = " ".join(re.split(r"[,;(]", t[:i])[-1].split()[-3:])
    post = re.split(r",|;|\band\b|\(", t[i + len(surface):])[0]
    return f"{pre} {post}"


def _v3b(sentence: str) -> str:
    from ct_bridge import classify
    return classify(sentence, "v3b")[0]


def _graph_view(concept: str, hypothesis: str) -> list:
    """그래프 간선을 읽어 보여 주기만 한다. SUGGESTS 는 ASSOCIATED_WITH 로 표시, 방향 판단에 쓰지 않는다."""
    g = LX._graph()
    n = LX.graph_node(concept)
    if not n or n not in g.nodes:
        return []
    out = []
    for e in g.out_edges(n):
        if e.dst != hypothesis:
            continue
        kind = "COOCCURRENCE" if "HSDN" in str(e.source) else "CURATED_NOT_VERIFIED"
        out.append({"src": e.src, "graph_rel": e.rel, "dst": e.dst, "v2_role": {"SUGGESTS": "ASSOCIATED_WITH", "EVALUATES": "EVALUATES_HYPOTHESIS", "RISK_FACTOR_FOR": "ASSOCIATED_WITH", "DIFFERENTIAL_OF": "DIFFERENTIAL_OF"}.get(e.rel, "NOT_USED"),
                    "source_kind": kind, "source": str(e.source)[:160], "used_for_direction": False})
    return out


def _agreement(state: str, sentence: str) -> dict:
    """동결 v3b 와 대조. 반대·불확실 의견이면 충돌로 표시(조용히 한쪽을 택하지 않음)."""
    v = _v3b(sentence)
    conflict = (state == "POS" and v in ("NEGATIVE", "UNCERTAIN", "CHRONIC_OR_PERSISTENT")) or (state == "NEG" and v in ("ACUTE_POS", "UNCERTAIN", "CHRONIC_OR_PERSISTENT"))
    return {"v3b_class": v, "conflict": conflict}


def _abbreviation_legend(s: str, start: int, end: int) -> bool:
    """P1: 'CTPA: computed tomography ...' 같은 약어 풀이는 검사 시행 근거가 아니다."""
    return bool(re.match(r"\s*[:=,]\s*(?:computed tomograph|ct pulmonary)", s[end:], re.I) or re.search(r"\b(?:ctpa|ct-pa)\s*[:=,]\s*$", s[:start], re.I))


def extract(text: str, doc_type: str = "") -> list:
    """문장에서 소견 레코드 추출. 판단 없음."""
    out = []
    ctpa_doc = doc_type == "CTPA_REPORT"
    for c in PS.split_clauses(text):
        mentions = LX.find_mentions(c.text)
        amb = LX.find_ambiguous(c.text, mentions)
        has_ctpa = ctpa_doc or any(m[3] == "CTPA_STUDY" and not _abbreviation_legend(c.sentence, m[0], m[1]) for m in LX.find_mentions(c.sentence))
        for s, e, surface, concept, kind in mentions:
            assertion, cue = PS.classify_assertion(c, s, e)
            if concept == "CTPA_STUDY" and assertion == PS.NEGATED:        # 검사 이름 자체는 부정 대상이 아님(부정은 그 결과의 소견에 적용)
                assertion, cue = PS.PRESENT, "STUDY_NAME"
            out.append({"text": c.text, "sentence": c.sentence, "section": c.section, "surface": surface, "concept": concept, "lexicon": kind, "assertion": assertion, "cue": cue, "link_status": "LINKED",
                        "graph_node": LX.graph_node(concept) if LX.graph_node(concept) in LX.lexicon()[1] else "", "codes": LX.codes(concept), "ctpa_context": has_ctpa})
        for s, e, surface, why in amb:
            if surface.lower() == "pe" and has_ctpa:                   # CTPA 맥락에서만 PE 약어 해소, 그 외는 모호 유지
                assertion, cue = PS.classify_assertion(c, s, e)
                out.append({"text": c.text, "sentence": c.sentence, "section": c.section, "surface": surface, "concept": "PE_DIAGNOSIS", "lexicon": "ABBREVIATION_IN_CTPA_CONTEXT", "assertion": assertion, "cue": cue, "link_status": "LINKED",
                            "graph_node": LX.graph_node("PE_DIAGNOSIS"), "codes": LX.codes("PE_DIAGNOSIS"), "ctpa_context": has_ctpa})
                continue
            out.append({"text": c.text, "sentence": c.sentence, "section": c.section, "surface": surface, "concept": "", "lexicon": "", "assertion": PS.classify_assertion(c, s, e)[0], "cue": why, "link_status": "AMBIGUOUS", "graph_node": "", "codes": {}, "ctpa_context": has_ctpa})
    return out


def finding_state(rec: dict) -> dict:
    """언급 레코드 → 관계 조회 키(finding). 근거 없는 추론 없음. 반환 finding 또는 abstain 사유."""
    a, concept, t = rec["assertion"], rec["concept"], rec["text"]
    if rec["link_status"] != "LINKED":
        return {"reason": "AMBIGUOUS_CONCEPT"}
    if a == PS.OTHER_PERSON:
        return {"reason": "OTHER_PERSON_NOT_PATIENT"}
    if a == PS.CONDITIONAL:
        return {"reason": "CONDITIONAL_STATEMENT"}
    if a == PS.PURPOSE:
        return {"reason": "TEST_PURPOSE_NOT_RESULT"}
    if a in (PS.ORDERED, PS.PENDING):
        return {"reason": "NO_RESULT_YET", "test_event": "ORDER" if a == PS.ORDERED else "COLLECT"}
    if a == PS.HISTORICAL:
        return {"finding": "HISTORY_PE_OR_VTE"} if concept in HX_SUPPORTED else {"reason": "HISTORICAL_FINDING"}
    if concept == "PE_DIAGNOSIS":
        if not rec["ctpa_context"]:
            return {"reason": "DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE"} if a != PS.UNCERTAIN else {"reason": "UNCERTAIN_MENTION"}
        if a == PS.UNCERTAIN:
            return {"reason": "UNCERTAIN_REPORT", "imaging": True}
        if a == PS.NEGATED:
            if R_PARTIAL.search(t):
                return {"reason": "PARTIAL_NEGATIVE_REPORT", "imaging": True}
            ag = _agreement("NEG", rec["sentence"])
            return {"finding": "CTPA_NORMAL", "v3b": ag} if not ag["conflict"] else {"reason": "EXTRACTOR_CONFLICT", "v3b": ag}
        ag = _agreement("POS", rec["sentence"])
        if ag["conflict"]:
            return {"reason": "EXTRACTOR_CONFLICT", "v3b": ag}
        level = "SUBSEGMENTAL" if R_LEVEL_SUB.search(t) else "SEGMENTAL_OR_PROXIMAL" if R_LEVEL_PROX.search(t) else None
        return {"finding": "CTPA_REPORTS_PE", "level": level, "v3b": ag}
    if concept == "FILLING_DEFECT":
        if a == PS.PRESENT and re.search(r"\b(pulmonary arter|segmental|lobar|interlobar)\w*", t, re.I):
            return {"finding": "CTPA_FILLING_DEFECT_ONLY"}
        return {"reason": "FILLING_DEFECT_SITE_OR_STATE_UNCLEAR"}
    if concept == "DDIMER":
        w = _dd_window(t, rec["surface"])                               # 해당 언급 주변만: 다른 검사의 'normal'·'elevated' 를 끌어오지 않음
        low = re.search(r"\bnot\s+(?:elevated|raised|increased)\b", w, re.I) or R_DD_NORMAL.search(w)
        high = R_DD_HIGH.search(w) and not re.search(r"\bnot\s+(?:elevated|raised|increased)\b", w, re.I)
        if low and high:
            return {"reason": "DDIMER_RESULT_CONFLICTING_TEXT"}
        if low and a in (PS.PRESENT, PS.NEGATED):
            return {"finding": "DDIMER_NORMAL"}
        if high and a == PS.PRESENT:
            return {"finding": "DDIMER_ELEVATED"}
        if R_NUMBER.search(w):
            return {"reason": "VALUE_WITHOUT_ASSAY_INTERPRETATION"}
        return {"reason": "DDIMER_RESULT_NOT_STATED"}
    if concept == "PERFUSION_SCAN":
        return {"finding": "PERFUSION_SCAN_NORMAL"} if a == PS.PRESENT and R_NORMAL.search(t) and not re.search(r"\bnot normal\b|\babnormal\b", t, re.I) else {"reason": "PERFUSION_RESULT_NOT_RELATED"}
    if concept == "DVT":
        if a == PS.PRESENT and R_PROX_VEIN.search(t) and not R_DIST_VEIN.search(t) and re.search(r"ultraso|doppler|duplex", rec["sentence"], re.I):
            return {"finding": "PROXIMAL_DVT_ON_ULTRASOUND"}
        return {"reason": "DVT_NOT_PROXIMAL_ULTRASOUND_CONFIRMED"}
    if concept in ("CTPA_STUDY", "ULTRASOUND"):
        return {"reason": "TEST_NAME_WITHOUT_RESULT"}
    return {"reason": "NO_VERIFIED_RELATION"}


def assess_record(rec: dict, hypothesis: DiagnosisAssertion, ctx: dict) -> dict:
    """소견 1건 + 가설 1개 → 출력. 관계가 없으면 ABSTAIN 이 정상."""
    norm = EC.normalize_context(ctx)                                    # P2: 출처가 인정되지 않은 임상 맥락은 None
    ctx = norm["values"]
    h = hypothesis.concept_id
    fs = finding_state(rec)
    out = {"input_sentence": rec["sentence"], "clause": rec["text"], "extracted_surface": rec["surface"], "concept": rec["concept"], "link_status": rec["link_status"], "standard_codes": rec["codes"], "graph_node": rec["graph_node"],
           "assertion": rec["assertion"], "assertion_cue": rec["cue"], "hypothesis": hypothesis.diagnosis_label, "hypothesis_status": hypothesis.status.value, "hypothesis_concept": h,
           "direction": ABSTAIN, "judgeable": False, "relation_id": "", "relation": "", "sources": [], "applicability": "", "uncertainty": [], "abstain_reason": "", "missing_context": [],
           "graph_edges_shown": _graph_view(rec["concept"], h) if rec["concept"] else [], "physician_confirmation_needed": True, "extractor_check": fs.get("v3b"), "clinical_context": None}
    out.update({"output_mode": norm["mode"], "context_provenance": norm["provenance"], "assumed_context_used": [], "hypothesis_target": ctx.get("hypothesis_target"), "test_conditions": None})
    if not hypothesis.usable_as_hypothesis():
        out["abstain_reason"] = "HYPOTHESIS_NOT_USABLE"
        return out
    if not h or h not in LX.lexicon()[1]:
        out["abstain_reason"] = "HYPOTHESIS_NOT_IN_GRAPH"
        return out
    if "finding" not in fs:
        out["abstain_reason"] = fs["reason"]
        if out["graph_edges_shown"] and fs["reason"] == "NO_VERIFIED_RELATION":
            out["abstain_reason"] = "ASSOCIATION_ONLY_NO_VERIFIED_DIRECTION"
        return out
    rel = RL.lookup(CATALOG, h, fs["finding"])
    if rel is None:
        out["abstain_reason"] = "NO_VERIFIED_RELATION_FOR_HYPOTHESIS"
        return out
    c = dict(ctx)
    if "level" in fs:
        c["level"] = fs["level"]
    tgt = {"result": None}
    if "clinical_phase" in rel.get("requires_context", ()):            # P1: 진단 알고리즘 관계는 임상 단계를 먼저 확인
        cc = CC.resolve(rec["sentence"], hypothesis.status.value, ctx)
        tgt = EC.target_check(ctx, cc["phase"])                         # P2: 가설 대상 에피소드·시점
        cc["phase_after_target"] = tgt["phase"]
        out["clinical_context"] = cc
        c["clinical_phase"] = None if tgt["phase"] == CC.UNKNOWN else tgt["phase"]   # None → 부족 맥락으로 처리(WEAKEN 안 함)
        if cc["assay"]:
            c["assay"] = cc["assay"]
    if rel["finding"] == "DDIMER_NORMAL":                              # P2: 검사법·판정 기준
        dd = EC.ddimer_conditions(rec["sentence"], ctx)
        out["test_conditions"] = dd
        c["ddimer_assay"], c["ddimer_cutoff"] = dd["assay"], dd["cutoff"]
    res = tgt["result"] or RL.apply(rel, c)
    used = {k for r in rel["by_context"] for k in r["when"]} | set(rel.get("requires_context", ()))
    if (out["clinical_context"] or {}).get("basis") == "INPUT_CONTEXT":   # 입력 의심 여부로 단계가 정해진 경우
        used |= {"suspected", "clinical_phase"}
    out["assumed_context_used"] = sorted(set(norm["assumed_keys"]) & used)
    out.update({"direction": res["direction"], "judgeable": res["direction"] != "INSUFFICIENT_EVIDENCE", "relation_id": rel["id"], "relation": rel["relation"], "applicability": rel["applicability"], "missing_context": res["missing_context"],
                "uncertainty": [x for x in (res["note"], rel.get("exceptions")) if x],
                "sources": [{**CATALOG["sources"][e["source"]], "location": e["location"], "summary": e["summary"], "quote": e["quote"], "verification": rel["verification"]} for e in rel["evidence"]]})
    return out


@dataclass
class Document:
    doc_id: str
    text: str
    doc_type: str
    observed_at: float | None
    available_at: float | None
    supersedes: str | None = None
    data_class: DataClass = DataClass.SYNTHETIC


class CaseTimeline:
    """사례 1개의 문서·가설·검사 사건(추가만). 상태는 as_of 로 계산. v1 시간 정책 사용. 의사 실제 확인 시각은 기록된 경우에만."""

    def __init__(self, case_id: str):
        self.case_id = case_id
        self.docs: dict = {}
        self.items: list = []
        self.hyps: list = []
        self.tests: list = []

    def set_hypothesis(self, assertion_id, label, concept, at, status=DxStatus.WORKING_DIAGNOSIS, supersedes=None, by=AssertedBy.SIMULATED):
        self.hyps.append(DiagnosisAssertion(assertion_id, self.case_id, label, status, by, at, Provenance("hypothesis_event", assertion_id, DataClass.SYNTHETIC), concept_id=concept, supersedes=supersedes))

    def add_test_event(self, test_id, event, at, ref=""):
        self.tests.append(TestEvent(test_id, self.case_id, event, at, Provenance("test_event", ref or f"{test_id}:{event}", DataClass.SYNTHETIC)))

    def add_document(self, doc: Document):
        self.docs[doc.doc_id] = doc
        self.items.append(EvidenceItem(doc.doc_id, self.case_id, EvidenceKind.OTHER, doc.text, Provenance("document", doc.doc_id, doc.data_class), observed_at=doc.observed_at, available_at=doc.available_at, polarity=Polarity.UNKNOWN, supersedes=doc.supersedes))

    def _case_phase_signals(self, vis: list, doc: Document) -> list:
        """P1: 이 문서 이용 시각까지 공개된 문서의 비의심 단계 신호. 나중에 공개된 문서를 소급 적용하지 않는다."""
        out = set()
        for it in vis:
            d = self.docs[it.evidence_id]
            if d is doc or d.available_at is None or doc.available_at is None or d.available_at > doc.available_at:
                continue
            for cl in PS.split_clauses(d.text):
                p = CC.sentence_signals(cl.sentence)["phase"]
                if p:
                    out.add(p)
            if any(finding_state(r).get("finding") == "CTPA_REPORTS_PE" for r in extract(d.text, d.doc_type) if r["concept"] == "PE_DIAGNOSIS"):
                out.add(CC.CONFIRMED)
        return sorted(out)

    def state(self, as_of: float, ctx: dict) -> dict:
        vis = T1.visible_evidence(self.items, as_of)
        hyps = [h for h in T1.diagnosis_state(self.hyps, as_of)]
        results = []
        for h in hyps:
            for it in vis:
                d = self.docs[it.evidence_id]
                c2 = {**ctx, "case_phase_signals": self._case_phase_signals(vis, d), "evidence_observed_at": it.observed_at, "evidence_available_at": it.available_at}
                for rec in extract(d.text, d.doc_type):
                    r = assess_record(rec, h, c2)
                    r.update({"document": it.evidence_id, "observed_at": it.observed_at, "available_at": it.available_at, "as_of": as_of})
                    results.append(r)
        by = {}
        for h in hyps:
            rs = [r for r in results if r["hypothesis"] == h.diagnosis_label]
            by[h.diagnosis_label] = {"status": h.status.value, "support": sorted({r["relation_id"] for r in rs if r["direction"] == "SUPPORT"}), "weaken": sorted({r["relation_id"] for r in rs if r["direction"] == "WEAKEN"}),
                                     "uncertain": sorted({r["relation_id"] for r in rs if r["direction"] in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE")}), "review_candidate": any(r["direction"] == "WEAKEN" for r in rs)}
        return {"as_of": as_of, "visible_documents": [i.evidence_id for i in vis], "hypotheses": by, "tests": {t: T1.test_status(self.tests, t, as_of).value for t in {x.test_id for x in self.tests}}, "results": results}
