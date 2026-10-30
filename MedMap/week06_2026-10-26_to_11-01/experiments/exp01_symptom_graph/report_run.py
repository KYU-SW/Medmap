"""실행 산출물(metrics.csv·run_meta·split_manifest·tau_selection·graph_stats·subgroups) → 보고 표(md). 숫자는 파일에서 생성.
사용: python report_run.py --run <outputs/run_id> --out <md>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def pct(x):
    return "-" if pd.isna(x) else f"{x * 100:.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    r = Path(a.run)
    meta = json.loads((r / "run_meta.json").read_text(encoding="utf-8"))
    sm = json.loads((r / "split_manifest.json").read_text(encoding="utf-8"))
    gs = json.loads((r / "graph_stats.json").read_text(encoding="utf-8"))
    ts = json.loads((r / "tau_selection.json").read_text(encoding="utf-8")) if (r / "tau_selection.json").exists() else None
    m = pd.read_csv(r / "metrics.csv")
    sg = pd.read_csv(r / "subgroups.csv")
    L = [f"# {meta['split']} 실행 보고 — {r.name}", "", f"**{meta['note']}** 무잡음 폐쇄세계 DDXPlus 시뮬레이션, 임상 성능 아님.", "",
         "## 실행 점검", "",
         f"- 기록 {meta['n_records']:,}개, {meta['elapsed_s']} s, 피크 RSS {meta['peak_rss_mb']:.0f} MB, 패키지 {meta.get('packages')}",
         f"- 분할: TRAIN16 {sm['train_rows']:,} / SELECT {sm['select_rows']:,} / FINAL {sm['final_rows']:,}, 평가 {sm['evaluated_split']} {sm['evaluated_rows']:,}행",
         f"- 중증 질환별 n(평가 행): {sm['severe_n_by_disease']} → n≥100 질환 {sm['severe_diseases_n_ge_100']}개, TRAIN16 에 없는 프로필 {sm['novel_rows']}행",
         f"- Baseline A STEP16B 경로 재현: {meta.get('baseline_a_repro_step16b_path')}",
         f"- Baseline A 평가 경로 매 단계 대조: {meta.get('baseline_a_eval_path_checks')}회, 최대 |차| {meta.get('baseline_a_eval_path_max_abs_diff')}",
         f"- 그래프 독립 참조 점수기 대조: {meta.get('graph_reference_checks')}회",
         f"- 누출 검사: PASS {int(m['leak_checked'].sum())}, NA {int(m['leak_na'].sum())} (위반 시 실행 중단)",
         f"- 입력 SHA 확인: {meta.get('input_sha256', {}).get('verified')}, 실행 잠금 해시 {meta.get('run_lock', {}).get('lock_sha256', '-')[:12]}…, 외부 코드 clean {meta.get('run_lock', {}).get('external_clean')}",
         f"- RG: {meta.get('rg_status')}", ""]
    if ts:
        L += [f"## τ 선택 규칙 결과 ({ts['use']})", "", f"- {ts}", ""]
    L += ["## 질문 5개(Q=5), 잡음 없음 — 주 조건", "",
          "| 모델 | WD | seed | τ | n | Top-1 | Top-5 | 재현율@8 | 중증 누락 | macro Top-5 | ECE | Brier | 감별 재현율 | 음성 방향 | 가지치기 발동 | 계산 수 중앙값 | ms p50 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    order = {"A": 0, "B": 1, "C": 2, "PA": 3, "PB_REL": 4, "PB": 5, "PC": 6}
    q5 = m[(m["budget"] == 5) & m["noise"].isna()].copy()
    q5["o"] = q5["model"].map(order)
    for _, x in q5.sort_values(["o", "wd_mode", "seed", "tau"], na_position="first").iterrows():
        L.append(f"| {x['model']} | {x['wd_mode'] if pd.notna(x['wd_mode']) else '-'} | {int(x['seed']) if pd.notna(x['seed']) else '-'} | "
                 f"{x['tau'] if pd.notna(x['tau']) else '-'} | {int(x['n'])} | {pct(x['top1'])} | {pct(x['top5'])} | {pct(x['recall8'])} | "
                 f"{pct(x['severe_miss'])} | {pct(x['macro_top5'])} | {pct(x['ece_top1'])} | {x['brier']:.3f} | {pct(x['diff_recall'])} | "
                 f"{pct(x['neg_direction_rate'])} | {pct(x['prune_rate'])} | {x['counter_median'] if pd.notna(x['counter_median']) else '-'} | {x['ms_p50']:.1f} |")
    L += ["", "## 응답 잡음 민감도(Q=5, 기술 통계)", "", "| 모델 | 잡음 | Top-5 | 중증 누락 |", "|---|---|---|---|"]
    for _, x in m[m["noise"].notna()].sort_values(["model", "noise"]).iterrows():
        L.append(f"| {x['model']} | {x['noise']} | {pct(x['top5'])} | {pct(x['severe_miss'])} |")
    L += ["", "## 질문 3·10개 Top-5(잡음 없음, 주요 모델)", "", "| 모델 | Q=3 | Q=10 |", "|---|---|---|"]
    for mod in ("A", "B", "C", "PA", "PB_REL"):
        v = {q: m[(m["model"] == mod) & (m["budget"] == q) & m["noise"].isna()]["top5"] for q in (3, 10)}
        L.append(f"| {mod} | {pct(v[3].iloc[0]) if len(v[3]) else '-'} | {pct(v[10].iloc[0]) if len(v[10]) else '-'} |")
    sd = sg[(sg["dimension"] == "severe_disease") & (sg["model"].isin(["A", "C", "PA"])) & sg["wd_mode"].isna()]
    L += ["", "## 중증 질환별(Q=5, A·C·PA) — n<100 질환은 결론 보류", "", "| 모델 | 질환 | n | 누락 수 | 누락률 | Wilson 95% |", "|---|---|---|---|---|---|"]
    for _, x in sd.sort_values(["value", "model"]).iterrows():
        L.append(f"| {x['model']} | {x['value']} | {int(x['n'])} | {int(x['severe_miss_count'])} | {pct(x['severe_miss'])} | "
                 f"{pct(x['severe_miss_wilson_lo'])}–{pct(x['severe_miss_wilson_hi'])} |")
    L += ["", "## 그래프 통계", "", f"- {json.dumps(gs, ensure_ascii=False, default=str)[:1500]}", "",
          "단위: %(Brier·계산 수·ms 제외). 이 표는 EXPLORATORY 이며 판정·τ 선택에 쓰지 않는다(SELECT_SMOKE)."]
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
