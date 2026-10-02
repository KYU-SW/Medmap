"""쉼 전수 기록(서버 로그 `event=pause`) → 완결 등급별 쉼 길이 분포 표. **값을 정하지 않는다**(Adaptive 결정용 데이터만).

행: 등급(cls_cand 우선, 후보가 없으면 cls_partial) · 쉼 수 · 발화 안 쉼(resumed=1) 수 · 발화 끝(resumed=0, censored) 수
    · 재개된 쉼 길이 p50/p90/p95/max(ms) · 그 등급에서 "이 길이 이상 쉬었다가 다시 말한 비율"(t = 300/350/400/450/500/600)
해석 예: complete 등급에서 재개된 쉼 p95 가 250 ms 면, 그보다 긴 대기는 complete 발화를 자를 위험이 작다는 근거가 된다.

실행: ~/ai_env/bin/python scripts/stt_pause_census.py <server_1500.log> [...]
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict

LINE = re.compile(r"event=pause dur_ms=(\d+) resumed=([01]) censored=([01]) silence_ms=(\d+) cls_partial=([a-z]+)/(\S+) "
                  r"cls_cand=([a-z]+) stable=(-?\d) cand_ready_ms=(-?[\d.]+)")
CUTS = (300, 350, 400, 450, 500, 600)


def parse(lines):
    out = []
    for line in lines:
        m = LINE.search(line)
        if m:
            dur, resumed, censored, silence, cp, reason, cc, stable, ready = m.groups()
            out.append({"dur": int(dur), "resumed": resumed == "1", "censored": censored == "1", "silence_ms": int(silence),
                        "cls_partial": cp, "reason_partial": reason, "cls_cand": cc, "stable": int(stable), "ready": float(ready)})
    return out


def q(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, int(round((len(s) - 1) * p)))]


def table(rows, min_ms: int = 96):
    """min_ms 미만(단어 사이 틈, predecode 시작 전)은 표에서 빼고 개수만 적는다."""
    groups = defaultdict(list)
    excluded = sum(r["dur"] < min_ms and r["resumed"] for r in rows)
    rows = [r for r in rows if not (r["dur"] < min_ms and r["resumed"])]
    for r in rows:
        groups[r["cls_cand"] if r["cls_cand"] != "none" else r["cls_partial"]].append(r)
    lines = [f"excluded_below_{min_ms}ms={excluded}", "class\tpauses\tresumed\tturn_end\tres_p50\tres_p90\tres_p95\tres_max\t" + "\t".join(f"resume_after>={c}" for c in CUTS)
             + "\tstable_rate\tcand_ready_p50\tcand_ready_p95"]
    for cls in sorted(groups):
        g = groups[cls]
        res = [r["dur"] for r in g if r["resumed"]]
        stable = [r["stable"] for r in g if r["stable"] >= 0]
        ready = [r["ready"] for r in g if r["ready"] >= 0]
        cells = [cls, len(g), len(res), sum(not r["resumed"] for r in g), q(res, .5), q(res, .9), q(res, .95), max(res) if res else None]
        cells += [f"{sum(d >= c for d in res)}/{len(g)}" for c in CUTS]
        cells += [round(sum(stable) / len(stable), 3) if stable else None, q(ready, .5), q(ready, .95)]
        lines.append("\t".join(str(c) for c in cells))
    return "\n".join(lines)


if __name__ == "__main__":
    rows = []
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8", errors="replace") as f:
            rows += parse(f)
    print(f"pauses={len(rows)} files={len(sys.argv) - 1}")
    print(table(rows))
