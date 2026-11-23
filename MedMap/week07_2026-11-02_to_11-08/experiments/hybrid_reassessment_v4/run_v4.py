"""v4 실행: CASE 1~15(합성 환자), TEST A~F, 그래프 vs 평면 규칙표, v3 대비 출력 차이 감사.
결과 outputs/v4_cases.json, v4_trees.json, v4_tests.json, v4_compare.json, v4_v3_diff.json. 기술 검증용, 임상 정확도 아님."""
import json
import sys
import time
from collections import Counter
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from hybrid4 import graphs as GR, logic as LG, reason as RS  # noqa: E402
from hybrid4.graphs import Doc, Episode, Hypothesis  # noqa: E402
from hybrid3 import reasoner as R3  # noqa: E402
from hybrid.schema import AssertedBy, DxStatus  # noqa: E402

PE = "DX:Pulmonary embolism"
SUSP = "Pulmonary embolism is suspected. Clinical probability was assessed as intermediate using the Wells score. The patient is hemodynamically stable."
SUSP_LOW = "Pulmonary embolism is suspected. Clinical probability was assessed as low using the Wells score. The patient is hemodynamically stable."
SUSP_HIGH = "Pulmonary embolism is suspected. Clinical probability was assessed as high using the Wells score. The patient is hemodynamically stable."
POS = "IMPRESSION: Acute pulmonary embolism in the right lower lobe segmental arteries."
NEG = "IMPRESSION: No evidence of pulmonary embolism."
DD_ELISA = "D-dimer measured by ELISA was normal, below the age-adjusted cut-off."
DD_MOD = "Moderately sensitive D-dimer was normal, below the fixed cut-off."


def cur(hid="h1", ep="E1", concept=PE, label="Pulmonary embolism"):
    return Hypothesis(hid, label, concept, 0.0, episode_id=ep)


