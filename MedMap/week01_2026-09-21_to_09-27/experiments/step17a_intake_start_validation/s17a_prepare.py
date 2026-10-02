"""STEP17A prepare.
  --mode split : PREREG SHA 검증 → STEP16B_TRAIN 내부 dev/holdout split manifest + dev-only coverage·fixed bootstrap 감사
  --mode fit   : dev만으로 IG table + MODEL_k3 (STEP16B 레시피). holdout은 소속 판정 외 사용하지 않는다.
"""
import sys, os, json, time, pickle, argparse, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s17a_core as k
c = k.c
T0 = time.time()
os.chdir(k.HERE)
ap = argparse.ArgumentParser()
ap.add_argument("--mode", choices=["split", "fit"], required=True)
mode = ap.parse_args().mode

FZ = json.load(open("FREEZE.json"))
assert c.sha("PREREG.md") == FZ["PREREG.md"], "PREREG SHA MISMATCH"
k.log(T0, "PREREG SHA verified")

tr, info16 = k.load_step16b_train()
k.log(T0, f"STEP16B_TRAIN {len(tr)} (STEP16B_HOLDOUT {info16['step16b_holdout_rows_dropped']} dropped by membership only)")
man = k.split_manifest(tr)
dev = tr[~tr.ho17].reset_index(drop=True)
n_ho = int(tr.ho17.sum())
del tr  # holdout 행은 이 스크립트에서 더 이상 존재하지 않음

if mode == "split":
    if os.path.exists("01_split_manifest.json"):
        sys.exit("STOP: 01_split_manifest.json exists")
    man.update(info16)
    man["input_sha256"] = {"release_train_patients": c.sha(c.TRAIN_PATH), "release_evidences.json": c.sha(f"{c.D}/release_evidences.json")}
    json.dump(man, open("01_split_manifest.json", "w"), indent=1)
    k.log(T0, f"split dev {man['dev_rows']} holdout {man['holdout_rows']} ({man['holdout_fraction']:.4f})")
    # ---- coverage (dev only) ----
    cnt = collections.Counter(dev.INITIAL_EVIDENCE.values)
    tot = sum(cnt.values())
    ko = set(k.KO27)
    run = sum(v for e, v in cnt.items() if e in ko)
    miss = sorted([(e, v) for e, v in cnt.items() if e not in ko], key=lambda x: (-x[1], c.qnum(x[0])))
    need, added = {}, []
    for e, v in miss:
        run += v
        added.append({"evidence_id": e, "count": v})
        for th in (0.8, 0.9, 0.95, 0.99):
            if str(th) not in need and run / tot >= th:
                need[str(th)] = {"n_additions": len(added), "ids": [a["evidence_id"] for a in added]}
    ev = json.load(open(c.guarded_path(f"{c.D}/release_evidences.json")))
    cov = {"scope": "STEP17A_DEV only", "rows": tot, "unique_initial": len(cnt),
           "ko27_present_in_dev": sorted([e for e in k.KO27 if e in cnt], key=c.qnum),
           "ko27_coverage": sum(v for e, v in cnt.items() if e in ko) / tot,
           "untranslated_initial": len(miss), "additions_needed": need,
           "untranslated_top30": [{"evidence_id": e, "count": v, "share": v / tot, "question_en": ev[e]["question_en"]} for e, v in miss[:30]]}
    json.dump(cov, open("02_initial_coverage_dev.json", "w"), indent=1)
    needs = {a: b["n_additions"] for a, b in need.items()}
    k.log(T0, f"coverage unique {cov['unique_initial']} ko27 {cov['ko27_coverage']:.4f} needs {needs}")
    # ---- fixed bootstrap audit (dev only) ----
    classes = sorted(dev.PATHOLOGY.unique())
    ci = {x: i for i, x in enumerate(classes)}
    y = np.array([ci[p] for p in dev.PATHOLOGY.values])
    prior = np.bincount(y, minlength=len(classes)) / len(y)
    base = [{t.partition("_@_")[0] for t in ts} for ts in dev.tokens.values]
    audit = {}
    sem = c.Semantics()
    for q in k.FIXED + k.BACKUP:
        assert sem.dtype[q] == "B" and q not in sem.parent and sem.safe[q], q
        pos = np.array([q in b for b in base])
        pd_pos = np.array([pos[y == d].mean() for d in range(len(classes))])
        p1 = float(pos.mean())
        def H(p): p = p[p > 0]; return float(-(p * np.log2(p)).sum())
        mi = H(np.array([p1, 1 - p1])) - float((prior * np.array([H(np.array([a, 1 - a])) for a in pd_pos])).sum())
        top = np.argsort(-pd_pos)[:5]
        audit[q] = {"dtype": "B", "parent": None, "pos_rate": p1, "neg_rate": 1 - p1,
                    "value_or_na": "not applicable (binary, closed-world)", "missing": 0,
                    "same_as_initial_rate": float((dev.INITIAL_EVIDENCE.values == q).mean()),
                    "mutual_information_bits": mi,
                    "top5_P_pos_given_disease": [{"disease": classes[d], "p_pos": float(pd_pos[d])} for d in top]}
    json.dump({"scope": "STEP17A_DEV only; 순서 변경 금지(다음 실험에서만)", "order": k.FIXED, "backup": k.BACKUP, "audit": audit},
              open("03_fixed_bootstrap_audit_dev.json", "w"), indent=1)
    k.log(T0, "SPLIT_DONE")

