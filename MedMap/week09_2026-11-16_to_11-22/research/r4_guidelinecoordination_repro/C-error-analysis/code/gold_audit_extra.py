"""SUBAGENT C - rules_gold.json 추가 감사 (LLM 미사용).

1) id/label 에 등장하는 질환 맥락(t2dm/ckd/hf...)이 condition 에 없는 규칙 (Contextual Loss 대리 지표)
2) '对于...使用X' 패턴: condition 에 pred.on_<subject> 가 들어간 금지/주의 규칙 (지침에 없는 조건 추가 후보)
3) 문자열 동일 condition + 겹치는 subjects + 상충 permission (analyzer.py 분류 기준) = 어휘 수준 intrinsic conflict 하한
4) 약물 subject 겹침: 원본 analyzer 의 정확 문자열 교집합 vs 계열 확장(med.class.sglt2 ⊇ 개별 gliflozin 등)
5) 데이터 결함: 빈 subjects, 'nan' subject, 빈 label, 빈 source, requirements 에 pred.* 혼입, id-permission 불일치
"""
from __future__ import annotations

import itertools
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path("/home/<user>/medmap-guidelinecoordination-repro-20261118")
GOLD = ROOT / "upstream/GuidelineCoordination/rules_gold.json"
OUT = ROOT / "C-error-analysis"

# analyzer.py L371-374 그대로
USAGE = {"contraindicate", "avoid", "caution", "allow", "recommend", "require", "continue", "stop", "consider"}
DOSE = {"reduce_dose", "max_dose_limit", "start_low_dose", "titrate", "increase_dose"}
PROHIBIT = {"contraindicate", "avoid", "stop"}
ALLOWP = {"caution", "allow", "recommend", "require", "continue", "consider"}

CTX = {  # id/label 토큰 -> condition 에 있어야 할 술어 패턴
    "t2dm": r"t2dm|diabetes|dkd",
    "ckd": r"ckd|renal|kidney|egfr|dialysis|dkd|uacr",
    "hf": r"hf|heart_failure|nyha|lvef",
    "hfref": r"hfref|lvef",
    "ascvd": r"ascvd|cardiovascular|cvd",
    "elderly": r"elderly|age",
    "pregnan": r"pregnan",
    "dialysis": r"dialysis|egfr_lt_15|stage_5",
}

SGLT2_MEMBERS = {"med.dapagliflozin", "med.empagliflozin", "med.canagliflozin", "med.henagliflozin",
                 "med.ertugliflozin", "med.class.sglt2", "med.class.sglt2i"}
CLASS_EXPAND = {
    "med.class.sglt2": SGLT2_MEMBERS, "med.class.sglt2i": SGLT2_MEMBERS,
    "med.class.glp1": {"med.class.glp1", "med.class.glp1ra", "med.semaglutide_tablet"},
    "med.class.glp1ra": {"med.class.glp1", "med.class.glp1ra", "med.semaglutide_tablet"},
    "med.class.bb": {"med.class.bb", "med.class.beta_blocker"},
    "med.class.beta_blocker": {"med.class.bb", "med.class.beta_blocker"},
    "med.class.insulin": {"med.class.insulin", "med.insulin"}, "med.insulin": {"med.class.insulin", "med.insulin"},
    "med.metformin": {"med.metformin", "med.metformin_er"}, "med.metformin_er": {"med.metformin", "med.metformin_er"},
}
for m in SGLT2_MEMBERS:
    CLASS_EXPAND.setdefault(m, {m, "med.class.sglt2", "med.class.sglt2i"})


def action_conflict(pa: str, pb: str) -> bool:
    if pa in USAGE and pb in USAGE:
        return (pa in PROHIBIT and pb in ALLOWP) or (pb in PROHIBIT and pa in ALLOWP)
    if pa in DOSE and pb in DOSE:
        return {pa, pb} == {"increase_dose", "reduce_dose"} or {pa, pb} == {"increase_dose", "max_dose_limit"}
    # 금지류 vs 용량조절 (analyzer 주석: 禁用 vs 剂量 → 冲突)
    return (pa in PROHIBIT and pb in DOSE) or (pb in PROHIBIT and pa in DOSE)


def norm_cond(c: str) -> str:
    c = re.sub(r"\s+", " ", c.strip())
    if " OR " not in c and "NOT " not in c and "(" not in c:
        return " AND ".join(sorted(c.split(" AND ")))
    return c


