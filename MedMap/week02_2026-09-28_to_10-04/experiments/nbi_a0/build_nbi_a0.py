#!/usr/bin/env python3
"""EXP-SN-NBI-001 NBI-A0 — deterministic implementation-conformance test.

ck-v0(동결 지식)에 manifest rev1 의 고정 규칙(R1–R3, CF1, PV1/PV2, 상태 규칙)을 적용해
NextInformationCandidate·SafetyNetReview(A0)를 만들고, 사전등록 expected_output.json 과 대조한다.
LLM 호출 0, 네트워크 0, 환자 데이터 0. 표준 라이브러리만 사용.

판정: CONFORMANT(출력 = 사전등록 예상) / NONCONFORMANT(불일치 → 구현 조사, 규칙 변경 금지) / INVALID.
출력은 가설 확증 증거가 아니다.
"""
import argparse
import csv
import hashlib
import itertools
import json
import os
import re
import sys

PAIRS = {"ACS~PE": ("ACS", "PE"), "ACS~PERI": ("ACS", "PERI")}
RULE_FIELDS = ["fact_id", "disease_or_pair", "relation_type", "favors", "finding_text",
               "finding_kind", "test_type", "quote", "unit_id"]
TYPE_BY_TEST = {"ECG": "ECG", "IMAGING": "IMAGING", "BIOMARKER": "BIOMARKER", "VITALS": "VITAL_SIGN",
                "PHYSICAL_EXAM": "PHYSICAL_EXAM", "RECORDS": "MEDICAL_RECORD"}
TYPE_BY_KIND = {"EXAM_SIGN": "PHYSICAL_EXAM", "SYMPTOM_HISTORY": "QUESTION", "RISK_FACTOR": "QUESTION",
                "DEMOGRAPHIC": "QUESTION", "TEST_RESULT": "OTHER", "OTHER": "OTHER"}
RELATION_CLASS = {"DIFFERENTIATING": "SOURCE_DIFFERENTIATING", "TEST_REQUIRED": "SOURCE_TEST_MENTION"}
RELATION_NOTE = {
    "SOURCE_DIFFERENTIATING": "ck-v0 extraction label DIFFERENTIATING; quote string verified only; "
                              "label correctness and diagnostic accuracy not verified",
    "SOURCE_TEST_MENTION": "ck-v0 extraction label TEST_REQUIRED; source mentions this test or procedure; "
                           "not evidence of clinical necessity",
}
# 역할명: 비임상·기술 표현 (rev2). R1 = 출처 추출 라벨이 DIFFERENTIATING 인 소견, R2/R3 = 출처의 검사 언급.
ROLE = {"R1": "SOURCE_LABELED_DISCRIMINATOR", "R2": "PAIR_LEVEL_TEST_MENTION", "R3": "DISEASE_LEVEL_TEST_MENTION"}
ROLE_NOTE = {
    "R1": "finding whose ck-v0 extraction label is DIFFERENTIATING for this pair; descriptive only; "
          "no claim of discrimination accuracy",
    "R2": "test or procedure mentioned by a source for this pair; outside the history-only scope; "
          "not a statement about what should be done",
    "R3": "test or procedure mentioned by a source for one disease of the pair; outside the history-only scope; "
          "not a statement about what should be done",
}
TARGET_ORIGIN = "CKV0_EXTRACTED_TEXT_LLM_GENERATED_NOT_VERBATIM"
STOP = {"on", "ecg", "the", "a", "an", "of", "in"}
PART_RE = re.compile(r" ?\(part \d+/\d+\) ?")
ID_RE = re.compile(r"^\[([^\]]+)\] ")
STRONG = [r"\bmust\b", r"\bshould\b", r"\brequire[sd]?\b", r"\brecommend\w*", r"\bindicated\b",
          r"\bmandatory\b", r"\bnecessary\b", r"\bessential\b", r"\bpreferred\b", r"\bfirst-line\b",
          r"\bwarrant\w*", r"\bperform\w*"]
