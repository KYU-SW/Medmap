"""STEP28.7 안전 오프라인 증상 검색기(연구용, production 아님). LLM·외부 API·네트워크 없음. 규칙은 평가 실행 전 고정(2026-10-11).

정책 D(STEP28.7 cleaned & safety-gated) — 구문(STEP28.5 kiwipiepy 추출)마다:
 k = STEP28.5 한국어 검색(KO_ONLY: 77 한국어 색인 EXACT → PHRASE, 통증+부위 규칙, '목' 모호, STEP27 B4 모델 자동수락) — 1·2·3 단계(기존 canonical·속성 조합·검증된 동의어)
 s = STEP28.7 정제 SILVER 대응표(data/cleaned_silver_mappings.csv) 조회 — 4·5·6 단계(이미 ontology 관계 검증·concept 분류가 붙어 있음)
   조회 키(순서, 처음 걸린 키만): 입력 전체(구문 1개일 때) · 구문 · 명사구 · 질의 — 모두 ko_key(stem_key(·)) **완전일치**(부분·유사 일치 없음).
   같은 키 행이 여럿이면 ACCEPT_* 결정만 모아 (결정, 대상) 이 하나일 때만 사용, 둘 이상이면 SILVER_KEY_CONFLICT → 보류(HOLD).
   ACCEPT 없이 HOLD·REJECT 만 있으면 HOLD, 전부 NO_MAPPING 이면 없음.
 결합(점수 비교 없음 — 근거 종류 규칙만):
  1 k 가 EXISTING_*(기존):  s 없음·HOLD → k · s 가 같은 canonical(동의어·하위 포함) → k(+SILVER 일치 기록, 하위면 subtype ontology id 를 속성으로 보존) ·
    s 가 NON · 다른 canonical · 신규 concept → UNCERTAIN(KO_SILVER_CONFLICT, 표시 없음)
  2 k 가 NON_SYMPTOM:       s 가 증상(기존·하위·신규) → UNCERTAIN(KO_SILVER_CONFLICT) · 그 외 → NON_SYMPTOM
  3 k 가 '목' 모호(표시 2개): s 가 표시 후보 중 하나의 기존 canonical → 그 canonical · 그 외 → k
  4 k 에 concept 없음(UNKNOWN_SYMPTOM·UNCERTAIN): s 로 결정 —
    ACCEPT_EXISTING → EXISTING_CANONICAL/COMPOSITE(SILVER 단독, 확인 필요) · ACCEPT_EXISTING_SYNONYM → EXISTING_CANONICAL(확인 필요) ·
    ACCEPT_SUBTYPE → EXISTING_SUBTYPE(canonical = 부모, 모델 미지원) · ACCEPT_NEW_CANDIDATE → NEW_ONTOLOGY_CANDIDATE(모델 미지원, 표시 없음) ·
    ACCEPT_NON_SYMPTOM → NON_SYMPTOM · HOLD → UNCERTAIN(SILVER_HOLD, 표시 없음) · 없음 → k 그대로(UNKNOWN_SYMPTOM / UNCERTAIN, 원문 보존)
 표시(display): 77 기존 canonical 만(EXISTING_* 결과와 '목' 모호). 신규·하위·보류·충돌은 표시 0.
 model_supported = 결과 canonical 이 77 이고 상태가 EXISTING_CANONICAL/COMPOSITE. usable_by_disease_model = model_supported 이고 근거가 MedMap 검증
 한국어 용어·규칙(EXACT/RULE) 또는 STEP27 B4(기존 경로)일 때만 — SILVER 단독 결과·신규·하위는 항상 False(49질환 모델 자동 반영 금지).
 부정·시점·주체는 STEP28.5 추출값을 그대로 전달(검증 안 됨, STEP29 범위).
비교 정책(같은 인터페이스): A = STEP27 POLICY_D(B4) · B = STEP28 Expansion · C = STEP28.6 대응표 조회(입력 전체 ko_key 완전일치, 표 밖 = UNKNOWN(LLM 필요)) ·
 D = 위 · D_NO_TABLE = D 에서 s 끔(= STEP28.5 KO_ONLY) · D_LOO = 입력과 같은 원문 행을 표에서 뺀 D(처음 보는 표면형 근사).
"""
from __future__ import annotations

import collections

import s287_common as S