def main() -> None:
    rules = json.loads(GOLD.read_text())
    out_rows = []

    # 1) id/label 맥락 vs condition
    for r in rules:
        idl = (r["id"] + " " + r["label"]).lower()
        cond = r["condition"].lower()
        missing = []
        for tok, pat in CTX.items():
            if re.search(rf"(^|[._\s]){tok}", r["id"].lower()) and not re.search(pat, cond):
                missing.append(tok)
        if missing:
            out_rows.append({"check": "id_context_absent_in_condition", "id": r["id"], "detail": "|".join(missing),
                             "condition": r["condition"], "permission": r["action"]["permission"],
                             "quote": r["provenance"][0]["quote"]})

    # 2) on_<drug> 조건 + 금지/주의
    for r in rules:
        ons = re.findall(r"pred\.on_(\w+)", r["condition"])
        subj = " ".join(r["action"]["subjects"])
        hit = [o for o in ons if o in subj or o.rstrip("s") in subj]
        if hit and r["action"]["permission"] in PROHIBIT | {"caution"}:
            q = r["provenance"][0]["quote"]
            out_rows.append({"check": "on_subject_in_condition_with_restrictive_perm", "id": r["id"],
                             "detail": "|".join(hit) + ("|quote_mentions_current_use" if re.search(r"正在|已使用|已用|如果正在|治疗中|期间", q) else "|quote_no_current_use_word"),
                             "condition": r["condition"], "permission": r["action"]["permission"], "quote": q})

    # 5) 데이터 결함
    for r in rules:
        a = r["action"]
        p = r["provenance"][0]
        if not a["subjects"]:
            out_rows.append({"check": "empty_subjects", "id": r["id"], "detail": a["permission"], "condition": r["condition"], "permission": a["permission"], "quote": p["quote"]})
        if any(s.lower() in ("nan", "none", "") for s in a["subjects"]):
            out_rows.append({"check": "nan_subject_string", "id": r["id"], "detail": str(a["subjects"]), "condition": r["condition"], "permission": a["permission"], "quote": p["quote"]})
        if not r["label"]:
            out_rows.append({"check": "empty_label", "id": r["id"], "detail": "", "condition": r["condition"], "permission": a["permission"], "quote": p["quote"]})
        if not p["source"]:
            out_rows.append({"check": "empty_source", "id": r["id"], "detail": "", "condition": r["condition"], "permission": a["permission"], "quote": p["quote"]})
        if any(x.startswith("pred.") for x in a["requirements"]):
            out_rows.append({"check": "predicate_in_requirements", "id": r["id"], "detail": "|".join(a["requirements"]), "condition": r["condition"], "permission": a["permission"], "quote": p["quote"]})
        # id 에 적힌 행위와 permission 불일치
        idp = None
        for kw, perms in [("contraindicat", {"contraindicate"}), ("avoid", {"avoid", "contraindicate"}), ("_stop", {"stop"}),
                          ("continue", {"continue"}), ("reduce", {"reduce_dose"}), ("recommend", {"recommend"}), ("caution", {"caution"})]:
            if kw in r["id"]:
                idp = (kw, perms)
                break
        if idp and a["permission"] not in idp[1]:
            out_rows.append({"check": "id_keyword_vs_permission_mismatch", "id": r["id"], "detail": f"id:{idp[0]} perm:{a['permission']}",
                             "condition": r["condition"], "permission": a["permission"], "quote": p["quote"]})
    pd.DataFrame(out_rows).to_csv(OUT / "gold_audit_rule_checks.csv", index=False, encoding="utf-8-sig")

    # 3)+4) 규칙 쌍
    pair_rows = []
    n_exact_overlap = n_exp_overlap = 0
    n_exact_conf = n_exp_conf = 0
    for a, b in itertools.combinations(rules, 2):
        sa, sb = set(a["action"]["subjects"]), set(b["action"]["subjects"])
        exact = bool(sa & sb)
        ea = set().union(*[CLASS_EXPAND.get(s, {s}) for s in sa]) if sa else set()
        eb = set().union(*[CLASS_EXPAND.get(s, {s}) for s in sb]) if sb else set()
        expanded = bool((ea & sb) or (sa & eb))  # 한쪽만 확장(개별약 간 class 경유 거짓 겹침 방지)
        conf = action_conflict(a["action"]["permission"], b["action"]["permission"])
        n_exact_overlap += exact
        n_exp_overlap += expanded
        n_exact_conf += exact and conf
        n_exp_conf += expanded and conf
        if conf and (exact or expanded) and norm_cond(a["condition"]) == norm_cond(b["condition"]):
            pair_rows.append({"rule_a": a["id"], "perm_a": a["action"]["permission"], "rule_b": b["id"], "perm_b": b["action"]["permission"],
                              "condition": a["condition"], "subject_overlap_exact": exact, "subject_overlap_only_after_class_expand": (not exact) and expanded,
                              "same_quote": a["provenance"][0]["quote"] == b["provenance"][0]["quote"],
                              "same_source": a["provenance"][0]["source"] == b["provenance"][0]["source"],
                              "quote_a": a["provenance"][0]["quote"], "quote_b": b["provenance"][0]["quote"]})
    pdf = pd.DataFrame(pair_rows)
    pdf.to_csv(OUT / "gold_audit_lexical_intrinsic_conflicts.csv", index=False, encoding="utf-8-sig")
    n_pairs = len(rules) * (len(rules) - 1) // 2
    summ = {
        "n_rule_pairs": n_pairs,
        "pairs_subject_overlap_exact(analyzer)": n_exact_overlap,
        "pairs_subject_overlap_after_class_expand": n_exp_overlap,
        "pairs_action_conflict_exact": n_exact_conf,
        "pairs_action_conflict_after_class_expand": n_exp_conf,
        "lexical_intrinsic_conflicts_total": len(pdf),
        "lexical_intrinsic_exact_subject": int(pdf.subject_overlap_exact.sum()) if len(pdf) else 0,
        "lexical_intrinsic_same_quote": int(pdf.same_quote.sum()) if len(pdf) else 0,
        "lexical_intrinsic_same_source": int(pdf.same_source.sum()) if len(pdf) else 0,
        "rule_checks": pd.DataFrame(out_rows).check.value_counts().to_dict(),
    }
    (OUT / "gold_audit_extra_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1, default=int))
    print(json.dumps(summ, ensure_ascii=False, indent=1, default=int))


if __name__ == "__main__":
    main()
