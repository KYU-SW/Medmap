"""병렬화 점검 요약(2026-10-28) — parallel_check/<ts>/ 의 JSON 에서 숫자를 읽어 markdown 표를 만든다(손으로 숫자 쓰지 않음).

사용: ~/ai_env/bin/python par_summary.py --equiv <equiv.json> --perf <perf.json> --scale <scale.json>
      --mutation <mutation.json> [--mutation-rerun <json>] --out <md>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SELECT_N = 102_460


def main():
    ap = argparse.ArgumentParser()
    for k in ("equiv", "perf", "scale", "mutation", "out"):
        ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--mutation-rerun", default=None)
    a = ap.parse_args()
    eq, pf, sc, mu = (json.loads(Path(getattr(a, k)).read_text(encoding="utf-8"))
                      for k in ("equiv", "perf", "scale", "mutation"))
    L = ["# EXP-01 병렬화 점검 요약(가상 환자, 자동 생성)", "",
         f"원자료: `{a.equiv}`, `{a.perf}`, `{a.scale}`, `{a.mutation}`", "",
         "## 1. 직렬·병렬 동일성", "",
         f"- 세계: {eq['world']}, 사례 {eq['n_cases']}, 기록 {eq['n_records']}, 판정 **{eq['VERDICT']}**",
         f"- BLAS 스레드 환경: {eq['env_threads']}",
         f"- 경로 통과량: {json.dumps(eq['coverage'], ensure_ascii=False)}", "",
         "| 작업자 | 기록 불일치 | 실수 최대 abs 차 | 추적 동일 | 카운터 동일 | 사례 ID 동일 | τ 선택 동일 | 확인적 분석 동일 | per_case(ms 제외) | metrics(ms 제외) | subgroups | graph_stats | ms 다른 기록 수 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for w, r in eq["runs"].items():
        o = r["outputs"]
        L.append(f"| {w} | {len(r['record_mismatches'])} | {max(r['float_max_abs_diff'].values())} | {r['traces_identical']} | "
                 f"{r['counters_identical']} | {r['case_ids_identical']} | {r['tau_selection_identical']} | "
                 f"{r['confirmatory_identical']} | {o['per_case_identical_except_ms']} | {o['metrics_identical_except_ms']} | "
                 f"{o['subgroups.csv']} | {o['graph_stats.json']} | {r['ms_values_differ']} |")
    L += ["", f"- 직렬 τ 선택(가상 세계, 의미 없음 — 동일성 확인용): {json.dumps(eq['serial_tau_selection'], ensure_ascii=False)}",
          "", "## 2. 실행시간·메모리(가상 환자, 같은 머신)", "",
          f"사례 {pf['n_cases']}, 논리 CPU {pf['cpu_logical']}", "",
          "| 조건 | 벽시계 s | 사례/s | s/사례 | 직렬 대비 배속 | 병렬 효율 | 부모 RSS MB | 작업자 PSS 합 MB | 작업자 RSS 합 MB | 시스템 사용 증가 MB |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for k, r in pf["runs"].items():
        m = r["mem_peak"]
        L.append(f"| {k} | {r['wall_s']} | {r['cases_per_s']} | {r['s_per_case']} | {r['speedup_vs_serial']} | "
                 f"{r.get('parallel_efficiency', '-')} | {m['parent_rss_mb']} | {m['children_pss_mb']} | {m['children_rss_mb']} | "
                 f"{m['system_used_delta_mb']} |")
    L += ["", "### SELECT 전체 예상(측정 × 가정)", "",
          "| 조건 | 측정 s/사례(가상) | 가정: 실제 사례 비용 = 가상과 같음 → 평가 시간 h |", "|---|---|---|"]
    for k, r in pf["runs"].items():
        L.append(f"| {k} | {r['s_per_case']} | {round(r['s_per_case'] * SELECT_N / 3600, 2)} |")
    L += ["", "가정: 실제 DDXPlus 사례의 사례당 비용이 가상 환자와 같다(측정 아님). 데이터 적재·집계 시간 별도.", "",
          "## 3. SELECT 전체 규모 집계 메모리(가상 기록 복제)", "",
          f"- 기록 {sc['records']}(사례 {sc['target_cases']} × {sc['records_per_case']})",
          f"- 열 단위 표 구성 최대: {json.dumps(sc['build_mem_peak'])}",
          f"- 산출물 쓰기(write_all) {sc['write_all_s']} s, 최대: {json.dumps(sc['write_all_mem_peak'])}",
          f"- per_case.parquet {sc['per_case_parquet_mb']} MB",
          f"- 확인적 분석(B={sc['confirm_B']}) {sc['confirm_s']} s, 최대: {json.dumps(sc['confirm_mem_peak'])}",
          f"- 프로세스 최대 RSS {sc['process_peak_rss_mb']} MB", "",
          "## 4. 변이 검사", "", f"- 1차: {mu['killed']}/{mu['total']} 검출, 깨끗한 코드 rc={mu['clean_suite_rc']}", "",
          "| 변이 | 상태 | 비고 |", "|---|---|---|"]
    for r in mu["mutants"]:
        L.append(f"| {r['mutant']} | {r['status']} | {r.get('note') or ''} |")
    if a.mutation_rerun:
        rr = json.loads(Path(a.mutation_rerun).read_text(encoding="utf-8"))
        L += ["", f"- 생존 변이 테스트 보강 후 재검사: {rr['killed']}/{rr['total']} 검출, 깨끗한 코드 rc={rr['clean_suite_rc']}", "",
              "| 변이 | 상태 | 비고 |", "|---|---|---|"]
        for r in rr["mutants"]:
            L.append(f"| {r['mutant']} | {r['status']} | {r.get('note') or ''} |")
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"WROTE {a.out}")


if __name__ == "__main__":
    main()
