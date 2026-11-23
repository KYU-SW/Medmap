"""E3 [가상] SYNTHETIC: 근거 확실성 전파 규칙 간 불일치 전수 탐색.

구조: 결론 X 와 not-X 가 서로 반박(rebut). 각 쪽은 k in {1,2} 개 논증, 각 논증은 길이 L in {1,2}
      의 사슬(전제 근거 확실성 + 규칙 강도). 원소 등급 1..4 (very low, low, moderate, high).
방법
  WL  : 논증 강도 = min(사슬)  [GRADE 간접추정 '낮은 쪽', possibilistic, ASPIC+ weakest-link(elitist)]
        결론 강도 = max(논증)  [GRADE NMA 일치 시 '높은 쪽', possibilistic max; ASPIC+ grounded(rebut-only)와 동일 판정]
  LL  : 논증 강도 = 마지막 원소 [ASPIC+ last-link], 결론 = max (grounded, rebut-only)
  PROB: 등급 -> 확률 {1:.2,2:.4,3:.6,4:.8} [가상 매핑], 논증 = 곱, 결론 = noisy-or(독립 가정)
판정: X / notX / UNDEC(동점)
ASPIC+ grounded 판정은 따로 구현해 WL/LL max-비교와 같은지 확인 (구현 대조).
출력: logs/e3_certainty.log, results_e3_certainty_summary.csv
"""
import csv, itertools, time
import numpy as np

P = {1: .2, 2: .4, 3: .6, 4: .8}
SHAPES = [(k, L) for k in (1, 2) for L in (1, 2)]


def verdict(a, b, tol=1e-12):
    if a > b + tol: return "X"
    if b > a + tol: return "notX"
    return "UNDEC"


def side_strength(args, method):
    if method == "WL":
        return max(min(c) for c in args)
    if method == "LL":
        return max(c[-1] for c in args)
    if method == "PROB":
        q = 1.0
        for c in args:
            q *= 1 - np.prod([P[e] for e in c])
        return 1 - q
    raise ValueError


def aspic_grounded(argsX, argsN, link):
    """rebut-only 대칭 공격, 선호: A 가 B 를 defeat ⇔ not(str(A) < str(B)). grounded 확장 계산."""
    st = (lambda c: min(c)) if link == "WL" else (lambda c: c[-1])
    nodes = [("X", i, st(c)) for i, c in enumerate(argsX)] + [("N", i, st(c)) for i, c in enumerate(argsN)]
    defeats = {(u, v) for u in nodes for v in nodes if u[0] != v[0] and not (u[2] < v[2])}
    IN, OUT = set(), set()
    changed = True
    while changed:
        changed = False
        for v in nodes:
            if v in IN or v in OUT: continue
            attackers = [u for u in nodes if (u, v) in defeats]
            if all(u in OUT for u in attackers):
                IN.add(v); changed = True
        for v in nodes:
            if v not in OUT and any((u, v) in defeats and u in IN for u in nodes):
                OUT.add(v); changed = True
    xin = any(v[0] == "X" and v in IN for v in nodes)
    nin = any(v[0] == "N" and v in IN for v in nodes)
    return "X" if xin and not nin else ("notX" if nin and not xin else "UNDEC")


def main():
    t0 = time.time()
    rows = []
    tot = 0
    dis = {("WL", "LL"): 0, ("WL", "PROB"): 0, ("LL", "PROB"): 0}
    all3 = 0
    opp = {("WL", "LL"): 0, ("WL", "PROB"): 0, ("LL", "PROB"): 0}
    aspic_mismatch = 0
    example = {}
    for (kx, Lx), (kn, Ln) in itertools.product(SHAPES, SHAPES):
        nx, nn = kx * Lx, kn * Ln
        for vals in itertools.product(range(1, 5), repeat=nx + nn):
            ax = [vals[i * Lx:(i + 1) * Lx] for i in range(kx)]
            an = [vals[nx + i * Ln: nx + (i + 1) * Ln] for i in range(kn)]
            v = {m: verdict(side_strength(ax, m), side_strength(an, m)) for m in ("WL", "LL", "PROB")}
            for link in ("WL", "LL"):
                if aspic_grounded(ax, an, link) != v[link]:
                    aspic_mismatch += 1
            tot += 1
            for pair in dis:
                if {v[pair[0]], v[pair[1]]} == {"X", "notX"}:
                    opp[pair] += 1
                if v[pair[0]] != v[pair[1]]:
                    dis[pair] += 1
                    key = pair
                    if key not in example or (len(vals) < len(example[key][0]) + len(example[key][1])):
                        example[key] = (ax, an, dict(v))
            if len(set(v.values())) == 3:
                all3 += 1
                if "ALL3" not in example or (nx + nn) < sum(len(c) for c in example["ALL3"][0] + example["ALL3"][1]):
                    example["ALL3"] = (ax, an, dict(v))
    print("== E3 exhaustive: structures evaluated =", tot)
    print(" ASPIC+ grounded implementation vs max-comparison mismatches:", aspic_mismatch)
    for pair, c in dis.items():
        print(f" disagree {pair}: {c} ({100*c/tot:.1f}%)  example: X-args={example[pair][0]} notX-args={example[pair][1]} -> {example[pair][2]}")
    for pair, c in opp.items():
        print(f" OPPOSITE strict verdicts (X vs notX, ties excluded) {pair}: {c} ({100*c/tot:.1f}%)")
    print(f" all three different: {all3} ({100*all3/tot:.2f}%)  example: {example.get('ALL3')}")
    # GRADE NMA 규칙과 possibilistic min/max 동일성 (정의 대입)
    same = 0; n = 0
    for d1, d2, dd in itertools.product(range(1, 5), repeat=3):
        indirect = min(d1, d2)              # GRADE: 간접 = 두 직접 중 낮은 쪽
        grade_net = max(dd, indirect)       # GRADE: 일치 시 높은 쪽
        poss = max(dd, min(d1, d2))         # possibilistic: 사슬 min, 대안 근거 max
        same += grade_net == poss; n += 1
    print(f" GRADE-NMA(coherent) vs possibilistic min/max identical: {same}/{n}")
    # 손 사례: 독립 근거 누적(accrual)
    hx = [(2,), (2,)]; hn = [(3,)]
    print(" HAND accrual: X has two independent LOW args, notX one MODERATE arg ->",
          {m: verdict(side_strength(hx, m), side_strength(hn, m)) for m in ("WL", "LL", "PROB")})
    hx = [(1, 4)]; hn = [(3, 3)]
    print(" HAND link: X = [very-low evidence, high-strength rule], notX = [moderate, moderate] ->",
          {m: verdict(side_strength(hx, m), side_strength(hn, m)) for m in ("WL", "LL", "PROB")})
    with open("results_e3_certainty_summary.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["metric", "count", "total", "pct"])
        for pair, c in dis.items(): w.writerow([f"disagree_{pair[0]}_{pair[1]}", c, tot, round(100*c/tot, 3)])
        for pair, c in opp.items(): w.writerow([f"opposite_{pair[0]}_{pair[1]}", c, tot, round(100*c/tot, 3)])
        w.writerow(["all_three_differ", all3, tot, round(100*all3/tot, 3)])
        w.writerow(["aspic_impl_mismatch", aspic_mismatch, 2*tot, 0])
        w.writerow(["grade_nma_eq_possibilistic", same, n, round(100*same/n, 1)])
    print(" elapsed %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
