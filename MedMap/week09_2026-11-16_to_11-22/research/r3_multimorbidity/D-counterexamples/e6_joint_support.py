"""E6 [가상] SYNTHETIC: 연구 대상 범위 vs 적용 대상. 주변(Table 1 범위) 비교 vs 결합 지지(볼록 껍질 LP).

시험 IPD: d 차원 상관 정규(rho=0.7) n=300 (가상 공변량, 표준화 단위).
환자: 시험의 각 공변량 [min,max] 상자 안에서 균일 추출 -> 주변 범위 비교는 모두 '범위 내'.
판정: 볼록 껍질 소속 LP (sum lam_k x_k = p, sum lam=1, lam>=0) 가능 여부 (King & Zeng 2006 WhatIf 의 껍질 기준과 같은 형태).
출력: logs/e6_joint_support.log, results_e6_joint_support.csv
"""
import csv, time
import numpy as np
from scipy.optimize import linprog


def in_hull(X, p):
    n = X.shape[0]
    A_eq = np.vstack([X.T, np.ones((1, n))]); b_eq = np.append(p, 1.0)
    r = linprog(np.zeros(n), A_eq=A_eq, b_eq=b_eq, bounds=(0, None), method="highs")
    return r.status == 0


def main():
    t0 = time.time()
    rng = np.random.default_rng(20261117)
    rows = []
    # 손 사례 2D: 나이(가상)·eGFR(가상) 음의 상관
    X = rng.multivariate_normal([0, 0], [[1, -.8], [-.8, 1]], size=300)
    p = np.array([X[:, 0].max() * .9, X[:, 1].max() * .9])  # '고령 + 높은 eGFR' 조합
    box = bool(np.all((p >= X.min(0)) & (p <= X.max(0))))
    print(f"HAND 2D [가상] corr=-0.8: patient=({p[0]:.2f},{p[1]:.2f}) within marginal ranges={box}, in convex hull={in_hull(X, p)}")
    for d in (2, 3, 5, 8):
        C = np.full((d, d), .7); np.fill_diagonal(C, 1)
        X = rng.multivariate_normal(np.zeros(d), C, size=300)
        lo, hi = X.min(0), X.max(0)
        P = rng.uniform(lo, hi, size=(200, d))
        inside = [in_hull(X, q) for q in P]
        rows.append(dict(d=d, n_trial=300, n_patients=200, within_marginal=200, in_hull=int(sum(inside)),
                         marginal_says_in_but_outside_hull=200 - int(sum(inside))))
        print(f" d={d}: patients within all marginal ranges=200, inside joint convex hull={sum(inside)}, "
              f"marginal-in/joint-out={200-sum(inside)} ({(200-sum(inside))/2:.1f}%)")
    with open("results_e6_joint_support.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(" elapsed %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
