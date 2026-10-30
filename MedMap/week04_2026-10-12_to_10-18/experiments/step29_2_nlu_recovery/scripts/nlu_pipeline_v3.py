"""STEP29.2 NLU 파이프라인 v3(연구용). analyze(text, policy) → {"source_text", "level", "mentions", "context"}. 이전 단계 코드는 import·호출만(원본 무수정).

정책: S29 = STEP29 NLU_P5 원본 · S291 = STEP29.1 P5 원본 · V3_B0–B3 = 아래 v3 + B4 가드 변형(b4_evidence_guard).
v3 단계:
 1 문장 분리(asr_sentence_segmenter — 종결어미 기반, 마침표 없어도). 하위 문장 text = 원문 구간(끝 '.'·'!' 제외, '?' 포함, 앞 채움말·접속부사 제외 = body_start).
 2 하위 문장마다 STEP29 analyze(sub, NLU_P5)(절 분해·단위·P5·부정·시점·주체·STEP29 의미 가드) → STEP29.1 불확실 표현 맥락 제외(evaluative_negation 의 drop_as_context)
   → 평가형 부정 범위(evaluative_negation_scope E1–E4) → 보고 아님 표시(STEP29.1 unsupported_input_guard: 가정·질문, 하위 문장 기준)
   → 오프셋을 원문 기준으로 이동(span_start += 문장 시작, source_text = 원문, source_sentence = 하위 문장, sentence_index)
 3 시간·해소 연결(temporal_resolution_linker — 문장·절 전체 문맥, 과거 사건 보존 + current_status·resolution)
 4 가드: b4_evidence_guard.apply(m, policy)(STEP29.1 mention_context_validator 를 포함, B4 단독 규칙만 정책별로 다름)
 5 model_input(표시만, applied=false): STEP29 symptom_context_builder 규칙 + assertion_certainty LOW·UNKNOWN 불가 + current_status RESOLVED 인 PRESENT 불가.
 assertion·temporality(사건 시점)는 해소 연결이 바꾸지 않는다. 원문·원래 값·사유는 모두 보존."""
from __future__ import annotations

import copy

import s292_common as S
import asr_sentence_segmenter as SEG
import b4_evidence_guard as B4G
import clinical_nlu_pipeline as P29
import evaluative_negation_scope as ENS
import nlu_pipeline_v2 as N2
import temporal_resolution_linker as TRL
import unsupported_input_guard as UIG
from clause_segmenter import segment
from symptom_context_builder import model_input

POLICIES = ("S29", "S291", "V3_B0", "V3_B1", "V3_B2", "V3_B3")
_CORE: dict[str, tuple] = {}
USE_CACHE = True   # 평가 속도용 메모(결정적). 지연 측정 시 False


def _mi(m):
    mi = model_input(m)
    if m.get("assertion_certainty") == "LOW" or m.get("assertion") in ("UNKNOWN", "POSSIBLE") or \
            (m.get("assertion") == "PRESENT" and m.get("current_status") == "RESOLVED"):
        mi = {**mi, "eligible": False, "polarity": None}
    return mi


def core(text: str) -> tuple[list[dict], dict, list[dict]]:
    if USE_CACHE and text in _CORE:
        return copy.deepcopy(_CORE[text])
    sents = SEG.sentences(text)
    mentions, clauses_all = [], []
    ctx = {"sentences": [{k: o[k] for k in ("start", "end", "text", "basis", "kiwi_agrees", "body_start", "lead_filler")} for o in sents], "dropped_context": [],
           "triggers": []}
    for si, o in enumerate(sents):
        s0 = o["body_start"]
        sub = text[s0:o["end"]]
        base = P29.analyze(sub, "NLU_P5")
        ctx["triggers"] += [{**t, "start": t["start"] + s0, "end": t["end"] + s0} for t in base["context"].get("triggers", [])]
        cls = segment(sub)
        for cl in cls:
            clauses_all.append({**cl, "start": cl["start"] + s0, "end": cl["end"] + s0, "sentence_index": si, "sentence_start": s0, "sentence_end": o["end"]})
        for m in base["mentions"]:
            cl = next((c for c in cls if c["start"] <= m["span_start"] < c["end"]), None)
            m2 = ENS.apply(m, cl["text"] if cl else "")
            if m2.get("drop_as_context"):
                ctx["dropped_context"].append({"raw_span": m2["raw_span"], "start": m2["span_start"] + s0, "reason": m2.get("context_reason", "UNSURE_CONTEXT")})
                continue
            m2 = UIG.apply(m2)
            m2 = {**m2, "span_start": m2["span_start"] + s0, "span_end": m2["span_end"] + s0, "source_text": text, "source_sentence": sub,
                  "sentence_index": si, "sentence_span": [s0, o["end"]]}
            assert m2["raw_span"] == text[m2["span_start"]:m2["span_end"]]
            mentions.append(m2)
    mentions, rctx = TRL.apply(text, mentions, clauses_all)
    ctx["resolution_context"] = rctx
    if not USE_CACHE:
        return mentions, ctx, sents
    _CORE[text] = (mentions, ctx, sents)
    return copy.deepcopy(_CORE[text])


def analyze(text: str, policy: str = "V3_B2") -> dict:
    if policy == "S29":
        return P29.analyze(text, "NLU_P5")
    if policy == "S291":
        return N2.analyze(text, "P5")
    ms, ctx, _ = core(text)
    out = []
    for m in ms:
        m = B4G.apply(m, policy)
        m["model_input"] = _mi(m)
        if m["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM") and not (m.get("reason") or m.get("guard_reasons")):
            m["reason"] = "NO_SUPPORTED_LINK(원문 보존)"
        out.append(m)
    return {"source_text": text, "level": policy, "mentions": out, "context": ctx}


def sentence_spans(text: str, policy: str) -> list[tuple[int, int]]:
    if policy in ("S29", "S291"):
        out = {}
        for c in segment(text):
            out.setdefault(c["sentence_index"], (c["sentence_start"], c["sentence_end"]))
        return [v for _, v in sorted(out.items())]
    return SEG.spans(text)


if __name__ == "__main__":
    import json
    import sys
    pol = "V3_B2"
    for t in sys.argv[1:]:
        if t.startswith("--policy="):
            pol = t.split("=", 1)[1]
            continue
        print("==", t)
        for m in analyze(t, pol)["mentions"]:
            print(json.dumps({k: m.get(k) for k in ("raw_span", "status", "canonical_id", "guard_blocked_concept", "assertion", "assertion_basis", "assertion_certainty",
                                                     "temporality", "current_status", "resolution", "experiencer", "guard_reasons", "b4_guard_detail")}
                             | {"model": m["model_input"]["polarity"] if m["model_input"]["eligible"] else None}, ensure_ascii=False))
