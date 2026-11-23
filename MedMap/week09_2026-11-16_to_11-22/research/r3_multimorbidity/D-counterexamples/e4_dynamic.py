"""E4 [가상] SYNTHETIC: 치료가 상태(eGFR 유사 수치)를 바꾸어 다른 치료의 적격성을 바꾸는 순환 의존.

모델: 기준 상태 e0, 약 i 의 효과 delta_i(상태 변화, 가산), 적격 조건 e >= t_i (또는 hand case 의 e < u_i), 이득 b_i,
      질환별 요구 needs(하나 이상).
의미론
  STATIC : 적격을 기준 상태 e0 에서만 판정 (단순 규칙 엔진)
  POST   : 선택 집합 S 의 사후 상태 e0+sum delta 에서 S 의 모든 약이 적격 (고정점/완성 의미론). MILP 로 정확히 인코딩
  SEQ    : 지침 순서대로 하나씩 탐욕 추가(현재 상태에서 적격이면 추가). 순서 2가지 비교
  TRAJ   : 시작 순서까지 고르고 모든 중간 상태에서 '이미 시작한 약' 이 적격 (bounded-horizon planning)
           brute force(순열) vs 시간 색인 MILP 비교
출력: logs/e4_dynamic.log, results_e4_dynamic.csv
"""
import csv, itertools, sys, time, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import solve_milp, all_subsets

M = 1000.0


def covers(I, S):
    return all(any(i in S for i in nd) for nd in I["needs"])


def post_ok(I, S):
    e = I["e0"] + sum(I["delta"][i] for i in S)
    return all(e >= I["t"][i] for i in S)


def traj_ok_order(I, order):
    e = I["e0"]; started = []
    for i in order:
        if e < I["t"][i]:  # 시작 시점 적격
            return False
        started.append(i); e += I["delta"][i]
        if any(e < I["t"][j] for j in started):
            return False
    return True


def val(I, S):
    return int(sum(I["benefit"][i] for i in S))


def brute(I, mode):
    best = None
    for _, S in all_subsets(I["n"]):
        if not covers(I, S): continue
        if mode == "STATIC" and not all(I["e0"] >= I["t"][i] for i in S): continue
        if mode == "POST" and not post_ok(I, S): continue
        if mode == "TRAJ" and not any(traj_ok_order(I, o) for o in itertools.permutations(S)): continue
        v = val(I, S)
        if best is None or v > best[0]: best = (v, S)
    return best


def milp_post(I):
    n = I["n"]; A, lo, hi = [], [], []
    for nd in I["needs"]:
        r = [0] * n
        for i in nd: r[i] = 1
        A.append(r); lo.append(1); hi.append(np.inf)
    # e0 + sum delta_j x_j >= t_i - M(1-x_i)  ->  sum delta_j x_j - M x_i >= t_i - e0 - M
    for i in range(n):
        r = list(map(float, I["delta"])); r[i] -= M
        A.append(r); lo.append(I["t"][i] - I["e0"] - M); hi.append(np.inf)
    st, x, obj = solve_milp(I["benefit"], A, lo, hi, [1] * n, [0] * n, [1] * n, maximize=True)
    return None if st != 0 else int(round(obj))


def milp_traj(I):
    """시간 색인: y[i,k]=1 이면 약 i 를 k 번째 단계에서 시작 (k=0..n-1, 단계당 최대 1개).
    started(i,k) = sum_{k'<=k} y[i,k'].  상태 e_k = e0 + sum_i delta_i started(i,k).
    시작 조건: e_{k-1} >= t_i - M(1-y[i,k])   (e_{-1}=e0)
    유지 조건: e_k >= t_i - M(1-started(i,k))  for all k."""
    n = I["n"]; nv = n * n
    idx = lambda i, k: i * n + k
    A, lo, hi = [], [], []
    for i in range(n):  # 각 약 최대 1번 시작
        r = [0] * nv
        for k in range(n): r[idx(i, k)] = 1
        A.append(r); lo.append(-np.inf); hi.append(1)
    for k in range(n):  # 단계당 최대 1개
        r = [0] * nv
        for i in range(n): r[idx(i, k)] = 1
        A.append(r); lo.append(-np.inf); hi.append(1)
    for nd in I["needs"]:
        r = [0] * nv
        for i in nd:
            for k in range(n): r[idx(i, k)] = 1
        A.append(r); lo.append(1); hi.append(np.inf)
    for i in range(n):
        for k in range(n):
            # 시작 조건: e0 + sum_j delta_j started(j,k-1) - M*y[i,k] >= t_i - M
            r = [0.0] * nv
            for j in range(n):
                for kk in range(k): r[idx(j, kk)] += I["delta"][j]
            r[idx(i, k)] -= M
            A.append(r); lo.append(I["t"][i] - I["e0"] - M); hi.append(np.inf)
            # 유지 조건: e0 + sum_j delta_j started(j,k) - M*started(i,k) >= t_i - M
            r = [0.0] * nv
            for j in range(n):
                for kk in range(k + 1): r[idx(j, kk)] += I["delta"][j]
            for kk in range(k + 1): r[idx(i, kk)] -= M
            A.append(r); lo.append(I["t"][i] - I["e0"] - M); hi.append(np.inf)
    c = [I["benefit"][i] for i in range(n) for k in range(n)]
    st, x, obj = solve_milp(c, A, lo, hi, [1] * nv, [0] * nv, [1] * nv, maximize=True)
    return None if st != 0 else int(round(obj))


