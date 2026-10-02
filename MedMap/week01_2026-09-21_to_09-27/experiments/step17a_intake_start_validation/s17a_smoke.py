"""STEP17A smoke — dev 200명(key17 내림차순 앞 200), 제품 model_k3 + STEP16B IG table.
코드 동작·시간·RAM 확인 전용. holdout 미사용. 지표 해석 금지."""
import sys, os, json, time, pickle, resource
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s17a_core as k
c = k.c
T0 = time.time()
os.chdir(k.HERE)
FZ = json.load(open("FREEZE.json"))
assert c.sha("PREREG.md") == FZ["PREREG.md"]
assert FZ.get("01_split_manifest.json") and c.sha("01_split_manifest.json") == FZ["01_split_manifest.json"]
tr, _ = k.load_step16b_train()
dev = tr[~tr.ho17]
del tr
rows = dev.sort_values("key17", ascending=False).head(200).sort_values("key17").reset_index(drop=True)
del dev
k.log(T0, f"smoke rows {len(rows)} (dev only)")
model = pickle.load(open(f"{k.S16}/model_k3.pkl", "rb"))
Z = np.load(f"{k.S16}/ig_table_step16b_train.npz", allow_pickle=True)
classes = list(Z["__classes__"])
sem = c.Semantics()
ig = {e: Z[e] for e in sem.qids}
t = time.time()
ini, sim, aud = k.evaluate(rows, 200, model, ig, classes, "step17a_smoke", T0)
el = time.time() - t
S = k.summarize(ini, sim, set(rows.row_index[rows.INITIAL_EVIDENCE.isin(k.KO27)]))
rss_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
rep = {"rows": len(rows), "eval_seconds": el, "peak_rss_gb": rss_gb, "audit": dict(aud),
       "gate_function_smoke": k.gates(S)["decision"] is not None,
       "projection_note": "SIM 비용은 n에 선형. primary SIM=10,000 → eval_seconds×50 근사(초기 예측 HO_ALL 전수 추가)"}
json.dump(rep, open("_smoke_report.json", "w"), indent=1, default=str)
json.dump(S, open("_smoke_summary.json", "w"), indent=1, default=str)
k.log(T0, f"SMOKE_DONE eval {el:.0f}s peak_rss {rss_gb:.2f}GB audit {dict(aud)}")
