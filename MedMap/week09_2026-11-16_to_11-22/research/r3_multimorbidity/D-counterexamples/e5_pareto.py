"""E5 [가상] SYNTHETIC: 목표 충돌·치료 부담. 가중합 스칼라화 vs 파레토 전체(epsilon-constraint MILP).

목표: 이득 B (max), 위험 R (min), 부담 = 약 개수 C (min). 제약: needs 충족, 금지쌍.
  brute force 파레토 집합 = 정답
  WS: 가중치 격자(각 축 0..10, 합>0, 1331개)로 MILP 스칼라화 -> 찾은 파레토 점
  EPS: C<=c, R<=r 를 모든 정수 수준에서 고정하고 B 최대화(MILP) 후 비지배 필터 -> 파레토 점
출력: logs/e5_pareto.log, results_e5_pareto.csv
"""
import csv, itertools, sys, os, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import solve_milp, all_subsets


def gen(rng, n=7):
    return dict(n=n, B=[int(v) for v in rng.integers(1, 10, size=n)], R=[int(v) for v in rng.integers(0, 6, size=n)],
                needs=[list(map(int, rng.choice(n, size=rng.integers(1, 3), replace=False))) for _ in range(rng.integers(1, 3))],
                pairs=[tuple(map(int, rng.choice(n, 2, replace=False))) for _ in range(rng.integers(0, 3))])


def feas(I, S):
    Ss = set(S)
    return all(any(i in Ss for i in nd) for nd in I["needs"]) and all(not set(p) <= Ss for p in I["pairs"])


def obj(I, S):  # 최소화 형태로 (-B, R, C)
    return (-sum(I["B"][i] for i in S), sum(I["R"][i] for i in S), len(S))


def nondom(points):
    pts = set(points)
    return {p for p in pts if not any(q != p and all(q[k] <= p[k] for k in range(3)) for q in pts)}


def base_cons(I):
    n = I["n"]; A, lo, hi = [], [], []
    for nd in I["needs"]:
        r = [0] * n
        for i in nd: r[i] = 1
        A.append(r); lo.append(1); hi.append(np.inf)
    for p in I["pairs"]:
        r = [0] * n; r[p[0]] = 1; r[p[1]] = 1
        A.append(r); lo.append(-np.inf); hi.append(1)
    return A, lo, hi


def ws(I):
    n = I["n"]; found = set()
    A, lo, hi = base_cons(I)
    for a, b, c in itertools.product(range(11), repeat=3):
        if a + b + c == 0: continue
        cost = [-a * I["B"][i] + b * I["R"][i] + c for i in range(n)]
        st, x, _ = solve_milp(cost, A, lo, hi, [1] * n, [0] * n, [1] * n)
        if st == 0:
            S = [i for i in range(n) if x[i] > .5]; found.add(obj(I, S))
    return found


def eps(I):
    n = I["n"]; cand = set()
    A0, lo0, hi0 = base_cons(I)
    for cmax in range(1, n + 1):
        for rmax in range(0, sum(I["R"]) + 1):
            A = A0 + [[1] * n, list(I["R"])]; lo = lo0 + [-np.inf, -np.inf]; hi = hi0 + [cmax, rmax]
            st, x, _ = solve_milp(I["B"], A, lo, hi, [1] * n, [0] * n, [1] * n, maximize=True)
            if st == 0:
                bval = int(round(sum(I["B"][i] * x[i] for i in range(n))))
                # 같은 B 에서 R, C 를 다시 최소화(사전식) — 약 비지배 방지
                A2 = A + [list(I["B"])]; lo2 = lo + [bval]; hi2 = hi + [np.inf]
                st2, x2, _ = solve_milp([I["R"][i] * (n + 1) + 1 for i in range(n)], A2, lo2, hi2, [1] * n, [0] * n, [1] * n)
                S = [i for i in range(n) if x2[i] > .5]; cand.add(obj(I, S))
    return nondom(cand)


def main():
    t0 = time.time()
    rng = np.random.default_rng(20261117)
    rows = []
    for k in range(60):
        I = gen(rng)
        pts = [obj(I, S) for _, S in all_subsets(I["n"]) if feas(I, S)]
        truth = nondom(pts) if pts else set()
        w = ws(I) & truth if truth else set()
        e = eps(I) if truth else set()
        rows.append(dict(inst=k, n_pareto=len(truth), ws_found=len(w), eps_found=len(e & truth), eps_exact=(e == truth),
                         unsupported=len(truth) - len(w)))
    with open("results_e5_pareto.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys())); wr.writeheader(); wr.writerows(rows)
    tp = sum(r["n_pareto"] for r in rows)
    print(f"== E5 RANDOM n=7, N={len(rows)}, seed=20261117 ==")
    print(" total Pareto points (brute force):", tp)
    print(" weighted-sum grid found:", sum(r["ws_found"] for r in rows), f" missed (unsupported): {sum(r['unsupported'] for r in rows)}")
    print(" instances with >=1 point missed by weighted sum:", sum(1 for r in rows if r["unsupported"] > 0), "/", len(rows))
    print(" epsilon-constraint MILP set == brute-force Pareto set:", sum(r["eps_exact"] for r in rows), "/", len(rows))
    print(" elapsed %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
