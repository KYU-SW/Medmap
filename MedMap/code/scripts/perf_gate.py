"""M6 성능 회귀 gate(REALTIME_FIRST): 실시간 루프 지연·품질을 baseline 과 비교해 회귀를 막는다(기능 PASS 와 별개).

입력 = 브라우저 e2e 결과(숫자만): realtime-stt.e2e.mjs 의 e2e_main.json(T_partial·T_final_vad·T_final·T_prep·CER, WS/HTTP),
doctor-latency.e2e.mjs 의 rt_m5_tnext.json(T_next). 서버 단독 bench 는 아직 없음(계획서 Task 16 — GPU 필요, 후속).

규칙(p95 기준, 목표는 낮추지 않는다):
- 회귀: current > baseline × (1 + REL_TOL) 이고 증가량 > ABS_SLACK_MS  (작은 지표의 잡음 오판 방지)
- 목표 초과: current > target 인데 baseline 은 목표 안 → 회귀(TARGET_MISS)
- 알려진 미달: baseline 도 목표 초과 → known_target_miss 로 표시만(더 나빠지면 위 회귀 규칙으로 걸림)
- 품질: CER 이 baseline 보다 CER_TOL 넘게 나빠지면 회귀
- 측정 시작 시 GPU 경합(util > 30 %)이면 비교 거부(INVALID_CONTENDED) · baseline 지표가 current 에 없으면 회귀(missing)

사용:
  python scripts/perf_gate.py collect --e2e <e2e_main.json> --doctor <rt_m5_tnext.json> --gpu-start <vram_0_idle.txt>
                                      --commit-stt <sha> --commit-doctor <sha> --out exp/perf_baseline/<date>_realtime.json
  python scripts/perf_gate.py compare --baseline <baseline.json> --current <current.json>
종료 코드: 0 PERF_OK · 2 PERF_REGRESSION · 3 INVALID_CONTENDED
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REL_TOL = 0.20
ABS_SLACK_MS = 10.0
CER_TOL = 0.01
CONTENDED_GPU_UTIL = 30
TARGETS = {"T_partial": 600, "T_final_vad": 500, "T_final": 500}
EXIT = {"PERF_OK": 0, "PERF_REGRESSION": 2, "INVALID_CONTENDED": 3}


def _lat(block: dict, key: str, target: int | None) -> dict | None:
    value = block.get(key) if block else None
    if not value or value.get("p95") is None:
        return None
    return {"kind": "latency_ms", "p50": value.get("p50"), "p95": value["p95"], "n": value.get("n"), "target": target}


def collect(e2e: dict, doctor: dict, conditions: dict) -> dict:
    metrics = {}
    summary = e2e.get("summary", {})
    for transport, block in (("ws", summary.get("ws_warm")), ("http", summary.get("http"))):
        for key, name in (("T_partial_ms", "T_partial"), ("T_final_vad_ms", "T_final_vad"), ("T_final_ms", "T_final")):
            item = _lat(block, key, TARGETS[name])
            if item:
                metrics[f"stt.{transport}.{name}"] = item
        if block and block.get("cer", {}).get("mean") is not None:
            metrics[f"stt.{transport}.cer"] = {"kind": "quality", "mean": block["cer"]["mean"], "max": block["cer"].get("max")}
    prep = _lat(summary.get("ws_warm"), "T_prep_ms", 300)
    if prep:
        metrics["intake.T_prep"] = prep
    tnext = _lat(doctor.get("summary", {}).get("warm"), "T_next", 500)
    if tnext:
        metrics["doctor.T_next_warm"] = tnext
    util = conditions.get("gpu_util_start")
    return {"schema": "medmap-perf-baseline-v1", "metrics": metrics,
            "conditions": {**conditions, "contended": util is not None and util > CONTENDED_GPU_UTIL},
            "rules": {"rel_tol": REL_TOL, "abs_slack_ms": ABS_SLACK_MS, "cer_tol": CER_TOL}}


def compare(baseline: dict, current: dict) -> dict:
    if current.get("conditions", {}).get("contended"):
        return {"status": "INVALID_CONTENDED", "detail": current["conditions"]}
    out = {"regressions": {}, "target_miss": {}, "known_target_miss": {}, "missing": [], "ok": []}
    for name, base in baseline["metrics"].items():
        cur = current["metrics"].get(name)
        if cur is None:
            out["missing"].append(name)
            continue
        if base["kind"] == "quality":
            if cur["mean"] - base["mean"] > CER_TOL:
                out["regressions"][name] = {"baseline": base["mean"], "current": cur["mean"]}
            else:
                out["ok"].append(name)
            continue
        b, c, target = base["p95"], cur["p95"], base.get("target")
        bad = False
        if c > b * (1 + REL_TOL) and c - b > ABS_SLACK_MS:
            out["regressions"][name] = {"baseline_p95": b, "current_p95": c}
            bad = True
        if target is not None and c > target:
            if b > target:
                out["known_target_miss"][name] = {"baseline_p95": b, "current_p95": c, "target": target}
            else:
                out["target_miss"][name] = {"baseline_p95": b, "current_p95": c, "target": target}
                bad = True
        if not bad:
            out["ok"].append(name)
    failed = out["regressions"] or out["target_miss"] or out["missing"]
    out["status"] = "PERF_REGRESSION" if failed else "PERF_OK"
    return out


def _gpu_util(path: str | None) -> int | None:
    if not path:
        return None
    first = Path(path).read_text().strip().split(",")[0]
    return int(float(first))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--e2e", required=True)
    c.add_argument("--doctor", required=True)
    c.add_argument("--gpu-start")
    c.add_argument("--commit-stt", default="")
    c.add_argument("--commit-doctor", default="")
    c.add_argument("--note", default="")
    c.add_argument("--out", required=True)
    k = sub.add_parser("compare")
    k.add_argument("--baseline", required=True)
    k.add_argument("--current", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "collect":
        conditions = {"gpu_util_start": _gpu_util(args.gpu_start), "commit_stt": args.commit_stt,
                      "commit_doctor": args.commit_doctor, "source_e2e": args.e2e, "source_doctor": args.doctor, "note": args.note}
        result = collect(json.loads(Path(args.e2e).read_text()), json.loads(Path(args.doctor).read_text()), conditions)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
        print(f"baseline metrics={len(result['metrics'])} contended={result['conditions']['contended']} out={args.out}")
        return 0
    verdict = compare(json.loads(Path(args.baseline).read_text()), json.loads(Path(args.current).read_text()))
    print(json.dumps(verdict, ensure_ascii=False, indent=1))
    print(verdict["status"])
    return EXIT[verdict["status"]]


if __name__ == "__main__":
    sys.exit(main())
