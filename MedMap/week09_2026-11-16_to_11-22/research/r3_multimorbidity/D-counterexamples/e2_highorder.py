"""E1/E2 [가상] SYNTHETIC: 고차(3개 이상) 상호작용과 '쌍마다 가능하지만 전체 불가능' 반례.

비교 방법
  M0 brute force (2^n 전수) = 정답
  M1 pairwise checker: 쌍 금지만 넣은 MILP 최적해 -> 고차 규칙 위반 여부 검사 ("놓침")
  M2 보수적 pairwise 근사: 고차 집합의 모든 쌍을 금지 -> 최적값 손실
  M3 full MILP: n-항 금지(sum_{i in S} x_i <= |S|-1) + 상태의존 누적위험 knapsack
  M4 MUS 열거(brute force): '모든 권고를 그대로 합친 처방'의 최소 충돌 집합. 크기>=3 MUS 개수
출력: logs/e2_highorder.log, results_e2_highorder.csv
"""
import csv, itertools, sys, time
import numpy as np
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from common import solve_milp, all_subsets, minimal_sets

OUT_CSV = "results_e2_highorder.csv"


# ---------------- 손계산 사례 ----------------
def hand_cases():
    print("== HAND CASE H1 [가상] triple-whammy 형 3항 금지 + 상태의존 고칼륨 ==")
    drugs = ["ACEi", "DIU", "NSAID", "MRA", "PCM"]  # [가상] 이름은 구조 설명용
    idx = {d: i for i, d in enumerate(drugs)}
    pair_forbid = []                         # 쌍 DDI 목록: 비어 있음
    tri_forbid = [("ACEi", "DIU", "NSAID")]  # [가상] 3항 금지
    krisk = {"ACEi": 1, "MRA": 1}             # [가상] 칼륨 위험 가산
    state_ckd = 1                              # [가상] CKD 상태 가산
    K_T = 2                                    # 합 <= 2 허용
    needs = [("ACEi",), ("DIU", "ACEi"), ("NSAID", "PCM"), ("MRA",)]  # [가상] 질환별 '하나 이상' 요구
    benefit = {"ACEi": 5, "DIU": 3, "NSAID": 3, "MRA": 4, "PCM": 2}

    def ok_pairwise(S):
        return all(not set(p) <= S for p in pair_forbid)

    def ok_full(S, ckd):
        if not ok_pairwise(S):
            return False
        if any(set(t) <= S for t in tri_forbid):
            return False
        return sum(krisk.get(d, 0) for d in S) + ckd <= K_T

    def covers(S):
        return all(any(d in S for d in nd) for nd in needs)

    for ckd in (0, state_ckd):
        naive = set(drugs[:4])  # 각 지침 1순위를 그대로 합침: ACEi, DIU, NSAID, MRA
        print(f" ckd={ckd} naive={sorted(naive)} pairwise_ok={ok_pairwise(naive)} full_ok={ok_full(naive, ckd)}")
        # MUS of naive regimen with respect to full rules (brute force)
        conf = [frozenset(drugs[i] for i in s) for _, s in all_subsets(len(drugs))
                if s and set(drugs[i] for i in s) <= naive and not ok_full(set(drugs[i] for i in s), ckd)]
        mus = minimal_sets(conf)
        print(f"   MUS(full rules) = {[sorted(m) for m in mus]}")
        # MILP full
        n = len(drugs); A, lo, hi = [], [], []
        for nd in needs:
            r = [0] * n
            for d in nd: r[idx[d]] = 1
            A.append(r); lo.append(1); hi.append(np.inf)
        for t in tri_forbid:
            r = [0] * n
            for d in t: r[idx[d]] = 1
            A.append(r); lo.append(-np.inf); hi.append(len(t) - 1)
        r = [krisk.get(d, 0) for d in drugs]; A.append(r); lo.append(-np.inf); hi.append(K_T - ckd)
        st, x, obj = solve_milp([benefit[d] for d in drugs], A, lo, hi, [1] * n, [0] * n, [1] * n, maximize=True)
        milp_set = sorted(drugs[i] for i in range(n) if x is not None and x[i] > .5) if st == 0 else None
        # brute force
        best = None
        for _, s in all_subsets(n):
            S = set(drugs[i] for i in s)
            if covers(S) and ok_full(S, ckd):
                v = sum(benefit[d] for d in S)
                if best is None or v > best[0]: best = (v, sorted(S))
        print(f"   MILP full: status={st} set={milp_set} obj={obj}; brute force best={best}")

    print("== HAND CASE H2 [가상] 논리적 고차 충돌: 권고 3개, 쌍마다 충족 가능, 3개 동시 불가 ==")
    # 변수: BP 약 A,B,C, 스타틴 S. R1: A+B+C>=2, R2: A+B+C+S<=2 (치료부담), R3: S=1
    names = ["A", "B", "C", "S"]
    R = {"R1": lambda x: x[0] + x[1] + x[2] >= 2,
         "R2": lambda x: sum(x) <= 2,
         "R3": lambda x: x[3] == 1}
    worlds = list(itertools.product([0, 1], repeat=4))
    for k in (2, 3):
        for combo in itertools.combinations(R, k):
            sat = any(all(R[c](w) for c in combo) for w in worlds)
            print(f"   {combo} jointly satisfiable={sat}")
    rows = [[1, 1, 1, 0], [1, 1, 1, 1], [0, 0, 0, 1]]
    st, x, _ = solve_milp([0] * 4, rows, [2, -np.inf, 1], [np.inf, 2, 1], [1] * 4, [0] * 4, [1] * 4)
    print(f"   MILP(R1,R2,R3) status={st} (2=infeasible 기대) -> MUS={{R1,R2,R3}} (모든 쌍이 가능하므로 크기3 MUS)")