PERMISSIVE = [r"\bcan\b", r"\bmay\b", r"\bcould\b", r"\bmight\b", r"\badvocated\b", r"\bsuggested\b",
              r"\bconsider(?:ed)?\b", r"\boption(?:al)?\b"]
FORBIDDEN = [r"REQUIRED_TEST", r"반드시", r"권고", r"오진", r"\brequired\b", r"\bmust\b", r"\brecommended\b",
             r"\brule out\b", r"\bdiagnose", r"\bmisdiagnos", r"\bneed(?:s|ed)?\b", r"\bnecessar",
             r"\bessential\b", r"\bindicated\b"]
# 금지어 검사 대상 = 스크립트가 생성한 값만. 면제 = ck-v0·원문에서 그대로 복사한 값(target_variable,
# finding_value, quote, ckv0_relation_type, unit_id, source_id, fact_id) 과 quote 에서 그대로 뽑은
# wording_markers(원문 단어 자체가 검사 대상 어휘이므로 면제).
GENERATED_FIELDS = ["candidate_id", "rule", "candidate_role", "role_note", "relation_class", "relation_label_note",
                    "information_type", "wording_class", "target_variable_origin", "mimic_available",
                    "mimic_dataset", "t0_leakage_note", "already_available_possible", "source_tier", "source_type"]
