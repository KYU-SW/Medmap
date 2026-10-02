"""Natural Intake v1 매퍼 평가 harness (제품 engineering gate — 임상 성능 주장 아님).

고정(실행 전):
  - 입력 fixture: tests/fixtures/intake_mapper_eval.json (매퍼와 독립된 에이전트가 작성, SHA는 매퍼 작성 전 동결)
  - 채점 단위: (item_id, evidence_id, status). status가 틀리면 FP 1 + FN 1.
  - Gate: 전체 precision >= 0.95, NEGATIVE precision >= 0.95. recall은 보고만.
  - primary = 전체 문항. temporal_ambiguous 제외 값은 민감도 참고용.
출력: 기본 exp/intake_mapper_v1/01_eval_result.json, --fixture/--out 으로 변경 (기존 파일이 있으면 덮어쓰지 않고 중단)
참고 gate(v1.2~): positive precision >= 0.95, recall >= 0.70 (PASS/FAIL 표시만)
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medmap.intake import IntakeMapper  # noqa: E402
from medmap.intake.mapper import ALIASES_JSON  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "intake_mapper_eval.json"
OUT = ROOT / "exp" / "intake_mapper_v1" / "01_eval_result.json"
GATE = {"overall_precision_min": 0.95, "negative_precision_min": 0.95}
REFERENCE_GATE = {"positive_precision_min": 0.95, "recall_min": 0.70}   # v1.2/v3 참고값(PASS/FAIL 표시만)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ratio(a: int, b: int):
    return round(a / b, 4) if b else None


def f1(p, r):
    return round(2 * p * r / (p + r), 4) if p and r else 0.0


def count_bucket(n: int) -> str:
    return str(n) if n < 5 else "5+"


def dist(counts: list[int]) -> dict:
    c = collections.Counter(count_bucket(n) for n in counts)
    tot = len(counts)
    return {k: {"n": c.get(k, 0), "ratio": ratio(c.get(k, 0), tot)} for k in ["0", "1", "2", "3", "4", "5+"]}


def score(items: list[dict], preds: dict) -> dict:
    tp = collections.Counter(); fp = collections.Counter(); fn = collections.Counter()
    neg_seen = neg_correct = flips = exact = 0
    for it in items:
        gold = {(g["evidence_id"], g["status"]) for g in it["gold"]}
        pred = {(p["evidence_id"], p["status"]) for p in preds[it["id"]]}
        for e, s in pred:
            (tp if (e, s) in gold else fp)[s] += 1
        for e, s in gold:
            if (e, s) not in pred:
                fn[s] += 1
        pred_ids = {e: s for e, s in pred}
        for e, s in gold:
            if e in pred_ids and pred_ids[e] != s:
                flips += 1
            if s == "NEGATIVE" and e in pred_ids:
                neg_seen += 1
                neg_correct += pred_ids[e] == "NEGATIVE"
        exact += pred == gold
    TP, FP, FN = sum(tp.values()), sum(fp.values()), sum(fn.values())
    P, R = ratio(TP, TP + FP), ratio(TP, TP + FN)
    out = {"n_items": len(items), "tp": TP, "fp": FP, "fn": FN, "precision": P, "recall": R, "f1": f1(P, R)}
    for s in ("POSITIVE", "NEGATIVE"):
        out[s.lower()] = {"tp": tp[s], "fp": fp[s], "fn": fn[s], "precision": ratio(tp[s], tp[s] + fp[s]),
                          "recall": ratio(tp[s], tp[s] + fn[s]), "gold": tp[s] + fn[s], "pred": tp[s] + fp[s]}
    out["negation_accuracy"] = {"definition": "gold NEGATIVE 중 매퍼가 같은 evidence를 낸 경우, NEGATIVE로 낸 비율",
                                "n": neg_seen, "correct": neg_correct, "value": ratio(neg_correct, neg_seen)}
    out["polarity_flips"] = flips
    out["exact_sentence_match"] = {"n": exact, "value": ratio(exact, len(items))}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", default=str(FIXTURE))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    fixture, out_path = Path(args.fixture).resolve(), Path(args.out).resolve()
    if out_path.exists():
        sys.exit(f"STOP: {out_path} already exists (덮어쓰기 금지)")
    fx = json.loads(fixture.read_text())
    items = fx["items"]
    mapper = IntakeMapper()
    preds = {it["id"]: mapper.extract(it["text"]) for it in items}
    # 결정성: 두 번째 인스턴스 재실행과 동일해야 함
    m2 = IntakeMapper()
    deterministic = all(m2.extract(it["text"]) == preds[it["id"]] for it in items)
    unsupported_gold = sorted({g["evidence_id"] for it in items for g in it["gold"]} - mapper.supported)

    primary = score(items, preds)
    no_temporal = score([it for it in items if it["category"] != "temporal_ambiguous"], preds)
    by_cat = {c: score([it for it in items if it["category"] == c], preds)
              for c in sorted({it["category"] for it in items})}

    errors = []
    for it in items:
        gold = {(g["evidence_id"], g["status"]) for g in it["gold"]}
        gold_ids = {g["evidence_id"]: g["status"] for g in it["gold"]}
        for p in preds[it["id"]]:
            if (p["evidence_id"], p["status"]) not in gold:
                kind = "FP_POLARITY_FLIP" if p["evidence_id"] in gold_ids else "FP_NOT_IN_GOLD"
                errors.append({"kind": kind, "item": it["id"], "category": it["category"], "text": it["text"],
                               "evidence_id": p["evidence_id"], "pred_status": p["status"],
                               "gold_status": gold_ids.get(p["evidence_id"]), "matched_text": p["matched_text"],
                               "alias_id": p.get("alias_id"), "note": it.get("note", "")})
        pred = {(p["evidence_id"], p["status"]) for p in preds[it["id"]]}
        for g in it["gold"]:
            if (g["evidence_id"], g["status"]) not in pred and g["evidence_id"] not in {p["evidence_id"] for p in preds[it["id"]]}:
                errors.append({"kind": "FN_MISSED", "item": it["id"], "category": it["category"], "text": it["text"],
                               "evidence_id": g["evidence_id"], "pred_status": None, "gold_status": g["status"],
                               "span": g.get("span"), "note": it.get("note", "")})
    order = {"FP_POLARITY_FLIP": 0, "FP_NOT_IN_GOLD": 1, "FN_MISSED": 2}
    errors.sort(key=lambda e: (order[e["kind"]], e["item"], e["evidence_id"]))

    pred_counts = [len(preds[it["id"]]) for it in items]
    gold_counts = [len(it["gold"]) for it in items]
    multi = [it for it in items if it["category"] == "multi_symptom"]
    result = {
        "schema": "medmap.intake_mapper_eval_result/1",
        "gate": GATE,
        "gate_result": {
            "overall_precision": "PASS" if (primary["precision"] or 0) >= GATE["overall_precision_min"] else "FAIL",
            "negative_precision": "PASS" if (primary["negative"]["precision"] or 0) >= GATE["negative_precision_min"] else "FAIL",
            "positive_precision_reference": "PASS" if (primary["positive"]["precision"] or 0) >= REFERENCE_GATE["positive_precision_min"] else "FAIL",
            "recall_reference": "PASS" if (primary["recall"] or 0) >= REFERENCE_GATE["recall_min"] else "FAIL",
        },
        "reference_gate": REFERENCE_GATE,
        "inputs": {"fixture": str(fixture.relative_to(ROOT)), "fixture_sha256": sha(fixture),
                   "aliases_sha256": sha(ALIASES_JSON), "mapper_sha256": sha(ROOT / "medmap" / "intake" / "mapper.py"),
                   "negative_policy_sha256": sha(ROOT / "medmap" / "intake" / "negative_policy.json")},
        "mapper": {"supported_evidence": len(mapper.supported), "aliases": len(mapper.aliases), "deterministic": deterministic},
        "fixture": {"items": len(items), "categories": dict(collections.Counter(it["category"] for it in items)),
                    "gold_labels": dict(collections.Counter(g["status"] for it in items for g in it["gold"])),
                    "zero_gold_items": sum(1 for n in gold_counts if n == 0), "unsupported_gold_ids": unsupported_gold},
        "primary": primary,
        "sensitivity_excluding_temporal_ambiguous": no_temporal,
        "by_category": by_cat,
        "extraction_count_distribution": {"pred_all": dist(pred_counts), "gold_all": dist(gold_counts),
                                          "pred_multi_symptom": dist([len(preds[it["id"]]) for it in multi]),
                                          "gold_multi_symptom": dist([len(it["gold"]) for it in multi])},
        "error_counts": dict(collections.Counter(e["kind"] for e in errors)),
        "errors_all": errors,
        "predictions": {it["id"]: preds[it["id"]] for it in items},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    p = primary
    print(json.dumps({k: result[k] for k in ("gate_result", "inputs", "mapper", "fixture", "error_counts")}, ensure_ascii=False, indent=1))
    print(json.dumps({k: p[k] for k in ("tp", "fp", "fn", "precision", "recall", "f1", "positive", "negative",
                                         "negation_accuracy", "polarity_flips", "exact_sentence_match")}, ensure_ascii=False, indent=1))
    print("sensitivity(no temporal):", {k: no_temporal[k] for k in ("precision", "recall", "f1")},
          "neg P", no_temporal["negative"]["precision"])
    print("by_category P/R:", {c: (v["precision"], v["recall"], v["fp"], v["fn"]) for c, v in by_cat.items()})
    print("dist:", json.dumps(result["extraction_count_distribution"], ensure_ascii=False))
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
