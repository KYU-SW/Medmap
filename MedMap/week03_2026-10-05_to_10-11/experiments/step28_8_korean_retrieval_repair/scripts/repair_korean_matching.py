"""STEP28.8 §3·§4 — STEP28.5 한국어 검색(KO) 수정판. 원본 bilingual_retriever.Retriever 를 상속만 하고 원본 파일은 바꾸지 않는다.
규칙은 정책 평가(evaluate_policies) 실행 전 고정(2026-10-11). STEP28.7 에서 본 오류 사례를 보고 만든 규칙이 있으므로 그 사례 결과는 회귀 확인용이다.

검색 순서(구문마다):
 A·B EXACT  : 질의 키 == 색인 키(용어 원문 키 · 조사 제거 키 · 술어 정규화 nkey) — STEP23 학습·STEP21 사전·용어집(검증된 표준·동의어)
   질의 키 = 구문 키(조사 제거) · 명사구 키(술어가 증상을 담으면 제외, STEP28.5 와 같음) · 질의(명사+술어 원형) 키 ·
            핵어 키(명사구가 한 토큰일 때만) · 술어 키(명사구 없을 때, 2자 이상)
   1글자 키는 명사구 전체가 그 1글자일 때만(예 '열'). 색인 nkey 1글자(616행, 예 '가슴 두근'→'근')는 쓰지 않는다.
   nkey(술어 정규화) 일치는 양태가 같을 때만(…할 것 같다·…듯·…싶다 유무) — '오바이트 할 것 같아요'(오심) ≠ '오바이트했어요'(구토).
 C BOUNDARY : 색인 용어의 핵심 형태소열(명사·용언 원형, XPN·XSN 결합, 가벼운 용언·의존명사·관형사·부사 제외, 명사 끝 '증' 제거[3자 이상])이
              질의 형태소열 안에 **연속·경계 일치**로 들어 있을 때만. 역방향(질의가 긴 색인 문장 안에 포함) 일치는 쓰지 않는다(STEP28.5 PHRASE 폐기).
              1글자 단일 형태소·신체 부위 단일 형태소 용어는 제외. 검사명(LNC-KO-KR)·약재명(TKMT)은 EXACT 만.
 D 합성     : 통증 합성어(두통·흉통·복통 …)는 명사구·구문의 띄어쓰기 제거 키 끝 일치('흉 통' 분리 대응) · 통증 술어 + 부위 → pain + E_55 (STEP28.5 와 같음)
 비증상 차단: 명사구 마지막 명사(한국어 핵어)가 질환·약물·치료·검사 접미(STEP27 NON_TYPE_CUE)이고 그 자체가 증상 용어가 아니면 NON_SYMPTOM('기침 억제제')
             진단형 수식어: 증상어 앞에 'X성' 명사(만성·급성 등 경과 수식어 제외)가 있으면 UNCERTAIN(DIAGNOSIS_LIKE_MODIFIER, 표시 없음)
             ('경추성 어지럼증' · '혈관성 편두통' — STEP28.7 위험 사례·지시문 예시를 보고 만든 일반 규칙)
 분류(STEP28.5 와 같음): 증상 concept 1개 → EXISTING_CANONICAL · 비증상 역할만 → NON · 둘 이상/섞임 → UNCERTAIN(충돌, 표시 없음, B4 가 후보 안이면 해소) ·
             부위만 → UNCERTAIN · 후보 없음 → STEP27 B4 자동수락이면 그 concept, 아니면 n-gram(후보만)·UNKNOWN/UNCERTAIN.
출력 evidence: 'EXACT:<출처>:<용어 전문>' · 'BOUNDARY:<출처>:<용어 전문>' · 'PAIN+SITE:…' · 'MODEL_AUTO(STEP27_B4)'.
CLI: 색인 핵심 형태소열을 data/index_core_tokens.csv 로 기록(투명성).
"""
from __future__ import annotations

import collections
import re

import numpy as np

import s288_common as S
from bilingual_retriever import NON_ROLES, Retriever
from extract_symptom_spans import kiwi

NOUN_T = {"NNG", "NNP", "XR", "SL", "NR"}
PRED_T = {"VV", "VA", "VA-I", "VV-I", "VV-R", "VA-R"}
LIGHT = {"하", "되", "있", "나", "생기", "들", "오", "같", "싶", "보", "지", "않", "없", "못하", "이", "아니", "주", "가", "받", "드리", "계시"}
COURSE = {"만성", "급성", "아급성", "반복성", "지속성", "간헐성", "일과성", "재발성", "진행성", "돌발성", "습관성"}
MODAL = re.compile(r"(것\s*같|듯|할\s*것|싶)")
EXACT_ONLY_ROLES = {"TEST", "HERB"}
_CACHE: dict[str, tuple] = {}


