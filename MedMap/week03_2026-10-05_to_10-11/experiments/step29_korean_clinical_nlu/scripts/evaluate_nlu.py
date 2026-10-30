"""STEP29 평가(임상 정확도 아님). 지표·데이터는 실행 전 고정(2026-10-11). 코드 SHA 가 data/prereg.json(동결본)과 다르면 실행하지 않는다.

[데이터 — data/evaluation_manifest.csv 에 출처·라벨 종류 기록]
 CONTRACTS68   개발용 합성 계약(규칙 작성자가 구현 전 작성, 규칙 개발에 사용) — 독립 정답 아님
 METAMORPHIC   계약 파일의 변환 6 묶음(36 문장) — 규칙 일관성
 PILOT274      STEP21 pilot_gold(합성·Claude 작성, gold_mentions concept·status·subject) — STEP21–28.8 반복 노출. 이번 규칙 개발에 쓰지 않음(평가 1회)
 REGRESSION168 PILOT274 중 STEP27 INT 세트(gold_concept) — 단일 증상 비회귀(S1), STEP28.8 P5 와 같은 정의(첫 EXISTING mention)
 SILVER442 · WEAKNON903  약한 라벨 — UNKNOWN 비율(S4)·비증상 연결 위험(참고)
[지표 — 분모 명시]
 G1 raw_ok_rate = 출력 source_text == 입력 이고 모든 mention raw_span == source_text[s:e] 인 입력 / 전체 입력
 G2 offset_valid_rate = 0 ≤ s < e ≤ len, raw_span == source_text[s:e], raw_span ⊂ source_sentence 인 mention / 전체 mention
 G3 = 검사기 v4 위반 입력(EXISTING concept(assertion 무관) + 표시 후보) · G4·G5·G6·G9 = build_report 문서열 정의
 pilot: gold mention(77 concept) 을 출력 EXISTING mention canonical 로 순서대로 대응. retention = 대응 / gold mention ·
   multi_retention = 77 gold mention ≥2 발화만 · assertion 일치(present→PRESENT, absent→ABSENT, uncertain→POSSIBLE, historical→PRESENT) ·
   시점 일치(historical ↔ PAST/RESOLVED) · 주체 일치(patient ↔ PATIENT, 그 외 ↔ OTHER_PERSON/MULTIPLE) — 대응 mention 기준 ·
   wrong_concept = EXISTING mention 중 canonical 이 그 발화 gold concept 집합 밖 · unsupported = should_link False 발화 중 EXISTING mention 있는 발화
 reg: 첫 EXISTING mention canonical == gold_concept → precision(분모 = EXISTING 있는 발화) · coverage(분모 168)
 오류 종류 별도: 계약 NOT_EXTRACTED · WRONG_NORMALIZATION · NEGATION · TEMPORALITY · EXPERIENCER(+ ATTRIBUTE·ONSET·FREQUENCY·SCOPE·ROLE·MUST_NOT_AUTO)
출력: outputs/{eval_summary.json, policy_comparison.csv, metamorphic_results.json} · data/{evaluation_manifest.csv, eval_mentions.csv}
"""
from __future__ import annotations

import collections
import json

import s29_common as S
from clinical_nlu_pipeline import LEVELS, analyze
from contract_check import check, concept_of, load
from evaluator_v4 import evaluator_sha, violations
from metamorphic import run as mrun

EXISTING = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")
POS = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "EXISTING_SUBTYPE", "NEW_ONTOLOGY_CANDIDATE")
EXP_ASSERT = {"present": "PRESENT", "absent": "ABSENT", "uncertain": "POSSIBLE", "historical": "PRESENT"}


