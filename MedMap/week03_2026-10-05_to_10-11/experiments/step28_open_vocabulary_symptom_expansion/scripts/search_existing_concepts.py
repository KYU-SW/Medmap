"""STEP28 기존 증상 검색(77 canonical + 속성 조합). 기존 모델·정책·제품 매퍼는 고정·read-only 로 호출만 한다.

검색 순서(s28_common 문서열 0–5 단계와 같음):
 COMPLEX → 통증+부위(EXISTING_COMPOSITE) → 한국어 용어 완전일치(EXACT_TERM) → STEP27 POLICY_D KNOWN(MODEL_AUTO)
 → 제품 매퍼 alias(PRODUCT_ALIAS) / KoE ≥ T_KOE + 어휘 근거(MODEL_LEXICAL) → 비증상 근거(NON) → 미해결(상위 단계로 넘김)
한국어 용어(77 concept 별): STEP23 학습 표현 1,119 · STEP21 사전 294 · terminology_ko evidence_short 라벨(crosswalk 87 증거, '·' 로 분리).
어휘 근거 lexical_support(text, c): 입력 stem(조사 제거, 공백 제거, 2자 이상)이 c 의 용어 stem 과 같거나 그 안에 있거나,
  c 의 짧은 용어(2–6자, 용어집 라벨·사전 라벨) 가 입력 안에 있다. 모델 출력만으로는 기존 concept 확정 안 함.
"""
from __future__ import annotations

import collections
import json
import re

import s28_common as S

S.sys.path.insert(0, str(S.REPO))
from medmap.intake.mapper import IntakeMapper  # noqa: E402  (worktree = master fb2d7f0 와 같은 코드, read-only)

EVID_JSON = S.MAIN / "data/ddxplus/en/release_evidences.json"


def ns_stem(text: str) -> str:
    return S.nospace(S.josa_strip(S.norm(text)))


