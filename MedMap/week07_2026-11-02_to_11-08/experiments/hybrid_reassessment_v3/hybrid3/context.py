"""기능 B: 의료 기록 문장에서 임상 맥락 사실(fact)을 추출하고 시점별로 모은다.
기록에 적힌 값만 RECORD 로 담는다. 확률·점수 범주를 계산하거나 추측하지 않는다. 의사 확인은 문서 메타데이터에 명시된 경우만."""
from __future__ import annotations

import re

from . import concepts as CP
from .concepts import CC_MOD as CC, EC_MOD as EC  # noqa: F401  (P2 모듈 재노출)

R_PROB = re.compile(r"\b(low|intermediate|moderate|high)\b[\w\s\-]{0,25}?\b(?:clinical|pre-?test)\s+probability\b|\b(?:clinical|pre-?test)\s+probability\b(?:\s+of\s+(?:PE|pulmonary embolism))?\s+(?:was|is|as|were)?\s*(?:assessed as|considered|deemed|estimated as|judged)?\s*(?:to be\s+)?(low|intermediate|moderate|high)\b", re.I)
R_PROB_NEG = re.compile(r"\bnot\s+(?:a\s+)?(?:low|intermediate|moderate|high)\b", re.I)
R_TWO_LEVEL = re.compile(r"\bPE\s+(?:unlikely|likely)\b|\b(?:unlikely|likely)\s+(?:PE|pulmonary embolism)\b")
R_METHOD = re.compile(r"\b(Wells|Geneva|YEARS|PERC|clinical gestalt|gestalt)\b")
R_SCORE = re.compile(r"\b(Wells|Geneva)\b[^.;]{0,40}?\b(\d+(?:\.\d+)?)\s*(?:points?)?", re.I)
R_SUSPECT = re.compile(r"\b(suspect\w*|suspicion|concern(?:ing)? for|to (?:rule out|exclude|investigate|evaluate)|rule out|r/o|evaluat\w+ for|work-?up for|possible)\b", re.I)
R_INSTABLE = re.compile(r"\b(?:ha?emodynamic(?:ally)?\s+(?:instability|unstable)|obstructive shock|cardiogenic shock|cardiac arrest)\b", re.I)
R_STABLE = re.compile(r"\bha?emodynamically\s+stable\b", re.I)
R_REL_TIME = re.compile(r"\b(\d+|one|two|three|four|five|six|several|a few)\s+(day|week|month|year)s?\s+(?:ago|earlier|before|prior)\b|\bin\s+(?:19|20)\d{2}\b", re.I)
R_TX_CURRENT = re.compile(r"\b(?:currently|is|are|was|were|remains?)\s+(?:\w+\s+)?(?:on|receiving|taking|treated with|continued)\b|\bon\s+(?:\w+\s+){0,2}$|\bcontinu\w+\b|\bstarted\b|\binitiated\b|\bcommenced\b", re.I)
R_TX_DONE = re.compile(r"\b(?:completed|completion of|discontinu\w+|stopped|ceased|cessation of|after\s+\d+\s+months?\s+of)\b", re.I)


def _fact(key, value, rec_or_sent, doc, method, certainty="EXPLICIT_TEXT", cue=""):
    s = rec_or_sent if isinstance(rec_or_sent, str) else rec_or_sent["sentence"]
    return {"key": key, "value": value, "source_type": "RECORD", "extraction_method": method, "certainty": certainty, "cue": cue[:120], "sentence": s,
            "doc_id": doc.doc_id, "observation_time": doc.observed_at, "available_time": doc.available_at,
            "physician_confirmation_status": "CONFIRMED_IN_METADATA" if doc.physician_confirmed else "UNCONFIRMED"}


def treatment_status(rec: dict) -> str:
    s = rec["sentence"]
    i = s.find(rec["surface"])
    near = s[max(0, i - 60): i + len(rec["surface"]) + 40]
    if rec["assertion"] in ("NEGATED",) and not R_TX_CURRENT.search(near):
        return "NOT_GIVEN"
    if rec["assertion"] in ("ORDERED_NOT_RESULTED", "CONDITIONAL"):
        return "PLANNED_OR_CONDITIONAL"
    if R_TX_DONE.search(near):
        return "COMPLETED"
    if R_TX_CURRENT.search(s[max(0, i - 60): i]) or R_TX_CURRENT.search(near):
        return "CURRENT"
    return "MENTIONED_STATUS_UNCLEAR"