def main():
    pre = S.load_json(S.DATA / "prereg.json")
    now = {p.name: S.sha256(p) for p in sorted((S.STEP / "scripts").glob("*.py")) if p.name in pre["frozen_scripts"]}
    assert now == pre["frozen_scripts"], f"동결 이후 코드 변경: {[k for k in now if now[k] != pre['frozen_scripts'].get(k)]}"
    assert S.sha256(S.DATA / "synthetic_nlu_contracts.json") == pre["contracts_sha256"]
    con = load()
    pilot = S.read_csv(S.S21_DIR / "data/pilot_gold.csv")
    regg = {r["text"]: r["gold_concept"] for r in S.read_csv(S.S27_DIR / "outputs/routing_features.csv") if r["set"] in ("INT_DEV_CORE", "INT_REGRESSION_CORE")}
    sil = [r["raw_expression"] for r in S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv")]
    wn = [r["text"] for r in S.read_csv(S.S28_DIR / "outputs/weak_non_check.csv")]
    models = {r["canonical_id"] for r in S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")}
    S.wcsv(S.DATA / "evaluation_manifest.csv", [
        {"set": "CONTRACTS68", "n": len(con["contracts"]), "label": "DEVELOPMENT_SYNTHETIC(규칙 개발 사용)", "source": "data/synthetic_nlu_contracts.json"},
        {"set": "METAMORPHIC", "n": 6 * len(con["metamorphic"]), "label": "DEVELOPMENT_SYNTHETIC(일관성)", "source": "data/synthetic_nlu_contracts.json"},
        {"set": "PILOT274", "n": len(pilot), "label": "SYNTHETIC_GOLD(Claude 작성, 반복 노출, 이번 개발 미사용)", "source": "exp/step21…/data/pilot_gold.csv"},
        {"set": "REGRESSION168", "n": len(regg), "label": "SYNTHETIC_GOLD(PILOT274 부분집합)", "source": "exp/step27…/outputs/routing_features.csv"},
        {"set": "SILVER442", "n": len(sil), "label": "WEAK_POSITIVE", "source": "exp/step28…/data/external_silver_expansion.csv"},
        {"set": "WEAKNON903", "n": len(wn), "label": "WEAK_NEGATIVE", "source": "exp/step28…/outputs/weak_non_check.csv"}])
    inputs = ([("CONTRACTS68", c["text"], c) for c in con["contracts"]] + [("PILOT274", r["text_ko"], r) for r in pilot] + [("SILVER442", t, None) for t in sil]
              + [("WEAKNON903", t, None) for t in wn])
    M, mention_rows, err_rows = {}, [], []
    meta = {}
    for L in LEVELS:
        outs = []
        for sname, t, ref in inputs:
            outs.append((sname, t, ref, analyze(t, L)))
        allm = [m for _, _, _, o in outs for m in o["mentions"]]
        raw_ok = sum(o["source_text"] == t and all(m["raw_span"] == t[m["span_start"]:m["span_end"]] for m in o["mentions"]) for _, t, _, o in outs)
        off_ok = sum(isinstance(m["span_start"], int) and isinstance(m["span_end"], int) and 0 <= m["span_start"] < m["span_end"] <= len(m["source_text"])
                     and m["raw_span"] == m["source_text"][m["span_start"]:m["span_end"]] and m["raw_span"] in m["source_sentence"] for m in allm)
        g3 = sum(bool(violations(t, [m["canonical_id"] for m in o["mentions"] if m["status"] in EXISTING] + [c for m in o["mentions"] for c in (m.get("display") or [])]))
                 for _, t, _, o in outs)
        g6 = sum(1 for m in allm if (m["status"] in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE") or m.get("evidence_sources") == "SILVER") and m["model_input"]["eligible"])
        g9 = sum(1 for m in allm if m["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM") and not (m.get("reason") or m.get("guard_reasons")) or not m["raw_span"])
        # 계약
        cerr = []
        nexp = 0
        for sname, t, ref, o in outs:
            if sname != "CONTRACTS68":
                continue
            nexp += len(ref["mentions"])
            for e in check(ref, o):
                cerr.append({**e, "id": ref["id"], "category": ref["category"], "text": t, "level": L})
        ce = collections.Counter(e["type"] for e in cerr)
        extracted = nexp - ce["NOT_EXTRACTED"]
        # pilot
        pm = {"n_gold": 0, "matched": 0, "multi_n": 0, "multi_matched": 0, "assert_ok": 0, "temp_ok": 0, "exp_ok": 0, "wrong": 0, "unsup_auto": 0, "unsup_n": 0,
              "neg_unsafe": 0, "other_unsafe": 0, "reg_auto": 0, "reg_correct": 0}
        for sname, t, ref, o in outs:
            if sname != "PILOT274":
                continue
            gm = [g for g in json.loads(ref["gold_mentions"] or "[]") if g["concept"] in models]
            gset = {g["concept"] for g in json.loads(ref["gold_mentions"] or "[]")}
            ex = [m for m in o["mentions"] if m["status"] in EXISTING]
            used = set()
            multi = len(gm) >= 2
            for g in gm:
                pm["n_gold"] += 1
                pm["multi_n"] += multi
                i = next((k for k, m in enumerate(ex) if k not in used and m["canonical_id"] == g["concept"]), None)
                if i is None:
                    err_rows.append({"level": L, "set": "PILOT274", "type": "MISSED_OR_UNMAPPED", "text": t, "gold": g["concept"], "gold_status": g.get("status"),
                                     "got": ";".join(f"{m['canonical_id'] or m.get('ontology_id')}:{m['status']}" for m in o["mentions"])})
                    continue
                used.add(i)
                m = ex[i]
                pm["matched"] += 1
                pm["multi_matched"] += multi
                wa = EXP_ASSERT.get(g.get("status"), "PRESENT")
                pm["assert_ok"] += m["assertion"] == wa
                hist = g.get("status") == "historical"
                pm["temp_ok"] += (m["temporality"] in ("PAST", "RESOLVED")) == hist
                other = g.get("subject", "patient") != "patient"
                pm["exp_ok"] += (m["experiencer"] in ("OTHER_PERSON", "MULTIPLE")) == other
                if g.get("status") == "absent" and m["assertion"] == "PRESENT" and m["model_input"]["polarity"] == "POSITIVE":
                    pm["neg_unsafe"] += 1
                if other and m["experiencer"] == "PATIENT" and m["model_input"]["eligible"]:
                    pm["other_unsafe"] += 1
                for typ, bad in (("NEGATION", m["assertion"] != wa), ("TEMPORALITY", (m["temporality"] in ("PAST", "RESOLVED")) != hist),
                                 ("EXPERIENCER", (m["experiencer"] in ("OTHER_PERSON", "MULTIPLE")) != other)):
                    if bad:
                        err_rows.append({"level": L, "set": "PILOT274", "type": typ, "text": t, "gold": f"{g['concept']}:{g.get('status')}:{g.get('subject')}",
                                         "got": f"{m['assertion']}|{m['temporality']}|{m['experiencer']}|{m['raw_span']}"})
            for m in ex:
                if m["canonical_id"] not in gset:
                    pm["wrong"] += 1
                    err_rows.append({"level": L, "set": "PILOT274", "type": "WRONG_CONCEPT", "text": t, "gold": ";".join(sorted(gset)), "got": f"{m['canonical_id']}|{m['raw_span']}"})
            if ref["should_link"] == "False":
                pm["unsup_n"] += 1
                pm["unsup_auto"] += bool(ex)
            if t in regg:
                if ex:
                    pm["reg_auto"] += 1
                    pm["reg_correct"] += ex[0]["canonical_id"] == regg[t]
        silm = [m for sname, _, _, o in outs if sname == "SILVER442" for m in o["mentions"]]
        M[L] = {"n_inputs": len(outs), "n_mentions": len(allm), "G1_raw_ok_rate": S.rnd(raw_ok / len(outs)), "G2_offset_valid_rate": S.rnd(off_ok / len(allm)) if allm else 1.0,
                "G3_semantic_violation_inputs": g3, "G4_neg_safety_errors": sum(1 for e in cerr if e["type"] == "NEGATION" and e.get("unsafe")) + pm["neg_unsafe"],
                "G5_other_safety_errors": sum(1 for e in cerr if e["type"] == "EXPERIENCER" and e.get("unsafe")) + pm["other_unsafe"],
                "G6_silver_or_new_model_input": g6, "G9_uncertain_without_reason": g9,
                "contract_mentions": nexp, "contract_extracted": extracted, "contract_failed_cases": len({e["id"] for e in cerr}),
                "err1_not_extracted": ce["NOT_EXTRACTED"], "err2_wrong_normalization": ce["WRONG_NORMALIZATION"], "err3_negation": ce["NEGATION"],
                "err4_temporality": ce["TEMPORALITY"], "err5_experiencer": ce["EXPERIENCER"], "err_other(attr/onset/freq/scope/role/must_not)":
                    ce["ATTRIBUTE"] + ce["ONSET"] + ce["FREQUENCY"] + ce["SCOPE"] + ce["ROLE"] + ce["MUST_NOT_AUTO"],
                "contract_assertion_pass": S.rnd(1 - ce["NEGATION"] / extracted) if extracted else None,
                "contract_temporality_pass": S.rnd(1 - ce["TEMPORALITY"] / extracted) if extracted else None,
                "contract_experiencer_pass": S.rnd(1 - ce["EXPERIENCER"] / extracted) if extracted else None,
                "pilot_gold_mentions": pm["n_gold"], "pilot_matched": pm["matched"], "pilot_retention": S.rnd(pm["matched"] / pm["n_gold"]),
                "pilot_multi_n": pm["multi_n"], "pilot_multi_retention": S.rnd(pm["multi_matched"] / pm["multi_n"]) if pm["multi_n"] else None,
                "pilot_assertion_agreement": S.rnd(pm["assert_ok"] / pm["matched"]) if pm["matched"] else None,
                "pilot_temporality_agreement": S.rnd(pm["temp_ok"] / pm["matched"]) if pm["matched"] else None,
                "pilot_experiencer_agreement": S.rnd(pm["exp_ok"] / pm["matched"]) if pm["matched"] else None,
                "pilot_wrong_concept_mentions": pm["wrong"], "pilot_unsupported_auto": pm["unsup_auto"], "pilot_unsupported_n": pm["unsup_n"],
                "reg_coverage": S.rnd(pm["reg_auto"] / len(regg)), "reg_precision": S.rnd(pm["reg_correct"] / pm["reg_auto"]) if pm["reg_auto"] else None,
                "silver_mentions": len(silm), "silver_unknown_uncertain_rate": S.rnd(sum(m["status"] in ("UNKNOWN_SYMPTOM", "UNCERTAIN") for m in silm) / len(silm)) if silm else None,
                "weaknon_positive_inputs": sum(any(m["status"] in POS for m in o["mentions"]) for sname, _, _, o in outs if sname == "WEAKNON903"),
                "weaknon_positive_present_inputs": sum(any(m["status"] in POS and m["assertion"] == "PRESENT" for m in o["mentions"]) for sname, _, _, o in outs if sname == "WEAKNON903"),
                "model_input_eligible_mentions": sum(m["model_input"]["eligible"] for m in allm)}
        err_rows += cerr
        if L in ("NLU_P0", "NLU_P5"):
            for sname, t, ref, o in outs:
                if sname in ("CONTRACTS68", "PILOT274"):
                    for m in o["mentions"]:
                        mention_rows.append({"level": L, "set": sname, "text": t, **{k: m.get(k) for k in ("raw_span", "span_start", "span_end", "role", "status", "canonical_id",
                                                                                                           "ontology_id", "assertion", "temporality", "onset_text", "time_scope",
                                                                                                           "experiencer", "experiencer_basis", "evidence_level", "silver")},
                                             "attributes": ";".join(m.get("attributes", [])), "guard": ";".join(m.get("guard_reasons") or []),
                                             "model_input": json.dumps(m["model_input"]["polarity"]) if m["model_input"]["eligible"] else ""})
        meta[L] = mrun(analyze, L)
        print(L, "done", flush=True)
    S.wcsv(S.DATA / "eval_mentions.csv", mention_rows)
    S.wcsv(S.OUT / "eval_errors.csv", [{k: str(v) for k, v in e.items()} for e in err_rows])
    keys = list(M["NLU_P5"])
    S.wcsv(S.OUT / "policy_comparison.csv", [{"metric": k, **{L: M[L][k] for L in LEVELS}} for k in keys])
    for L in LEVELS:
        M[L]["metamorphic_pass"] = f"{meta[L]['pass']}/{meta[L]['n']}"
    S.dump_json(S.OUT / "metamorphic_results.json", {"label": "규칙 일관성(개발용 변환 — 임상 정확도 아님)", "summary": meta["NLU_P5"]["summary"],
                                                     "by_level": {L: meta[L]["summary"] for L in LEVELS}, "rows_NLU_P5": meta["NLU_P5"]["rows"]})
    S.dump_json(S.OUT / "eval_summary.json", {"metrics": M, "evaluator_sha256": evaluator_sha(), "contracts_sha256": S.sha256(S.DATA / "synthetic_nlu_contracts.json"),
                                              "step28_8_p5_reference": {"precision": 0.9451, "coverage": 0.5417}})
    print(S.dumps({L: {k: M[L][k] for k in ("G2_offset_valid_rate", "G3_semantic_violation_inputs", "G4_neg_safety_errors", "G5_other_safety_errors", "pilot_multi_retention",
                                             "pilot_assertion_agreement", "pilot_temporality_agreement", "pilot_experiencer_agreement", "reg_precision", "reg_coverage",
                                             "contract_failed_cases", "metamorphic_pass")} for L in LEVELS}))


if __name__ == "__main__":
    main()
