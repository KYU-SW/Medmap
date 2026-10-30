"""STEP28.8 §5 — 보류 우선 대상 키 목록(정제표 HOLD_CONCEPT_UNCERTAIN·HOLD_AUDIT_NOT_EXACT) 기록. 적용 로직 = policies.PolicyEngine.apply_held.
출력: data/held_keys.csv"""
import s288_common as S
from policies import HELD_DECISIONS

rows = [{"normalized_korean": r["normalized_korean"], "korean_expression": r["korean_expression"], "mapping_decision": r["mapping_decision"],
         "ontology_id": r["ontology_id"], "rejection_reason": r["rejection_reason"][:120]}
        for r in S.read_csv(S.S287_DIR / "data/cleaned_silver_mappings.csv") if r["mapping_decision"] in HELD_DECISIONS]
S.wcsv(S.DATA / "held_keys.csv", rows)
print({"held_rows": len(rows), "distinct_keys": len({r["normalized_korean"] for r in rows})})
