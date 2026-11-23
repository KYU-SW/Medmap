"""Shadow 임상 맥락. v4 가 이미 추출한 CONTEXT_FACT(검사 전 확률·도구·D-dimer 검사법·혈역학 문구·치료)를 그대로 쓰고,
v4 가 추출하지 않는 항목만 연구용 정규식으로 같은 기록 원문에서 읽는다(레거시와 같은 입력).
- 검사 전 확률: 값·도구·시각·출처를 보존한 관측 목록. 2단계(PE likely/unlikely)는 3단계와 섞지 않는 별도 키.
- 혈역학: 명시 문구(안정/불안정, 심정지·CPR — Table 4 행 제목)만 판정. 혈압·승압제·저관류 조합은 원문 행 구조를 확정하지 못해(평탄화된 표) 판정하지 않고 기록만.
- YEARS: 항목 수 + D-dimer 수치·단위(µg/L, ng/mL — 1 ng/mL = 1 µg/L). FEU/DDU 미기재는 주석.
미확인 조건은 만족으로 처리하지 않는다(NOT_FOUND 로 둠)."""
from __future__ import annotations

import re

from hybrid4 import graphs as GR
from hybrid4 import logic as LG

R_TWO = re.compile(r"\b(?:PE|pulmonary embolism)\s+(?:was\s+|is\s+)?(?:considered\s+|deemed\s+|classified\s+as\s+)?(unlikely|likely)\b|\bPE[- ](unlikely|likely)\b", re.I)
R_ARREST = re.compile(r"\b(cardiac arrest|cardiopulmonary resuscitation|CPR)\b", re.I)
R_OBS_SHOCK = re.compile(r"\bobstructive shock\b", re.I)
R_SBP = re.compile(r"\b(?:blood pressure|BP|systolic(?: blood pressure)?)\D{0,15}(\d{2,3})\s*(?:/\s*\d{2,3})?\s*mm ?Hg", re.I)
R_VASO = re.compile(r"\b(norepinephrine|noradrenaline|vasopressors?|dopamine|epinephrine|adrenaline)\b", re.I)
R_HYPOPERF = re.compile(r"\b(altered mental status|cold,? clammy skin|oliguria|anuria|lactate\s*(?:of\s*)?\d)", re.I)
R_INPATIENT = re.compile(r"\b(hospitali[sz]ed|inpatient|in-hospital|admitted\s+(?:for|since)\s+\d|hospital day\s*\d)", re.I)
R_PREG = re.compile(r"\b(pregnan\w*|gestation(?:al)?\s+week|weeks?\s+of\s+gestation)\b", re.I)
R_PREG_NEG = re.compile(r"\b(not pregnant|no pregnancy|pregnancy test (?:was )?negative)\b", re.I)
R_YEARS = re.compile(r"\b(no|zero|one|two|three|\d)\s+YEARS\s+(?:items?|criteria|criterion)\b", re.I)
R_DD_NUM = re.compile(r"\bD-?dimer\b[^.;]{0,40}?(\d+(?:\.\d+)?)\s*(µg/L|μg/L|ug/L|ng/mL|mg/L|µg/mL|μg/mL)?", re.I)
R_HS_ASSAY = re.compile(r"\b(high[- ]sensitivity|highly sensitive)\s+(?:D-?dimer\s+)?assay\b", re.I)
WORDS = {"no": 0, "zero": 0, "one": 1, "two": 2, "three": 3}


def pretest_observations(facts: list) -> list:
    """v4 CONTEXT_FACT → 검사 전 확률 관측(값·도구·시각·출처). 도구는 같은 기록의 pretest_method."""
    meth = {f["source_record_id"]: f["value"] for f in facts if f["key"] == "pretest_method"}
    return sorted([{"value": f["value"], "tool": meth.get(f["source_record_id"], "NOT_STATED"), "available_time": f["available_time"], "source_record_id": f["source_record_id"],
                    "scale": "THREE_LEVEL"} for f in facts if f["key"] == "pretest"], key=lambda x: (str(x["available_time"]), x["source_record_id"]))


