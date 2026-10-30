"""STEP23 생성 표현 품질 감사(의미 감사 결과 결합 + 기계 검사 + regression/dev 누수 제거).

입력: 격리 폴더 out/gen_b*.tsv(작성자) · out/audit_b*.tsv(독립 감사자) → data/raw_generated/ 로 복사(SHA 기록)
      STEP22 data/train_expressions.csv(CURATED, 기존 표현) · STEP21 pilot_gold.csv(누수 검사용 문장 비교만)
판정 순서(실행 전 고정, 앞에서 걸리면 그 사유로 확정):
 1 INVALID_ROW            concept_id 가 TARGET_20 밖이거나 표현 비어 있음
 2 감사자 판정            AMBIGUOUS / WRONG_CONCEPT / TOO_GENERIC / NOT_SINGLE_PRESENT (감사 누락 행 = AUDIT_MISSING)
 3 TOO_SHORT              공백 제거 길이 ≤ 2
 4 CONFLICT               같은 공백제거 표현이 다른 concept 에도 있음(생성·기존 모두 포함)
 5 EXACT_DUPLICATE        공백제거 표현이 기존 사전 또는 앞선 생성 표현과 같음
 6 NEAR_DUPLICATE         같은 concept 안 기존/앞선 표현과 difflib ratio ≥ 0.90
 7 REMOVED_TEST_EXACT / REMOVED_TEST_NEAR_DUPLICATE   FIXED_REGRESSION_TEST(전체 177) 문장과 완전일치 / ratio ≥ 0.80
 8 REMOVED_DEV_NEAR_DUPLICATE                          dev(97) 문장과 완전일치 또는 ratio ≥ 0.80 (dev 는 선택에 쓰므로)
 9 REMOVED_PROMPT_EXAMPLE                              STEP23 지시문이 금지한 예시 문자열과 ratio ≥ 0.80
 그 외 = VALID. 제거한 표현은 대체하지 않는다. 누수 검사는 생성 후 1회만 수행(반복 맞추기 없음).
출력: data/target20_candidates_audited.csv · data/excluded_expressions.csv · data/overlap_audit.csv
"""
import collections
import difflib
import shutil

import s23_common as S

RAW = S.DATA / "raw_generated"
SEM_BAD = {"AMBIGUOUS", "WRONG_CONCEPT", "TOO_GENERIC", "NOT_SINGLE_PRESENT"}
PROMPT_FORBIDDEN = ["호흡이 딸려요", "숨이 벅차요", "물만 마셔도 다 토해요", "토했어요", "머리가 아파요"]
NEAR_TRAIN, NEAR_GOLD = 0.90, 0.80


def ratio(a, b):
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def read_tsv(p):
    return S.read_csv(p) if p.suffix == ".tsv" else []


