"""STEP29.3 §15 STEP29.2 NLU 연결 어댑터(STEP29.2 원본 무수정 — 같은 모듈을 같은 순서로 호출, 검색 계층만 끼움).
analyze(text, policy):
 R0 = STEP29.2 V3_B0 원본 · R1 = STEP29.2 V3_B3 원본
 N1–N4 · R2–R4 = 아래 core3(시점 가림 질의) → 검색 계층(context_preserving_retriever, 모드 N1–N4) → B4 정책(b4_evidence_policy) → model_input(STEP29.2 _mi)
core3(text) = STEP29.2 core 와 같은 단계(문장 분리 → 하위 문장 STEP29 분석 → 평가형 부정 범위 → 보고 아님 → 오프셋 원문 복원 → 해소 연결) +
 (a) STEP29 분석에는 시점 표현을 공백으로 가린 하위 문장을 넣는다(오프셋 같음, raw_span 은 원문에서 다시 자름) — 가린 구는 mention 의 onset_text 로 되돌리고
     '…부터'면 temporality CURRENT → ONGOING. 절 구조·해소 연결·문맥 판정은 가리지 않은 원문으로 한다.
 (b) '…할 때' 조건(TRIGGER) 절의 명시 주체(엄마가·아이가 …)를 같은 문장 다음 절의 주체 생략 mention 에 이어 준다(INHERITED_FROM_TRIGGER).
     STEP29 는 TRIGGER 절의 주체를 넘기지 않아 '엄마가 침을 삼킬 때 목이 아파요'의 엄마 증상을 환자로 처리했다(DEV 시험 중 발견).
정책 구성: N1 = core3 + N1 + B0 · N2 = core3 + N2 + B0 · R2(= N3) = core3 + N3 + B0 · N4 = core3 + N4 + B0 · R3 = core3 + N4 + B3C · R4 = core3 + N4 + B23."""
from __future__ import annotations

import copy

import s293_common  # noqa: F401  (경로)
import asr_sentence_segmenter as SEG
import b4_evidence_policy as BP
import clinical_nlu_pipeline as P29
import context_preserving_retriever as CPR
import evaluative_negation_scope as ENS
import nlu_pipeline_v3 as V3
import temporal_resolution_linker as TRL
import unsupported_input_guard as UIG
from clause_segmenter import segment
from experiencer_analyzer import explicit
from korean_morphological_normalizer import mask_time

POLICIES = ("R0", "R1", "N1", "N2", "R2", "N4", "R3", "R4")
CFG = {"N1": ("N1", "B0"), "N2": ("N2", "B0"), "R2": ("N3", "B0"), "N4": ("N4", "B0"), "R3": ("N4", "B3C"), "R4": ("N4", "B23")}
_CORE: dict[str, tuple] = {}
USE_CACHE = True


def core3(text: str):
    if USE_CACHE and text in _CORE:
        return copy.deepcopy(_CORE[text])
    sents = SEG.sentences(text)
    mentions, clauses_all = [], []
    ctx = {"sentences": [{k: o[k] for k in ("start", "end", "text", "basis", "body_start")} for o in sents], "dropped_context": [], "masked_time": []}
    for si, o in enumerate(sents):
        s0 = o["body_start"]
        sub = text[s0:o["end"]]
        msub, phr = mask_time(sub)
        ctx["masked_time"] += [{**p, "start": p["start"] + s0, "end": p["end"] + s0} for p in phr]
        base = P29.analyze(msub, "NLU_P5") if msub.strip() else {"mentions": []}
        cls = segment(sub)
        for cl in cls:
            clauses_all.append({**cl, "start": cl["start"] + s0, "end": cl["end"] + s0, "sentence_index": si, "sentence_start": s0, "sentence_end": o["end"]})
        trig_exp = []
        for cl in cls:
            if cl["kind"] == "TRIGGER":
                ex, basis = explicit(cl["tokens"])
                if ex:
                    trig_exp.append((cl["end"], ex, basis))
        for m in base["mentions"]:
            m = {**m, "raw_span": sub[m["span_start"]:m["span_end"]], "source_text": sub, "source_sentence": sub}
            cl = next((c for c in cls if c["start"] <= m["span_start"] < c["end"]), None)
            for p in phr:
                if cl and cl["start"] <= p["start"] < cl["end"] and not m.get("onset_text"):
                    m["onset_text"] = p["text"].strip()
                    m["time_scope"] = "CLAUSE"
                    if p["ongoing"] and m.get("temporality") == "CURRENT":
                        m["temporality"] = "ONGOING"
            if m.get("experiencer_basis") == "ASSUMED_INTAKE_DEFAULT":
                prev = [t for t in trig_exp if t[0] <= m["span_start"]]
                if prev:
                    m.update(experiencer=prev[-1][1], experiencer_basis="INHERITED_FROM_TRIGGER:" + prev[-1][2])
            m2 = ENS.apply(m, cl["text"] if cl else "")
            if m2.get("drop_as_context"):
                ctx["dropped_context"].append({"raw_span": m2["raw_span"], "start": m2["span_start"] + s0, "reason": m2.get("context_reason", "UNSURE_CONTEXT")})
                continue
            m2 = UIG.apply(m2)
            m2 = {**m2, "span_start": m2["span_start"] + s0, "span_end": m2["span_end"] + s0, "source_text": text, "source_sentence": sub, "sentence_index": si,
                  "sentence_span": [s0, o["end"]]}
            assert m2["raw_span"] == text[m2["span_start"]:m2["span_end"]]
            mentions.append(m2)
    mentions, rctx = TRL.apply(text, mentions, clauses_all)
    ctx["resolution_context"] = rctx
    if USE_CACHE:
        _CORE[text] = (mentions, ctx)
        return copy.deepcopy(_CORE[text])
    return mentions, ctx


def analyze(text: str, policy: str) -> dict:
    if policy == "R0":
        return V3.analyze(text, "V3_B0")
    if policy == "R1":
        return V3.analyze(text, "V3_B3")
    mode, b4 = CFG[policy]
    ms, ctx = core3(text)
    out = []
    for m in ms:
        m = CPR.apply(m, mode)
        m = BP.apply(m, b4)
        m["model_input"] = V3._mi(m)
        if m["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM", "NON_SYMPTOM") and not (m.get("reason") or m.get("guard_reasons")):
            m["reason"] = "NO_SUPPORTED_LINK(원문 보존)"
        out.append(m)
    return {"source_text": text, "level": policy, "mentions": out, "context": ctx}


def sentence_spans(text: str, policy: str):
    return SEG.spans(text) if policy not in ("R0", "R1") else V3.sentence_spans(text, "V3_B0")


if __name__ == "__main__":
    import json
    import sys
    pol = "R2"
    for t in sys.argv[1:]:
        if t.startswith("--policy="):
            pol = t.split("=", 1)[1]
            continue
        print("==", t)
        for m in analyze(t, pol)["mentions"]:
            print(json.dumps({k: m.get(k) for k in ("raw_span", "status", "canonical_id", "ontology_id", "guard_blocked_concept", "assertion", "temporality",
                                                     "onset_text", "experiencer", "guard_reasons", "retrieval", "semantic_conflict")}
                             | {"model": m["model_input"]["polarity"] if m["model_input"]["eligible"] else None}, ensure_ascii=False))
