"""M5(독립 감사): manifest expected_outputs 7종 + 이차 지표 집계.

split_manifest.json · metrics.csv · comparisons.csv · per_case.parquet · graph_stats.json · run_meta.json · subgroups.csv
모든 숫자는 사례별 기록(per_case)에서 계산한다. 근거 문자열·환자 원문은 저장하지 않는다.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

import metrics as mt

GROUP_KEYS = ("model", "budget", "wd_mode", "seed", "tau", "noise")
PER_CASE_COLS = ("row_index", "truth", "model", "budget", "wd_mode", "seed", "tau", "noise", "rank", "top1", "top3",
                 "top5", "in8", "p_top1", "top1_correct", "brier", "n_questions", "first_top5_step", "counter", "ms",
                 "truth_gap", "wrong_term", "prune_steps", "cand_steps", "reactivations", "neg_events", "neg_hits",
                 "init_top1", "wd", "diff_recall", "novel", "age", "sex", "leak")


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def wrong_term_at(r, tau):
    if r["truth_gap"] is not None:
        return None if tau is None else bool(r["truth_gap"] < math.log(tau))
    return r["wrong_term"]


def group(recs):
    g = collections.defaultdict(list)
    for r in recs:
        g[tuple(r[k] for k in GROUP_KEYS)].append(r)
    return g


def metrics_rows(recs, severe, taus):
    rows = []
    for k, rs in sorted(group(recs).items(), key=lambda x: tuple(str(v) for v in x[0])):
        sev = [r for r in rs if r["truth"] in severe]
        eval_taus = [k[4]] if k[4] is not None else (list(taus) if k[0] == "PB_REL" else [None])
        wts = {}
        for tv in eval_taus:
            wts[str(tv)] = _mean([None if wrong_term_at(r, tv) is None else float(wrong_term_at(r, tv)) for r in rs])
        conf = np.array([r["p_top1"] for r in rs if r["p_top1"] is not None])
        corr = np.array([r["top1_correct"] for r in rs if r["p_top1"] is not None], dtype=float)
        ece = None
        if len(conf):
            edges = np.linspace(0, 1, 16)
            ece = 0.0
            for lo, hi in zip(edges[:-1], edges[1:]):
                msk = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
                if msk.any():
                    ece += msk.mean() * abs(corr[msk].mean() - conf[msk].mean())
        per_d = collections.defaultdict(list)
        for r in rs:
            per_d[r["truth"]].append(r["top5"])
        neg_e = sum(r["neg_events"] or 0 for r in rs)
        cand = sum(r["cand_steps"] or 0 for r in rs)
        rows.append({
            "model": k[0], "budget": k[1], "wd_mode": k[2], "seed": k[3], "tau": k[4], "noise": k[5], "n": len(rs),
            "top1": _mean([r["top1"] for r in rs]), "top3": _mean([r["top3"] for r in rs]),
            "top5": _mean([r["top5"] for r in rs]), "recall8": _mean([r["in8"] for r in rs]),
            "macro_top5": _mean([np.mean(v) for v in per_d.values()]),
            "severe_n": len(sev), "severe_miss": _mean([not r["in8"] for r in sev]),
            "wrong_term_by_tau": json.dumps(wts),
            "diff_recall": _mean([r["diff_recall"] for r in rs]),
            "neg_direction_rate": (sum(r["neg_hits"] or 0 for r in rs) / neg_e) if neg_e else None,
            "first_top5_step_mean": _mean([(r["first_top5_step"] if r["first_top5_step"] is not None else r["budget"] + 1)
                                           for r in rs]),
            "mean_questions": _mean([r["n_questions"] for r in rs]),
            "counter_median": (float(np.median([r["counter"] for r in rs])) if rs[0]["counter"] is not None else None),
            "prune_rate": (sum(r["prune_steps"] or 0 for r in rs) / cand) if cand else None,
            "reactivations_mean": _mean([r["reactivations"] for r in rs]),
            "ece_top1": ece, "brier": _mean([r["brier"] for r in rs]),
            "ms_p50": float(np.percentile([r["ms"] for r in rs], 50)),
            "ms_p95": float(np.percentile([r["ms"] for r in rs], 95)),
            "leak_checked": sum(1 for r in rs if r["leak"] == "PASS"),
            "leak_na": sum(1 for r in rs if r["leak"] == "NA"),
        })
    return rows


def _wilson(k, n, z=1.959964):
    """누락 0건에서도 의미 있는 95% Wilson 구간(통계 gate5 MINOR, 기술 통계)."""
    if not n:
        return {"severe_miss_wilson_lo": None, "severe_miss_wilson_hi": None}
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {"severe_miss_wilson_lo": max(0.0, c - h), "severe_miss_wilson_hi": min(1.0, c + h)}


def _age_band(a):
    return "0-14" if a < 15 else ("15-64" if a < 65 else "65+")


def subgroup_rows(recs, severe, prior, classes):
    """AGE·SEX·사전확률 사분위·FINAL_NOVEL·질환별(n, 누락 수, 누락률, SE) — 주 비교 조건(Q=5, noise 없음)."""
    q = np.quantile(prior, [0.25, 0.5, 0.75])
    pq = {c: int(np.searchsorted(q, prior[i], side="right")) + 1 for i, c in enumerate(classes)}
    out = []
    for k, rs in sorted(group(recs).items(), key=lambda x: tuple(str(v) for v in x[0])):
        if k[1] != 5 or k[5] is not None:
            continue
        base = dict(zip(GROUP_KEYS, k))
        def add(dim, val, sub):
            if not sub:
                return
            sv = [r for r in sub if r["truth"] in severe]
            m = _mean([not r["in8"] for r in sv])
            out.append({**base, "dimension": dim, "value": val, "n": len(sub), "top5": _mean([r["top5"] for r in sub]),
                        "severe_n": len(sv), "severe_miss_count": sum(1 for r in sv if not r["in8"]),
                        "severe_miss": m, "severe_miss_se": (math.sqrt(m * (1 - m) / len(sv)) if sv else None),
                        **_wilson(sum(1 for r in sv if not r["in8"]), len(sv))})
        for band in ("0-14", "15-64", "65+"):
            add("age", band, [r for r in rs if _age_band(r["age"]) == band])
        for sx in ("M", "F"):
            add("sex", sx, [r for r in rs if r["sex"] == sx])
        for i in (1, 2, 3, 4):
            add("prior_quartile", i, [r for r in rs if pq[r["truth"]] == i])
        add("final_novel", True, [r for r in rs if r["novel"] is True])
        for d in sorted({r["truth"] for r in rs if r["truth"] in severe}):
            add("severe_disease", d, [r for r in rs if r["truth"] == d])
    return out


def wd_mixture_rows(recs, severe, ps=(0.5, 0.7, 0.9)):
    """WD 정답률 혼합 민감도(기술 통계): 사례별 sha256 으로 WD_CORRECT / WD_MODEL_WRONG 중 하나를 고른다."""
    out = []
    by = collections.defaultdict(dict)
    for r in recs:
        if r["model"] == "PC" and r["wd_mode"] in ("WD_CORRECT", "WD_MODEL_WRONG") and r["noise"] is None:
            by[(r["budget"], r["tau"])].setdefault(r["row_index"], {})[r["wd_mode"]] = r
    for (Q, tau), cases in sorted(by.items(), key=lambda x: (x[0][0], str(x[0][1]))):
        for p in ps:
            pick = []
            for ri, d in cases.items():
                if len(d) < 2:
                    continue
                u = int(hashlib.sha256(f"EXP01WDMIX|{p}|{ri}".encode()).hexdigest()[:8], 16) / 2**32
                pick.append(d["WD_CORRECT"] if u < p else d["WD_MODEL_WRONG"])
            sv = [r for r in pick if r["truth"] in severe]
            out.append({"budget": Q, "tau": tau, "p_correct": p, "n": len(pick), "top5": _mean([r["top5"] for r in pick]),
                        "severe_miss": _mean([not r["in8"] for r in sv])})
    return out


def wd_model_agreement(recs):
    """WD_MODEL 과 그래프 계열 초기 top-1(첫 질문 전) 일치율."""
    init = {r["row_index"]: r["init_top1"] for r in recs if r["model"] == "C" and r["init_top1"] is not None}
    wd = {r["row_index"]: r["wd"] for r in recs if r["model"] == "PC" and r["wd_mode"] == "WD_MODEL"}
    common = sorted(set(init) & set(wd))
    return {"n": len(common), "agreement": (float(np.mean([init[i] == wd[i] for i in common])) if common else None)}


def graph_stats(lik, cond_edges=None):
    out = {"relation_counts": lik.relation_counts()}
    if cond_edges is not None:
        sug = {(lik.classes[d], q) for q in lik.binary for d in range(lik.n) if lik.suggests[q][d]}
        cond_b = {(d, q) for d, q in cond_edges if q in lik.p_pos}
        inter = sug & cond_b
        out["suggests_vs_generator_table"] = {
            "suggests_edges": len(sug), "generator_binary_edges": len(cond_b), "overlap": len(inter),
            "precision": len(inter) / len(sug) if sug else None, "recall": len(inter) / len(cond_b) if cond_b else None,
            "note": "평가 전용(생성기 지식표 ↔ TRAIN16 학습 그래프 일치율, 기능적 순환 정도)"}
    return out


def write_csv(path, rows):
    rows = list(rows)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        if not rows:
            fh.write("status\nEMPTY\n")
            return
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def comparisons_rows(final):
    """FINAL 확인적 분석 → 비교표(성분 p·합성 p·rank·α_j*·Holm 조정 p·기각·라벨)."""
    rows = []
    for h, comps in final["components"].items():
        hol = final["holm"][h]
        for comp, p in comps.items():
            rows.append({"hypothesis": h, "component": comp, "component_p": p, "composite_p": final["composite"][h],
                         "rank": hol["rank"], "alpha_star": hol["alpha_star"], "holm_adjusted_p": hol["p_adj"],
                         "rejected": hol["rejected"]})
    for st, lab in final["stages"].items():
        rows.append({"hypothesis": f"STAGE:{st}", "component": "label", "component_p": None,
                     "composite_p": None, "rank": None, "alpha_star": None, "holm_adjusted_p": None,
                     "rejected": json.dumps(lab, ensure_ascii=False)})
    rows.append({"hypothesis": "H1", "component": "label", "component_p": None, "composite_p": None, "rank": None,
                 "alpha_star": None, "holm_adjusted_p": None,
                 "rejected": json.dumps({"label": final["H1"], "effect": final["effect"],
                                         "prespecified_model": final["prespecified_model"]}, ensure_ascii=False)})
    return rows


def per_case_frame(recs):
    """사례 기록 → DataFrame. 열 단위 기록(parallel.RecordTable)은 열에서 바로 만든다(행 dict 재생성 없음 — 메모리)."""
    import pandas as pd
    if hasattr(recs, "column"):
        return pd.DataFrame({c: recs.column(c) for c in PER_CASE_COLS})
    return pd.DataFrame([{c: r.get(c) for c in PER_CASE_COLS} for r in recs])


def write_per_case(recs, path, rows_per_group=1 << 20):
    """per_case.parquet 쓰기. 작은 표·dict 기록은 기존과 같은 to_parquet 한 번.
    큰 열 단위 표(parallel.RecordTable)는 표 전체 DataFrame 을 만들지 않는다(메모리): 열마다 전체 열로 형을 정한 뒤
    (DataFrame 생성과 같은 추론), 그 형을 지정해 행 묶음씩 DataFrame→arrow 로 바꿔 쓴다."""
    import pandas as pd
    if not hasattr(recs, "column") or len(recs) <= rows_per_group:
        per_case_frame(recs).to_parquet(path, index=False)
        return
    import pyarrow as pa
    import pyarrow.parquet as pq
    dtypes, fields = {}, []
    for c in PER_CASE_COLS:
        s = pd.Series(recs.column(c))
        dtypes[c] = s.dtype
        fields.append(pa.Table.from_pandas(s.to_frame(c), preserve_index=False).schema.field(c))
        del s

    def frame(lo, hi):
        return pd.DataFrame({c: pd.Series(recs.column(c)[lo:hi], dtype=dtypes[c]) for c in PER_CASE_COLS})
    meta = pa.Schema.from_pandas(frame(0, min(len(recs), rows_per_group)), preserve_index=False).metadata
    schema = pa.schema(fields, metadata=meta)
    with pq.ParquetWriter(path, schema) as w:
        for lo in range(0, len(recs), rows_per_group):
            w.write_table(pa.Table.from_pandas(frame(lo, lo + rows_per_group), schema=schema, preserve_index=False))


def write_all(out: Path, recs, severe, taus, prior, classes, lik, split_manifest: dict, run_meta: dict,
              final=None, cond_edges=None, tau_selection=None):
    out = Path(out)
    write_per_case(recs, out / "per_case.parquet")
    mrows = metrics_rows(recs, severe, taus)
    write_csv(out / "metrics.csv", mrows)
    write_csv(out / "subgroups.csv", subgroup_rows(recs, severe, prior, classes))
    if final is not None:
        write_csv(out / "comparisons.csv", comparisons_rows(final))
    else:
        write_csv(out / "comparisons.csv", [{"status": "NOT_COMPUTED_NON_FINAL",
                                             "note": "확인적 비교는 FINAL 1회에서만 계산(manifest)"}])
    gs = graph_stats(lik, cond_edges)
    gs["wd_model_vs_graph_initial_top1"] = wd_model_agreement(recs)
    gs["wd_mixture"] = wd_mixture_rows(recs, severe)
    (out / "graph_stats.json").write_text(json.dumps(gs, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    (out / "split_manifest.json").write_text(json.dumps(split_manifest, ensure_ascii=False, indent=1, default=float),
                                             encoding="utf-8")
    if tau_selection is not None:
        (out / "tau_selection.json").write_text(json.dumps(tau_selection, ensure_ascii=False, indent=1, default=float),
                                                encoding="utf-8")
    (out / "run_meta.json").write_text(json.dumps(run_meta, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps({"meta": run_meta, "rows": mrows}, ensure_ascii=False, indent=1,
                                                 default=float), encoding="utf-8")
    return mrows


def tau_stats(recs, severe, taus):
    """select_tau 입력(Q=5, noise 없음): PB 각 τ, PB_REL, PB_REL 가상 판정."""
    def rs(model, tau=None):
        return [r for r in recs if r["model"] == model and r["budget"] == 5 and r["noise"] is None
                and (model != "PB" or r["tau"] == tau)]
    def sm(x):
        sv = [r for r in x if r["truth"] in severe]
        return _mean([not r["in8"] for r in sv])
    st = {"PB_REL": {"severe_miss": sm(rs("PB_REL"))}}
    for t in taus:
        pb = rs("PB", t)
        st[t] = {"top5": _mean([r["top5"] for r in pb]), "k_top5": sum(1 for r in pb if r["top5"]), "n": len(pb),
                 "severe_miss": sm(pb),
                 "wrong_term": _mean([float(wrong_term_at(r, t)) for r in pb])}
        st[("PB_REL_virtual", t)] = {"wrong_term": _mean([float(wrong_term_at(r, t)) for r in rs("PB_REL")])}
    return st
