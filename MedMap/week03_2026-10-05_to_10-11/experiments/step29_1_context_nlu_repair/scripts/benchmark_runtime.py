"""STEP29.1 CPU 지연·메모리 — P5(v2) 단일 입력, P5 검색 메모 끔, pilot_gold 274, warm-up 20. 출력: outputs/latency.json"""
import os
import time

import s291_common as S  # 경로 먼저
import p5_normalizer_adapter as A  # noqa: E402
from nlu_pipeline_v2 import analyze


def rss():
    for ln in open("/proc/self/status"):
        if ln.startswith("VmHWM"):
            return round(int(ln.split()[1]) / 1024, 1)


def main():
    A.USE_CACHE = False
    A.engine()
    texts = [r["text_ko"] for r in S.read_csv(S.S21_DIR / "data/pilot_gold.csv")]
    for t in texts[:20]:
        analyze(t, "P5")
    res = {}
    for L in ("P1", "P5"):
        ms = []
        for t in texts:
            a = time.perf_counter()
            analyze(t, L)
            ms.append((time.perf_counter() - a) * 1000)
        ms.sort()
        q = lambda x: round(ms[int(round(x * (len(ms) - 1)))], 3)  # noqa: E731
        res[L] = {"n": len(ms), "p50_ms": q(0.5), "p95_ms": q(0.95), "max_ms": round(ms[-1], 3)}
    out = {"single_input_cpu": res, "peak_rss_mib": rss(), "omp_num_threads": os.environ.get("OMP_NUM_THREADS"), "gpu": "사용 안 함"}
    S.dump_json(S.OUT / "latency.json", out)
    print(S.dumps(out))


if __name__ == "__main__":
    main()
