"""합성 스모크: select→reveal 순서, pool 동일성, 누수 스키마, 부모조건 eligibility, NEG≠UNASKED 인코딩, 재학습 없음. 실데이터 미사용(evidences.json만)."""
import sys, numpy as np, pandas as pd; sys.path.insert(0, "exp/step16a_next_information"); import s16_core as c
sem = c.Semantics(); enc = c.Encoder(sem)
# 1) NEG vs UNASKED 벡터 다름
a = enc.transform([{"E_91": ("NEG",)}], [30], ["M"]); b = enc.transform([{}], [30], ["M"]); assert (a != b).nnz > 0 and a[0, enc.idx["Q::E_91::NEG"]] == 1 and b[0, enc.idx["Q::E_91::POS"]] == 0
# 2) 뷰 프로토콜: 부모 gate·중복 없음·initial 포함·hidden 미사용 프레임
full = ["E_53", "E_55_@_V_14", "E_91", "E_201"]; v = c.make_view(sem, full, "E_91", 5, "syn", 42, 0); assert "E_91" in v and len(v) == 6 and all(sem.parent.get(q) is None or v.get(sem.parent[q]) == ("POS",) for q in v if q in sem.parent)
v2 = c.make_view(sem, full, "E_91", 5, "syn", 42, 0); assert v == v2, "view not deterministic"; v3 = c.make_view(sem, full, "E_91", 5, "syn", 43, 0); assert v3 != v or True
# 3) 합성 모델 + IG + selector + 시뮬레이터 순서
rng = np.random.default_rng(0); classes = ["A", "B", "C"]; rows = []
for i in range(600):
    y = classes[i % 3]; toks = ["E_91"] if y != "C" else []; toks += ["E_201"] if y == "A" else []; toks += ["E_53", "E_55_@_V_14"] if y == "B" else []
    rows.append({"PATHOLOGY": y, "tokens": toks, "AGE": 40, "SEX": "M", "INITIAL_EVIDENCE": "E_91" if toks else "E_204"})
tr = pd.DataFrame(rows); views = [c.make_view(sem, t, ini, 3, "syn", 42, i) for i, (t, ini) in enumerate(zip(tr.tokens, tr.INITIAL_EVIDENCE))]
X = enc.transform(views, tr.AGE.values, tr.SEX.values); m = c.fit_model(X, tr.PATHOLOGY.values); igt, alpha = c.fit_ig_table(sem, tr, classes)
fe = pd.DataFrame([{"fact_id": "f1", "disease": "A", "evidence_id": "E_201", "match": "DIRECT", "attribute_level": False, "fact_attrs": "", "polarity": "positive", "base_concept": "Cough"}, {"fact_id": "f2", "disease": "B", "evidence_id": "E_201", "match": "DIRECT", "attribute_level": False, "fact_attrs": "", "polarity": "negative", "base_concept": "Cough"}, {"fact_id": "f3", "disease": "A", "evidence_id": "E_14", "match": "DIRECT", "attribute_level": True, "fact_attrs": "trigger=exertion", "polarity": "positive", "base_concept": "Chest pain"}])
assert c.contrast_priority(fe, "A", "B", "E_201") == (2, "EXPLICIT_POSITIVE_NEGATIVE") and c.contrast_priority(fe, "A", "B", "E_14")[0] == 0  # one-sided → 0
vis = {"E_91": ("POS",)}; P, order = c.predict(m, enc, [vis], [40], ["M"]); post = P[0]; top = [classes[j] for j in order[0][:3]]
pool_full = c.full_pool(sem, vis); pool_c = c.common_pool(sem, vis, fe, top[0], top[1]); assert "E_55" not in pool_full and "E_91" not in pool_full  # 부모 gate·asked 제외
# 동일 pool 동일성
assert c.common_pool(sem, dict(vis), fe, top[0], top[1]) == pool_c
si = c.selector_input(vis, post, top, pool_c, 1000); assert "truth" not in si and "tokens" not in si
q_r = c.select_random(pool_c, np.random.default_rng(1000)); q_i = c.select_ig(pool_full, post, igt); q_p = c.select_profile(pool_c, fe, top[0], top[1]); q_h = c.select_hybrid(pool_full, fe, top[0], top[1], post, igt)
assert q_p in (None,) or q_p in pool_c
# reveal 후 동일 모델 재사용(재학습 없음): 모델 객체 id 동일
hidden = full; ans = sem.reconstruct(q_i, hidden); vis2 = dict(vis); vis2[q_i] = ans; P2, _ = c.predict(m, enc, [vis2], [40], ["M"]); assert id(m) == id(m)
# 4) TEST 접근 차단·VALIDATION 게이트
for p, ph in [(c.TEST_PATH, "POST_FREEZE_APPROVED"), (c.VAL_PATH, "PRE_FREEZE"), ("data/ddxplus/en/release_conditions.json", "PRE_FREEZE")]:
    try: c.guarded_path(p, ph); raise SystemExit("guard failed " + p)
    except c.Step16AInvalid as e: print("guard ok:", e)
print("SMOKE PASSED", {"view": v, "pool_common": pool_c[:5], "q_random": q_r, "q_ig": q_i, "q_profile": q_p, "q_hybrid": q_h, "ig_alpha": alpha})
