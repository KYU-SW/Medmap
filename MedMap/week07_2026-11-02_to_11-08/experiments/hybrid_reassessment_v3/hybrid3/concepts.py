"""기능 A·C: 문장 해석과 개념 연결. P2 parser·lexicon·finding_state 를 그대로 쓰고, 그 위에
(1) PE 하위형·근위부 DVT·항응고 치료 등 추가 표현, (2) 문서 안 약어 정의, (3) 약어 풀이(용어 목록) 구분을 더한다.
유사 매칭 없음. 처음 보는 표현은 연결하지 않는다."""
from __future__ import annotations

import re
import sys
from pathlib import Path

V2 = Path(__file__).resolve().parents[2] / "hybrid_reassessment_v2"
if str(V2) not in sys.path:
    sys.path.insert(0, str(V2))

from hybrid2_p2 import clinical_context as CC_MOD, evidence_conditions as EC_MOD, lexicon as LX, parser as PS, pipeline as P2, relations as RLX  # noqa: E402,F401

# 하위 개념은 parent 로 관계를 조회하고 subtype 을 따로 보존(동일 개념으로 합치지 않음)
EXTRA = {
    "PE_SUBSEGMENTAL": {"parent": "PE_DIAGNOSIS", "kind": "DISEASE_SUBTYPE",
                        "terms": ["subsegmental pulmonary embolism", "subsegmental pulmonary emboli", "subsegmental pulmonary embolus", "sub-segmental pulmonary embolism",
                                  "isolated subsegmental pulmonary embolism", "subsegmental pulmonary embolisms"]},
    "PE_RECURRENT": {"parent": "PE_DIAGNOSIS", "kind": "DISEASE_EPISODE_QUALIFIER",
                     "terms": ["recurrent pulmonary embolism", "recurrent pulmonary emboli", "recurrent pulmonary embolus", "recurrence of pulmonary embolism"]},
    "DVT_PROXIMAL": {"parent": "DVT", "kind": "FINDING_SUBTYPE", "terms": ["proximal deep vein thrombosis", "proximal deep venous thrombosis", "proximal dvt"]},
    "FILLING_DEFECT": {"kind": "FINDING", "terms": ["pulmonary arterial filling defect", "pulmonary arterial filling defects", "pulmonary artery filling defect",
                                                    "pulmonary artery filling defects", "intraluminal filling defect", "intraluminal filling defects"]},
    "CTPA_STUDY": {"kind": "TEST", "terms": ["computed tomography pulmonary angiogram", "computed tomographic pulmonary angiogram", "ct pulmonary angiograms",
                                             "ct pulmonary arteriography", "ctpa scan"]},
    "ANTICOAGULATION": {"kind": "TREATMENT", "terms": ["anticoagulation", "anticoagulant therapy", "anticoagulant treatment", "anticoagulants", "anticoagulant",
                                                       "apixaban", "rivaroxaban", "dabigatran", "edoxaban", "warfarin", "heparin", "unfractionated heparin", "enoxaparin",
                                                       "low-molecular-weight heparin", "low molecular weight heparin", "lmwh", "doac", "doacs", "fondaparinux"]},
    "THROMBOLYSIS": {"kind": "TREATMENT", "terms": ["thrombolysis", "systemic thrombolysis", "thrombolytic therapy", "alteplase"]},
}
KIND = {"PE_DIAGNOSIS": "DISEASE", "DDIMER": "TEST", "CTPA_STUDY": "TEST", "PERFUSION_SCAN": "TEST", "ULTRASOUND": "TEST", "FILLING_DEFECT": "FINDING", "DVT": "FINDING",
        "PERICARDITIS_DIAGNOSIS": "DISEASE", "MYOCARDITIS_DIAGNOSIS": "DISEASE", "TB_DIAGNOSIS": "DISEASE"}
AMBIG_EXTRA = {r"\bsspe\b": "SSPE 약어(문서 정의 필요)", r"\bvte\b": "VTE 약어(PE·DVT 포괄)"}
R_DEF_PAREN = re.compile(r"([A-Za-z][A-Za-z\- ]{3,80}?)\s*\(\s*([A-Z][A-Za-z]{1,6})\s*\)")
R_TEST_LIKE = re.compile(r"\b[a-z]{4,}(?:graphy|gram|scopy|scan)\b|\b(?:MRI|PET|EKG|ECG|echo)\b", re.I)   # 사전에 없는 검사명 표시용(연결하지 않음)
R_PE_DOC = re.compile(r"pulmonary (?:thrombo)?embol|\b(?:Wells|Geneva)\b|\bCTPA\b|ct pulmonary angiogra|computed tomograph\w* pulmonary angiogra", re.I)
R_PE_EXAM = re.compile(r"\b(?i:on|during|at)\s+PE\b|\bPE\s*:|\bPE\s+(?:was|is|were)\s+(?:unremarkable|normal|notable|significant)\b|\bPE\s+(?:showed|revealed|demonstrated)\b")
R_DEF_LEGEND = re.compile(r"\b([A-Z][A-Za-z]{1,6})\s*[:=,]\s*([A-Za-z][A-Za-z\- ]{3,80})")