def scan_records(records: list) -> dict:
    """같은 기록 원문(에피소드·as_of 공개분)에서 v4 미추출 항목. records: [{record_id, text, available_time}]."""
    out = {"two_level": [], "arrest": [], "obstructive_shock": [], "vitals": [], "inpatient": [], "pregnant": [], "not_pregnant": [], "years": [], "ddimer_values": [], "hs_assay": []}
    for r in sorted(records, key=lambda r: r["record_id"]):
        t, rid = r["text"], r["record_id"]
        for m in R_TWO.finditer(t):
            out["two_level"].append({"value": (m.group(1) or m.group(2)).upper(), "source_record_id": rid, "available_time": r["available_time"], "scale": "TWO_LEVEL"})
        if R_ARREST.search(t):
            out["arrest"].append(rid)
        if R_OBS_SHOCK.search(t):
            out["obstructive_shock"].append(rid)
        sbp = [int(m.group(1)) for m in R_SBP.finditer(t)]
        if sbp or R_VASO.search(t) or R_HYPOPERF.search(t):
            out["vitals"].append({"source_record_id": rid, "sbp": sbp, "vasopressor": bool(R_VASO.search(t)), "hypoperfusion_terms": [m.group(1) for m in R_HYPOPERF.finditer(t)],
                                  "status": "RECORDED_NOT_ADJUDICATED(Table 4 행 구조 미확정)"})
        if R_INPATIENT.search(t):
            out["inpatient"].append(rid)
        if R_PREG_NEG.search(t):
            out["not_pregnant"].append(rid)
        elif R_PREG.search(t):
            out["pregnant"].append(rid)
        for m in R_YEARS.finditer(t):
            w = m.group(1).lower()
            out["years"].append({"items": WORDS.get(w, int(w) if w.isdigit() else None), "source_record_id": rid})
        for m in R_DD_NUM.finditer(t):
            out["ddimer_values"].append({"value": float(m.group(1)), "unit": (m.group(2) or "NOT_STATED"), "source_record_id": rid})
        if R_HS_ASSAY.search(t):
            out["hs_assay"].append(rid)
    return out


def _fact(key, vals, srcs):
    vals = list(dict.fromkeys(vals))
    if not vals:
        return LG.Fact(key, "NOT_FOUND")
    if len(vals) > 1:
        return LG.Fact(key, "CONFLICT", None, tuple(vals), tuple(srcs))
    return LG.Fact(key, "FOUND", vals[0], tuple(vals), tuple(srcs))


def haemo_state(agg: dict, scan: dict) -> tuple:
    """명시 문구만: v4 haemodynamic_instability 사실 + 심정지·CPR·폐쇄성 쇼크 문구(Table 4 행 제목)."""
    vals, srcs = [], []
    hi = agg["haemodynamic_instability"]
    if hi.status == "FOUND":
        vals.append("UNSTABLE" if hi.value else "STABLE")
        srcs += list(hi.sources)
    elif hi.status == "CONFLICT":
        vals += ["UNSTABLE", "STABLE"]
        srcs += list(hi.sources)
    for k in ("arrest", "obstructive_shock"):
        if scan[k]:
            vals.append("UNSTABLE")
            srcs += [f"{r}:{k}" for r in scan[k]]
    f = _fact("haemo_state", vals, srcs)
    return f, {"state": f.status if f.status != "FOUND" else f.value, "sources": srcs, "vitals_not_adjudicated": scan["vitals"]}


def years_fact(scan: dict) -> tuple:
    items = [y["items"] for y in scan["years"] if y["items"] is not None]
    vals = [d for d in scan["ddimer_values"] if d["unit"].lower().replace("μ", "µ") in ("µg/l", "ug/l", "ng/ml")]
    detail = {"years_items": items, "ddimer_values": scan["ddimer_values"], "usable_values": vals,
              "unit_note": "1 ng/mL = 1 µg/L(산술 동치). FEU/DDU 미기재 — 원문 기준값 단위 대응 미확인"}
    if len(set(items)) != 1 or len({v["value"] for v in vals}) != 1:
        why = "YEARS 항목 수 없음/충돌" if len(set(items)) != 1 else "D-dimer 수치·단위 없음/충돌"
        return LG.Fact("years_rule_out", "NOT_FOUND"), {**detail, "status": "NOT_FOUND", "reason": why}
    n, v = items[0], vals[0]["value"]
    ok = (n == 0 and v < 1000) or (n >= 1 and v < 500)
    srcs = tuple(sorted({y["source_record_id"] for y in scan["years"]} | {d["source_record_id"] for d in vals}))
    return LG.Fact("years_rule_out", "FOUND", ok, (ok,), srcs), {**detail, "status": "FOUND", "value": ok, "rule": "항목 0 & <1000 µg/L, 또는 항목 ≥1 & <500 µg/L(각주 c)"}


