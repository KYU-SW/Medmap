"""v4 PatientGraph 를 상속해 확장(원본 무수정): 다질환 가설(분류 축), 미확인 진단 후보, 검사 수치·시계열, ECG 소견, 정정, as_of.
그래프 순회로 에피소드 입력을 모으고, 평면표(flat.py)와 같은 공용 함수(evaluate_common)로 평가한다. 신규 방향 관계 0건."""
from __future__ import annotations

from hybrid4 import graphs as GR
from hybrid4 import reason as RS4

from . import classification as CL, concepts as CN, ecg as EC, observations as OB

UNRES = "UNRESOLVED_EPISODE_LINK"


class PatientGraph5(GR.PatientGraph):
    def __init__(self, patient_id: str, patient_sex: str = "UNKNOWN"):
        super().__init__(patient_id)
        self.sex = patient_sex
        self.obs, self.ecg, self.hyps5, self.records = [], [], [], []

    # ---------- 입력 ----------
    def add_multi_hypothesis(self, h: CN.MultiHypothesis):
        if h.episode_id not in self.episodes:
            raise KeyError(h.episode_id)
        self.hyps5.append(h)
        self.g.node(f"HYP5:{h.hyp_id}", "MULTI_DISEASE_HYPOTHESIS", **{k: getattr(h, k) for k in h.__dataclass_fields__})
        self.g.edge(f"EP:{h.episode_id}", "HAS_HYPOTHESIS", f"HYP5:{h.hyp_id}")

    def _ep_of(self, explicit):
        if explicit:
            return explicit
        return next(iter(self.episodes)) if len(self.episodes) == 1 else None

    def add_record(self, doc, episode_id=None):
        super().add_record(doc, episode_id)                                    # v4 추출·증거·사실·후보(그대로)
        rec = self.g.nodes[f"REC:{doc.doc_id}"]
        ep = rec["diagnosis_episode_id"] if rec["diagnosis_episode_id"] != UNRES else None
        ecg = EC.extract(doc.text, doc.doc_id, doc.observed_at, doc.available_at, ep or UNRES)
        self.records.append({"record_id": doc.doc_id, "text": doc.text, "episode_id": ep or UNRES, "available_time": doc.available_at, "observed_time": doc.observed_at,
                             "unstructured_ecg": ecg["unstructured_ecg_statements"]})
        spans = [f.interpretation_text for f in ecg["findings"] if f.finding_type in ("PR_DEPRESSION", "ST_DEPRESSION")]
        for nid, v in self.g.nodes.items():                                    # v3 오연결(ECG 'depression'→우울성향) 차단: 노드는 지우지 않고 표시
            if v["kind"] == "EVIDENCE" and v["source_record_id"] == doc.doc_id and v.get("base_concept") == "HP:0000716" and v["sentence"] in spans:
                v["v5_override"] = "ECG_TERM_NOT_PSYCHIATRIC(HP:0000716 오연결, 추론 제외)"
        for i, m in enumerate(CN.find_disease_mentions(doc.text)):
            st = "RECORD_HISTORY" if m["assertion"] == "HISTORICAL" else "AI_CANDIDATE_UNCONFIRMED"
            nid = f"CAND5:{doc.doc_id}:{i}"
            self.g.node(nid, "AI_DIAGNOSIS_CANDIDATE_V5", concept_id=m["concept_id"], attributes=m["attributes"], assertion=m["assertion"], diagnosis_status=st,
                        physician_confirmed=False, surface=m["surface"], sentence=m["sentence"], source_record_id=doc.doc_id, episode_id=ep or UNRES)
            self.g.edge(f"REC:{doc.doc_id}", "MENTIONS_DIAGNOSIS", nid)
        for f in ecg["findings"]:
            self.ecg.append(f)
            self.g.node(f.finding_id, "ECG_FINDING", **f.as_row())
            self.g.edge(f.finding_id, "DERIVED_FROM", f"REC:{doc.doc_id}")
            self.g.edge(f"EP:{ep}" if ep else self.pid, "HAS_ECG_FINDING" if ep else UNRES, f.finding_id)
        rec["ecg_other"] = {k: ecg[k] for k in ("rhythm", "heart_rate", "unstructured_ecg_statements")}
        for o in OB.extract(doc.text, self.pid, ep or UNRES, doc.doc_id, doc.observed_at, doc.available_at):
            self._add_obs(o, ep)

    def add_observation(self, o: OB.Observation, episode_id=None):
        """구조화 검사 자료 직접 입력(검사실 기록 등)."""
        ep = self._ep_of(episode_id)
        o.episode_id = ep or UNRES
        o.source_type = "STRUCTURED_LAB"
        self._add_obs(o, ep)

    def _add_obs(self, o, ep):
        self.obs.append(o)
        self.g.node(o.obs_id, "LAB_OBSERVATION", **o.as_row())
        if f"REC:{o.source_record_id}" in self.g.nodes:
            self.g.edge(o.obs_id, "DERIVED_FROM", f"REC:{o.source_record_id}")
        if o.supersedes:
            self.g.edge(o.obs_id, "CORRECTS", o.supersedes, correction_time=o.available_time)
        self.g.edge(f"EP:{ep}" if ep else self.pid, "HAS_OBSERVATION" if ep else UNRES, o.obs_id)

    # ---------- 그래프 순회로 입력 수집 ----------
    def episode_inputs5(self, episode_id, as_of):
        v = self.episode_view(episode_id, as_of)
        vis = set(self.visible_records(as_of))
        ep = f"EP:{episode_id}"
        ecg = [self.g.nodes[e["dst"]] for e in self.g.outs(ep, "HAS_ECG_FINDING") if self.g.nodes[e["dst"]]["source_record_id"] in vis]
        oids = [e["dst"] for e in self.g.outs(ep, "HAS_OBSERVATION")]
        obs_objs = [o for o in OB.visible([o for o in self.obs if o.obs_id in oids], as_of) if o.source_record_id in vis or o.source_type == "STRUCTURED_LAB"]
        recs = [{"record_id": self.g.nodes[e["dst"]]["doc_id"], "text": self.g.nodes[e["dst"]]["text"],
                 "unstructured_ecg": self.g.nodes[e["dst"]]["ecg_other"]["unstructured_ecg_statements"]} for e in self.g.outs(ep, "HAS_RECORD") if self.g.nodes[e["dst"]]["doc_id"] in vis]
        un_obs = [o.obs_id for o in OB.visible([o for o in self.obs if o.episode_id == UNRES], as_of) if o.source_record_id in vis or o.source_type == "STRUCTURED_LAB"]
        unres = sorted([x["evidence_id"] for x in v["unresolved_evidence"]] + un_obs + [e["dst"] for e in self.g.outs(self.pid, UNRES)
                        if self.g.nodes[e["dst"]]["kind"] == "ECG_FINDING" and self.g.nodes[e["dst"]]["source_record_id"] in vis])   # as_of 공개분만
        return {"evidence": v["evidence"], "ecg": ecg, "obs": obs_objs, "records": recs, "unresolved": unres,
                "candidates": [self.g.nodes[e["dst"]] for r in recs for e in self.g.outs(f"REC:{r['record_id']}", "MENTIONS_DIAGNOSIS")]}