EXISTING = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")
POSITIVE = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "EXISTING_SUBTYPE", "NEW_ONTOLOGY_CANDIDATE")
ACCEPT = ("ACCEPT_EXISTING", "ACCEPT_EXISTING_SYNONYM", "ACCEPT_SUBTYPE", "ACCEPT_NEW_CANDIDATE", "ACCEPT_NON_SYMPTOM")


def nk(s: str) -> str:
    return S.ko_key(S.stem_key(s or ""))


class SilverTable:
    def __init__(self, path=None):
        self.rows = S.read_csv(path or S.DATA / "cleaned_silver_mappings.csv")
        self.by_key = collections.defaultdict(list)
        for r in self.rows:
            if r["normalized_korean"]:
                self.by_key[r["normalized_korean"]].append(r)
        self.excluded_raw: str | None = None          # D_LOO: 이 원문(ko_key)과 같은 행 제외

    def lookup(self, keys: list[str]) -> dict | None:
        for k in keys:
            rs = [r for r in self.by_key.get(k, []) if not (self.excluded_raw and S.ko_key(r["korean_expression"]) == self.excluded_raw)]
            if not rs:
                continue
            acc = [r for r in rs if r["mapping_decision"] in ACCEPT]
            if acc:
                tgt = {(r["mapping_decision"], r["canonical_id"], r["ontology_id"]) for r in acc}
                if len(tgt) == 1:
                    r = acc[0]
                    lv = sorted({x["evidence_level"] for x in acc})[-1]
                    return {"decision": r["mapping_decision"], "canonical": r["canonical_id"], "ontology_id": r["ontology_id"], "row": r, "key": k,
                            "evidence_level": lv, "n_rows": len(rs)}
                return {"decision": "HOLD", "reason": "SILVER_KEY_CONFLICT", "key": k, "row": acc[0], "evidence_level": "LEVEL_1", "n_rows": len(rs)}
            if any(r["mapping_decision"] != "NO_MAPPING" for r in rs):
                r = next(r for r in rs if r["mapping_decision"] != "NO_MAPPING")
                return {"decision": "HOLD", "reason": r["mapping_decision"], "key": k, "row": r, "evidence_level": r["evidence_level"], "n_rows": len(rs)}
            return None
        return None


def ko_tier(o: dict) -> str:
    ev = " | ".join(o.get("evidence_ko") or [])
    if "MODEL_AUTO" in ev or "CONFLICT_RESOLVED_BY_STEP27_B4" in ev:
        return "MODEL_B4"
    if "PAIN+SITE" in ev or "SORE_THROAT_SITE" in ev or "NECK_AMBIGUOUS" in ev:
        return "RULE"
    if "EXACT:" in ev:
        return "EXACT"
    if "PHRASE:" in ev:
        return "PHRASE"
    return "NONE"


