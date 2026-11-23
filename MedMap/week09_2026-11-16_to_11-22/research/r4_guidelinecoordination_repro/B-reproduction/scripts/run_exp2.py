# -*- coding: utf-8 -*-
"""
SUBAGENT B - 실험2(규칙 쌍 관계 판정) 결정적 재현 실행기.

- 원본 코드(src_copy/pipeline, upstream commit deb4ae34) 를 수정 없이 import 한다.
- pipeline/__init__.py 는 langgraph/langchain(LLM 단계)을 import 하므로 실행하지 않고,
  'pipeline' 이름의 빈 패키지 모듈을 만들어 __path__ 만 지정한다(원본 파일 무수정).
- 네트워크 차단: socket.connect 계열을 막아 LLM/외부 호출이 생기면 즉시 예외가 나게 한다.
- LLM 관련 모듈(graph, graph_api, processors, standard_library) 은 import 하지 않는다.

모드
  faithful_lsh        : 원본 기본값 ConflictResolver(rules, predicates=[]).generate_report()
                        (predicates.json 미공개 -> 빈 리스트)
  faithful_exhaustive : 동일, 단 use_lsh_filter=False, use_bucket_filter=False, 전 쌍
  atom_lsh / atom_exhaustive : [추가 변형, 원본 아님] 각 pred.X 를 독립 Bool 원자
                        "$ Has(atom.X) $" 로 합성한 predicates 를 넣어 Z3 경로를 실제로 태움
"""
import sys, os, json, time, csv, types, socket, argparse, platform, re

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.dirname(HERE)
SRC = os.path.join(B, "src_copy")

# ---- network guard ----
def _blocked(*a, **k):
    raise RuntimeError("NETWORK BLOCKED by run_exp2.py guard")
socket.socket.connect = _blocked
socket.socket.connect_ex = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked

# ---- load pipeline without __init__ ----
pkg = types.ModuleType("pipeline")
pkg.__path__ = [os.path.join(SRC, "pipeline")]
sys.modules["pipeline"] = pkg
from pipeline import analyzer as A  # noqa: E402
import z3  # noqa: E402

for forbidden in ("pipeline.graph", "pipeline.graph_api", "langchain_openai", "langchain_core", "langgraph", "openai", "httpx", "requests"):
    assert forbidden not in sys.modules, forbidden

CONFLICT_LABELS = {"local_conflict", "intrinsic_conflict", "implication_conflict",
                   "intrinsic_disagreement", "implication_disagreement"}
STRICT_CONFLICT_LABELS = {"local_conflict", "intrinsic_conflict", "implication_conflict"}
REDUNDANCY_LABELS = {"complete_redundancy", "contained_redundancy"}


