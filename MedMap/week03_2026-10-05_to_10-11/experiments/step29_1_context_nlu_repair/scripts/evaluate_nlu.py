"""STEP29.1 평가(임상 정확도 아님). 지표·데이터는 실행 전 고정(2026-10-11). 동결 SHA(data/prereg.json) 불일치 시 실행하지 않는다.

[데이터 — data/evaluation_manifest.csv]
 EXPOSED_REGRESSION      STEP29 계약 68 · pilot_gold 274(합성·Claude 작성·반복 노출) · REGRESSION168(pilot 부분집합)
 PRE_REGISTERED_CONTRACT 새 계약 42(v2 구현 전 작성 — 개발에 사용, 독립 정답 아님)
 PROSPECTIVE_SYNTHETIC   231(템플릿 슬롯 정답, NLU 미실행 상태로 동결 — 이 평가가 첫 실행)
 WEAK_EXTERNAL           SILVER442 · WEAKNON903(약한 라벨)
[지표 — 분모 명시, 세트끼리 합치지 않음]
 raw_ok_rate(입력) · offset_valid_rate(mention) · v5_violation_inputs(검사기 v5, mention 단위 위반이 있는 입력) · v4_violation_inputs(문장 단위, 검사기 효과 비교용)
 G5 = STEP29 계약·새 계약 safety=NEG 의 unsafe + 새 계약 no_model_positive 위반 + pilot absent 대응 mention 의 PRESENT·POSITIVE · G6 = 계약 safety=OTHER unsafe + pilot 타인 대응 PATIENT·eligible
 G7 = 신규·하위·SILVER 단독 mention eligible · G10 = UNCERTAIN/UNKNOWN 인데 사유·원문 없음
 pilot(STEP29 와 같은 정의): multi_retention · retention · assertion·시점·주체 일치(대응 mention) · wrong_concept · unsupported_auto(should_link False 발화 중 EXISTING 있는 발화)
   · unsupported_patient_positive(그 발화들의 PATIENT·POSITIVE eligible mention 수)
 reg: 첫 EXISTING mention precision·coverage(분모 168) · 새 계약 범주별 통과 수 · 전향적 템플릿별 통과 수·오류 종류·no_model_positive 위반
 over_split(새 계약 OVER_SPLIT) · duplicate_span_mentions(같은 구간 mention 중복)
출력: outputs/{eval_summary.json, policy_comparison.csv, eval_errors.csv} · data/{evaluation_manifest.csv, eval_mentions.csv}
"""
from __future__ import annotations

import collections
import json

import s291_common as S
from contract_check import check as check29
from contract_check import load as load29
from contract_check_v2 import check as check2
from evaluator_v4 import violations as v4
from evaluator_v5 import evaluate as v5eval
from evaluator_v5 import evaluator_sha
from nlu_pipeline_v2 import LEVELS, analyze

EXISTING = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")
POS = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "EXISTING_SUBTYPE", "NEW_ONTOLOGY_CANDIDATE")
EXP_ASSERT = {"present": "PRESENT", "absent": "ABSENT", "uncertain": "POSSIBLE", "historical": "PRESENT"}


