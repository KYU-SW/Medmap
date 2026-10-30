"""38회차 판별 근거 산출물: 관계표·집계·공통 소견·가상 사례 실행 보고. 성능 평가 아님(가상 사례만).
실행: ~/ai_env/bin/python -B kb38_report.py --out outputs/discriminators_<시각>
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from ddxplus_adapter import build_mapping, case_records, mapping_summary
from graph_engine import EvidenceRecord, PatientRecord, ReasoningSession, Status, assess_working_dx, infer
from knowledge_real_kg import build_real_graph, disease_node_id
from report_ko import render_ko

DIS = {disease_node_id(x): k for x, k in (("Pulmonary embolism", "폐색전증"), ("Pericarditis", "심낭염"),
                                          ("Myocarditis", "심근염"), ("Tuberculosis", "결핵"))}


def virtual(g, m):
    """가상 사례(구조 시험용, 실제 환자 아님). (제목, 기록 목록, 2단계 추가 기록, WD)"""
    def ddx(evs, pid):
        c = {"EVIDENCES": str(evs), "INITIAL_EVIDENCE": evs[0]}
        return case_records(pid, c, m, sorted({t.split("_@_")[0] for t in evs}), 1.0)

    def test(node, st, eid):
        return EvidenceRecord(node, Status(st), f"V-{eid}", 2.0, 2.0, "test", evidence_id=eid)
    return [
        ("V1 흉통+앞으로 숙이면 완화, 현재 진단 심근염 → 검사 결과(마찰음·ST 상승) 추가",
         ddx(["E_53", "E_55_@_V_29", "E_33", "E_66"], "V1"), [test("HP:0034788", "POSITIVE", "V1rub"), test("HP:0012251", "POSITIVE", "V1st")],
         disease_node_id("Myocarditis")),
        ("V2 흉통, 진찰·심전도·초음파 모두 음성 기록(마찰음 음성은 정보 없음), 현재 진단 심낭염",
         ddx(["E_53", "E_55_@_V_29"], "V2"), [test("HP:0034788", "NEGATIVE", "V2rub"), test("HP:0012251", "NEGATIVE", "V2st"),
                                              test("HP:0031594", "NEGATIVE", "V2pr"), test("HP:0001698", "NEGATIVE", "V2eff")],
         disease_node_id("Pericarditis")),
        ("V3 흉통·호흡곤란, 현재 진단 심근염 → 심장 MRI T2 만 양성 → T1 도 양성",
         ddx(["E_53", "E_55_@_V_29", "E_66"], "V3"), [test("CONCEPT:cmr_t2_marker", "POSITIVE", "V3t2")], disease_node_id("Myocarditis")),
        ("V4 HIV 감염 + 발열·기침, 현재 진단 폐색전증 → HIV 음성으로 정정",
         ddx(["E_2", "E_91", "E_201"], "V4"), [], disease_node_id("Pulmonary embolism")),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=False)
    m = build_mapping()
    g, meta = build_real_graph(sorted({h for v in m.values() if v["used"] for h in v["hp_ids"]}), discriminators=True)
    R = meta["discriminators"]
    with open(out / "discriminator_relations.csv", "w", newline="", encoding="utf-8") as fh:
        cols = ["id", "disease", "relation_type", "op", "leaves", "gate", "condition", "source", "evidence_class",
                "quote_check", "limitation", "ddx", "status"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in R:
            w.writerow({c: (";".join(r[c]) if isinstance(r.get(c), list) else r.get(c, "")) for c in cols})
    obs_nodes = {h for v in m.values() if v["used"] for h in v["hp_ids"]}
    per = {}
    for r in R:
        leaves = [n for n in r["leaves"] + r.get("gate", []) if not n.startswith("(")]
        observable = [n for n in leaves if n in obs_nodes]
        x = per.setdefault(DIS[r["disease"]], {"relations": 0, "applied": 0, "by_type": {}, "observable_any_leaf": 0,
                                               "observable_all_leaves": 0, "needs_test_or_exam": 0})
        x["relations"] += 1
        x["applied"] += r["status"] == "APPLIED"
        x["by_type"][r["relation_type"]] = x["by_type"].get(r["relation_type"], 0) + 1
        x["observable_any_leaf"] += bool(observable)
        x["observable_all_leaves"] += bool(leaves) and len(observable) == len(leaves)
        x["needs_test_or_exam"] += "미검사" in r["ddx"]
    # 공통 소견(A): DisMech SUGGESTS 로 3질환 이상과 연결된 HP 소견
    common = {}
    for n, node in g.nodes.items():
        ds = {e.dst for e in g.out_edges(n, "SUGGESTS") if e.spec_dict().get("evidence_class", "").startswith("DISMECH")}
        if len(ds) >= 3:
            common[n] = {"label": node.label, "diseases": sorted(DIS[d] for d in ds), "ddx_observable": n in obs_nodes}
    summary = {"per_disease": per, "relations_total": len(R), "applied": sum(r["status"] == "APPLIED" for r in R),
               "not_applied": [r["id"] for r in R if r["status"] != "APPLIED"], "common_findings_dismech_ge3": common,
               "mapping_summary": mapping_summary(m), "graph_counts": meta["counts"],
               "ddx_codes_feeding_new_nodes": sorted(k for k, v in m.items() if v["used"] and set(v["hp_ids"]) &
                                                     {"CONCEPT:chest_pain_relieved_sitting_forward", "CONCEPT:hiv_infection"})}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# EXP-01b 38회차 판별 근거 — 가상 사례 실행(구조 시험, 실제 환자·성능 아님)", "",
          "> 관계표 = discriminator_relations.csv · 집계 = summary.json. 진료지침 원문은 로컬에 없어 DisMech·캐시 초록/본문만 사용.", ""]
    for title, recs, more, wd in virtual(g, m):
        pr = PatientRecord(title.split()[0])
        for r in recs:
            pr.add(r)
        s = ReasoningSession(g, pr, 1.0)
        a1 = assess_working_dx(g, s.current, pr, wd)
        md += [f"# {title}", "", render_ko(g, s.current, a1, title="1단계", compact=True, rank_key="graded"), ""]
        if more:
            inf2, trans, aff = s.update(more, 2.0)
            md += [render_ko(g, inf2, assess_working_dx(g, inf2, pr, wd), trans, title="2단계(검사 결과 추가)", compact=True,
                             rank_key="graded"), ""]
        if title.startswith("V3"):
            inf3, trans3, _ = s.update([EvidenceRecord("CONCEPT:cmr_t1_marker", Status.POSITIVE, "V-V3t1", 3.0, 3.0, "test",
                                                       evidence_id="V3t1")], 3.0)
            md += [render_ko(g, inf3, assess_working_dx(g, inf3, pr, wd), trans3, title="3단계(T1 지표 추가)", compact=True,
                             rank_key="graded"), ""]
        if title.startswith("V4"):
            old = next(r for r in pr.history("CONCEPT:hiv_infection"))
            inf3, trans3, _ = s.update([EvidenceRecord("CONCEPT:hiv_infection", Status.NEGATIVE, "V4-chart", 2.0, 2.0, "chart_review",
                                                       evidence_id="V4-hivneg", supersedes=old.evidence_id)], 2.0)
            md += [render_ko(g, inf3, assess_working_dx(g, inf3, pr, wd), trans3, title="2단계(HIV 음성으로 정정)", compact=True,
                             rank_key="graded"), ""]
    (out / "virtual_cases_ko.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("per_disease", "relations_total", "applied", "not_applied",
                                              "ddx_codes_feeding_new_nodes")}, ensure_ascii=False, indent=1))
    print("common:", {k: (v["label"], v["diseases"], v["ddx_observable"]) for k, v in common.items()})


if __name__ == "__main__":
    main()