MIMIC = {  # 스키마·README 수준 고정표 (환자 행 미열람). 판정 미사용.
    "VITAL_SIGN": ("YES", "mimic-iv-ed triage/vitalsign",
                   "triage 행 기록 시각 컬럼 없음(intime 근사, 확인 필요); vitalsign 은 체류 전체 시계열 — 시간 창 고정 필요"),
    "ECG": ("PARTIAL", "mimic-iv-ecg-ext-icd ecg_time; 내용은 mimic-iv-ecg (미다운로드)",
            "ECG-Ext-ICD 같은 파일에 *_diag_*·dod·fold 존재 — 입력 금지; Cardiac Disease ECG/reports 는 퇴원요약 유래 — T0 입력 금지"),
    "BIOMARKER": ("UNKNOWN", "mimic-iv 3.1 hosp labevents (미다운로드)",
                  "결과 가용 시각 = storetime; Cardiac Disease labevents 는 입원 코호트·포함 기준 미확인"),
    "IMAGING": ("UNKNOWN", "mimic-iv-note radiology (미다운로드)",
                "Cardiac Disease X-ray/CT/Ultrasound/MRI 섹션은 퇴원요약 유래 — T0 입력 금지"),
    "PHYSICAL_EXAM": ("NO_TIMED", "Cardiac Disease physical_exam (퇴원요약)",
                      "퇴원요약 유래, 시점 없음 — T0 입력 금지; 활력 유사 EXAM_SIGN 은 triage 로 관측 가능할 수 있으나 A0 매핑은 필드 기준"),
    "MEDICAL_RECORD": ("UNKNOWN", "", "확인 필요"),
    "QUESTION": ("UNKNOWN", "", "DDXPlus 문항 응답은 MIMIC 에 없음"),
    "OTHER": ("UNKNOWN", "", "확인 필요"),
}
ALREADY_AVAILABLE = {"PHYSICAL_EXAM": "TRUE", "VITAL_SIGN": "TRUE", "QUESTION": "TRUE", "MEDICAL_RECORD": "TRUE"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check_sums(sumfile):
    """sha256sum 형식 목록의 모든 줄을 sumfile 디렉터리 기준으로 대조."""
    base = os.path.dirname(os.path.abspath(sumfile))
    n = 0
    for line in open(sumfile, encoding="utf-8"):
        if not line.strip():
            continue
        h, p = line.rstrip("\n").split(None, 1)
        p = p.lstrip("*")
        if sha256(os.path.join(base, p)) != h:
            raise SystemExit(f"INVALID: SHA mismatch {p} ({sumfile})")
        n += 1
    return n


def norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def jl(path):
    return [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]


def load_facts(path):
    """254행 → fact 단위 dedupe. RULE_FIELDS 9개만 동일성 assert (evidence_* 는 대응 행마다 다름)."""
    facts = {}
    for r in jl(path):
        k = r["fact_id"]
        if k in facts:
            for fld in RULE_FIELDS:
                if facts[k].get(fld) != r.get(fld):
                    raise SystemExit(f"INVALID: dedupe field mismatch {k}.{fld}")
        else:
            facts[k] = {fld: r.get(fld) for fld in RULE_FIELDS} | {"finding_value": r.get("finding_value")}
    return facts


def info_type(f):
    if f["test_type"] is not None:
        return TYPE_BY_TEST.get(f["test_type"], "OTHER")
    return TYPE_BY_KIND.get(f["finding_kind"], "OTHER")


def norm_cf1(text):
    toks = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split()
    out = []
    for t in toks:
        if t in STOP:
            continue
        if len(t) > 3 and t.endswith("s"):
            t = t[:-1]
        out.append(t)
    return " ".join(out)


def cf_match(a, b, mode):
    na, nb = norm_cf1(a), norm_cf1(b)
    if not na or not nb:  # 빈 정규화 문자열은 비교 제외
        return False
    if mode == "CF1":
        return na == nb
    ta, tb = set(na.split()), set(nb.split())  # CF2
    return len(ta & tb) >= 2 or ta <= tb or tb <= ta


def unit_texts(units_dir, listed=None):
    """v2 단위 본문: 같은 unit 의 part 를 파일·줄 순서대로 연결, part 표식 제거, 공백 정규화.
    listed 가 주어지면 input/*.txt 파일 집합이 SHA 목록의 input/ 줄과 같아야 한다."""
    parts = {}
    names = sorted(n for n in os.listdir(units_dir) if n.endswith(".txt"))
    if listed is not None and set(names) != set(listed):
        raise SystemExit("INVALID: unit file set differs from INPUT_SHA256SUMS")
    for name in names:
        for x in open(os.path.join(units_dir, name), encoding="utf-8"):
            m = ID_RE.match(x)
            if m:
                parts.setdefault(m.group(1), []).append(PART_RE.sub(" ", x[m.end():]))
    return {k: norm_ws(" ".join(v)) for k, v in parts.items()}


def pv2(f, ut):
    uid = PART_RE.sub("", f["unit_id"] or "")
    q = norm_ws(PART_RE.sub(" ", f["quote"] or ""))
    return bool(q) and uid in ut and q in ut[uid]


def pv2_source(f, ut):  # 보조(진단용): 같은 source 의 아무 unit 에서나
    q = norm_ws(PART_RE.sub(" ", f["quote"] or ""))
    src = f["unit_id"].split("#")[0]
    return bool(q) and any(q in t for k, t in ut.items() if k.split("#")[0] == src)


def wording(quote):
    """고정 어휘표로 서술 강도 분류. markers = quote 에서 실제로 일치한 단어(소문자)."""
    q = (quote or "").lower()
    s = sorted({m.group(0) for p in STRONG for m in re.finditer(p, q)})
    w = sorted({m.group(0) for p in PERMISSIVE for m in re.finditer(p, q)})
    cls = "MIXED" if s and w else "STRONG" if s else "PERMISSIVE" if w else "UNMARKED"
    return cls, s + w


def conflicts(c, facts, pair, mode):
    a, b = PAIRS[pair]
    other = b if c["favors"] == a else a
    scope = []
    for g in facts.values():
        if g["fact_id"] == c["fact_id"]:
            continue
        if g["disease_or_pair"] == pair and g["relation_type"] == "OVERLAPPING":
            scope.append(g)
        elif (g["disease_or_pair"] == pair and g["relation_type"] == "DIFFERENTIATING"
              and g["favors"] != c["favors"]):
            scope.append(g)
        elif mode == "CF2" and g["disease_or_pair"] == other and g["relation_type"] == "SUPPORTING":
            scope.append(g)
    return sorted(g["fact_id"] for g in scope if cf_match(c["finding_text"], g["finding_text"], mode))


def build(facts, precount, ut, tiers, rules=("R1", "R2", "R3"), cf="CF1", exclude=(), tiers_allowed=None):
    cands, reviews = [], []
    for pair, (a, b) in PAIRS.items():
        pc = []
        for f in sorted(facts.values(), key=lambda x: x["fact_id"]):
            rule = None
            if (f["relation_type"] == "DIFFERENTIATING" and f["disease_or_pair"] == pair
                    and f["favors"] in (a, b)):
                rule = "R1"
            elif f["relation_type"] == "TEST_REQUIRED" and f["disease_or_pair"] == pair:
                rule = "R2"
            elif f["relation_type"] == "TEST_REQUIRED" and f["disease_or_pair"] in (a, b):
                rule = "R3"
            if rule is None or rule not in rules or f["fact_id"] in exclude:
                continue
            src0 = f["unit_id"].split("#")[0]
            if tiers_allowed is not None and tiers.get(src0, ("UNKNOWN",))[0] not in tiers_allowed:
                continue
            it = info_type(f)
            cls = RELATION_CLASS[f["relation_type"]]
            wc, wm = wording(f["quote"]) if rule != "R1" else (None, [])
            cmode = cf if rule == "R1" and cf != "NONE" else None
            conf = conflicts(f, facts, pair, cmode) if cmode else []
            src = f["unit_id"].split("#")[0]
            pc.append({
                "candidate_id": f"NIC-{pair}-{f['fact_id']}",
                "pair": pair, "rule": rule,
                "candidate_role": ROLE[rule], "role_note": ROLE_NOTE[rule],
                "fact_id": f["fact_id"], "favors": f["favors"] if rule == "R1" else None,
                "target_disease": f["disease_or_pair"] if rule == "R3" else None,
                "information_type": it, "is_history": it == "QUESTION",
                "target_variable": f["finding_text"], "target_variable_origin": TARGET_ORIGIN,
                "finding_value": f["finding_value"],
                "ckv0_relation_type": f["relation_type"], "relation_class": cls,
                "relation_label_note": RELATION_NOTE[cls],
                "wording_class": wc, "wording_markers": wm,
                "source_id": src, "unit_id": f["unit_id"],
                "source_tier": tiers.get(src, ("UNKNOWN", "UNKNOWN"))[0],
                "source_type": tiers.get(src, ("UNKNOWN", "UNKNOWN"))[1],
                "quote_sha256": hashlib.sha256((f["quote"] or "").encode()).hexdigest(),
                "pv1": None, "pv2": pv2(f, ut), "pv2_source_level": pv2_source(f, ut),
                "conflict_mode": cmode, "conflicts_with": conf, "is_conflict": bool(conf),
                "already_available_possible": ALREADY_AVAILABLE.get(it, "UNKNOWN"),
                "mimic_available": MIMIC[it][0], "mimic_dataset": MIMIC[it][1], "t0_leakage_note": MIMIC[it][2],
                "research_only": True,
            })
        cands += pc
        for d in precount["pairs"][pair]:
            if not d.startswith("true="):
                continue
            n_u = precount["pairs"][pair][d]["n_U_possible"]
            true_d, wd = d[5:].split("|WD=")
            reviews.append({"pair": pair, "direction": d, "wd": wd, "alternative": true_d,
                            "history_scope": "DDXPlus 223-question observation space + ck-v0",
                            "history_evaluability": "EVALUABLE" if n_u > 0 else "INSUFFICIENT",
                            "n_U_possible": n_u})
    return cands, reviews


def finalize(cands, reviews, cite):
    for c in cands:
        c["pv1"] = bool(cite.get(c["fact_id"], False))
        c["pv_ok"] = c["pv1"] and c["pv2"]
    for r in reviews:
        pc = [c for c in cands if c["pair"] == r["pair"]]
        usable = [c for c in pc if not c["is_history"] and c["pv_ok"] and not c["is_conflict"]]
        if r["history_evaluability"] == "EVALUABLE":
            r["status"] = "HISTORY_EVALUABLE"
        else:
            r["status"] = "HISTORY_INSUFFICIENT" if usable else "ABSTAIN"
        r["next_information_candidates"] = [c["candidate_id"] for c in usable]
        r["n_by_rule"] = {k: sum(c["rule"] == k for c in usable) for k in ("R1", "R2", "R3")}
        r["r1_favors_wd"] = [c["candidate_id"] for c in usable if c["rule"] == "R1" and c["favors"] == r["wd"]]
        r["r1_favors_alternative"] = [c["candidate_id"] for c in usable
                                      if c["rule"] == "R1" and c["favors"] == r["alternative"]]
        r["R3_by_target_role"] = {
            "wd": sum(c["rule"] == "R3" and c["target_disease"] == r["wd"] for c in usable),
            "alternative": sum(c["rule"] == "R3" and c["target_disease"] == r["alternative"] for c in usable)}
    return cands, reviews


def grid_redundancy(cands, reviews):
    """정보 상태 격자: 관측 집합 O 의 모든 부분집합에서 type∈O 후보 출력 수 (구성상 0 기대)."""
    red, n_states = 0, 0
    by_id = {c["candidate_id"]: c for c in cands}
    for r in reviews:
        usable = [by_id[i] for i in r["next_information_candidates"]]
        types = sorted({c["information_type"] for c in usable})
        for k in range(len(types) + 1):
            for obs in itertools.combinations(types, k):
                n_states += 1
                nxt = [c for c in usable if c["information_type"] not in obs]
                red += sum(c["information_type"] in obs for c in nxt)
    return red, n_states


def forbidden_hits(cands, reviews):
    hits = []
    for c in cands:
        for fld in GENERATED_FIELDS:
            v = str(c.get(fld))
            for p in FORBIDDEN:
                if re.search(p, v, re.I):
                    hits.append((c["candidate_id"], fld, p))
    for r in reviews:
        for fld in ("status", "history_evaluability", "history_scope"):
            for p in FORBIDDEN:
                if re.search(p, str(r[fld]), re.I):
                    hits.append((r["pair"] + r["direction"], fld, p))
    return hits


def summarize(cands, reviews):
    s = {}
    for pair in PAIRS:
        pc = [c for c in cands if c["pair"] == pair]
        r1 = [c for c in pc if c["rule"] == "R1"]
        ok1 = [c for c in r1 if c["pv_ok"] and not c["is_conflict"]
               and c["information_type"] in ("ECG", "PHYSICAL_EXAM")]
        a, b = PAIRS[pair]
        s[pair] = {
            "R1_ids": sorted(c["fact_id"] for c in r1),
            "R1_conflict_ids": sorted(c["fact_id"] for c in r1 if c["is_conflict"]),
            "conflict_pairs": sorted([c["fact_id"], g] for c in r1 for g in c["conflicts_with"]),
            "favors_ids": {d: sorted(c["fact_id"] for c in ok1 if c["favors"] == d) for d in (a, b)},
            "n_favors": {d: sum(c["favors"] == d for c in ok1) for d in (a, b)},
            "favors_unique_source_ids": {d: sorted({c["source_id"] for c in ok1 if c["favors"] == d}) for d in (a, b)},
            "favors_unique_unit_ids": {d: sorted({c["unit_id"] for c in ok1 if c["favors"] == d}) for d in (a, b)},
            "R2_ids": sorted(c["fact_id"] for c in pc if c["rule"] == "R2"),
            "n_R2_usable": sum(c["rule"] == "R2" and c["pv_ok"] and not c["is_conflict"] and not c["is_history"]
                               for c in pc),
            "R2_types": count(c["information_type"] for c in pc if c["rule"] == "R2"),
            "R3_by_target": {d: sum(c["rule"] == "R3" and c["target_disease"] == d for c in pc) for d in (a, b)},
            "R3_types_by_target": {d: count(c["information_type"] for c in pc
                                            if c["rule"] == "R3" and c["target_disease"] == d) for d in (a, b)},
            "pv_fail_ids": sorted(c["fact_id"] for c in pc if not c["pv_ok"]),
            "status": {r["direction"]: r["status"] for r in reviews if r["pair"] == pair},
        }
    return s


def count(it):
    out = {}
    for x in it:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items()))