def seq(I, order):
    e = I["e0"]; S = []
    for i in order:
        if e >= I["t"][i] and all(e + I["delta"][i] >= I["t"][j] for j in S + [i]):
            S.append(i); e += I["delta"][i]
    return S


def gen(rng, n=6):
    return dict(n=n, e0=int(rng.integers(25, 61)),
                delta=[int(v) for v in rng.integers(-10, 6, size=n)],
                t=[int(v) for v in rng.choice([0, 15, 20, 30, 45], size=n)],
                benefit=[int(v) for v in rng.integers(1, 10, size=n)],
                needs=[list(map(int, rng.choice(n, size=rng.integers(1, 3), replace=False))) for _ in range(rng.integers(1, 3))])


def hand():
    print("== HAND D1 [가상] STATIC 이 승인하지만 사후 상태에서 위반 ==")
    I = dict(n=2, e0=33, delta=[-5, 0], t=[0, 30], benefit=[5, 5], needs=[[0], [1]])
    print("  STATIC best:", brute(I, "STATIC"), " POST best:", brute(I, "POST"), " MILP POST:", milp_post(I),
          " TRAJ:", brute(I, "TRAJ"), " MILP TRAJ:", milp_traj(I))
    print("== HAND D2 [가상] 순서 의존: 상태 개선 약을 먼저 시작해야만 가능 ==")
    I = dict(n=2, e0=28, delta=[5, -2], t=[0, 30], benefit=[3, 6], needs=[[1]])
    print("  POST:", brute(I, "POST"), " TRAJ:", brute(I, "TRAJ"), " MILP TRAJ:", milp_traj(I),
          " SEQ order(1,0):", seq(I, [1, 0]), " SEQ order(0,1):", seq(I, [0, 1]))
    print("== HAND D3 [가상] 자기정당화 고정점(완성 의미론 vs 근거있는 의미론) ==")
    # 약 B_full: e>=30 일 때 사용, B_red(감량): e<30 일 때 사용. 둘 다 효과 -2. e0=31. 요구: 둘 중 하나.
    e0 = 31
    opts = {"B_full": (lambda e: e >= 30, -2), "B_red": (lambda e: e < 30, -2)}
    for name, (cond, d) in opts.items():
        print(f"  {name}: baseline-eligible={cond(e0)}  post-state={e0+d} post-eligible={cond(e0+d)}")
    print("  -> STATIC 은 B_full 선택(사후 위반), POST(고정점)는 B_red 만 일관: B_red 는 자기 효과로만 적격(self-supporting).")
    print("     TRAJ(시작 시점 적격 요구)에서는 B_red 가 e0=31 에서 부적격이라 시작 불가, B_full 은 시작 후 29 로 유지 위반 -> '해 없음'")
    print("     -> POST 와 TRAJ 가 다른 답: 어느 의미론이 맞는지는 계산이 아니라 임상 판단(예상 감소를 미리 반영한 감량 허용 여부)")


def main():
    t0 = time.time()
    hand()
    rng = np.random.default_rng(20261117)
    rows = []
    for k in range(300):
        I = gen(rng)
        bs, bp, bt = brute(I, "STATIC"), brute(I, "POST"), brute(I, "TRAJ")
        mp, mt = milp_post(I), milp_traj(I)
        static_post_viol = (bs is not None) and (not post_ok(I, bs[1]))
        o1 = list(range(I["n"])); o2 = o1[::-1]
        s1, s2 = seq(I, o1), seq(I, o2)
        rows.append(dict(inst=k, static=None if bs is None else bs[0], post=None if bp is None else bp[0],
                         traj=None if bt is None else bt[0], milp_post=mp, milp_traj=mt,
                         post_agree=(None if bp is None else bp[0]) == mp, traj_agree=(None if bt is None else bt[0]) == mt,
                         static_plan_violates_post=static_post_viol,
                         seq_order_dependent=(sorted(s1) != sorted(s2)),
                         seq1_covers=covers(I, s1), seq2_covers=covers(I, s2),
                         post_ne_traj=((None if bp is None else bp[0]) != (None if bt is None else bt[0]))))
    with open("results_e4_dynamic.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    N = len(rows)
    print(f"== RANDOM n=6 drugs, N={N}, seed=20261117 ==")
    print(" MILP POST == brute POST:", sum(r["post_agree"] for r in rows), "/", N)
    print(" MILP TRAJ (time-indexed) == brute TRAJ (permutations):", sum(r["traj_agree"] for r in rows), "/", N)
    print(" STATIC optimum violates post-state eligibility:", sum(r["static_plan_violates_post"] for r in rows), "/", N)
    print(" SEQ greedy: order-dependent result:", sum(r["seq_order_dependent"] for r in rows), "/", N)
    print(" POST optimum != TRAJ optimum (ordering matters):", sum(r["post_ne_traj"] for r in rows), "/", N)
    print(" elapsed %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
