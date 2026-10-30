"""STEP29.1 P5 — 보고가 아닌 발화(가정·질문) 표시. 규칙(평가 전 고정):
 HYPOTHETICAL : mention 단위의 술어 뒤에 조건 연결어미 '면/으면'(EC) → assertion UNKNOWN(보고 아님, concept 은 유지·모델 입력 안 함)
 QUESTION     : 문장이 '?' 로 끝나거나 의문 어미(나요·까요·가요·니까)로 끝나고 의문사·요청어(어떻게·뭐·왜·언제·어디·무엇·병원·해야)가 있음 → 그 문장 mention assertion UNKNOWN
(가족 증상·비증상은 STEP29 주체·P5 NON 으로 이미 분리 — 여기서 바꾸지 않음)"""
from __future__ import annotations

import s291_common  # noqa: F401  (경로)

import re

from extract_symptom_spans import kiwi

QW = re.compile(r"(어떻게|뭐|왜|언제|어디|무엇|병원|해야)")
QEND = re.compile(r"(\?|나요|까요|가요|니까|나\?)\s*[.!]?\s*$")


def apply(m: dict) -> dict:
    if not m.get("is_symptom"):
        return m
    toks = kiwi().tokenize(m.get("unit_text") or m["raw_span"])
    hyp = any(t.tag == "EC" and t.form in ("면", "으면") for t in toks)
    sent = m.get("source_sentence") or ""
    tail = m["source_text"][m["span_end"]:]
    q = bool(QEND.search(sent + tail[: max(0, len(tail))].split(".")[0]) or QEND.search(m["source_text"])) and bool(QW.search(sent + tail))
    if hyp or q:
        return {**m, "assertion": "UNKNOWN", "assertion_basis": "HYPOTHETICAL_CONDITIONAL" if hyp else "QUESTION_NOT_REPORT", "requires_confirmation": True}
    return m
