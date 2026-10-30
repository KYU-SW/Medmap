#!/usr/bin/env python3
"""EXP-SN-NBI-002 B0c — d_labitems 사전(dictionary) 매핑 도구.

환자 데이터 아님: MIMIC-IV hosp d_labitems(itemid·label·fluid·category)만 읽는다. labevents 미사용.
규칙 = manifest [D] B0c 사전등록 그대로(label 소문자 부분 문자열 ∧ fluid == 'Blood'). itemid 를 기억·외부 지식으로
하드코딩하지 않는다. near-miss(규칙 밖이지만 비슷한 이름)는 모호성 검토용으로만 함께 기록하고 매핑에 넣지 않는다.
출력 = itemid·label·fluid·category 와 규칙 판정뿐(건수·환자 정보 없음).
"""
import argparse
import csv
import gzip
import hashlib
import json
import sys

# manifest [D] B0c + rev6 사전 검토 보완(CKMB 'isoenzyme mb', CRP 'high-sensitivity crp') — label 부분 문자열(OR), fluid == 'Blood'
RULES = {
    "BIOMARKER_TROPONIN": ("troponin",),
    "BIOMARKER_DDIMER": ("d-dimer",),
    "BIOMARKER_CKMB": ("ck-mb", "creatine kinase, mb", "isoenzyme mb"),
    "LAB_CRP_ESR": ("c-reactive protein", "sedimentation", "high-sensitivity crp"),
}
FLUID = "Blood"
# 모호성 검토용 near-miss 토큰(매핑에 쓰지 않음)
NEAR = ("trop", "dimer", "fibrin", "ck-", "ck ", "creatine kinase", "cpk", "crp", "c reactive", "c-reactive",
        "esr", "sed rate", "sedimentation")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def classify(label, fluid):
    """규칙에 맞는 개념 목록(fluid 조건 포함)."""
    lab = (label or "").lower()
    return sorted(c for c, keys in RULES.items() if fluid == FLUID and any(k in lab for k in keys))


def build_map(rows):
    mapping = {c: [] for c in RULES}
    near = []
    for r in rows:
        item = {"itemid": r["itemid"].strip(), "label": r["label"], "fluid": r["fluid"], "category": r["category"]}
        hits = classify(r["label"], r["fluid"])
        for c in hits:
            mapping[c].append(item)
        lab = (r["label"] or "").lower()
        if not hits and any(k in lab for k in NEAR):
            near.append(item)
    multi = sorted({i["itemid"] for c in mapping for i in mapping[c]
                    if sum(i["itemid"] in {x["itemid"] for x in mapping[o]} for o in mapping) > 1})
    for c in mapping:
        mapping[c].sort(key=lambda x: int(x["itemid"]))
    near.sort(key=lambda x: int(x["itemid"]))
    return {"mapping": mapping, "near_miss_not_mapped": near, "items_in_multiple_concepts": multi}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--d-labitems", required=True)
    ap.add_argument("--d-labitems-sha", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if sha256(a.d_labitems) != a.d_labitems_sha:
        print("B0C_MAP INVALID reason=sha_mismatch")
        return 2
    with gzip.open(a.d_labitems, "rt", encoding="utf-8", newline="") as fh:
        res = build_map(csv.DictReader(fh))
    res["meta"] = {"experiment": "EXP-SN-NBI-002", "phase": "B0c", "artifact": "labitem_map",
                   "rule": "label lower-case substring (manifest [D] B0c) AND fluid == 'Blood'",
                   "d_labitems_sha256": a.d_labitems_sha, "script_sha256": sha256(__file__),
                   "note": "dictionary only; no patient data read"}
    with open(a.out, "x", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False, sort_keys=True)
    print("B0C_MAP DONE " + " ".join(f"{c}={len(v)}" for c, v in res["mapping"].items())
          + f" near_miss={len(res['near_miss_not_mapped'])} multi={len(res['items_in_multiple_concepts'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