# ---------------- 무작위 실험 ----------------
def gen(rng, n=8):
    m = rng.integers(2, 4)
    needs = [list(rng.choice(n, size=rng.integers(1, 4), replace=False)) for _ in range(m)]
    pairs = set()
    for _ in range(rng.integers(0, 3)):
        p = tuple(sorted(rng.choice(n, 2, replace=False))); pairs.add(p)
    tris = []
    tries = 0
    while len(tris) < rng.integers(1, 4) and tries < 50:
        tries += 1
        t = tuple(sorted(rng.choice(n, 3, replace=False)))
        if all(tuple(sorted(q)) not in pairs for q in itertools.combinations(t, 2)):
            tris.append(t)
    krisk = rng.integers(0, 3, size=n)
    state = int(rng.integers(0, 3))
    KT = int(rng.integers(2, 6))
    benefit = rng.integers(1, 10, size=n)
    return dict(n=n, needs=needs, pairs=sorted(pairs), tris=tris, krisk=krisk, state=state, KT=KT, benefit=benefit)


def feasible(I, S, use_tri=True, use_k=True, conservative=False):
    Sset = set(S)
    for nd in I["needs"]:
        if not any(i in Sset for i in nd): return False
    for p in I["pairs"]:
        if set(p) <= Sset: return False
    if conservative:
        for t in I["tris"]:
            for q in itertools.combinations(t, 2):
                if set(q) <= Sset: return False
    if use_tri:
        for t in I["tris"]:
            if set(t) <= Sset: return False
    if use_k and sum(I["krisk"][i] for i in S) + I["state"] > I["KT"]:
        return False
    return True


def brute(I, **kw):
    best = None
    for _, S in all_subsets(I["n"]):
        if feasible(I, S, **kw):
            v = int(sum(I["benefit"][i] for i in S))
            if best is None or v > best: best = v
    return best