def main():
    pre = S.load_json(S.DATA / "prereg.json")
    now = {n: S.sha256(S.STEP / "scripts" / n) for n in pre["frozen_scripts"]}
    prereg_ok = (now == pre["frozen_scripts"] and S.sha256(S.DATA / "contract_cases.json") == pre["contracts_sha256"]
                 and S.sha256(S.DATA / "prospective_synthetic_cases.json") == pre["prospective_sha256"] and evaluator_sha() == pre["evaluator_v5_sha256"])
    assert prereg_ok, "동결 이후 변경 — 평가 중단"
    c29 = load29()["contracts"]
    cnew = json.loads((S.DATA / "contract_cases.json").read_text(encoding="utf-8"))["contracts"]
    pros = json.loads((S.DATA / "prospective_synthetic_cases.json").read_text(encoding="utf-8"))["contracts"]
    pilot = S.read_csv(S.S21_DIR / "data/pilot_gold.csv")
    regg = {r["text"]: r["gold_concept"] for r in S.read_csv(S.S27_DIR / "outputs/routing_features.csv") if r["set"] in ("INT_DEV_CORE", "INT_REGRESSION_CORE")}
    sil = [r["raw_expression"] for r in S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv")]
    wn = [r["text"] for r in S.read_csv(S.S28_DIR / "outputs/weak_non_check.csv")]
    models = {r["canonical_id"] for r in S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")}
    S.wcsv(S.DATA / "evaluation_manifest.csv", [
        {"set": "STEP29_CONTRACTS68", "class": "EXPOSED_REGRESSION", "n": len(c29), "gold": "STEP29 개발 계약(Claude 작성)"},
        {"set": "PILOT274", "class": "EXPOSED_REGRESSION", "n": len(pilot), "gold": "합성 Gold(Claude 작성, STEP21–29 노출)"},
        {"set": "REGRESSION168", "class": "EXPOSED_REGRESSION", "n": len(regg), "gold": "pilot 부분집합 gold_concept"},
        {"set": "NEW_CONTRACTS42", "class": "PRE_REGISTERED_CONTRACT", "n": len(cnew), "gold": "STEP29.1 구현 전 작성(개발 사용)"},
        {"set": "PROSPECTIVE231", "class": "PROSPECTIVE_SYNTHETIC", "n": len(pros), "gold": "템플릿 슬롯 의미(NLU 규칙 미사용), 동결 후 첫 실행"},
        {"set": "SILVER442", "class": "WEAK_EXTERNAL", "n": len(sil), "gold": "약한 양성"}, {"set": "WEAKNON903", "class": "WEAK_EXTERNAL", "n": len(wn), "gold": "약한 음성"}])
    inputs = ([("C29", c["text"], c) for c in c29] + [("NEW", c["text"], c) for c in cnew] + [("PROS", c["text"], c) for c in pros]
              + [("PILOT", r["text_ko"], r) for r in pilot] + [("SIL", t, None) for t in sil] + [("WN", t, None) for t in wn])
    M, errs, mrows = {}, [], []
    cache = {}
    for L in LEVELS:
        key = "P1" if L == "P2" else L
        if key not in cache:
            cache[key] = [(sn, t, ref, analyze(t, key)) for sn, t, ref in inputs]
        outs = cache[key]
        allm = [m for *_, o in outs for m in o["mentions"]]
        m = {"n_inputs": len(outs), "n_mentions": len(allm)}
        m["raw_ok_rate"] = S.rnd(sum(o["source_text"] == t and all(x["raw_span"] == t[x["span_start"]:x["span_end"]] for x in o["mentions"]) for _, t, _, o in outs) / len(outs))
        m["offset_valid_rate"] = S.rnd(sum(isinstance(x["span_start"], int) and 0 <= x["span_start"] < x["span_end"] <= len(x["source_text"])
                                           and x["raw_span"] == x["source_text"][x["span_start"]:x["span_end"]] for x in allm) / len(allm))
        vv = [(sn, t, v5eval(o)) for sn, t, _, o in outs]
        m["v5_violation_inputs"] = sum(bool(v) for *_, v in vv)
        m["v4_violation_inputs"] = sum(bool(v4(t, [x["canonical_id"] for x in o["mentions"] if x["status"] in EXISTING] + [c for x in o["mentions"] for c in (x.get("display") or [])]))
                                       for _, t, _, o in outs)
        for sn, t, v in vv:
            for x in v:
                errs.append({"level": L, "set": sn, "type": "V5_" + x["violation"], "text": t, "got": f"{x['concept']}|{x['raw_span']}"})
        g5 = g6 = 0
        cat = collections.Counter()
        catn = collections.Counter()
        pt = collections.Counter()
        ptn = collections.Counter()
        perr = collections.Counter()
        for sn, t, ref, o in outs:
            if sn == "C29":
                for e in check29(ref, o):
                    g5 += e["type"] == "NEGATION" and bool(e.get("unsafe"))
                    g6 += e["type"] == "EXPERIENCER" and bool(e.get("unsafe"))
                    errs.append({"level": L, "set": sn, "type": e["type"], "text": t, "got": str(e.get("got")), "anchor": e.get("anchor")})
                cat["C29_failed"] += bool(check29(ref, o))
            elif sn == "NEW":
                es = check2(ref, o)
                catn[ref["category"]] += 1
                cat[ref["category"]] += not es
                for e in es:
                    g5 += (e["type"] == "NEGATION" and bool(e.get("unsafe"))) or e["type"] == "MODEL_POSITIVE_FORBIDDEN"
                    g6 += e["type"] == "EXPERIENCER" and bool(e.get("unsafe"))
                    errs.append({"level": L, "set": sn, "type": e["type"], "text": t, "got": str(e.get("got")), "anchor": e.get("anchor")})
            elif sn == "PROS":
                es = check2(ref, o)
                ptn[ref["template"]] += 1
                pt[ref["template"]] += not es
                for e in es:
                    perr[e["type"]] += 1
                    errs.append({"level": L, "set": sn, "type": e["type"], "text": t, "got": str(e.get("got")), "anchor": e.get("anchor")})
        pm = collections.Counter()
        for sn, t, ref, o in outs:
            if sn != "PILOT":
                continue
            golds = json.loads(ref["gold_mentions"] or "[]")
            gm = [g for g in golds if g["concept"] in models]
            gset = {g["concept"] for g in golds}
            ex = [x for x in o["mentions"] if x["status"] in EXISTING]
            used = set()
            for g in gm:
                pm["n"] += 1
                pm["multi_n"] += len(gm) >= 2
                i = next((k for k, x in enumerate(ex) if k not in used and x["canonical_id"] == g["concept"]), None)
                if i is None:
                    errs.append({"level": L, "set": "PILOT", "type": "MISSED_OR_UNMAPPED", "text": t, "got": g["concept"]})
                    continue
                used.add(i)
                x = ex[i]
                pm["matched"] += 1
                pm["multi_matched"] += len(gm) >= 2
                wa = EXP_ASSERT.get(g.get("status"), "PRESENT")
                hist = g.get("status") == "historical"
                other = g.get("subject", "patient") != "patient"
                pm["a_ok"] += x["assertion"] == wa
                pm["t_ok"] += (x["temporality"] in ("PAST", "RESOLVED")) == hist
                pm["e_ok"] += (x["experiencer"] in ("OTHER_PERSON", "MULTIPLE")) == other
                if x["assertion"] != wa:
                    errs.append({"level": L, "set": "PILOT", "type": "NEGATION", "text": t, "got": f"{g['concept']}:{g.get('status')}→{x['assertion']}({x.get('assertion_basis')})"})
                if (x["temporality"] in ("PAST", "RESOLVED")) != hist:
                    errs.append({"level": L, "set": "PILOT", "type": "TEMPORALITY", "text": t, "got": f"{g['concept']}:{g.get('status')}→{x['temporality']}"})
                if g.get("status") == "absent" and x["assertion"] == "PRESENT" and x["model_input"]["polarity"] == "POSITIVE":
                    g5 += 1
                if other and x["experiencer"] == "PATIENT" and x["model_input"]["eligible"]:
                    g6 += 1
            for x in ex:
                if x["canonical_id"] not in gset:
                    pm["wrong"] += 1
                    errs.append({"level": L, "set": "PILOT", "type": "WRONG_CONCEPT", "text": t, "got": f"{x['canonical_id']}|{x['raw_span']}"})
            if ref["should_link"] == "False":
                pm["un"] += 1
                pm["ua"] += bool(ex)
                pm["upp"] += sum(1 for x in o["mentions"] if x["model_input"]["eligible"] and x["model_input"]["polarity"] == "POSITIVE" and x["experiencer"] == "PATIENT")
                if ex:
                    errs.append({"level": L, "set": "PILOT_UNSUPPORTED", "type": "UNSUPPORTED_AUTO", "text": t,
                                 "got": ";".join(f"{x['canonical_id']}|{x['assertion']}|{x['experiencer']}|{x['model_input']['eligible']}" for x in ex)})
            if t in regg and ex:
                pm["ra"] += 1
                pm["rc"] += ex[0]["canonical_id"] == regg[t]
        silm = [x for sn, _, _, o in outs if sn == "SIL" for x in o["mentions"]]
        m.update({"G5_neg_resolved_hypothetical_positive": g5, "G6_other_person_positive": g6,
                  "G7_silver_or_new_model_input": sum(1 for x in allm if (x["status"] in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE") or x.get("evidence_sources") == "SILVER") and x["model_input"]["eligible"]),
                  "G10_uncertain_without_reason": sum(1 for x in allm if (x["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM") and not (x.get("reason") or x.get("guard_reasons"))) or not x["raw_span"]),
                  "pilot_multi_retention": S.rnd(pm["multi_matched"] / pm["multi_n"]), "pilot_retention": S.rnd(pm["matched"] / pm["n"]),
                  "pilot_assertion_agreement": S.rnd(pm["a_ok"] / pm["matched"]), "pilot_temporality_agreement": S.rnd(pm["t_ok"] / pm["matched"]),
                  "pilot_experiencer_agreement": S.rnd(pm["e_ok"] / pm["matched"]), "pilot_wrong_concept_mentions": pm["wrong"],
                  "pilot_unsupported_auto": pm["ua"], "pilot_unsupported_n": pm["un"], "pilot_unsupported_patient_positive": pm["upp"],
                  "reg_precision": S.rnd(pm["rc"] / pm["ra"]) if pm["ra"] else None, "reg_coverage": S.rnd(pm["ra"] / len(regg)),
                  "step29_contracts_failed": cat["C29_failed"]})
        for k in ("EVAL", "RES", "MIX", "MULTI", "EXP", "UNSUP"):
            m[f"new_{k}_pass"], m[f"new_{k}_n"] = cat[k], catn[k]
        m["new_total_pass"] = sum(cat[k] for k in catn)
        for k in sorted(ptn):
            m[f"pros_{k}_pass"], m[f"pros_{k}_n"] = pt[k], ptn[k]
        m["pros_total_pass"] = sum(pt.values())
        m["pros_n"] = sum(ptn.values())
        for k in ("NOT_EXTRACTED", "WRONG_NORMALIZATION", "NEGATION", "TEMPORALITY", "EXPERIENCER", "MODEL_POSITIVE_FORBIDDEN", "UNEXPECTED_SYMPTOM", "OVER_SPLIT"):
            m[f"pros_err_{k}"] = perr[k]
        m["new_over_split"] = sum(1 for e in errs if e["level"] == L and e["set"] == "NEW" and e["type"] == "OVER_SPLIT")
        m["duplicate_span_mentions"] = sum(len(o["mentions"]) - len({(x["span_start"], x["span_end"]) for x in o["mentions"]}) for *_, o in outs)
        m["silver_unknown_uncertain_rate"] = S.rnd(sum(x["status"] in ("UNKNOWN_SYMPTOM", "UNCERTAIN") for x in silm) / len(silm))
        m["weaknon_positive_inputs"] = sum(any(x["status"] in POS for x in o["mentions"]) for sn, _, _, o in outs if sn == "WN")
        m["model_input_eligible_mentions"] = sum(x["model_input"]["eligible"] for x in allm)
        M[L] = m
        if L in ("P1", "P5"):
            for sn, t, _, o in outs:
                if sn in ("NEW", "PROS", "C29"):
                    for x in o["mentions"]:
                        mrows.append({"level": L, "set": sn, "text": t, **{k: x.get(k) for k in ("raw_span", "span_start", "span_end", "status", "canonical_id", "ontology_id",
                                                                                                   "assertion", "assertion_basis", "temporality", "experiencer")},
                                      "resolution": json.dumps(x.get("resolution"), ensure_ascii=False) if x.get("resolution") else "", "guard": ";".join(x.get("guard_reasons") or []),
                                      "model_input": x["model_input"]["polarity"] if x["model_input"]["eligible"] else ""})
        print(L, "done", flush=True)
    S.wcsv(S.DATA / "eval_mentions.csv", mrows)
    S.wcsv(S.OUT / "eval_errors.csv", errs)
    keys = list(M["P5"])
    S.wcsv(S.OUT / "policy_comparison.csv", [{"metric": k, **{L: M[L].get(k) for L in LEVELS}} for k in keys])
    S.dump_json(S.OUT / "eval_summary.json", {"metrics": M, "prereg_ok": prereg_ok, "evaluator_sha256": evaluator_sha()})
    print(S.dumps({L: {k: M[L][k] for k in ("v5_violation_inputs", "v4_violation_inputs", "G5_neg_resolved_hypothetical_positive", "G6_other_person_positive",
                                             "pilot_multi_retention", "pilot_assertion_agreement", "reg_precision", "reg_coverage", "pilot_unsupported_auto",
                                             "new_total_pass", "pros_total_pass")} for L in LEVELS}))


if __name__ == "__main__":
    main()
