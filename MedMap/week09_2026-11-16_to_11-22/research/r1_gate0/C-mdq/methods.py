"""기준선 정책 1~6, EC2, 점추정(naive) + 정책트리 생성/평가 (이산 모델 위)."""
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

BIG = 10.0


# ---------------- 트리 ----------------
def build_tree(M, choose, S=None, asked=(), stop=None, _guard=0):
    if S is None:
        S = M.ALL
    if stop is not None:
        lab = stop(M, S, asked)
        if lab is not None:
            return dict(leaf=True, label=lab, S=S)
    else:
        ok, lab = M.certified(S)
        if ok:
            return dict(leaf=True, label=lab, S=S)
    t = choose(M, S, asked)
    if t is None:
        return dict(leaf=True, label="UNDET", S=S)
    parts = M.split(S, t)
    if len(parts) < 2 and stop is None:
        raise RuntimeError("uninformative choice")
    ch = {v: build_tree(M, choose, sub, tuple(asked) + (t,), stop) for v, sub in parts.items()}
    return dict(leaf=False, test=t, children=ch, S=S)


def chain_tree(M, order, S=None, i=0):
    """일괄(non-adaptive): order 의 모든 테스트를 무조건 질문."""
    if S is None:
        S = M.ALL
    if i == len(order):
        ok, lab = M.certified(S)
        return dict(leaf=True, label=lab if ok else "UNDET_FAIL", S=S)
    t = order[i]
    parts = M.split(S, t)
    ch = {v: chain_tree(M, order, sub, i + 1) for v, sub in parts.items()}
    return dict(leaf=False, test=t, children=ch, S=S)


def eval_tree(M, tree):
    """atom 별 경로 비용·질문 수·선언 결론."""
    cost = np.zeros(M.nA)
    nq = np.zeros(M.nA)
    decl = [None] * M.nA

    def rec(node, c, q):
        if node["leaf"]:
            b = M.to_bool(node["S"])
            cost[b] = c
            nq[b] = q
            for a in np.nonzero(b)[0]:
                decl[a] = node["label"]
            return
        t = node["test"]
        for sub in node["children"].values():
            rec(sub, c + M.cost[t], q + 1)
    rec(tree, 0.0, 0)
    return cost, nq, decl


def tree_metrics(M, tree):
    cost, nq, decl = eval_tree(M, tree)
    wrong = np.array([(decl[a] != M.g[a]) and decl[a] != "UNDET" for a in range(M.nA)])
    overhold = np.array([(decl[a] == "UNDET") and M.g[a] != "UNDET" for a in range(M.nA)])
    return dict(worst_cost=cost.max(), worst_nq=nq.max(),
                exp_cost_u=float(cost @ M.w_unif), exp_nq_u=float(nq @ M.w_unif),
                exp_cost_s=float(cost @ M.w_skew), exp_nq_s=float(nq @ M.w_skew),
                wrong_det_u=float(M.w_unif[wrong].sum()), wrong_hold_u=float(M.w_unif[overhold].sum())), cost


# ---------------- 정책 ----------------
def pol_random(seed):
    rng = np.random.default_rng(seed)

    def choose(M, S, asked):
        inf = M.informative(S)
        return int(rng.choice(inf))
    return choose


def pol_fixed(M, S, asked):
    inf = M.informative(S)
    return inf[0]


def pol_greedy_count(M, S, asked):
    """최악 답 기준 남은 가설 수(균등가중) 최대 감소 / 비용."""
    best, bt = -1, None
    tot = M.weight(S, M.w_unif)
    for t in M.informative(S):
        worst = max(M.weight(sub, M.w_unif) for sub in M.split(S, t).values())
        sc = (tot - worst) / M.cost[t]
        if sc > best + 1e-12:
            best, bt = sc, t
    return bt


def _edges(M, S, w):
    b = M.to_bool(S)
    tot = w[b].sum()
    lab = {}
    for a in np.nonzero(b)[0]:
        lab[M.g[a]] = lab.get(M.g[a], 0.0) + w[a]
    return (tot ** 2 - sum(x ** 2 for x in lab.values())) / 2.0, tot


def pol_ec2(prior="u"):
    """Golovin et al. 2010 EC2 (잡음 없는 등가류 결정): 기대 절단 간선 가중치 / 비용."""
    def choose(M, S, asked):
        w = M.w_unif if prior == "u" else M.w_skew
        E0, tot = _edges(M, S, w)
        best, bt = -1, None
        for t in M.informative(S):
            exp_rem = 0.0
            for sub in M.split(S, t).values():
                e, wt = _edges(M, sub, w)
                exp_rem += (wt / tot) * e
            sc = (E0 - exp_rem) / M.cost[t]
            if sc > best + 1e-15:
                best, bt = sc, t
        return bt
    return choose


def _hyp_mask(M, S):
    return M.to_bool(S)[M.hAtom]


