"""CSV -> 요약 CSV + 마크다운 표 (보고서 수치는 전부 여기서 생성)."""
import numpy as np, pandas as pd
D = "/home/<user>/medmap-gate0-parallel/C-mdq"
I = pd.read_csv(f"{D}/results_instances_main.csv")
M = pd.read_csv(f"{D}/results_methods_main.csv")
T = {}

def md(df, fmt="{:.3f}"):
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("NaN" if np.isnan(v) else (str(int(v)) if float(v).is_integer() and abs(v) > 0 and c.startswith("n") else fmt.format(v)))
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)

MAIN = [s for s in I.scen.unique() if not s.startswith("R")]
Im = I[I.scen.isin(MAIN)]
e = 1e-9
# --- 표1 환원 검증 ---
g = Im.groupby("scen", sort=False)
t1 = pd.DataFrame({
    "인스턴스": g.size(),
    "격자 milp=전수": g.apply(lambda x: int((abs(x.hs_milp - x.opt_batch_brute) < e).sum())),
    "정확 milp=전수=9a": g.apply(lambda x: int(((abs(x.x_hs_milp - x.x_opt_batch_brute) < e) & (abs(x.x_opt_batch_brute - x.cont_batch) < e)).sum())),
    "정확 8(DP)=9b": g.apply(lambda x: int((abs(x.x_opt_adaptive_worst - x.cont_adaptive_worst) < e).sum())),
    "격자 8=9b": g.apply(lambda x: int((abs(x.opt_adaptive_worst - x.cont_adaptive_worst) < e).sum())),
    "일괄>적응 비율": g.apply(lambda x: float((x.x_opt_batch_brute > x.x_opt_adaptive_worst + e).mean())),
    "평균(일괄-적응)": g.apply(lambda x: float((x.x_opt_batch_brute - x.x_opt_adaptive_worst).mean())),
    "AXp하한<적응 비율": g.apply(lambda x: float((x.x_axp_lb < x.x_opt_adaptive_worst - e).mean())),
    "UNDET비율(연속)": g.undet_frac_cont.mean(),
    "UNDET비율(격자)": g.undet_frac_grid.mean(),
}).reset_index().rename(columns={"scen": "조건"})
tot = pd.DataFrame([{"조건": "전체", "인스턴스": len(Im),
    "격자 milp=전수": int((abs(Im.hs_milp - Im.opt_batch_brute) < e).sum()),
    "정확 milp=전수=9a": int(((abs(Im.x_hs_milp - Im.x_opt_batch_brute) < e) & (abs(Im.x_opt_batch_brute - Im.cont_batch) < e)).sum()),
    "정확 8(DP)=9b": int((abs(Im.x_opt_adaptive_worst - Im.cont_adaptive_worst) < e).sum()),
    "격자 8=9b": int((abs(Im.opt_adaptive_worst - Im.cont_adaptive_worst) < e).sum()),
    "일괄>적응 비율": float((Im.x_opt_batch_brute > Im.x_opt_adaptive_worst + e).mean()),
    "평균(일괄-적응)": float((Im.x_opt_batch_brute - Im.x_opt_adaptive_worst).mean()),
    "AXp하한<적응 비율": float((Im.x_axp_lb < Im.x_opt_adaptive_worst - e).mean()),
    "UNDET비율(연속)": Im.undet_frac_cont.mean(), "UNDET비율(격자)": Im.undet_frac_grid.mean()}])
t1 = pd.concat([t1, tot], ignore_index=True)
t1.to_csv(f"{D}/results_summary_reduction.csv", index=False)
T["reduction"] = md(t1)

# --- 표2 정확 모델: 최악 (확률 없음) ---
X = M[M.method.str.startswith("X") & M.scen.isin(MAIN)]
gx = X.groupby("method")
t2 = pd.DataFrame({"평균 최악비용": gx.worst_cost.mean(), "평균 최악질문수": gx.worst_nq.mean(),
                   "평균 최적대비 차이(최악)": gx.gap_worst.mean(), "최대 차이": gx.gap_worst.max(),
                   "최적 달성 비율": gx.gap_worst.apply(lambda s: float((s.abs() < e).mean())),
                   "잘못된 확정": gx.wrong_det_u.max(), "평균 시간(s)": gx.time.mean()}).reset_index()
