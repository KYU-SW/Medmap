"""Generic regex/rule baseline: ClinicalTrials.gov eligibility text -> criteria tree (same DSL as gold).
Written before seeing experiment results. Not tuned per trial. Input text is untrusted data (parsed only).
Strategy (typical rule-based extractor):
  - split inclusion / exclusion at the first 'Exclusion' header
  - per bullet/line, detect lab mention, parse numeric bounds; inclusion bounds per lab are merged as a UNION
    interval (min lower, max upper) -> disjunctions get flattened (known weakness of flat extraction)
  - exclusion numeric: 'HbA1c > 12', 'potassium > 5.5' become exclusion atoms
  - keyword atoms for diagnoses / treatments / time windows
"""
import json
import re

LABS = {
    "egfr": r"\beGFR\b|glomerular filtration",
    "uacr": r"\bUACR\b|albumin\s*(?:to|:)?\s*creatinine ratio",
    "hba1c": r"HbA1c|\bA1C\b|glycated ha?emoglobin|glycosylated ha?emoglobin",
    "k": r"potassium",
    "age": r"\baged?\b|years of age|\bage\b",
}
NUM = r"(\d+(?:\.\d+)?)"
# normalise escaped symbols used by ClinicalTrials.gov markdown
def norm(s):
    s = s.replace("\\>", ">").replace("\\<", "<").replace("\\^", "^")
    s = re.sub(r"greater than or equal to|above or equal to|≥", ">=", s)
    s = re.sub(r"less than or equal to|≤", "<=", s)
    s = re.sub(r"greater than|above", ">", s)
    s = re.sub(r"less than|below", "<", s)
    return s

def bounds_in(seg):
    """return list of (cmp, value) found in a text segment"""
    out = []
    seg = norm(seg)
    # 'X to <Y' / 'X to Y' / 'X-Y' ranges
    for m in re.finditer(NUM + r"\s*(?:%|mL/min[^ ]*|mg/g|mmol/L)?\s*(?:to|-|–|and)\s*(<=|<)?\s*" + NUM, seg):
        lo, cmp_hi, hi = float(m.group(1)), m.group(2) or "<=", float(m.group(3))
        if lo < hi:
            out.append((">=", lo)); out.append((cmp_hi, hi))
    for m in re.finditer(r"(>=|<=|>|<)\s*\(?\s*" + NUM, seg):
        out.append((m.group(1), float(m.group(2))))
    return out

def lines(text):
    return [l.strip(" *-\t") for l in re.split(r"\n|(?<=\s)-\s(?=[A-Z])", text) if l.strip(" *-\t")]

def extract(text):
    parts = re.split(r"(?i)\bkey exclusion criteria\b|\bexclusion criteria\b", text, maxsplit=1)
    inc, exc = parts[0], parts[1] if len(parts) > 1 else ""
    inc_atoms, exc_atoms = [], []
    union = {}
    for l in lines(inc):
        for lab, pat in LABS.items():
            for m in re.finditer(pat, l, flags=re.I):
                seg = l[m.end(): m.end() + 80]  # look right of the mention only
                for cmp_, val in bounds_in(seg):
                    if lab == "age" and not (10 <= val <= 100):
                        continue
                    lo, hi = union.setdefault(lab, [None, None])
                    if cmp_ in (">=", ">"):
                        if lo is None or val < lo[1]:
                            union[lab][0] = (cmp_, val)
                    else:
                        if hi is None or val > hi[1]:
                            union[lab][1] = (cmp_, val)
        if re.search(r"type 2 diabetes|\bT2DM?\b|type type 2", l, re.I):
            inc_atoms.append({"v": "t2d", "eq": "Y"})
        if re.search(r"\bACE|angiotensin|\bARB\b|RAAS|RAS-inhibition", l, re.I):
            inc_atoms.append({"v": "acei_arb", "eq": "Y"})
    for lab, (lo, hi) in union.items():
        if lo: inc_atoms.append({"v": lab, "cmp": lo[0], "x": lo[1]})
        if hi: inc_atoms.append({"v": lab, "cmp": hi[0], "x": hi[1]})
    for l in lines(exc):
        nl = norm(l)
        for lab in ("hba1c", "k"):
            if re.search(LABS[lab], l, re.I):
                for cmp_, val in bounds_in(l[re.search(LABS[lab], l, re.I).end():][:60]):
                    if cmp_ in (">", ">="):
                        exc_atoms.append({"v": lab, "cmp": cmp_, "x": val})
        if re.search(r"systolic", l, re.I):
            for m in re.finditer(r"SBP\)?\s*(>=|<=|>|<)\s*" + NUM, nl):
                exc_atoms.append({"v": "sbp", "cmp": m.group(1), "x": float(m.group(2))})
        if re.search(r"dialysis", l, re.I):
            exc_atoms.append({"v": "dialysis", "eq": "Y"})
        if re.search(r"transplant|allograft", l, re.I):
            exc_atoms.append({"v": "transplant", "eq": "Y"})
        if re.search(r"type 1 diabetes", l, re.I):
            exc_atoms.append({"v": "t1d", "eq": "Y"})
        if re.search(r"NYHA|New York Heart", l, re.I) and re.search(r"\bIV\b|class 4", l):
            exc_atoms.append({"v": "nyha", "cmp": ">=", "x": 4})
        if re.search(r"SGLT", l, re.I) and re.search(r"receiv|current|within", l, re.I):
            exc_atoms.append({"v": "sglt2_current", "eq": "Y"})
        if re.search(r"GLP-1|glucagon-like", l, re.I):
            m = re.search(NUM + r"\s*days", l)
            if m: exc_atoms.append({"v": "glp1_days", "cmp": "<=", "x": float(m.group(1))})
        if re.search(r"myocardial infarction|\bMI\b|stroke|acute coronary", l, re.I):
            m = re.search(NUM + r"\s*(days|weeks)", l)
            if m:
                d = float(m.group(1)) * (7 if m.group(2) == "weeks" else 1)
                exc_atoms.append({"v": "recent_cv_days", "cmp": "<=", "x": d})
    # de-duplicate
    def dd(xs):
        seen, out = set(), []
        for a in xs:
            k = json.dumps(a, sort_keys=True)
            if k not in seen:
                seen.add(k); out.append(a)
        return out
    return {"inclusion": {"and": dd(inc_atoms)}, "exclusion": dd(exc_atoms)}
