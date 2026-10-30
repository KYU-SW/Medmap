"""DEV 사례 수정 전/후 비교. 각 버전 모듈 폴더를 별도 프로세스로 불러 같은 사례·같은 가상 WD 로 계산한다(성능 평가 아님).
실행: ~/ai_env/bin/python -B compare_runs.py --before <이전 모듈 폴더> --cases <dev_cases.json> --out <출력 폴더>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WD_ORDER = ("Pericarditis", "Pulmonary embolism", "Myocarditis", "Tuberculosis")   # demo_real 과 같은 회전

WORKER = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from ddxplus_adapter import build_mapping, patient_from_case
from graph_engine import ReasoningSession, assess_working_dx
from knowledge_real_kg import build_real_graph, disease_node_id
m = build_mapping()
g, meta = build_real_graph(sorted({h for v in m.values() if v["used"] for h in v["hp_ids"]}))
cases = json.load(open(sys.argv[2]))["cases"]
order = json.loads(sys.argv[3])
out = {"mapping": {k: {"status": v["status"], "hp_ids": v["hp_ids"] if v["used"] else [], "used": v["used"]} for k, v in m.items()},
       "edges": len(meta["edges"]), "counts": meta["counts"], "cases": []}
for i, c in enumerate(cases):
    wd = disease_node_id(order[i % 4])
    pr, p1, new = patient_from_case(f"DEV{i+1}", c, m, wd)
    s = ReasoningSession(g, pr, 1.0)
    inf, trans, aff = s.update(new, 2.0)
    a = assess_working_dx(g, inf, pr, wd)
    view = pr.view(2.0)
    def row(x):
        return {"disease": x.disease, "n_support": x.n_support,
                "n_clinical": getattr(x, "n_clinical", None), "n_cooc_only": getattr(x, "n_cooccurrence_only", None),
                "groups": [sorted(gr) for gr in x.support_groups], "grades": list(getattr(x, "group_grades", ()))}
    rk = inf.ranking("graded") if "key" in inf.ranking.__code__.co_varnames else inf.ranking()
    out["cases"].append({
        "pid": f"DEV{i+1}-row{c['row_index']}", "wd": wd,
        "codes": sorted(set(json.loads(c["EVIDENCES"].replace("'", '"')) and
                            [t.split("_@_")[0] for t in json.loads(c["EVIDENCES"].replace("'", '"'))])),
        "in_graph_positive": sorted(inf.positive_in_graph),
        "in_graph_negative": sorted(n for n, o in view.items() if n in g.nodes and o.status.value == "NEGATIVE"),
        "out_of_graph": sorted(inf.positive_out_of_graph),
        "ranking": [row(x) for x in rk],
        "unexplained": [[n, cl] for n, cl, *_ in a.unexplained],
        "undetermined": len(a.undetermined),
        "review": [[d, list(r)] for d, r in a.review_candidates],
        "conflict_knowledge": a.conflict_knowledge, "transitions": len(trans), "recomputed": len(aff)})
print(json.dumps(out, ensure_ascii=False))
'''


def run(moddir: Path, cases: Path) -> dict:
    r = subprocess.run([sys.executable, "-B", "-c", WORKER, str(moddir), str(cases), json.dumps(WD_ORDER)],
                       capture_output=True, text=True, timeout=300, cwd=moddir,
                       env={**__import__("os").environ, "EXP01B_MAIN_AI": str(HERE.parent / "main_ai")})
    if r.returncode:
        raise SystemExit(r.stderr[-3000:])
    return json.loads(r.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    b, n = run(Path(a.before), Path(a.cases)), run(HERE, Path(a.cases))
    changed = {k: {"before": b["mapping"][k], "after": n["mapping"][k]} for k in n["mapping"]
               if (b["mapping"][k]["status"], b["mapping"][k]["hp_ids"]) != (n["mapping"][k]["status"], n["mapping"][k]["hp_ids"])}
    L = ["# EXP-01b 35회차 수정 전/후 비교(DEV1–8, TRAIN16 합성 환자, 성능 평가 아님)", "",
         f"- 이전 모듈: `{a.before}` · 이후 모듈: `{HERE}` · 사례: `{a.cases}` · 가상 WD 회전 {list(WD_ORDER)}",
         f"- 간선 수 {b['edges']} → {n['edges']} · 노드 {b['counts']['nodes_by_kind']} → {n['counts']['nodes_by_kind']}",
         f"- 매핑이 바뀐 DDXPlus 근거 {len(changed)}개(아래 사례에 등장한 것만 사례별 표시)", ""]
    for cb, cn in zip(b["cases"], n["cases"]):
        codes = [c for c in cn["codes"] if c in changed]
        L += [f"## {cn['pid']} — WD {cn['wd']}",
              f"- 그래프에 연결된 양성 근거 {len(cb['in_graph_positive'])} → {len(cn['in_graph_positive'])} "
              f"(빠짐 {sorted(set(cb['in_graph_positive']) - set(cn['in_graph_positive']))}, "
              f"추가 {sorted(set(cn['in_graph_positive']) - set(cb['in_graph_positive']))}) · 그래프 내 음성 {cn['in_graph_negative']}",
              "- 이 사례의 매핑 변경: " + ("; ".join(f"{c} {changed[c]['before']['status']}{changed[c]['before']['hp_ids']}"
                                              f"→{changed[c]['after']['status']}{changed[c]['after']['hp_ids']}" for c in codes) or "없음"),
              "- 순위(이전 = 묶음 수 기준 · 이후 = 임상 소견 묶음 → 전체 묶음):",
              "  - 이전: " + " > ".join(f"{x['disease'][3:]}({x['n_support']})" for x in cb["ranking"]),
              "  - 이후: " + " > ".join(f"{x['disease'][3:]}({x['n_support']}, 임상 {x['n_clinical']}, 공출현만 {x['n_cooc_only']})"
                                       for x in cn["ranking"]),
              "  - 이후 묶음: " + " | ".join(f"{x['disease'][3:]}: " + ", ".join(
                  "{" + ",".join(gr) + "}:" + gd for gr, gd in zip(x["groups"], x["grades"])) for x in cn["ranking"]),
              f"- 설명 부족: {cb['unexplained']} → {cn['unexplained']}",
              f"- 판단 불가 근거 수: {cb['undetermined']} → {cn['undetermined']} · 충돌 지식: {cb['conflict_knowledge']} → {cn['conflict_knowledge']}",
              f"- 추가 검토 후보: {[d for d, _ in cb['review']]} → {[d for d, _ in cn['review']]}",
              f"- 2단계 재계산 질환 {cb['recomputed']} → {cn['recomputed']}, 바뀐 경로 {cb['transitions']} → {cn['transitions']}", ""]
    L += ["## 매핑 변경 전체", "| 근거 | 이전 | 이후 |", "|---|---|---|"] + \
         [f"| {k} | {v['before']['status']} {v['before']['hp_ids']} | {v['after']['status']} {v['after']['hp_ids']} |"
          for k, v in sorted(changed.items(), key=lambda kv: int(kv[0][2:]))]
    (out / "compare_report_ko.md").write_text("\n".join(L), encoding="utf-8")
    (out / "compare.json").write_text(json.dumps({"before": b, "after": n, "mapping_changed": changed},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