def spec():
    """사례 정의: episodes, hyps[(Hypothesis, physician_confirmed)], docs[(Doc, episode or None)], tests[(id, event, at, ep)], as_of[]."""
    E1 = [Episode("E1", "CURRENT_EVALUATION", "현재 PE 의심")]
    S = {}
    S["C01_single_positive"] = (E1, [(cur(), True)], [(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), None)], [], [5.0])
    S["C02_single_negative"] = (E1, [(cur(), True)], [(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), None)], [], [5.0])
    S["C03_multiple_evidence"] = (E1, [(cur(), True)], [(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None),
                                  (Doc("u1", "Compression ultrasound shows femoral deep vein thrombosis.", "NOTE", 1.0, 1.5), None),
                                  (Doc("l1", "Laboratory testing revealed an elevated D-dimer (4365 ng/mL).", "LAB", 1.0, 1.6), None),
                                  (Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), None), (Doc("o1", "A ventilation-perfusion scan was ordered.", "NOTE", 4.1, 4.1), None),
                                  (Doc("x1", "The patient has dyspnea and tachycardia.", "NOTE", 0.5, 1.0), None)], [("vq", "ORDER", 4.1, "E1")], [5.0])
    S["C04_and_partly_unknown"] = (E1, [(cur(), True)], [(Doc("n1", "Pulmonary embolism is suspected.", "NOTE", 0.5, 1.0), None), (Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), None)], [], [5.0])
    S["C05_and_explicit_false"] = (E1, [(cur(), True)], [(Doc("n1", SUSP_HIGH, "NOTE", 0.5, 1.0), None), (Doc("l1", DD_ELISA, "LAB", 1.0, 1.5), None)], [], [2.0])
    S["C05b_required_false_fallback"] = (E1, [(cur(), True)], [(Doc("n1", SUSP_LOW, "NOTE", 0.5, 1.0), None), (Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), None)], [], [5.0])
    S["C06a_or_path_intermediate_elisa"] = (E1, [(cur(), True)], [(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("l1", DD_ELISA, "LAB", 1.0, 1.5), None)], [], [2.0])
    S["C06b_or_path_low_moderate"] = (E1, [(cur(), True)], [(Doc("n1", SUSP_LOW, "NOTE", 0.5, 1.0), None), (Doc("l1", DD_MOD, "LAB", 1.0, 1.5), None)], [], [2.0])
    S["C06c_or_gate_intermediate_moderate"] = (E1, [(cur(), True)], [(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("l1", DD_MOD, "LAB", 1.0, 1.5), None)], [], [2.0])
    S["C07_conflicting_records"] = (E1, [(cur(), True)], [(Doc("n1", SUSP_LOW, "NOTE", 0.5, 1.0), None), (Doc("n2", "Clinical probability was assessed as high.", "NOTE", 0.6, 1.1), None),
                                    (Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), None)], [], [5.0])
    eps8 = [Episode("E0", "PAST_EPISODE", "2024 확진 PE", 1.0), Episode("E2", "RECURRENCE", "현재 재발 의심", 200.0)]
    S["C08_past_vs_recurrence"] = (eps8, [(Hypothesis("h0", "Pulmonary embolism", PE, 1.0, DxStatus.CONFIRMED_DIAGNOSIS, "E0", "PAST_EPISODE", 1.0), True),
                                          (Hypothesis("h3", "Pulmonary embolism", PE, 200.0, episode_id="E2", kind="RECURRENCE", target_time=200.0), True)],
                                   [(Doc("n0", "Pulmonary embolism was diagnosed in 2024 and anticoagulation was completed.", "NOTE", 5.0, 5.0), "E0"),
                                    (Doc("n2", "New dyspnea; recurrent pulmonary embolism is suspected. Clinical probability was assessed as intermediate.", "NOTE", 200.0, 200.0), None),
                                    (Doc("r2", NEG, "CTPA_REPORT", 201.0, 202.0), "E2"), (Doc("u1", "No evidence of pulmonary embolism.", "CTPA_REPORT", 150.0, 151.0), None)], [], [203.0])
    eps9 = [Episode("E0", "PAST_EPISODE", "확진 PE", 1.0)]
    S["C09_post_treatment_followup"] = (eps9, [(Hypothesis("h0", "Pulmonary embolism", PE, 1.0, DxStatus.CONFIRMED_DIAGNOSIS, "E0", "PAST_EPISODE", 1.0), True)],
                                        [(Doc("n0", "Pulmonary embolism was diagnosed one month ago and she is currently receiving apixaban.", "NOTE", 30.0, 30.0), "E0"),
                                         (Doc("r9", "Follow-up CTPA after three months of anticoagulation showed no pulmonary embolism.", "CTPA_REPORT", 90.0, 91.0), "E0"),
                                         (Doc("p9", "Perfusion scan was normal at follow-up after treatment for pulmonary embolism.", "NOTE", 92.0, 93.0), "E0")], [], [95.0])
    S["C10_delayed_result"] = (E1, [(cur(), True)], [(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("o1", "CTPA was ordered to rule out pulmonary embolism.", "NOTE", 1.0, 1.0), None),
                                                     (Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), None)], [("ctpa", "ORDER", 1.0, "E1"), ("ctpa", "COLLECT", 2.0, "E1"), ("ctpa", "RESULT", 4.0, "E1")], [1.5, 3.0, 4.0])
    S["C11_correction"] = (E1, [(cur(), True)], [(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), None),
                                                 (Doc("r2", NEG, "CTPA_REPORT", 2.0, 7.0, supersedes="r1"), None)], [("ctpa", "RESULT", 4.0, "E1"), ("ctpa", "CORRECT", 7.0, "E1")], [6.9, 7.0])
    S["C12_unsupported"] = (E1, [(cur(), True), (cur("h2", "E1", "DX:Aortic dissection", "Aortic dissection"), True)],
                            [(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("e1", "Echocardiography showed a pericardial effusion and the aorta was dilated.", "NOTE", 2.0, 3.0), None)], [], [4.0])
    S["C15_working_dx_vs_ai_candidate"] = (E1, [(cur("h5", "E1", "DX:Pericarditis", "Pericarditis"), True),
                                                (Hypothesis("h6", "Pulmonary embolism", PE, 0.0, episode_id="E1", asserted_by=AssertedBy.MODEL_EXTRACTED), False)],
                                           [(Doc("n1", "Pleuritic chest pain. Pulmonary embolism was confirmed according to the outside note.", "NOTE", 0.5, 1.0), None),
                                            (Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), None)], [], [5.0])
    return S


