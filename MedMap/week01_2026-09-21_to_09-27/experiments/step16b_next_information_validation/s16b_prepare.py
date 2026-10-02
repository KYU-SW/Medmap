"""STEP16B prepare: 80/20 split → 01_split_manifest.json, STEP16B_TRAIN 전용 IG table + MODEL_k3/k5/k10.
HOLDOUT은 split 배정 외에는 읽지 않는다(토큰/라벨 사용 금지)."""
import sys, json, time, pickle, hashlib
import numpy as np
sys.path.insert(0, ".")
import s16b_core as c

T0 = time.time()
def log(m): print(f"[{time.time()-T0:7.0f}s] {m}", flush=True)

EXPECT = json.load(open("00_preregistration_sha256.json"))
for f in ["00_STEP16B_PREREGISTRATION.md", "00_STEP16B_RULES.json"]:
    assert c.sha(f) == EXPECT[f], f"PREREG SHA MISMATCH {f}"
log("prereg SHA verified")

json.dump({"release_train_patients": c.sha(c.TRAIN_PATH), "release_evidences.json": c.sha(f"{c.D}/release_evidences.json")}, open("00_input_integrity.json", "w"), indent=1)
df = c.load_train(); log(f"train file loaded {len(df)}")
tr = df[~df.holdout].reset_index(drop=True); ho = df[df.holdout]
classes = sorted(df.PATHOLOGY.unique())
key_digest = hashlib.sha256("".join(df.split_key.values).encode()).hexdigest()
json.dump({"source_rows": int(len(df)), "train_rows": int(len(tr)), "holdout_rows": int(len(ho)),
           "holdout_fraction": float(df.holdout.mean()), "split_rule": "sha256(row_index|AGE|SEX|PATHOLOGY|EVIDENCES), int(hex[:8],16)%10<2",
           "split_key_stream_sha256": key_digest, "holdout_row_index_sha256": hashlib.sha256(",".join(map(str, ho.row_index.values)).encode()).hexdigest(),
           "classes": classes, "excluded_questions": list(c.EXCLUDED)}, open("01_split_manifest.json", "w"), indent=1)
log(f"split: train {len(tr)} holdout {len(ho)}")
del ho

sem = c.Semantics(); enc = c.Encoder(sem)
ig_table, missing = c.fit_ig_table(sem, tr.tokens.tolist(), tr.PATHOLOGY.tolist(), classes)
log(f"IG table done; unsafe-missing on included questions: none (excluded {dict((k, v) for k, v in missing.items() if v > 0)})")
np.savez_compressed("ig_table_step16b_train.npz", **{e: ig_table[e] for e in ig_table}, __classes__=np.array(classes))

ages = tr.AGE.values; sexes = tr.SEX.values; y = tr.PATHOLOGY.values; toks = tr.tokens.tolist(); ini = tr.INITIAL_EVIDENCE.values; ridx = tr.row_index.values
for k in (3, 5, 10):
    states = [c.make_view(sem, toks[i], ini[i], k, "step16b_train", 42, int(ridx[i])) for i in range(len(tr))]
    X = enc.transform(states, ages, sexes); log(f"k{k} views encoded {X.shape}")
    m = c.fit_model(X, y); acc = float((m.predict(X) == y).mean())
    pickle.dump(m, open(f"model_k{k}.pkl", "wb")); log(f"k{k} model trained train_acc {acc:.4f} sha {c.sha(f'model_k{k}.pkl')[:8]}")
    del states, X
log("PREPARE_DONE")
