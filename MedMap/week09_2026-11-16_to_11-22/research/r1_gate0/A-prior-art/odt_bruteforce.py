# Brute force: hypotheses = joint worlds (binary tests), label = decision class.
# Compare policy minimizing worst-case cost vs policy minimizing expected cost under uniform prior.
import itertools, random, functools
def solve(H, labels, costs, n):
    @functools.lru_cache(None)
    def rec(hs, used):
        hs_l = [labels[h] for h in hs]
        if len(set(hs_l)) <= 1: return (0.0, 0.0)  # (worst, expected-sum)
        best_w = best_e = float('inf')
        for t in range(n):
            if used >> t & 1: continue
            parts = [tuple(h for h in hs if H[h][t]==v) for v in (0,1)]
            if any(len(p)==len(hs) for p in parts): continue
            ws, es = [], 0.0
            for p in parts:
                if not p: continue
                w, e = rec(p, used | 1<<t); ws.append(w); es += e + costs[t]*len(p)
            best_w = min(best_w, costs[t] + max(ws)); best_e = min(best_e, es)
        return (best_w, best_e)
    return rec
def eval_policy(H, labels, costs, n, objective):
    # build greedy-optimal policy for an objective, return (worst, expected)
    rec = solve(H, labels, costs, n)
    def run(hs, used):
        if len(set(labels[h] for h in hs)) <= 1: return (0.0, 0.0)
        cands = []
        for t in range(n):
            if used >> t & 1: continue
            parts = [tuple(h for h in hs if H[h][t]==v) for v in (0,1)]
            if any(len(p)==len(hs) for p in parts): continue
            ws, es = [], 0.0
            for p in parts:
                if not p: continue
                w, e = rec(p, used | 1<<t); ws.append(w); es += e + costs[t]*len(p)
            key = (costs[t]+max(ws), es) if objective=='wc' else (es, costs[t]+max(ws))
            cands.append((key, t, parts))
        _, t, parts = min(cands)
        W, E = 0.0, 0.0
        for p in parts:
            if not p: continue
            w, e = run(p, used | 1<<t); W = max(W, costs[t]+w); E += e + costs[t]*len(p)
        return (W, E)
    return run(tuple(range(len(H))), 0)
random.seed(0)
# CE-M2: batch vs adaptive on f = x1 ? x2 : x3 (all 8 worlds possible)
H = list(itertools.product((0,1), repeat=3)); lab = [h[1] if h[0] else h[2] for h in H]
print("CE-M2 adaptive worst-case cost (unit):", eval_policy(H, lab, [1,1,1], 3, 'wc')[0], "; batch needs all 3 variables (each essential)")
for trial in range(20000):
    n = 4; m = random.randint(4,7)
    H = random.sample(list(itertools.product((0,1), repeat=n)), m)
    lab = [random.randint(0,1) for _ in H]
    costs = [random.choice([1,2,3]) for _ in range(n)]
    wc = eval_policy(H, lab, costs, n, 'wc'); ex = eval_policy(H, lab, costs, n, 'ex')
    if ex[0] > wc[0] and ex[1] < wc[1]:
        print("CE-M3 found: worlds(test outcomes)=", H, "labels=", lab, "costs=", costs)
        print("  worst-case-optimal policy: worst=%g expected=%g" % (wc[0], wc[1]/m))
        print("  uniform-expected-optimal policy: worst=%g expected=%g" % (ex[0], ex[1]/m))
        break
