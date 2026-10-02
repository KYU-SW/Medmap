"""STEP16B smoke: 소표본으로 split·뷰·인코딩·IG·pool·selector 불변식 확인. 결과 파일 생성 없음."""
import sys, collections, numpy as np
sys.path.insert(0, ".")
import s16b_core as c

df = c.load_train(nrows=20000)
print("rows", len(df), "holdout frac", round(df.holdout.mean(), 4))
sem = c.Semantics(); enc = c.Encoder(sem)
tr = df[~df.holdout]
classes = sorted(df.PATHOLOGY.unique())
ig_table, missing = c.fit_ig_table(sem, tr.tokens.tolist(), tr.PATHOLOGY.tolist(), classes)
print("IG table ok; missing(default-fill) per excluded:", {k: v for k, v in missing.items() if v > 0})
qs, qpos, M, grp = c.pack_ig(sem, ig_table)
# 뷰 불변식
ho = df[df.holdout].head(300)
dup = 0; unsafe = 0; excl = 0
for r in ho.itertuples():
    v = c.make_view(sem, r.tokens, r.INITIAL_EVIDENCE, 5, "step16b_holdout", 42, r.row_index)
    assert len(v) == len(set(v)), "dup question"
    if any(q in sem.excluded for q in v): excl += 1
    for q, a in v.items():
        par = sem.parent.get(q)
        if par: assert v.get(par) == ("POS",), f"gate violation {q}"
        if a == ("NA",): assert par and v.get(par) != ("POS",)
print("views ok; excluded-in-view", excl, "| unsafe raised", unsafe)
# 모델 + selector 경로
states = [c.make_view(sem, r.tokens, r.INITIAL_EVIDENCE, 3, "step16b_train", 42, r.row_index) for r in tr.head(4000).itertuples()]
X = enc.transform(states, tr.head(4000).AGE.values, tr.head(4000).SEX.values)
m = c.fit_model(X, tr.head(4000).PATHOLOGY.values)
hs = [c.make_view(sem, r.tokens, r.INITIAL_EVIDENCE, 3, "step16b_holdout", 42, r.row_index) for r in ho.itertuples()]
P = m.predict_proba(enc.transform(hs, ho.AGE.values, ho.SEX.values))
cls = list(m.classes_); cpos = {cc: i for i, cc in enumerate(cls)}
post = P[0]
full = np.zeros(len(classes)); 
pool = [q for q in sem.qids if sem.currently_eligible(q, hs[0])]
bpool = [q for q in pool if sem.dtype[q] == "B"]
print("pool", len(pool), "binary pool", len(bpool), "excluded in pool", [q for q in pool if q in sem.excluded])
# IG: 모델 클래스 순서로 정렬된 ig_table 필요 → 확인만
ig = c.ig_all(post if len(post) == len(classes) else np.pad(post, (0, len(classes) - len(post))), M, grp, len(qs))
best = sorted([(q) for q in pool], key=lambda q: (-round(float(ig[qpos[q]]), 12), c.qnum(q)))[0]
print("IG pick", best, "IG value", round(float(ig[qpos[best]]), 4), "| classes model", len(cls), "global", len(classes))
print("SMOKE_OK")
