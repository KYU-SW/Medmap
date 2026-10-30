"""STEP29.3 §16 처리 시간·메모리. 모든 메모(P5·v3 core·core3·B4 특징) 끔. 단일 입력 순차, warm-up 20.
 조건 A(저부하): 측정 직전 1분 load average 기록, 다른 작업이 있으면 그대로 두고 값만 기록(강제 종료 없음).
 조건 B(동시 부하): 측정 동안 이 스크립트가 CPU 바쁜 루프 프로세스 2개를 띄워 개발 환경 동시 작업을 흉내(측정 뒤 종료).
 입력: pilot 274(STEP29.1·29.2 와 같은 입력) · DEV29_3 222. 정책: R0(STEP29.2 V3_B0) · 선택 정책.
 단계별(조건 A, pilot 274): P5 단독(문장 전체 p5) · 전체 NLU core3 · STEP29.3 검색 계층만(CPR.apply + B4 정책, core3 결과 위) · 요청당 전체 analyze.
 초기 로딩: P5 엔진(B4 라우터·KoELECTRA 포함) 첫 생성 시간. 메모리: 프로세스 최대 RSS(VmHWM).
출력: outputs/latency.json · outputs/memory.json"""
import multiprocessing as mp
import os
import time

import s293_common as S


def rss():
    for ln in open("/proc/self/status"):
        if ln.startswith("VmHWM"):
            return round(int(ln.split()[1]) / 1024, 1)


def burn(stop):
    x = 0
    while not stop.is_set():
        x = (x * 31 + 7) % 1000003


def q(ms):
    ms = sorted(ms)
    f = lambda p: round(ms[int(round(p * (len(ms) - 1)))], 3)  # noqa: E731
    return {"n": len(ms), "p50_ms": f(0.5), "p95_ms": f(0.95), "max_ms": round(ms[-1], 3)}


def run(fn, texts):
    out = []
    for t in texts:
        a = time.perf_counter()
        fn(t)
        out.append((time.perf_counter() - a) * 1000)
    return q(out)


def main():
    t0 = time.perf_counter()
    import b4_evidence_guard as B4G
    import b4_evidence_policy as BP
    import context_preserving_retriever as CPR
    import nlu_pipeline_v3 as V3
    import p5_normalizer_adapter as PA
    import step29_2_adapter as A
    PA.USE_CACHE = False
    V3.USE_CACHE = False
    A.USE_CACHE = False
    B4G.USE_CACHE = False
    PA.engine()
    init_ms = round((time.perf_counter() - t0) * 1000, 1)
    sel = S.load_json(S.DATA / "policy_freeze.json")["SELECTED_POLICY"]
    pilot = [r["text_ko"] for r in S.read_csv(S.S21_DIR / "data/pilot_gold.csv")]
    dev = [c["text"] for c in S.load_json(S.DATA / "development_cases.json")["cases"]]
    for t in pilot[:20]:
        A.analyze(t, sel)
    pols = ["R0"] + ([sel] if sel != "R0" else [])
    mode, b4 = A.CFG.get(sel, ("N3", "B0"))

    def layer_only(t):
        ms, _ = A.core3(t)
        a = time.perf_counter()
        for m in ms:
            BP.apply(CPR.apply(m, mode), b4)
        return (time.perf_counter() - a) * 1000

    res = {"condition_A_low_load": {"loadavg_1m_before": round(os.getloadavg()[0], 2)}}
    for name, ts in (("pilot274", pilot), ("dev29_3", dev)):
        res["condition_A_low_load"][name] = {p: run(lambda t, p=p: A.analyze(t, p), ts) for p in pols}
    res["condition_A_low_load"]["stages_pilot274"] = {"P5_only_whole_text": run(PA.p5, pilot), "core3_NLU": run(A.core3, pilot),
                                                      "step29_3_layer_only": q([layer_only(t) for t in pilot]),
                                                      "full_request_" + sel: run(lambda t: A.analyze(t, sel), pilot)}
    res["condition_A_low_load"]["loadavg_1m_after"] = round(os.getloadavg()[0], 2)
    stop = mp.Event()
    ps = [mp.Process(target=burn, args=(stop,)) for _ in range(2)]
    for p in ps:
        p.start()
    time.sleep(3)
    res["condition_B_concurrent_load"] = {"background": "이 스크립트가 띄운 CPU 바쁜 루프 2개", "loadavg_1m_during": round(os.getloadavg()[0], 2),
                                          "pilot274": {p: run(lambda t, p=p: A.analyze(t, p), pilot) for p in pols}}
    stop.set()
    for p in ps:
        p.join()
    out = {**res, "selected_policy": sel, "init_load_ms(P5 엔진·B4 라우터·KoELECTRA)": init_ms, "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
           "gpu": "사용 안 함", "repeats": "입력당 1회(순차), warm-up 20", "note": "판정 P7 = 조건 A pilot274 선택 정책 p95"}
    S.dump_json(S.OUT / "latency.json", out)
    S.dump_json(S.OUT / "memory.json", {"peak_rss_mib": rss(), "process": "benchmark_runtime(전 정책·조건 측정 후)", "selected_policy": sel})
    print(S.dumps({"A": {k: v for k, v in res["condition_A_low_load"].items() if k in ("loadavg_1m_before", "pilot274", "stages_pilot274")},
                   "B": res["condition_B_concurrent_load"], "init_ms": init_ms, "rss": rss()}))


if __name__ == "__main__":
    main()
