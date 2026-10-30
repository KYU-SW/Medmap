"""EXP-01b 첫 소규모 성능 탐색 실험(EXPLORATORY — 임상 성능 검증·확인적 검정 아님, RG 사전등록 없음: 사용자 지시).

단계(결과를 보기 전에 1단계에서 사례·조건·지표·코드 SHA 고정):
  1) select  : TRAIN16(EXP-01 HOLDOUT 제외)에서 4질환 × 25 선정 + 조건 B 의 가상 WD 고정 + protocol.json(코드·매핑 SHA, 지표 정의) 저장
  2) run     : protocol.json 의 코드 SHA 와 현재 코드가 같을 때만 계산 → rows.csv · summary.json · report_ko.md
선정 규칙: PATHOLOGY ∈ 4질환, holdout=False, 개발 사례(dev_cases_20261029_1456, 매핑 수정에 사용)와 row 겹침 제외,
  sha256("EXP01B_EXPLORE1|"+row_index) 오름차순 질환별 앞 25.
조건 A: WD = DDXPlus 정답. 조건 B: WD = 정답 제외 3질환(고정 순서 OTHERS[정답]) 중 질환 내 순번 k 에 대해 k % 3 번째.
정답 질환은 평가에만 사용, 엔진 입력에 없음. 가중치 학습·임계값 조정 없음.
실행: ~/ai_env/bin/python -B explore1.py select --out outputs/explore1_<시각>
      ~/ai_env/bin/python -B explore1.py run --dir outputs/explore1_<시각>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from ddxplus_adapter import build_mapping, mapping_summary, parse_tokens, patient_from_case
from extract_dev_cases import TRAIN, is_holdout, split_key
from graph_engine import assess_working_dx, infer, isa_closure
from knowledge_real_kg import SELECTED, build_real_graph, disease_node_id

HERE = Path(__file__).resolve().parent
DEV = HERE / "outputs/dev_cases_20261029_1456/dev_cases.json"
N_PER = 25
DISEASES = list(SELECTED)                                 # Pulmonary embolism, Pericarditis, Myocarditis, Tuberculosis
OTHERS = {d: [x for x in DISEASES if x != d] for d in DISEASES}
CODE_FILES = ["graph_engine.py", "knowledge_real_kg.py", "ddxplus_adapter.py", "explore1.py", "report_ko.py"]
VARIANTS = {"ALL": (), "CLINICAL_ONLY": ("HSDN_LITERATURE_COOCCURRENCE",),
            "HSDN_ONLY": ("DISMECH_QUOTE_IN_ABSTRACT", "DISMECH_PMID_QUOTE_UNVERIFIED", "DISMECH_NO_REF")}
METRICS = {
    "A_input_codes": "환자 EVIDENCES 의 고유 DDXPlus 코드 수(병력 포함)",
    "A_exact_codes": "그중 매핑 상태 EXACT·EXACT_COMPOSITE(흉통은 E_53 동반 시) 코드 수",
    "A_used_codes": "그래프 HP 노드 기록을 만든 코드 수(EXACT·EXACT_BROADER·흉통 복합, 값 규칙 적용 후 양성/명시 음성)",
    "A_unmapped_ratio": "1 − used/input",
    "A_gap_true": "환자 그래프 내 양성 근거 중 정답 질환으로 가는 SUGGESTS 경로(자신·IS_A 상위 포함)가 없는 비율(양성 0 이면 NA)",
    "B_wd_support_paths": "WD SUPPORTS 경로 수(모든 경로에 출처 문자열 있음 → '출처 있는 경로')",
    "B_wd_groups": "WD 독립 지지 묶음 수 · 임상 소견 묶음 수",
    "B_unexplained": "설명 부족 분류 근거 수(4분류 합)", "B_undetermined": "WD 판단 불가 근거 수",
    "C_recover": "조건 B: 정답 질환이 WD 추가 검토 후보(review_candidates)에 있음",
    "C_rank": "정답 질환 순위(비관적: 같은 정렬 키 동점은 모두 앞에 둠, 낙관적 병기). 정렬 graded=(−임상 묶음, −전체 묶음), support=(−전체 묶음)",
    "C_pe_miss": "정답 PE 인 조건 B 에서 PE 가 추가 검토 후보에 없음 / 비관적 top3 밖",
    "D_warn": "조건 A: 설명 부족 ≥1(전체·EXPLAINED_BY_OTHER 만) 비율, 추가 검토 후보 ≥1 비율",
    "D_withhold": "조건 A·B: WD 지지 묶음 0(근거 부족으로 지지 판단 불가) 비율 · 충돌 지식 NO_KNOWLEDGE 비율",
    "E_variants": f"지식원 변형 {list(VARIANTS)} 별 C·D 지표, graded·support 정렬",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def code_shas() -> dict:
    return {f: sha(HERE / f) for f in CODE_FILES}


# ───────────── 1) select ─────────────

def cmd_select(out: Path):
    out.mkdir(parents=True, exist_ok=False)
    dev_rows = {c["row_index"] for c in json.loads(DEV.read_text(encoding="utf-8"))["cases"]}
    cand, n, hold = {d: [] for d in DISEASES}, 0, 0
    for ch in pd.read_csv(TRAIN, usecols=["AGE", "SEX", "PATHOLOGY", "EVIDENCES", "INITIAL_EVIDENCE"], chunksize=200_000):
        for i, (age, sex, pat, evs, ini) in enumerate(zip(ch.AGE, ch.SEX, ch.PATHOLOGY, ch.EVIDENCES, ch.INITIAL_EVIDENCE)):
            ri = n + i
            k = split_key(ri, age, sex, pat, evs)
            h = is_holdout(k)
            hold += h
            if not h and pat in SELECTED and ri not in dev_rows:
                cand[pat].append({"row_index": ri, "split_key": k, "AGE": int(age), "SEX": sex,
                                  "PATHOLOGY_EVAL_ONLY": pat, "EVIDENCES": evs, "INITIAL_EVIDENCE": ini,
                                  "order": hashlib.sha256(f"EXP01B_EXPLORE1|{ri}".encode()).hexdigest()})
        n += len(ch)
    if (n, hold) != (1_025_602, 204_663):
        raise SystemExit(f"split mismatch {n} {hold}")
    cases = []
    for d in DISEASES:
        for k, c in enumerate(sorted(cand[d], key=lambda r: r["order"])[:N_PER]):
            cases.append({**c, "k": k, "wd_A": d, "wd_B": OTHERS[d][k % 3]})
    m = build_mapping()
    g, meta = build_real_graph(sorted({h for v in m.values() if v["used"] for h in v["hp_ids"]}))
    proto = {"created": time.strftime("%Y-%m-%d %H:%M:%S"), "type": "EXPLORATORY(사전등록 심사 없음, 사용자 지시)",
             "code_sha256": code_shas(), "mapping_summary": mapping_summary(m),
             "mapping_sha256": hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest(),
             "kg_counts": meta["counts"], "kg_sources": meta["sources"],
             "selection": {"rule": __doc__.split("선정 규칙:")[1].split("조건 A")[0].strip(), "n_per_disease": N_PER,
                           "candidates": {d: len(v) for d, v in cand.items()}, "dev_rows_excluded": sorted(dev_rows),
                           "split_check": {"rows": n, "holdout": hold}},
             "conditions": {"A": "WD = 정답", "B": "WD = OTHERS[정답][k % 3]", "OTHERS": OTHERS},
             "metrics": METRICS, "variants": {k: list(v) for k, v in VARIANTS.items()},
             "primary_ranking": "graded(비관적 동점)", "limitations": [
                 "DDXPlus = 합성 환자, 정답·WD 일치 ≠ 의학적 적절성", "설명 부족의 의학적 정확성은 이 자료로 검증 불가",
                 "반박 관계·AND/OR 진단 규칙 없음", "4질환 폐쇄 집합(정답이 항상 4개 중 하나)"]}
    (out / "protocol.json").write_text(json.dumps(proto, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"cases": len(cases), "candidates": proto["selection"]["candidates"]}, ensure_ascii=False))


# ───────────── 2) run ─────────────

def ranks(inf, target, key):
    def kv(x):
        return (-x.n_clinical, -x.n_support) if key == "graded" else (-x.n_support,)
    me = kv(inf.diseases[target])
    others = [kv(x) for d, x in inf.diseases.items() if d != target]
    better = sum(1 for o in others if o < me)
    tie = sum(1 for o in others if o == me)
    return better + tie + 1, better + 1                              # 비관적, 낙관적


def make_graph(m, drop):
    g, meta = build_real_graph(sorted({h for v in m.values() if v["used"] for h in v["hp_ids"]}))
    for e in [e for v in g.out.values() for e in v if e.spec_dict().get("evidence_class") in drop]:
        g.remove_edge(e)
    return g


def coverage(case, m, pr, g):
    toks = parse_tokens(case["EVIDENCES"])
    codes = sorted(toks)
    recs = pr.all_records()
    used = sorted({r.source_id.split("-", 1)[1] for r in recs if r.node_id in g.nodes})   # source_id = "<pid>-<E 코드>"
    exact = [c for c in codes if m[c]["status"] == "EXACT" or (c == "E_55" and "HP:0100749" in {r.node_id for r in recs})]
    return codes, exact, used


def gap_true(g, inf, d):
    pos = list(inf.positive_in_graph)
    if not pos:
        return None
    linked = {e.src for e in g.in_edges(d, "SUGGESTS")}
    miss = [n for n in pos if not (isa_closure(g, n) & linked)]
    return len(miss) / len(pos)


def pe_cause(g, m, case, pr, inf, wd_assess, truth):
    """정답 PE 가 조건 B 에서 대안에 없거나 top3 밖일 때 원인 1개(우선순위 순)."""
    linked = {e.src for e in g.in_edges(truth, "SUGGESTS")}
    pos = set(inf.positive_in_graph)
    hit = {n for n in pos if isa_closure(g, n) & linked}
    toks = parse_tokens(case["EVIDENCES"])
    lost = sorted(c for c in toks if not m[c]["used"]
                  and set(m[c].get("candidate_hp_ids", [])) & (linked | {a for h in linked for a in isa_closure(g, h)}))
    de = inf.diseases[truth]
    if not toks:
        return "NO_PATIENT_INFO", hit, lost
    if hit and de.n_support == 0:
        return "INFERENCE_MISSED", hit, lost
    if hit:
        return "RANKING_PUSHED_DOWN", hit, lost
    if lost:
        return "MAPPING_FAILURE", hit, lost
    if pos:
        return "NO_KG_RELATION", hit, lost
    return "NO_PATIENT_INFO_MAPPED", hit, lost


def cmd_run(d: Path):
    proto = json.loads((d / "protocol.json").read_text(encoding="utf-8"))
    if proto["code_sha256"] != code_shas():
        raise SystemExit("코드가 protocol 고정 시점과 다름 — 실행 거부")
    cases = json.loads((d / "cases.json").read_text(encoding="utf-8"))
    m = build_mapping()
    if hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest() != proto["mapping_sha256"]:
        raise SystemExit("매핑이 protocol 과 다름 — 실행 거부")
    graphs = {k: make_graph(m, v) for k, v in VARIANTS.items()}
    rows, pe_rows = [], []
    for c in cases:
        truth = disease_node_id(c["PATHOLOGY_EVAL_ONLY"])
        for cond in ("A", "B"):
            wd = disease_node_id(c[f"wd_{cond}"])
            for vname, g in graphs.items():
                pr, _, new = patient_from_case(f"X{c['row_index']}", c, m, wd)
                for r in new:
                    pr.add(r)
                inf = infer(g, pr, 2.0)
                a = assess_working_dx(g, inf, pr, wd)
                codes, exact, used = coverage(c, m, pr, g)
                de = inf.diseases[wd]
                cls = [x[1] for x in a.unexplained]
                row = {"row_index": c["row_index"], "truth": c["PATHOLOGY_EVAL_ONLY"], "k": c["k"], "cond": cond,
                       "variant": vname, "wd": c[f"wd_{cond}"], "age": c["AGE"], "sex": c["SEX"],
                       "n_input_codes": len(codes), "n_exact_codes": len(exact), "n_used_codes": len(used),
                       "unmapped_ratio": round(1 - len(used) / len(codes), 4) if codes else None,
                       "n_pos_in_graph": len(inf.positive_in_graph), "n_out_of_graph": len(inf.positive_out_of_graph),
                       "gap_true": gap_true(g, inf, truth),
                       "wd_support_paths": sum(p.state == "SUPPORTS" for p in de.paths),
                       "wd_support_paths_with_source": sum(p.state == "SUPPORTS" and all(h[3] for h in p.hops) for p in de.paths),
                       "wd_groups": de.n_support, "wd_clinical_groups": de.n_clinical,
                       "n_unexplained": len(cls), "n_explained_by_other": cls.count("EXPLAINED_BY_OTHER"),
                       "n_narrower": cls.count("NARROWER_CONCEPT_LINKED"), "n_unexpl_in_graph": cls.count("UNEXPLAINED_IN_GRAPH"),
                       "n_wd_path_not_sat": cls.count("WD_PATH_NOT_SATISFIED"), "n_undetermined": len(a.undetermined),
                       "conflict_knowledge": a.conflict_knowledge,
                       "review": ";".join(x[0][3:] for x in a.review_candidates),
                       "truth_in_review": truth in dict(a.review_candidates),
                       "truth_groups": inf.diseases[truth].n_support, "truth_clinical": inf.diseases[truth].n_clinical}
                for key in ("graded", "support"):
                    pess, opt = ranks(inf, truth, key)
                    row[f"rank_{key}_pess"], row[f"rank_{key}_opt"] = pess, opt
                rows.append(row)
                if vname == "ALL" and cond == "B" and c["PATHOLOGY_EVAL_ONLY"] == "Pulmonary embolism":
                    miss = (not row["truth_in_review"]) or row["rank_graded_pess"] > 3
                    if miss:
                        cause, hit, lost = pe_cause(g, m, c, pr, inf, a, truth)
                        pe_rows.append({"row_index": c["row_index"], "wd": c["wd_B"], "in_review": row["truth_in_review"],
                                        "rank_graded_pess": row["rank_graded_pess"], "cause": cause,
                                        "pe_linked_patient_nodes": sorted(hit), "lost_by_mapping_codes": lost,
                                        "pe_groups": row["truth_groups"], "pe_clinical": row["truth_clinical"],
                                        "wd_groups": row["wd_groups"], "wd_clinical": row["wd_clinical_groups"]})
    with open(d / "rows.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (d / "pe_miss.json").write_text(json.dumps(pe_rows, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = summarize(rows, pe_rows)
    (d / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "report_ko.md").write_text(render(proto, summary), encoding="utf-8")
    print(d)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def _rate(xs):
    xs = list(xs)
    return {"k": sum(bool(x) for x in xs), "n": len(xs), "rate": round(sum(bool(x) for x in xs) / len(xs), 4) if xs else None}


def summarize(rows, pe_rows):
    S = {}
    for v in VARIANTS:
        for scope in ["ALL"] + DISEASES:
            R = [r for r in rows if r["variant"] == v and (scope == "ALL" or r["truth"] == scope)]
            A = [r for r in R if r["cond"] == "A"]
            B = [r for r in R if r["cond"] == "B"]
            S[f"{v}|{scope}"] = {
                "n_patients": len(A),
                "coverage": {"input_codes_mean": _mean(r["n_input_codes"] for r in A),
                             "exact_codes_mean": _mean(r["n_exact_codes"] for r in A),
                             "used_codes_mean": _mean(r["n_used_codes"] for r in A),
                             "unmapped_ratio_mean": _mean(r["unmapped_ratio"] for r in A),
                             "pos_in_graph_mean": _mean(r["n_pos_in_graph"] for r in A),
                             "gap_true_mean": _mean(r["gap_true"] for r in A),
                             "no_pos_in_graph": _rate(r["n_pos_in_graph"] == 0 for r in A)},
                "A_truth_wd": {"support_paths_mean": _mean(r["wd_support_paths"] for r in A),
                               "support_paths_with_source_mean": _mean(r["wd_support_paths_with_source"] for r in A),
                               "groups_mean": _mean(r["wd_groups"] for r in A),
                               "clinical_groups_mean": _mean(r["wd_clinical_groups"] for r in A),
                               "unexplained_mean": _mean(r["n_unexplained"] for r in A),
                               "undetermined_mean": _mean(r["n_undetermined"] for r in A),
                               "warn_any_unexplained": _rate(r["n_unexplained"] > 0 for r in A),
                               "warn_explained_by_other": _rate(r["n_explained_by_other"] > 0 for r in A),
                               "warn_review_nonempty": _rate(bool(r["review"]) for r in A),
                               "withhold_wd_support0": _rate(r["wd_groups"] == 0 for r in A),
                               "conflict_no_knowledge": _rate(r["conflict_knowledge"] == "NO_KNOWLEDGE" for r in A),
                               "truth_top1_graded_pess": _rate(r["rank_graded_pess"] == 1 for r in A)},
                "B_wrong_wd": {"support_paths_mean": _mean(r["wd_support_paths"] for r in B),
                               "groups_mean": _mean(r["wd_groups"] for r in B),
                               "unexplained_mean": _mean(r["n_unexplained"] for r in B),
                               "undetermined_mean": _mean(r["n_undetermined"] for r in B),
                               "warn_any_unexplained": _rate(r["n_unexplained"] > 0 for r in B),
                               "truth_in_review": _rate(r["truth_in_review"] for r in B),
                               "withhold_wd_support0": _rate(r["wd_groups"] == 0 for r in B),
                               **{f"truth_top{k}_{key}_{t}": _rate(r[f"rank_{key}_{t}"] <= k for r in B)
                                  for k in (1, 3) for key in ("graded", "support") for t in ("pess", "opt")}}}
    S["pe_miss_ALL_condB"] = {"n": len(pe_rows), "by_cause": {c: sum(r["cause"] == c for r in pe_rows)
                                                             for c in sorted({r["cause"] for r in pe_rows})}}
    return S


def render(proto, S):
    def r(x):
        return "NA" if x is None else (f"{x['k']}/{x['n']} ({x['rate']:.1%})" if isinstance(x, dict) else str(x))
    L = ["# EXP-01b 첫 소규모 성능 탐색 실험(EXPLORATORY)", "",
         "> DDXPlus TRAIN16 합성 환자 100명 × 조건 2(A: WD=정답, B: WD=고정된 다른 질환). 임상 성능·확인적 검정 아님.",
         "> 정답·WD 일치는 의학적 적절성의 정답이 아니며, 설명 부족의 의학적 정확성은 이 자료로 검증할 수 없다.",
         "> 반박 관계·AND/OR 진단 규칙 없음. 4질환 폐쇄 집합. 수치는 모두 rows.csv 에서 계산.", "",
         f"- 프로토콜 고정 {proto['created']} · 코드 SHA {', '.join(f'{k}={v[:10]}' for k, v in proto['code_sha256'].items())}",
         f"- 매핑 {proto['mapping_summary']} · 지식 그래프 {proto['kg_counts']['edges_by_rel_class']}", ""]
    for v in VARIANTS:
        L += [f"## 지식원 변형 {v}", "",
              "| 범위 | n | 입력 코드 | EXACT 코드 | 사용 코드 | 미연결 비율 | 그래프 양성 | 정답 지식 부족 | A 지지 경로 | A 묶음(임상) | A 설명부족≥1 | A 다른질환 설명≥1 | A 검토후보≥1 | A WD지지0 | B 정답∈검토후보 | B top1 graded 비관 | B top3 graded 비관 | B top1 support 비관 | B top3 support 비관 | B top1 graded 낙관 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for scope in ["ALL"] + DISEASES:
            x = S[f"{v}|{scope}"]
            c, a, b = x["coverage"], x["A_truth_wd"], x["B_wrong_wd"]
            L.append(f"| {scope} | {x['n_patients']} | {c['input_codes_mean']} | {c['exact_codes_mean']} | {c['used_codes_mean']} | "
                     f"{c['unmapped_ratio_mean']} | {c['pos_in_graph_mean']} | {c['gap_true_mean']} | {a['support_paths_mean']} | "
                     f"{a['groups_mean']}({a['clinical_groups_mean']}) | {r(a['warn_any_unexplained'])} | {r(a['warn_explained_by_other'])} | "
                     f"{r(a['warn_review_nonempty'])} | {r(a['withhold_wd_support0'])} | {r(b['truth_in_review'])} | "
                     f"{r(b['truth_top1_graded_pess'])} | {r(b['truth_top3_graded_pess'])} | {r(b['truth_top1_support_pess'])} | "
                     f"{r(b['truth_top3_support_pess'])} | {r(b['truth_top1_graded_opt'])} |")
        L.append("")
    L += ["## PE 정답 · 조건 B · ALL 에서 대안 누락 또는 top3 밖", "```json", json.dumps(S["pe_miss_ALL_condB"], ensure_ascii=False), "```",
          "- 원인 정의: NO_PATIENT_INFO(기록 근거 없음) / MAPPING_FAILURE(PE 관련 HPO 후보를 가진 코드가 REVIEW 등으로 미사용) / "
          "NO_KG_RELATION(그래프 양성은 있으나 PE 로 가는 관계 없음) / INFERENCE_MISSED(관계·양성이 있는데 지지 0) / "
          "RANKING_PUSHED_DOWN(PE 지지는 있으나 정렬·후보 규칙에서 밀림). 사례별 = pe_miss.json"]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("select")
    s1.add_argument("--out", required=True)
    s2 = sub.add_parser("run")
    s2.add_argument("--dir", required=True)
    a = ap.parse_args()
    cmd_select(Path(a.out)) if a.cmd == "select" else cmd_run(Path(a.dir))


if __name__ == "__main__":
    main()
