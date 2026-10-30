"""STEP28.5 속도·메모리(CPU, single input). 입력 = Silver 442 원문(순서 고정), warm-up 20. 모드별 Retriever.run.
일관성: PARALLEL live 범주 == data/retrieval_results.csv(assert). 출력: outputs/latency.json
"""
import resource
import statistics
import time

import s285_common as S


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
    from bilingual_retriever import Retriever
    from extract_symptom_spans import extract_kiwi
    R = Retriever()
    extract_kiwi("워밍업")
    load = time.perf_counter() - t
    texts = list(dict.fromkeys(r["input"] for r in S.read_csv(S.DATA / "retrieval_results.csv")))
    res = {"SPAN_EXTRACTION": None}
    for name, fn in (("SPAN_EXTRACTION", extract_kiwi), ("KO_ONLY", lambda x: R.run(x, "KO_ONLY")), ("EN_ONLY", lambda x: R.run(x, "EN_ONLY")),
                     ("PARALLEL", lambda x: R.run(x, "PARALLEL"))):
        for x in texts[:20]:
            fn(x)
        ms = []
        for x in texts:
            t0 = time.perf_counter()
            fn(x)
            ms.append((time.perf_counter() - t0) * 1000)
        res[name] = stats(ms)
    ref = {}
    for r in S.read_csv(S.DATA / "retrieval_results.csv"):
        if r["mode"] == "PARALLEL":
            ref.setdefault(r["input"], []).append(r["category"])
    mism = [x for x in texts if [o["category"] for o in R.run(x, "PARALLEL")] != ref[x]]
    assert not mism, f"live ≠ 저장 {len(mism)}: {mism[:3]}"
    out = {"single_input_cpu": res, "n_inputs": len(texts), "pipeline_load_seconds": round(load, 2), "rss_before_mib": r0, "rss_after_load_mib": rss(),
           "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
           "korean_index_bytes": (S.INDEX / "korean_index.csv").stat().st_size + (S.INDEX / "korean_ngram.joblib").stat().st_size,
           "bilingual_links_bytes": (S.INDEX / "bilingual_links.csv").stat().st_size, "ontology_index_bytes": S.ONT_DB.stat().st_size,
           "model_path_enabled": R.model_path, "consistency": f"PASS(0/{len(texts)})", "omp_num_threads": __import__("os").environ.get("OMP_NUM_THREADS")}
    S.dump_json(S.OUT / "latency.json", out)
    print(S.dumps(out))


if __name__ == "__main__":
    main()
