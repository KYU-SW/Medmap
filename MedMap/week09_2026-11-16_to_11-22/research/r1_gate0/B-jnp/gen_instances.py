"""SYNTHETIC JNP instance generator (가상 조건 c1..ck, 가상 선택지 O1..On). 실제 치료 규칙 아님.

Instance dict format
  k       : 조건 수
  obs     : 각 조건 관측 'T' | 'F' | 'U'(미확인) | 'C'(상충 기록: T 출처와 F 출처가 모두 있음)
  cw      : 'C' 조건에 대해 closed-world 기준선이 쓰는 '마지막 기록' 값 ('T'/'F'), 그 외 None
  deps    : [["imp",a,b]] (c_a=T -> c_b=T),  [["excl",a,b]] (not (c_a=T and c_b=T))
  n, m    : 선택지 수, 기준 수
  rules   : [[o, [[i, val], ...]]]  : 모든 literal (c_i == val) 이 참이면 o 금기(부적격)
  base    : n x m 기준 점수 (None = 점수 정의 없음)
  mods    : [[o, j, i, delta]] : c_i=T 이면 v_j(o) += delta  (상태 의존 점수)
  ordinal : [[a,b]] : w_a >= w_b
  bounds  : [[j,"lo"|"hi",val]]
  가중치 polytope W = { w >= 0, sum w = 1, ordinal, bounds }
"""
import json
import numpy as np


def gen(seed, k=10, nU=6, n=6, m=4, n_rules=6, dep_density=0.3, conflict_rate=0.1,
        n_wcons=2, n_mods=3, missing_rate=0.0):
    rng = np.random.default_rng(seed)
    k = max(k, nU)
    hidden = rng.integers(0, 2, size=k)  # hidden consistent world -> S never empty
    perm = rng.permutation(k)
    unk = sorted(int(x) for x in perm[:nU])
    obs, cw = [], []
    for i in range(k):
        if i in unk:
            if rng.random() < conflict_rate:
                obs.append('C')
                cw.append('T' if rng.random() < 0.5 else 'F')
            else:
                obs.append('U')
                cw.append(None)
        else:
            obs.append('T' if hidden[i] else 'F')
            cw.append(None)
    deps = []
    n_deps = int(round(dep_density * k))
    tries = 0
    while len(deps) < n_deps and tries < 1000:
        tries += 1
        a, b = (int(x) for x in rng.choice(k, 2, replace=False))
        if rng.random() < 0.7:
            if hidden[a] and not hidden[b]:
                continue
            d = ["imp", a, b]
        else:
            if hidden[a] and hidden[b]:
                continue
            d = ["excl", a, b]
        if d not in deps:
            deps.append(d)

    def pick_cond():
        if unk and rng.random() < 0.7:
            return int(rng.choice(unk))
        return int(rng.integers(0, k))

    rules = []
    for _ in range(n_rules):
        o = int(rng.integers(0, n))
        L = int(rng.integers(1, 3))
        lits, used = [], set()
        for _ in range(L):
            i = pick_cond()
            if i in used:
                continue
            used.add(i)
            lits.append([i, int(rng.integers(0, 2))])
        rules.append([o, lits])
    base = np.round(rng.random((n, m)), 4).tolist()
    for o in range(n):
        for j in range(m):
            if rng.random() < missing_rate:
                base[o][j] = None
    mods = []
    for _ in range(n_mods):
        mods.append([int(rng.integers(0, n)), int(rng.integers(0, m)), pick_cond(),
                     float(np.round(rng.uniform(-0.3, 0.3), 4))])
    order = [int(x) for x in rng.permutation(m)]
    ordinal, bounds = [], []
    oi = 0
    for t in range(n_wcons):
        if t % 2 == 0 and oi < m - 1:
            ordinal.append([order[oi], order[oi + 1]])
            oi += 1
        else:
            j = int(rng.integers(0, m))
            if rng.random() < 0.5:
                bounds.append([j, "lo", float(np.round(rng.uniform(0.02, 0.9 / m), 4))])
            else:
                bounds.append([j, "hi", float(np.round(rng.uniform(1.1 / m, 0.9), 4))])
    return dict(name=f"seed{seed}", k=k, obs=obs, cw=cw, deps=deps, n=n, m=m, rules=rules,
                base=base, mods=mods, ordinal=ordinal, bounds=bounds)


if __name__ == "__main__":
    print(json.dumps(gen(0), indent=1))
