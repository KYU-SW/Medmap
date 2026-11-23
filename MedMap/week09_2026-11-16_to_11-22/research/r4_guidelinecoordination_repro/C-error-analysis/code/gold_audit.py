"""SUBAGENT C - rules_gold.json 정답 품질 감사 (LLM 미사용, 읽기 전용 입력).

입력: upstream/GuidelineCoordination/rules_gold.json (읽기 전용)
출력: C-error-analysis/gold_audit_*.csv, gold_audit_summary.json
모든 판정은 규칙 기반 휴리스틱 '후보' 표시이며 정답 수정이 아님.
"""
from __future__ import annotations

import collections
import difflib
import hashlib
import json
import random
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/<user>/medmap-guidelinecoordination-repro-20261118")
GOLD = ROOT / "upstream/GuidelineCoordination/rules_gold.json"
OUT = ROOT / "C-error-analysis"
SEED = 20261118
SAMPLE_N = 60

PRED_RE = re.compile(r"pred\.[\w\.]+")


def load() -> list[dict]:
    raw = GOLD.read_bytes()
    print("gold sha256", hashlib.sha256(raw).hexdigest())
    return json.loads(raw)


def norm_cond(c: str) -> str:
    """AND-only 조건이면 술어 집합을 정렬, 그 외는 공백 정규화."""
    c = re.sub(r"\s+", " ", c.strip())
    if " OR " not in c and "NOT " not in c and "(" not in c:
        return " AND ".join(sorted(p.strip() for p in c.split(" AND ")))
    return c


def cond_features(c: str) -> dict:
    return {
        "n_pred": len(PRED_RE.findall(c)),
        "n_and": len(re.findall(r"\bAND\b", c)),
        "n_or": len(re.findall(r"\bOR\b", c)),
        "n_not": len(re.findall(r"\bNOT\b", c)),
        "has_paren": "(" in c,
        "mixed_and_or_no_paren": (" AND " in c and " OR " in c and "(" not in c),
    }


# ---- 원문(quote) 키워드 휴리스틱 ----
MODAL_RULES = [  # (패턴, 기대 permission 집합, 라벨)
    (r"禁用|禁忌|禁止", {"contraindicate", "stop", "avoid"}, "禁用/禁忌"),
    (r"不建议|不推荐|不宜|避免|不应", {"avoid", "contraindicate", "stop", "caution"}, "不建议/避免"),
    (r"慎用|谨慎", {"caution", "avoid", "reduce_dose", "max_dose_limit", "start_low_dose"}, "慎用"),
    (r"停用|停药|暂停", {"stop", "avoid", "contraindicate"}, "停用"),
]
POS_RE = r"(推荐|建议|首选|优先|应(当)?(使用|选用|联合)|可(以)?(考虑|使用|选用|联合)|无需|不需|继续)"
TIME_RE = r"(\d+\s*(个)?(月|周|天|日|年|小时|h)|术前|术后|围手术期|期间|之前|之后|开始后|起始后|治疗后|随访|初始|首次|长期|短期|急性)"
EXCEPT_RE = r"(除外|除非|以外|排除|但|然而|除了)"
NUM_RE = re.compile(r"(eGFR|估算肾小球滤过率|血钾|K\+|HbA1c|BMI|LVEF|UACR|血压|收缩压)[^，。；;,]{0,25}?([≥≤<>＜＞]|大于|小于|不低于|低于|高于|以上|以下|至)?\s*(\d+(\.\d+)?)")