def main():
    RAW.mkdir(exist_ok=True)
    gen, aud = [], {}
    for k in ("b1", "b2", "b3", "b4"):
        for kind in ("gen", "audit"):
            src = S.WS / "out" / f"{kind}_{k}.tsv"
            shutil.copyfile(src, RAW / src.name)
        for i, r in enumerate(read_tsv(RAW / f"gen_{k}.tsv"), 1):
            gen.append({"gen_id": f"{k}_{i:03d}", "batch": k, "row": i, "concept_id": (r.get("concept_id") or "").strip(),
                        "style": (r.get("style") or "").strip(), "expression": (r.get("expression") or "").strip()})
        for r in read_tsv(RAW / f"audit_{k}.tsv"):
            try:
                aud[(k, int(r["row"]))] = r
            except (KeyError, ValueError, TypeError):
                pass

    existing = [r for r in S.read_csv(S.S22 / "data/train_expressions.csv") if r["curated_include"] == "True"]
    gold = S.load_gold()
    gold_ns = [(g["utterance_id"], g["split"], S.nospace(g["text_ko"])) for g in gold]
    forb = [S.nospace(x) for x in PROMPT_FORBIDDEN]

    ns_concepts = collections.defaultdict(set)
    for r in existing:
        ns_concepts[S.nospace(r["expression"])].add(r["canonical_id"])
    for g in gen:
        g["nospace"] = S.nospace(g["expression"])
        if g["concept_id"] in S.TARGET20 and g["nospace"]:
            ns_concepts[g["nospace"]].add(g["concept_id"])

    kept_by_concept = collections.defaultdict(list)
    for r in existing:
        kept_by_concept[r["canonical_id"]].append(S.nospace(r["expression"]))
    seen_ns = {S.nospace(r["expression"]) for r in existing}
    overlap = []
    for g in gen:
        a = aud.get((g["batch"], g["row"]))
        g["audit_verdict"] = (a or {}).get("verdict", "").strip() or "AUDIT_MISSING"
        g["audit_reason"] = (a or {}).get("reason", "") or ""
        if a and S.nospace(a.get("expression", "")) != g["nospace"]:
            g["audit_verdict"], g["audit_reason"] = "AUDIT_MISSING", "감사 행 표현 불일치"
        ns = g["nospace"]
        # 누수 근접도(판정과 별도로 전 행 기록)
        bt = max(((ratio(ns, x), u, sp) for u, sp, x in gold_ns if sp == "test"), default=(0, "", ""))
        bd = max(((ratio(ns, x), u, sp) for u, sp, x in gold_ns if sp == "dev"), default=(0, "", ""))
        bf = max((ratio(ns, x) for x in forb), default=0)
        overlap.append({"gen_id": g["gen_id"], "concept_id": g["concept_id"],
                        "test_exact": str(any(ns == x for _, sp, x in gold_ns if sp == "test")),
                        "test_max_ratio": round(bt[0], 4), "test_nearest_id": bt[1],
                        "dev_exact": str(any(ns == x for _, sp, x in gold_ns if sp == "dev")),
                        "dev_max_ratio": round(bd[0], 4), "dev_nearest_id": bd[1], "prompt_example_max_ratio": round(bf, 4)})
        o = overlap[-1]
        if g["concept_id"] not in S.TARGET20 or not ns:
            st = "INVALID_ROW"
        elif g["audit_verdict"] in SEM_BAD or g["audit_verdict"] == "AUDIT_MISSING":
            st = g["audit_verdict"]
        elif g["audit_verdict"] != "VALID":
            st = "AUDIT_MISSING"
        elif len(ns) <= 2:
            st = "TOO_SHORT"
        elif len(ns_concepts[ns]) > 1:
            st = "CONFLICT"
        elif ns in seen_ns:
            st = "EXACT_DUPLICATE"
        elif any(ratio(ns, x) >= NEAR_TRAIN for x in kept_by_concept[g["concept_id"]]):
            st = "NEAR_DUPLICATE"
        elif o["test_exact"] == "True":
            st = "REMOVED_TEST_EXACT"
        elif o["test_max_ratio"] >= NEAR_GOLD:
            st = "REMOVED_TEST_NEAR_DUPLICATE"
        elif o["dev_exact"] == "True" or o["dev_max_ratio"] >= NEAR_GOLD:
            st = "REMOVED_DEV_NEAR_DUPLICATE"
        elif bf >= NEAR_GOLD:
            st = "REMOVED_PROMPT_EXAMPLE"
        else:
            st = "VALID"
        g["status"] = st
        if st == "VALID":
            seen_ns.add(ns)
            kept_by_concept[g["concept_id"]].append(ns)

    fields = ["gen_id", "concept_id", "style", "expression", "nospace", "audit_verdict", "audit_reason", "status"]
    S.write_csv(S.DATA / "target20_candidates_audited.csv", gen, fields)
    S.write_csv(S.DATA / "excluded_expressions.csv", [g for g in gen if g["status"] != "VALID"], fields)
    S.write_csv(S.DATA / "overlap_audit.csv", overlap)
    valid = [g for g in gen if g["status"] == "VALID"]
    assert not any(o["test_exact"] == "True" for o, g in zip(overlap, gen) if g["status"] == "VALID")
    print("generated", len(gen), "status", dict(collections.Counter(g["status"] for g in gen)))
    print("audit verdicts", dict(collections.Counter(g["audit_verdict"] for g in gen)))
    print("valid per concept", dict(sorted(collections.Counter(g["concept_id"] for g in valid).items())))


if __name__ == "__main__":
    main()
