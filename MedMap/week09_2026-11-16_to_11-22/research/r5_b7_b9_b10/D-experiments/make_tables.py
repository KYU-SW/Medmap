"""[합성] 결과 CSV -> report_tables.md (보고서 숫자는 모두 이 파일에서 계산된 값)."""
import os, json
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda f: pd.read_csv(os.path.join(HERE, f))


def md(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if pd.isna(r[c]) else str(r[c]) for c in cols) + " |")
    return "\n".join(out)


def main():
    L = ["# report_tables (자동 생성, [합성] 실험)\n"]
    ov = R("results_summary_overall.csv")
    L.append("## 전체(손 사례·정답없음 제외)\n" + md(ov[["method", "n", "label_ok", "state_ok", "full_ok", "wrong_confirm", "hold_set_ok",
                                                   "gap_distinction_acc", "ewas_ok", "app_ok", "rule_ok", "F1_states", "F2_states", "F3",
                                                   "F4_states", "F5", "time_median_s", "time_max_s", "mem_peak_max_bytes"]]))
    ex = R("results_summary_by_exp.csv")
    L.append("\n## 실험별 full_ok (라벨+상태별 조건 함수 일치)\n" + md(ex.pivot(index="exp", columns="method", values="full_ok").reset_index()))
    L.append("\n## 실험별 label_ok\n" + md(ex.pivot(index="exp", columns="method", values="label_ok").reset_index()))
    L.append("\n## 실험별 ewas_ok (∃w∀s)\n" + md(ex.pivot(index="exp", columns="method", values="ewas_ok").reset_index()))
    L.append("\n## 실험별 wrong_confirm\n" + md(ex.pivot(index="exp", columns="method", values="wrong_confirm").reset_index()))
    L.append("\n## 실험별 시간 중앙값(s)\n" + md(ex.pivot(index="exp", columns="method", values="time_median_s").reset_index()))
    pi = R("results_per_instance.csv")
    pe = pi[(pi.exp == "E5") & (pi.nogt == 0)].groupby(["level", "method"]).full_ok.mean().round(3).unstack().reset_index()
    L.append("\n## E5 결측 수준별 full_ok\n" + md(pe))
    pe = pi[(pi.exp == "E6") & (pi.nogt == 0)].groupby(["level", "method"]).full_ok.mean().round(3).unstack().reset_index()
    L.append("\n## E6 선호 범위 r 별 full_ok\n" + md(pe))
    pe = pi[(pi.exp == "E7") & (pi.nogt == 0)].groupby(["level", "method"]).full_ok.mean().round(3).unstack().reset_index()
    L.append("\n## E7 근거 정보 수준별 full_ok (0:항목100%/공유0, 1:90%/0, 2:90%/공유100%, 3:60%/공유100%)\n" + md(pe))
    pe = pi[(pi.exp == "E8")].groupby(["family", "method"]).time_s.median().round(4).unstack().reset_index()
    L.append("\n## E8 지침 수별 시간 중앙값(s)\n" + md(pe))
    gtd = pi[pi.method == "B_joint"].groupby(["exp", "gt_final"]).size().unstack(fill_value=0).reset_index()
    L.append("\n## 정답 라벨 분포\n" + md(gtd))
    L.append("\n## 손 사례\n" + md(R("results_cases.csv")))
    L.append("\n## 안정성\n" + md(R("results_stability.csv")))
    bb = R("results_bvsbp.csv")
    L.append("\n## B vs B' 차이 원인 집계\n" + md(bb.groupby(["cause"]).size().reset_index(name="count")))
    L.append("\n## B vs B' 차이(실험별)\n" + md(bb.groupby(["exp", "cause"]).size().reset_index(name="count")))
    mc = R("results_milp_check.csv")
    L.append("\n## B_milp 대조\n" + f"n={len(mc)}, ewas_ok={mc.ewas_ok.sum()}, app_ok={mc.app_ok.sum()}, 비어있지 않은 정답 EWAS={int((mc.gt_ewas_size>0).sum())}, 시간 중앙값={mc.time_s.median():.4f}s 최대={mc.time_s.max():.4f}s")
    sc = R("results_scaling_e8b.csv")
    g = sc.groupby("n_unknown").agg(t_milp_med=("t_milp_s", "median"), t_B_enum_med=("t_B_enum_s", "median"),
                                    t_gt_med=("t_gt_s", "median"), B_agree=("B_agree", "sum"), gt_agree_milp=("gt_agree_milp", "sum")).reset_index()
    L.append("\n## E8b 확장성(미확인 변수 수)\n" + md(g.round(4)))
    s = json.load(open(os.path.join(HERE, "results_situations.json")))
    L.append("\n## 상황 분류\n" + "\n".join(f"- {k}: {v['count'] if isinstance(v, dict) and 'count' in v else v}" for k, v in s.items() if k != "freeze_manifest"))
    open(os.path.join(HERE, "report_tables.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
