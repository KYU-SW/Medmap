"""개발용 DDXPlus 사례 추출(TRAIN16 만 — EXP-01 HOLDOUT = SELECT·FINAL 제외).

분할: STEP16B s16b_core.split_key/is_holdout 과 같은 식(코드 복사 아님, 식 재현 후 전체 HOLDOUT 수 204,663 일치 검증).
선택: PATHOLOGY ∈ 선택 4질환, holdout=False, split_key 오름차순 앞 PER_DISEASE 건(결정적). PATHOLOGY 는 사례 선택·참고 표시에만 쓰고
엔진 입력에 넣지 않는다. DIFFERENTIAL_DIAGNOSIS(생성기 출력) 열은 읽지 않는다.
실행: ~/ai_env/bin/python -B extract_dev_cases.py [--nrows N] --out outputs/dev_cases_<시각>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from knowledge_real_kg import SELECTED

TRAIN = Path("/home/<user>/medmap/data/ddxplus/en/release_train_patients")
EXPECTED_ROWS, EXPECTED_HOLDOUT = 1_025_602, 204_663
PER_DISEASE = 2


def split_key(row_index, age, sex, pathology, evidences):
    return hashlib.sha256(f"{row_index}|{age}|{sex}|{pathology}|{evidences}".encode()).hexdigest()


def is_holdout(key):
    return int(key[:8], 16) % 10 < 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--nrows", type=int, default=None)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    t0 = time.time()
    n = hold = 0
    cand = []
    cols = ["AGE", "SEX", "PATHOLOGY", "EVIDENCES", "INITIAL_EVIDENCE"]
    for ch in pd.read_csv(TRAIN, usecols=cols, chunksize=200_000, nrows=a.nrows):
        for i, (age, sex, pat, evs, ini) in enumerate(zip(ch.AGE, ch.SEX, ch.PATHOLOGY, ch.EVIDENCES, ch.INITIAL_EVIDENCE)):
            ri = n + i
            k = split_key(ri, age, sex, pat, evs)
            h = is_holdout(k)
            hold += h
            if not h and pat in SELECTED:
                cand.append({"row_index": ri, "split_key": k, "AGE": int(age), "SEX": sex, "PATHOLOGY_REFERENCE_ONLY": pat,
                             "EVIDENCES": evs, "INITIAL_EVIDENCE": ini})
        n += len(ch)
    full = a.nrows is None
    check = {"rows": n, "holdout": hold, "train16": n - hold,
             "matches_step16b": (n, hold) == (EXPECTED_ROWS, EXPECTED_HOLDOUT) if full else "NOT_CHECKED(nrows)"}
    if full and not check["matches_step16b"]:
        raise SystemExit(f"split mismatch: {check}")
    cand.sort(key=lambda r: r["split_key"])
    picked = []
    for d in SELECTED:
        picked += [r for r in cand if r["PATHOLOGY_REFERENCE_ONLY"] == d][:PER_DISEASE]
    meta = {"train_file": str(TRAIN), "split_check": check, "candidates_train16": len(cand),
            "per_disease": PER_DISEASE, "picked": len(picked), "seconds": round(time.time() - t0, 1)}
    (out / "dev_cases.json").write_text(json.dumps({"meta": meta, "cases": picked}, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
