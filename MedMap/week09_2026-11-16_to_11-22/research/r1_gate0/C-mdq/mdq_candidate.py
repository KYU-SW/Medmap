"""9: MDQ 후보 (연속 W 폴리토프 위 정확 인증). core.GridModel / exact_grid 와 독립 작성.

MDQ 정의(후보):
  가설 공간 = {(임상 세계 s, 선호 완전응답 셀 R)}  (R = 모든 선호 질문에 답했을 때의 W 부분 폴리토프, 내부 비어있지 않음)
  라벨 L(s,R) = R 전체(모든 w∈R)에서 최적인 단일 선택지(꼭짓점 검사로 정확 인증) / 없으면 UNDET / 가능 선택지 없으면 NONE
  지식상태 K 에서 '확정' = K 와 양립하는 모든 (s,R) 의 L 이 동일 (UNDET 이면 '확정 불가 판정').
  9a 일괄 MDQ = 모든 답 조합에서 확정되는 최소 비용 질문 집합 (전수)
  9b 적응형 MDQ = 최악 비용 최소 적응 정책 (AND-OR minimax 탐색, 지식상태 memo)
"""
import itertools
import numpy as np
from scipy.spatial import ConvexHull

NAMES = "ABCDEFGH"


def _worlds(inst):
    ws = []
    for s in itertools.product((0, 1), repeat=inst.n):
        if all(not (s[i] == vi and s[j] != vj) for (i, vi, j, vj) in inst.deps):
            ws.append(np.array(s))
    return ws


def region_vertices(d, prefs, vec):
    """W = simplex ∩ {선호 답 vec} 의 꼭짓점 (닫힘 기준)."""
    rows = [np.eye(d)[i] for i in range(d)]
    for (j, k, rho), y in zip(prefs, vec):
        r = np.zeros(d)
        r[j] += 1.0
        r[k] -= rho
        rows.append(r if y == 1 else -r)
    rows = np.array(rows)
    if d == 1:
        return np.ones((1, 1)) if (rows @ np.ones(1) >= -1e-9).all() else np.zeros((0, 1))
    verts = []
    for comb in itertools.combinations(range(len(rows)), d - 1):
        A = np.vstack([rows[list(comb)], np.ones(d)])
        b = np.zeros(d)
        b[-1] = 1.0
        if abs(np.linalg.det(A)) < 1e-12:
            continue
        w = np.linalg.solve(A, b)
        if (rows @ w >= -1e-9).all():
            if not any(np.allclose(w, v, atol=1e-9) for v in verts):
                verts.append(w)
    return np.array(verts) if verts else np.zeros((0, d))


def region_volume(V, d):
    if len(V) == 0:
        return 0.0
    if d == 1:
        return 1.0
    if d == 2:
        return float(V[:, 0].max() - V[:, 0].min())
    if len(V) < d:
        return 0.0
    try:
        return float(ConvexHull(V[:, : d - 1]).volume)
    except Exception:
        return 0.0