class ExistingSearch:
    def __init__(self, router=None):
        from safe_symptom_router import SafeSymptomRouter
        self.router = router or SafeSymptomRouter("POLICY_D")
        self.cw = S.evidence_crosswalk()
        self.ev = json.loads(EVID_JSON.read_text(encoding="utf-8"))
        self.term = S.load_terminology()
        self.mapper = IntakeMapper(evidences_json=str(EVID_JSON))
        self.terms = collections.defaultdict(set)      # canonical → stem 집합
        self.short = collections.defaultdict(set)      # canonical → 짧은 용어(2–6자)
        for r in S.read_csv(S.S23 / "data/expanded_train_expressions.csv"):
            self.terms[r["canonical_id"]].add(ns_stem(r["expression"]))
        for r in S.read_csv(S.S21 / "data/dictionary_expressions.csv"):
            st = ns_stem(r["expression"])
            self.terms[r["concept_id"]].add(st)
            if 2 <= len(st) <= 6:
                self.short[r["concept_id"]].add(st)
        for e, c in self.cw.items():
            lab = self.term["evidence_short"].get(e, {}).get("label_ko", "")
            for part in re.split(r"[·,/()]", lab):
                st = ns_stem(part)
                if st:
                    self.terms[c].add(st)
                    if 2 <= len(st) <= 6:
                        self.short[c].add(st)
        self.stem_index = collections.defaultdict(set)
        for c, ss in self.terms.items():
            for st in ss:
                self.stem_index[st].add(c)
        self.disease_ko = {ns_stem(v["label_ko"]): k for k, v in self.term["diseases"].items() if v.get("label_ko")}
        self.bp = S.body_parts()
        e55 = self.ev["E_55"]["possible-values"]
        self.site_values = {v: self.term["values"].get(v, {}).get("label_ko", "") for v in e55}

    # ---- 어휘 근거 ----
    def lexical_support(self, text: str, c: str) -> bool:
        st = ns_stem(text)
        if len(st) < 2:
            return st in self.terms.get(c, ())
        if st in self.terms.get(c, ()) or any(st in t for t in self.terms.get(c, ())):
            return True
        x = S.nospace(S.norm(text))
        return any(s in x for s in self.short.get(c, ()))

    def site_candidates(self, site: str) -> list[str]:
        return [v for v, lab in self.site_values.items() if site and site in lab][:12]

    def composite(self, text: str):
        x = S.nospace(S.norm(text))
        for comp, site in sorted(S.PAIN_COMPOUND.items(), key=lambda kv: -len(kv[0])):
            if comp in x:
                if comp == "경부통":
                    return "AMBIGUOUS_NECK", site
                return "PAIN_SITE", site
        if not S.PAIN_MORPH.search(S.norm(text)):
            return None, None
        if S.SORE_THROAT_SITE.search(S.norm(text)):
            return "SORE_THROAT", "목구멍"
        if S.NECK_SITE.search(S.norm(text)):
            return "PAIN_SITE", "뒷목"
        for b in self.bp:
            if b in x:
                if b == "목":
                    return "AMBIGUOUS_NECK", "목"
                if b in ("속",):
                    continue
                return "PAIN_SITE", b
        return None, None

    def search(self, text: str) -> dict:
        ev = []
        from safe_symptom_router import route
        feats = self.router.features(text)
        r27 = route(self.router.policy, feats, self.router.params)
        mp = self.mapper.extract(text)
        ev.append({"source": "STEP27_POLICY_D", "status": r27["status"], "canonical": r27["canonical_id"], "candidates": r27["candidate_ids"]})
        ev.append({"source": "PRODUCT_MAPPER", "hits": [(m["evidence_id"], m["status"]) for m in mp]})
        base = {"source_text": text, "router": r27, "features": {k: feats[k] for k in ("lin_top1", "koe_top1", "koe_conf", "agree", "p_non", "sym_cue", "non_type")},
                "mapper": mp, "evidence": ev}
        if feats["complex"]:
            return {**base, "category": "UNCERTAIN", "reason": "COMPLEX_INPUT:" + ";".join(feats["complex_flags"]), "canonical_id": None, "display": []}
        # 1 통증 + 부위
        kind, site = self.composite(text)
        if kind == "PAIN_SITE":
            return {**base, "category": "EXISTING_COMPOSITE", "reason": "PAIN_PLUS_SITE", "canonical_id": "pain",
                    "attributes": {"site_ko": site, "E_55_value_candidates": self.site_candidates(site)}, "display": ["pain"]}
        if kind == "SORE_THROAT":
            return {**base, "category": "EXISTING_CANONICAL", "reason": "SORE_THROAT_SITE_RULE", "canonical_id": "sore_throat", "display": ["sore_throat"]}
        if kind == "AMBIGUOUS_NECK":
            return {**base, "category": "UNCERTAIN", "reason": "NECK_SITE_AMBIGUOUS(sore_throat vs pain+neck)", "canonical_id": None,
                    "display": ["sore_throat", "pain"], "attributes": {"pain_site_ko": "목"}}
        # 2 용어 완전일치
        hit = self.stem_index.get(ns_stem(text), set())
        if len(hit) == 1:
            c = next(iter(hit))
            return {**base, "category": "EXISTING_CANONICAL", "reason": "EXACT_TERM", "canonical_id": c, "display": [c]}
        if len(hit) > 1:
            return {**base, "category": "UNCERTAIN", "reason": "EXACT_TERM_MULTI", "canonical_id": None, "display": sorted(hit)}
        # 3 STEP27 KNOWN
        if r27["status"] == "KNOWN_SYMPTOM":
            return {**base, "category": "EXISTING_CANONICAL", "reason": "MODEL_AUTO(STEP27)", "canonical_id": r27["canonical_id"], "display": [r27["canonical_id"]]}
        # 4 제품 매퍼 / 모델 + 어휘 근거
        pos = [m["evidence_id"] for m in mp if m["status"] == "POSITIVE"]
        mapc = {self.cw[e] for e in pos if e in self.cw}
        hist = [e for e in pos if e not in self.cw]
        koe = feats["koe_top1"] if feats["koe_conf"] >= S.T_KOE and self.lexical_support(text, feats["koe_top1"]) else None
        cands = set(mapc) | ({koe} if koe else set())
        if len(cands) == 1:
            c = next(iter(cands))
            why = "+".join(x for x, ok in (("PRODUCT_ALIAS", c in mapc), ("MODEL_LEXICAL", c == koe)) if ok)
            return {**base, "category": "EXISTING_CANONICAL", "reason": why, "canonical_id": c, "display": [c]}
        if len(cands) > 1:
            return {**base, "category": "UNCERTAIN", "reason": "SOURCE_CONFLICT", "canonical_id": None, "display": sorted(cands)}
        # 5 비증상 근거
        non = []
        if hist:
            non.append("PRODUCT_MAPPER_NON77:" + ";".join(f"{e}({'antecedent' if self.ev.get(e, {}).get('is_antecedent') else 'other'})" for e in hist))
        st = ns_stem(text)
        dz = [k for d, k in self.disease_ko.items() if len(st) >= 2 and (st == d or (len(st) >= 3 and st in d))]
        if dz:
            non.append("DISEASE_LABEL_KO:" + ";".join(dz[:3]))
        if r27["status"] == "NON_SYMPTOM":
            non.append("STEP27_NON:" + ";".join(r27["reason_codes"]))
        return {**base, "category": None, "reason": "", "canonical_id": None, "display": [], "non_evidence": non}
