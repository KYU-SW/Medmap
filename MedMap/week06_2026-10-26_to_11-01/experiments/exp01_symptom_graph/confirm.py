"""FINAL 확인적 분석(manifest rev5 statistical_test A안). SELECT·SMOKE 에서는 호출하지 않는다.

입력: run_exp01.evaluate 의 사례 기록 + 중증 집합 + 선택된 τ(None=TAU_FAIL) + seeds.
출력: 성분 p·합성 p·Holm(rank·α_j*·조정 p·기각)·라벨·순차 채택 모델. 모든 성분 p 를 따로 남긴다.
"""
from __future__ import annotations

import math

import numpy as np

import metrics as mt

B_SAFE = 0.005          # 중증 누락·잘못된 분기 종료 +0.5%p
B_SAFE_WRONG_WD = 0.01  # H3a·H3b 중증 누락 +1%p
B_NI = -0.005           # Top-5 비열등 −0.5%p
B_EFF = 0.90            # 계산 수 비 기하평균


def _vec(recs, model, budget=5, wd_mode=None, seed=None, tau="any"):
    sel = [r for r in recs if r["model"] == model and r["budget"] == budget and r["wd_mode"] == wd_mode
           and r.get("noise") is None                       # 응답 잡음 민감도 행은 확인적 분석에서 제외(재감사 N1)
           and (seed is None or r["seed"] == seed) and (tau == "any" or r["tau"] == tau)]
    return sorted(sel, key=lambda r: r["row_index"])


def _arr(rs, f):
    return np.array([f(r) for r in rs], dtype=float)


def component_ps(recs, severe, tau, seeds, B=mt.B_DEFAULT, seed=mt.BOOT_SEED, dist=None):
    """반환: {가설: {성분: p or None}} 와 효과 점추정."""
    def pair(a_rs, b_rs):
        if [r["row_index"] for r in a_rs] != [r["row_index"] for r in b_rs]:
            raise RuntimeError("EXP01_UNPAIRED")
        return a_rs, b_rs
    sev_mask = None
    cur = {"key": None}
    def boot_p(a, b, mask, bnd, direction, key=None):
        if key is not None:
            cur["key"] = key
        f = mt.diff_rate(a, b, mask)
        d = mt.boot_stat(f, len(a), B, seed)
        if dist is not None and cur["key"] is not None:        # 보조 보고(한계·CI)용 bootstrap 분포 보관
            dist[cur["key"]] = {"deltas": d, "direction": direction, "bound": bnd, "empty_resamples": f.empty,
                                "point": float(f(np.arange(len(a))))}
        cur["key"] = None
        return mt.p_one_sided(d, bnd, direction)
    def wt(rs, tv):
        return _arr(rs, lambda r: 0.0 if tv is None else float(r["truth_gap"] < math.log(tv)))
    C, PA, PBR = _vec(recs, "C"), _vec(recs, "PA"), _vec(recs, "PB_REL")
    PB = _vec(recs, "PB", tau=tau) if tau is not None else PBR
    pair(C, PA); pair(PA, PBR); pair(PBR, PB)
    sev_mask = np.array([r["truth"] in severe for r in C])
    top5 = lambda rs: _arr(rs, lambda r: float(r["top5"]))        # noqa: E731
    miss = lambda rs: _arr(rs, lambda r: float(not r["in8"]))     # noqa: E731
    comps, eff = {}, {}
    k_pa, k_c = int(top5(PA).sum()), int(top5(C).sum())
    eff["H1_delta"] = (k_pa - k_c) / len(C)
    eff["H1_mid_met"] = mt.mid_met(k_pa, k_c, len(C))
    def K(h, c, val_fn):
        cur["key"] = (h, c)
        try:
            return val_fn()
        finally:
            cur["key"] = None
    comps["H1"] = {"top5": K("H1", "top5", lambda: boot_p(top5(PA), top5(C), None, 0.0, "better")),
                   "severe_miss": K("H1", "severe_miss", lambda: boot_p(miss(PA), miss(C), sev_mask, B_SAFE, "notworse"))}
    comps["H2a"] = {"top5_ni": boot_p(top5(PBR), top5(PA), None, B_NI, "better", ("H2a", "top5_ni")),
                    "severe_miss": boot_p(miss(PBR), miss(PA), sev_mask, B_SAFE, "notworse", ("H2a", "severe_miss"))}
    if tau is None:
        comps["H2b"] = {"tau_fail": 1.0}
    else:
        ratio = np.log(_arr(PB, lambda r: r["counter"]) / _arr(PBR, lambda r: r["counter"]))
        gm = mt.boot_stat(lambda idx: float(np.exp(ratio[idx].mean())), len(ratio), B, seed)
        if dist is not None:
            dist[("H2b", "efficiency")] = {"deltas": gm, "direction": "notworse", "bound": B_EFF,
                                           "point": float(np.exp(ratio.mean())), "empty_resamples": 0}
        comps["H2b"] = {"severe_miss": boot_p(miss(PB), miss(PBR), sev_mask, B_SAFE, "notworse", ("H2b", "severe_miss")),
                        "wrong_term": boot_p(wt(PB, tau), wt(PBR, tau), None, B_SAFE, "notworse", ("H2b", "wrong_term")),
                        "efficiency": mt.p_one_sided(gm, B_EFF, "notworse")}
    def pc(mode, sd=None):            # TAU_FAIL 이면 PC = PB_REL + WD(tau=None 행, M3)
        rs = _vec(recs, "PC", wd_mode=mode, seed=sd, tau=tau)
        if not rs:
            raise RuntimeError(f"EXP01_PC_RECORDS_MISSING:{mode}:{sd}:{tau}")
        return pair(PB, rs)[1]
    h3a = pc("WD_MODEL_WRONG")
    comps["H3a"] = {"severe_miss": boot_p(miss(h3a), miss(PB), sev_mask, B_SAFE_WRONG_WD, "notworse", ("H3a", "severe_miss")),
                    "wrong_term": None if tau is None else boot_p(wt(h3a, tau), wt(PB, tau), None, B_SAFE, "notworse", ("H3a", "wrong_term"))}
    h3b = {}
    for sd in seeds:
        rs = pc("WD_RANDOM_WRONG", sd)
        h3b[f"severe_miss@{sd}"] = boot_p(miss(rs), miss(PB), sev_mask, B_SAFE_WRONG_WD, "notworse", ("H3b", f"severe_miss@{sd}"))
        h3b[f"wrong_term@{sd}"] = None if tau is None else boot_p(wt(rs, tau), wt(PB, tau), None, B_SAFE, "notworse", ("H3b", f"wrong_term@{sd}"))
    comps["H3b"] = h3b
    h3c = pc("WD_MODEL")
    comps["H3c"] = {"top5_ni": boot_p(top5(h3c), top5(PB), None, B_NI, "better", ("H3c", "top5_ni")),
                    "severe_miss": boot_p(miss(h3c), miss(PB), sev_mask, B_SAFE, "notworse", ("H3c", "severe_miss")),
                    "wrong_term": None if tau is None else boot_p(wt(h3c, tau), wt(PB, tau), None, B_SAFE, "notworse", ("H3c", "wrong_term"))}
    return comps, eff