else:
    FZ_MAN = FZ.get("01_split_manifest.json")
    assert FZ_MAN and c.sha("01_split_manifest.json") == FZ_MAN, "split manifest not frozen/matched"
    saved = json.load(open("01_split_manifest.json"))
    for key in ("dev_rows", "holdout_rows", "dev_row_index_sha256", "holdout_row_index_sha256", "key17_stream_sha256"):
        assert saved[key] == man[key], f"split mismatch {key}"
    for f in ("ig_table_step17a_dev.npz", "model_k3_step17a_dev.pkl"):
        if os.path.exists(f):
            sys.exit(f"STOP: {f} exists")
    classes = sorted(dev.PATHOLOGY.unique())
    assert classes == k.S16_MAN["classes"], "classes differ from STEP16B"
    sem = c.Semantics(); enc = c.Encoder(sem)
    ig_table, missing = c.fit_ig_table(sem, dev.tokens.tolist(), dev.PATHOLOGY.tolist(), classes)
    np.savez_compressed("ig_table_step17a_dev.npz", **{e: ig_table[e] for e in ig_table}, __classes__=np.array(classes))
    k.log(T0, "IG table (dev) saved")
    toks = dev.tokens.tolist(); ini = dev.INITIAL_EVIDENCE.values; ridx = dev.row_index.values
    states = [c.make_view(sem, toks[i], ini[i], 3, "step17a_dev", 42, int(ridx[i])) for i in range(len(dev))]
    X = enc.transform(states, dev.AGE.values, dev.SEX.values)
    k.log(T0, f"k3 dev views encoded {X.shape}")
    m = c.fit_model(X, dev.PATHOLOGY.values)
    acc = float((m.predict(X) == dev.PATHOLOGY.values).mean())
    pickle.dump(m, open("model_k3_step17a_dev.pkl", "wb"))
    json.dump({"dev_rows": len(dev), "holdout_rows_not_used": n_ho, "train_acc_k3": acc, "recipe": "s16b_core.fit_model, make_view k=3 seed 42",
               "unsafe_missing_excluded": {e: v for e, v in missing.items() if v > 0}},
              open("04_fit_report.json", "w"), indent=1)
    k.log(T0, f"k3 trained on dev, train acc {acc:.4f}")
    k.log(T0, "FIT_DONE")
