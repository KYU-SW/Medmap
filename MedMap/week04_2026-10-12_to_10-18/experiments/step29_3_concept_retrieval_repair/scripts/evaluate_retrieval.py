"""STEP29.3 평가(연구용 엔지니어링 지표 — 임상 정확도 아님). 지표·분모·게이트는 검색기 구현 전 고정(data/prereg_gates.json, 2026-10-14).

실행: evaluate_retrieval.py dev   → DEV29_3 + 회귀 사례 + 노출(STEP29.2 HOLDOUT·pilot·계약) · 모든 정책 — 정책 선택용(outputs/dev_policy_metrics.json)
      evaluate_retrieval.py final → FROZEN29_3(최초 실행) + 위 전부 + WEAKNON903 — 공식(outputs/eval_summary.json). prereg_gates·policy_freeze SHA 가 같을 때만.
정책: R0 = STEP29.2 V3_B0 원본 · R1 = STEP29.2 V3_B3 원본 · N1–N4 = 정규화 ablation(B4 가드 B0) · R2 = N3 + B0 · R3 = N4 + 의미 충돌 보류(B3C) · R4 = N4 + B4 근거·충돌(B2+B3).
 (R2 와 N3 는 같은 구성 — 표에서 둘 다 표시하지 않고 R2 로만 보고)

[새 합성 세트 지표 — DEV29_3·FROZEN29_3 각각, 합치지 않음. 정렬 = STEP29.2 contract_check_v3.align]
 RAW_PRESERVATION       입력 중 source_text 그대로 + 모든 raw_span == text[s:e]          OFFSET_VALID  mention 중 오프셋·raw_span 일치
 CONCEPT_AUTO_PRECISION 시스템 EXISTING mention 중 그 case 정답 concept 합집합(None 제외) 안 + 정렬 정답의 forbid 아님
 CONCEPT_AUTO_COVERAGE  필수(optional 아님) 정답 mention 중 정답 concept 이 있는 것 → 정렬 mention 이 EXISTING 이고 concept ∈ concept_any
 CONCEPT_RECALL_ON_SUPPORTED 정답 concept_any 가 모두 77 concept(None 없음)인 정답 mention(부정·optional 포함) 중 정렬 EXISTING 정답 concept
 MULTI_SPAN_RETENTION   필수 정답 concept mention ≥2 인 case 의 그 mention 중 정답 EXISTING 정렬
 MORPHOLOGICAL_VARIANT_SUCCESS morph_group 중 (모든 활용형의 정렬 mention concept_view 동일) AND (그룹 정답이 필수 concept 이면 모두 정답) 인 그룹 비율
 MORPH_VARIANT_MENTION_SUCCESS MORPH case 의 필수 정답 mention 중 정답 EXISTING 정렬 비율(형태별 표 별도)
 SEMANTIC_AMBIGUITY_ERRORS ambiguity 범주(VOMIT_FAMILY·NECK_THROAT·GI_SENSATION·TREMOR_CHILLS·NON_SYMPTOM) case 의 EXISTING mention 중 정답 합집합 밖 또는 forbid 인 수
 WRONG_CONCEPT_AUTO_ACCEPT 모든 case 의 EXISTING mention 중 정답 합집합 밖 또는 forbid 인 수(정밀도의 분자 보완 — UNKNOWN 과 따로 셈)
 UNSUPPORTED_AUTO_LINK  no_existing_link case(비증상·미지원·SILVER) 중 EXISTING mention 이 있는 case 수 / 그 case 수
 UNKNOWN_RATE / UNCERTAIN_RATE 지원 정답 mention(concept_any ⊂ 77) 중 정렬 실패 또는 UNKNOWN_SYMPTOM / UNCERTAIN 비율
 SILVER_CONCEPT_PRESERVATION SILVER case 중 EXISTING 0 AND 모델 eligible 0 인 비율(NEW_ONTOLOGY_CANDIDATE 로 보존된 수 별도)
 NEGATION_SCOPE · TEMPORALITY · EXPERIENCER 정렬 정답 mention 의 assertion·사건 시점·주체 일치(STEP29.2 와 같은 view)
 SEMANTIC_VIOLATIONS    STEP29.2 검사기 v6(동결 SHA) 위반 입력 수
 안전: NEG_POSITIVE(정답 NEG 인데 PRESENT·모델 POSITIVE) · OTHER_POSITIVE(정답 OTHER 인데 PATIENT·eligible POSITIVE) · SILVER_MODEL_INPUT(NEW/SUBTYPE/SILVER eligible)
       · REASON_MISSING(사유 없는 UNCERTAIN/UNKNOWN) · STRING_SIM_ONLY_AUTO(EXISTING 인데 KO 근거 등급이 PHRASE·NGRAM 뿐)
[회귀 사례(data/regression_cases.json, 노출)] REGRESSION_VIOLATIONS = 사례별 (forbidden 인 EXISTING 존재) + (allowed 가 비었는데 EXISTING 존재) + (allowed 밖 EXISTING) 의 위반 사례 수 · must_any 누락 별도
[노출 — STEP29.2 와 같은 입력·정의] STEP29.2 HOLDOUT 1,052: STEP29.2 evaluate_nlu.new_set_metrics · pilot/REGRESSION168/계약: exposed_metrics
[약한 외부] WEAK_NEGATIVE_AUTO_MAP = WEAKNON903 중 EXISTING mention 이 있는 입력 수 / 903 (final 만)
"""
from __future__ import annotations