t2.to_csv(f"{D}/results_summary_exact_worst.csv", index=False)
T["exact_worst"] = md(t2)
# 9a/9b 행
N9 = M[M.method.str.startswith("9") & M.scen.isin(MAIN)].merge(Im[["scen", "seed", "x_opt_adaptive_worst"]], on=["scen", "seed"])
N9["gap_vs_X8"] = N9.worst_cost - N9.x_opt_adaptive_worst
t2b = N9.groupby("method").agg(평균최악비용=("worst_cost", "mean"), 평균차이_vs_X8=("gap_vs_X8", "mean"),
                               최대차이_vs_X8=("gap_vs_X8", "max"), 평균시간=("time", "mean")).reset_index()
T["mdq9"] = md(t2b)

# --- 표3 정확 모델: 기대(확률 가정) ---
t3 = pd.DataFrame({"기대비용(균등)": gx.exp_cost_u.mean(), "Bayes최적 대비 차이(균등)": gx.gap_exp_u.mean(),
                   "최대 차이(균등)": gx.gap_exp_u.max(), "기대질문수(균등)": gx.exp_nq_u.mean(),
                   "기대비용(편향 P(T)=0.2)": gx.exp_cost_s.mean()}).reset_index()
t3.to_csv(f"{D}/results_summary_exact_expected.csv", index=False)
T["exact_expected"] = md(t3)

# --- 표4 격자 모델 (VOI/regret/naive 포함) + 연속 진실 검증 ---
Gm = M[~M.method.str.startswith("X") & ~M.method.str.startswith("9") & M.scen.isin(MAIN)]
gg = Gm.groupby("method")
t4 = pd.DataFrame({"평균 최악비용": gg.worst_cost.mean(), "최악차이(격자8 대비)": gg.gap_worst.mean(),
                   "기대차이(균등, 격자8e 대비)": gg.gap_exp_u.mean(), "기대차이(편향)": gg.gap_exp_s.mean(),
                   "잘못된확정(격자)": gg.wrong_det_u.mean(), "잘못된보류(격자)": gg.wrong_hold_u.mean(),
                   "잘못된확정(연속진실)": gg.wrong_det_c.mean(), "잘못된보류(연속)": gg.hold_c.mean(),
                   "확정후 추가질문(연속)": gg.overask_c.mean(), "트리이탈(연속)": gg.off_c.mean(),
                   "평균 시간(s)": gg.time.mean()}).reset_index()
t4.to_csv(f"{D}/results_summary_grid.csv", index=False)
T["grid"] = md(t4)

# --- 표5 해상도 ---
R = I[I.scen.str.startswith("R")]
MR = M[M.scen.str.startswith("R") & (M.method == "8_opt_adaptive_worst")]
gr = R.groupby("scen", sort=False)
t5 = pd.DataFrame({"인스턴스": gr.size(),
                   "격자8=9b": gr.apply(lambda x: int((abs(x.opt_adaptive_worst - x.cont_adaptive_worst) < e).sum())),
                   "격자일괄=9a": gr.apply(lambda x: int((abs(x.opt_batch_brute - x.cont_batch) < e).sum())),
                   "UNDET 격자": gr.undet_frac_grid.mean(), "UNDET 연속": gr.undet_frac_cont.mean()}).reset_index()
w = MR.groupby("scen", sort=False).agg(잘못된확정_연속=("wrong_det_c", "mean"), 잘못된보류_연속=("hold_c", "mean"),
                                        트리이탈=("off_c", "mean")).reset_index()
t5 = t5.merge(w, on="scen").rename(columns={"scen": "해상도"})
t5.to_csv(f"{D}/results_summary_resolution.csv", index=False)
T["resolution"] = md(t5)

# --- 표6 시간 ---
t6 = Im.groupby("scen", sort=False).agg(T=("T", "mean"), 원자수=("n_atoms", "mean"), DP상태=("dp_states", "mean"),
        t_DP=("t_dp", "mean"), t_전수일괄=("t_brute", "mean"), t_milp=("t_milp", "mean"),
        t_9b=("t_cont_adapt", "mean"), t_9a=("t_cont_batch", "mean"), t_AXp=("t_axp", "mean")).reset_index()