def build(case, drop_docs=(), relink=None):
    eps, hyps, docs, tests, _ = spec()[case]
    pg = GR.PatientGraph(f"SYN-{case}")
    for e in eps:
        pg.add_episode(e)
    for h, conf in hyps:
        pg.add_hypothesis(h, conf)
    for d, ep in docs:
        if d.doc_id in drop_docs:
            continue
        pg.add_record(d, (relink or {}).get(d.doc_id, ep))
    for t in tests:
        pg.add_test_event(*t)
    return pg


def key_items(res):
    return {f"{h['hyp_id']}|{i['evidence_id']}|{i['relation_id'] or i['hold_reason']}": i["direction"] for h in res["hypotheses"] for i in h["items"]}


REL = GR.normalized_relations()
G, FL = RS.Reasoner(REL, "graph"), RS.Reasoner(REL, "flat")
cases, trees, cmp_rows = {}, {}, []
for c, (_, _, _, _, ts) in spec().items():
    pg = build(c)
    cases[c] = {"patient_graph_stats": pg.g.stats(), "records": {d: n["episode_link"] for d, n in ((v["doc_id"], v) for v in pg.g.nodes.values() if v["kind"] == "SOURCE_RECORD")}, "states": []}
    for t in ts:
        rg, rf = G.evaluate(pg, t), FL.evaluate(pg, t)
        cases[c]["states"].append({"as_of": t, "graph": rg})
        trees[f"{c}@{t}"] = RS.review_tree(rg, pg)
        kg_, kf = key_items(rg), key_items(rf)
        same_dec = all(json.dumps(i.get("decision"), sort_keys=True, default=str) == json.dumps(j.get("decision"), sort_keys=True, default=str)
                       and i["sources"] == j["sources"] and i["gaps"] == j["gaps"] for hg, hf in zip(rg["hypotheses"], rf["hypotheses"]) for i, j in zip(hg["items"], hf["items"]))
        cmp_rows.append({"case": c, "as_of": t, "n_items": len(kg_), "direction_agree": sum(kg_[k] == kf.get(k) for k in kg_), "keys_equal": set(kg_) == set(kf),
                         "decision_trace_equal": same_dec, "graph_paths": sorted({" ".join(i["path"]) for h in rg["hypotheses"] for i in h["items"] if i["path"]})})
