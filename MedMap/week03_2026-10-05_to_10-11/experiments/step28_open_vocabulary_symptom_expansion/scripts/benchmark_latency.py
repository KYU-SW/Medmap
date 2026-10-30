"""STEP28 속도·메모리(CPU, single input). 입력 = Silver 442 원문(순서 고정), warm-up 20.
경로: STEP27_ROUTER(특징+라우팅) · PRODUCT_MAPPER(regex) · STEP28_FULL(기존 검색 + 비증상 + ontology 색인 조회 + 경로 C(활성 시)).
색인 크기·적재 시간·RSS 를 분리 기록. 일관성: live 범주 == data/external_silver_expansion.csv (assert).
출력: outputs/latency.json
"""
import resource
import statistics
import time

import s28_common as S


def rss():
    for ln in open("/proc/self/status"):
        if ln.startswith("VmRSS:"):
            return round(int(ln.split()[1]) / 1024, 1)


def stats(xs):
    xs = sorted(xs)
    return {"n": len(xs), "mean_ms": round(statistics.mean(xs), 3), "p50_ms": round(xs[len(xs) // 2], 3),
            "p95_ms": round(xs[int(round(0.95 * (len(xs) - 1)))], 3), "max_ms": round(xs[-1], 3)}


def main():
    r0 = rss()
    t = time.perf_counter()
    from evaluate_expansion import Expansion
    from safe_symptom_router import route
    ex = Expansion()
    load_s = time.perf_counter() - t
    r1 = rss()
    texts = [r["raw_expression"] for r in S.read_csv(S.DATA / "external_silver_expansion.csv")]
    paths = {"STEP27_ROUTER": lambda x: route(ex.es.router.policy, ex.es.router.features(x), ex.es.router.params),
             "PRODUCT_MAPPER": ex.es.mapper.extract, "ONTOLOGY_KOR_LOOKUP": lambda x: ex.oi.kor_lookup(S.norm(x)), "STEP28_FULL": ex}
    res = {}
    for name, fn in paths.items():
        for x in texts[:20]:
            fn(x)
        ms = []
        for x in texts:
            t0 = time.perf_counter()
            fn(x)
            ms.append((time.perf_counter() - t0) * 1000)
        res[name] = stats(ms)
    ref = {r["raw_expression"]: r["step28_category"] for r in S.read_csv(S.DATA / "external_silver_expansion.csv")}
    mism = [x for x in texts if ex(x)["category"] != ref[x]]
    assert not mism, f"live ≠ 저장 결과 {len(mism)}: {mism[:3]}"
    b = S.load_json(S.OUT / "index_build.json")
    out = {"single_input_cpu": res, "n_inputs": len(texts), "pipeline_load_seconds": round(load_s, 2), "rss_before_mib": r0, "rss_after_load_mib": r1,
           "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1), "index_bytes": b["index_bytes"],
           "index_build_seconds": b["total_seconds"], "path_c_enabled": ex.path_c, "consistency": f"PASS(0/{len(texts)})",
           "omp_num_threads": __import__("os").environ.get("OMP_NUM_THREADS")}
    S.dump_json(S.OUT / "latency.json", out)
    print(S.dumps(out))


if __name__ == "__main__":
    main()
