"""STEP27 오류·보존·후보 분석 + SILVER_CANDIDATE 데이터 + STEP28 준비 목록(정책은 바꾸지 않음 — 분석 전용).

출력:
 outputs/symptom_retention_analysis.csv  : weak-symptom 단위별 정책 A–E 상태(DEV·EVAL), 전이 요약은 routing_error_summary.json
 outputs/non_symptom_analysis.csv        : weak-non-symptom 단위별 A vs BEST 상태·NON 근거·표시 후보
 outputs/unknown_analysis.csv            : BEST 상태 UNKNOWN_SYMPTOM 전체(집합·weak label·이유·내부 후보·후보 유사도)
 outputs/candidate_suppression_analysis.csv : A 가 후보를 표시한 행의 A 후보 vs BEST 후보, 부적절 표시 가능성 표시
 outputs/representative_cases.csv        : 지시문 §10 대표 표현을 포함하는 데이터 행(탐색적, 지표·조정 미사용)
 outputs/routing_error_summary.json      : 전이표·UNKNOWN↔NON 분리표·원문 보존 검사·부적절 후보 가능 사례 수
 data/external_silver_candidates.csv     : STEP25 BERT-NER-KO 증상 span 442 의 모델·정책 출력(SILVER_CANDIDATE, 사람 검증 아님)
 outputs/step28_candidates.csv           : STEP28 ontology 확장 준비 목록(기계 분류, 의학적 판단 아님)
부적절 표시 가능성(proxy, 사전 고정): 표시 후보가 있는데 (weak-non-symptom) 또는 (표시 후보 최대 cand_sim < 0.2) 또는 (INT 행에서 gold 가 표시 후보에 없음).
STEP28 기계 분류(사전 고정): 증상 근거(SYMPTOM_CUE 또는 p_non<0.5)가 있고 KNOWN 이 아닌 외부 증상 표현 중
 SYNONYM_GAP_CANDIDATE = 내부 1순위 후보 cand_sim ≥ 0.3 이고 KoE 확률 ≥ 0.5(기존 concept 의 표현 보완 후보)
 ONTOLOGY_SEARCH_CANDIDATE = 그 외(77 밖 concept 가능성 → HPO/SNOMED/UMLS 검색 대상). 둘 다 사람 검토 전 후보일 뿐.
"""
import collections
import json

import s27_common as S
from safe_symptom_router import POLICIES, STATUSES

REP_TERMS = ["고혈압", "결핵", "코피", "숨이차", "기침이", "토했", "열이나"]


