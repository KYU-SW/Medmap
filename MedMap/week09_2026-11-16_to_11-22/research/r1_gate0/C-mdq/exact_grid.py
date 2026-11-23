"""정답(이산 모델): 7 최적 일괄(전수), 8 최적 적응형(최악 minimax DP), 8e 기대비용 최적 DP, AXp 하한.
methods.py 의 milp/정책 코드와 독립 작성 (atom 서명 직접 비교)."""
import itertools
import sys
import numpy as np

sys.setrecursionlimit(100000)


def batch_bruteforce(M):
    """모든 테스트 부분집합을 비용순 열거, '부분집합 답 서명이 같은 atom 은 g 가 같다'를 만족하는 최소 비용."""
    T = M.T
    subsets = []
    for r in range(T + 1):
        for Q in itertools.combinations(range(T), r):
            subsets.append((float(M.cost[list(Q)].sum()) if Q else 0.0, Q))
    subsets.sort(key=lambda x: (x[0], len(x[1])))
    for c, Q in subsets:
        groups = {}
        ok = True
        for a in range(M.nA):
            key = tuple(M.ans[t, a] for t in Q)
            lab = M.g[a]
            if groups.setdefault(key, lab) != lab:
                ok = False
                break
        if ok:
            return list(Q), c
    raise RuntimeError("no batch")


def adaptive_minimax(M):
    memo = {}

    def V(S):
        if S in memo:
            return memo[S][0]
        lab0 = M.g[(S & -S).bit_length() - 1]
        if (S & ~M.label_mask[lab0]) == 0:
            memo[S] = (0.0, None)
            return 0.0
        best, bt = np.inf, None
        for t in range(M.T):
            parts = [S & mk for mk in M.masks[t].values() if S & mk]
            if len(parts) < 2:
                continue
            if M.cost[t] >= best:
                continue
            v = M.cost[t]
            for p in parts:
                v = max(v, M.cost[t] + V(p))
                if v >= best:
                    break
            if v < best:
                best, bt = v, t
        memo[S] = (best, bt)
        return best
    val = V(M.ALL)

    def choose(MM, S, asked):
        V(S)
        return memo[S][1]
    return val, choose, len(memo)


def adaptive_expected(M, w):
    """확률 가정(가중치 w) 하 기대 비용 최소 적응형 정책 (Bayes 최적 결정나무)."""
    memo = {}
    wb = w

    def mass(S):
        b = M.to_bool(S)
        return float(wb[b].sum())

    def V(S):
        if S in memo:
            return memo[S][0]
        lab0 = M.g[(S & -S).bit_length() - 1]
        if (S & ~M.label_mask[lab0]) == 0:
            memo[S] = (0.0, None)
            return 0.0
        z = mass(S)
        best, bt = np.inf, None
        for t in range(M.T):
            parts = [S & mk for mk in M.masks[t].values() if S & mk]
            if len(parts) < 2:
                continue
            v = M.cost[t] + sum(mass(p) / z * V(p) for p in parts) if z > 0 else M.cost[t]
            if v < best - 1e-12:
                best, bt = v, t
        memo[S] = (best, bt)
        return best
    val = V(M.ALL)

    def choose(MM, S, asked):
        V(S)
        return memo[S][1]
    return val, choose


def axp_lower_bound(M):
    """각 atom 에 대해: 그 atom 의 답만으로 g 가 함의되는 최소 비용 테스트 부분집합 (abductive explanation /
    minimal sufficient reason, 비용 가중). 적응형 최악 최적값의 하한: max_atom AXp_cost(atom)."""
    T = M.T
    subsets = []
    for r in range(T + 1):
        for Q in itertools.combinations(range(T), r):
            subsets.append((float(M.cost[list(Q)].sum()) if Q else 0.0, Q))
    subsets.sort(key=lambda x: (x[0], len(x[1])))
    best = np.full(M.nA, np.inf)
    left = M.nA
    for c, Q in subsets:
        groups = {}
        for a in range(M.nA):
            key = tuple(M.ans[t, a] for t in Q)
            groups.setdefault(key, set()).add(M.g[a])
        for a in range(M.nA):
            if best[a] == np.inf:
                key = tuple(M.ans[t, a] for t in Q)
                if len(groups[key]) == 1:
                    best[a] = c
                    left -= 1
        if left == 0:
            break
    return float(best.max()), best
