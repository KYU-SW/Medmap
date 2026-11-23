"""C_MDQ_REPORT.md 생성: 서술 템플릿 + CSV 에서 계산한 수치/표만 삽입."""
import re
import numpy as np, pandas as pd
D = "/home/<user>/medmap-gate0-parallel/C-mdq"
I = pd.read_csv(f"{D}/results_instances_main.csv")
M = pd.read_csv(f"{D}/results_methods_main.csv")
H = pd.read_csv(f"{D}/results_hand_cases.csv")
V = pd.read_csv(f"{D}/results_validation_checks.csv").iloc[0]
S = pd.read_csv(f"{D}/results_struct_hitting.csv")
SC = pd.read_csv(f"{D}/results_scaling.csv")
tables = {}
cur = None
for line in open(f"{D}/tables_generated.md"):
    m = re.match(r"## (\w+)", line)
    if m:
        cur = m.group(1); tables[cur] = []
    elif cur:
        tables[cur].append(line)
tables = {k: "".join(v).strip() for k, v in tables.items()}
e = 1e-9
Im = I[~I.scen.str.startswith("R")]
X = M[M.method.str.startswith("X") & ~M.scen.str.startswith("R")]
G = M[~M.method.str.startswith("X") & ~M.method.str.startswith("9") & ~M.scen.str.startswith("R")]
R = M[M.scen.str.startswith("R") & (M.method == "8_opt_adaptive_worst")].groupby("scen").wrong_det_c.mean()
def gm(meth, col, df=X): return df[df.method == meth][col].mean()
def f3(x): return f"{round(float(x) + 1e-12, 3):.3f}"
P = dict(
    N_INST=len(Im), N_SCEN=Im.scen.nunique(),
    HAND_PASS=int((H.status == "PASS").sum()), HAND_N=len(H),
    MILP_EQ=int((abs(Im.x_hs_milp - Im.x_opt_batch_brute) < e).sum()),
    MILP9A_EQ=int(((abs(Im.x_hs_milp - Im.x_opt_batch_brute) < e) & (abs(Im.x_opt_batch_brute - Im.cont_batch) < e)).sum()),
    X8_9B=int((abs(Im.x_opt_adaptive_worst - Im.cont_adaptive_worst) < e).sum()),
    G8_9B=int((abs(Im.opt_adaptive_worst - Im.cont_adaptive_worst) < e).sum()),
    BATCH_GT=int((Im.x_opt_batch_brute > Im.x_opt_adaptive_worst + e).sum()),
    BATCH_GAP=f3((Im.x_opt_batch_brute - Im.x_opt_adaptive_worst).mean()),
    AXP_LT=int((Im.x_axp_lb < Im.x_opt_adaptive_worst - e).sum()),
    AXP_LE=int((Im.x_axp_lb <= Im.x_opt_adaptive_worst + e).sum()),
    UNDET_C=f3(Im.undet_frac_cont.mean()), UNDET_G=f3(Im.undet_frac_grid.mean()),
    UNDET_P0=f3(Im[Im.scen == "P0"].undet_frac_cont.mean()), UNDET_P6=f3(Im[Im.scen == "P6"].undet_frac_cont.mean()),
    EC2_GAP=f3(gm("XEC2_unif", "gap_worst")), EC2_OPT=f3(gm("XEC2_unif", "gap_worst", X.assign(gap_worst=(X.gap_worst.abs() < e).astype(float)))),
    GR_GAP=f3(gm("X3_greedy_count", "gap_worst")), RND_GAP=f3(gm("X1_random", "gap_worst")),
    HS_GAP=f3(gm("X6b_hs_ordered", "gap_worst")),
    E8E_WGAP=f3(gm("X8e_opt_expected_unif", "gap_worst")), E8_EGAP=f3(gm("X8_opt_adaptive_worst", "gap_exp_u")),
    EC2_EGAP=f3(gm("XEC2_unif", "gap_exp_u")),
    REG_GAP=f3(gm("5_minimax_regret", "gap_worst", G)), VOI_GAP=f3(gm("4_voi_unif", "gap_worst", G)),
    REG_EGAP=f3(gm("5_minimax_regret", "gap_exp_u", G)), VOI_EGAP=f3(gm("4_voi_unif", "gap_exp_u", G)),
    NAIVE_WD=f3(gm("0_naive_point", "wrong_det_u", G)), NAIVE_WDC=f3(gm("0_naive_point", "wrong_det_c", G)),
    G8_WDC=f3(gm("8_opt_adaptive_worst", "wrong_det_c", G)),
    G8_WDC_N=int((G[G.method == "8_opt_adaptive_worst"].wrong_det_c > e).sum()),
    R5=f3(R.get("R5", np.nan)), R10=f3(R.get("R10", np.nan)), R20=f3(R.get("R20", np.nan)), R40=f3(R.get("R40", np.nan)),
    BATCH_OVER=f3(gm("X6a_hs_batch", "exp_cost_u") - gm("X6b_hs_ordered", "exp_cost_u")),
    CERT_N=int(V.cert_checked), CERT_V=int(V.cert_viol), UND_N=int(V.undet_total), UND_F=int(V.undet_found),
    MUT_N=int(V.mut_tried), MUT_D=int(V.mut_detected),
    SING=int(S.all_singleton.sum()), SING_N=len(S),
    SING_B=int(S[S.scen == "BUNDLE"].all_singleton.sum()), MAXSZ_B=int(S[S.scen == "BUNDLE"].max_size.max()),
    DP9_T=f3(SC[SC.n == 9].t_dp.mean()), DP9_S=int(SC[SC.n == 9].dp_states.mean()),
    T9B9=f3(SC[SC.n == 9].t_9b.mean()), MILP12=f3(SC[SC.n == 12].t_milp.mean()),
    P0_GAP=f3((Im[Im.scen == "P0"].x_opt_batch_brute - Im[Im.scen == "P0"].x_opt_adaptive_worst).mean()),
)
tmpl = open(f"{D}/report_template.md").read()
for k, v in tables.items():
    tmpl = tmpl.replace("{{TABLE:" + k + "}}", v)
hand = H[["case", "status", "exp_adaptive", "got_adaptive", "exp_batch", "got_batch", "exp_axp", "got_axp",
          "exp_cont_adaptive", "got_cont_adaptive", "exp_cont_batch", "got_cont_batch"]]
lines = ["| " + " | ".join(hand.columns) + " |", "|" + "---|" * len(hand.columns)]
for _, r in hand.iterrows():
    lines.append("| " + " | ".join(str(x) for x in r.values) + " |")
tmpl = tmpl.replace("{{TABLE:hand}}", "\n".join(lines))
for k, v in P.items():
    tmpl = tmpl.replace("{{" + k + "}}", str(v))
left = re.findall(r"\{\{[^}]+\}\}", tmpl)
assert not left, left
open(f"{D}/C_MDQ_REPORT.md", "w").write(tmpl)
print("report written; placeholders:", len(P))
