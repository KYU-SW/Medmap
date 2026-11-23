"""MDQ Gate0 - core model (SYNTHETIC / 가상 규칙만 사용, 의학적 정확성 주장 없음).

이산(grid) 모델: 가설 h = (임상 세계 s, 가중치 격자점 w).
결론 f(h) = 안전 hard 제약을 만족하는 선택지 중 u(a,s,w) 최대 집합 ("A", "A|B", "NONE").
원자(atom) = 모든 질문에 대한 답 서명이 같은 가설 묶음 = (world, 선호 셀).
g(atom) = atom 안에서 f 가 상수면 그 값, 아니면 "UNDET" (모든 정보를 알아도 확정 불가).
"""
import itertools
from dataclasses import dataclass, field
import numpy as np

OPT_NAMES = "ABCDEFGH"
EPS = 1e-9


@dataclass
class Instance:
    name: str
    n: int
    d: int
    m: int
    base: np.ndarray            # (m, d)
    delta: np.ndarray           # (m, d, n)  점수 = base + delta @ s
    contra: list                # per option: list of (item, value) -> 그 값이면 금기(hard)
    deps: list                  # (i, vi, j, vj): c_i=vi 이면 c_j=vj (조건 의존성)
    tests: list                 # dict(kind='clin', items=(..), cost, src) | dict(kind='pref', j,k,rho,cost)
    grid_r: int
    prior_T: float = 0.2        # 확률 가정 평가용(편향 prior): P(c_i=T)
    meta: dict = field(default_factory=dict)


def answer_code_clin(s, items):
    return int(sum(int(s[it]) << k for k, it in enumerate(items)))


def answer_code_pref(w, j, k, rho):
    return int(w[j] >= rho * w[k] - 1e-12)


def enum_worlds(inst):
    out = []
    for s in itertools.product((0, 1), repeat=inst.n):
        ok = all(not (s[i] == vi and s[j] != vj) for (i, vi, j, vj) in inst.deps)
        if ok:
            out.append(s)
    return out


def simplex_grid(d, r):
    if d == 1:
        return np.ones((1, 1))
    pts = []
    for c in itertools.product(range(r + 1), repeat=d - 1):
        if sum(c) <= r:
            pts.append(list(c) + [r - sum(c)])
    return np.array(pts, dtype=float) / r


def feasible(inst, s):
    return np.array([all(s[i] != v for (i, v) in inst.contra[a]) for a in range(inst.m)])


def score_matrix(inst, s):
    return inst.base + inst.delta @ np.array(s, dtype=float)   # (m, d)


def label_from_utils(u, feas):
    if not feas.any():
        return "NONE"
    uu = np.where(feas, u, -np.inf)
    mx = uu.max()
    best = [OPT_NAMES[a] for a in range(len(u)) if feas[a] and uu[a] >= mx - EPS]
    return "|".join(best)


def world_prior(inst, worlds, p):
    pr = np.array([np.prod([p if x else 1 - p for x in s]) for s in worlds])
    return pr / pr.sum()


