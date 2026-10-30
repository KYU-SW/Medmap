"""explore1 사후 분석(POST-HOC — protocol.json 고정 후, 결과를 본 뒤 추가한 분석. 판정·조정에 쓰지 않음).
1) 크기 맞춘 무작위 기준선: 조건 B 추가 검토 목록 크기 s(정답 제외 3질환 중) → 무작위면 정답 포함 확률 = s/3,
   순위 top-k 는 4질환 중 무작위 순서면 k/4.
2) 1위 쏠림: 환자별(조건 무관) 정렬 1위가 유일한지·동점인지, 유일 1위 질환 분포(정답별).
3) PE 누락 사례의 보조 원인: 매핑 미사용(REVIEW 등) 코드 중 PE 관련 HPO 후보를 가진 것.
실행: ~/ai_env/bin/python -B explore1_posthoc.py --dir outputs/explore1_<시각>
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path

from ddxplus_adapter import build_mapping, patient_from_case
from explore1 import VARIANTS, make_graph
from graph_engine import infer
from knowledge_real_kg import disease_node_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    d = Path(ap.parse_args().dir)
    rows = list(csv.DictReader(open(d / "rows.csv", encoding="utf-8")))
    cases = json.loads((d / "cases.json").read_text(encoding="utf-8"))
    m = build_mapping()
    out = {"type": "POST_HOC(결과 확인 후 추가)", "baseline": {}, "top1": {}}
    for v in VARIANTS:
        B = [r for r in rows if r["variant"] == v and r["cond"] == "B"]
        sizes = [len(r["review"].split(";")) if r["review"] else 0 for r in B]
        out["baseline"][v] = {
            "review_size_mean": round(sum(sizes) / len(sizes), 4),
            "review_size_dist": dict(collections.Counter(sizes)),
            "observed_truth_in_review": sum(r["truth_in_review"] == "True" for r in B) / len(B),
            "size_matched_random_expected": round(sum(s / 3 for s in sizes) / len(sizes), 4),
            "random_top1": 0.25, "random_top3": 0.75}
        g = make_graph(m, VARIANTS[v])
        dist = collections.Counter()
        for c in cases:
            pr, _, new = patient_from_case(f"X{c['row_index']}", c, m, None)
            for r in new:
                pr.add(r)
            inf = infer(g, pr, 2.0)
            keys = {x: (-y.n_clinical, -y.n_support) for x, y in inf.diseases.items()}
            best = min(keys.values())
            tops = sorted(x[3:] for x, k in keys.items() if k == best)
            dist[(c["PATHOLOGY_EVAL_ONLY"], "UNIQUE:" + tops[0] if len(tops) == 1 else f"TIE{len(tops)}:" + "+".join(tops))] += 1
        out["top1"][v] = {f"{t}|{k}": n for (t, k), n in sorted(dist.items())}
    pe = json.loads((d / "pe_miss.json").read_text(encoding="utf-8"))
    out["pe_miss_contributing_mapping"] = dict(collections.Counter(c for r in pe for c in r["lost_by_mapping_codes"]))
    out["pe_miss_with_mapping_loss"] = sum(bool(r["lost_by_mapping_codes"]) for r in pe)
    out["pe_miss_n"] = len(pe)
    (d / "posthoc.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
