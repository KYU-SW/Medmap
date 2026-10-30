"""EXP-01b 판별력 개선 1차 평가(EXPLORATORY — 임상 성능 아님, RG 사전등록 없음: 사용자 지시).

새 사례(이전 explore1 100명·개발 8명 제외) 100명 = 4질환 × 25, sha256("EXP01B_EXPLORE2|"+row) 앞 25.
조건 A: WD = 정답 / B: WD = OTHERS[정답][k % 3](explore1 과 같은 규칙). 정답은 평가만.
세 팔(같은 사례·같은 입력):
  OLD_GRADED : explore1 시점 모듈(~/medmap-worktrees/main-ai/archive/exp01b_explore1_modules, 별도 프로세스) + graded 정렬
  NEW_GRADED : 37회차 매핑 + graded 정렬(−임상 묶음, −전체 묶음)         → OLD 대비 = 매핑 효과
  NEW_SPEC   : 37회차 매핑 + spec 정렬(discrimination.spec_key)           → NEW_GRADED 대비 = 정렬 효과
순위: 같은 정렬 키 동점은 비관적(정답 뒤로)·낙관적 둘 다. 무작위 기준: top1 25%·top3 75%·WD 제외 1위 33.3%.
지표는 protocol.json(METRICS)에 고정. 결과를 보고 점수식·매핑을 바꾸거나 재평가하지 않는다.
실행: ~/ai_env/bin/python -B explore2.py select --out outputs/explore2_<시각>
      ~/ai_env/bin/python -B explore2.py run --dir outputs/explore2_<시각>
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OLD_DIR = HERE.parents[1] / "archive" / "exp01b_explore1_modules"
DEV = HERE / "outputs/dev_cases_20261029_1456/dev_cases.json"
EX1 = HERE / "outputs/explore1_20261029_2232/cases.json"
DISEASES = ["Pulmonary embolism", "Pericarditis", "Myocarditis", "Tuberculosis"]
OTHERS = {d: [x for x in DISEASES if x != d] for d in DISEASES}
N_PER = 25
NEW_CODE = ["graph_engine.py", "knowledge_real_kg.py", "ddxplus_adapter.py", "discrimination.py", "report_ko.py", "explore2.py"]
METRICS = {
    "top1/top3": "정답 질환 순위(4질환 중) ≤ 1 / ≤ 3, 비관적·낙관적 동점",
    "alt_first": "조건 B: WD 를 뺀 3질환 중 정답이 1위(비관적·낙관적) — 정렬 기반 대안 후보",
    "review_incl": "조건 B: 정답 ∈ 엔진 추가 검토 후보(review_candidates, 정렬과 무관한 규칙) + 크기 맞춘 무작위 기대(s/3)",
    "pe_miss": "정답 PE·조건 B: (a) 비관적 top3 밖 (b) WD 제외 1위 아님(비관적) (c) 추가 검토 후보에 없음",
    "tie_rate": "환자별 최고 정렬 키를 2개 이상 질환이 공유하는 비율",
    "concentration": "환자별 단독 1위 질환 분포 · 최대 점유율(100명 중)",
    "linked": "그래프 HP 기록을 만든 코드 수(사용 코드)·그래프 내 양성 근거 수 평균",
    "gap": "WD 비교에서 C(관계 없음 + 하위 개념만) 근거 수 평균(조건 A·B)",
    "A_warn": "조건 A: 재검토 신호(B 다른 질환만 연결 ≥1 또는 검증 반박 ≥1) 비율 · 지식 부족 표시(C ≥1) 비율 · 이전 정의 '설명 부족 ≥1' 비율",
    "kb_richness": "질환별 DisMech·HSDN SUGGESTS 간선 수와 단독 1위 횟수(지식원 풍부 질환 유리 여부 확인)",
}

WORKER = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from ddxplus_adapter import build_mapping, patient_from_case, parse_tokens
from graph_engine import assess_working_dx, infer
from knowledge_real_kg import build_real_graph, disease_node_id
spec = None
try:
    from discrimination import spec_scores, wd_categories
    spec = True
except ImportError:
    pass
m = build_mapping()
g, meta = build_real_graph(sorted({h for v in m.values() if v["used"] for h in v["hp_ids"]}))
cases = json.load(open(sys.argv[2]))
out = []
for c in cases:
    for cond in ("A", "B"):
        wd = disease_node_id(c["wd_" + cond])
        pr, _, new = patient_from_case("X%d" % c["row_index"], c, m, wd)
        for r in new:
            pr.add(r)
        inf = infer(g, pr, 2.0)
        a = assess_working_dx(g, inf, pr, wd)
        cls = [x[1] for x in a.unexplained]
        recs = pr.all_records()
        used = sorted({r.source_id.split("-", 1)[1] for r in recs if r.node_id in g.nodes})
        sc = spec_scores(g, inf) if spec else None
        out.append({"row_index": c["row_index"], "cond": cond, "wd": c["wd_" + cond], "truth": c["PATHOLOGY_EVAL_ONLY"],
                    "n_input_codes": len(parse_tokens(c["EVIDENCES"])), "n_used_codes": len(used),
                    "n_pos_in_graph": len(inf.positive_in_graph),
                    "dis": {d[3:]: {"n_clin": x.n_clinical, "n_sup": x.n_support,
                                    "S_clin": sc[d]["S_clin"] if sc else None, "S_all": sc[d]["S_all"] if sc else None}
                            for d, x in inf.diseases.items()},
                    "review": [x[0][3:] for x in a.review_candidates],
                    "B": cls.count("EXPLAINED_BY_OTHER"), "C": cls.count("UNEXPLAINED_IN_GRAPH") + cls.count("NARROWER_CONCEPT_LINKED"),
                    "D": len(a.conflicting), "n_unexplained": len(cls), "wd_groups": inf.diseases[wd].n_support})
print(json.dumps({"rows": out, "counts": meta["counts"],
                  "kb": {d[3:]: {"dismech": sum(1 for e in g.in_edges(d, "SUGGESTS") if e.spec_dict().get("evidence_class", "").startswith("DISMECH")),
                                 "hsdn": sum(1 for e in g.in_edges(d, "SUGGESTS") if e.spec_dict().get("evidence_class", "").startswith("HSDN"))}
                         for d in g.diseases()}}, ensure_ascii=False))
'''


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def code_shas() -> dict:
    d = {f: sha(HERE / f) for f in NEW_CODE}
    d.update({f"OLD/{p.name}": sha(p) for p in sorted(OLD_DIR.glob("*.py"))})
    return d


def cmd_select(out: Path):
    sys.path.insert(0, str(HERE))
    from extract_dev_cases import TRAIN, is_holdout, split_key
    out.mkdir(parents=True, exist_ok=False)
    used = {c["row_index"] for c in json.loads(DEV.read_text(encoding="utf-8"))["cases"]} | \
           {c["row_index"] for c in json.loads(EX1.read_text(encoding="utf-8"))}
    cand, n, hold = {d: [] for d in DISEASES}, 0, 0
    for ch in pd.read_csv(TRAIN, usecols=["AGE", "SEX", "PATHOLOGY", "EVIDENCES", "INITIAL_EVIDENCE"], chunksize=200_000):
        for i, (age, sex, pat, evs, ini) in enumerate(zip(ch.AGE, ch.SEX, ch.PATHOLOGY, ch.EVIDENCES, ch.INITIAL_EVIDENCE)):
            ri = n + i
            k = split_key(ri, age, sex, pat, evs)
            h = is_holdout(k)
            hold += h
            if not h and pat in cand and ri not in used:
                cand[pat].append({"row_index": ri, "split_key": k, "AGE": int(age), "SEX": sex, "PATHOLOGY_EVAL_ONLY": pat,
                                  "EVIDENCES": evs, "INITIAL_EVIDENCE": ini,
                                  "order": hashlib.sha256(f"EXP01B_EXPLORE2|{ri}".encode()).hexdigest()})
        n += len(ch)
    if (n, hold) != (1_025_602, 204_663):
        raise SystemExit("split mismatch")
    cases = []
    for d in DISEASES:
        for k, c in enumerate(sorted(cand[d], key=lambda r: r["order"])[:N_PER]):
            cases.append({**c, "k": k, "wd_A": d, "wd_B": OTHERS[d][k % 3]})
    proto = {"created": time.strftime("%Y-%m-%d %H:%M:%S"), "type": "EXPLORATORY", "code_sha256": code_shas(),
             "arms": ["OLD_GRADED", "NEW_GRADED", "NEW_SPEC"], "metrics": METRICS,
             "excluded_rows": len(used), "candidates": {d: len(v) for d, v in cand.items()},
             "spec_formula": "discrimination.py 머리 주석", "doc": __doc__}
    (out / "protocol.json").write_text(json.dumps(proto, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"cases": len(cases), "excluded": len(used), "candidates": proto["candidates"]}, ensure_ascii=False))


def run_worker(moddir: Path, cases: Path) -> dict:
    env = {**os.environ, "EXP01B_MAIN_AI": str(HERE.parent / "main_ai")}
    r = subprocess.run([sys.executable, "-B", "-c", WORKER, str(moddir), str(cases)], capture_output=True, text=True,
                       timeout=600, cwd=moddir, env=env)
    if r.returncode:
        raise SystemExit(r.stderr[-3000:])
    return json.loads(r.stdout)


def key(arm, x):
    return (-x["S_clin"], -x["S_all"]) if arm == "NEW_SPEC" else (-x["n_clin"], -x["n_sup"])


def rank(arm, dis, target, among=None):
    names = among or list(dis)
    me = key(arm, dis[target])
    others = [key(arm, dis[n]) for n in names if n != target]
    better = sum(o < me for o in others)
    tie = sum(o == me for o in others)
    return better + tie + 1, better + 1


def rate(xs):
    xs = list(xs)
    return {"k": sum(bool(x) for x in xs), "n": len(xs), "rate": round(sum(bool(x) for x in xs) / len(xs), 4) if xs else None}


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def metrics(arm, rows):
    A = [r for r in rows if r["cond"] == "A"]
    B = [r for r in rows if r["cond"] == "B"]
    res = {}
    for scope in ["ALL"] + DISEASES:
        a = [r for r in A if scope == "ALL" or r["truth"] == scope]
        b = [r for r in B if scope == "ALL" or r["truth"] == scope]
        rk = [rank(arm, r["dis"], r["truth"]) for r in a]
        alt = [rank(arm, r["dis"], r["truth"], [x for x in r["dis"] if x != r["wd"]]) for r in b]
        tops, ties = collections.Counter(), 0
        for r in a:
            ks = {d: key(arm, x) for d, x in r["dis"].items()}
            best = min(ks.values())
            t = [d for d, k in ks.items() if k == best]
            ties += len(t) > 1
            tops["UNIQUE:" + t[0] if len(t) == 1 else f"TIE{len(t)}"] += 1
        sizes = [len(r["review"]) for r in b]
        res[scope] = {
            "n": len(a),
            "top1_pess": rate(p == 1 for p, _ in rk), "top1_opt": rate(o == 1 for _, o in rk),
            "top3_pess": rate(p <= 3 for p, _ in rk), "top3_opt": rate(o <= 3 for _, o in rk),
            "alt_first_pess": rate(p == 1 for p, _ in alt), "alt_first_opt": rate(o == 1 for _, o in alt),
            "review_incl": rate(r["truth"] in r["review"] for r in b),
            "review_size_mean": mean(sizes), "review_random_expected": mean(s / 3 for s in sizes),
            "tie_rate": rate([True] * ties + [False] * (len(a) - ties)),
            "top_distribution": dict(sorted(tops.items())),
            "max_unique_share": round(max([v for k, v in tops.items() if k.startswith("UNIQUE")] or [0]) / len(a), 4) if a else None,
            "used_codes_mean": mean(r["n_used_codes"] for r in a), "input_codes_mean": mean(r["n_input_codes"] for r in a),
            "pos_in_graph_mean": mean(r["n_pos_in_graph"] for r in a),
            "gap_C_mean_A": mean(r["C"] for r in a), "gap_C_mean_B": mean(r["C"] for r in b),
            "A_review_signal": rate(r["B"] > 0 or r["D"] > 0 for r in a), "A_gap_flag": rate(r["C"] > 0 for r in a),
            "A_old_any_unexplained": rate(r["n_unexplained"] > 0 for r in a),
            "B_review_signal": rate(r["B"] > 0 or r["D"] > 0 for r in b)}
        if scope == "Pulmonary embolism":
            res[scope]["pe_miss_top3_pess"] = sum(p > 3 for p, _ in [rank(arm, r["dis"], r["truth"]) for r in b])
            res[scope]["pe_miss_alt_first_pess"] = sum(p != 1 for p, _ in alt)
            res[scope]["pe_miss_review"] = sum(r["truth"] not in r["review"] for r in b)
    return res


def cmd_run(d: Path):
    proto = json.loads((d / "protocol.json").read_text(encoding="utf-8"))
    if proto["code_sha256"] != code_shas():
        raise SystemExit("코드가 protocol 고정 시점과 다름 — 실행 거부")
    cases = d / "cases.json"
    old, new = run_worker(OLD_DIR, cases), run_worker(HERE, cases)
    arms = {"OLD_GRADED": old["rows"], "NEW_GRADED": new["rows"], "NEW_SPEC": new["rows"]}
    S = {arm: metrics(arm, rows) for arm, rows in arms.items()}
    S["kb"] = {"OLD": old["kb"], "NEW": new["kb"]}
    S["graph_counts"] = {"OLD": old["counts"], "NEW": new["counts"]}
    with open(d / "rows.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["arm_source", "row_index", "cond", "truth", "wd", "n_input_codes", "n_used_codes", "n_pos_in_graph", "B", "C", "D",
                    "n_unexplained", "review", "dis_json"])
        for src, rows in (("OLD", old["rows"]), ("NEW", new["rows"])):
            for r in rows:
                w.writerow([src, r["row_index"], r["cond"], r["truth"], r["wd"], r["n_input_codes"], r["n_used_codes"],
                            r["n_pos_in_graph"], r["B"], r["C"], r["D"], r["n_unexplained"], ";".join(r["review"]),
                            json.dumps(r["dis"], ensure_ascii=False)])
    (d / "summary.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "report_ko.md").write_text(render(proto, S), encoding="utf-8")
    print(d)


def render(proto, S):
    def f(x):
        return "NA" if x is None else (f"{x['k']}/{x['n']} ({x['rate']:.0%})" if isinstance(x, dict) else str(x))
    L = ["# EXP-01b 판별력 개선 1차 평가(EXPLORATORY, DDXPlus TRAIN16 새 100명 — 임상 성능 아님)", "",
         f"- 프로토콜 고정 {proto['created']} · 무작위 기준 top1 25% · top3 75% · WD 제외 1위 33% · 동점은 비관/낙관 병기",
         "- 정답·WD 일치 ≠ 의학적 적절성. 반박 관계·진단 규칙 없음. 4질환 폐쇄 집합. 수치는 rows.csv·summary.json 에서 생성.", ""]
    cols = ["top1_pess", "top1_opt", "top3_pess", "alt_first_pess", "alt_first_opt", "review_incl", "review_random_expected",
            "tie_rate", "max_unique_share", "used_codes_mean", "pos_in_graph_mean", "gap_C_mean_A", "A_review_signal",
            "A_gap_flag", "A_old_any_unexplained"]
    for scope in ["ALL"] + DISEASES:
        L += [f"## {scope}", "| 팔 | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        for arm in ("OLD_GRADED", "NEW_GRADED", "NEW_SPEC"):
            L.append(f"| {arm} | " + " | ".join(f(S[arm][scope][c]) for c in cols) + " |")
        if scope == "Pulmonary embolism":
            L.append("- PE 누락(조건 B, 25건): " + " · ".join(
                f"{arm} top3 밖 {S[arm][scope]['pe_miss_top3_pess']} / WD 제외 1위 아님 {S[arm][scope]['pe_miss_alt_first_pess']} / "
                f"추가 검토 후보 없음 {S[arm][scope]['pe_miss_review']}" for arm in ("OLD_GRADED", "NEW_GRADED", "NEW_SPEC")))
        L.append("")
    L += ["## 1위 분포(조건 무관, 환자별)", ""] + [f"- {arm}: {S[arm]['ALL']['top_distribution']}" for arm in ("OLD_GRADED", "NEW_GRADED", "NEW_SPEC")]
    L += ["", "## 지식원 풍부도(질환별 SUGGESTS 간선 수)", f"- OLD {S['kb']['OLD']}", f"- NEW {S['kb']['NEW']}"]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("select").add_argument("--out", required=True)
    sub.add_parser("run").add_argument("--dir", required=True)
    a = ap.parse_args()
    cmd_select(Path(a.out)) if a.cmd == "select" else cmd_run(Path(a.dir))


if __name__ == "__main__":
    main()
