"""실제 의료 지식 그래프(HSDN+DisMech+HPO) × DDXPlus TRAIN16 개발 사례 시연. 성능 평가 아님.

흐름(사례마다): 1단계(첫 증상 + 병력) 입력 → 그래프 탐색·조건 판정·다중 경로 통합·중복 제거 → 현재 의사 진단 비교
→ 2단계(나머지 증상 답변) 입력 → 영향 질환만 재계산 → 전후 변화·경로·출처 출력.
현재 의사 진단(WD)은 시연용 가상 입력: 사례 순서 i 에 대해 WD_ROTATION[i % 4](정답 라벨과 무관하게 사전 고정).
실행: ~/ai_env/bin/python -B demo_real.py --cases outputs/dev_cases_<시각>/dev_cases.json [--out outputs/real_demo_<시각>]
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from ddxplus_adapter import build_mapping, mapping_summary, patient_from_case
from graph_engine import ReasoningSession, assess_working_dx
from knowledge_real_kg import build_real_graph, disease_node_id
from report_ko import render_ko, to_json

HERE = Path(__file__).resolve().parent
WD_ROTATION = [disease_node_id(x) for x in ("Pericarditis", "Pulmonary embolism", "Myocarditis", "Tuberculosis")]


def build():
    m = build_mapping()
    extra = sorted({h for v in m.values() if v["used"] for h in v["hp_ids"]})
    g, meta = build_real_graph(extra_hp_nodes=extra)
    return m, g, meta


def run_case(g, m, i, case):
    pid = f"DEV{i + 1}-row{case['row_index']}"
    wd = WD_ROTATION[i % len(WD_ROTATION)]
    pr, p1, new = patient_from_case(pid, case, m, wd)
    sess = ReasoningSession(g, pr, 1.0)
    inf1 = sess.current
    wd1 = assess_working_dx(g, inf1, pr, wd)
    inf2, trans, aff = sess.update(new, 2.0)
    wd2 = assess_working_dx(g, inf2, pr, wd)
    return pid, wd, pr, p1, new, (inf1, wd1), (inf2, wd2, trans), aff


def input_lines(g, m, case, pr, p1, new):
    def code_line(c):
        mm = m.get(c, {})
        return f"{c}[{mm.get('status')}] {mm.get('question', '')[:70]}"
    toks = case["EVIDENCES"]
    L = [f"- 나이 {pr.age} · 성별 {pr.sex} · 첫 증상 {case['INITIAL_EVIDENCE']} · (참고 전용, 엔진 입력 아님) DDXPlus 라벨 = {case['PATHOLOGY_REFERENCE_ONLY']}",
         f"- 1단계 입력 DDXPlus 코드 {len(p1)}: " + "; ".join(code_line(c) for c in p1),
         f"- 2단계 추가 답변 레코드 {len(new)}: " + "; ".join(sorted({r.provenance.split(':')[0].replace('DDXPlus ', '') for r in new})),
         f"- 원본 EVIDENCES 토큰 수 {len(json.loads(toks.replace(chr(39), chr(34))))} — 기록에 없는 근거는 미기록(음성 변환 없음)"]
    nodes = sorted({r.node_id for r in pr.all_records()} | {r.node_id for r in new})
    ing = [n for n in nodes if n in g.nodes]
    L.append(f"- 연결된 실제 지식 노드 {len(ing)}: " + ", ".join(f"{g.nodes[n].label}[{n}]" for n in ing))
    L.append(f"- 그래프 밖(연결 개념 없음·검토 필요·미조사) {len(nodes) - len(ing)}: " + ", ".join(n for n in nodes if n not in g.nodes))
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--out", default=str(HERE / "outputs" / time.strftime("real_demo_%Y%m%d_%H%M%S")))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    m, g, meta = build()
    cases = json.loads(Path(a.cases).read_text(encoding="utf-8"))
    ms = mapping_summary(m)
    md = ["# EXP-01b 실제 지식 그래프 × DDXPlus 개발 사례 시연", "",
          "> 실제 지식 = HSDN(문헌 공출현) + DisMech(AI 큐레이션, PMID 근거 표시) + HPO 계층. 환자 = DDXPlus TRAIN16(합성 환자, EXP-01 HOLDOUT 제외).",
          "> 진단 확정·성능 주장 없음. 현재 의사 진단은 시연용 가상 입력. 반박·AND/OR 진단 규칙은 실제 출처가 없어 그래프에 없음.", "",
          "## 지식 그래프", "```json", json.dumps({"counts": meta["counts"], "sources": meta["sources"],
                                                 "diseases": meta["diseases"],
                                                 "excluded_annotations": meta["excluded_annotations"],
                                                 "excluded_self_concept": meta["excluded_self_concept"],
                                                 "relation_roles_absent": meta["relation_roles_absent"],
                                                 "hpoa_rows_for_selected": meta["hpoa_rows_for_selected"]},
                                                ensure_ascii=False, indent=1), "```", "",
          "## DDXPlus 223 근거 매핑 요약", "```json", json.dumps(ms, ensure_ascii=False), "```",
          f"- 개발 사례 메타: {json.dumps(cases['meta'], ensure_ascii=False)}", ""]
    res = {"mapping_summary": ms, "cases": []}
    for i, case in enumerate(cases["cases"]):
        pid, wd, pr, p1, new, (inf1, wd1), (inf2, wd2, trans), aff = run_case(g, m, i, case)
        md += [f"# 사례 {i + 1}: {pid} — 현재 의사 진단(가상) {g.nodes[wd].label}", ""] + input_lines(g, m, case, pr, p1, new) + [""]
        md.append(render_ko(g, inf1, wd1, title=f"사례 {i + 1} — 1단계(첫 증상+병력) 후", compact=True, rank_key="graded"))
        md += ["", f"- 2단계 입력 후 그래프 순회로 재계산한 질환: {sorted(aff)}", ""]
        md.append(render_ko(g, inf2, wd2, trans, title=f"사례 {i + 1} — 2단계(추가 답변) 후", compact=True, rank_key="graded"))
        md.append("")
        res["cases"].append({"pid": pid, "row_index": case["row_index"], "working_dx": wd,
                             "pathology_reference_only": case["PATHOLOGY_REFERENCE_ONLY"],
                             "step1": to_json(inf1, wd1, rank_key="graded"), "step2": to_json(inf2, wd2, trans, rank_key="graded"), "recomputed": sorted(aff)})
    (out / "real_demo_report_ko.md").write_text("\n".join(md), encoding="utf-8")
    (out / "real_demo_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "kg_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out / "ddxplus_evidence_mapping.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["evidence", "is_antecedent", "data_type", "status", "used_in_inference", "negative_answer_usable", "value_rule", "hp_ids", "candidate_hp_ids", "reason", "question"])
        for k in sorted(m, key=lambda x: int(x[2:])):
            v = m[k]
            w.writerow([k, v["is_antecedent"], v["data_type"], v["status"], v["used"], v["negative_ok"], v["value_rule"], ";".join(v["hp_ids"]), ";".join(v.get("candidate_hp_ids", [])), v["reason"], v["question"]])
    with open(out / "disease_link_audit.csv", "w", newline="", encoding="utf-8") as fh:
        rows = meta["disease_link_audit"]
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(out)


if __name__ == "__main__":
    main()
