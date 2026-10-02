"""STEP17A final evaluation.
  --mode primary   : recipe 모델(dev 재학습) + dev IG table → STEP17A_HOLDOUT 1회 평가, gate 판정
  --mode secondary : 제품 model_k3 + STEP16B IG table → 같은 행(IN_SAMPLE_DESCRIPTIVE, 판정 불가)
FREEZE.json + FREEZE_ARTIFACTS.json SHA 전부 검증 후에만 holdout을 연다."""
import sys, os, json, time, pickle, argparse, resource
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s17a_core as k
c = k.c
T0 = time.time()
os.chdir(k.HERE)
ap = argparse.ArgumentParser()
ap.add_argument("--mode", choices=["primary", "secondary"], required=True)
mode = ap.parse_args().mode
P = "P_" if mode == "primary" else "S_"
for f in (P + "initial.csv.gz", P + "summary.json"):
    if os.path.exists(f):
        sys.exit(f"STOP: {f} exists (1회 평가)")
if mode == "secondary" and not os.path.exists("P_summary.json"):
    sys.exit("STOP: primary must run first")

FZ = json.load(open("FREEZE.json"))
FA = json.load(open("FREEZE_ARTIFACTS.json"))
assert c.sha("PREREG.md") == FZ["PREREG.md"], "PREREG"
assert c.sha("01_split_manifest.json") == FZ["01_split_manifest.json"], "manifest"
assert c.sha("FREEZE.json") == FA["FREEZE.json"], "FREEZE.json"
for f, h in FA["files"].items():
    assert c.sha(f) == h, f"FREEZE_ARTIFACTS mismatch {f}"
k.log(T0, f"freeze verified ({len(FA['files'])} files)")

MAN = json.load(open("01_split_manifest.json"))
tr, info16 = k.load_step16b_train()
man = k.split_manifest(tr)
for key in ("dev_rows", "holdout_rows", "holdout_row_index_sha256", "key17_stream_sha256"):
    assert man[key] == MAN[key], key
rows = tr[tr.ho17].sort_values("key17").reset_index(drop=True)
del tr
k.log(T0, f"STEP17A_HOLDOUT opened: {len(rows)} rows ({mode})")

if mode == "primary":
    model = pickle.load(open("model_k3_step17a_dev.pkl", "rb"))
    Z = np.load("ig_table_step17a_dev.npz", allow_pickle=True)
else:
    model = pickle.load(open(f"{k.S16}/model_k3.pkl", "rb"))
    Z = np.load(f"{k.S16}/ig_table_step16b_train.npz", allow_pickle=True)
classes = list(Z["__classes__"])
sem = c.Semantics()
ig = {e: Z[e] for e in sem.qids}
ini, sim, aud = k.evaluate(rows, 10000, model, ig, classes, "step17a_holdout", T0)
ini.to_csv(P + "initial.csv.gz", index=False)
sim.to_csv(P + "sim.csv.gz", index=False)
S = k.summarize(ini, sim, set(rows.row_index[rows.INITIAL_EVIDENCE.isin(k.KO27)]))
S["audit"] = dict(aud)
S["audit"].update({"original_validation_reads": 0, "test_reads": 0, "step16b_holdout_token_or_label_use": 0,
                   "read_log_unique": sorted(set(c.READ_LOG)), "peak_rss_gb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024})
S["mode"] = mode
S["evaluation_type"] = "CLEAN_HOLDOUT_RECIPE_MODEL" if mode == "primary" else "IN_SAMPLE_DESCRIPTIVE (product MODEL_k3; cannot change decision)"
S["cohort"] = {"HO_ALL": len(rows), "HO_KO27": int(rows.INITIAL_EVIDENCE.isin(k.KO27).sum()), "SIM": min(10000, len(rows))}
if mode == "primary":
    S["gates"] = k.gates(S)
json.dump(S, open(P + "summary.json", "w"), indent=1, default=str)
k.log(T0, f"RUN_DONE {mode} " + (S["gates"]["decision"] if mode == "primary" else "descriptive"))
