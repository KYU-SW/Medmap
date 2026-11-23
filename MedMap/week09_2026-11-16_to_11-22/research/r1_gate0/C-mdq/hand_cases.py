"""손계산 소형 사례 (SYNTHETIC). 예상값은 코드 실행 전에 손으로 계산해 EXPECTED 에 기록함."""
import sys, json
import numpy as np
sys.path.insert(0, "/home/<user>/medmap-gate0-parallel/C-mdq")
from core import Instance, GridModel
from methods import build_tree, tree_metrics, hitting_set_milp
from exact_grid import batch_bruteforce, adaptive_minimax, adaptive_expected, axp_lower_bound
from mdq_candidate import ContModel


def clin(i, c=1.0):
    return dict(kind="clin", items=(i,), cost=c, src="record")


def pref(j, k, rho=1.0, c=1.0):
    return dict(kind="pref", j=j, k=k, rho=rho, cost=c)


def inst(name, n, d, base, delta=None, contra=None, deps=(), tests=(), r=9):
    base = np.array(base, dtype=float)
    m = base.shape[0]
    if delta is None:
        delta = np.zeros((m, d, n))
    return Instance(name=name, n=n, d=d, m=m, base=base, delta=np.array(delta, dtype=float),
                    contra=contra or [[] for _ in range(m)], deps=list(deps), tests=list(tests), grid_r=r)


CASES = []
# H1: 안전 hard 제약. A 가 모든 기준 우세지만 c0=T 면 금기 -> B. 선호로 상쇄 불가.
CASES.append((inst("H1_safety", 1, 1, [[2.0], [1.0]], contra=[[(0, 1)], []], tests=[clin(0)], r=1),
              dict(adaptive=1, batch=1, axp=1, exp_u=1.0, cont_adaptive=1, cont_batch=1, g_set=["A", "B"])))
# H2: 선호 질문 1개로 확정 (격자 r=9, 동점점 없음)
CASES.append((inst("H2_pref", 0, 2, [[1, 0], [0, 1]], tests=[pref(0, 1)], r=9),
              dict(adaptive=1, batch=1, axp=1, exp_u=1.0, cont_adaptive=1, cont_batch=1, g_set=["A", "B"])))
# H2b: 같은 문제, 격자 r=10 -> w=(.5,.5) 동점점이 yes 셀에 포함 -> 격자 g(yes)=UNDET (격자 인공물)
CASES.append((inst("H2b_tie_grid", 0, 2, [[1, 0], [0, 1]], tests=[pref(0, 1)], r=10),
              dict(adaptive=1, batch=1, axp=1, exp_u=1.0, cont_adaptive=1, cont_batch=1, g_set=["B", "UNDET"],
                   grid_tree_hold_c=0.5)))
# H3: 모든 정보를 알아도 확정 불가 -> 질문 0개로 '확정 불가' 판정해야 함
CASES.append((inst("H3_undeterminable", 0, 3, [[1, 0, 0], [0, 1, 0], [0, 0, 1]], tests=[pref(0, 1)], r=10),
              dict(adaptive=0, batch=0, axp=0, exp_u=0.0, cont_adaptive=0, cont_batch=0, g_set=["UNDET"])))
# H4: 적응형 < 일괄. c0 결과에 따라 c1 또는 c2 만 필요
CASES.append((inst("H4_adaptive_gap", 3, 1, [[4], [3], [2], [1]],
                   contra=[[(0, 0), (1, 1)], [(0, 0)], [(0, 1), (2, 1)], [(0, 1)]],
                   tests=[clin(0), clin(1), clin(2)], r=1),
              dict(adaptive=2, batch=3, axp=2, exp_u=2.0, cont_adaptive=2, cont_batch=3, g_set=["A", "B", "C", "D"])))
# H5: 다수결(선형 효용). 사례별 충분근거(AXp)=2 이지만 적응형 최악=3 -> MDQ ≠ AXp
d5 = np.zeros((2, 1, 3)); d5[0, 0, :] = 1.0
CASES.append((inst("H5_majority", 3, 1, [[0.0], [1.5]], delta=d5, tests=[clin(0), clin(1), clin(2)], r=1),
              dict(adaptive=3, batch=3, axp=2, exp_u=2.5, cont_adaptive=3, cont_batch=3, g_set=["A", "B"])))
# H6: 묶음 검사(한 질문이 두 조건 확인, 비용 1.5)
CASES.append((inst("H6_bundle", 2, 1, [[3], [2], [1]], contra=[[(0, 1)], [(1, 1)], []],
                   tests=[clin(0), clin(1), dict(kind="clin", items=(0, 1), cost=1.5, src="bundle")], r=1),
              dict(adaptive=1.5, batch=1.5, axp=1.5, exp_u=1.5, cont_adaptive=1.5, cont_batch=1.5, g_set=["A", "B", "C"])))
# H7: 얇은 영역. 격자(r=9)에서 B 는 어디서도 최적 아님 -> 격자 기반 정답은 A/C 로 '확정' 선언, 연속 진실은 UNDET
CASES.append((inst("H7_thin_region", 0, 2, [[0, 1], [0.53, 0.53], [1, 0]], tests=[pref(0, 1)], r=9),
              dict(adaptive=1, batch=1, axp=1, exp_u=1.0, cont_adaptive=0, cont_batch=0, g_set=["A", "C"],
                   grid_tree_wrong_c=1.0)))


def run():
    rows = []
    allok = True
    for I, E in CASES:
        M = GridModel(I)
        C = ContModel(I)
        v8, ch8, _ = adaptive_minimax(M)
        Q7, c7 = batch_bruteforce(M)
        Q6, c6, _ = hitting_set_milp(M)
        axp, _ = axp_lower_bound(M)
        ve, _ = adaptive_expected(M, M.w_unif)
        v9, _ = C.adaptive_opt()
        Q9, c9 = C.batch_opt()
        tree8 = build_tree(M, ch8)
        ce = C.eval_grid_tree(tree8)
        got = dict(adaptive=v8, batch=c7, milp=c6, axp=axp, exp_u=round(ve, 6), cont_adaptive=v9, cont_batch=c9,
                   g_set=sorted(set(M.g)), grid_tree_hold_c=round(ce["hold_c"], 6),
                   grid_tree_wrong_c=round(ce["wrong_det_c"], 6))
        ok = True
        for k, v in E.items():
            if isinstance(v, list):
                good = got[k] == sorted(v)
            else:
                good = abs(got[k] - v) < 1e-6
            ok &= good
        ok &= abs(c6 - c7) < 1e-9
        allok &= ok
        print(f"[{'PASS' if ok else 'FAIL'}] {I.name}: expected={json.dumps(E)}")
        print(f"        got={json.dumps({k: (float(v) if not isinstance(v, list) else v) for k, v in got.items()})}")
        rows.append(dict(case=I.name, status="PASS" if ok else "FAIL",
                         **{f"exp_{k}": (v if not isinstance(v, list) else "/".join(v)) for k, v in E.items()},
                         **{f"got_{k}": (v if not isinstance(v, list) else "/".join(v)) for k, v in got.items()}))
    import pandas as pd
    pd.DataFrame(rows).to_csv("/home/<user>/medmap-gate0-parallel/C-mdq/results_hand_cases.csv", index=False)
    print("ALL_PASS" if allok else "SOME_FAIL")


if __name__ == "__main__":
    run()