def pol_voi(prior="u"):
    """근시안적 VOI: E_ans[max_a E(u|ans)] - max_a E(u). 금기 효용 = -BIG. 분포: 균등(u) 또는 편향(s)."""
    def choose(M, S, asked):
        w_atom = M.w_unif if prior == "u" else M.w_skew
        # 가설 가중치: atom 가중치를 atom 내부 격자점에 균등 분배
        hm = _hyp_mask(M, S)
        cnt = np.bincount(M.hAtom, minlength=M.nA).astype(float)
        hw = w_atom[M.hAtom] / cnt[M.hAtom]
        U = np.where(M.hFeas, M.hU, -BIG)
        def val(mask):
            ww = hw * mask
            z = ww.sum()
            return (ww @ U).max() / z, z
        v0, z0 = val(hm)
        best, bt, inf = -1, None, M.informative(S)
        for t in inf:
            ev = 0.0
            for sub in M.split(S, t).values():
                v, z = val(_hyp_mask(M, sub))
                ev += (z / z0) * v
            sc = (ev - v0) / M.cost[t]
            if sc > best + 1e-12:
                best, bt = sc, t
        choose.calls += 1
        if best <= 1e-12:      # VOI=0 인데 미확정 -> 대체 규칙(탐욕)
            choose.fallback += 1
            return pol_greedy_count(M, S, asked)
        return bt
    choose.calls = 0
    choose.fallback = 0
    return choose


def _regret_table(M, hm):
    U = M.hU[hm]
    F = M.hFeas[hm]
    Uf = np.where(F, U, -np.inf)
    best = Uf.max(axis=1)
    none = ~F.any(axis=1)
    R = np.where(F, best[:, None] - U, BIG)
    R[none] = 0.0
    return R


def pol_regret():
    """minimax regret 기반(Boutilier식 current solution strategy의 이산 근사).
    a* = argmin_a max_h regret, h* = adversary. h* 와 a*가 최적인 가설을 구분하는 테스트 중
    최악 답 기준 minimax regret 감소/비용 최대 선택."""
    def choose(M, S, asked):
        hm = _hyp_mask(M, S)
        idx = np.nonzero(hm)[0]
        R = _regret_table(M, hm)
        MR = R.max(axis=0)
        a_star = int(MR.argmin())
        mr0 = MR[a_star]
        inf = M.informative(S)
        if mr0 <= 1e-9:
            choose.fallback += 1
            return pol_greedy_count(M, S, asked)
        h_star = idx[int(R[:, a_star].argmax())]
        good = idx[R[:, a_star] <= 1e-9]
        atom_star = M.hAtom[h_star]
        good_atoms = set(M.hAtom[good].tolist())
        cand = [t for t in inf if any(M.ans[t, ga] != M.ans[t, atom_star] for ga in good_atoms)] or inf
        best, bt = -np.inf, None
        for t in cand:
            worst = 0.0
            for sub in M.split(S, t).values():
                r = _regret_table(M, _hyp_mask(M, sub)).max(axis=0).min()
                worst = max(worst, r)
            sc = (mr0 - worst) / M.cost[t]
            if sc > best + 1e-12 or (abs(sc - best) <= 1e-12 and M.cost[t] < M.cost[bt]):
                best, bt = sc, t
        return bt
    choose.fallback = 0
    return choose


def naive_stop(M, S, asked):
    """점추정 선호(현재 셀 격자점 평균 가중치) 기준: 모든 가능 세계에서 그 점의 최선이 같으면 확정 선언.
    W 불확실성을 무시 -> 잘못된 확정 위험 (실패 사례 시연용)."""
    hm = _hyp_mask(M, S)
    idx = np.nonzero(hm)[0]
    ng = len(M.G)
    gi = idx % ng
    wbar = M.G[np.unique(gi)].mean(axis=0)
    worlds = np.unique(idx // ng)
    from core import score_matrix, feasible, label_from_utils
    labs = set()
    for wi in worlds:
        s = M.worlds[wi]
        labs.add(label_from_utils(score_matrix(M.inst, s) @ wbar, feasible(M.inst, s)))
    if len(labs) == 1:
        return next(iter(labs))
    if not M.informative(S):
        return "UNDET"
    return None


def pol_naive(M, S, asked):
    inf = M.informative(S)
    return inf[0] if inf else None


# ---------------- 6: hitting set (scipy milp) ----------------
def hitting_set_milp(M):
    """결론(g)이 다른 atom 쌍마다 '그 쌍을 구분하는 테스트 집합'을 하나의 hitting 제약으로.
    동일 제약은 중복 제거. min sum c_t x_t s.t. 각 제약 sum_{t in sep} x_t >= 1."""
    T = M.T
    labs = np.array(M.g)
    seps = set()
    # 쌍 열거: label 이 다른 atom 쌍. 구분 테스트 집합을 bitmask 로.
    ans = M.ans
    nA = M.nA
    for a in range(nA):
        diff = np.nonzero(labs[a + 1:] != labs[a])[0] + a + 1
        if len(diff) == 0:
            continue
        sepm = (ans[:, diff] != ans[:, [a]])      # (T, k)
        codes = (sepm.T.astype(np.int64) * (1 << np.arange(T, dtype=np.int64))).sum(axis=1)
        seps.update(np.unique(codes).tolist())
    seps = sorted(seps)
    if not seps:
        return [], 0.0, 0
    # 최소화: 상위집합 제약 제거
    seps_min = [s for s in seps if not any((o != s) and (o & s) == o for o in seps)]
    A = np.array([[(s >> t) & 1 for t in range(T)] for s in seps_min], dtype=float)
    res = milp(c=M.cost, constraints=LinearConstraint(A, lb=np.ones(len(seps_min)), ub=np.inf),
               integrality=np.ones(T), bounds=Bounds(0, 1))
    assert res.success, res.message
    Q = [t for t in range(T) if res.x[t] > 0.5]
    return Q, float(M.cost[Q].sum()), len(seps_min)


def pol_ordered(Q):
    order = list(Q)

    def choose(M, S, asked):
        for t in order:
            if t not in asked and len(M.split(S, t)) >= 2:
                return t
        raise RuntimeError("Q exhausted")
    return choose
