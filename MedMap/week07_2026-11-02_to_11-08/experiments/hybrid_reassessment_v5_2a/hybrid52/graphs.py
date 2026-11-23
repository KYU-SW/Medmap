"""v5-1 PatientGraph5 를 상속해 확장(원본 무수정): 가설 출처, 기록 메타데이터(원본 사건·파생·완전 중복), 검사 종류.
비교 입력은 그래프 순회로만 모은다(평면표 flat.py 는 같은 정보를 행 필터로 모음). 평가는 comparator.compare_common 공용."""
from __future__ import annotations

from hybrid4 import graphs as GR
from hybrid4 import reason as RS4
from hybrid4.graphs import Hypothesis
from hybrid5 import graphs as GR5
from hybrid5 import observations as OB

from . import comparator as CMP
from . import dependency as DP
from . import hypotheses as HY

UNRES = GR5.UNRES
_LEGACY = {}


def legacy_v4(pg, as_of: float, mode: str) -> dict:
    """v4 PE 추론기(그래프/평면표 모드 각각) 결과 → {hyp_id: items}. 라벨은 comparator 가 LEGACY_V4_UNVALIDATED 로 붙임."""
    if not pg.active_hypotheses(as_of):
        return {}
    if mode not in _LEGACY:
        _LEGACY[mode] = RS4.Reasoner(GR.normalized_relations(), mode)
    r = _LEGACY[mode].evaluate(pg, as_of)
    return {hh["hyp_id"]: [{k: i.get(k) for k in ("evidence_id", "relation_id", "direction", "hold_reason")} for i in hh["items"] if i.get("relation_id")]
            for hh in r["hypotheses"]}


