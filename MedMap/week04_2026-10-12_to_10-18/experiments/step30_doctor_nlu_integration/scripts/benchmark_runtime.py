"""§14 처리 시간·메모리(CPU). STEP29.3 benchmark_runtime 과 같은 조건 우선: 모든 메모 끔, 입력당 1회 순차, warm-up 20, OMP 4,
 조건 A(저부하: 다른 작업은 그대로 두고 load average 만 기록) · 조건 B(이 스크립트가 CPU 바쁜 루프 2개를 띄움, 측정 뒤 종료).
입력: STEP21 pilot 274(STEP29.3 과 같은 입력) + STEP30 평가 82.
단계: NLU(core3) · 검색(CPR.apply + B4 정책, core3 결과 위) · 통합 어댑터(build_packet) · JSON 직렬화 · 전체(analyze R2 + build_packet + json.dumps).
출력: outputs/latency.json(재현 비교 제외 파일) · outputs/memory.json"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import time

import s30_common as S


def rss_hwm():
    for ln in open("/proc/self/status"):
        if ln.startswith("VmHWM"):
            return round(int(ln.split()[1]) / 1024, 1)


def rss_now():
    for ln in open("/proc/self/status"):
        if ln.startswith("VmRSS"):
            return round(int(ln.split()[1]) / 1024, 1)


def burn(stop):
    x = 0
    while not stop.is_set():
        x = (x * 31 + 7) % 1000003


def q(ms):
    ms = sorted(ms)
    f = lambda p: round(ms[int(round(p * (len(ms) - 1)))], 3)  # noqa: E731
    return {"n": len(ms), "p50_ms": f(0.5), "p95_ms": f(0.95), "max_ms": round(ms[-1], 3)}


def main():
    rss0 = rss_now()
    t0 = time.perf_counter()
    A = S.nlu()
    import b4_evidence_guard as B4G
    import b4_evidence_policy as BP
    import context_preserving_retriever as CPR
    import nlu_pipeline_v3 as V3
    import p5_normalizer_adapter as PA
    import doctor_integration_adapter as AD
    import model_input_eligibility as ELIG
    PA.USE_CACHE = False
    V3.USE_CACHE = False
    A.USE_CACHE = False
    B4G.USE_CACHE = False
    PA.engine()
    ELIG.mapping(), ELIG.catalog()
    init_ms = round((time.perf_counter() - t0) * 1000, 1)
    rss_after_init = rss_now()
    mode, b4 = A.CFG[S.NLU_POLICY]
    pilot = [r["text_ko"] for r in S.read_csv(S.REPO / "exp/step21_korean_symptom_entity_linking/data/pilot_gold.csv")]
    s30 = [c["text"] for c in S.load_json(S.DATA / "integration_contract_cases.json")["cases"]]
    for t in pilot[:20]:
        AD.build_packet(t, A.analyze(t, S.NLU_POLICY))

    def stages(texts):
        nlu, ret, ada, ser, full = [], [], [], [], []
        for t in texts:
            a = time.perf_counter()
            ms, ctx = A.core3(t)
            b = time.perf_counter()
            outm = []
            for m in ms:
                m = BP.apply(CPR.apply(m, mode), b4)
                m["model_input"] = V3._mi(m)
                outm.append(m)
            c = time.perf_counter()
            pkt = AD.build_packet(t, {"source_text": t, "level": S.NLU_POLICY, "mentions": outm, "context": ctx})
            d = time.perf_counter()
            json.dumps(pkt, ensure_ascii=False, default=str)
            e = time.perf_counter()
            nlu.append((b - a) * 1000)
            ret.append((c - b) * 1000)
            ada.append((d - c) * 1000)
            ser.append((e - d) * 1000)
            f0 = time.perf_counter()
            json.dumps(AD.build_packet(t, A.analyze(t, S.NLU_POLICY)), ensure_ascii=False, default=str)
            full.append((time.perf_counter() - f0) * 1000)
        return {"nlu_core3": q(nlu), "retrieval_cpr_b4": q(ret), "integration_adapter": q(ada), "json_serialization": q(ser), "full_pipeline": q(full)}

    res = {"condition_A_low_load": {"loadavg_1m_before": round(os.getloadavg()[0], 2), "pilot274": stages(pilot), "step30_cases82": stages(s30)}}
    res["condition_A_low_load"]["loadavg_1m_after"] = round(os.getloadavg()[0], 2)
    stop = mp.Event()
    ps = [mp.Process(target=burn, args=(stop,)) for _ in range(2)]
    for p in ps:
        p.start()
    time.sleep(3)
    res["condition_B_concurrent_load"] = {"background": "이 스크립트가 띄운 CPU 바쁜 루프 2개", "loadavg_1m_during": round(os.getloadavg()[0], 2),
                                          "pilot274": stages(pilot)}
    stop.set()
    for p in ps:
        p.join()
    out = {**S.RESEARCH_BANNER, **res, "init_load_ms(NLU 엔진·B4 라우터·KoELECTRA·변환표·카탈로그)": init_ms, "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
           "gpu": "사용 안 함", "repeats": "입력당 1회(순차), warm-up 20", "nproc": os.cpu_count(),
           "step29_3_reference": "STEP29.3 조건 A pilot274 R2 analyze p95 52.6 ms(다른 시점·부하 — 같은 날 다른 시각 측정이라 직접 비교는 참고만)",
           "CPU_P95_definition": "조건 A pilot274 full_pipeline(analyze R2 + build_packet + json.dumps) p95",
           "note": "개발 PC 단일 측정 — 병원 운영 성능 검증 아님"}
    S.dump_json(S.OUT / "latency.json", out)
    S.dump_json(S.OUT / "memory.json", {"rss_before_import_mib": rss0, "rss_after_init_mib": rss_after_init, "peak_rss_hwm_mib": rss_hwm(),
                                        "process": "benchmark_runtime(전 조건 측정 후)"})
    print(S.dumps({"init_ms": init_ms, "A_pilot_full": res["condition_A_low_load"]["pilot274"]["full_pipeline"],
                   "A_adapter": res["condition_A_low_load"]["pilot274"]["integration_adapter"], "B_full": res["condition_B_concurrent_load"]["pilot274"]["full_pipeline"],
                   "hwm": rss_hwm()}))


if __name__ == "__main__":
    main()