def core_tokens(text: str) -> tuple:
    if text in _CACHE:
        return _CACHE[text]
    out, prefix = [], ""
    for t in kiwi().tokenize(text or ""):
        if t.tag == "XPN":
            prefix = t.form
            continue
        if t.tag in NOUN_T:
            out.append(prefix + t.form)
        elif t.tag == "XSN" and out:
            out[-1] += t.form
        elif t.tag in PRED_T and t.form not in LIGHT:
            out.append(t.form)
        prefix = ""
    out = [w[:-1] if len(w) >= 3 and w.endswith("증") else w for w in out]
    _CACHE[text] = tuple(out)
    return _CACHE[text]


def modal(text: str) -> bool:
    return bool(MODAL.search(text or ""))


def contains(Q: tuple, C: tuple) -> bool:
    n = len(C)
    return n > 0 and any(Q[i:i + n] == C for i in range(len(Q) - n + 1))


class RepairedRetriever(Retriever):
    def __init__(self):
        super().__init__()
        self.body = set(self.bp) | set(self.site_vals) | {S.ko_key(r["ko_term"]) for rs in self.idx.values() for r in rs if r["role"] == "BODY_SITE"}
        self.by_first = collections.defaultdict(list)
        seen = set()
        for rs in self.idx.values():
            for r in rs:
                k = (r["ko_term"], r["target_id"], r["role"])
                if k in seen or r["role"] in EXACT_ONLY_ROLES:
                    continue
                seen.add(k)
                C = core_tokens(r["ko_term"])
                if not C or (len(C) == 1 and (len(C[0]) < 2 or C[0] in self.body)):
                    continue
                self.by_first[C[0]].append((C, r))
        self.skey = collections.defaultdict(list)        # 조사 제거 키(원본 색인에 없는 정규화 — 질의와 같은 함수)
        for k, rs in self.idx.items():
            for r in rs:
                sk = S.ko_key(S.stem_key(r["ko_term"]))
                if sk and sk != r["key"] and len(sk) >= 2:
                    self.skey[sk].append(r)

    # ---------- 질의 키 ----------
    def rkeys(self, sp):
        np_key = S.ko_key(sp["noun_phrase"])
        single_np = len(core_tokens(sp["noun_phrase"])) <= 1 if sp["noun_phrase"] else False
        if sp["pred_class"] in ("PAIN", "OTHER"):
            ks = [S.ko_key(sp["query_ko"].removesuffix("다"))]
        else:
            ks = [S.ko_key(S.stem_key(sp["span_text"])), np_key, S.ko_key(sp["query_ko"].removesuffix("다"))]
            if single_np:
                ks.append(S.ko_key(sp["head_noun"]))
            if not sp["noun_phrase"] and sp["predicate"]:
                ks.append(S.ko_key(sp["predicate"]))
        out = []
        for k in dict.fromkeys(ks):
            if not k:
                continue
            if len(k) == 1 and not (k == np_key and single_np):
                continue
            out.append(k)
        return out

    def exact(self, sp, keys):
        qm = modal(sp["span_text"]) or modal(sp.get("source_text", ""))
        out = []
        for k in keys:
            for r in self.idx.get(k, []) + self.skey.get(k, []):
                via_nkey = r.get("nkey") == k and r["key"] != k
                if via_nkey and (len(k) < 2 or modal(r["ko_term"]) != qm):
                    continue
                out.append({**r, "tier": "EXACT", "qkey": k})
        return out

    def boundary(self, sp):
        Q = core_tokens(sp["span_text"])
        qm = modal(sp["span_text"]) or modal(sp.get("source_text", ""))
        out = []
        for i, tok in enumerate(Q):
            for C, r in self.by_first.get(tok, []):
                if Q[i:i + len(C)] == C and modal(r["ko_term"]) == qm:
                    out.append({**r, "tier": "BOUNDARY", "qkey": " ".join(C), "span_end_tok": i + len(C)})
        return out, Q

    # ---------- 판정 ----------
    def ko(self, sp, feats):
        Q = core_tokens(sp["span_text"])
        diag = [t for t in Q if len(t) >= 2 and t.endswith("성") and t not in COURSE]
        npk = S.ko_key(S.stem_key(sp["noun_phrase"] or sp["span_text"]))
        nouns = [t for t in core_tokens(sp["noun_phrase"])] if sp["noun_phrase"] else []
        head = nouns[-1] if nouns else ""
        comp = next((c for c in sorted(S.S28.PAIN_COMPOUND, key=len, reverse=True) if npk.endswith(c)), None)
        if comp and not diag:
            site = S.S28.PAIN_COMPOUND[comp]
            vals = [r["target_id"] for k, rs in self.idx.items() for r in rs if r["role"] == "BODY_SITE" and S.ko_key(site) in k][:12]
            return {"category": "EXISTING_COMPOSITE", "concept": "pain", "evidence": [f"PAIN+SITE:{comp}"], "attributes": {"site_ko": site, "E_55_values": vals},
                    "display": ["pain"], "tiers": ["RULE"]}
        if not comp:
            kind, site = self.composite(sp)
            if kind == "PAIN_SITE" and not diag:
                vals = [r["target_id"] for k, rs in self.idx.items() for r in rs if r["role"] == "BODY_SITE" and site and S.ko_key(site) in k][:12]
                return {"category": "EXISTING_COMPOSITE", "concept": "pain", "evidence": [f"PAIN+SITE:{site}"], "attributes": {"site_ko": site, "E_55_values": vals},
                        "display": ["pain"], "tiers": ["RULE"]}
            if kind == "SORE_THROAT":
                return {"category": "EXISTING_CANONICAL", "concept": "sore_throat", "evidence": ["SORE_THROAT_SITE"], "display": ["sore_throat"], "tiers": ["RULE"]}
            if kind == "NECK":
                return {"category": "UNCERTAIN", "concept": None, "evidence": ["NECK_AMBIGUOUS"], "display": ["sore_throat", "pain"], "tiers": ["RULE"]}
        cands = self.exact(sp, self.rkeys(sp))
        if not cands:
            cands, _ = self.boundary(sp)
        sym = sorted({c["target_id"] for c in cands if c["role"] == "SYMPTOM"})
        non = sorted({f"{c['role']}:{c['target_id']}" for c in cands if c["role"] in NON_ROLES})
        site_only = cands and all(c["role"] in ("BODY_SITE", "VALUE", "ATTRIBUTE") for c in cands)
        tiers = sorted({c["tier"] for c in cands})
        ev = [f"{c['tier']}:{c['provenance']}:{c['ko_term']}" for c in cands[:4]]
        nt = S.S28.non_type(head) if head else ""
        head_is_sym = any(c["role"] == "SYMPTOM" and (c["tier"] == "EXACT" or c.get("span_end_tok") == len(Q)) and Q and Q[-1] == head for c in cands)
        if nt and not head_is_sym:
            return {"category": "NON_SYMPTOM", "concept": None, "evidence": [f"HEAD_NON_TYPE:{nt}:{head}"] + ev[:2], "display": [], "tiers": ["CUE"],
                    "reason": "HEAD_NON_TYPE"}
        if (sym or comp) and diag:
            return {"category": "UNCERTAIN", "concept": None, "evidence": [f"DIAGNOSIS_LIKE_MODIFIER:{diag[0]}"] + ev[:2], "display": [], "tiers": tiers,
                    "reason": "DIAGNOSIS_LIKE_MODIFIER", "held_ko_candidates": sym or ["pain"]}
        b4 = feats["b4_known"] if feats else None
        if len(sym) == 1 and not non:
            c = sym[0]
            agree = feats and feats["koe_top1"] == c and feats["koe_conf"] >= S.S28.T_KOE
            return {"category": "EXISTING_CANONICAL", "concept": c, "evidence": ev + (["MODEL_AGREES"] if agree else []), "display": [c], "tiers": tiers}
        if non and not sym:
            return {"category": "NON_SYMPTOM", "concept": None, "evidence": non[:4], "display": [], "tiers": tiers}
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
        qk = self.rkeys(sp)
        if qk:
            v = self.vec.transform([qk[0]])
            s = (self.X @ v.T).toarray().ravel()
            ng = [(self.nkeys[i], float(s[i])) for i in np.argsort(-s)[:3] if s[i] >= 0.6]
            if ng:
                tg = sorted({r["target_id"] for k, _ in ng for r in self.idx[k]})
                return {"category": "UNCERTAIN", "concept": None, "evidence": [f"NGRAM:{t}" for t in tg[:3]], "display": [], "tiers": ["NGRAM"],
                        "reason": "NGRAM_ONLY", "ngram_targets": tg}
        sym_ev = sp["pred_class"] in ("PAIN", "OCCUR", "OTHER") or bool((feats or {}).get("sym_cue"))
        return {"category": "UNKNOWN_SYMPTOM" if sym_ev else "UNCERTAIN", "concept": None, "evidence": [], "display": [], "tiers": [], "reason": "NO_KOREAN_MATCH"}


def main():
    R = RepairedRetriever()
    rows = [{"first": f, "core": " ".join(C), "ko_term": r["ko_term"], "target_id": r["target_id"], "role": r["role"], "provenance": r["provenance"]}
            for f, lst in sorted(R.by_first.items()) for C, r in lst]
    S.wcsv(S.DATA / "index_core_tokens.csv", rows)
    dropped_nkey1 = sum(1 for r in S.read_csv(S.S285_DIR / "index/korean_index.csv") if r["nkey"] and len(r["nkey"]) == 1)
    print({"boundary_entries": len(rows), "index_rows_with_1char_nkey(not used)": dropped_nkey1})


if __name__ == "__main__":
    main()
