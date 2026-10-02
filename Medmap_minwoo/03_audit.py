"""전체 split을 조금씩 읽어 통계와 데이터 중복을 점검합니다."""
from collections import Counter
from itertools import combinations
from pathlib import Path
import ast
import hashlib
import json
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
evidences = json.loads((DATA / "release_evidences.json").read_text(encoding="utf-8"))
conditions = json.loads((DATA / "release_conditions.json").read_text(encoding="utf-8"))
labels = {c["condition_name"] for c in conditions.values()}

def fingerprint(values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False,
                                    separators=(",", ":")).encode()).digest()

if __name__ == "__main__":
    report = {"evidence_count": len(evidences), "condition_count": len(conditions),
              "evidence_types": dict(Counter(e["data_type"] for e in evidences.values())),
              "antecedents": sum(e["is_antecedent"] for e in evidences.values()),
              "splits": {}, "cross_split_overlap": {}}
    signatures = {}
    for split in ("train", "validate", "test"):
        counts, missing, errors = Counter(), Counter(), Counter()
        token_lengths, code_lengths, ddx_lengths = [], [], []
        seen_full, seen_features = set(), set()
        n, duplicate_full, duplicate_features = 0, 0, 0
        for chunk in pd.read_csv(DATA / f"release_{split}_patients.zip", chunksize=20000):
            missing.update({k: int(v) for k, v in chunk.isna().sum().items()})
            counts.update(chunk["PATHOLOGY"])
            for row in chunk.itertuples(index=False):
                tokens = ast.literal_eval(row.EVIDENCES)
                ddx = ast.literal_eval(row.DIFFERENTIAL_DIAGNOSIS)
                codes = set()
                for token in tokens:
                    code, sep, value = token.partition("_@_")
                    codes.add(code)
                    if code not in evidences:
                        errors["unknown_code"] += 1
                        continue
                    meta = evidences[code]
                    if sep and value not in {str(v) for v in meta["possible-values"]}:
                        errors["invalid_value"] += 1
                    if (meta["data_type"] == "B") == bool(sep):
                        errors["type_mismatch"] += 1
                errors["unknown_label"] += row.PATHOLOGY not in labels
                errors["initial_not_in_codes"] += row.INITIAL_EVIDENCE not in codes
                errors["unknown_ddx_label"] += sum(d not in labels for d, p in ddx)
                errors["ddx_sum_not_one"] += abs(sum(p for d, p in ddx) - 1) > 1e-6
                token_lengths.append(len(tokens))
                code_lengths.append(len(codes))
                ddx_lengths.append(len(ddx))
                # 초기 소견과 정답을 제외한 환자 특징 자체의 일치도 검사합니다.
                features = [row.AGE, row.SEX, sorted(tokens)]
                feature_key = fingerprint(features)
                full_key = fingerprint(features + [row.PATHOLOGY, row.INITIAL_EVIDENCE, sorted(ddx)])
                duplicate_features += feature_key in seen_features
                duplicate_full += full_key in seen_full
                seen_features.add(feature_key)
                seen_full.add(full_key)
            n += len(chunk)
            print(split, n, "rows", flush=True)
        signatures[split] = {"full": seen_full, "features": seen_features}
        report["splits"][split] = {
            "shape": [n, len(chunk.columns)], "columns": chunk.columns.tolist(),
            "label_count": len(counts), "label_distribution": dict(counts.most_common()),
            "missing_cells": dict(missing), "validation_counts": dict(errors),
            "evidence_tokens": pd.Series(token_lengths).describe().to_dict(),
            "evidence_codes": pd.Series(code_lengths).describe().to_dict(),
            "differential_lengths": pd.Series(ddx_lengths).describe().to_dict(),
            "duplicate_full_rows_beyond_first": duplicate_full,
            "duplicate_feature_rows_beyond_first": duplicate_features}
    for a, b in combinations(signatures, 2):
        report["cross_split_overlap"][f"{a}__{b}"] = {
            kind: len(signatures[a][kind] & signatures[b][kind])
            for kind in ("full", "features")}
    (ROOT / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"overlap": report["cross_split_overlap"],
                      "shapes": {s: v["shape"] for s, v in report["splits"].items()}}, indent=2))
