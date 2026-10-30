"""STEP28.5 한·영 검색기(사전 고정 규칙). 모드: KO_ONLY · EN_ONLY · PARALLEL. 구문 = extract_symptom_spans(KIWI).

[KO_ONLY] 질의 키 = 명사구 키 · 핵어 키 · query_ko 키 · (명사구 없으면) 용언 원형 키. 한국어 색인(index/korean_index.csv) 대상:
 EXACT  : 색인 키 == 질의 키
 PHRASE : 색인 키(2자 이상)가 명사구 키의 끝부분(핵어 쪽, 한국어 핵어-말미 원칙) 이거나, 질의 키가 색인 키 안에 있고 길이 ≥ 색인 키의 60%
          (STEP28 의 '짧은 입력이 긴 학습 문장 안에 있으면 근거' 규칙이 신체 부위 단독을 통과시킨 결함 → 길이 비율 조건으로 바꿈)
 NGRAM  : char 2–3gram TF-IDF 코사인 ≥ 0.6 상위 3(후보 생성 전용 — 확정·표시 안 함)
 통증+부위: pred_class PAIN 이고 핵어가 BODY_SITE 값·제품 매퍼 부위 어휘이거나, 핵어가 통증 합성어(두통·흉통·복통 …) → EXISTING_COMPOSITE(pain + E_55 값 후보)
          '목' 은 STEP28 과 같이 인후통 vs 목 통증 UNCERTAIN
 분류: EXACT/PHRASE 의 role 로 — SYMPTOM 1 개 concept → EXISTING_CANONICAL · 비증상 role(DISEASE·ANTECEDENT·TEST·HERB)만 → NON_SYMPTOM ·
       둘 다 / SYMPTOM 2 개 이상 → UNCERTAIN(CONFLICT) · BODY_SITE 만 → UNCERTAIN(BODY_PART_ONLY) · NGRAM 만 → UNCERTAIN(NGRAM_ONLY) ·
       아무것도 없음 → 증상 근거(술어 PAIN/OCCUR/OTHER 또는 STEP27 SYMPTOM_CUE) 있으면 UNKNOWN_SYMPTOM, 없으면 UNCERTAIN
       핵어에 STEP27 NON_TYPE_CUE(질환·약물·치료·검사 접미) 이고 SYMPTOM 근거 없음 → NON_SYMPTOM
 술어 분류 PAIN·OTHER(술어가 증상을 담음)면 질의 키 = 명사+술어 구문 키 하나(명사 단독 검색 안 함).
 [변경 기록] 위 줄과 색인 nkey 매칭은 smoke('목이 아파요' 가 LOINC '목' 과 맞아 NON 이 됨, '숨이 차요' 불일치)를 본 뒤 고친 일반 규칙.
 모델: STEP27 KoE top1(conf ≥ 0.953)이 KO 결과 concept 과 같으면 MODEL_AGREES 근거만 덧붙임. STEP27 POLICY_D KNOWN(B4 자동수락)은 독립 근거:
       한국어 후보가 없으면 그 concept(MODEL_AUTO), SYMPTOM 충돌이면 충돌 후보 안에 있을 때만 그것으로 해소. 입력이 구문 2개 이상이면 모델 미사용.
 충돌(CONCEPT_AMBIGUITY)이면 의미가 서로 다른 후보이므로 표시하지 않는다(지시 §9).
 [변경 기록] B4 근거·충돌 표시 금지는 smoke('토했어요' 충돌로 토혈 후보 표시)를 본 뒤 고정. 이후 규칙 변경 없음.
 제품 매퍼는 KO 근거에 넣지 않음(regex 패턴이라 용어-ID 쌍이 아니고, 구토→오심(E_148) 오매핑이 STEP28 에서 확인됨).
[EN_ONLY] 질의 키가 한·영 연결표(index/bilingual_links.csv)의 키와 완전일치할 때만 영어 쪽 concept id(EN_TERM_EXACT·ID_ANCHORED·UMLS_CUI) →
 STEP28 validate(경로 B) → DUPLICATE_OF_EXISTING → EXISTING_CANONICAL · NARROWER_AS_ATTRIBUTE → EXISTING_COMPOSITE · new_concept → NEW_ONTOLOGY_CANDIDATE ·
 NOT_SYMPTOM_TYPE / TEST·HERB → NON_SYMPTOM. 다국어 모델 경로는 gate 통과 시에만(후보, 확정 없음). 연결 없음 → BILINGUAL_BRIDGE_MISSING.
[PARALLEL] KO·EN 독립 실행 → concept 기준 통합: 같은 기존 canonical(또는 같은 CUI) → 일치(근거 둘) · 한쪽만 결과 → 그 결과(근거 하나) ·
 서로 다른 concept·범주 충돌 → UNCERTAIN(CONFLICT). 점수는 더하지 않는다(근거 등급 EXACT > PHRASE > NGRAM, 출처 수만 기록).
모든 결과: 원문·구문 위치·부정·시점·주체 그대로 전달. 표시 후보 = EXISTING 결과와 '목' 모호 후보만.
"""
from __future__ import annotations

