"""EXP-03-TIME v2 실행 시간·RAM 추정용 합성 규모 시험(지어낸 행 — 실제 MIMIC 없음, PROTOCOL_TIME_v2.md §10).

규모는 EXP-02 공개 집계와 맞춤: 체류 12,358 · 환자 10,277 · 검사 216,397행 · 판독 259,099행 · ECG 13,335행.
판독 중 CTA 비율·addendum 비율은 임의 가정(실제 분포 아님) — 시간·메모리 추정에만 사용. 출력 = outputs/bench_v2_<시각>/bench_v2.json
"""
from __future__ import annotations

import json
import resource
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tests"))

import fixture_v2 as FX  # noqa: E402
import run_time_policy_audit_v2 as R  # noqa: E402

N_STAY, N_SUBJ, N_LAB, N_RAD, N_ECG = 12_358, 10_277, 216_397, 259_099, 13_335
CTA_FRAC, AR_FRAC = 0.08, 0.01
BASE = pd.Timestamp("2150-01-01")


def gen(d: Path, seed: int = 0):
    rng = np.random.default_rng(seed)
    subj = np.concatenate([np.arange(N_SUBJ), rng.integers(0, N_SUBJ, N_STAY - N_SUBJ)])
    start = BASE + pd.to_timedelta(rng.integers(0, 3650 * 24 * 60, N_STAY), unit="min")
    dur = pd.to_timedelta(rng.integers(60, 24 * 60, N_STAY), unit="min")
    co = pd.DataFrame({"subject_id": subj, "hadm_id": None, "stay_id": np.arange(N_STAY) + 30_000_000, "intime": start,
                       "outtime": start + dur, "gender": "F", "cohort_diseases": "",
                       "temperature": rng.normal(98.6, 1.2, N_STAY), "heartrate": rng.normal(95, 20, N_STAY),
                       "resprate": rng.normal(18, 4, N_STAY), "o2sat": rng.normal(96, 3, N_STAY), "sbp": rng.normal(130, 20, N_STAY),
                       "dbp": rng.normal(75, 12, N_STAY), "pain": rng.integers(0, 10, N_STAY).astype(float), "acuity": 2.0,
                       "chiefcomplaint": rng.choice(["SOB", "Chest pain", "Fever", "Abd pain", None], N_STAY)})
    si = rng.integers(0, N_STAY, N_LAB)
    ct = co["intime"].values[si] + pd.to_timedelta(rng.integers(-600, 1500, N_LAB), unit="min").values
    stt = ct + pd.to_timedelta(rng.integers(-5, 240, N_LAB), unit="min").values
    stt = pd.Series(stt).where(rng.random(N_LAB) > 0.02)
    items = rng.choice([51003, 50915, 51002, 50889], N_LAB)
    labs = pd.DataFrame({"labevent_id": np.arange(N_LAB) + 1, "subject_id": co["subject_id"].values[si], "hadm_id": None,
                         "specimen_id": np.arange(N_LAB), "itemid": items, "charttime": ct, "storetime": stt,
                         "value": None, "valuenum": rng.gamma(2, 300, N_LAB), "valueuom": "ng/mL", "ref_range_lower": None,
                         "ref_range_upper": 500.0, "flag": None, "priority": "STAT", "comments": None})
    ri = rng.integers(0, N_STAY, N_RAD)
    rct = co["intime"].values[ri] + pd.to_timedelta(rng.integers(-20000, 20000, N_RAD), unit="min").values
    rst = rct + pd.to_timedelta(rng.integers(-5, 600, N_RAD), unit="min").values
    cta = rng.random(N_RAD) < CTA_FRAC
    ar = rng.random(N_RAD) < AR_FRAC
    exam = np.where(cta, FX.CTA, rng.choice(["CHEST (PORTABLE AP)", "CT HEAD W/O CONTRAST", "CT CHEST W/CONTRAST"], N_RAD))
    texts = np.where(cta, rng.choice([FX.POS, FX.NEG, FX.NOM], N_RAD), "FINDINGS: Unremarkable study.")
    rad = pd.DataFrame({"note_id": [f"{s}-{'AR' if a else 'RR'}-{k}" for k, (s, a) in enumerate(zip(co["subject_id"].values[ri], ar))],
                        "subject_id": co["subject_id"].values[ri], "hadm_id": None, "note_type": np.where(ar, "AR", "RR"),
                        "note_seq": 1, "charttime": rct, "storetime": rst, "text": texts, "exam_name": exam})
    ei = rng.integers(0, N_STAY, N_ECG)
    ecg = pd.DataFrame({"study_id": np.arange(N_ECG) + 40_000_000, "ed_stay_id": co["stay_id"].values[ei].astype(float),
                        "ecg_time_ext": co["intime"].values[ei]})
    kids = rad.loc[ar & cta, "note_id"].tolist()
    pars = rad.loc[~ar & cta, "note_id"].sample(len(kids), random_state=seed).tolist()
    det = pd.DataFrame([(k, "parent_note_id", p) for k, p in zip(kids, pars)] + [(p, "addendum_note_id", k) for k, p in zip(kids, pars)],
                       columns=["note_id", "field_name", "field_value"])
    d.mkdir(parents=True)
    co.to_parquet(d / "cohort.parquet")
    labs.to_parquet(d / "labs.parquet")
    rad.to_parquet(d / "radiology.parquet")
    ecg.to_parquet(d / "ecg.parquet")
    det.to_parquet(d / "radiology_detail.parquet")


def main():
    out = HERE / "outputs" / f"bench_v2_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.time()
        gen(Path(tmp) / "src")
        tg = time.time() - t0
        t1 = time.time()
        r = R.run(Path(tmp) / "src", Path(tmp) / "o", Path(tmp) / "src" / "radiology_detail.parquet")
        tr = time.time() - t1
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    res = {"created": datetime.now().isoformat(timespec="seconds"), "synthetic": True, "scale": [N_STAY, N_SUBJ, N_LAB, N_RAD, N_ECG],
           "assumed_cta_frac": CTA_FRAC, "assumed_ar_frac": AR_FRAC, "gen_seconds": round(tg, 1), "run_seconds": round(tr, 1),
           "peak_rss_mb": round(rss), "status": r["status"], "violations": r.get("violations"),
           "disclosure": {k: (r.get("disclosure_check") or {}).get(k) for k in ("verifier_status", "rounds")},
           "relations_file_sha256": (r.get("disclosure_check") or {}).get("relations_file_sha256"),
           "code_sha256_at_run": r.get("code_sha256"),                  # 어떤 코드·관계로 나온 시험인지 고정(이전 bench 는 최종 검증기보다 먼저 생성됨)
           "published_tables": (r.get("disclosure_check") or {}).get("published_tables"),
           "withheld_tables": (r.get("disclosure_check") or {}).get("withheld_tables"),
           "n_published_tables": len((r.get("disclosure_check") or {}).get("published_tables", [])),
           "n_withheld_tables": len((r.get("disclosure_check") or {}).get("withheld_tables", []))}
    (out / "bench_v2.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("BENCH", json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