SAFETY_KEYS = ("severe_miss", "wrong_term")


def judge(comps, eff, disease_fired: dict, invalid=False, tau_fail=False):
    composite = {h: mt.composite_p(c) for h, c in comps.items()}
    hol = mt.holm(composite)
    def split(h):
        c = comps[h]
        safety = [p for k, p in c.items() if k.split("@")[0] in SAFETY_KEYS]
        ni = [p for k, p in c.items() if k.startswith("top5_ni")]
        effp = [p for k, p in c.items() if k == "efficiency"]
        return safety, ni, effp
    s1, _, _ = split("H1")
    h1 = mt.label_h1(invalid, max([p for p in s1 if p is not None] or [0]), hol["H1"]["alpha_star"],
                     disease_fired.get("PA", []), hol["H1"]["p_adj"], eff["H1_mid_met"])
    stages, prev = {}, h1 == "SUCCESS"
    for st, h in (("PB_REL", ["H2a"]), ("PB", ["H2b"]), ("PC", ["H3a", "H3b", "H3c"])):
        sp, nip, ep = [], [], []
        for x in h:                       # 성분 p 를 자기 가설의 α_x* 로 나눈 비로 바꿔 수준 1 과 비교(가설별 α* 유지)
            a, b, c = split(x)
            ax = hol[x]["alpha_star"]
            sp += [None if p is None else p / ax for p in a]
            nip += [None if p is None else p / ax for p in b]
            ep += [None if p is None else p / ax for p in c]
        rej = all(hol[x]["rejected"] for x in h)
        lab = mt.label_stage(invalid, prev, tau_fail and st in ("PB", "PC"), sp, 1.0, disease_fired.get(st, []),
                             nip, ep, rej)
        stages[st] = lab
        prev = lab["label"] == "ADOPTED"
    model = mt.chain(h1, {k: v["label"] for k, v in stages.items()})
    return {"composite": composite, "holm": hol, "H1": h1, "stages": stages, "prespecified_model": model}


