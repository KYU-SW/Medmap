"""STEP22 training inventory + audit + NORMALIZER_CORE subset 파일.

입력(읽기만): STEP21 data/dictionary_expressions.csv(기존 MedMap 자원 294 표현), data/pilot_gold.csv,
            STEP20 curation/curated_mappings.tsv(비 pilot class 의 내부 영문 label 용).
출력: data/train_expressions.csv · data/excluded_training_expressions.csv · data/normalizer_core_{dev,test}.csv
      outputs/training_data_audit.csv · outputs/class_inventory.json

audit 상태(우선순위 CONFLICT > AMBIGUOUS > TOO_SHORT > SAFE, DUPLICATE 는 별도 flag):
- DUPLICATE : 같은 정규화 표현·같은 class 가 이미 있음 → 두 view 모두에서 1개만 남김
- CONFLICT  : 같은 공백제거 표현이 서로 다른 class 에 붙음
- AMBIGUOUS : 아래 AMBIGUOUS_FRAGMENTS(사전 원문 의미 검토로 고정, test 를 보기 전 작성) — 신체 부위·색·수식어만 남은 조각
- TOO_SHORT : 공백제거 길이 ≤ 2 (표시만, 자동 제외 안 함: '열'·'기침'·'설사'·'오한' 같은 정식 증상어 보호)
CURATED 제외 규칙: AMBIGUOUS 전부 + terminology_ko '(part)' 조각 중 CONFLICT. 정식 label('통증'→pain 등)은 유지.
"""
import collections
import json

import lin_common as L

# 사전 원문 의미 검토만으로 정한 위험 조각(test 문장·STEP21 test 오류 미참조). (concept_id, 표현) → 사유
AMBIGUOUS_FRAGMENTS = {
    ("EV:E_83", "얼굴"): "신체 부위만 남은 조각(원 label '얼굴·눈 근육 힘 빠짐')",
    ("EV:E_193", "얼굴"): "신체 부위만 남은 조각(원 label 근육 경련 부위)",
    ("EV:E_193", "목 등"): "신체 부위 열거 조각",
    ("EV:E_157", "양팔"): "신체 부위만 남은 조각(원 label 저림)",
    ("EV:E_157", "양다리"): "신체 부위만 남은 조각(원 label 저림)",
    ("limb_weakness", "양팔"): "신체 부위만 남은 조각(원 label 힘 빠짐)",
    ("limb_weakness", "팔다리"): "신체 부위만 남은 조각(원 label 마비·힘 빠짐)",
    ("EV:E_182", "누런"): "색 수식어만 남은 조각(원 label 누런·초록 콧물)",
    ("EV:E_150", "대변"): "증상 아닌 명사 조각(STEP20: E_150 극성 반전 PARTIAL)",
    ("EV:E_150", "방귀 배출 가능 여부"): "질문 조각·극성 반전(STEP20 PARTIAL)",
    ("EV:E_9", "통증"): "일반 증상어가 림프절 증거에 붙은 조각(pain 과 충돌)",
    ("EV:E_9", "부음"): "일반 증상어가 림프절 증거에 붙은 조각(swelling 과 혼동)",
    ("EV:E_9", "림프절"): "해부 구조명만 남은 조각",
    ("EV:E_38", "힘 빠짐"): "원 증거 맥락 없는 일반 조각(E_156 과 충돌)",
    ("EV:E_156", "힘 빠짐"): "원 증거 맥락 없는 일반 조각(E_38 과 충돌)",
}