def extract_facts(doc) -> list:
    """문서 1건 → 맥락 사실 목록. 문장 단위 근거를 보존."""
    facts = []
    abbr = CP.abbreviations(doc.text)
    recs = CP.extract(doc.text, doc.doc_type, abbr)
    for ab, (c, ev, form) in abbr.items():
        facts.append(_fact("abbreviation", {"abbr": ab, "concept": c, "form": form}, ev, doc, "DOC_ABBREVIATION_RULE"))
    sentences = sorted({r["sentence"] for r in recs} | {c.sentence for c in CP.PS.split_clauses(doc.text)})
    for s in sentences:
        srecs = [r for r in recs if r["sentence"] == s]
        pe = [r for r in srecs if r["concept"] == "PE_DIAGNOSIS" and r["link_status"] == "LINKED" and r["role"] == "MENTION"]
        for m in R_PROB.finditer(s):
            if R_PROB_NEG.search(s[max(0, m.start() - 8): m.end()]):
                continue
            v = (m.group(1) or m.group(2)).upper()
            meth = R_METHOD.search(s)
            facts.append(_fact("pretest", "INTERMEDIATE" if v == "MODERATE" else v, s, doc, "RULE_STATED_CATEGORY", cue=m.group(0)))
            facts.append(_fact("pretest_method", meth.group(1) if meth else "NOT_STATED", s, doc, "RULE"))
        if R_TWO_LEVEL.search(s):
            facts.append(_fact("pretest_two_level_statement", R_TWO_LEVEL.search(s).group(0), s, doc, "RULE", certainty="NOT_MAPPED_TO_THREE_LEVEL"))
        for m in R_SCORE.finditer(s):
            facts.append(_fact("probability_score", {"rule": m.group(1), "value": m.group(2)}, s, doc, "RULE", certainty="SCORE_NOT_CONVERTED", cue=m.group(0)))
        for r in pe:
            near = s[max(0, s.find(r["surface"]) - 60): s.find(r["surface"]) + len(r["surface"]) + 30]   # "X is suspected" 처럼 뒤에 오는 단서 포함
            if r["assertion"] in ("PURPOSE_OR_DIFFERENTIAL", "UNCERTAIN", "ORDERED_NOT_RESULTED", "RESULT_PENDING") and R_SUSPECT.search(near) and not CC.R_RECUR.search(s):
                facts.append(_fact("suspected", True, r, doc, "RULE_SUSPICION_OR_TEST_PURPOSE", cue=R_SUSPECT.search(near).group(0)))
            if r["assertion"] in ("PRESENT", "HISTORICAL") and (CC._confirmed(s) or r["assertion"] == "HISTORICAL" or R_REL_TIME.search(s)):
                t = R_REL_TIME.search(s)
                facts.append(_fact("pe_episode_statement", {"status": "DIAGNOSED_STATEMENT" if CC._confirmed(s) else "HISTORY_OR_PAST_STATEMENT",
                                                            "relative_time": t.group(0) if t else "NOT_STATED", "subtype": r["subtype"] or ""}, r, doc, "RULE"))
        sig = CC.sentence_signals(s)
        if sig["phase"]:
            facts.append(_fact("clinical_phase_signal", sig["phase"], s, doc, "P2_SENTENCE_SIGNALS", cue=",".join(sig["signals"])))
        for r in srecs:
            if r["concept"] in ("ANTICOAGULATION", "THROMBOLYSIS") and r["role"] == "MENTION":
                facts.append(_fact("treatment", {"agent": r["surface"], "class": r["concept"], "status": treatment_status(r)}, r, doc, "RULE"))
            if r["concept"] == "DDIMER" and r["role"] == "MENTION":
                dd = EC.ddimer_conditions(s, {})
                if dd["assay"]:
                    facts.append(_fact("ddimer_assay", dd["assay"], s, doc, "RULE_ASSAY_NAME"))
                if dd["cutoff"]:
                    facts.append(_fact("ddimer_cutoff", dd["cutoff"], s, doc, "RULE_CUTOFF_TEXT"))
        if R_INSTABLE.search(s) and not re.search(r"\b(no|without|absence of)\b[^.;]{0,25}" + R_INSTABLE.pattern, s, re.I):
            facts.append(_fact("haemodynamic_instability", True, s, doc, "RULE", cue=R_INSTABLE.search(s).group(0)))
        elif R_STABLE.search(s):
            facts.append(_fact("haemodynamic_instability", False, s, doc, "RULE", cue=R_STABLE.search(s).group(0)))
    return facts


def aggregate(facts: list, as_of: float) -> dict:
    """as_of 까지 이용 가능한 사실만. 같은 키에 서로 다른 값이면 CONFLICT(값 None). 결과: {키: {value, status, facts}}"""
    vis = [f for f in facts if f["available_time"] is not None and f["available_time"] <= as_of]
    out = {}
    for k in ("pretest", "suspected", "ddimer_assay", "ddimer_cutoff", "haemodynamic_instability"):
        fs = [f for f in vis if f["key"] == k]
        vals = {json_key(f["value"]) for f in fs}
        out[k] = {"value": fs[0]["value"] if len(vals) == 1 else None, "status": "FOUND" if len(vals) == 1 else "CONFLICT" if vals else "NOT_FOUND", "facts": fs}
    out["phase_signals"] = sorted({f["value"] for f in vis if f["key"] == "clinical_phase_signal"})
    out["treatment"] = [f["value"] | {"doc_id": f["doc_id"]} for f in vis if f["key"] == "treatment"]
    out["pe_episodes"] = [f["value"] | {"doc_id": f["doc_id"], "observation_time": f["observation_time"]} for f in vis if f["key"] == "pe_episode_statement"]
    out["unmapped"] = [f for f in vis if f["key"] in ("probability_score", "pretest_two_level_statement", "pretest_method")]
    return out


def json_key(v):
    return repr(sorted(v.items())) if isinstance(v, dict) else repr(v)