def table() -> dict:
    t = dict(LX.lexicon()[0])
    for c, d in EXTRA.items():
        for term in d["terms"]:
            t[term] = (c, "V3_DEFINED")
    return t


_TABLE = None


def _tbl() -> dict:
    global _TABLE
    if _TABLE is None:
        _TABLE = table()
    return _TABLE


def _lookup_long(phrase: str, anchor: str = "end") -> str | None:
    """정의 문구의 약어 쪽 끝에 붙은 가장 긴 사전 구문. 괄호 정의는 괄호 바로 앞(end), 용어 목록은 기호 바로 뒤(start)."""
    toks = LX.TOKEN.findall(phrase.lower())
    for n in range(min(len(toks), 7), 0, -1):
        seg = toks[-n:] if anchor == "end" else toks[:n]
        hit = _tbl().get(" ".join(seg))
        if hit and hit[1] != "HPO":
            return hit[0]
    return None


def _initial_ok(abbr: str, long: str) -> bool:
    w = [x for x in re.split(r"[\s\-]+", long.strip()) if x]
    return bool(w) and any(x[0].lower() == abbr[0].lower() for x in w[-6:])


def abbreviations(text: str) -> dict:
    """문서 안 약어 정의 → {약어: (개념, 근거 문구, 정의 형식)}. 정의가 없으면 약어를 해소하지 않는다."""
    out = {}
    for m in R_DEF_PAREN.finditer(text):
        long, ab = m.group(1), m.group(2)
        c = _lookup_long(long)
        if c and _initial_ok(ab, long) and ab.lower() not in ("ct",):
            out.setdefault(ab, (c, m.group(0)[-120:], "PAREN"))
    for m in R_DEF_LEGEND.finditer(text):
        ab, long = m.group(1), m.group(2)
        c = _lookup_long(long[:60], "start")
        if c and _initial_ok(ab, long[:40]) and ab.lower() not in ("ct",):
            out.setdefault(ab, (c, m.group(0)[:120], "LEGEND"))
    return out


def legend_spans(sentence: str) -> list:
    """'CTPA: computed tomography ...', 'SSPE: subsegmental ...' 처럼 용어 목록 형식인 구간. 이 안의 언급은 검사·진단 근거가 아님."""
    spans = []
    for m in R_DEF_LEGEND.finditer(sentence):
        ab, long = m.group(1), m.group(2)
        c = _lookup_long(long[:60], "start")
        if not (c and _initial_ok(ab, long[:40])):
            continue
        toks = list(LX.TOKEN.finditer(sentence[m.start(2):].lower()))
        end = m.start(2)
        for n in range(min(len(toks), 7), 0, -1):                       # 정의 문구는 사전 구문 1개까지
            seg = " ".join(t.group(0) for t in toks[:n])
            if _tbl().get(seg, (None,))[0] == c:
                end = m.start(2) + toks[n - 1].end()
                break
        spans.append((m.start(1), end, ab, c))
    return spans


def find_mentions(clause: str, abbr: dict) -> list:
    """P2 와 같은 긴 구문 우선 정확 일치 + 문서 정의 약어(대소문자 일치). [(시작, 끝, 표현, 개념, 종류)]"""
    tbl = _tbl()
    low = clause.lower()
    toks = list(LX.TOKEN.finditer(low))
    out, used = [], set()
    for n in range(7, 0, -1):
        for i in range(len(toks) - n + 1):
            s, e = toks[i].start(), toks[i + n - 1].end()
            if any(x in used for x in range(s, e)):
                continue
            hit = tbl.get(low[s:e])
            if hit:
                used.update(range(s, e))
                out.append((s, e, clause[s:e], hit[0], hit[1]))
    for ab, (c, _, _) in abbr.items():
        for m in re.finditer(r"\b" + re.escape(ab) + r"\b", clause):
            if not any(x in used for x in range(m.start(), m.end())):
                used.update(range(m.start(), m.end()))
                out.append((m.start(), m.end(), m.group(0), c, "DOC_ABBREVIATION"))
    return sorted(out)


