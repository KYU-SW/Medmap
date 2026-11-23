"""질환 지식그래프 A 와 환자 증거그래프 B.
- 정규화 관계 원본(normalized_relations)은 P2 카탈로그 + v3 덧층에서 한 번 만든다. 그래프 A 와 평면 규칙표가 같은 원본을 쓴다.
- A: 기존 EXP-01b 그래프(v3 EvidenceGraph 경유, 읽기 전용) 노드 + 결과 상태 + 관계 노드 + 조건 요구 + 출처. 연관(SUGGESTS 등)은 표시 전용.
- B: 환자·에피소드·가설·원본 기록·증거·맥락 사실·검사 사건·정정. 추가만 하고 지우지 않으며 as_of 로 조회.
EXP-01b MedGraph 는 노드·관계 종류가 고정 목록이라(원본 수정 금지) 여기서는 작은 그래프 클래스를 쓴다."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

V3 = Path(__file__).resolve().parents[2] / "hybrid_reassessment_v3"
if str(V3) not in sys.path:
    sys.path.insert(0, str(V3))

from hybrid3 import concepts as CP, context as CX  # noqa: E402
from hybrid3.kg import EvidenceGraph  # noqa: E402
from hybrid3.reasoner import Doc, Hypothesis  # noqa: E402,F401
from hybrid.schema import AssertedBy, DataClass, DiagnosisAssertion, DxStatus, EvidenceItem, EvidenceKind, Polarity, Provenance, TestEvent  # noqa: E402

from . import logic as LG  # noqa: E402

T1 = CP.P2.T1
DIR_EDGE = {"SUPPORTS_HYPOTHESIS": "SUPPORTS_HYPOTHESIS", "WEAKENS_HYPOTHESIS": "WEAKENS_HYPOTHESIS", "EVALUATES_HYPOTHESIS": "EVALUATES_HYPOTHESIS",
            "UNCERTAIN_RELATIONSHIP": "UNCERTAIN_RELATIONSHIP", "ASSOCIATED_WITH": "ASSOCIATED_WITH"}


class Graph:
    def __init__(self, name):
        self.name, self.nodes, self.out, self.inc = name, {}, {}, {}

    def node(self, nid, kind, **attrs):
        if nid in self.nodes:
            if self.nodes[nid]["kind"] != kind:
                raise ValueError(f"node kind conflict {nid}")
            self.nodes[nid].update(attrs)
            return self.nodes[nid]
        self.nodes[nid] = {"id": nid, "kind": kind, **attrs}
        self.out.setdefault(nid, [])
        self.inc.setdefault(nid, [])
        return self.nodes[nid]

    def edge(self, src, rel, dst, **attrs):
        if src not in self.nodes or dst not in self.nodes:
            raise KeyError(f"{src} -{rel}-> {dst}")
        e = {"src": src, "rel": rel, "dst": dst, **attrs}
        self.out[src].append(e)
        self.inc[dst].append(e)
        return e

    def outs(self, nid, rel=None):
        return [e for e in self.out.get(nid, []) if rel is None or e["rel"] == rel]

    def ins(self, nid, rel=None):
        return [e for e in self.inc.get(nid, []) if rel is None or e["rel"] == rel]

    def stats(self):
        from collections import Counter
        return {"nodes": len(self.nodes), "node_kinds": dict(Counter(v["kind"] for v in self.nodes.values())),
                "edges": sum(len(v) for v in self.out.values()), "edge_kinds": dict(Counter(e["rel"] for v in self.out.values() for e in v))}


# ---------------- 정규화 관계 원본 ----------------
def normalized_relations(disabled=()) -> list:
    eg = EvidenceGraph()
    cat, spec = eg.catalog, eg.spec
    ex = spec.get("exclusion_conditions", {})
    out = []
    for r in cat["relations"]:
        if r["id"] in disabled:
            continue
        extra = []
        if r["id"] in ex.get("relations", ()):
            extra.append({"cond": [LG.Atom(k, tuple(v)) for k, v in ex["when"].items()], "outcome": ex["direction"], "note": ex["note"],
                          "unknown_policy": "BLOCK_ONLY_IF_TRUE", "origin": "V3_OVERLAY_EXPLICIT_MENTION"})   # 카탈로그 필수 조건이 아님 → 미확인이면 막지 않음(v3 와 같음)
        out.append({"relation_id": r["id"], "finding": r["finding"], "result_state": f"STATE:{r['finding']}", "test_node": spec["result_states"].get(r["finding"], ""),
                    "target_diagnosis": r["hypothesis"], "relation_type": r["relation"], "structured": LG.structure(r, extra),
                    "applicability": r["applicability"], "exceptions": r.get("exceptions", ""), "requires_context": r.get("requires_context", []),
                    "sources": [{**cat["sources"][e["source"]], **{k: e[k] for k in ("location", "summary", "quote")}} for e in r["evidence"]],
                    "verification_status": r["verification"], "evidence_version": cat["catalog_version"], "catalog_path": eg.catalog_path})
    return out


def association_rows() -> list:
    """기존 그래프의 표시 전용 연관(SUGGESTS·RISK_FACTOR_FOR). 그래프 A 와 평면 규칙표 모두 같은 목록을 쓴다(방향 판단에 쓰지 않음)."""
    base = EvidenceGraph().base
    return [{"concept_node": e.src, "diagnosis": e.dst, "graph_rel": e.rel} for d in ("DX:Pulmonary embolism",) for e in base.in_edges(d) if e.rel in ("SUGGESTS", "RISK_FACTOR_FOR")] if base else []


# ---------------- 그래프 A ----------------
class DiseaseKG:
    def __init__(self, relations: list, use_base=True):
        self.eg = EvidenceGraph(use_base=use_base)
        g = self.g = Graph("disease_kg_A")
        for nid, v in self.eg.nodes.items():
            g.node(nid, v["kind"], label=v["label"], origin=v["origin"])
        base = self.eg.base
        if base:
            for d in ("DX:Pulmonary embolism",):
                for e in base.in_edges(d):
                    rel = {"SUGGESTS": "HAS_ASSOCIATED_FINDING", "RISK_FACTOR_FOR": "HAS_RISK_FACTOR", "EVALUATES": "EVALUATED_BY", "DIFFERENTIAL_OF": "DIFFERENTIAL_OF"}.get(e.rel)
                    if rel:
                        g.edge(d, rel, e.src, origin="EXP01B_GRAPH", evidence_status="ASSOCIATION_ONLY" if rel != "EVALUATED_BY" else "STRUCTURAL", used_for_direction=False, source=str(e.source)[:120])
        for sub, parent in (("PE_SUBSEGMENTAL", "DX:Pulmonary embolism"), ("DVT_PROXIMAL", "HP:0002625")):
            if parent in g.nodes:
                g.node(f"V4:SUBTYPE:{sub}", "DISEASE_SUBTYPE" if sub.startswith("PE") else "FINDING_SUBTYPE", label=sub, origin="V3_CONCEPT_SUBTYPE")
                g.edge(parent, "HAS_SUBTYPE", f"V4:SUBTYPE:{sub}", origin="V3_LEXICON", used_for_direction=False)
        for state, test in self.eg.spec["result_states"].items():
            if test in g.nodes:
                g.edge(test, "HAS_RESULT", f"STATE:{state}", origin="V3_OVERLAY")
        for r in relations:
            if r["result_state"] not in g.nodes or r["target_diagnosis"] not in g.nodes:
                continue
            rid = f"REL:{r['relation_id']}"
            g.node(rid, "EVIDENCE_RELATION", relation_id=r["relation_id"], relation_type=r["relation_type"], verification_status=r["verification_status"],
                   evidence_version=r["evidence_version"], applicability=r["applicability"], conditions=r["structured"].to_dict(), norm=r)
            g.edge(r["result_state"], "HAS_EVIDENCE_RELATION", rid)
            g.edge(rid, DIR_EDGE[r["relation_type"]], r["target_diagnosis"], verified=r["verification_status"].startswith("SOURCE_TEXT_CHECKED"))
            for k in r["requires_context"]:
                g.node(f"COND:{k}", "CLINICAL_CONTEXT_REQUIREMENT", key=k)
                g.edge(rid, "REQUIRES_CONDITION", f"COND:{k}")
            for gt in r["structured"].gates:
                for a in gt["cond"]:
                    g.node(f"COND:{a.key}", "CLINICAL_CONTEXT_REQUIREMENT", key=a.key)
                    g.edge(rid, "EXCLUDED_WHEN", f"COND:{a.key}", allowed=list(a.allowed), outcome=gt["outcome"], unknown_policy=gt["unknown_policy"])
            for s in r["sources"]:
                sid = f"SRC:{s['name'][:40]}|{s['location']}"
                g.node(sid, "EVIDENCE_SOURCE", name=s["name"], location=s["location"], quote=s["quote"], url=s.get("url", ""))
                g.edge(rid, "SUPPORTED_BY_SOURCE", sid)

    def relations_for(self, finding: str, diagnosis: str) -> list:
        """그래프 탐색: 결과 상태 → 관계 노드 → 진단. (평면 규칙표의 표 조회에 해당)"""
        st = f"STATE:{finding}"
        out = []
        for e in self.g.outs(st, "HAS_EVIDENCE_RELATION"):
            rn = self.g.nodes[e["dst"]]
            hit = [x for x in self.g.outs(e["dst"]) if x["dst"] == diagnosis and x["rel"] in DIR_EDGE.values()]
            if hit:
                test = [x["src"] for x in self.g.ins(st, "HAS_RESULT")]
                out.append({"norm": rn["norm"], "path": (test[:1] or ["?"]) + [st, e["dst"], hit[0]["rel"], diagnosis],
                            "sources_from_graph": [self.g.nodes[x["dst"]] for x in self.g.outs(e["dst"], "SUPPORTED_BY_SOURCE")]})
        return out

    def display_associations(self, concept_node: str, diagnosis: str) -> list:
        return [e for e in self.g.outs(diagnosis) if e["dst"] == concept_node and not e.get("used_for_direction", True) is True]


# ---------------- 그래프 B ----------------
FACT_KEYS = ("pretest", "suspected", "ddimer_assay", "ddimer_cutoff", "haemodynamic_instability")


@dataclass
class Episode:
    episode_id: str
    kind: str                     # CURRENT_EVALUATION / PAST_EPISODE / RECURRENCE
    label: str = ""
    target_time: float | None = None


class PatientGraph:
    """환자 1명의 증거그래프. synthetic ID 만."""

    def __init__(self, patient_id: str, synthetic: bool = True):
        if not synthetic:
            raise ValueError("이번 v4 는 합성 환자만")
        self.pid = patient_id
        self.g = Graph(f"patient_{patient_id}")
        self.g.node(patient_id, "PATIENT", synthetic=True)
        self.docs, self.items, self.tests, self.hyps, self.episodes = {}, [], [], [], {}

    def add_episode(self, ep: Episode):
        self.episodes[ep.episode_id] = ep
        self.g.node(f"EP:{ep.episode_id}", "DIAGNOSIS_EPISODE", episode_id=ep.episode_id, episode_kind=ep.kind, label=ep.label, target_time=ep.target_time)
        self.g.edge(self.pid, "HAS_EPISODE", f"EP:{ep.episode_id}")

    def add_hypothesis(self, h: Hypothesis, physician_confirmed: bool):
        """의사 Working Diagnosis. physician_confirmed=False 면 판단 대상 가설로 쓰지 않음(v1 usable_as_hypothesis)."""
        if h.episode_id not in self.episodes:
            raise KeyError(f"에피소드 없음 {h.episode_id}")
        prov = Provenance("hypothesis_event", h.hyp_id, DataClass.SYNTHETIC, physician_confirmed=physician_confirmed)
        a = DiagnosisAssertion(h.hyp_id, self.pid, h.label, h.status, h.asserted_by, h.at, prov, concept_id=h.concept, supersedes=h.supersedes)
        self.hyps.append((h, a))
        self.g.node(f"HYP:{h.hyp_id}", "WORKING_DIAGNOSIS" if physician_confirmed else "DIAGNOSIS_HYPOTHESIS_UNCONFIRMED", hyp_id=h.hyp_id, label=h.label, concept=h.concept,
                    status=h.status.value, asserted_by=h.asserted_by.value, physician_confirmed=physician_confirmed, asserted_at=h.at, usable=a.usable_as_hypothesis())
        self.g.edge(f"EP:{h.episode_id}", "HAS_HYPOTHESIS", f"HYP:{h.hyp_id}")

    def _resolve_episode(self, doc: Doc, explicit: str | None, facts: list) -> tuple:
        if explicit:
            if explicit not in self.episodes:
                raise KeyError(explicit)
            return explicit, "EXPLICIT_RECORD_METADATA"
        if len(self.episodes) == 1:
            return next(iter(self.episodes)), "SINGLE_EPISODE"
        sig = {f["value"] for f in facts if f["key"] == "clinical_phase_signal"}
        want = "RECURRENCE" if "RECURRENCE_EVALUATION" in sig else "PAST_EPISODE" if sig & {"UNDER_TREATMENT", "POST_TREATMENT_FOLLOWUP"} else None
        cand = [e for e, v in self.episodes.items() if v.kind == want] if want else []
        if len(cand) == 1:
            return cand[0], f"TEXT_SIGNAL_{want}"
        return None, "UNRESOLVED_EPISODE_LINK"

    def add_record(self, doc: Doc, episode_id: str | None = None):
        """원본 기록 추가 → v3 추출(개념·상태·결과·맥락) → 증거 노드. 기존 노드는 지우지 않는다."""
        abbr = {}
        for d in self.docs.values():
            if d.available_at is not None and doc.available_at is not None and d.available_at <= doc.available_at:
                abbr.update(CP.abbreviations(d.text))
        abbr.update(CP.abbreviations(doc.text))
        recs = CP.extract(doc.text, doc.doc_type, abbr)
        facts = CX.extract_facts(doc)
        ep, how = self._resolve_episode(doc, episode_id, facts)
        self.docs[doc.doc_id] = doc
        self.items.append(EvidenceItem(doc.doc_id, self.pid, EvidenceKind.OTHER, doc.text, Provenance("document", doc.doc_id, DataClass.SYNTHETIC, physician_confirmed=doc.physician_confirmed),
                                       observed_at=doc.observed_at, available_at=doc.available_at, polarity=Polarity.UNKNOWN, supersedes=doc.supersedes))
        rid = f"REC:{doc.doc_id}"
        self.g.node(rid, "SOURCE_RECORD", doc_id=doc.doc_id, doc_type=doc.doc_type, text=doc.text, observation_time=doc.observed_at, available_time=doc.available_at,
                    author_role=doc.author_role, diagnosis_episode_id=ep or "UNRESOLVED_EPISODE_LINK", physician_confirmation_status="CONFIRMED_IN_METADATA" if doc.physician_confirmed else "UNCONFIRMED", episode_link=how)
        self.g.edge(self.pid, "HAS_RECORD", rid)
        if doc.supersedes:
            self.g.edge(rid, "CORRECTS", f"REC:{doc.supersedes}", correction_time=doc.available_at)
        if ep:
            self.g.edge(f"EP:{ep}", "HAS_RECORD", rid, link_basis=how)
        else:
            self.g.edge(self.pid, "UNRESOLVED_EPISODE_LINK", rid)
        for i, r in enumerate(recs):
            eid = f"EV:{doc.doc_id}:{i}"
            fs = CP.finding_state(r)
            node = self._kg_node(r, fs)
            self.g.node(eid, "EVIDENCE", evidence_id=eid, patient_id=self.pid, diagnosis_episode_id=ep or "UNRESOLVED_EPISODE_LINK", concept_id=r["subtype"] or r["concept"] or "",
                        base_concept=r["concept"], kg_node=node, evidence_type=r["concept_kind"], assertion_status=r["assertion"], assertion_cue=r["cue"],
                        evidence_value=fs.get("finding") or fs.get("reason"), finding_state=fs, source_record_id=doc.doc_id, source_type="RECORD", surface=r["surface"],
                        sentence=r["sentence"], char_span=r["char_span"], observation_time=doc.observed_at if doc.observed_at is not None else "UNKNOWN",
                        available_time=doc.available_at if doc.available_at is not None else "UNKNOWN", correction_time="UNKNOWN",
                        confirmation_status="CONFIRMED_IN_METADATA" if doc.physician_confirmed else "UNCONFIRMED",
                        extraction_status=r["role"] if r["role"] != "MENTION" else r["link_status"], rec=r)
            self.g.edge(eid, "DERIVED_FROM", rid)
            self.g.edge(f"EP:{ep}" if ep else self.pid, "HAS_EVIDENCE" if ep else "UNRESOLVED_EPISODE_LINK", eid)
            if fs.get("finding"):
                tid = f"TR:{doc.doc_id}:{fs['finding']}"
                if tid not in self.g.nodes:
                    self.g.node(tid, "TEST_RESULT", result_state=fs["finding"], kg_state=f"STATE:{fs['finding']}", source_record_id=doc.doc_id)
                self.g.edge(eid, "HAS_RESULT_STATE", tid)
            if r["concept"] == "PE_DIAGNOSIS" and r["assertion"] == "PRESENT" and r["role"] == "MENTION" and r["link_status"] == "LINKED":
                cid = f"CAND:{doc.doc_id}:{i}"
                cand = DiagnosisAssertion(cid, self.pid, "Pulmonary embolism", DxStatus.WORKING_DIAGNOSIS, AssertedBy.MODEL_EXTRACTED, doc.available_at,
                                          Provenance("document", doc.doc_id, DataClass.SYNTHETIC, extractor="hybrid3.concepts"), concept_id="DX:Pulmonary embolism")
                self.g.node(cid, "AI_DIAGNOSIS_CANDIDATE", text=r["sentence"][:160], asserted_by="MODEL_EXTRACTED", physician_confirmed=False, usable_as_hypothesis=cand.usable_as_hypothesis())
                self.g.edge(eid, "SUGGESTS_CANDIDATE", cid)
        for j, f in enumerate(facts):
            fid = f"FACT:{doc.doc_id}:{j}"
            self.g.node(fid, "CONTEXT_FACT", **{k: f[k] for k in ("key", "value", "source_type", "extraction_method", "certainty", "cue", "observation_time", "available_time",
                                                                      "physician_confirmation_status")}, source_record_id=doc.doc_id, sentence=f["sentence"])
            self.g.edge(fid, "DERIVED_FROM", rid)
            self.g.edge(f"EP:{ep}" if ep else self.pid, "HAS_CONTEXT" if ep else "UNRESOLVED_EPISODE_LINK", fid)

    @staticmethod
    def _kg_node(r, fs):
        if fs.get("finding"):
            return f"STATE:{fs['finding']}"
        return CP.LX.graph_node(r["concept"]) if r["concept"] else ""

    def add_test_event(self, test_id, event, at, episode_id=None):
        self.tests.append((episode_id, TestEvent(test_id, self.pid, event, at, Provenance("test_event", f"{test_id}:{event}", DataClass.SYNTHETIC))))
        nid = f"TEV:{test_id}:{event}:{at}"
        self.g.node(nid, "TEMPORAL_EVENT", test_id=test_id, event=event, at=at)
        self.g.edge(f"EP:{episode_id}" if episode_id else self.pid, "HAS_TEST_EVENT", nid)

    # ---------- as_of 조회 ----------
    def visible_records(self, as_of: float) -> list:
        return [i.evidence_id for i in T1.visible_evidence(self.items, as_of)]

    def episode_view(self, episode_id: str, as_of: float) -> dict:
        """그래프 순회: EP -HAS_RECORD-> 기록(as_of 공개분) / EP -HAS_EVIDENCE-> 증거 / EP -HAS_CONTEXT-> 사실."""
        vis = set(self.visible_records(as_of))
        ep = f"EP:{episode_id}"
        ev = [self.g.nodes[e["dst"]] for e in self.g.outs(ep, "HAS_EVIDENCE") if self.g.nodes[e["dst"]]["source_record_id"] in vis]
        facts = [self.g.nodes[e["dst"]] for e in self.g.outs(ep, "HAS_CONTEXT") if self.g.nodes[e["dst"]]["source_record_id"] in vis]
        unresolved = [self.g.nodes[e["dst"]] for e in self.g.outs(self.pid, "UNRESOLVED_EPISODE_LINK") if self.g.nodes[e["dst"]]["kind"] == "EVIDENCE" and self.g.nodes[e["dst"]]["source_record_id"] in vis]
        superseded = [x for x in self.docs if x not in vis and any(i.supersedes == x for i in self.items if i.evidence_id in vis)]
        return {"evidence": ev, "facts": facts, "unresolved_evidence": unresolved, "visible_records": sorted(vis), "superseded_records": superseded,
                "texts": " ".join(self.docs[d].text for d in vis if any(e["dst"] == f"REC:{d}" for e in self.g.outs(ep, "HAS_RECORD")))}

    def active_hypotheses(self, as_of: float) -> list:
        act = {a.assertion_id for a in T1.diagnosis_state([a for _, a in self.hyps], as_of)}
        return [(h, a) for h, a in self.hyps if h.hyp_id in act]

    def test_states(self, episode_id, as_of):
        ev = [t for e, t in self.tests if e == episode_id]
        return {t: T1.test_status(ev, t, as_of).value for t in {x.test_id for x in ev}}

    def export_rows(self) -> dict:
        """평면 표 형태로 내보내기(평면 규칙표 기준선 입력). 같은 추출 결과."""
        return {"evidence": [v for v in self.g.nodes.values() if v["kind"] == "EVIDENCE"], "facts": [v for v in self.g.nodes.values() if v["kind"] == "CONTEXT_FACT"],
                "fact_episode": {e["dst"]: e["src"][3:] for v in self.g.out.values() for e in v if e["rel"] == "HAS_CONTEXT"}}


def aggregate_facts(facts: list) -> dict:
    """에피소드 사실 → 조건 키별 LG.Fact. 서로 다른 값이면 CONFLICT(값 버리지 않음)."""
    out = {}
    for k in FACT_KEYS:
        fs = [f for f in facts if f["key"] == k]
        vals = []
        for f in fs:
            if f["value"] not in vals:
                vals.append(f["value"])
        src = tuple(f"{f['source_record_id']}:{f['key']}" for f in fs)
        out[k] = LG.Fact(k, "FOUND", vals[0], tuple(vals), src) if len(vals) == 1 else LG.Fact(k, "CONFLICT", None, tuple(vals), src) if vals else LG.Fact(k, "NOT_FOUND")
    return out