def quote_flags(quote: str, perm: str, cond: str) -> dict:
    flags = []
    neg_hit = [lab for pat, exp, lab in MODAL_RULES if re.search(pat, quote)]
    for pat, exp, lab in MODAL_RULES:
        if re.search(pat, quote) and perm not in exp:
            flags.append(f"modal_{lab}_but_perm_{perm}")
    if not neg_hit and perm in {"avoid", "contraindicate", "stop"} and re.search(POS_RE, quote):
        flags.append(f"positive_wording_but_perm_{perm}")
    # 禁用 vs avoid (논문의 Action Alignment Error 유형과 동일 축)
    if re.search(r"禁用|禁忌", quote) and perm == "avoid":
        flags.append("quote_禁用禁忌_mapped_avoid")
    if re.search(r"不建议|不推荐", quote) and not re.search(r"禁用|禁忌", quote) and perm == "contraindicate":
        flags.append("quote_不建议_mapped_contraindicate")
    t = re.findall(TIME_RE, quote)
    time_terms = sorted(set(x[0] for x in t))
    cond_has_time = bool(re.search(r"(month|week|day|year|hour|duration|_mo_|_wk|_d_|before|after|post_|postop|preop|pre_|periop|surgery|initial|newly|acute|long_term|history)", cond.replace("pred.", " ")))
    if time_terms and not cond_has_time:
        flags.append("time_in_quote_not_in_condition")
    exc = re.findall(EXCEPT_RE, quote)
    if exc and " NOT " not in f" {cond}":
        flags.append("exception_word_in_quote_no_NOT")
    # 수치
    nums = sorted(set(m.group(3) for m in NUM_RE.finditer(quote)))
    cond_nums = set(re.findall(r"\d+(?:_\d+)?", cond.replace("pred.", "")))
    cond_nums_flat = set(x for c in cond_nums for x in c.split("_"))
    missing_nums = [n for n in nums if n.split(".")[0] not in cond_nums_flat and n.replace(".", "_") not in cond_nums]
    if missing_nums:
        flags.append("threshold_in_quote_absent_in_condition:" + "|".join(missing_nums))
    return {
        "time_terms": "|".join(time_terms),
        "except_terms": "|".join(sorted(set(exc))),
        "quote_numbers": "|".join(nums),
        "flags": ";".join(flags),
        "n_flags": len(flags),
    }


def pred_concept(p: str) -> str:
    s = p[len("pred."):]
    s = re.sub(r"^(has|on|history_of|history|is|with|patient|patients)_", "", s)
    return s