def evaluate_common(hyps5: list, legacy: dict, inputs_by_ep: dict, sex: str, as_of: float, mode: str) -> dict:
    """그래프·평면표 공용: 가설별 정보 관리 + 연구용 분류. 방향 관계 없음."""
    out = {"as_of": as_of, "mode": mode, "hypotheses": [], "active_direction_relations_v5": 0}
    for h in sorted(hyps5, key=lambda x: x.hyp_id):
        if h.at > as_of:
            continue
        inp = inputs_by_ep[h.episode_id]
        ev = sorted(inp["evidence"], key=lambda x: x["evidence_id"])
        ecg = sorted(inp["ecg"], key=lambda x: x["finding_id"])
        obs = sorted(inp["obs"], key=lambda x: x.obs_id)
        series = OB.build_series(obs, as_of, sex)
        row = {k: getattr(h, k) for k in h.__dataclass_fields__} | {
            "evaluation_status": "INFORMATION_MANAGED_NO_ACTIVE_RELATION", "supporting_evidence_ids": [], "weakening_evidence_ids": [],
            "linked_evidence_ids": [x["evidence_id"] for x in ev if not x.get("v5_override")] + [x["finding_id"] for x in ecg] + [o.obs_id for o in obs],
            "excluded_by_v5_override": [x["evidence_id"] for x in ev if x.get("v5_override")], "unresolved_episode_link_ids": inp["unresolved"],
            "ai_candidates_unconfirmed": [{k: c[k] for k in ("concept_id", "attributes", "assertion", "diagnosis_status", "surface", "source_record_id")} for c in sorted(inp["candidates"], key=lambda c: (c["source_record_id"], c["surface"]))],
            "series": series, "ecg_findings": [{k: f[k] for k in ("finding_id", "finding_type", "assertion_status", "lead_or_distribution", "numeric_measurement", "certainty",
                                                                  "temporal_context", "reciprocal_change_reported", "notes")} for f in ecg],
            "unsupported_ecg_statements": [u for r in sorted(inp["records"], key=lambda r: r["record_id"]) for u in r.get("unstructured_ecg", [])], "classifications": []}
        fam = CN.CONCEPTS[h.concept_id]["family"]
        if fam == "PERICARDIAL":
            facts = CL.criterion_facts_pericarditis(ev, ecg, [o.as_row() for o in obs], inp["records"])
            row["classifications"].append(CL.pericarditis_classification(facts, h.episode_id, as_of))
        if fam in ("ACS", "MI", "INJURY"):
            facts = CL.criterion_facts_injury(series, inp["records"])
            row["classifications"].append(CL.injury_classification(facts, series, h.episode_id, as_of))
        if fam == "PE" and h.hyp_id in legacy:
            row["legacy_v4"] = {"label": "LEGACY_V4(전문의 검토 전, v5 검증 결과 아님)", "items": legacy[h.hyp_id]}
        out["hypotheses"].append(row)
    return out


class Reasoner5:
    def __init__(self):
        self.legacy = RS4.Reasoner(GR.normalized_relations(), "graph")

    def evaluate(self, pg: PatientGraph5, as_of: float) -> dict:
        eps = {h.episode_id for h in pg.hyps5}
        inputs = {e: pg.episode_inputs5(e, as_of) for e in eps}
        legacy = {}
        for h4 in pg.active_hypotheses(as_of):                                     # v4 PE 가설은 그대로 v4 엔진(레거시 라벨)
            r = self.legacy.evaluate(pg, as_of)
            for hh in r["hypotheses"]:
                legacy[hh["hyp_id"]] = [{k: i.get(k) for k in ("evidence_id", "relation_id", "direction", "hold_reason")} for i in hh["items"] if i.get("relation_id")]
            break
        return evaluate_common(pg.hyps5, legacy, inputs, pg.sex, as_of, "graph")