import collections
import json
import sys

import s293_common as S
from contract_check_v3 import EXISTING, POS, a_ok, align, check, concept_view, event_view
from evaluate_nlu import exposed_metrics, new_set_metrics
from evaluator_v6 import evaluate as v6eval
from evaluator_v6 import evaluator_sha

AMB = ("VOMIT_FAMILY", "NECK_THROAT", "GI_SENSATION", "TREMOR_CHILLS", "NON_SYMPTOM")
REASON_TIERS_SIM = ("PHRASE", "NGRAM")


def load(name):
    return json.loads((S.DATA / name).read_text(encoding="utf-8"))


def safety_counts(outs):
    c = collections.Counter()
    for o in outs:
        for x in o["mentions"]:
            mi = x.get("model_input") or {}
            if (x["status"] in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE") or x.get("evidence_sources") == "SILVER") and mi.get("eligible"):
                c["SILVER_MODEL_INPUT"] += 1
            if (x["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM") and not (x.get("reason") or x.get("guard_reasons"))) or not x.get("raw_span"):
                c["REASON_MISSING"] += 1
            if x["status"] in EXISTING and (x.get("ko_tier") in REASON_TIERS_SIM or (x.get("retrieval") or {}).get("tier") in REASON_TIERS_SIM):
                c["STRING_SIM_ONLY_AUTO"] += 1
    return c


def new_metrics(cases, outs, models):
    m = collections.Counter()
    errs, groups = [], collections.defaultdict(list)
    for c, o in zip(cases, outs):
        t = c["text"]
        m["inputs"] += 1
        m["raw_ok"] += o["source_text"] == t and all(x["raw_span"] == t[x["span_start"]:x["span_end"]] for x in o["mentions"])
        for x in o["mentions"]:
            m["mentions"] += 1
            m["off_ok"] += isinstance(x["span_start"], int) and 0 <= x["span_start"] < x["span_end"] <= len(t) and x["raw_span"] == t[x["span_start"]:x["span_end"]]
        union = {cc for g in c["mentions"] for cc in g["concept_any"] if cc}
        pairs = align(c, o["mentions"])
        forb_idx = {idx for g, idx in pairs if idx is not None and o["mentions"][idx].get("canonical_id") in (g.get("forbid") or [])}
        for i, x in enumerate(o["mentions"]):
            if x["status"] not in EXISTING:
                continue
            m["sys_ex"] += 1
            wrong = x.get("canonical_id") not in union or i in forb_idx or bool(c.get("no_existing_link"))
            m["sys_ex_ok"] += not wrong
            m["wrong_auto"] += wrong
            if wrong and c.get("ambiguity") in AMB:
                m["amb_err"] += 1
            if wrong:
                errs.append({"id": c["id"], "category": c["category"], "text": t, "type": "WRONG_AUTO", "got": f"{x.get('canonical_id')}|{x['raw_span']}"})
        req = [g for g in c["mentions"] if not g.get("optional") and any(c2 for c2 in g["concept_any"])]
        for g, idx in pairs:
            x = o["mentions"][idx] if idx is not None else None
            okc = x is not None and x["status"] in EXISTING and x.get("canonical_id") in g["concept_any"] and x.get("canonical_id") not in (g.get("forbid") or [])
            if g in req:
                m["cov_n"] += 1
                m["cov_ok"] += okc
                if len(req) >= 2:
                    m["multi_n"] += 1
                    m["multi_ok"] += okc
                if c["category"] == "MORPH":
                    m["morphm_n"] += 1
                    m["morphm_ok"] += okc
                    m[f"morph_{c['variant']}_n"] += 1
                    m[f"morph_{c['variant']}_ok"] += okc
                if not okc:
                    errs.append({"id": c["id"], "category": c["category"], "text": t, "type": "NOT_COVERED", "anchor": g["anchor"],
                                 "got": f"{x['status']}|{x.get('canonical_id')}|{x.get('reason')}" if x else "NOT_ALIGNED"})
            sup = all(cc in models for cc in g["concept_any"]) and None not in g["concept_any"]
            if sup:
                m["sup_n"] += 1
                m["sup_ok"] += okc
                m["unk"] += x is None or x["status"] == "UNKNOWN_SYMPTOM"
                m["unc"] += x is not None and x["status"] == "UNCERTAIN"
            if x is not None:
                m["aligned"] += 1
                m["neg_ok"] += a_ok(x, g["assertion_any"])
                m["exp_ok"] += x.get("experiencer") in g["experiencer_any"]
                if g.get("temporality_any"):
                    m["temp_n"] += 1
                    m["temp_ok"] += event_view(x) in g["temporality_any"]
        if c.get("morph_group"):
            g0 = c["mentions"][0]
            idx = pairs[0][1]
            x = o["mentions"][idx] if idx is not None else None
            okc = x is not None and x["status"] in EXISTING and x.get("canonical_id") in g0["concept_any"] and x.get("canonical_id") not in (g0.get("forbid") or [])
            groups[c["morph_group"]].append((str(concept_view(x)) if x else "NONE", okc, not g0.get("optional") and any(g0["concept_any"])))
        if c.get("no_existing_link"):
            m["unsup_n"] += 1
            m["unsup_auto"] += any(x["status"] in EXISTING for x in o["mentions"])
        if c["category"] == "SILVER":
            m["silver_n"] += 1
            m["silver_ok"] += not any(x["status"] in EXISTING or (x.get("model_input") or {}).get("eligible") for x in o["mentions"])
            m["silver_new"] += any(x["status"] == "NEW_ONTOLOGY_CANDIDATE" and (x.get("ontology_id") == c.get("silver_id")) for x in o["mentions"])
        for e in check(c, o):
            m["neg_positive"] += e["type"] == "ASSERTION" and bool(e.get("unsafe"))
            m["other_positive"] += e["type"] == "EXPERIENCER" and bool(e.get("unsafe"))
            m[f"err:{e['type']}"] += 1
        m["v6"] += bool(v6eval(o))
        m["case_pass"] += not check(c, o)
    gs = [(len({v for v, _, _ in g}) == 1) and (all(ok for _, ok, _ in g) if g[0][2] else True) for g in groups.values()]
    sc = safety_counts(outs)
    q = lambda a, b: S.rnd(m[a] / m[b]) if m[b] else None  # noqa: E731
    res = {"n_inputs": m["inputs"], "RAW_PRESERVATION": q("raw_ok", "inputs"), "OFFSET_VALID": q("off_ok", "mentions"),
           "CONCEPT_AUTO_PRECISION": q("sys_ex_ok", "sys_ex"), "precision_n": m["sys_ex"], "CONCEPT_AUTO_COVERAGE": q("cov_ok", "cov_n"), "coverage_n": m["cov_n"],
           "CONCEPT_RECALL_ON_SUPPORTED": q("sup_ok", "sup_n"), "supported_n": m["sup_n"], "MULTI_SPAN_RETENTION": q("multi_ok", "multi_n"), "multi_n": m["multi_n"],
           "MORPHOLOGICAL_VARIANT_SUCCESS": S.rnd(sum(gs) / len(gs)) if gs else None, "morph_groups_n": len(gs),
           "MORPH_VARIANT_MENTION_SUCCESS": q("morphm_ok", "morphm_n"), "morph_by_variant": {k[6:-2]: f"{m[k[:-2] + '_ok']}/{m[k]}" for k in sorted(m) if k.startswith("morph_") and k.endswith("_n")},
           "SEMANTIC_AMBIGUITY_ERRORS": m["amb_err"], "WRONG_CONCEPT_AUTO_ACCEPT": m["wrong_auto"],
           "UNSUPPORTED_AUTO_LINK": f"{m['unsup_auto']}/{m['unsup_n']}", "unsupported_auto": m["unsup_auto"], "unsupported_n": m["unsup_n"],
           "UNKNOWN_RATE": q("unk", "sup_n"), "UNCERTAIN_RATE": q("unc", "sup_n"),
           "SILVER_CONCEPT_PRESERVATION": q("silver_ok", "silver_n"), "silver_new_candidate": m["silver_new"], "silver_n": m["silver_n"],
           "NEGATION_SCOPE": q("neg_ok", "aligned"), "TEMPORALITY": q("temp_ok", "temp_n"), "EXPERIENCER": q("exp_ok", "aligned"), "aligned_n": m["aligned"],
           "SEMANTIC_VIOLATIONS": m["v6"], "NEG_POSITIVE": m["neg_positive"], "OTHER_POSITIVE": m["other_positive"], **dict(sc),
           "SILVER_MODEL_INPUT": sc["SILVER_MODEL_INPUT"], "REASON_MISSING": sc["REASON_MISSING"], "STRING_SIM_ONLY_AUTO": sc["STRING_SIM_ONLY_AUTO"],
           "CASE_PASS_RATE": q("case_pass", "inputs"), "errors_by_type": {k[4:]: m[k] for k in sorted(m) if k.startswith("err:")}}
    return res, errs


def regression_metrics(analyze_fn, policy):
    rc = load("regression_cases.json")["cases"]
    viol, miss, rows = 0, 0, []
    for c in rc:
        o = analyze_fn(c["text"], policy)
        ex = [x.get("canonical_id") for x in o["mentions"] if x["status"] in EXISTING]
        bad = [e for e in ex if e in c["forbidden"] or (not c["allowed"]) or e not in c["allowed"]]
        mis = [m for m in c["must_any"] if m not in ex]
        viol += bool(bad)
        miss += bool(mis)
        rows.append({"policy": policy, "text": c["text"], "existing": ";".join(map(str, ex)), "violation": ";".join(map(str, bad)), "must_missing": ";".join(mis),
                     "statuses": ";".join(f"{x['raw_span']}:{x['status']}:{x.get('canonical_id') or x.get('ontology_id')}" for x in o["mentions"])})
    return {"REGRESSION_VIOLATIONS": viol, "REGRESSION_MUST_MISSING": miss, "n": len(rc)}, rows


def weak_metrics(analyze_fn, policy):
    wn = [r["text"] for r in S.read_csv(S.S28_DIR / "outputs/weak_non_check.csv")]
    outs = [analyze_fn(t, policy) for t in wn]
    sc = safety_counts(outs)
    return {"WEAK_NEGATIVE_AUTO_MAP": sum(any(x["status"] in EXISTING for x in o["mentions"]) for o in outs), "weaknon_n": len(wn),
            "raw_ok": sum(o["source_text"] == t and all(x["raw_span"] == t[x["span_start"]:x["span_end"]] for x in o["mentions"]) for t, o in zip(wn, outs)),
            "SILVER_MODEL_INPUT": sc["SILVER_MODEL_INPUT"], "REASON_MISSING": sc["REASON_MISSING"]}


def prereg_ok(final: bool) -> dict:
    pre = S.load_json(S.DATA / "prereg_gates.json")
    st = {"gates_scripts": all(S.sha256(S.STEP / "scripts" / n) == h for n, h in pre["frozen_scripts"].items()),
          "data": all(S.sha256(S.DATA / n) == h for n, h in pre["frozen_data"].items()), "evaluator_v6_same_as_step29_2": evaluator_sha() == pre["evaluator_v6_sha256"]}
    if final:
        pf = S.load_json(S.DATA / "policy_freeze.json")
        st["policy_scripts"] = all(S.sha256(S.STEP / "scripts" / n) == h for n, h in pf["frozen_scripts"].items())
        st["selected_policy"] = pf["SELECTED_POLICY"]
    return st


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dev"
    st = prereg_ok(mode == "final")
    assert all(v for k, v in st.items() if k != "selected_policy"), f"동결 이후 변경 — 평가 중단 {st}"
    import step29_2_adapter as A
    models = S.models()
    sets = [("DEV29_3", load("development_cases.json"))] + ([("FROZEN29_3", load("frozen_evaluation_cases.json"))] if mode == "final" else [])
    hold = json.loads((S.S292_DIR / "data/frozen_holdout_pairs.json").read_text(encoding="utf-8"))
    M, E, R = {}, [], []
    for P in A.POLICIES:
        M[P] = {}
        for name, d in sets:
            outs = [A.analyze(c["text"], P) for c in d["cases"]]
            res, errs = new_metrics(d["cases"], outs, models)
            M[P][name] = res
            E += [{"policy": P, "set": name, **e} for e in errs]
        rg, rows = regression_metrics(A.analyze, P)
        M[P]["REGRESSION_CASES"] = rg
        R += rows
        outs = [A.analyze(c["text"], P) for c in hold["cases"]]
        res, errs = new_set_metrics(hold["cases"], outs, hold["metamorphic"], lambda t, P=P: A.sentence_spans(t, P))
        M[P]["STEP29_2_HOLDOUT"] = {k: v for k, v in res.items() if k not in ("by_category_pass",)}
        res, errs = exposed_metrics(A.analyze, P)
        M[P]["EXPOSED"] = res
        if mode == "final":
            M[P]["WEAK"] = weak_metrics(A.analyze, P)
        print(P, "done", flush=True)
    tag = "final" if mode == "final" else "dev"
    S.dump_json(S.OUT / ("eval_summary.json" if tag == "final" else "dev_policy_metrics.json"), {"mode": tag, "prereg_status": st, "metrics": M})
    S.wcsv(S.OUT / ("eval_errors.csv" if tag == "final" else "dev_errors.csv"), E)
    S.wcsv(S.OUT / ("regression_cases_result.csv" if tag == "final" else "dev_regression_cases_result.csv"), R)
    keys = ("CONCEPT_AUTO_PRECISION", "CONCEPT_AUTO_COVERAGE", "MULTI_SPAN_RETENTION", "MORPHOLOGICAL_VARIANT_SUCCESS", "SEMANTIC_AMBIGUITY_ERRORS",
            "WRONG_CONCEPT_AUTO_ACCEPT", "UNKNOWN_RATE", "NEGATION_SCOPE", "CASE_PASS_RATE")
    for P in A.POLICIES:
        for name, _ in sets:
            print(P, name, S.dumps({k: M[P][name][k] for k in keys}))
        h = M[P]["STEP29_2_HOLDOUT"]
        print(P, "H292", S.dumps({k: h[k] for k in ("CONCEPT_PRECISION", "CONCEPT_COVERAGE", "MULTI_SPAN_RETENTION", "NEGATION_SCOPE", "PROPAGATION_ERRORS")}),
              "REG", M[P]["REGRESSION_CASES"], "X", S.dumps({k: M[P]["EXPOSED"][k] for k in ("reg_precision", "reg_coverage", "pilot_multi_retention")}))


if __name__ == "__main__":
    main()