def build_agg(facts: list, records: list) -> tuple:
    """에피소드 사실 + 기록 원문 → (기본 agg, 맥락 상세). 검사 전 확률(pretest)은 세계별로 따로 덮어쓴다(shadow_reasoner)."""
    agg = GR.aggregate_facts(facts)                       # v4 와 같은 집계(pretest, suspected, ddimer_*, haemodynamic_instability)
    scan = scan_records(records)
    hs, hdet = haemo_state(agg, scan)
    agg["haemo_state"] = hs
    tl = scan["two_level"]
    agg["pretest_two_level"] = _fact("pretest_two_level", [x["value"] for x in tl], [x["source_record_id"] + ":two_level" for x in tl])
    agg["inpatient"] = LG.Fact("inpatient", "FOUND", True, (True,), tuple(scan["inpatient"])) if scan["inpatient"] else LG.Fact("inpatient", "NOT_FOUND")
    if scan["pregnant"] and scan["not_pregnant"]:
        agg["pregnant"] = LG.Fact("pregnant", "CONFLICT", None, (True, False), tuple(scan["pregnant"] + scan["not_pregnant"]))
    else:
        agg["pregnant"] = LG.Fact("pregnant", "FOUND", bool(scan["pregnant"]), (bool(scan["pregnant"]),), tuple(scan["pregnant"] + scan["not_pregnant"])) \
            if (scan["pregnant"] or scan["not_pregnant"]) else LG.Fact("pregnant", "NOT_FOUND")
    ac = [f["source_record_id"] for f in facts if f["key"] == "treatment" and isinstance(f["value"], dict) and f["value"].get("class") == "ANTICOAGULATION"
          and f["value"].get("status") == "CURRENT"]
    agg["anticoagulated"] = LG.Fact("anticoagulated", "FOUND", True, (True,), tuple(ac)) if ac else LG.Fact("anticoagulated", "NOT_FOUND")
    if agg["ddimer_assay"].status == "NOT_FOUND" and scan["hs_assay"]:     # 'high-sensitivity assay' 명시 문구 → 고민감(연구용 매핑, v3 미추출)
        agg["ddimer_assay"] = LG.Fact("ddimer_assay", "FOUND", "HIGH_SENSITIVITY", ("HIGH_SENSITIVITY",), tuple(f"{r}:hs_assay_phrase" for r in scan["hs_assay"]))
    yf, ydet = years_fact(scan)
    agg["years_rule_out"] = yf
    ctx = {"pretest_observations": pretest_observations(facts), "two_level_observations": tl, "haemodynamic": hdet, "years": ydet,
           "inpatient_sources": scan["inpatient"], "pregnancy_sources": scan["pregnant"], "anticoagulation_sources": ac, "hs_assay_phrase_records": scan["hs_assay"],
           "unchecked_exclusions_policy": "입원·임신·항응고는 명시된 경우만 차단(BLOCK_ONLY_IF_TRUE) — 미기재는 판단 출력의 optional_unchecked 로 표시"}
    return agg, ctx


def pretest_worlds(obs: list, policy: str, test_available_time) -> dict:
    """검사 전 확률 해석 세계. 반환 {worlds: [값|None], kind, note}."""
    vals = list(dict.fromkeys(o["value"] for o in obs))
    if not vals:
        return {"worlds": [None], "kind": "NOT_RECORDED", "note": "확률 기록 없음 → NOT_FOUND"}
    if len(vals) == 1:
        return {"worlds": vals, "kind": "SINGLE", "note": ""}
    times = {str(o["available_time"]) for o in obs}
    if policy == "LEGACY_ANY_CONFLICT_HOLD":
        return {"worlds": ["__CONFLICT__"], "kind": "CONFLICT", "note": "값이 다르면 충돌(v4 와 같음)"}
    if policy == "LATEST_BEFORE_TEST":
        before = [o for o in obs if isinstance(o["available_time"], (int, float)) and isinstance(test_available_time, (int, float)) and o["available_time"] <= test_available_time]
        pick = sorted(before or obs, key=lambda o: (o["available_time"], o["source_record_id"]))[-1]
        return {"worlds": [pick["value"]], "kind": "LATEST_BEFORE_TEST", "note": f"검사 공개 전 최신 평가 {pick['source_record_id']}(민감도 분석 정책, 원문 근거 없음)"}
    return {"worlds": vals, "kind": "MULTI_SAME_TIME" if len(times) == 1 else "MULTI_REASSESSED_OVER_TIME",
            "note": "모든 기록 값에서 결과가 같으면 채택, 다르면 보류(같은 시각 충돌 / 시간 재평가 정책 미확인)"}