class SafeOfflineRetriever:
    def __init__(self, use_table: bool = True):
        from bilingual_retriever import Retriever
        self.R = Retriever()
        self.table = SilverTable() if use_table else None
        self.ont_names = {}
        self.models = {r["canonical_id"] for r in S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")}
        self.concepts = {r["concept_id"]: r for r in S.read_csv(S.DATA / "audited_concepts.csv")}

    def _keys(self, text, o, n_spans):
        # [변경 기록 — 평가 전 기능 점검(§14 예시 문장)] '머리가 아파' 의 명사구 '머리'(신체 부위 NON 행)가 통증 구문을 막음 →
        #  STEP28.5 qkeys 와 같은 규칙: 술어가 증상을 담으면(PAIN·OTHER) 명사구 단독 키를 쓰지 않는다.
        np_key = [] if o.get("pred_class") in ("PAIN", "OTHER") else [nk(o["noun_phrase"])]
        ks = ([nk(text)] if n_spans == 1 else []) + [nk(o["span_text"])] + np_key + [nk(o["query_ko"].removesuffix("다"))]
        return [k for k in dict.fromkeys(ks) if k]

    def run(self, text: str) -> list[dict]:
        ko = self.R.run(text, "KO_ONLY")
        out = []
        for o in ko:
            s = self.table.lookup(self._keys(text, o, len(ko))) if self.table else None
            out.append(self.combine(text, o, s))
        return out

    def combine(self, text, o, s):
        kc, kcon, tier = o["category"], o.get("concept"), ko_tier(o)
        sd = s["decision"] if s else None
        st_canon = (s or {}).get("canonical") or ""
        s_pos = sd in ("ACCEPT_EXISTING", "ACCEPT_EXISTING_SYNONYM", "ACCEPT_SUBTYPE", "ACCEPT_NEW_CANDIDATE")
        res = {"status": kc, "canonical_id": kcon, "display": list(o.get("display") or []), "reason": o.get("reason", ""), "evidence": f"KO:{tier}",
               "ontology_id": None, "subtype_ontology_id": None, "evidence_level": None, "audit_status": None, "isolation_status": None}
        if kc in EXISTING:
            if s and s_pos and st_canon and st_canon == kcon:
                res.update(evidence=f"KO:{tier}+SILVER", subtype_ontology_id=s["ontology_id"] if sd == "ACCEPT_SUBTYPE" else None)
            elif s and (sd == "ACCEPT_NON_SYMPTOM" or s_pos):
                res.update(status="UNCERTAIN", canonical_id=None, display=[], reason=f"KO_SILVER_CONFLICT(KO={kc}:{kcon}|SILVER={sd}:{st_canon or s.get('ontology_id')})",
                           evidence=f"KO:{tier}|SILVER")
        elif kc == "NON_SYMPTOM":
            if s and s_pos:
                res.update(status="UNCERTAIN", canonical_id=None, display=[], reason=f"KO_SILVER_CONFLICT(KO=NON|SILVER={sd})", evidence=f"KO:{tier}|SILVER")
        elif kc == "UNCERTAIN" and res["display"] and s and sd in ("ACCEPT_EXISTING", "ACCEPT_EXISTING_SYNONYM") and st_canon in res["display"]:
            res.update(status="EXISTING_CANONICAL", canonical_id=st_canon, display=[st_canon], reason="AMBIGUITY_RESOLVED_BY_SILVER", evidence=f"KO:{tier}+SILVER")
        elif not kcon and not res["display"] and s:
            row = s["row"]
            if sd in ("ACCEPT_EXISTING", "ACCEPT_EXISTING_SYNONYM"):
                cat = "EXISTING_COMPOSITE" if row["relation_to_existing"] == "EXISTING_COMPOSITE" else "EXISTING_CANONICAL"
                res.update(status=cat, canonical_id=st_canon, display=[st_canon], reason=f"SILVER_{sd}", evidence="SILVER")
            elif sd == "ACCEPT_SUBTYPE":
                res.update(status="EXISTING_SUBTYPE", canonical_id=st_canon, display=[], reason="SILVER_SUBTYPE", evidence="SILVER", ontology_id=s["ontology_id"])
            elif sd == "ACCEPT_NEW_CANDIDATE":
                res.update(status="NEW_ONTOLOGY_CANDIDATE", canonical_id=None, display=[], reason="SILVER_NEW", evidence="SILVER", ontology_id=s["ontology_id"])
            elif sd == "ACCEPT_NON_SYMPTOM":
                res.update(status="NON_SYMPTOM", canonical_id=None, display=[], reason="SILVER_NON", evidence="SILVER")
            else:
                res.update(status="UNCERTAIN", canonical_id=None, display=[], reason=f"SILVER_HOLD({s.get('reason')})", evidence="SILVER")
        if s:
            r = s["row"]
            res.update(evidence_level=s["evidence_level"], audit_status=r["audit_status"], isolation_status=r["isolation_status"], silver_key=s["key"],
                       silver_decision=sd)
        oid = res["ontology_id"] or res["subtype_ontology_id"]
        c = self.concepts.get(oid or "", {})
        ms = res["status"] in EXISTING and res["canonical_id"] in self.models
        usable = ms and (res["evidence"].startswith("KO:") and tier in ("EXACT", "RULE", "MODEL_B4"))
        return {"source_text": text, "span_text": o["span_text"], "span_start": o.get("start"), "span_end": o.get("end"),
                "normalized_expression": nk(o["span_text"]), "status": "UNKNOWN_SYMPTOM" if res["status"] == "UNKNOWN_SYMPTOM" else res["status"],
                "canonical_id": res["canonical_id"], "ontology_id": oid, "ontology_source": c.get("ontology_source"),
                "concept_name": c.get("preferred_label") if c and not c.get("snomed_only") in ("True", True) else (oid and "SNOMED(LOCAL_ONLY)"),
                "relation_to_existing": c.get("relation_to_existing") if oid else ("EXISTING" if res["status"] in EXISTING else None),
                "evidence_level": res["evidence_level"] or ("MEDMAP_VERIFIED_TERM" if tier in ("EXACT", "RULE") else "STEP27_B4" if tier == "MODEL_B4"
                                                            else "PHRASE_PARTIAL" if tier == "PHRASE" else None),
                "audit_status": "SILVER" if res["evidence"] != f"KO:{tier}" else None, "silver_audit": res["audit_status"],
                "isolation_status": res["isolation_status"], "model_supported": ms, "usable_by_disease_model": bool(usable),
                "safe_for_candidate_display": bool(res["display"]), "display": res["display"],
                "requires_confirmation": res["status"] not in ("NON_SYMPTOM",) and not usable,
                "reason": res["reason"], "evidence_sources": res["evidence"], "ko_category": kc, "ko_concept": kcon, "ko_tier": tier,
                "polarity": o.get("polarity"), "temporal": o.get("temporal"), "subject": o.get("subject"), "context_verified": False, "raw_preserved": True}


# ---------------- 비교 정책(같은 출력 모양) ----------------
class PolicyA:
    """STEP27 POLICY_D(B4)."""
    def __init__(self, router=None):
        from safe_symptom_router import SafeSymptomRouter
        self.r = router or SafeSymptomRouter("POLICY_D")

    def run(self, text):
        o = self.r(text)
        st = {"KNOWN_SYMPTOM": "EXISTING_CANONICAL", "COMPLEX_INPUT": "UNCERTAIN"}.get(o["status"], o["status"])
        return [{"source_text": text, "status": st, "canonical_id": o["canonical_id"], "ontology_id": None, "display": list(o.get("candidate_ids") or []),
                 "reason": o.get("reason", ""), "raw_preserved": True, "usable_by_disease_model": st == "EXISTING_CANONICAL"}]


class PolicyB:
    """STEP28 Expansion(경로 C 비활성)."""
    def __init__(self):
        from evaluate_expansion import Expansion
        self.e = Expansion()

    def run(self, text):
        o = self.e(text)
        st = {"NEW_ONTOLOGY_CONCEPT": "NEW_ONTOLOGY_CANDIDATE"}.get(o["category"], o["category"])
        return [{"source_text": text, "status": st, "canonical_id": o["canonical_id"], "ontology_id": (o.get("ontology_ids") or [None])[0] if st == "NEW_ONTOLOGY_CANDIDATE" else None,
                 "display": list(o.get("display") or []), "reason": o.get("reason", ""), "raw_preserved": o.get("raw_preserved", True),
                 "usable_by_disease_model": st in EXISTING}]


class PolicyC:
    """STEP28.6 대응표 조회(런타임 = 표에 있는 표현만). 입력 전체 ko_key 완전일치, 표 밖 → UNKNOWN_SYMPTOM(LLM_REQUIRED)."""
    def __init__(self):
        self.by = collections.defaultdict(list)
        ev ={r["id"]: r for r in S.read_csv(S.S286_DIR / "data/ontology_links.csv")}
        gr = {}
        for r in S.read_csv(S.S286_DIR / "outputs/new_concept_candidates.csv"):
            gr[r["id"]] = r["grade"]
        for i, r in ev.items():
            fc = "UNKNOWN" if gr.get(i) == "REJECTED" else r["final_cat"]
            self.by[S.ko_key(r["korean"])].append((fc, r["final_concept"]))

    def run(self, text):
        hits = self.by.get(S.ko_key(text))
        if not hits:
            return [{"source_text": text, "status": "UNKNOWN_SYMPTOM", "canonical_id": None, "ontology_id": None, "display": [], "reason": "NOT_IN_TABLE(LLM_REQUIRED)",
                     "raw_preserved": True, "usable_by_disease_model": False}]
        fc, con = hits[0]
        st = {"UNKNOWN": "UNKNOWN_SYMPTOM"}.get(fc, fc)
        return [{"source_text": text, "status": st, "canonical_id": con if st in EXISTING else None, "ontology_id": con if st == "NEW_ONTOLOGY_CANDIDATE" else None,
                 "display": [con] if st in EXISTING else [], "reason": "STEP28_6_TABLE", "raw_preserved": True, "usable_by_disease_model": st in EXISTING}]


if __name__ == "__main__":
    import sys
    R = SafeOfflineRetriever()
    for t in sys.argv[1:] or ["코피가 나요", "어제부터 코피가 나고 머리가 아파요. 열은 없어요."]:
        for x in R.run(t):
            print(S.dumps({k: x[k] for k in ("span_text", "status", "canonical_id", "ontology_id", "evidence_level", "display", "reason", "polarity",
                                              "model_supported", "usable_by_disease_model", "requires_confirmation")}))