# ------------------------------------------------------------ 질환별 규칙 입력(M4) + FINAL 전체 판정(M2)
def disease_counts(rs, severe) -> tuple:
    """중증 질환별 (누락 사례 수, n) — 정수."""
    miss, n = {}, {}
    for r in rs:
        if r.get("noise") is not None:
            raise RuntimeError("EXP01_NOISE_ROW_IN_CONFIRMATORY")
        if r["truth"] in severe:
            n[r["truth"]] = n.get(r["truth"], 0) + 1
            miss[r["truth"]] = miss.get(r["truth"], 0) + (0 if r["in8"] else 1)
    return miss, n


def disease_fired_all(recs, severe, tau, seeds) -> dict:
    """단계별 질환별 악화 규칙 발동 목록. PC 는 WD_MODEL·WD_MODEL_WRONG·WD_RANDOM_WRONG(seed 전부)의 합집합, WD_CORRECT 제외."""
    def fired(new_rs, old_rs):
        kn, nn = disease_counts(new_rs, severe)
        ko, no = disease_counts(old_rs, severe)
        if nn != no:
            raise RuntimeError("EXP01_DISEASE_N_MISMATCH")
        return mt.disease_rule_fires({d: kn.get(d, 0) for d in nn}, {d: ko.get(d, 0) for d in nn}, nn)
    C, PA, PBR = _vec(recs, "C"), _vec(recs, "PA"), _vec(recs, "PB_REL")
    PB = _vec(recs, "PB", tau=tau) if tau is not None else PBR
    out = {"PA": fired(PA, C), "PB_REL": fired(PBR, PA), "PB": fired(PB, PBR) if tau is not None else []}
    pc = set()
    for mode, sds in (("WD_MODEL", [None]), ("WD_MODEL_WRONG", [None]), ("WD_RANDOM_WRONG", list(seeds))):
        for sd in sds:
            pc |= set(fired(_vec(recs, "PC", wd_mode=mode, seed=sd, tau=tau), PB))
    out["PC"] = sorted(pc)
    return out


def descriptive(dist, hol, mid=0.01) -> dict:
    """사전등록 보조 보고(판정 아님): 성분 점추정, 그 합성 가설 Holm 순위 수준 단측 한계, 양측 95% percentile CI,
    H1 Top-5 의 P*(Δ*≥MID) 와 단측 하한 ≥ MID 여부, 빈 부분집합 재표본 수."""
    out = {}
    for (h, c), v in dist.items():
        d = np.asarray(v["deltas"])
        a = hol[h]["alpha_star"]
        one = float(np.quantile(d, a)) if v["direction"] == "better" else float(np.quantile(d, 1 - a))
        out[f"{h}:{c}"] = {"point": v["point"], "one_sided_limit_at_alpha_star": one, "alpha_star": a,
                           "ci95_two_sided": [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))],
                           "empty_resamples": v["empty_resamples"]}
    if ("H1", "top5") in dist:
        d = np.asarray(dist[("H1", "top5")]["deltas"])
        out["H1:top5"]["p_star_ge_mid"] = float((d >= mid).mean())
        out["H1:top5"]["one_sided_lower_ge_mid"] = out["H1:top5"]["one_sided_limit_at_alpha_star"] >= mid
    return out


def final_analysis(recs, severe, tau, seeds, invalid=False, B=mt.B_DEFAULT) -> dict:
    """FINAL 확인적 분석 전체: 성분 p → 합성 p → Holm → 질환별 규칙 → 라벨 → 순차 채택."""
    dist = {}
    comps, eff = component_ps(recs, severe, tau, seeds, B=B, dist=dist)
    fired = disease_fired_all(recs, severe, tau, seeds)
    out = judge(comps, eff, fired, invalid=invalid, tau_fail=tau is None)
    out["descriptive"] = descriptive(dist, out["holm"])
    out.update({"components": comps, "effect": eff, "disease_fired": fired, "tau": tau,
                "tau_status": "TAU_FAIL" if tau is None else "SELECTED"})
    return out
