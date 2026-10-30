"""STEP28 ontology 검색 — 사전 생성 색인(index/ontology_index.sqlite)만 조회한다(요청마다 원본 순회 없음).

한국어 → ontology 연결 경로(분리 평가):
 A  MedMap 한국어 용어 → 77 canonical (search_existing_concepts)                         — 기존 concept, 신규 아님
 B  MedMap 한국어 용어 → canonical → STEP20 curated HPO/SNOMED/CUI                       — 기존 concept 의 표준 id(신규 아님)
 K  UMLS KOR SRL 0(LNC-KO-KR 검사명 · TKMT 약재명) 완전일치                              — NON(검사·약재) 근거로만
 C  로컬 xlm-roberta-base 평균 풀링 임베딩 ↔ HPO phenotype 이름·EXACT 동의어 코사인 top-k  — feasibility gate 통과 시에만 후보 생성,
    후보는 AUTO_CANDIDATE(검증 전), 표시 안 함
 D  위 경로가 모두 없음 → KOREAN_LINK_MISSING
 (MDRKOR·KCD5 = SRL 3 → 색인에 없음. 사용자 이용 조건 확인 전 경로 없음)
영어 검색 search_en(): 정규화 완전일치 → 없으면 토큰 Jaccard(후보는 첫 토큰 LIKE 로 최대 400행). 데모·검증용.
"""
from __future__ import annotations

import re
import sqlite3

import numpy as np

import s28_common as S

DB = S.INDEX / "ontology_index.sqlite"
XLMR_CACHE = S.INDEX / "xlmr_hpo_embeddings.npz"


def tnorm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class OntologyIndex:
    def __init__(self, path=DB):
        self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)

    def q(self, sql, *a):
        return self.db.execute(sql, a).fetchall()

    def concept(self, cid: str) -> dict | None:
        if cid.startswith("HP:"):
            alt = self.q("SELECT cid FROM hpo_alt WHERE alt=?", cid)
            if alt and not self.q("SELECT 1 FROM concept WHERE cid=?", cid):
                cid = alt[0][0]
        r = self.q("SELECT cid,source,name,definition,active,kind,parents,replaced_by FROM concept WHERE cid=?", cid)
        if not r:
            if cid.startswith("SCTID:"):
                st = self.q("SELECT active FROM sct_status WHERE sctid=?", cid[6:])
                return {"cid": cid, "source": "SNOMED", "name": "", "definition": "", "active": st[0][0] if st else None,
                        "kind": "outside_clinical_finding", "parents": [], "replaced_by": ""}
            return None
        c = dict(zip(("cid", "source", "name", "definition", "active", "kind", "parents", "replaced_by"), r[0]))
        c["parents"] = [p for p in c["parents"].split(";") if p]
        return c

    def ancestors(self, cid: str, limit=5000) -> set[str]:
        out, st = set(), [cid]
        while st and len(out) < limit:
            x = st.pop()
            c = self.concept(x)
            for p in (c or {}).get("parents", []):
                if p not in out:
                    out.add(p)
                    st.append(p)
        return out

    def cuis(self, cid: str) -> list[str]:
        if cid.startswith("HP:"):
            return [r[0] for r in self.q("SELECT cui FROM xref WHERE sab='HPO' AND code=?", cid)]
        if cid.startswith("SCTID:"):
            return [r[0] for r in self.q("SELECT cui FROM xref WHERE sab='SNOMEDCT_US' AND code=?", cid[6:])]
        if cid.startswith("CUI:"):
            return [cid[4:]]
        return []

    def codes(self, cui: str) -> list[str]:
        return [("HP:" if sab == "HPO" else "SCTID:") + code if sab == "SNOMEDCT_US" else code
                for sab, code in self.q("SELECT sab,code FROM xref WHERE cui=?", cui)]

    def sty(self, cid: str) -> list[tuple[str, str]]:
        out = []
        for cui in self.cuis(cid):
            out += self.q("SELECT tui,sty FROM sty WHERE cui=?", cui)
        return sorted(set(out))

    def search_en(self, query: str, k=10) -> list[dict]:
        qn = tnorm(query)
        rows = self.q("SELECT term,cid,ttype FROM term WHERE term_norm=?", qn)
        scored = [(1.0, r) for r in rows]
        if not scored and qn:
            toks = set(qn.split())
            first = max(toks, key=len)
            for r in self.q("SELECT term,cid,ttype,term_norm FROM term WHERE term_norm LIKE ? LIMIT 400", f"%{first}%"):
                tt = set(r[3].split())
                scored.append((len(toks & tt) / len(toks | tt), r[:3]))
        best = {}
        for s, (term, cid, ttype) in sorted(scored, key=lambda x: -x[0]):
            if cid not in best:
                best[cid] = {"cid": cid, "matched_term": term, "ttype": ttype, "lexical_score": round(s, 4)}
        return list(best.values())[:k]

    def kor_lookup(self, text: str) -> list[tuple[str, str, str]]:
        t = text.strip()
        return self.q("SELECT term,cui,sab FROM kor_term WHERE term=?", t)


class CrossLingual:
    """경로 C. xlm-roberta-base(로컬 캐시) 평균 풀링. HPO phenotype 이름 + EXACT 동의어."""

    def __init__(self, oi: OntologyIndex):
        import torch
        from transformers import AutoModel, AutoTokenizer
        snap = next((S.XLMR / "snapshots").iterdir())
        self.tok = AutoTokenizer.from_pretrained(snap)
        self.model = AutoModel.from_pretrained(snap).to("cpu").eval()
        torch.set_grad_enabled(False)
        if XLMR_CACHE.exists():
            z = np.load(XLMR_CACHE, allow_pickle=False)
            self.E, self.ids, self.strs = z["E"], list(z["ids"]), list(z["strs"])
        else:
            rows = oi.q("SELECT t.term, t.cid FROM term t JOIN concept c ON c.cid=t.cid WHERE c.source='HPO' AND c.kind='phenotype' AND c.active=1 "
                        "AND (t.ttype='HPO:name' OR t.ttype='HPO:syn:EXACT') ORDER BY t.cid, t.term")
            self.strs, self.ids = [r[0] for r in rows], [r[1] for r in rows]
            self.E = np.concatenate([self.embed(self.strs[i:i + 128]) for i in range(0, len(self.strs), 128)])
            np.savez(XLMR_CACHE, E=self.E, ids=np.array(self.ids), strs=np.array(self.strs))

    def embed(self, texts):
        b = self.tok(texts, padding=True, truncation=True, max_length=32, return_tensors="pt")
        h = self.model(**b).last_hidden_state
        m = b["attention_mask"].unsqueeze(-1).float()
        v = ((h * m).sum(1) / m.sum(1)).numpy()
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    def search(self, text: str, k=5) -> list[dict]:
        q = self.embed([text])[0]
        s = self.E @ q
        out, seen = [], set()
        for i in np.argsort(-s):
            if self.ids[i] in seen:
                continue
            seen.add(self.ids[i])
            out.append({"cid": self.ids[i], "matched_term": self.strs[i], "ttype": "XLMR_COSINE", "lexical_score": round(float(s[i]), 4)})
            if len(out) == k:
                break
        return out
