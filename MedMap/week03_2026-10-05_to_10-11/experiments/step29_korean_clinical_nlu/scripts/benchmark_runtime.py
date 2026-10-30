"""STEP29 CPU 지연·메모리 — NLU_P5 단일 입력(P5 메모 끔), pilot_gold 274 문장, warm-up 20. p 위치 = int(round(q·(n−1))). 출력: outputs/latency.json"""
import os
import time

import p5_normalizer_adapter as A
import s29_common as S
from clinical_nlu_pipeline import analyze


def rss():
    d = {}
    for ln in open("/proc/self/status"):
        if ln.startswith(("VmRSS", "VmHWM")):
            d[ln.split(":")[0]] = round(int(ln.split()[1]) / 1024, 1)
    return d


def main():
    A.USE_CACHE = False
    t0 = time.perf_counter()
    A.engine()
    load = time.perf_counter() - t0
    texts = [r["text_ko"] for r in S.read_csv(S.S21_DIR / "data/pilot_gold.csv")]
    for t in texts[:20]:
        analyze(t, "NLU_P5")
    res = {}
    for L in ("NLU_P0", "NLU_P5"):
        ms = []
        for t in texts:
            a = time.perf_counter()
            analyze(t, L)
            ms.append((time.perf_counter() - a) * 1000)
        ms.sort()
        q = lambda x: round(ms[int(round(x * (len(ms) - 1)))], 3)  # noqa: E731
        res[L] = {"n": len(ms), "p50_ms": q(0.5), "p95_ms": q(0.95), "max_ms": round(ms[-1], 3)}
    out = {"single_input_cpu": res, "pipeline_load_seconds": round(load, 2), "peak_rss_mib": rss().get("VmHWM"), "omp_num_threads": os.environ.get("OMP_NUM_THREADS"), "gpu": "사용 안 함"}
    S.dump_json(S.OUT / "latency.json", out)
    print(S.dumps(out))


if __name__ == "__main__":
    main()