def milp_model(I, use_tri=True, use_k=True, conservative=False):
    n = I["n"]; A, lo, hi = [], [], []
    for nd in I["needs"]:
        r = [0] * n
        for i in nd: r[i] = 1
        A.append(r); lo.append(1); hi.append(np.inf)
    cons_pairs = list(I["pairs"])
    if conservative:
        for t in I["tris"]: cons_pairs += list(itertools.combinations(t, 2))
    for p in cons_pairs:
        r = [0] * n; r[p[0]] = 1; r[p[1]] = 1
        A.append(r); lo.append(-np.inf); hi.append(1)
    if use_tri:
        for t in I["tris"]:
            r = [0] * n
            for i in t: r[i] = 1
            A.append(r); lo.append(-np.inf); hi.append(2)
    if use_k:
        A.append(list(I["krisk"])); lo.append(-np.inf); hi.append(I["KT"] - I["state"])
    st, x, obj = solve_milp(I["benefit"], A, lo, hi, [1] * n, [0] * n, [1] * n, maximize=True)
    if st != 0: return None, None
    return int(round(obj)), [i for i in range(n) if x[i] > .5]


def run_random(N=600, seed=20261117):
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(N):
        I = gen(rng)
        truth = brute(I)
        full_obj, _ = milp_model(I)
        pw_obj, pw_set = milp_model(I, use_tri=False, use_k=False)
        pw_violates = None if pw_set is None else (not feasible(I, pw_set))
        pw_viol_tri = None if pw_set is None else any(set(t) <= set(pw_set) for t in I["tris"])
        pw_viol_k = None if pw_set is None else (sum(I["krisk"][i] for i in pw_set) + I["state"] > I["KT"])
        cons_truth = brute(I, conservative=True)
        cons_obj, _ = milp_model(I, conservative=True)
        # naive union regimen = 각 need 의 첫 약 합집합
        naive = sorted(set(nd[0] for nd in I["needs"]))
        # MUS (rules: pairs, tris, knapsack; need 제외) brute force over subsets of naive
        def conflict(S):
            Ss = set(S)
            if any(set(p) <= Ss for p in I["pairs"]): return True
            if any(set(t) <= Ss for t in I["tris"]): return True
            return sum(I["krisk"][i] for i in S) + I["state"] > I["KT"]
        allsets = [frozenset(c) for r in range(1, len(naive) + 1) for c in itertools.combinations(naive, r) if conflict(c)]
        mus = minimal_sets(allsets)
        rows.append(dict(inst=k, truth=truth, milp_full=full_obj, agree_full=(truth == full_obj),
                         pairwise_obj=pw_obj, pairwise_plan_violates_highorder=pw_violates, pw_viol_triple=pw_viol_tri, pw_viol_accum=pw_viol_k,
                         conservative_truth=cons_truth, conservative_milp=cons_obj,
                         conservative_loss=(None if truth is None or cons_truth is None else truth - cons_truth),
                         conservative_false_infeasible=(truth is not None and cons_truth is None),
                         n_mus=len(mus), n_mus_size_ge3=sum(1 for m in mus if len(m) >= 3),
                         n_mus_size1_state_only=sum(1 for m in mus if len(m) == 1)))
    return rows


def main():
    t0 = time.time()
    hand_cases()
    rows = run_random()
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    feas = [r for r in rows if r["truth"] is not None]
    print("== RANDOM (n=8 drugs, N=%d, seed=20261117) ==" % len(rows))
    print(" feasible instances:", len(feas), " infeasible:", len(rows) - len(feas))
    print(" full MILP == brute force (incl. infeasible):", sum(r["agree_full"] for r in rows), "/", len(rows))
    pv = [r for r in rows if r["pairwise_plan_violates_highorder"] is not None]
    print(" pairwise-only plan violates higher-order/accumulation rule:", sum(r["pairwise_plan_violates_highorder"] for r in pv), "/", len(pv))
    print("   of which triple rule:", sum(bool(r["pw_viol_triple"]) for r in pv), " accumulation rule:", sum(bool(r["pw_viol_accum"]) for r in pv))
    print(" conservative pairwise: MILP==brute(conservative):", sum(r["conservative_truth"] == r["conservative_milp"] for r in rows), "/", len(rows))
    print(" conservative pairwise: optimum loss>0:", sum(1 for r in feas if r["conservative_loss"] not in (None, 0)), "/", len(feas),
          " false infeasible:", sum(r["conservative_false_infeasible"] for r in rows))
    print(" naive-union regimens with >=1 MUS of size>=3:", sum(1 for r in rows if r["n_mus_size_ge3"] > 0), "/", len(rows))
    print(" elapsed %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
