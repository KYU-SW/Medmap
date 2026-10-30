"""STEP28.8 CPU 지연·메모리 — P5 경로만(수정 KO + 정제표 + 보류 + 구별 차단), 단일 입력 warm, SILVER442 순서. p 위치 = int(round(q·(n−1))).
출력: outputs/latency.json"""
import os
import time

import s288_common as S
from policies import PolicyEngine


def rss():
    d = {}
    for ln in open("/proc/self/status"):
        if ln.startswith(("VmRSS", "VmHWM")):
            d[ln.split(":")[0]] = round(int(ln.split()[1]) / 1024, 1)
    return d


def main():
    r0 = rss()
    t0 = time.perf_counter()
    E = PolicyEngine()
    load = time.perf_counter() - t0
    E.R.ko_mode = "repaired"

    def p5(t):
        rep = E.R.run(t, "KO_ONLY")
        out = []
        for o in rep:
            ks = E.keys(t, o, len(rep))
            r = E.combine(t, o, E.clean.lookup(ks), "P5")
            out.append(E.apply_distinct(E.apply_held(r, o, ks), ks))
        return out
    sil = [r["raw_expression"] for r in S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv")]
    for t in sil[:20]:
        p5(t)
    ms = []
    for t in sil:
        a = time.perf_counter()
        p5(t)
        ms.append((time.perf_counter() - a) * 1000)
    ms.sort()
    q = lambda x: round(ms[int(round(x * (len(ms) - 1)))], 3)  # noqa: E731
    out = {"single_input_cpu": {"P5": {"n": len(ms), "p50_ms": q(0.5), "p95_ms": q(0.95), "max_ms": round(ms[-1], 3), "mean_ms": round(sum(ms) / len(ms), 3)}},
           "pipeline_load_seconds": round(load, 2), "rss_before_mib": r0.get("VmRSS"), "peak_rss_mib": rss().get("VmHWM"),
           "omp_num_threads": os.environ.get("OMP_NUM_THREADS"), "gpu": "사용 안 함"}
    S.dump_json(S.OUT / "latency.json", out)
    print(S.dumps(out))


if __name__ == "__main__":
    main()