def main() -> None:
    rules = load()
    print("n_rules", len(rules))

    # ---------- 규칙 단위 표 ----------
    rows = []
    for r in rules:
        prov = r["provenance"][0]
        c = r["condition"]
        f = cond_features(c)
        qf = quote_flags(prov["quote"], r["action"]["permission"], c)
        rows.append({
            "id": r["id"], "label": r["label"], "condition": c,
            "subjects": "|".join(r["action"]["subjects"]),
            "permission": r["action"]["permission"],
            "requirements": "|".join(r["action"]["requirements"]),
            "source": prov["source"], "quote": prov["quote"],
            "recommendation_grade": prov["recommendation_grade"],
            "evidence_level": prov["evidence_level"],
            **f, **qf,
        })
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "gold_audit_rules.csv", index=False, encoding="utf-8-sig")

    # ---------- 술어 인벤토리 ----------
    pc = collections.Counter(p for c in df.condition for p in PRED_RE.findall(c))
    pred_rows = []
    for p, n in pc.most_common():
        s = p[5:]
        m = re.match(r"^(egfr|potassium|hba1c|bmi|lvef|uacr|sbp|k)_(ge|gt|le|lt|eq)_(\d+(?:_\d+)?)$", s)
        m2 = re.match(r"^(egfr|potassium|hba1c|bmi|lvef|uacr)_(\d+)_to_(\d+)$", s)
        if m:
            kind = "numeric_threshold_discretized"
        elif m2:
            kind = "numeric_range_discretized"
        elif re.search(r"\d", s):
            kind = "contains_number_other"
        elif s.startswith("has_"):
            kind = "has_diagnosis"
        elif s.startswith("on_"):
            kind = "on_medication"
        elif "stage" in s or "child_pugh" in s or "nyha" in s:
            kind = "stage"
        else:
            kind = "other_freeform"
        pred_rows.append({"predicate": p, "n_rules": n, "kind": kind, "concept_core": pred_concept(p),
                          "uses_compound_in_name": bool(re.search(r"_or_|_and_|_with_|_without_|^pred\.no_|_not_|non_", p))})
    pdf = pd.DataFrame(pred_rows)
    pdf.to_csv(OUT / "gold_audit_predicates.csv", index=False, encoding="utf-8-sig")

    # 유사 술어 쌍(같은 개념 다른 이름 후보): 문자열 유사도 + 핵심어 동일
    preds = list(pc)
    sim = []
    for i in range(len(preds)):
        for j in range(i + 1, len(preds)):
            a, b = preds[i], preds[j]
            ca, cb = pred_concept(a), pred_concept(b)
            r = difflib.SequenceMatcher(None, ca, cb).ratio()
            same_core = ca == cb
            # 숫자 차이만 있는 쌍(egfr_lt_30 vs egfr_lt_25)은 다른 개념이므로 제외
            if re.sub(r"\d+", "#", ca) == re.sub(r"\d+", "#", cb) and ca != cb:
                continue
            if same_core or r >= 0.85:
                sim.append({"pred_a": a, "n_a": pc[a], "pred_b": b, "n_b": pc[b],
                            "similarity": round(r, 3), "same_core_after_prefix_strip": same_core})
    sdf = pd.DataFrame(sim).sort_values("similarity", ascending=False)
    sdf.to_csv(OUT / "gold_audit_similar_predicates.csv", index=False, encoding="utf-8-sig")

    # 수동 확인된 동의어 후보 그룹 (이름 기반; 의미는 predicates.json 미공개로 확인 필요)
    synonym_groups = {
        "CKD/신기능저하": [p for p in preds if re.search(r"has_ckd$|renal_insufficiency|renal_impairment|kidney_disease|has_ckd_|ckd_adult", p)],
        "심부전": [p for p in preds if re.search(r"has_hf$|heart_failure|symptomatic_hf|has_chf", p)],
        "당뇨": [p for p in preds if re.search(r"has_t2dm$|has_diabetes$|type_2_diabetes|has_dm$|t2dm_adult", p)],
        "동맥경화성심혈관질환/고위험": [p for p in preds if re.search(r"ascvd|cardiovascular_high_risk|high_cv_risk|cv_risk", p)],
        "투석/말기신부전": [p for p in preds if re.search(r"dialysis|esrd|ckd_stage_5|egfr_lt_15", p)],
        "간기능": [p for p in preds if re.search(r"liver|hepatic|child_pugh", p)],
        "혈당조절불충분": [p for p in preds if re.search(r"glycemic|hba1c|glucose_control|poor_control", p)],
    }
    syn_rows = [{"group": g, "predicate": p, "n_rules": pc[p]} for g, ps in synonym_groups.items() for p in ps]
    pd.DataFrame(syn_rows).to_csv(OUT / "gold_audit_synonym_groups.csv", index=False, encoding="utf-8-sig")

    # 약물 ID 동의어 후보
    mc = collections.Counter(s for x in df.subjects for s in x.split("|"))
    med_pairs = [("med.class.sglt2", "med.class.sglt2i"), ("med.class.glp1", "med.class.glp1ra"),
                 ("med.class.bb", "med.class.beta_blocker"), ("med.insulin", "med.class.insulin"),
                 ("med.class.mra", "med.class.nsmra"), ("med.class.oad", "med.class.oas"),
                 ("med.class.su", "med.class.insulin_secretagogues")]
    med_rows = [{"med_a": a, "n_a": mc.get(a, 0), "med_b": b, "n_b": mc.get(b, 0)} for a, b in med_pairs]
    pd.DataFrame(med_rows).to_csv(OUT / "gold_audit_med_id_variants.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(mc.most_common(), columns=["med_id", "n_rules"]).to_csv(OUT / "gold_audit_meds.csv", index=False, encoding="utf-8-sig")

    # ---------- 중복 ----------
    df["cond_norm"] = df.condition.map(norm_cond)
    df["subj_norm"] = df.subjects.map(lambda s: "|".join(sorted(s.split("|"))))
    key_full = df.cond_norm + "##" + df.subj_norm + "##" + df.permission
    key_cs = df.cond_norm + "##" + df.subj_norm
    dup_rows = []
    for k, g in df.groupby(key_full):
        if len(g) > 1:
            dup_rows.append({"dup_type": "same_condition_subjects_permission", "n": len(g), "ids": "|".join(g.id),
                             "sources": "|".join(sorted(set(g.source))), "permission": g.permission.iloc[0], "condition": g.condition.iloc[0]})
    for k, g in df.groupby(key_cs):
        if g.permission.nunique() > 1:
            dup_rows.append({"dup_type": "same_condition_subjects_DIFFERENT_permission", "n": len(g), "ids": "|".join(g.id),
                             "sources": "|".join(sorted(set(g.source))), "permission": "|".join(g.permission), "condition": g.condition.iloc[0]})
    for k, g in df.groupby("quote"):
        if len(g) > 1:
            dup_rows.append({"dup_type": "same_quote_multiple_rules", "n": len(g), "ids": "|".join(g.id),
                             "sources": "|".join(sorted(set(g.source))), "permission": "|".join(g.permission), "condition": " || ".join(g.condition)})
    pd.DataFrame(dup_rows).to_csv(OUT / "gold_audit_duplicates.csv", index=False, encoding="utf-8-sig")

    # ---------- 출처/등급 ----------
    src = df.source.value_counts().rename_axis("source").reset_index(name="n_rules")
    src.to_csv(OUT / "gold_audit_sources_in_gold.csv", index=False, encoding="utf-8-sig")
    grade = df.groupby(["recommendation_grade", "permission"]).size().reset_index(name="n")
    grade.to_csv(OUT / "gold_audit_grade_by_permission.csv", index=False, encoding="utf-8-sig")

    # ---------- 무작위 표본(수동 원문 대조용) ----------
    rng = random.Random(SEED)
    idx = sorted(rng.sample(range(len(rules)), SAMPLE_N))
    samp = df.iloc[idx][["id", "label", "condition", "subjects", "permission", "requirements", "source", "quote",
                         "recommendation_grade", "evidence_level", "flags"]].copy()
    samp.insert(0, "sample_order", range(1, SAMPLE_N + 1))
    samp.insert(1, "gold_index", idx)
    samp.to_csv(OUT / "gold_audit_sample60_raw.csv", index=False, encoding="utf-8-sig")

    # ---------- 요약 ----------
    flag_counter = collections.Counter()
    for fl in df["flags"]:
        for x in filter(None, fl.split(";")):
            flag_counter[x.split(":")[0] if x.startswith("threshold") else re.sub(r"_but_perm_.*", "_but_perm_X", x)] += 1
    summary = {
        "n_rules": len(df), "n_unique_ids": int(df.id.nunique()), "n_predicates": len(pc),
        "n_predicates_used_once": int(sum(1 for v in pc.values() if v == 1)),
        "permission": df.permission.value_counts().to_dict(),
        "conditions_with_OR": int((df.n_or > 0).sum()), "conditions_with_NOT": int((df.n_not > 0).sum()),
        "conditions_mixed_and_or_no_paren": int(df.mixed_and_or_no_paren.sum()),
        "conditions_single_predicate": int((df.n_pred == 1).sum()),
        "pred_kind": pdf.kind.value_counts().to_dict(),
        "pred_name_contains_logic_word": int(pdf.uses_compound_in_name.sum()),
        "similar_pred_pairs": len(sdf), "flag_counts": dict(flag_counter),
        "rules_with_any_flag": int((df.n_flags > 0).sum()),
        "dup_counts": collections.Counter(r["dup_type"] for r in dup_rows),
        "n_sources_strings": int(df.source.nunique()), "empty_source": int((df.source == "").sum()),
        "grade_None": int((df.recommendation_grade == "None").sum()), "evidence_None": int((df.evidence_level == "None").sum()),
        "sample_seed": SEED, "sample_idx": idx,
    }
    (OUT / "gold_audit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=int))
    print(json.dumps({k: v for k, v in summary.items() if k != "sample_idx"}, ensure_ascii=False, indent=1, default=int))


if __name__ == "__main__":
    sys.exit(main())
