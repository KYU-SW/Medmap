"""SELECT_SMOKE summary.json → 예비 평가 표(md). 숫자는 전부 파일에서 생성. EXPLORATORY — 판정·τ 선택 금지.
사용: python report_smoke.py --run <outputs/smoke_*> --out <md>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def f(x, pct=True):
    if x is None:
        return "-"
    return f"{x*100:.1f}" if pct else f"{x:.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = json.loads(Path(a.run, "summary.json").read_text(encoding="utf-8"))
    m, rows = d["meta"], d["rows"]
    sr = m["split_report"]
    L = [f"# SELECT_SMOKE 예비 평가 — {Path(a.run).name}", "",
         "**EXPLORATORY: 판정·τ 선택·통계적 성공에 쓰지 않음. 무잡음 폐쇄세계 DDXPlus 시뮬레이션, 임상 성능 아님.**", "",
         "## 실행 점검", "",
         f"- 기록 {m['n_records']:,}개, {m['elapsed_s']} s, 피크 RSS {m['peak_rss_mb']:.0f} MB",
         f"- 분할: TRAIN16 {sr['train_rows']:,} / SELECT {sr['select_rows']:,} / FINAL {sr['final_rows']:,}, "
         f"holdout SHA {sr['holdout_row_index_sha256'][:12]}… (STEP16B 기대값 대조 통과 시에만 진행됨)",
         f"- FINAL 프로필이 TRAIN16 에 있는 비율 {sr['final_profile_in_train16_rate']*100:.1f}%, SELECT 에 있는 비율 "
         f"{sr['final_profile_in_select_rate']*100:.1f}% (FINAL 은 라벨 개수 외 미평가)",
         f"- Baseline A 재현 대조: {m['baseline_a_repro']}",
         f"- 관계 유형 간선: {m['relation_counts']}",
         f"- 숨은 기록 누출 위반 합계: {sum(r['leak_violations'] for r in rows)}", ""]
    for Q in m["budgets"]:
        L += [f"## 질문 예산 Q={Q}", "",
              "| 모델 | WD | seed | τ | n | Top-1 | Top-3 | Top-5 | 재현율@8 | 중증 n | 중증 누락 | 잘못된 분기 종료(τ별) | 평균 질문 | ms p50 | ms p95 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        order = {"A": 0, "B": 1, "C": 2, "PA": 3, "PB_REL": 4, "PB": 5, "PC": 6}
        for r in sorted((r for r in rows if r["budget"] == Q),
                        key=lambda r: (order[r["model"]], str(r["wd_mode"]), str(r["seed"]), str(r["tau"]))):
            wt = ", ".join(f"{k}:{f(v)}" for k, v in r["wrong_term_by_tau"].items() if v is not None) or "-"
            L.append(f"| {r['model']} | {r['wd_mode'] or '-'} | {r['seed'] or '-'} | {r['tau'] or '-'} | {r['n']} | "
                     f"{f(r['top1'])} | {f(r['top3'])} | {f(r['top5'])} | {f(r['recall8'])} | {r['severe_n']} | "
                     f"{f(r['severe_miss'])} | {wt} | {r['mean_questions']:.2f} | {r['ms_p50']:.1f} | {r['ms_p95']:.1f} |")
        L.append("")
    L.append("단위: Top-k·재현율·누락·종료율은 %, 시간은 ms(사례당, 누출 검사 재실행 제외 1회 실행 기준).")
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