(H / "outputs/v4_cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
(H / "outputs/v4_trees.json").write_text(json.dumps(trees, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

# ---------------- TEST A~F ----------------
T = {}
base_dirs = {f"{c}@{t}": key_items(G.evaluate(build(c), t)) for c, (*_, ts) in spec().items() for t in ts}
for rid in ("PE-CTPA-POSITIVE", "PE-CTPA-NEGATIVE", "PE-DDIMER-NORMAL"):
    g2 = RS.Reasoner(GR.normalized_relations(disabled=[rid]), "graph")
    ch = {}
    for k, before in base_dirs.items():
        c, t = k.split("@")
        after = key_items(g2.evaluate(build(c), float(t)))
        for kk, v in before.items():
            a = after.get(kk) or next((after[x] for x in after if x.split("|")[:2] == kk.split("|")[:2]), None)
            if a != v:
                ch[f"{k}|{kk}"] = (v, a)
    T[f"A_disable_{rid}"] = {"changed": ch, "n_changed": len(ch), "all_changed_depend_on_relation": all(rid in k for k in ch)}
rb = key_items(G.evaluate(build("C03_multiple_evidence"), 5.0))
ra = key_items(G.evaluate(build("C03_multiple_evidence", drop_docs=("u1",)), 5.0))
T["B_remove_ultrasound_record"] = {"removed": {k: v for k, v in rb.items() if k not in ra}, "changed_other": {k: (rb[k], ra[k]) for k in rb if k in ra and rb[k] != ra[k]}}
e1 = G.evaluate(build("C08_past_vs_recurrence"), 203.0)
e2 = G.evaluate(build("C08_past_vs_recurrence", relink={"r2": "E0"}), 203.0)
e3 = G.evaluate(build("C08_past_vs_recurrence", relink={"u1": "E2"}), 203.0)
pick = lambda res, doc: {h["episode_id"]: [(i["direction"], i["relation_id"], i["stage"] if "stage" in i else i["hold_reason"]) for i in h["items"] if i["source_record_id"] == doc] for h in res["hypotheses"]}  # noqa: E731
T["C_episode_relink"] = {"r2_in_E2": pick(e1, "r2"), "r2_relinked_E0": pick(e2, "r2"), "u1_unresolved": [h["unresolved_episode_evidence"] for h in e1["hypotheses"]][0], "u1_relinked_E2": pick(e3, "u1")}
T["D_graph_vs_flat"] = {"rows": cmp_rows, "items": sum(r["n_items"] for r in cmp_rows), "direction_agree": sum(r["direction_agree"] for r in cmp_rows),
                        "all_keys_equal": all(r["keys_equal"] for r in cmp_rows), "all_decision_traces_equal": all(r["decision_trace_equal"] for r in cmp_rows)}
T["E_and_or_same_structure"] = {"structures_identical": all(G.kg.g.nodes[f"REL:{r['relation_id']}"]["conditions"] == FL.table.lookup(r["finding"], r["target_diagnosis"])[0]["structured"].to_dict() for r in REL),
                                "or_relations": [r["relation_id"] for r in REL if r["structured"].alternatives]}
need = ("sentence", "source_record_id", "evidence_id", "relation_id", "available_time")
traces = {"graph": [], "flat": []}
for c, (*_, ts) in spec().items():
    for mode, rsn in (("graph", G), ("flat", FL)):
        pg = build(c)
        for h in rsn.evaluate(pg, ts[-1])["hypotheses"]:
            for i in h["items"]:
                if i["direction"] in LG.DIRECTIONAL:
                    ok = all(i.get(k) not in (None, "") for k in need) and bool(i["sources"]) and all(s["quote"] for s in i["sources"]) and bool(i["decision"])
                    chain = mode == "graph" and any(e["dst"] == f"REC:{i['source_record_id']}" for e in pg.g.outs(i["evidence_id"], "DERIVED_FROM"))
                    traces[mode].append({"case": c, "evidence_id": i["evidence_id"], "complete": ok, "graph_edge_chain_to_record": chain})
T["F_provenance"] = {m: {"directional": len(v), "complete": sum(x["complete"] for x in v), "graph_chain": sum(x["graph_edge_chain_to_record"] for x in v)} for m, v in traces.items()}


def timeit(rsn, n=5):
    pgs = {c: build(c) for c in spec()}
    t0 = time.perf_counter()
    for _ in range(n):
        for c, (*_, ts) in spec().items():
            for t in ts:
                rsn.evaluate(pgs[c], t)
    return (time.perf_counter() - t0) / n


T["cost"] = {"graph_sec_per_full_run": round(timeit(G), 4), "flat_sec_per_full_run": round(timeit(FL), 4),
             "loc": {f: sum(1 for _ in open(H / f"hybrid4/{f}.py", encoding="utf-8")) for f in ("logic", "graphs", "reason", "flat")},
             "graph_A_stats": G.kg.g.stats(), "relation_edit_points": "둘 다 P2 카탈로그 1곳(normalized_relations 에서 파생)"}
(H / "outputs/v4_tests.json").write_text(json.dumps(T, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

# ---------------- v3 대비 ----------------
diff = []
for c, (eps, hyps, docs, tests, ts) in spec().items():
    v3 = R3.Case(c)
    for h, conf in hyps:
        v3.add_hypothesis(h)
    for d, _ in docs:
        v3.add_document(d)
    for t in ts:
        s3 = v3.state(t)
        r4 = G.evaluate(build(c), t)
        m4 = {(h["episode_id"], h["hyp_id"], i["source_record_id"], i["surface"]): i for h in r4["hypotheses"] for i in h["items"]}
        usable = {h["hyp_id"]: h["usable"] for h in r4["hypotheses"]}
        hid = {(h.episode_id, h.label): h.hyp_id for h, _ in hyps}
        for r in s3["results"]:
            if r["link_status"] != "LINKED" and not r["gaps"]:
                continue
            hk = hid.get((r["episode_id"], r["hypothesis"]))
            i4 = m4.get((r["episode_id"], hk, r["document"], r["surface"]))
            v4d = i4["direction"] if i4 else None
            if v4d == r["direction"]:
                continue
            if not usable.get(hk, True):
                why = "WD_POLICY: 의사 미확인 가설은 v4 에서 평가 안 함"
            elif i4 is None:
                why = "EPISODE_LINK_POLICY: 기록이 이 가설의 에피소드에 연결되지 않음(다른 에피소드 또는 UNRESOLVED)"
            elif i4.get("stage") in ("EXCLUSION_GATE_UNRESOLVED", "TRUE_PATH_DEPENDS_ON_CONFLICT", "DIRECTIONAL_PATH_CONFLICT", "FALLBACK_CONFLICT"):
                why = f"CONDITION_POLICY: {i4['stage']}"
            elif r["direction"] in LG.DIRECTIONAL or (v4d in LG.DIRECTIONAL):
                why = "DIRECTION_CHANGE: 조사 필요"
            else:
                why = f"NON_DIRECTIONAL_LABEL: v3 {r['direction']}({r['abstain_reason']}) → v4 {v4d}({i4.get('stage') or i4['hold_reason']})"
            diff.append({"case": c, "as_of": t, "episode": r["episode_id"], "doc": r["document"], "surface": r["surface"], "relation": r["relation_id"] or (i4 or {}).get("relation_id"),
                         "v3": r["direction"], "v4": v4d, "why": why})
(H / "outputs/v4_v3_diff.json").write_text(json.dumps({"n_diff": len(diff), "by_reason": dict(Counter(d["why"].split(":")[0] for d in diff)), "rows": diff}, ensure_ascii=False, indent=1), encoding="utf-8")

for c, v in cases.items():
    for st in v["states"]:
        for h in st["graph"]["hypotheses"]:
            print(f"== {c}@{st['as_of']} {h['hyp_id']} {h['episode_id']} usable={h['usable']} ctx={ {k: (x['status'], x['value'] if x['status'] != 'CONFLICT' else x['values']) for k, x in h['context'].items() if x['status'] != 'NOT_FOUND'} }")
            for i in h["items"]:
                if i["direction"] != "ABSTAIN" or i["concept_id"].startswith(("PE", "DDIMER", "DVT", "PERF")):
                    print(f"    {i['source_record_id']} '{i['surface']}' {i['assertion_status']} → {i['direction']} {i['relation_id']} {i.get('stage', i['hold_reason'])} miss={[g['item'] + ':' + g['class'] for g in i['gaps']]} fs={i['finding_status']} dup={i['duplicate_of']}")
            if h["unresolved_episode_evidence"]:
                print("    UNRESOLVED:", h["unresolved_episode_evidence"])
print(json.dumps({k: v for k, v in T.items() if k not in ("D_graph_vs_flat",)}, ensure_ascii=False, default=str)[:3500])
print({k: T["D_graph_vs_flat"][k] for k in ("items", "direction_agree", "all_keys_equal", "all_decision_traces_equal")})
print(json.dumps(json.loads((H / "outputs/v4_v3_diff.json").read_text(encoding="utf-8")), ensure_ascii=False)[:2500])