class GridModel:
    """이산 가설 모델. 모든 기준선/정확해(7,8)가 공유하는 입력."""

    def __init__(self, inst):
        self.inst = inst
        self.worlds = enum_worlds(inst)
        self.G = simplex_grid(inst.d, inst.grid_r)
        W, ng = len(self.worlds), len(self.G)
        self.T = len(inst.tests)
        self.pref_ids = [t for t, q in enumerate(inst.tests) if q["kind"] == "pref"]
        # 격자점별 선호 서명
        if self.pref_ids:
            sig = np.array([[answer_code_pref(w, inst.tests[t]["j"], inst.tests[t]["k"], inst.tests[t]["rho"])
                             for t in self.pref_ids] for w in self.G])
        else:
            sig = np.zeros((ng, 0), dtype=int)
        cells = {}
        cell_of_pt = np.zeros(ng, dtype=int)
        for gi in range(ng):
            key = tuple(sig[gi])
            cells.setdefault(key, len(cells))
            cell_of_pt[gi] = cells[key]
        self.cell_keys = [None] * len(cells)
        for k, v in cells.items():
            self.cell_keys[v] = k
        # 가설별 효용/결론
        self.hU = np.zeros((W * ng, inst.m))
        self.hFeas = np.zeros((W * ng, inst.m), dtype=bool)
        self.hLabel = []
        self.hAtom = np.zeros(W * ng, dtype=int)
        atoms = {}
        atom_labels = {}
        atom_count = {}
        for wi, s in enumerate(self.worlds):
            S = score_matrix(inst, s)
            fe = feasible(inst, s)
            U = self.G @ S.T
            for gi in range(ng):
                h = wi * ng + gi
                self.hU[h] = U[gi]
                self.hFeas[h] = fe
                lab = label_from_utils(U[gi], fe)
                self.hLabel.append(lab)
                key = (wi, cell_of_pt[gi])
                if key not in atoms:
                    atoms[key] = len(atoms)
                    atom_labels[key] = set()
                    atom_count[key] = 0
                atom_labels[key].add(lab)
                atom_count[key] += 1
                self.hAtom[h] = atoms[key]
        self.nA = len(atoms)
        self.atom_key = [None] * self.nA
        for k, v in atoms.items():
            self.atom_key[v] = k
        self.g = []
        for a in range(self.nA):
            labs = atom_labels[self.atom_key[a]]
            self.g.append(next(iter(labs)) if len(labs) == 1 else "UNDET")
        cnt = np.array([atom_count[self.atom_key[a]] for a in range(self.nA)], dtype=float)
        self.w_unif = cnt / (W * ng)
        wp = world_prior(inst, self.worlds, inst.prior_T)
        self.w_skew = np.array([wp[self.atom_key[a][0]] * cnt[a] / ng for a in range(self.nA)])
        # 테스트 답 / 마스크
        self.ans = np.zeros((self.T, self.nA), dtype=int)
        for t, q in enumerate(inst.tests):
            for a in range(self.nA):
                wi, ci = self.atom_key[a]
                if q["kind"] == "clin":
                    self.ans[t, a] = answer_code_clin(self.worlds[wi], q["items"])
                else:
                    self.ans[t, a] = self.cell_keys[ci][self.pref_ids.index(t)]
        self.masks = []
        for t in range(self.T):
            mk = {}
            for a in range(self.nA):
                mk[self.ans[t, a]] = mk.get(self.ans[t, a], 0) | (1 << a)
            self.masks.append(mk)
        self.ALL = (1 << self.nA) - 1
        self.label_mask = {}
        for a in range(self.nA):
            self.label_mask[self.g[a]] = self.label_mask.get(self.g[a], 0) | (1 << a)
        self.cost = np.array([q["cost"] for q in inst.tests], dtype=float)
        self.nbytes = (self.nA + 7) // 8

    # ---- helpers ----
    def to_bool(self, S):
        b = np.frombuffer(S.to_bytes(self.nbytes, "little"), dtype=np.uint8)
        return np.unpackbits(b, bitorder="little")[: self.nA].astype(bool)

    def first_atom(self, S):
        return (S & -S).bit_length() - 1

    def certified(self, S):
        lab = self.g[self.first_atom(S)]
        return (S & ~self.label_mask[lab]) == 0, lab

    def split(self, S, t):
        out = {}
        for v, mk in self.masks[t].items():
            sub = S & mk
            if sub:
                out[v] = sub
        return out

    def informative(self, S):
        return [t for t in range(self.T) if len(self.split(S, t)) >= 2]

    def weight(self, S, w):
        return float(w[self.to_bool(S)].sum())


# ---------------- 합성 인스턴스 생성기 ----------------
def make_instance(seed, n=4, d=3, m=4, pref="pairs", cost="uniform", contra_p=0.3,
                  n_deps=1, bundles=0, grid_r=None, exam_cost=4.0, record_cost=1.0, pref_cost=1.0):
    rng = np.random.default_rng(seed)
    base = rng.uniform(0, 1, (m, d))
    delta = np.zeros((m, d, n))
    for a in range(m):
        for i in range(n):
            if rng.random() < 0.4:
                delta[a, rng.integers(d), i] = rng.uniform(-0.6, 0.6)
    contra = []
    for a in range(m):
        lits = []
        if rng.random() < contra_p:
            lits.append((int(rng.integers(n)), 1))
        contra.append(lits)
    deps = []
    tries = 0
    while len(deps) < n_deps and tries < 100:
        tries += 1
        i, j = rng.choice(n, 2, replace=False)
        cand = (int(i), 1, int(j), 1)
        if cand not in deps:
            deps.append(cand)
    kinds = []
    tests = []
    for i in range(n):
        if cost == "uniform":
            kind, c = "record", 1.0
        else:
            kind = "exam" if rng.random() < 0.5 else "record"
            c = exam_cost if kind == "exam" else record_cost
        kinds.append(kind)
        tests.append(dict(kind="clin", items=(i,), cost=c, src=kind))
    for b in range(bundles):
        k = min(3, n)
        items = tuple(sorted(int(x) for x in rng.choice(n, k if n >= 3 else n, replace=False)))
        c = round(0.6 * sum(tests[i]["cost"] for i in items), 3)
        tests.append(dict(kind="clin", items=items, cost=c, src="bundle"))
    pairs = [(j, k) for j in range(d) for k in range(j + 1, d)]
    if pref == "none":
        pq = []
    elif pref == "one":
        pq = [(0, 1, 1.0)]
    elif pref == "pairs":
        pq = [(j, k, 1.0) for j, k in pairs]
    elif pref == "pairs+ratio":
        pq = [(j, k, 1.0) for j, k in pairs] + [(j, k, 2.0) for j, k in pairs]
    else:
        raise ValueError(pref)
    for (j, k, rho) in pq:
        tests.append(dict(kind="pref", j=j, k=k, rho=rho, cost=pref_cost))
    if grid_r is None:
        grid_r = {1: 1, 2: 20, 3: 10, 4: 6}[d]
    return Instance(name=f"s{seed}", n=n, d=d, m=m, base=base, delta=delta, contra=contra, deps=deps,
                    tests=tests, grid_r=grid_r, meta=dict(kinds=kinds, seed=seed))