class ContModel:
    def __init__(self, inst, vol_eps=1e-7):
        self.inst = inst
        self.T = len(inst.tests)
        self.pref_t = [t for t, q in enumerate(inst.tests) if q["kind"] == "pref"]
        prefs = [(inst.tests[t]["j"], inst.tests[t]["k"], inst.tests[t]["rho"]) for t in self.pref_t]
        self.worlds = _worlds(inst)
        self.cells = []      # (vec, vertices, volume)
        self.dropped_cells = 0
        for vec in itertools.product((0, 1), repeat=len(prefs)):
            V = region_vertices(inst.d, prefs, vec)
            vol = region_volume(V, inst.d)
            if vol > vol_eps:
                self.cells.append((vec, V, vol))
            elif len(V):
                self.dropped_cells += 1     # 측도 0 셀(경계)은 무시
        totvol = sum(c[2] for c in self.cells)
        pairs, labels, wts = [], [], []
        for wi, s in enumerate(self.worlds):
            S = inst.base + inst.delta @ s.astype(float)
            feas = np.array([all(s[i] != v for (i, v) in inst.contra[a]) for a in range(inst.m)])
            for ci, (vec, V, vol) in enumerate(self.cells):
                pairs.append((wi, ci))
                wts.append(vol / totvol / len(self.worlds))
                if not feas.any():
                    labels.append("NONE")
                    continue
                U = V @ S.T
                Uf = np.where(feas, U, -np.inf)
                mx = Uf.max(axis=1, keepdims=True)
                cert = [a for a in range(inst.m) if feas[a] and (U[:, a:a + 1] >= mx - 1e-9).all()]
                labels.append("|".join(NAMES[a] for a in cert) if cert else "UNDET")
        self.pairs = pairs
        self.labels = np.array(labels)
        self.wt = np.array(wts)
        P = len(pairs)
        self.pans = np.zeros((self.T, P), dtype=int)
        for t, q in enumerate(inst.tests):
            for p, (wi, ci) in enumerate(pairs):
                if q["kind"] == "clin":
                    s = self.worlds[wi]
                    self.pans[t, p] = int(sum(int(s[it]) << k for k, it in enumerate(q["items"])))
                else:
                    self.pans[t, p] = self.cells[ci][0][self.pref_t.index(t)]
        self.cost = np.array([q["cost"] for q in inst.tests], dtype=float)
        lab_ids = {l: i for i, l in enumerate(sorted(set(labels)))}
        self.lab_id = np.array([lab_ids[l] for l in labels])

    # ---------- 9a 일괄 ----------
    def batch_opt(self):
        T = self.T
        cands = sorted(((float(self.cost[list(Q)].sum()), Q) for r in range(T + 1)
                        for Q in itertools.combinations(range(T), r)), key=lambda x: (x[0], len(x[1])))
        for c, Q in cands:
            if not Q:
                if len(set(self.lab_id)) == 1:
                    return [], 0.0
                continue
            key = np.zeros(len(self.pairs), dtype=np.int64)
            for t in Q:
                key = key * 16 + self.pans[t]
            ok = True
            seen = {}
            for kk, l in zip(key.tolist(), self.lab_id.tolist()):
                if seen.setdefault(kk, l) != l:
                    ok = False
                    break
            if ok:
                return list(Q), c
        raise RuntimeError

    # ---------- 9b 적응형 ----------
    def adaptive_opt(self):
        memo = {}

        def V(cons):
            key = np.packbits(cons).tobytes()
            if key in memo:
                return memo[key][0]
            ids = self.lab_id[cons]
            if (ids == ids[0]).all():
                memo[key] = (0.0, None)
                return 0.0
            best, bt = np.inf, None
            for t in np.argsort(self.cost, kind="stable"):
                if self.cost[t] >= best:
                    continue
                vals = self.pans[t][cons]
                uv = np.unique(vals)
                if len(uv) < 2:
                    continue
                v = self.cost[t]
                for u in uv:
                    sub = cons & (self.pans[t] == u)
                    v = max(v, self.cost[t] + V(sub))
                    if v >= best:
                        break
                if v < best:
                    best, bt = v, int(t)
            memo[key] = (best, bt)
            return best
        root = np.ones(len(self.pairs), dtype=bool)
        val = V(root)
        self._memo = memo
        return val, len(memo)

    def adaptive_tree_stats(self):
        """9b 정책 트리의 쌍별 경로 비용 (최악/기대, 연속 가중치)."""
        cost = np.zeros(len(self.pairs))

        def rec(cons, c):
            key = np.packbits(cons).tobytes()
            bt = self._memo[key][1]
            if bt is None:
                cost[cons] = c
                return
            for u in np.unique(self.pans[bt][cons]):
                rec(cons & (self.pans[bt] == u), c + self.cost[bt])
        rec(np.ones(len(self.pairs), dtype=bool), 0.0)
        return float(cost.max()), float(cost @ self.wt / self.wt.sum())

    def undet_frac(self):
        return float(self.wt[self.labels == "UNDET"].sum() / self.wt.sum())

    # ---------- 이산 트리를 연속 진실로 평가 ----------
    def eval_grid_tree(self, tree):
        P = len(self.pairs)
        res = dict(off=np.zeros(P, bool), wrong=np.zeros(P, bool), hold=np.zeros(P, bool),
                   overask=np.zeros(P, bool), cost=np.zeros(P))

        def rec(node, idx, c, already):
            if len(idx) == 0:
                return
            labs = self.lab_id[idx]
            const = bool((labs == labs[0]).all())
            if node["leaf"]:
                decl = node["label"]
                tl = self.labels[idx]
                res["cost"][idx] = c
                res["wrong"][idx] = (tl != decl) & (decl != "UNDET")
                res["hold"][idx] = (decl == "UNDET") & (tl != "UNDET")
                return
            if const:
                res["overask"][idx] = True
            t = node["test"]
            vals = self.pans[t][idx]
            for u in np.unique(vals):
                sub = idx[vals == u]
                if int(u) in node["children"]:
                    rec(node["children"][int(u)], sub, c + self.cost[t], already)
                else:
                    res["off"][sub] = True
        rec(tree, np.arange(P), 0.0, False)
        w = self.wt / self.wt.sum()
        on = ~res["off"]
        return dict(off_c=float(w[res["off"]].sum()), wrong_det_c=float(w[res["wrong"] & on].sum()),
                    hold_c=float(w[res["hold"] & on].sum()), overask_c=float(w[res["overask"]].sum()),
                    worst_cost_c=float(res["cost"][on].max()) if on.any() else np.nan)
