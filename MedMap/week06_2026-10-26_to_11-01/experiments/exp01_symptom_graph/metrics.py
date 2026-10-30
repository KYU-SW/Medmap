"""EXP-01 지표·통계·판정(manifest rev5 secondary_metrics·statistical_test·success_criterion 그대로).

중증 질환 목록은 severity_eval.py 만 읽는다(이 모듈은 이름 집합을 인자로 받는다).
"""
from __future__ import annotations

import math

import numpy as np

ALPHA, M_FAMILY, B_DEFAULT, BOOT_SEED = 0.025, 6, 10_000, 20261026
MID_H1_NUM, MID_H1_DEN = 1, 100           # +0.01 절대(정수 비교)


# ------------------------------------------------------------ 사례 지표
def truth_rank_pessimistic(scores, truth_idx: int) -> int:
    """비관적 동점 처리: 정답과 같은 점수의 다른 질환은 모두 정답보다 앞."""
    s = np.asarray(scores, dtype=np.float64)
    t = s[truth_idx]
    return 1 + int((s > t).sum()) + int((s == t).sum() - 1)


def in_topk(scores, truth_idx, k) -> bool:
    return truth_rank_pessimistic(scores, truth_idx) <= k


def wrong_termination(scores_log, truth_idx, tau) -> bool | None:
    """종료 시 정답이 Act(τ) 밖인가. τ 없음(TAU_FAIL) → None(NA). scores_log 는 로그 사후(그래프 계열)."""
    if tau is None:
        return None
    s = np.asarray(scores_log, dtype=np.float64)
    return bool(s[truth_idx] - s.max() < math.log(tau))


def wrong_termination_tree(node_counts, truth_idx) -> bool:
    return bool(np.asarray(node_counts)[truth_idx] == 0)


def ece_top1(probs: np.ndarray, truth: np.ndarray, bins=15) -> float:
    conf = probs.max(1)
    pred = probs.argmax(1)
    acc = (pred == truth).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    e = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        if m.any():
            e += m.mean() * abs(acc[m].mean() - conf[m].mean())
    return float(e)


def brier(probs: np.ndarray, truth: np.ndarray) -> float:
    oh = np.zeros_like(probs)
    oh[np.arange(len(truth)), truth] = 1
    return float(((probs - oh) ** 2).sum(1).mean())


# ------------------------------------------------------------ bootstrap
def boot_indices(n, B=B_DEFAULT, seed=BOOT_SEED, chunk=500):
    """모든 모델·비교에 같은 재표본 인덱스(청크 단위 생성기)."""
    rng = np.random.default_rng(seed)
    done = 0
    while done < B:
        b = min(chunk, B - done)
        yield rng.integers(0, n, size=(b, n))
        done += b


def boot_stat(fn, n, B=B_DEFAULT, seed=BOOT_SEED):
    """fn(idx: (n,) int array) -> float. 같은 seed 이면 같은 인덱스."""
    out = []
    for blk in boot_indices(n, B, seed):
        out.extend(fn(row) for row in blk)
    return np.asarray(out)