def _rec(c, s, e, surface, concept, kind_src, assertion, cue, has_ctpa, legend, offset):
    base = EXTRA.get(concept, {}).get("parent", concept)
    sub = concept if base != concept else ""
    kind = EXTRA.get(concept, {}).get("kind") or KIND.get(base) or ("HPO_FINDING" if base.startswith("HP:") else "OTHER")
    in_legend = any(a <= offset + s and offset + e <= b for a, b, *_ in legend)
    return {"text": c.text, "sentence": c.sentence, "section": c.section, "surface": surface, "concept": base, "subtype": sub, "concept_kind": kind,
            "lexicon": kind_src, "assertion": assertion, "cue": cue, "link_status": "LINKED", "role": "DEFINITION_ONLY" if in_legend else "MENTION",
            "graph_node": LX.graph_node(base) if LX.graph_node(base) in LX.lexicon()[1] else "", "codes": LX.codes(base) if base in LX.DEFINED or base.startswith("HP:") else {},
            "ctpa_context": has_ctpa, "char_span": [offset + s, offset + e]}


def extract(text: str, doc_type: str = "", abbr: dict | None = None) -> list:
    """P2.extract 와 같은 순서(절 분리 → 언급 → 언급 상태 → CTPA 맥락 → PE 약어)에 v3 사전·문서 약어·용어 목록 구분을 더함."""
    abbr = abbreviations(text) if abbr is None else abbr
    pe_doc = bool(R_PE_DOC.search(text))                                # 문서에 PE 고유 단서가 있을 때만 'PE' 약어 해소(신체검진 표기 제외)
    out = []
    for c in PS.split_clauses(text):
        legend = legend_spans(c.sentence)
        off = max(c.sentence.find(c.text), 0)
        mentions = find_mentions(c.text, abbr)
        sent_mentions = find_mentions(c.sentence, abbr)
        has_ctpa = doc_type == "CTPA_REPORT" or any(m[3] == "CTPA_STUDY" and not any(a <= m[0] and m[1] <= b for a, b, *_ in legend) and not P2._abbreviation_legend(c.sentence, m[0], m[1])
                                                     for m in sent_mentions)
        for s, e, surface, concept, kind in mentions:
            a, cue = PS.classify_assertion(c, s, e)
            if concept == "CTPA_STUDY" and a == PS.NEGATED:
                a, cue = PS.PRESENT, "STUDY_NAME"
            out.append(_rec(c, s, e, surface, concept, kind, a, cue, has_ctpa, legend, off))
        amb = LX.find_ambiguous(c.text, mentions) + [(m.start(), m.end(), c.text[m.start():m.end()], why) for pat, why in AMBIG_EXTRA.items()
                                                      for m in re.finditer(pat, c.text.lower()) if not any(s <= m.start() and m.end() <= e for s, e, *_ in mentions)]
        for s, e, surface, why in amb:
            if surface == "PE" and (has_ctpa or (pe_doc and not R_PE_EXAM.search(c.sentence))):
                a, cue = PS.classify_assertion(c, s, e)
                out.append(_rec(c, s, e, surface, "PE_DIAGNOSIS", "ABBREVIATION_IN_CTPA_CONTEXT" if has_ctpa else "ABBREVIATION_DOC_PE_CONTEXT", a, cue, has_ctpa, legend, off))
                continue
            r = _rec(c, s, e, surface, "", "", PS.classify_assertion(c, s, e)[0], why, has_ctpa, legend, off)
            r.update(link_status="AMBIGUOUS", concept_kind="UNRESOLVED", graph_node="", codes={})
            out.append(r)
        for m in R_TEST_LIKE.finditer(c.text):                           # 사전에 없는 검사명: 비슷한 개념에 붙이지 않고 '지원 안 함'으로 표시
            if not any(s <= m.start() < e for s, e, *_ in mentions):
                r = _rec(c, m.start(), m.end(), m.group(0), "", "", PS.classify_assertion(c, m.start(), m.end())[0], "NOT_IN_LEXICON", has_ctpa, legend, off)
                r.update(link_status="UNSUPPORTED", concept_kind="UNSUPPORTED_TEST_OR_PROCEDURE", graph_node="", codes={})
                out.append(r)
    return out


def finding_state(rec: dict) -> dict:
    """P2 finding_state + v3 보정: 용어 목록 안 언급 제외, 아분절 하위형은 수준 정보로 사용."""
    if rec.get("role") == "DEFINITION_ONLY":
        return {"reason": "ABBREVIATION_DEFINITION_ONLY"}
    if rec.get("link_status") == "UNSUPPORTED":
        return {"reason": "CONCEPT_NOT_SUPPORTED"}
    fs = P2.finding_state(rec)
    if fs.get("finding") == "CTPA_REPORTS_PE" and rec.get("subtype") == "PE_SUBSEGMENTAL":
        fs = {**fs, "level": "SUBSEGMENTAL"}
    return fs