def main():
    cur = {r["evidence_id"]: r["canonical_concept"] for r in L.read_csv(L.c21.STEP20 / "curation/curated_mappings.tsv")}
    dic = L.read_csv(L.S21 / "data/dictionary_expressions.csv")
    assert all(d["concept_id"] for d in dic), "canonical ID 누락"

    rows, seen = [], set()
    for i, d in enumerate(dic):
        cid = d["concept_id"]
        name = L.PILOT_NAMES.get(cid) or cur.get(cid.removeprefix("EV:"), "")
        assert name, ("canonical name 누락", cid)
        ne = L.norm(d["expression"])
        key = (ne, cid)
        rows.append({"row_id": f"T{i + 1:03d}", "expression": d["expression"], "canonical_id": cid, "canonical_name": name,
                     "is_pilot_class": str(cid in L.PILOT), "source": d["source"], "source_type": d["source_type"],
                     "normalized_expression": ne, "nospace": ne.replace(" ", ""), "duplicate": str(key in seen)})
        seen.add(key)

    by_ns = collections.defaultdict(set)
    for r in rows:
        by_ns[r["nospace"]].add(r["canonical_id"])
    excluded = []
    for r in rows:
        amb = AMBIGUOUS_FRAGMENTS.get((r["canonical_id"], r["expression"]))
        conflict = len(by_ns[r["nospace"]]) > 1
        status = ("CONFLICT" if conflict else "AMBIGUOUS" if amb else "TOO_SHORT" if len(r["nospace"]) <= 2 else "SAFE")
        reasons = []
        if conflict:
            reasons.append("CONFLICT:" + "|".join(sorted(by_ns[r["nospace"]])))
        if amb:
            reasons.append("AMBIGUOUS:" + amb)
        if len(r["nospace"]) <= 2:
            reasons.append("TOO_SHORT")
        drop = bool(amb) or (conflict and r["source"].endswith("(part)"))
        r["audit_status"] = status
        r["audit_reason"] = "; ".join(reasons)
        r["curated_include"] = str(not drop and r["duplicate"] == "False")
        r["raw_include"] = str(r["duplicate"] == "False")
        if drop:
            excluded.append({**r, "exclusion_reason": r["audit_reason"]})

    for k, v in AMBIGUOUS_FRAGMENTS.items():
        assert any((r["canonical_id"], r["expression"]) == k for r in rows), ("AMBIGUOUS 목록 항목이 사전에 없음", k)
    # 중복 제거는 두 view 공통
    train = [r for r in rows if r["raw_include"] == "True"]
    fields = ["row_id", "expression", "canonical_id", "canonical_name", "source", "normalized_expression",
              "is_pilot_class", "source_type", "audit_status", "audit_reason", "curated_include"]
    L.write_csv(L.DATA / "train_expressions.csv", train, fields)
    L.write_csv(L.DATA / "excluded_training_expressions.csv", excluded,
                ["row_id", "expression", "canonical_id", "source", "audit_status", "exclusion_reason"])
    L.write_csv(L.OUT / "training_data_audit.csv", rows,
                ["row_id", "expression", "canonical_id", "is_pilot_class", "source", "normalized_expression", "duplicate",
                 "audit_status", "audit_reason", "raw_include", "curated_include"])

    # NORMALIZER_CORE subset (평가용 사본; 학습 스크립트는 test 파일을 읽지 않음)
    gold = L.load_gold()
    core_fields = ["utterance_id", "split", "tier", "utt_type", "text_ko", "primary_concept", "lexical_exposure", "source_type"]
    for sp in ("dev", "test"):
        L.write_csv(L.DATA / f"normalizer_core_{sp}.csv", [g for g in gold if g["split"] == sp and L.is_core(g)], core_fields)

    # class 인벤토리 + assert
    cnt = {v: collections.Counter(r["canonical_id"] for r in train if v == "RAW" or r["curated_include"] == "True")
           for v in L.VIEWS}
    core_test_cls = {g["primary_concept"] for g in gold if g["split"] == "test" and L.is_core(g)}
    core_dev_cls = {g["primary_concept"] for g in gold if g["split"] == "dev" and L.is_core(g)}
    inv = {
        "n_dictionary_rows": len(rows), "n_exact_duplicates": sum(r["duplicate"] == "True" for r in rows),
        "n_train_raw": len(train), "n_train_curated": sum(r["curated_include"] == "True" for r in train),
        "n_excluded_curated": len(excluded),
        "audit_status_counts": dict(collections.Counter(r["audit_status"] for r in rows)),
        "n_classes_raw": len(cnt["RAW"]), "n_classes_curated": len(cnt["CURATED"]),
        "n_pilot_classes": len(L.PILOT), "core_test_classes": sorted(core_test_cls), "core_dev_classes": sorted(core_dev_cls),
        "UNSEEN_CLASS": {v: sorted(core_test_cls - set(cnt[v])) for v in L.VIEWS},
        "train_only_classes_not_in_core_test": {v: sorted(set(cnt[v]) - core_test_cls) for v in L.VIEWS},
        "pilot_class_train_counts": {v: {c: cnt[v].get(c, 0) for c in L.PILOT} for v in L.VIEWS},
        "n_core_dev": sum(1 for g in gold if g["split"] == "dev" and L.is_core(g)),
        "n_core_test": sum(1 for g in gold if g["split"] == "test" and L.is_core(g)),
    }
    assert core_test_cls <= set(L.PILOT), core_test_cls - set(L.PILOT)
    L.dump_json(L.OUT / "class_inventory.json", inv)
    print(json.dumps({k: inv[k] for k in ("n_train_raw", "n_train_curated", "n_excluded_curated", "audit_status_counts",
                                          "n_classes_raw", "n_classes_curated", "UNSEEN_CLASS", "n_core_dev", "n_core_test")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
