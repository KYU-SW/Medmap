"""STEP28.8 정책 P0–P5(연구용). 규칙은 평가 전 고정(2026-10-11). 원본 STEP28.5·28.7 코드는 import 만.

 P0 = STEP28.5 KO_ONLY(원본 한국어 검색)
 P1 = P0 + STEP28.6 원 대응표(A·B 통합 final_cat 그대로: 기존·신규·NON 수락, UNCERTAIN 보류) — STEP28.7 결합 규칙
 P2 = P0 + STEP28.7 정제 대응표 = STEP28.7 정책 D
 P3 = STEP28.8 수정 KO(repair_korean_matching) + 정제 대응표(같은 결합 규칙)
 P4 = P3 + 보류 우선(HELD precedence):
      정제표에서 concept 관계 보류(HOLD_CONCEPT_UNCERTAIN)·감사 비EXACT 보류(HOLD_AUDIT_NOT_EXACT) 행과 **구문 조회 키가 완전일치**하면
      긍정·미표기 구문 → status UNCERTAIN · canonical null · 표시 0 · reason AMBIGUOUS_CONCEPT_RELATION(KO 후보는 held_ko_candidate 로만 보존)
      부정 구문('무기력하지 않아요') → 같은 차단을 하지 않고 KO 결과 유지 + 확인 필요(requires_confirmation) · 모델 사용 불가 · reason HELD_RELATION_NEGATED_CONFIRM
      보류 행이 없는 구문·다른 구문에는 적용하지 않는다(문장 전체 차단 아님).
 P5 = P4 + 의미 충돌 후보 차단: 구문 조회 키의 정제표 행(보류 포함)이 가리키는 ontology concept·canonical 과 STEP28.7 ontology 관계 검사에서
      모든 id 쌍이 DISTINCT 인 기존 canonical(+ vomiting↔nausea)은 자동 연결·표시 후보에서 뺀다(자동이면 UNCERTAIN SEMANTIC_CONFLICT_BLOCKED).
결합(STEP28.7 D 와 같음): k 기존 + s 같은 canonical → k · s NON/다른 concept → UNCERTAIN · k NON + s 증상 → UNCERTAIN · k 없음 → s 결정 · s HOLD 는 k 를 덮지 않음(P4 예외).
usable_by_disease_model = 77 기존 결과 + KO 근거(EXACT·BOUNDARY·RULE·B4) + 보류·충돌 없음. SILVER 단독·신규·하위 = False.
"""
from __future__ import annotations

import collections
import json

import s288_common as S
from repair_korean_matching import RepairedRetriever
from safe_offline_retriever import ACCEPT, EXISTING, POSITIVE, SilverTable, nk

HELD_DECISIONS = ("HOLD_CONCEPT_UNCERTAIN", "HOLD_AUDIT_NOT_EXACT")
POLICIES = ("P0", "P1", "P2", "P3", "P4", "P5")


def ko_tier(o: dict) -> str:
    ev = " | ".join(o.get("evidence_ko") or [])
    if "MODEL_AUTO" in ev or "CONFLICT_RESOLVED_BY_STEP27_B4" in ev:
        return "MODEL_B4"
    if "PAIN+SITE" in ev or "SORE_THROAT_SITE" in ev or "NECK_AMBIGUOUS" in ev:
        return "RULE"
    for t in ("EXACT", "BOUNDARY", "PHRASE"):
        if f"{t}:" in ev:
            return t
    return "NONE"


