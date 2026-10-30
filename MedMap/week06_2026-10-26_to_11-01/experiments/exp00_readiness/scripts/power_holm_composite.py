"""A안(안전·효율 IUT 를 최대 p 로 Holm family 에 합침)의 검정력 영향 — 정규 근사 설계 계산(실데이터 미사용).

대응 비율 차의 SE ≈ sqrt(d / n)  (d = 두 모델 결과가 다른 사례 비율, 참 Δ≈0 근처).
비열등 성분 검정력 = Φ((margin − Δ_true)/SE − z_{1−α_level}).
Holm 에서 성분이 받는 수준: 최악 = α/m (첫 단계), 최선 = α (마지막 단계).
사용: python power_holm_composite.py --out <md>
"""
from __future__ import annotations

import argparse
from statistics import NormalDist

N = NormalDist()
ALPHA, M = 0.025, 6


def power(margin, delta_true, d, n, level):
    se = (d / n) ** 0.5
    return N.cdf((margin - delta_true) / se - N.inv_cdf(1 - level))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    levels = {"Holm 최악 α/6": ALPHA / M, "Holm 중간 α/3": ALPHA / 3, "IUT·Holm 최선 α": ALPHA}
    L = ["# A안 검정력 근사표 (정규 근사, 실데이터 미사용)", "",
         f"- 단측 α={ALPHA}, Holm m={M}. SE=sqrt(d/n). 참 Δ 는 '나빠짐' 방향 양수.",
         "- 행 = 부분집합 크기 n, 불일치율 d, 참 Δ, margin. 열 = 성분이 받는 유의수준별 검정력.", "",
         "| margin | 참 Δ | d | n | " + " | ".join(levels) + " |", "|---|---|---|---|" + "---|" * len(levels)]
    for margin in (0.005, 0.01):
        for dt in (0.0, 0.002):
            for d in (0.01, 0.03, 0.05):
                for n in (5_000, 20_000, 50_000, 100_000):
                    row = [f"{power(margin, dt, d, n, lv):.3f}" for lv in levels.values()]
                    L.append(f"| {margin*100:.1f}%p | {dt*100:.1f}%p | {d:.2f} | {n:,} | " + " | ".join(row) + " |")
    L += ["", "해석 규칙(사전 고정): FINAL 잠금 전 SELECT 의 실제 d·n 을 이 식에 넣어 각 성분 검정력을 rg record 로 남긴다.",
          "최대 p 합성 가설의 검정력 ≤ 성분 검정력의 최솟값(성분이 독립이면 곱)."]
    open(a.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