T["timing"] = md(t6, "{:.4f}")
try:
    S = pd.read_csv(f"{D}/results_scaling.csv")
    t7 = S.groupby("n").mean(numeric_only=True).reset_index().drop(columns=["seed"])
    keep = [c for c in ["n", "n_pairs", "T", "t_milp", "hs_cost", "t_greedy", "greedy_worst", "t_ec2", "ec2_worst",
                        "t_dp", "dp_worst", "dp_states", "t_9b", "mdq9b_worst"] if c in t7.columns]
    T["scaling"] = md(t7[keep], "{:.3f}")
except FileNotFoundError:
    T["scaling"] = "(results_scaling.csv 없음)"

# --- 반례 목록 ---
def first(df, cond, cols):
    x = df[cond]
    return x[cols].head(3)
cx = []
a = Im[Im.x_opt_batch_brute > Im.x_opt_adaptive_worst + e]
cx.append(("일괄 최소비용 > 적응형 최악 최적", len(a), a[["scen", "seed", "x_opt_batch_brute", "x_opt_adaptive_worst"]].head(3).to_dict("records")))
a = Im[Im.x_axp_lb < Im.x_opt_adaptive_worst - e]
cx.append(("max AXp(최소충분근거) < 적응형 최악 최적", len(a), a[["scen", "seed", "x_axp_lb", "x_opt_adaptive_worst"]].head(3).to_dict("records")))
for meth in ["XEC2_unif", "X3_greedy_count", "X6b_hs_ordered"]:
    a = X[(X.method == meth) & (X.gap_worst > e)]
    cx.append((f"{meth} 최악비용 > 최적", len(a), a[["scen", "seed", "worst_cost", "gap_worst"]].head(3).to_dict("records")))
a = X[(X.method == "X8_opt_adaptive_worst") & (X.gap_exp_u > e)]
cx.append(("최악-최적 정책의 기대비용 > Bayes 최적(균등)", len(a), a[["scen", "seed", "exp_cost_u", "gap_exp_u"]].head(3).to_dict("records")))
a = X[(X.method == "X8e_opt_expected_unif") & (X.gap_worst > e)]
cx.append(("Bayes 최적(균등) 정책의 최악비용 > 최악 최적", len(a), a[["scen", "seed", "worst_cost", "gap_worst"]].head(3).to_dict("records")))
for meth in ["5_minimax_regret", "4_voi_unif"]:
    a = Gm[(Gm.method == meth) & (Gm.gap_worst > e)]
    cx.append((f"{meth} 최악비용 > 격자 최적", len(a), a[["scen", "seed", "worst_cost", "gap_worst"]].head(3).to_dict("records")))
a = Gm[(Gm.method == "8_opt_adaptive_worst") & (Gm.wrong_det_c > e)]
cx.append(("격자(표본) 최적정책이 연속 진실에서 잘못된 확정", len(a), a[["scen", "seed", "wrong_det_c"]].head(3).to_dict("records")))
a = Gm[(Gm.method == "0_naive_point") & (Gm.wrong_det_u > e)]
cx.append(("점추정 선호 정책의 잘못된 확정(격자)", len(a), a[["scen", "seed", "wrong_det_u"]].head(3).to_dict("records")))
lines = ["| 현상 | 해당 (인스턴스 또는 인스턴스×방법) 수 | 예시(최대 3) |", "|---|---|---|"]
nX = len(Im)
for name, k, ex in cx:
    exs = "; ".join(", ".join(f"{kk}={(round(vv,3) if isinstance(vv,float) else vv)}" for kk, vv in r.items()) for r in ex)
    lines.append(f"| {name} | {k} / {nX} | {exs} |")
T["counter"] = "\n".join(lines)

# VOI fallback 없음(트리 내부 기록 안 함) -> 생략
with open(f"{D}/tables_generated.md", "w") as f:
    for k, v in T.items():
        f.write(f"## {k}\n\n{v}\n\n")
print("tables:", list(T))