class PatientGraph52(GR5.PatientGraph5):
    def __init__(self, patient_id: str, patient_sex: str = "UNKNOWN"):
        super().__init__(patient_id, patient_sex)
        self.specs, self.meta, self.test_kinds = [], {}, {}

    # ---------- 입력 ----------
    def add_hypothesis_spec(self, s: HY.HypothesisSpec):
        HY.check_addition(self.specs, s)
        self.add_multi_hypothesis(s.to_multi())
        self.specs.append(s)
        self.g.nodes[f"HYP5:{s.hypothesis_id}"].update(hypothesis_source=s.hypothesis_source, is_working_diagnosis=s.is_working_diagnosis)
        if s.family == "PE":                                          # v4 레거시 PE 경로(의사 제시 가설만 v4 에서 판단 대상)
            self.add_hypothesis(Hypothesis(s.hypothesis_id, "Pulmonary embolism", s.disease_concept_id, s.evaluation_time, episode_id=s.diagnosis_episode_id),
                                s.physician_asserted)

    def add_record52(self, doc, episode_id=None, source_event_id=None, derived_from=(), exact_duplicate_of=None):
        self.add_record(doc, episode_id)
        self._meta(f"REC:{doc.doc_id}", DP.RecordMeta(doc.doc_id, source_event_id, tuple(derived_from), exact_duplicate_of))

    def add_observation52(self, o: OB.Observation, episode_id=None, source_event_id=None, derived_from=()):
        self.add_observation(o, episode_id)
        self._meta(o.obs_id, DP.RecordMeta(o.obs_id, source_event_id, tuple(derived_from)))

    def _meta(self, nid, m: DP.RecordMeta):
        self.meta[m.record_key] = m
        if m.source_event_id:
            ev = f"EVT:{m.source_event_id}"
            if ev not in self.g.nodes:
                self.g.node(ev, "SOURCE_EVENT", source_event_id=m.source_event_id)
            self.g.edge(nid, "FROM_SOURCE_EVENT", ev)
        for d in m.derived_from:
            self.g.edge(nid, "DERIVED_FROM_RECORD", self._nid(d))
        if m.exact_duplicate_of:
            self.g.edge(nid, "EXACT_DUPLICATE_OF", self._nid(m.exact_duplicate_of))

    def _nid(self, key):
        return f"REC:{key}" if f"REC:{key}" in self.g.nodes else key

    def add_test_order(self, test_id, test_kind, event, at, episode_id=None):
        self.add_test_event(test_id, event, at, episode_id)
        self.test_kinds[test_id] = test_kind
        self.g.nodes[f"TEV:{test_id}:{event}:{at}"]["test_kind"] = test_kind

    # ---------- 그래프 순회로 입력 수집 ----------
    @staticmethod
    def _key(nid):
        return nid[4:] if nid.startswith("REC:") else nid

    def _meta_from_graph(self, nid) -> DP.RecordMeta:
        ev = [self.g.nodes[e["dst"]]["source_event_id"] for e in self.g.outs(nid, "FROM_SOURCE_EVENT")]
        der = tuple(self._key(e["dst"]) for e in self.g.outs(nid, "DERIVED_FROM_RECORD"))
        dup = [self._key(e["dst"]) for e in self.g.outs(nid, "EXACT_DUPLICATE_OF")]
        return DP.RecordMeta(self._key(nid), ev[0] if ev else None, der, dup[0] if dup else None)

    def collect(self, as_of: float) -> dict:
        vis = set(self.visible_records(as_of))
        eps = {}
        for ep in sorted(self.episodes):
            inp = self.episode_inputs5(ep, as_of)
            inp["tests"] = sorted([{k: self.g.nodes[e["dst"]].get(k, "UNKNOWN") for k in ("test_id", "event", "at", "test_kind")}
                                   for e in self.g.outs(f"EP:{ep}", "HAS_TEST_EVENT")], key=lambda t: (t["test_id"], t["at"], t["event"]))
            eps[ep] = inp
        un = [self.g.nodes[e["dst"]] for e in self.g.outs(self.pid, UNRES)]
        objs = {o.obs_id: o for o in self.obs}
        unres = {"evidence": [n for n in un if n["kind"] == "EVIDENCE" and n["source_record_id"] in vis],
                 "ecg": [n for n in un if n["kind"] == "ECG_FINDING" and n["source_record_id"] in vis],
                 "obs": [o for o in OB.visible([objs[n["obs_id"]] for n in un if n["kind"] == "LAB_OBSERVATION"], as_of)
                         if o.source_record_id in vis or o.source_type == "STRUCTURED_LAB"],
                 "records": [{"record_id": n["doc_id"], "text": n["text"], "unstructured_ecg": n["ecg_other"]["unstructured_ecg_statements"]}
                             for n in un if n["kind"] == "SOURCE_RECORD" and n["doc_id"] in vis]}
        meta = {}
        for nid, n in self.g.nodes.items():
            if n["kind"] in ("SOURCE_RECORD", "LAB_OBSERVATION") and any(self.g.outs(nid, r) for r in ("FROM_SOURCE_EVENT", "DERIVED_FROM_RECORD", "EXACT_DUPLICATE_OF")):
                m = self._meta_from_graph(nid)
                meta[m.record_key] = m
        recs = [{"record_key": n["doc_id"], "record_type": n["doc_type"], "episode_id": n["diagnosis_episode_id"], "observation_time": n["observation_time"],
                 "available_time": n["available_time"], "corrects": [self._key(e["dst"]) for e in self.g.outs(nid, "CORRECTS")]}
                for nid, n in self.g.nodes.items() if n["kind"] == "SOURCE_RECORD"]
        recs += [{"record_key": n["obs_id"], "record_type": "STRUCTURED_LAB", "episode_id": n["episode_id"], "observation_time": n["observation_time"],
                  "available_time": n["available_time"], "corrects": [e["dst"] for e in self.g.outs(nid, "CORRECTS")]}
                 for nid, n in self.g.nodes.items() if n["kind"] == "LAB_OBSERVATION" and n["source_type"] == "STRUCTURED_LAB"]
        vis_obs = {o.obs_id for o in OB.visible(self.obs, as_of)}
        return {"patient_id": self.pid, "episodes": eps, "unresolved": unres, "meta": meta, "provenance": provenance(recs, vis | vis_obs, as_of)}

    def compare(self, as_of: float) -> dict:
        return CMP.compare_common(self.specs, legacy_v4(self, as_of, "graph"), self.collect(as_of), self.sex, as_of, "graph")

    def comparison_subgraph(self, result: dict) -> GR.Graph:
        """비교 결과를 가설·조건·증거 연결 그래프로 표현(비방향 간선만: EVALUATES_CRITERION, USES_INPUT)."""
        g = GR.Graph(f"comparison_{self.pid}_{result['as_of']}")
        for h in result["hypotheses"]:
            g.node(f"HYP:{h['hypothesis_id']}", "HYPOTHESIS", source=h["hypothesis_source"])
            for r in h.get("condition_evaluations", []):
                g.node(f"CRIT:{r['condition_id']}", "CRITERION_EVALUATION", result=r["evaluation_result"])
                g.edge(f"HYP:{h['hypothesis_id']}", "EVALUATES_CRITERION", f"CRIT:{r['condition_id']}")
                for i in r["input_item_ids"]:
                    if f"ITEM:{i}" not in g.nodes:
                        g.node(f"ITEM:{i}", "EVIDENCE_ITEM")
                    g.edge(f"CRIT:{r['condition_id']}", "USES_INPUT", f"ITEM:{i}")
        return g


def provenance(recs: list, visible: set, as_of: float) -> list:
    """기록별 as_of 상태(VISIBLE / NOT_YET_AVAILABLE / SUPERSEDED). 원본과 정정 관계는 보존."""
    corrected_by = {}
    for r in recs:
        for c in r["corrects"]:
            corrected_by.setdefault(c, []).append(r["record_key"])
    out = []
    for r in sorted(recs, key=lambda x: x["record_key"]):
        k = r["record_key"]
        av = r["available_time"]
        if k in visible:
            st = "VISIBLE"
        elif isinstance(av, (int, float)) and av > as_of:
            st = "NOT_YET_AVAILABLE"
        elif any(c in visible for c in corrected_by.get(k, [])):
            st = "SUPERSEDED"
        else:
            st = "NOT_VISIBLE"
        out.append({**r, "corrected_by": sorted(corrected_by.get(k, [])), "status_at_as_of": st})
    return out