def raw_table() -> SilverTable:
    """STEP28.6 원 대응표를 SilverTable 형식으로(정제 없음)."""
    grade = {r["id"]: r["grade"] for r in S.read_csv(S.S286_DIR / "outputs/new_concept_candidates.csv")}
    rows = []
    for l in S.read_csv(S.S286_DIR / "data/ontology_links.csv"):
        fc = "UNKNOWN" if grade.get(l["id"]) == "REJECTED" else l["final_cat"]
        dec = {"EXISTING_CANONICAL": "ACCEPT_EXISTING", "EXISTING_COMPOSITE": "ACCEPT_EXISTING", "NEW_ONTOLOGY_CANDIDATE": "ACCEPT_NEW_CANDIDATE",
               "NON_SYMPTOM": "ACCEPT_NON_SYMPTOM", "UNCERTAIN": "HOLD_STEP28_6_UNCERTAIN"}.get(fc, "NO_MAPPING")
        rows.append({"korean_expression": l["korean"], "normalized_korean": nk(l["korean"]), "mapping_decision": dec,
                     "canonical_id": l["final_concept"] if fc.startswith("EXISTING") else "", "ontology_id": l["final_concept"] if fc == "NEW_ONTOLOGY_CANDIDATE" else "",
                     "relation_to_existing": fc, "evidence_level": "STEP28_6_RAW", "audit_status": "", "isolation_status": "NOT_CHECKED"})
    t = SilverTable.__new__(SilverTable)
    t.rows, t.by_key, t.excluded_raw = rows, collections.defaultdict(list), None
    for r in rows:
        if r["normalized_korean"]:
            t.by_key[r["normalized_korean"]].append(r)
    return t


def distinct_map() -> dict[str, set]:
    d = S.load_json(S.S287_DIR / "outputs/priority_pair_relations.json")
    rel = collections.defaultdict(lambda: collections.defaultdict(set))
    ids = {"lethargy": "HP:0001254", "dry cough": "HP:0031246", "loose stool": "SCTID:398032003", "tremor": "HP:0001337", "hand tremor": "HP:0002378",
           "fine tremor": "SCTID:42800007", "epistaxis": "HP:0000421", "chronic cough": "HP:0034315", "tachycardia": "HP:0001649", "drowsiness": "HP:0002329",
           "high fever": "HP:0033031", "muscle fatigue": "HP:0003750", "stiffness": "SCTID:271587009", "tingling": "SCTID:62507009", "muscle cramp": "SCTID:55300003",
           "spasticity": "HP:0001257", "epigastric discomfort": "SCTID:119416008", "cold sweat": "SCTID:83547004", "collapse": "SCTID:271787007"}
    for p in d["pairs"]:
        rel[ids[p["new"]]][p["canonical"]].add(p["relation"])
    out = collections.defaultdict(set)
    for x, cs in rel.items():
        for c, rs in cs.items():
            if rs == {"DISTINCT"}:
                out[x].add(c)
    out["vomiting"].add("nausea")
    out["nausea"].add("vomiting")
    return out


