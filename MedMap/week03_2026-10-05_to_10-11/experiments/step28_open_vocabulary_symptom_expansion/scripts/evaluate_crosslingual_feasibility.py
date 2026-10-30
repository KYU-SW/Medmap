"""STEP28 경로 C 타당성 gate(사전 고정). 로컬 xlm-roberta-base(신규 다운로드 없음) 평균 풀링 임베딩으로 한국어 → HPO 영어 검색이 되는지 본다.

질의: crosswalk 87 증거의 terminology_ko 한국어 라벨 중 STEP20 curated HPO id 가 있는 것(정답 = curated HPO id, 같은 CUI 의 HPO code 포함).
지표: hit@1·hit@5·hit@10. gate: hit@5 ≥ 0.50 → PATH_C_ENABLED(후보 생성만, 표시·확정 없음). 미달 → 경로 C 를 쓰지 않는다.
질의는 짧은 정식 라벨이라 실제 구어보다 쉬운 조건(상한 추정).
출력: outputs/crosslingual_feasibility.json · index/xlmr_hpo_embeddings.npz(LOCAL)
"""
import time

import s28_common as S
from search_new_ontology_concepts import CrossLingual, OntologyIndex


def main():
    t0 = time.time()
    oi = OntologyIndex()
    cl = CrossLingual(oi)
    t_build = time.time() - t0
    term = S.load_terminology()
    cw = S.evidence_crosswalk()
    import csv
    with (S.S20 / "curation/curated_mappings.tsv").open(encoding="utf-8") as fh:
        cur = {r["evidence_id"]: r for r in csv.DictReader(fh, delimiter="\t")}
    rows = []
    for e in sorted(cw, key=lambda x: int(x.split("_")[1])):
        lab = term["evidence_short"].get(e, {}).get("label_ko", "")
        gold = {x.strip() for x in cur.get(e, {}).get("hpo_ids", "").replace(";", "|").split("|") if x.strip().startswith("HP:")}
        if not lab or not gold:
            continue
        gold_c = set(gold) | {c for g in gold for u in oi.cuis(g) for c in oi.codes(u) if c.startswith("HP:")}
        res = cl.search(lab, k=10)
        ids = [r["cid"] for r in res]
        rank = next((i + 1 for i, x in enumerate(ids) if x in gold_c), None)
        rows.append({"evidence_id": e, "label_ko": lab, "gold_hpo": ";".join(sorted(gold)), "rank": rank, "top1": ids[0], "top1_term": res[0]["matched_term"],
                     "top1_cos": res[0]["lexical_score"]})
    n = len(rows)
    hit = {k: S.rnd(sum(1 for r in rows if r["rank"] and r["rank"] <= k) / n) for k in (1, 5, 10)}
    enabled = hit[5] >= 0.5
    S.write_csv(S.OUT / "crosslingual_feasibility_rows.csv", rows)
    out = {"n_queries": n, "hit@k": hit, "gate": "hit@5 >= 0.50", "PATH_C_ENABLED": enabled, "n_hpo_strings": len(cl.strs),
           "embedding_build_or_load_seconds": round(t_build, 1), "model": "xlm-roberta-base (local cache, mean pooling, no fine-tuning)",
           "note": "짧은 정식 라벨 질의 = 쉬운 조건. 미달이면 경로 C 미사용"}
    S.dump_json(S.OUT / "crosslingual_feasibility.json", out)
    print(S.dumps(out))


if __name__ == "__main__":
    main()