def h_verdicts(s):
    p = s["ACS~PERI"]
    q = s["ACS~PE"]
    # H1: ACS~PERI 에서 pv_ok·non-CONFLICT·ECG/PHYSICAL_EXAM R1 이 favors=ACS ≥1 그리고 favors=PERI ≥1.
    # H2: ACS~PE 에서 R1 0개 ∧ true=ACS|WD=PE status = HISTORY_INSUFFICIENT ∧ pv_ok·non-CONFLICT·비병력 R2 ≥1.
    h1 = p["n_favors"]["ACS"] >= 1 and p["n_favors"]["PERI"] >= 1
    h2 = (not q["R1_ids"] and q["status"].get("true=ACS|WD=PE") == "HISTORY_INSUFFICIENT"
          and q["n_R2_usable"] >= 1)
    return {"H1": "PASS" if h1 else "FAIL", "H2": "PASS" if h2 else "FAIL"}


def run_all(facts, precount, ut, tiers, cite):
    out = {}
    cfg = {"AB3_CF1": dict(rules=("R1", "R2", "R3"), cf="CF1"),
           "AB1_R1_only": dict(rules=("R1",), cf="CF1"),
           "AB2_R1_R2": dict(rules=("R1", "R2"), cf="CF1"),
           "AB4_no_CF": dict(rules=("R1", "R2", "R3"), cf="NONE"),
           "AB5_known_conflict_excluded": dict(rules=("R1", "R2", "R3"), cf="CF1",
                                               exclude=("A1b3-0046", "A1b3-0047")),
           "AB6_tier1_only": dict(rules=("R1", "R2", "R3"), cf="CF1", tiers_allowed=("TIER1",)),
           "CF2_sensitivity": dict(rules=("R1", "R2", "R3"), cf="CF2")}
    main = None
    for name, kw in cfg.items():
        c, r = finalize(*build(facts, precount, ut, tiers, **kw), cite)
        s = summarize(c, r)
        out[name] = {"summary": s, "H": h_verdicts(s)}
        if name == "AB3_CF1":
            main = (c, r)
    return out, main


