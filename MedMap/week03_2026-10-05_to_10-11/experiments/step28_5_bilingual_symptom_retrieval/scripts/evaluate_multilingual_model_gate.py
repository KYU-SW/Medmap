"""STEP28.5 경로 D(로컬 다국어 모델) 타당성 gate — STEP28 과 같은 질의·같은 기준(사전 고정).

모델: siglip2-base-patch16-224 텍스트 인코더(로컬 캐시, 신규 다운로드 없음, 학습 없음). get_text_features 정규화 벡터 코사인.
문서: STEP28 색인의 HPO phenotype 활성 term 이름 + EXACT 동의어(STEP28 xlm-roberta 와 같은 42,328 문자열).
질의: crosswalk 87 증거 중 STEP20 curated HPO id 가 있는 84 개의 terminology_ko 한국어 라벨. 정답 = curated HPO(+같은 CUI 의 HPO code).
gate: hit@5 ≥ 0.50 → MODEL_PATH_ENABLED(후보 생성만, 확정·표시 없음). 미달 → 사용 안 함.
참고 행: STEP28 xlm-roberta-base hit@5 = 0.0119(outputs/crosslingual_feasibility.json).
캐시: index/siglip2_hpo_embeddings.npz 가 있으면 재사용(STEP285_REBUILD_EMB=1 이면 다시 계산). 최초 계산 2026-10-11 1,801 s.
출력: outputs/multilingual_model_gate.json · outputs/multilingual_model_gate_rows.csv · index/siglip2_hpo_embeddings.npz(LOCAL)
"""
import csv
import time

import numpy as np

import s285_common as S
from search_new_ontology_concepts import OntologyIndex

CACHE = S.INDEX / "siglip2_hpo_embeddings.npz"


class Siglip:
    def __init__(self):
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(S.SIGLIP)
        self.model = AutoModel.from_pretrained(S.SIGLIP).to("cpu").eval()
        torch.set_grad_enabled(False)

    def embed(self, texts):
        b = self.tok(texts, padding="max_length", truncation=True, max_length=64, return_tensors="pt")
        v = self.model.get_text_features(**b)
        v = v.pooler_output if hasattr(v, "pooler_output") else v
        v = v.numpy()
        return v / np.linalg.norm(v, axis=1, keepdims=True)


def main():
    t0 = time.time()
    oi = OntologyIndex(S.ONT_DB)
    m = Siglip()
    rows = oi.q("SELECT t.term, t.cid FROM term t JOIN concept c ON c.cid=t.cid WHERE c.source='HPO' AND c.kind='phenotype' AND c.active=1 "
                "AND (t.ttype='HPO:name' OR t.ttype='HPO:syn:EXACT') ORDER BY t.cid, t.term")
    strs, ids = [r[0] for r in rows], [r[1] for r in rows]
    import os
    if CACHE.exists() and os.environ.get("STEP285_REBUILD_EMB") != "1":      # 재현 실행은 저장 임베딩 재사용(최초 계산 1,801 s)
        z = np.load(CACHE)
        assert list(z["ids"]) == ids and list(z["strs"]) == strs, "임베딩 캐시와 HPO 문자열 불일치"
        E = z["E"]
    else:
        E = np.concatenate([m.embed(strs[i:i + 128]) for i in range(0, len(strs), 128)])
        np.savez(CACHE, E=E, ids=np.array(ids), strs=np.array(strs))
    t_emb = time.time() - t0
    term = S.S28.load_terminology()
    cw = S.S28.evidence_crosswalk()
    with (S.S28.S20 / "curation/curated_mappings.tsv").open(encoding="utf-8") as fh:
        cur = {r["evidence_id"]: r for r in csv.DictReader(fh, delimiter="\t")}
    out = []
    for e in sorted(cw, key=lambda x: int(x.split("_")[1])):
        lab = term["evidence_short"].get(e, {}).get("label_ko", "")
        gold = {x.strip() for x in cur.get(e, {}).get("hpo_ids", "").replace(";", "|").split("|") if x.strip().startswith("HP:")}
        if not lab or not gold:
            continue
        gold_c = set(gold) | {c for g in gold for u in oi.cuis(g) for c in oi.codes(u) if c.startswith("HP:")}
        s = E @ m.embed([lab])[0]
        seen, top = set(), []
        for i in np.argsort(-s):
            if ids[i] not in seen:
                seen.add(ids[i])
                top.append((ids[i], strs[i], float(s[i])))
            if len(top) == 10:
                break
        rank = next((k + 1 for k, (c, _, _) in enumerate(top) if c in gold_c), None)
        out.append({"evidence_id": e, "label_ko": lab, "gold_hpo": ";".join(sorted(gold)), "rank": rank, "top1": top[0][0], "top1_term": top[0][1],
                    "top1_cos": round(top[0][2], 4)})
    n = len(out)
    hit = {str(k): S.rnd(sum(1 for r in out if r["rank"] and r["rank"] <= k) / n) for k in (1, 5, 10)}
    S.write_csv(S.OUT / "multilingual_model_gate_rows.csv", out)
    res = {"model": "google/siglip2-base-patch16-224 text tower (local, no fine-tuning)", "n_queries": n, "n_hpo_strings": len(strs), "hit@k": hit,
           "gate": "hit@5 >= 0.50", "MODEL_PATH_ENABLED": hit["5"] >= 0.5, "embedding_or_cache_load_seconds": round(t_emb, 1), "first_embedding_seconds": 1801.4,
           "reference_xlmr_step28": S.load_json(S.S28.OUT / "crosslingual_feasibility.json")["hit@k"]}
    S.dump_json(S.OUT / "multilingual_model_gate.json", res)
    print(S.dumps(res))


if __name__ == "__main__":
    main()