def diff_rate(a: np.ndarray, b: np.ndarray, mask: np.ndarray | None = None):
    """대응 비율 차 함수 생성: mean(a)−mean(b) (mask 부분집합, 매 반복 분모 재계산)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    mk = None if mask is None else np.asarray(mask, bool)
    def f(idx):
        if mk is None:
            return a[idx].mean() - b[idx].mean()
        sel = idx[mk[idx]]
        if not len(sel):
            f.empty += 1                                   # 빈 부분집합 재표본 수 기록(통계 gate5 MINOR)
            return 0.0
        return a[sel].mean() - b[sel].mean()
    f.empty = 0
    return f


def p_one_sided(deltas: np.ndarray, b: float, direction: str) -> float:
    """direction='better' (귀무 Δ ≤ b): p=(#{Δ*≤b}+1)/(B+1); 'notworse' (귀무 Δ ≥ b): p=(#{Δ*≥b}+1)/(B+1)."""
    d = np.asarray(deltas)
    cnt = int((d <= b).sum()) if direction == "better" else int((d >= b).sum())
    return (cnt + 1) / (len(d) + 1)


def composite_p(components: dict) -> float:
    """A안: 성분 p 의 최대. NA(None) 성분은 제외. 전부 NA 면 1."""
    vals = [p for p in components.values() if p is not None]
    return max(vals) if vals else 1.0


def holm(pvals: dict, alpha=ALPHA) -> dict:
    """단조 누적 Holm 조정 p, 순위 수준 α_j* 와 단계 하강 기각 여부.
    동률 합성 p 는 가장 작은 순위(가장 엄격한 α*)를 공유한다(gate4 통계 MINOR). 정렬 안정성용 보조 키 = 가설 이름."""
    names = sorted(pvals, key=lambda k: (pvals[k], k))
    m = len(names)
    first_rank = {}
    for i, k in enumerate(names):
        first_rank.setdefault(pvals[k], i)
    adj, running, out, stopped = {}, 0.0, {}, False
    for i, k in enumerate(names):
        running = max(running, min(1.0, (m - i) * pvals[k]))
        adj[k] = running
        r = first_rank[pvals[k]]
        level = alpha / (m - r)
        rej = (not stopped) and pvals[k] <= level and running < alpha   # 판정 = Holm 조정 p < 0.025(manifest); 경계 불일치 제거
        if not rej:
            stopped = True
        out[k] = {"p": pvals[k], "p_adj": running, "rank": r + 1, "alpha_star": level, "rejected": rej}
    return out


# ------------------------------------------------------------ 판정
def mid_met(k_new: int, k_old: int, n: int) -> bool:
    """Δ̂ ≥ 0.01 정수 비교: (k_new − k_old)·100 ≥ n."""
    return (k_new - k_old) * MID_H1_DEN >= MID_H1_NUM * n


def disease_rule_fires(miss_count_new: dict, miss_count_old: dict, n_d: dict, n_min=100) -> list:
    """FINAL n≥100 중증 질환별 누락률 점추정 악화 > +2%p. 입력은 비율이 아니라 **누락 사례 수**(정수):
    (k_new − k_old)/n_d > 0.02 ⇔ (k_new − k_old)·50 > n_d. 발동 질환 목록."""
    for v in list(miss_count_new.values()) + list(miss_count_old.values()) + list(n_d.values()):
        if int(v) != v:
            raise ValueError("EXP01_DISEASE_RULE_NEEDS_COUNTS")
    return sorted(d for d in n_d if n_d[d] >= n_min and (miss_count_new[d] - miss_count_old[d]) * 50 > n_d[d])


H1_LABELS = ("INVALID", "SAFETY_FAIL", "SAFETY_HOLD", "SUCCESS", "SIGNIFICANT_BELOW_MID",
             "ABOVE_MID_NOT_SIGNIFICANT", "FAILURE")


def label_h1(invalid: bool, safety_p: float, alpha_star: float, disease_fired: list,
             p_adj: float, mid_ok: bool) -> str:
    if invalid:
        return "INVALID"
    if safety_p > alpha_star:
        return "SAFETY_FAIL"
    if disease_fired:
        return "SAFETY_HOLD"
    sig = p_adj < ALPHA
    if sig and mid_ok:
        return "SUCCESS"
    if sig:
        return "SIGNIFICANT_BELOW_MID"
    if mid_ok:
        return "ABOVE_MID_NOT_SIGNIFICANT"
    return "FAILURE"


def label_stage(invalid, prev_adopted, tau_fail, safety_ps, alpha_star, disease_fired,
                ni_ps, eff_ps, rejected) -> dict:
    """비H1 단계 라벨(채택 라벨)과 안전 상태 열(의료 gate4 MINOR: 채택 라벨이 안전 신호를 가리지 않게)을 함께 반환."""
    safety_fail = any(p is not None and p > alpha_star for p in safety_ps)
    safety_state = "SAFETY_FAIL" if safety_fail else ("SAFETY_HOLD" if disease_fired else "PASS")
    cond = label_stage(invalid, True, tau_fail, safety_ps, alpha_star, disease_fired, ni_ps, eff_ps, rejected)["label"] \
        if (not prev_adopted and not invalid) else None      # 사슬을 무시했을 때의 조건부 라벨(설계 gate4 MINOR)
    if invalid:
        lab = "INVALID"
    elif not prev_adopted:
        lab = "NOT_ELIGIBLE"
    elif tau_fail:
        lab = "TAU_FAIL"
    elif safety_fail:
        lab = "SAFETY_FAIL"
    elif disease_fired:
        lab = "SAFETY_HOLD"
    elif any(p is not None and p > alpha_star for p in ni_ps):
        lab = "NI_NOT_SHOWN"
    elif any(p is not None and p > alpha_star for p in eff_ps):
        lab = "EFFICIENCY_NOT_SHOWN"
    elif not rejected:
        lab = "HOLM_NOT_REJECTED"
    else:
        lab = "ADOPTED"
    return {"label": lab, "safety_state": safety_state, "tau_fail": bool(tau_fail), "conditional_label": cond}


def chain(h1_label: str, stage_labels: dict) -> str:
    """순차 채택: C → PA → PB_REL → PB → PC. 첫 미채택에서 멈춤."""
    if h1_label != "SUCCESS":
        return "C"
    model = "PA"
    for st in ("PB_REL", "PB", "PC"):
        if stage_labels.get(st) != "ADOPTED":
            break
        model = st
    return model


# ------------------------------------------------------------ τ 선택(manifest threshold_selection, SELECT 전용)
TAU_TIE = 0.001          # Top-5 차 < 0.1%p 이면 동률


def select_tau(stats: dict, taus) -> dict:
    """stats[τ] = {"top5", "severe_miss", "wrong_term"} (PB, Q=5), stats["PB_REL"] = {"severe_miss"},
    stats[("PB_REL_virtual", τ)] = {"wrong_term"}. 규칙: (중증 누락 ≤ PB_REL) AND (잘못된 분기 종료 ≤ 같은 τ 의 PB_REL 가상 판정)
    인 τ 중 Top-5 최고, 최고와 차 < 0.1%p 이면 더 작은 τ. 없으면 TAU_FAIL(None)."""
    def le(a, b):                       # 중증 사례 0건 등으로 값이 없으면 둘 다 없을 때만 조건 충족(재감사 N3b)
        if a is None or b is None:
            return a is None and b is None
        return a <= b
    ok = [t for t in taus
          if le(stats[t]["severe_miss"], stats["PB_REL"]["severe_miss"])
          and le(stats[t]["wrong_term"], stats[("PB_REL_virtual", t)]["wrong_term"])]
    if not ok:
        return {"tau": None, "status": "TAU_FAIL", "eligible": []}
    best = max(stats[t]["top5"] for t in ok)
    if all("k_top5" in stats[t] and "n" in stats[t] for t in ok):      # 정수 비교(통계 gate5 MINOR): (k_best−k_τ)·1000 < n
        kb = max(stats[t]["k_top5"] for t in ok)
        tied = [t for t in ok if (kb - stats[t]["k_top5"]) * 1000 < stats[t]["n"]]
    else:
        tied = [t for t in ok if best - stats[t]["top5"] < TAU_TIE]
    return {"tau": min(tied), "status": "SELECTED", "eligible": sorted(ok), "tied": sorted(tied)}