def compare(expected, actual, path=""):
    """expected 에 적힌 키만 대조. 차이 목록 반환."""
    diffs = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [(path, expected, actual)]
        for k, v in expected.items():
            if k.startswith("_"):
                continue
            diffs += compare(v, actual.get(k) if isinstance(actual, dict) else None, f"{path}/{k}")
        return diffs
    return [] if expected == actual else [(path, expected, actual)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckv0", required=True)
    ap.add_argument("--ckv0-sha", required=True)
    ap.add_argument("--units-sums", required=True, help="stage1/INPUT_SHA256SUMS")
    ap.add_argument("--units-sums-sha", required=True)
    ap.add_argument("--t0-forbidden-ref", required=True, help="설계 문서 경로 (§13 T0 금지 필드)")
    ap.add_argument("--t0-forbidden-ref-sha", required=True)
    ap.add_argument("--coverage", required=True)
    ap.add_argument("--coverage-sha", required=True)
    ap.add_argument("--expected", required=True)
    ap.add_argument("--expected-sha", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    if os.path.exists(a.out):
        raise SystemExit(f"INVALID: output dir exists {a.out}")
    check_sums(os.path.join(a.ckv0, "CKV0_SHA256SUMS"))
    ck = os.path.join(a.ckv0, "ck-v0.jsonl")
    for p, h in ((ck, a.ckv0_sha), (a.coverage, a.coverage_sha), (a.expected, a.expected_sha),
                 (a.units_sums, a.units_sums_sha), (a.t0_forbidden_ref, a.t0_forbidden_ref_sha)):
        if sha256(p) != h:
            raise SystemExit(f"INVALID: SHA mismatch {p}")
    check_sums(a.units_sums)
    units_dir = os.path.join(os.path.dirname(os.path.abspath(a.units_sums)), "input")
    listed = [ln.split(None, 1)[1].strip().lstrip("*")[len("input/"):]
              for ln in open(a.units_sums, encoding="utf-8")
              if ln.strip() and ln.split(None, 1)[1].strip().lstrip("*").startswith("input/")]

    facts = load_facts(ck)
    precount = json.load(open(os.path.join(a.ckv0, "precount.json"), encoding="utf-8"))
    cite = {r["fact_id"]: r["quote_match"]
            for r in json.load(open(os.path.join(a.ckv0, "citation_check.json"), encoding="utf-8"))["rows"]}
    tiers = {}
    with open(a.coverage, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tiers.setdefault(row["source_id"], (row["tier"], row["source_type"]))
    ut = unit_texts(units_dir, listed)

    res, (cands, reviews) = run_all(facts, precount, ut, tiers, cite)
    red, n_states = grid_redundancy(cands, reviews)
    hits = forbidden_hits(cands, reviews)
    wording_dist = count(c["wording_class"] for c in cands if c["rule"] in ("R2", "R3"))
    actual = {"ablations": {k: v["summary"] for k, v in res.items()},
              "H": {k: v["H"] for k, v in res.items()},
              "grid_redundant": red, "forbidden_hits": len(hits),
              "pv1_pv2_disagree": sorted(c["fact_id"] for c in cands if c["pv1"] != c["pv2"])}
    expected = json.load(open(a.expected, encoding="utf-8"))
    diffs = compare(expected, actual)
    invalid = red != 0 or hits
    verdict = "INVALID" if invalid else ("CONFORMANT" if not diffs else "NONCONFORMANT")

    os.makedirs(a.out)
    with open(os.path.join(a.out, "nbi_a0_candidates.jsonl"), "w", encoding="utf-8") as f:
        for c in cands:
            f.write(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n")
    json.dump(reviews, open(os.path.join(a.out, "nbi_a0_review.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    report = {"verdict": verdict, "diffs": [list(map(str, d)) for d in diffs],
              "forbidden_hit_list": hits, "grid_states": n_states, "wording_distribution_R2_R3": wording_dist,
              "actual": actual, "note": "conformance test only; not evidence for hypotheses",
              "python_version": sys.version.split()[0],
              "inputs": {"ckv0_sha256": a.ckv0_sha, "coverage_sha256": a.coverage_sha,
                         "expected_sha256": a.expected_sha, "units_sums_sha256": a.units_sums_sha,
                         "t0_forbidden_ref": os.path.basename(a.t0_forbidden_ref),
                         "t0_forbidden_ref_sha256": a.t0_forbidden_ref_sha,
                         "script_sha256": sha256(os.path.abspath(__file__))}}
    json.dump(report, open(os.path.join(a.out, "nbi_a0_report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    with open(os.path.join(a.out, "NBI_A0_SHA256SUMS"), "w", encoding="utf-8") as f:
        for n in ("nbi_a0_candidates.jsonl", "nbi_a0_review.json", "nbi_a0_report.json"):
            f.write(f"{sha256(os.path.join(a.out, n))}  {n}\n")
    print(f"NBI_A0_VERDICT {verdict} diffs={len(diffs)} forbidden={len(hits)} grid_redundant={red}")
    return 0 if verdict == "CONFORMANT" else 2


if __name__ == "__main__":
    sys.exit(main())