def atom_predicates(rules):
    preds = sorted({p for r in rules for p in re.findall(r"pred\.[A-Za-z0-9_]+", r.get("condition") or "")})
    return [{"id": p, "formal_definition": f"$ Has(atom.{p.split('.', 1)[1]}) $"} for p in preds]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True,
                    choices=["faithful_lsh", "faithful_exhaustive", "atom_lsh", "atom_exhaustive"])
    ap.add_argument("--outdir", default=os.path.join(B, "results"))
    args = ap.parse_args()

    # 원본 RuleAnalyzer 는 cwd 의 gen/predicate_relations.json 을 읽으므로, 없는 곳에서 실행
    os.chdir(os.path.join(B, "logs"))
    assert not os.path.exists("gen/predicate_relations.json")

    rules = json.load(open(os.path.join(SRC, "rules_gold.json"), encoding="utf-8"))
    predicates = atom_predicates(rules) if args.mode.startswith("atom") else []
    exhaustive = args.mode.endswith("exhaustive")

    t0 = time.perf_counter()
    resolver = A.ConflictResolver(rules, predicates)
    t1 = time.perf_counter()

    lsh_pairs = None
    if not exhaustive:
        lsh_pairs = resolver.rule_analyzer._find_similar_rule_pairs_lsh(num_bands=20, rows_per_band=5,
                                                                        similarity_threshold=0.3)
    t2 = time.perf_counter()

    report = resolver.generate_report(
        analyze_predicates=True, analyze_rules=True,
        max_rule_pairs=10**9 if exhaustive else 10000,
        lsh_similarity_threshold=0.3, lsh_num_bands=20, lsh_rows_per_band=5,
        use_lsh_filter=not exhaustive, use_bucket_filter=not exhaustive,
    )
    t3 = time.perf_counter()

    os.makedirs(args.outdir, exist_ok=True)
    tag = args.mode
    resolver.export_report(report, os.path.join(args.outdir, f"exp2_{tag}_upstream_report.json"))

    rmap = {r["id"]: r for r in rules}
    all_pairs = report.redundant_rules + report.conflicting_rules + report.other_rule_relations
    csv_path = os.path.join(args.outdir, f"exp2_{tag}_pairs.csv")
    cols = ["mode", "rule_a", "rule_b", "overall_relation", "condition_relation", "action_relation",
            "is_conflict_family", "is_strict_conflict", "is_redundancy", "subjects_overlap",
            "permission_a", "permission_b", "condition_a", "condition_b", "source_a", "source_b",
            "same_source", "in_lsh_candidates", "recommendation"]
    from collections import Counter
    cnt = Counter()
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for p in sorted(all_pairs, key=lambda x: (x.rule_a, x.rule_b)):
            ra, rb = rmap[p.rule_a], rmap[p.rule_b]
            act = A.ActionAnalyzer.analyze_pair(ra["action"], rb["action"])
            ov = p.overall_relation.value
            cnt[ov] += 1
            sa = ra["provenance"][0]["source"] if ra["provenance"] else ""
            sb = rb["provenance"][0]["source"] if rb["provenance"] else ""
            key = tuple(sorted((p.rule_a, p.rule_b)))
            w.writerow({
                "mode": tag, "rule_a": p.rule_a, "rule_b": p.rule_b,
                "overall_relation": ov,
                "condition_relation": p.condition_relation.value,
                "action_relation": p.action_relation.value,
                "is_conflict_family": int(ov in CONFLICT_LABELS),
                "is_strict_conflict": int(ov in STRICT_CONFLICT_LABELS),
                "is_redundancy": int(ov in REDUNDANCY_LABELS),
                "subjects_overlap": "|".join(sorted(act.subjects_overlap)),
                "permission_a": ra["action"].get("permission", ""),
                "permission_b": rb["action"].get("permission", ""),
                "condition_a": ra.get("condition", ""), "condition_b": rb.get("condition", ""),
                "source_a": sa, "source_b": sb, "same_source": int(sa == sb),
                "in_lsh_candidates": "" if lsh_pairs is None else int(key in lsh_pairs),
                "recommendation": p.recommendation,
            })

    n = len(rules)
    summary = {
        "mode": tag,
        "upstream_commit": "deb4ae34bdb055f93301bd93ed640d8c77e0ee5e",
        "python": platform.python_version(), "z3": z3.get_version_string(),
        "n_rules": n, "n_predicates_supplied": len(predicates),
        "total_possible_pairs": n * (n - 1) // 2,
        "lsh_candidate_pairs": None if lsh_pairs is None else len(lsh_pairs),
        "analyzed_pairs_total(incl_transitive_closure)": len(all_pairs),
        "relation_counts": dict(sorted(cnt.items())),
        "conflict_family_pairs": sum(v for k, v in cnt.items() if k in CONFLICT_LABELS),
        "strict_conflict_pairs": sum(v for k, v in cnt.items() if k in STRICT_CONFLICT_LABELS),
        "redundancy_pairs": sum(v for k, v in cnt.items() if k in REDUNDANCY_LABELS),
        "condition_relation_counts": dict(Counter(p.condition_relation.value for p in all_pairs)),
        "timing_sec": {"init": round(t1 - t0, 3), "lsh_candidates_only": round(t2 - t1, 3),
                       "generate_report(incl_lsh)": round(t3 - t2, 3), "total": round(t3 - t0, 3)},
        "csv": csv_path,
    }
    with open(os.path.join(args.outdir, f"exp2_{tag}_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