class PolicyEngine:
    def __init__(self):
        self.R = RepairedRetriever()
        self.clean = SilverTable(S.S287_DIR / "data/cleaned_silver_mappings.csv")
        self.raw = raw_table()
        self.models = {r["canonical_id"] for r in S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")}
        self.concepts = {r["concept_id"]: r for r in S.read_csv(S.S287_DIR / "data/audited_concepts.csv")}
        self.held = collections.defaultdict(list)
        for r in self.clean.rows:
            if r["mapping_decision"] in HELD_DECISIONS:
                self.held[r["normalized_korean"]].append(r)
        self.span_rows = collections.defaultdict(list)    # P5: 키 → 정제표 행(보류 포함)
        for r in self.clean.rows:
            if r["mapping_decision"] != "NO_MAPPING":
                self.span_rows[r["normalized_korean"]].append(r)
        self.distinct = distinct_map()

    def keys(self, text, o, n):
        np_key = [] if o.get("pred_class") in ("PAIN", "OTHER") else [nk(o["noun_phrase"])]
        ks = ([nk(text)] if n == 1 else []) + [nk(o["span_text"])] + np_key + [nk(o["query_ko"].removesuffix("다"))]
        return [k for k in dict.fromkeys(ks) if k]

    def ko_runs(self, text):
        self.R.ko_mode = "orig"
        orig = self.R.run(text, "KO_ONLY")
        self.R.ko_mode = "repaired"
        rep = self.R.run(text, "KO_ONLY")
        return orig, rep

    def run_all(self, text) -> dict[str, list[dict]]:
        orig, rep = self.ko_runs(text)
        out = {}
        for p in POLICIES:
            base = orig if p in ("P0", "P1", "P2") else rep
            tab = None if p == "P0" else self.raw if p == "P1" else self.clean
            res = []
            for o in base:
                ks = self.keys(text, o, len(base))
                s = tab.lookup(ks) if tab else None
                r = self.combine(text, o, s, p)
                if p in ("P4", "P5"):
                    r = self.apply_held(r, o, ks)
                if p == "P5":
                    r = self.apply_distinct(r, ks)
                res.append(r)
            out[p] = res
        return out

    def apply_held(self, r, o, ks):
        hit = next((k for k in ks if k in self.held), None)
        if not hit:
            return r
        h = self.held[hit][0]
        info = {"held_key": hit, "held_decision": h["mapping_decision"], "held_ontology_id": h["ontology_id"], "held_ko_candidate": r["canonical_id"]}
        if o.get("polarity") == "NEGATIVE":
            return {**r, **info, "reason": "HELD_RELATION_NEGATED_CONFIRM", "requires_confirmation": True, "usable_by_disease_model": False}
        return {**r, **info, "status": "UNCERTAIN", "canonical_id": None, "ontology_id": None, "display": [], "safe_for_candidate_display": False,
                "model_supported": False, "usable_by_disease_model": False, "requires_confirmation": True, "reason": "AMBIGUOUS_CONCEPT_RELATION"}

    def apply_distinct(self, r, ks):
        marks = set()
        for k in ks:
            for row in self.span_rows.get(k, []):
                for x in [row["ontology_id"], row["canonical_id"]] + row.get("ontology_id", "").split(";"):
                    if x:
                        marks |= self.distinct.get(x, set())
        if not marks:
            return r
        disp = [c for c in r["display"] if c not in marks]
        if r["status"] in EXISTING and r["canonical_id"] in marks:
            return {**r, "status": "UNCERTAIN", "canonical_id": None, "display": [], "safe_for_candidate_display": False, "model_supported": False,
                    "usable_by_disease_model": False, "requires_confirmation": True, "reason": f"SEMANTIC_CONFLICT_BLOCKED({r['canonical_id']})"}
        return {**r, "display": disp, "safe_for_candidate_display": bool(disp)}

    def combine(self, text, o, s, policy):
        kc, kcon, tier = o["category"], o.get("concept"), ko_tier(o)
        sd = s["decision"] if s else None
        sc = (s or {}).get("canonical") or ""
        s_pos = sd in ("ACCEPT_EXISTING", "ACCEPT_EXISTING_SYNONYM", "ACCEPT_SUBTYPE", "ACCEPT_NEW_CANDIDATE")
        st, canon, disp, reason, evid, oid = kc, kcon, list(o.get("display") or []), o.get("reason", ""), f"KO:{tier}", None
        if kc in EXISTING:
            if s and s_pos and sc and sc == kcon:
                evid = f"KO:{tier}+SILVER"
            elif s and (sd == "ACCEPT_NON_SYMPTOM" or s_pos):
                st, canon, disp, reason, evid = "UNCERTAIN", None, [], f"KO_SILVER_CONFLICT(KO={kcon}|SILVER={sd}:{sc or s.get('ontology_id')})", f"KO:{tier}|SILVER"
        elif kc == "NON_SYMPTOM":
            if s and s_pos:
                st, canon, disp, reason, evid = "UNCERTAIN", None, [], f"KO_SILVER_CONFLICT(KO=NON|SILVER={sd})", f"KO:{tier}|SILVER"
        elif kc == "UNCERTAIN" and disp and s and sd in ("ACCEPT_EXISTING", "ACCEPT_EXISTING_SYNONYM") and sc in disp:
            st, canon, disp, reason, evid = "EXISTING_CANONICAL", sc, [sc], "AMBIGUITY_RESOLVED_BY_SILVER", f"KO:{tier}+SILVER"
        elif not kcon and not disp and s:
            row = s["row"]
            if sd in ("ACCEPT_EXISTING", "ACCEPT_EXISTING_SYNONYM"):
                st = "EXISTING_COMPOSITE" if row["relation_to_existing"] == "EXISTING_COMPOSITE" else "EXISTING_CANONICAL"
                canon, disp, reason, evid = sc, [sc], f"SILVER_{sd}", "SILVER"
            elif sd == "ACCEPT_SUBTYPE":
                st, canon, disp, reason, evid, oid = "EXISTING_SUBTYPE", sc, [], "SILVER_SUBTYPE", "SILVER", s["ontology_id"]
            elif sd == "ACCEPT_NEW_CANDIDATE":
                st, canon, disp, reason, evid, oid = "NEW_ONTOLOGY_CANDIDATE", None, [], "SILVER_NEW", "SILVER", s["ontology_id"]
            elif sd == "ACCEPT_NON_SYMPTOM":
                st, canon, disp, reason, evid = "NON_SYMPTOM", None, [], "SILVER_NON", "SILVER"
            else:
                st, canon, disp, reason, evid = "UNCERTAIN", None, [], f"SILVER_HOLD({s.get('reason')})", "SILVER"
        ms = st in EXISTING and canon in self.models
        usable = ms and evid.startswith("KO:") and "|" not in evid and tier in ("EXACT", "BOUNDARY", "RULE", "MODEL_B4", "PHRASE")
        c = self.concepts.get(oid or "", {})
        return {"source_text": text, "span_text": o["span_text"], "span_start": o.get("start"), "span_end": o.get("end"), "normalized_expression": nk(o["span_text"]),
                "status": st, "canonical_id": canon, "ontology_id": oid, "relation_to_existing": c.get("relation_to_existing") if oid else None,
                "evidence_level": (s or {}).get("evidence_level") if "SILVER" in evid else {"EXACT": "MEDMAP_VERIFIED_TERM", "BOUNDARY": "MEDMAP_VERIFIED_TERM_BOUNDARY",
                                                                                              "RULE": "MEDMAP_RULE", "MODEL_B4": "STEP27_B4", "PHRASE": "PHRASE_PARTIAL"}.get(tier),
                "isolation_status": (s or {}).get("row", {}).get("isolation_status") if s else None, "model_supported": ms, "usable_by_disease_model": bool(usable),
                "safe_for_candidate_display": bool(disp), "display": disp, "requires_confirmation": st != "NON_SYMPTOM" and not usable, "reason": reason,
                "evidence_sources": evid, "ko_tier": tier, "ko_category": kc, "ko_concept": kcon, "ko_evidence": list(o.get("evidence_ko") or []),
                "polarity": o.get("polarity"), "temporal": o.get("temporal"), "subject": o.get("subject"), "context_verified": False, "raw_preserved": True}


# RepairedRetriever 에 원본/수정 ko 선택 스위치(원본 클래스는 그대로)
_orig_ko = RepairedRetriever.__mro__[1].ko


def _ko(self, sp, feats):
    return _orig_ko(self, sp, feats) if getattr(self, "ko_mode", "repaired") == "orig" else RepairedRetriever._repaired_ko(self, sp, feats)


RepairedRetriever._repaired_ko = RepairedRetriever.ko
RepairedRetriever.ko = _ko

if __name__ == "__main__":
    import sys
    E = PolicyEngine()
    for t in sys.argv[1:]:
        for p, rs in E.run_all(t).items():
            print(p, json.dumps([(r["span_text"], r["status"], r["canonical_id"], r["ontology_id"], r["display"], r["reason"][:60]) for r in rs], ensure_ascii=False))