import collections
import csv

import numpy as np

import s285_common as S
from extract_symptom_spans import extract_kiwi
from search_new_ontology_concepts import OntologyIndex
from validate_concept_candidates import existing_ids, validate

NON_ROLES = {"DISEASE", "ANTECEDENT", "TEST", "HERB"}


class Retriever:
    def __init__(self):
        import joblib
        from safe_symptom_router import SafeSymptomRouter
        self.router = SafeSymptomRouter("POLICY_D")
        self.idx = collections.defaultdict(list)
        for r in S.read_csv(S.INDEX / "korean_index.csv"):
            self.idx[r["key"]].append(r)
            if r.get("nkey") and r["nkey"] != r["key"]:
                self.idx[r["nkey"]].append(r)
        self.keys_by_len = sorted(self.idx, key=len, reverse=True)
        self.links = collections.defaultdict(list)
        for r in S.read_csv(S.INDEX / "bilingual_links.csv"):
            if r["linked_concept_ids"]:
                self.links[r["key"]].append(r)
                if r.get("nkey") and r["nkey"] != r["key"]:
                    self.links[r["nkey"]].append(r)
        ng = joblib.load(S.INDEX / "korean_ngram.joblib")
        self.vec, self.X, self.nkeys = ng["vec"], ng["X"], ng["keys"]
        self.oi = OntologyIndex(S.ONT_DB)
        self.inv = {r["canonical_id"]: r for r in S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")}
        self.ex = existing_ids(self.inv.values())
        self.bp = S.S28.body_parts()
        self.site_vals = {r["key"]: r["target_id"] for k, rs in self.idx.items() for r in rs if r["role"] == "BODY_SITE"}
        g = S.OUT / "multilingual_model_gate.json"
        self.model_path = S.load_json(g)["MODEL_PATH_ENABLED"] if g.exists() else False
        self.siglip = None
        if self.model_path:
            from evaluate_multilingual_model_gate import CACHE, Siglip
            self.siglip = Siglip()
            z = np.load(CACHE)
            self.E, self.Eids, self.Estrs = z["E"], list(z["ids"]), list(z["strs"])

    # ---------- 한국어 ----------
    def qkeys(self, sp):
        if sp["pred_class"] in ("PAIN", "OTHER"):      # 술어가 증상을 담음 → 명사(부위 등) 단독으로 검색하지 않음
            return [k for k in [S.ko_key(sp["query_ko"].removesuffix("다"))] if k]
        ks = [S.ko_key(sp["noun_phrase"]), S.ko_key(sp["head_noun"]), S.ko_key(sp["query_ko"].removesuffix("다"))]
        if not sp["noun_phrase"] and sp["predicate"]:
            ks.append(S.ko_key(sp["predicate"]))
        return [k for k in dict.fromkeys(ks) if k]

    def ko_candidates(self, sp):
        out = []
        qk = self.qkeys(sp)
        npk = S.ko_key(sp["noun_phrase"])
        for k in qk:
            out += [{**r, "tier": "EXACT", "qkey": k} for r in self.idx.get(k, [])]
        if not out:
            for ik in self.keys_by_len:
                if len(ik) < 2:
                    break
                hit = (npk and npk.endswith(ik) and len(ik) >= 2) or any(q in ik and len(q) >= 0.6 * len(ik) for q in qk)
                if hit:
                    out += [{**r, "tier": "PHRASE", "qkey": ik} for r in self.idx[ik]]
                if len(out) > 40:
                    break
        ng = []
        if not out and qk:
            v = self.vec.transform([qk[0]])
            s = (self.X @ v.T).toarray().ravel()
            for i in np.argsort(-s)[:3]:
                if s[i] >= 0.6:
                    ng += [{**r, "tier": "NGRAM", "qkey": self.nkeys[i], "ngram_cos": round(float(s[i]), 4)} for r in self.idx[self.nkeys[i]]]
        return out, ng

    def composite(self, sp):
        head = S.ko_key(sp["head_noun"])
        for comp, site in S.S28.PAIN_COMPOUND.items():
            if head.endswith(comp):
                return ("PAIN_SITE", site)
        if sp["pred_class"] != "PAIN" or not head:
            return (None, None)
        if head in ("목",):
            return ("NECK", "목")
        if head in ("목구멍", "인후", "편도"):
            return ("SORE_THROAT", head)
        if head in self.site_vals or head in self.bp:
            return ("PAIN_SITE", sp["head_noun"])
        return (None, None)

    def ko(self, sp, feats):
        kind, site = self.composite(sp)
        if kind == "PAIN_SITE":
            vals = [r["target_id"] for k, rs in self.idx.items() for r in rs if r["role"] == "BODY_SITE" and site and S.ko_key(site) in k][:12]
            return {"category": "EXISTING_COMPOSITE", "concept": "pain", "evidence": [f"PAIN+SITE:{site}"], "attributes": {"site_ko": site, "E_55_values": vals},
                    "display": ["pain"], "tiers": ["RULE"]}
        if kind == "SORE_THROAT":
            return {"category": "EXISTING_CANONICAL", "concept": "sore_throat", "evidence": ["SORE_THROAT_SITE"], "display": ["sore_throat"], "tiers": ["RULE"]}
        if kind == "NECK":
            return {"category": "UNCERTAIN", "concept": None, "evidence": ["NECK_AMBIGUOUS"], "display": ["sore_throat", "pain"], "tiers": ["RULE"]}
        cands, ng = self.ko_candidates(sp)
        sym = sorted({c["target_id"] for c in cands if c["role"] == "SYMPTOM"})
        non = sorted({f"{c['role']}:{c['target_id']}" for c in cands if c["role"] in NON_ROLES})
        site_only = cands and all(c["role"] in ("BODY_SITE", "VALUE", "ATTRIBUTE") for c in cands)
        tiers = sorted({c["tier"] for c in cands})
        nt = S.S28.non_type(sp["head_noun"]) if sp["head_noun"] else ""
        ev = [f"{c['tier']}:{c['provenance']}:{c['ko_term'][:30]}" for c in cands[:4]]
        if len(sym) == 1 and not non:
            c = sym[0]
            agree = feats and feats["koe_top1"] == c and feats["koe_conf"] >= S.S28.T_KOE
            return {"category": "EXISTING_CANONICAL", "concept": c, "evidence": ev + (["MODEL_AGREES"] if agree else []), "display": [c], "tiers": tiers}
        if non and not sym:
            return {"category": "NON_SYMPTOM", "concept": None, "evidence": non[:4], "display": [], "tiers": tiers}
        b4 = feats["b4_known"] if feats else None
        if sym:
            if b4 and b4 in sym and not non:
                return {"category": "EXISTING_CANONICAL", "concept": b4, "evidence": ev + ["CONFLICT_RESOLVED_BY_STEP27_B4"], "display": [b4], "tiers": tiers}
            return {"category": "UNCERTAIN", "concept": None, "evidence": ["CONFLICT"] + ev, "display": [], "tiers": tiers, "reason": "CONCEPT_AMBIGUITY"}
        if b4 and not cands:
            return {"category": "EXISTING_CANONICAL", "concept": b4, "evidence": ["MODEL_AUTO(STEP27_B4)"], "display": [b4], "tiers": ["MODEL"]}
        if nt and not (feats or {}).get("sym_cue"):
            return {"category": "NON_SYMPTOM", "concept": None, "evidence": [f"NON_TYPE_CUE:{nt}"], "display": [], "tiers": ["CUE"]}
        if site_only:
            return {"category": "UNCERTAIN", "concept": None, "evidence": ["BODY_PART_ONLY"], "display": [], "tiers": tiers, "reason": "BODY_PART_ONLY"}
        if ng:
            return {"category": "UNCERTAIN", "concept": None, "evidence": [f"NGRAM:{n['target_id']}:{n['ngram_cos']}" for n in ng[:3]], "display": [], "tiers": ["NGRAM"],
                    "reason": "NGRAM_ONLY", "ngram_targets": sorted({n["target_id"] for n in ng})}
        sym_ev = sp["pred_class"] in ("PAIN", "OCCUR", "OTHER") or bool((feats or {}).get("sym_cue"))
        return {"category": "UNKNOWN_SYMPTOM" if sym_ev else "UNCERTAIN", "concept": None, "evidence": [], "display": [], "tiers": [],
                "reason": "NO_KOREAN_MATCH"}

    # ---------- 영어 ----------
    def en(self, sp):
        links = [l for k in self.qkeys(sp) for l in self.links.get(k, [])]
        if not links:
            res = {"category": "UNKNOWN_SYMPTOM", "concept": None, "evidence": [], "display": [], "reason": "BILINGUAL_BRIDGE_MISSING", "validations": []}
            if self.siglip is not None and sp["query_ko"]:
                q = self.siglip.embed([sp["query_ko"]])[0]
                s = self.E @ q
                cand = [{"cid": self.Eids[i], "matched_term": self.Estrs[i], "lexical_score": round(float(s[i]), 4)} for i in np.argsort(-s)[:5]]
                vals = [validate(self.oi, c, "C", self.ex) for c in cand]
                res.update(validations=vals, reason="MODEL_CANDIDATE_ONLY")
            return res
        vals, roles = [], {l["role"] for l in links}
        if roles <= {"TEST", "HERB"}:
            return {"category": "NON_SYMPTOM", "concept": None, "evidence": [f"{l['role']}:{l['linked_concept_ids']}" for l in links[:3]], "display": [], "validations": [],
                    "en_terms": []}
        en_terms = sorted({l["en_term"] for l in links if l["en_term"]})
        for l in links:
            for cid in l["linked_concept_ids"].split(";"):
                if cid and (cid.startswith(("HP:", "SCTID:")) or cid[:1] == "C"):
                    cid = cid if cid.startswith(("HP:", "SCTID:", "CUI:")) else f"CUI:{cid}"
                    vals.append(validate(self.oi, {"cid": cid, "lexical_score": 1.0, "matched_term": l["en_term"]}, "B", self.ex))
        ex_c = sorted({v.get("existing_canonical") for v in vals if str(v["check"]).startswith("DUPLICATE_OF_EXISTING") and v.get("existing_canonical")})
        attr = sorted({v.get("existing_canonical") for v in vals if str(v["check"]).startswith("NARROWER_AS_ATTRIBUTE")})
        new = [v for v in vals if v["new_concept"]]
        wrong = [v for v in vals if str(v["check"]) == "NOT_SYMPTOM_TYPE"]
        base = {"evidence": [f"LINK:{l['link_type']}:{l['provenance']}" for l in links[:3]], "validations": vals, "en_terms": en_terms[:5]}
        if len(ex_c) == 1 and not new:
            return {**base, "category": "EXISTING_CANONICAL", "concept": ex_c[0], "display": ex_c}
        if attr and not ex_c and not new:
            return {**base, "category": "EXISTING_COMPOSITE", "concept": attr[0], "display": attr[:1]}
        if new and not ex_c:
            return {**base, "category": "NEW_ONTOLOGY_CANDIDATE", "concept": new[0]["candidate_concept_id"], "display": []}
        if wrong and not ex_c:
            return {**base, "category": "NON_SYMPTOM", "concept": None, "display": [], "reason": "SEMANTIC_TYPE_NON_SYMPTOM"}
        if len(ex_c) > 1 or (ex_c and new):
            return {**base, "category": "UNCERTAIN", "concept": None, "display": [], "reason": "CONCEPT_AMBIGUITY"}
        return {**base, "category": "UNCERTAIN", "concept": None, "display": [], "reason": "ENGLISH_RETRIEVAL_FAILURE"}

    # ---------- 통합 ----------
    def run(self, text: str, mode: str = "PARALLEL") -> list[dict]:
        spans = extract_kiwi(text)
        feats = None
        if len(spans) == 1:
            from safe_symptom_router import route
            feats = self.router.features(text)
            r27 = route(self.router.policy, feats, self.router.params)
            feats["b4_known"] = r27["canonical_id"] if r27["status"] == "KNOWN_SYMPTOM" else None
        out = []
        for sp in spans:
            meta = {k: sp.get(k, "") for k in ("span_text", "start", "end", "noun_phrase", "head_noun", "predicate", "pred_class", "query_ko", "polarity",
                                                "temporal", "subject")}
            if sp.get("failure"):
                out.append({"source_text": text, **meta, "category": "UNKNOWN_SYMPTOM", "concept": None, "display": [], "reason": "SPAN_EXTRACTION_FAILURE",
                            "evidence_ko": [], "evidence_en": [], "n_sources": 0})
                continue
            k = self.ko(sp, feats) if mode in ("KO_ONLY", "PARALLEL") else None
            e = self.en(sp) if mode in ("EN_ONLY", "PARALLEL") else None
            if mode == "KO_ONLY":
                r = k
            elif mode == "EN_ONLY":
                r = e
            else:
                kc, ec = k["category"], e["category"]
                k_ok = kc in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "NON_SYMPTOM")
                e_ok = ec in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "NON_SYMPTOM", "NEW_ONTOLOGY_CANDIDATE")
                if k_ok and e_ok:
                    same = (kc == ec and k.get("concept") == e.get("concept")) or (kc == ec == "NON_SYMPTOM") or \
                           (kc == "EXISTING_COMPOSITE" and ec in ("EXISTING_COMPOSITE", "EXISTING_CANONICAL") and e.get("concept") == "pain")
                    r = {**k, "n_sources": 2} if same else {"category": "UNCERTAIN", "concept": None, "display": [],
                                                             "reason": "CONCEPT_AMBIGUITY(KO_vs_EN)", "n_sources": 2}
                elif k_ok:
                    r = {**k, "n_sources": 1}
                elif e_ok:
                    r = {**e, "n_sources": 1}
                else:
                    r = {**k, "n_sources": 0}
                    if k["category"] == "UNKNOWN_SYMPTOM" and e.get("reason"):
                        r["reason"] = e["reason"] if e["reason"] == "BILINGUAL_BRIDGE_MISSING" else k.get("reason", "")
            out.append({"source_text": text, **meta, "category": r["category"], "concept": r.get("concept"), "attributes": r.get("attributes", {}),
                        "display": r.get("display", []), "reason": r.get("reason", ""), "evidence_ko": (k or {}).get("evidence", []),
                        "evidence_en": (e or {}).get("evidence", []), "en_terms": (e or {}).get("en_terms", []),
                        "en_validations": [{x: v.get(x) for x in ("candidate_concept_id", "concept_name", "check", "mapping_decision", "new_concept")}
                                           for v in (e or {}).get("validations", [])][:5],
                        "ko_category": (k or {}).get("category"), "en_category": (e or {}).get("category"), "en_reason": (e or {}).get("reason", ""),
                        "ko_reason": (k or {}).get("reason", ""), "ngram_targets": (k or {}).get("ngram_targets", []), "n_sources": r.get("n_sources", 1),
                        "raw_preserved": True})
        return out
