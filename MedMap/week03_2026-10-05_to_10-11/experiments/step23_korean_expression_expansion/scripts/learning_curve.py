"""STEP23 learning curve. TARGET_20 class 당 학습 표현 수를 k 로 제한(CONFUSER_57 은 그대로), seed 3개 평균.

- hyperparameter = selection.json 의 EXPANDED 선택값 고정(곡선 지점마다 재선택하지 않음).
- dev core Top-1 = 곡선의 기준. FIXED_REGRESSION_TEST core Top-1 은 서술용(어떤 선택에도 쓰지 않음).
- pool = class 의 ORIGINAL + STEP23 VALID 표현. pool 이 k 보다 작으면 전부 사용(실제 평균 개수 기록).
출력: outputs/learning_curve.csv
"""
import json
import random
import statistics

import s23_common as S

KS = [5, 10, 20, 30, 40, 10 ** 6]
SEEDS = [42, 43, 44]


def main():
    sel = json.load(open(S.OUT / "selection.json", encoding="utf-8"))
    rows = S.read_csv(S.DATA / "expanded_train_expressions.csv")
    conf = [(r["normalized_expression"], r["canonical_id"]) for r in rows if r["group"] == "CONFUSER_57"]
    pool = {c: [r["normalized_expression"] for r in rows if r["canonical_id"] == c] for c in S.TARGET20}
    gold = S.load_gold()
    sets = {"dev_core": [g for g in gold if g["split"] == "dev" and S.is_core(g)],
            "regression_core(descriptive)": [g for g in gold if g["split"] == "test" and S.is_core(g)]}
    out = []
    for fam in S.FAMILIES:
        p = sel["conditions"]["EXPANDED"]["families"][fam]["params"]
        for k in KS:
            acc = {s: [] for s in sets}
            sizes = []
            for seed in SEEDS:
                rng = random.Random(seed)
                X, y = [x for x, _ in conf], [c for _, c in conf]
                for c in S.TARGET20:
                    pl = sorted(pool[c])
                    take = pl if len(pl) <= k else rng.sample(pl, k)
                    sizes.append(len(take))
                    X += take
                    y += [c] * len(take)
                m = S.build(fam, p).fit(X, y)
                for sn, rs in sets.items():
                    tk = S.topk(m, [S.norm(g["text_ko"]) for g in rs])
                    acc[sn].append(S.score(rs, {g["utterance_id"]: [c for c, _ in t] for g, t in zip(rs, tk)})["top1"])
            row = {"model": fam, "k_cap_per_target_class": "ALL" if k == KS[-1] else k,
                   "mean_examples_per_target_class": round(sum(sizes) / len(sizes), 2), "n_seeds": len(SEEDS)}
            for sn in sets:
                row[f"{sn}_top1_mean"] = round(statistics.mean(acc[sn]), 4)
                row[f"{sn}_top1_std"] = round(statistics.pstdev(acc[sn]), 4)
            out.append(row)
            print(row)
    S.write_csv(S.OUT / "learning_curve.csv", out)


if __name__ == "__main__":
    main()