def main():
    sel = S.load_json(S.OUT / "routing_selection.json")
    best = sel["BEST_POLICY"]
    dec = S.read_csv(S.OUT / "routing_decisions.csv")
    feat = {r["row_id"]: r for r in S.read_csv(S.OUT / "routing_features.csv")}
    bi = {d["row_id"]: json.loads(d["best_interface_json"]) for d in dec}

    ws = [d for d in dec if d["set"].startswith("EXT") and d["weak_label"] == "WEAK_SYMPTOM"]
    S.write_csv(S.OUT / "symptom_retention_analysis.csv",
                [{**{k: d[k] for k in ("row_id", "set", "text", "lin_top1", "koe_top1", "agree", "sym_cue", "non_type", "p_non")},
                  **{f"{p}_status": d[f"{p}_status"] for p in POLICIES}, "A_to_best": f'{d["POLICY_A_status"]}->{d[f"{best}_status"]}'} for d in ws])
    trans = {st: dict(collections.Counter(f'{d["POLICY_A_status"]}->{d[f"{best}_status"]}' for d in ws if d["set"] == st)) for st in ("EXT_DEV", "EXT_EVAL")}

    wn = [d for d in dec if d["set"].startswith("EXT") and d["weak_label"] == "WEAK_NON_SYMPTOM"]
    S.write_csv(S.OUT / "non_symptom_analysis.csv",
                [{**{k: d[k] for k in ("row_id", "set", "text", "lin_top1", "koe_top1", "agree", "sym_cue", "non_type", "p_non")},
                  "A_status": d["POLICY_A_status"], "best_status": d[f"{best}_status"], "best_reasons": d[f"{best}_reasons"],
                  "A_candidates": d["POLICY_A_candidates"], "best_candidates": d[f"{best}_candidates"]} for d in wn])
    trans_wn = {st: dict(collections.Counter(f'{d["POLICY_A_status"]}->{d[f"{best}_status"]}' for d in wn if d["set"] == st)) for st in ("EXT_DEV", "EXT_EVAL")}

    unk = [d for d in dec if d[f"{best}_status"] == "UNKNOWN_SYMPTOM"]
    S.write_csv(S.OUT / "unknown_analysis.csv",
                [{**{k: d[k] for k in ("row_id", "set", "weak_label", "gold_concept", "text", "lin_top1", "koe_top1", "agree", "sym_cue", "p_non")},
                  "reasons": d[f"{best}_reasons"], "internal_candidates": ";".join(bi[d["row_id"]]["raw_record"]["internal_candidate_ids"]),
                  "candidate_similarity": S.dumps(bi[d["row_id"]]["model_evidence"]["candidate_similarity"]),
                  "candidate_transformer_prob": S.dumps(bi[d["row_id"]]["model_evidence"]["candidate_transformer_prob"])} for d in unk])

    def inappropriate(d, cands):
        if not cands:
            return ""
        sims = bi[d["row_id"]]["model_evidence"]["candidate_similarity"]
        f = []
        if d["weak_label"] == "WEAK_NON_SYMPTOM":
            f.append("SHOWN_FOR_WEAK_NON")
        if max((sims.get(c, 0.0) for c in cands), default=0.0) < 0.2:
            f.append("LOW_CAND_SIM")
        if d["set"].startswith("INT") and d["gold_concept"] not in cands:
            f.append("GOLD_NOT_SHOWN")
        return ";".join(f)

    a_shown = [d for d in dec if d["POLICY_A_status"] == "UNCERTAIN" and d["POLICY_A_candidates"]]
    cs = []
    for d in a_shown:
        ac = d["POLICY_A_candidates"].split(";")
        bc = [c for c in d[f"{best}_candidates"].split(";") if c] if d[f"{best}_status"] == "UNCERTAIN" else []
        cs.append({**{k: d[k] for k in ("row_id", "set", "weak_label", "gold_concept", "text")}, "A_candidates": ";".join(ac), "best_status": d[f"{best}_status"],
                   "best_candidates": ";".join(bc), "suppressed": ";".join(c for c in ac if c not in bc),
                   "A_inappropriate_flags": inappropriate(d, ac), "best_inappropriate_flags": inappropriate(d, bc)})
    S.write_csv(S.OUT / "candidate_suppression_analysis.csv", cs)
    inap = {}
    for st in ("EXT_DEV", "EXT_EVAL", "INT_DEV_CORE", "INT_REGRESSION_CORE", "KMC_COMPLEX_STRESS"):
        rs = [c for c in cs if c["set"] == st]
        inap[st] = {"A_shown_rows": len(rs), "A_flagged": sum(bool(c["A_inappropriate_flags"]) for c in rs),
                    "best_shown_rows": sum(bool(c["best_candidates"]) for c in rs), "best_flagged": sum(bool(c["best_inappropriate_flags"]) for c in rs),
                    "A_flag_counts": dict(collections.Counter(x for c in rs for x in c["A_inappropriate_flags"].split(";") if x)),
                    "best_flag_counts": dict(collections.Counter(x for c in rs for x in c["best_inappropriate_flags"].split(";") if x))}
    # BEST 가 새로 표시하는 행(A 는 표시 안 함) — D 는 표시를 줄이기만 하지만 B 의 NON 완화로 UNCERTAIN 이 된 행이 있음
    new_shown = [d for d in dec if d[f"{best}_status"] == "UNCERTAIN" and d[f"{best}_candidates"] and not (d["POLICY_A_status"] == "UNCERTAIN" and d["POLICY_A_candidates"])]
    inap_new = {st: {"rows": sum(d["set"] == st for d in new_shown),
                     "flagged": sum(d["set"] == st and bool(inappropriate(d, d[f"{best}_candidates"].split(";"))) for d in new_shown)}
                for st in ("EXT_DEV", "EXT_EVAL", "INT_DEV_CORE", "INT_REGRESSION_CORE", "KMC_COMPLEX_STRESS")}

    # UNKNOWN ↔ NON 분리(외부 weak label 대비, 보고 집합 EXT_EVAL 와 DEV 따로)
    sep = {}
    for st in ("EXT_DEV", "EXT_EVAL"):
        for p in POLICIES:
            t = collections.Counter((d[f"{p}_status"], d["weak_label"]) for d in dec if d["set"] == st and d["weak_label"] in ("WEAK_SYMPTOM", "WEAK_NON_SYMPTOM"))
            uk_ws, uk_wn, nn_ws, nn_wn = t[("UNKNOWN_SYMPTOM", "WEAK_SYMPTOM")], t[("UNKNOWN_SYMPTOM", "WEAK_NON_SYMPTOM")], t[("NON_SYMPTOM", "WEAK_SYMPTOM")], t[("NON_SYMPTOM", "WEAK_NON_SYMPTOM")]
            sep[f"{st}|{p}"] = {"UNKNOWN_on_WS": uk_ws, "UNKNOWN_on_WN": uk_wn, "NON_on_WS": nn_ws, "NON_on_WN": nn_wn,
                                "UNKNOWN_weak_symptom_share": S.rnd(uk_ws / (uk_ws + uk_wn)) if uk_ws + uk_wn else None,
                                "NON_weak_non_share": S.rnd(nn_wn / (nn_ws + nn_wn)) if nn_ws + nn_wn else None}

    # 원문 보존 검사(전 행·BEST)
    raw = {"rows": len(dec), "source_text_lost": sum(bi[d["row_id"]]["source_text"] != d["text"] for d in dec),
           "raw_expression_missing": sum(not bi[d["row_id"]]["raw_record"]["raw_expression"] for d in dec),
           "unknown_with_canonical": sum(bi[d["row_id"]]["status"] == "UNKNOWN_SYMPTOM" and bi[d["row_id"]]["canonical_id"] is not None for d in dec),
           "unknown_with_displayed_candidates": sum(bi[d["row_id"]]["status"] == "UNKNOWN_SYMPTOM" and bool(bi[d["row_id"]]["candidate_ids"]) for d in dec),
           "non_with_canonical_or_candidates": sum(bi[d["row_id"]]["status"] == "NON_SYMPTOM" and bool(bi[d["row_id"]]["canonical_id"] or bi[d["row_id"]]["candidate_ids"]) for d in dec),
           "complex_auto_accept": sum(bi[d["row_id"]]["status"] == "KNOWN_SYMPTOM" and bool(feat[d["row_id"]]["complex_flags"]) for d in dec),
           "status_counts": dict(collections.Counter(bi[d["row_id"]]["status"] for d in dec))}

    rep = []
    for term in REP_TERMS:
        for d in dec:
            if term in S.nospace(d["text"]):
                rep.append({"term": term, **{k: d[k] for k in ("row_id", "set", "weak_label", "text", "lin_top1", "koe_top1", "p_non", "sym_cue", "non_type")},
                            **{f"{p}_status": d[f"{p}_status"] for p in POLICIES}, "best_candidates": d[f"{best}_candidates"], "best_reasons": d[f"{best}_reasons"]})
    S.write_csv(S.OUT / "representative_cases.csv", rep)

    # SILVER_CANDIDATE 442
    from safe_symptom_router import SafeSymptomRouter, route
    s25 = [r for r in S.read_csv(S.S26.S25_DIR / "outputs/external_predictions.csv") if r["set"] == "A_NERKO_ST"]
    by_ns = {}
    for d in dec:
        if d["set"].startswith("EXT"):
            by_ns.setdefault(S.nospace(d["text"]), d)
    router = None
    silver, live_n = [], 0
    for r in s25:
        d = by_ns.get(S.nospace(r["text"]))
        if d is not None:
            o = bi[d["row_id"]]
            split = d["set"]
            b4 = (d["lin_top1"] if d["POLICY_A_status"] == "KNOWN_SYMPTOM" else "", d["POLICY_A_status"] == "KNOWN_SYMPTOM")
        else:
            router = router or SafeSymptomRouter(best)
            f = router.features(r["text"])
            o = route(best, f, router.params)
            live_n += 1
            split = "NOT_IN_STEP26_UNITS(train-exact/conflict 제외 단위 → live 계산)"
            b4 = (f["lin_top1"] if f["b4_auto"] else "", f["b4_auto"])
        me = o["model_evidence"]
        silver.append({"tier": "SILVER_CANDIDATE", "unit_id": r["unit_id"], "raw_expression": r["text"], "external_source": "BERT_NER_KO",
                       "external_entity_type": "ST", "step26_split": split, "linear_prediction": me["linear_top1"], "linear_margin": me["linear_margin"],
                       "koelectra_prediction": me["transformer_top1"], "koelectra_conf": me["transformer_score"],
                       "hybrid_b_prediction": r["hybrid_b_top1"], "hybrid_b_auto": r["hybrid_b_auto"],
                       "b4_auto": b4[1], "b4_prediction": b4[0], "step27_policy": best, "step27_status": o["status"], "step27_decision": o["decision"],
                       "step27_canonical_id": o["canonical_id"] or "", "candidate_concept_ids": ";".join(o["candidate_ids"]),
                       "internal_candidate_ids": ";".join(o["raw_record"]["internal_candidate_ids"]), "agreement": me["agreement"],
                       "non_symptom_score": me["non_symptom_score"], "train_similarity": me["train_similarity"],
                       "candidate_similarity": S.dumps(me["candidate_similarity"]), "symptom_cue": me["symptom_cue"], "non_type_cue": me["non_type_cue"],
                       "unknown_reason": ";".join(o["raw_record"]["uncertain_reason"]) if o["status"] != "KNOWN_SYMPTOM" else "",
                       "human_verified": False})
    S.write_csv(S.DATA / "external_silver_candidates.csv", silver)

    # STEP28 준비
    s28 = []
    seen = set()
    for row in silver:
        if row["step27_status"] == "KNOWN_SYMPTOM":
            continue
        ns = S.nospace(row["raw_expression"])
        if ns in seen:
            continue
        seen.add(ns)
        sym_ev = row["symptom_cue"] or row["non_symptom_score"] < 0.5
        ic = row["internal_candidate_ids"].split(";")
        sims = json.loads(row["candidate_similarity"])
        top = ic[0] if ic and ic[0] else ""
        kp = row["koelectra_conf"] if row["koelectra_prediction"] == top else 0.0
        if not sym_ev:
            cat = "TYPE_UNCLEAR_REVIEW"
        elif sims.get(top, 0.0) >= 0.3 and kp >= 0.5:
            cat = "SYNONYM_GAP_CANDIDATE"
        else:
            cat = "ONTOLOGY_SEARCH_CANDIDATE"
        s28.append({"raw_expression": row["raw_expression"], "source": "BERT_NER_KO:ST", "step27_status": row["step27_status"],
                    "machine_category": cat, "nearest_supported_concept": top, "nearest_cand_sim": sims.get(top, 0.0), "koelectra_conf_for_nearest": kp,
                    "unknown_reason": row["unknown_reason"], "note": "기계 분류 — 의학적 판단·정답 아님"})
    S.write_csv(S.OUT / "step28_candidates.csv", s28)

    summ = {"BEST_POLICY": best, "weak_symptom_transitions_A_to_best": trans, "weak_non_transitions_A_to_best": trans_wn,
            "unknown_vs_non_separation": sep, "raw_preservation_check(best, all rows)": raw,
            "inappropriate_display_proxy(A shown rows)": inap, "inappropriate_display_proxy(best newly shown rows)": inap_new,
            "silver": {"n": len(silver), "live_computed": live_n, "status_counts": dict(collections.Counter(r["step27_status"] for r in silver)),
                       "split_counts": dict(collections.Counter(r["step26_split"] for r in silver))},
            "step28": dict(collections.Counter(r["machine_category"] for r in s28)), "representative_rows": len(rep),
            "statuses": list(STATUSES)}
    S.dump_json(S.OUT / "routing_error_summary.json", summ)
    print(S.dumps({k: v for k, v in summ.items() if k != "unknown_vs_non_separation"}))


if __name__ == "__main__":
    main()
