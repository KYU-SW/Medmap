"""STEP26 데이터 준비: 외부 weak label 단위 구축 → near-dup cluster → DEVELOPMENT / HELD_OUT 분할 → 누수 감사 → 고정 모델 출력 cache.

단위 = 공백 제거 표현이 같은 외부 entity span(문서 여러 개에 반복되면 하나로 합침).
weak label(파일의 실제 태그만): BERT-NER-KO ST→WEAK_SYMPTOM, DS·BD→WEAK_NON_SYMPTOM, KBMC Body·Treatment→WEAK_NON_SYMPTOM,
KBMC Disease→WEAK_MIXED(증상 표현도 Disease 로 태깅됨). ST 와 비증상 태그가 같은 표현에 함께 붙으면 WEAK_CONFLICT(지표 제외).
분할: 같은 stem(조사 제거) + 같은 앞 2글자 block 안 difflib ≥ 0.80 을 union-find 로 묶은 cluster 단위 hash 50/50.
  → 같은/거의 같은 표현은 한쪽에만. 같은 문서의 다른 span 은 양쪽에 갈 수 있음(문서 겹침률 기록). STEP25 에서 전체 예측을 이미 봤으므로
    HELD_OUT 은 blind 가 아닌 frozen retrospective evaluation.
내부 집합: STEP23 core dev 59(DEV utility 제약용) · FIXED_REGRESSION_TEST core 109(보고 전용, 임계값 선택 금지) ·
           ko_medical_chat 첫 발화 1,677(COMPLEX 스트레스, 보고 전용)
출력: data/weak_label_inventory.csv · data/external_dev_manifest.csv · data/external_eval_manifest.csv · outputs/leakage_audit.json
      outputs/model_cache.npz · outputs/features.csv
"""
import collections
import difflib

import numpy as np
import torch

import s26_common as S


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def f(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def u(self, a, b):
        a, b = self.f(a), self.f(b)
        if a != b:
            self.p[max(a, b)] = min(a, b)


def bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


def main():
    occ = []
    for r in S.load_bert_ner_ko_docs():
        for t, x in r["spans"]:
            occ.append(("BERT_NER_KO", t, x, r["doc"]))
    for r in S25_load_kbmc():
        for t, x in r["spans"]:
            occ.append(("KBMC", t, x, r["id"]))
    by = collections.OrderedDict()
    for ds, t, x, doc in occ:
        k = S.nospace(x)
        if not k:
            continue
        u = by.setdefault(k, {"key": k, "surface": collections.Counter(), "cats": collections.Counter(), "datasets": set(), "docs": set()})
        u["surface"][x] += 1
        u["cats"][f"{ds}:{t}"] += 1
        u["datasets"].add(ds)
        u["docs"].add(doc)
    units = list(by.values())
    for u in units:
        groups = {S.WEAK_GROUP[tuple(c.split(":"))] for c in u["cats"]}
        if "WEAK_SYMPTOM" in groups and "WEAK_NON_SYMPTOM" in groups:
            w = "WEAK_CONFLICT"
        elif "WEAK_SYMPTOM" in groups:
            w = "WEAK_SYMPTOM"
        elif groups == {"WEAK_NON_SYMPTOM"}:
            w = "WEAK_NON_SYMPTOM"
        else:
            w = "WEAK_MIXED"
        u["weak_label"] = w
        u["text"] = sorted(u["surface"].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        u["stem"] = S.stem_key(u["text"])

    # clustering
    uf = UF(len(units))
    st_first = {}
    for i, u in enumerate(units):
        if u["stem"] in st_first:
            uf.u(i, st_first[u["stem"]])
        else:
            st_first[u["stem"]] = i
    blocks = collections.defaultdict(list)
    for i, u in enumerate(units):
        blocks[u["stem"][:2]].append(i)
    for idx in blocks.values():
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                x, y = units[idx[a]]["key"], units[idx[b]]["key"]
                sm = difflib.SequenceMatcher(None, x, y, autojunk=False)
                if sm.real_quick_ratio() >= 0.8 and sm.quick_ratio() >= 0.8 and sm.ratio() >= 0.8:
                    uf.u(idx[a], idx[b])
    roots = collections.defaultdict(list)
    for i in range(len(units)):
        roots[uf.f(i)].append(i)
    for r, members in roots.items():
        ck = min(units[i]["stem"] for i in members)
        for i in members:
            units[i]["cluster"] = ck
            units[i]["split"] = S.split_of(ck)

    # 누수
    train = S.read_csv(S.S23 / "data/expanded_train_expressions.csv")
    train_ns = [S.nospace(r["expression"]) for r in train]
    tset = set(train_ns)
    gold = S.S24.load_gold()
    gset = {S.nospace(g["text_ko"]) for g in gold}
    cross = 0
    for i, u in enumerate(units):
        u["train_exact"] = u["key"] in tset
        u["gold_exact"] = u["key"] in gset
        u["eligible"] = not u["train_exact"] and not u["gold_exact"] and u["weak_label"] != "WEAK_CONFLICT"
    dev_keys = [u["key"] for u in units if u["split"] == "DEVELOPMENT"]
    ev = [u for u in units if u["split"] != "DEVELOPMENT"]
    dev_by_block = collections.defaultdict(list)
    for k in dev_keys:
        dev_by_block[S.stem_key(k)[:2]].append(k)
    for u in ev:
        for k in dev_by_block.get(u["stem"][:2], []):
            if difflib.SequenceMatcher(None, u["key"], k, autojunk=False).ratio() >= 0.8:
                cross += 1
                break
    ner_docs = collections.defaultdict(set)
    for u in units:
        for d in u["docs"]:
            if d.startswith("NERKO"):
                ner_docs[d].add(u["split"])
    leak = {"n_units": len(units), "n_clusters": len(roots), "weak_label_counts": dict(collections.Counter(u["weak_label"] for u in units)),
            "split_counts": dict(collections.Counter((u["split"], u["weak_label"]) for u in units if u["eligible"]).items()),
            "train_exact_excluded": sum(u["train_exact"] for u in units), "gold_exact": sum(u["gold_exact"] for u in units),
            "conflict_excluded": sum(u["weak_label"] == "WEAK_CONFLICT" for u in units),
            "eval_units_near_dup_ge_0.80_to_dev_same_block": cross,
            "nerko_docs_spanning_both_splits": sum(len(v) == 2 for v in ner_docs.values()), "nerko_docs": len(ner_docs),
            "note": "cross-split near-dup 는 같은 앞 2글자 block 안에서만 검사(clustering 과 같은 범위)"}
    leak["split_counts"] = {f"{a}|{b}": v for (a, b), v in leak["split_counts"].items()}

    # 내부·보조 집합
    _, core_dev, core_test = S.S24.eval_sets()
    rows = []
    for u in units:
        if not u["eligible"]:
            continue
        rows.append({"row_id": "U_" + u["key"][:40] + f"_{len(rows)}", "set": "EXT_" + ("DEV" if u["split"] == "DEVELOPMENT" else "EVAL"),
                     "text": u["text"], "weak_label": u["weak_label"], "categories": ";".join(sorted(u["cats"])), "freq": sum(u["cats"].values()),
                     "datasets": ";".join(sorted(u["datasets"])), "n_docs": len(u["docs"]), "cluster": u["cluster"], "gold_concept": ""})
    for g in core_dev:
        rows.append({"row_id": g["utterance_id"], "set": "INT_DEV_CORE", "text": g["text_ko"], "weak_label": "", "gold_concept": g["primary_concept"]})
    for g in core_test:
        rows.append({"row_id": g["utterance_id"], "set": "INT_REGRESSION_CORE", "text": g["text_ko"], "weak_label": "", "gold_concept": g["primary_concept"]})
    for u in S.read_csv(S.S25_DIR / "data/eligible_external_examples.csv"):
        if u["dataset"] == "KO_MEDICAL_CHAT" and u["eligible_for_unlabeled_analysis"] == "True":
            rows.append({"row_id": u["unit_id"], "set": "KMC_COMPLEX_STRESS", "text": u["text"], "weak_label": "", "gold_concept": ""})

    inv = [{"row_id": r["row_id"], "set": r["set"], "weak_label": r["weak_label"], "categories": r.get("categories", ""), "freq": r.get("freq", ""),
            "datasets": r.get("datasets", ""), "n_docs": r.get("n_docs", ""), "cluster": r.get("cluster", ""), "text": r["text"]} for r in rows if r["set"].startswith("EXT")]
    S.write_csv(S.DATA / "weak_label_inventory.csv", inv)
    S.write_csv(S.DATA / "external_dev_manifest.csv", [r for r in inv if r["set"] == "EXT_DEV"])
    S.write_csv(S.DATA / "external_eval_manifest.csv", [r for r in inv if r["set"] == "EXT_EVAL"])

    # 고정 모델 출력 cache
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    lin, _ = S.S24.linear_model()
    cls = list(lin.classes_)
    tok = AutoTokenizer.from_pretrained(S.KOE_DIR)
    koe = AutoModelForSequenceClassification.from_pretrained(S.KOE_DIR).to("cpu").eval()
    max_len = S.load_json(S.S24.ENV_JSON)["selected_max_length"]
    texts = [S.norm(r["text"]) for r in rows]
    L = np.atleast_2d(lin.decision_function(texts))
    with torch.no_grad():
        T = np.concatenate([koe(**tok(texts[i:i + 128], padding=True, truncation=True, max_length=max_len, return_tensors="pt")).logits.float().numpy()
                            for i in range(0, len(texts), 128)])
    P = np.exp(T - T.max(1, keepdims=True))
    P /= P.sum(1, keepdims=True)
    np.savez(S.OUT / "model_cache.npz", row_id=np.array([r["row_id"] for r in rows]), L=L, P=P, classes=np.array(cls))

    tr_by_c = collections.defaultdict(list)
    for r, k in zip(train, train_ns):
        tr_by_c[r["canonical_id"]].append(bigrams(k))
    feats = []
    for i, r in enumerate(rows):
        ls, ps = np.sort(L[i]), np.sort(P[i])
        l1, k1 = cls[int(L[i].argmax())], cls[int(P[i].argmax())]
        x = S.nospace(r["text"])
        if len(x) <= 40:
            b, best = 0.0, 0.0
            for t in train_ns:
                sm = difflib.SequenceMatcher(None, x, t, autojunk=False)
                if sm.real_quick_ratio() > best and sm.quick_ratio() > best:
                    best = max(best, sm.ratio())
            sim = best
        else:
            sim = -1.0
        bx = bigrams(x)
        lex = max((len(bx & t) / len(bx | t) for t in tr_by_c[l1]), default=0.0)
        flags = S.complex_flags(r["text"])
        feats.append({**{k: r.get(k, "") for k in ("row_id", "set", "weak_label", "gold_concept", "text")},
                      "lin_top1": l1, "lin_top2": cls[int(np.argsort(-L[i])[1])], "lin_margin": round(float(ls[-1] - ls[-2]), 6),
                      "koe_top1": k1, "koe_conf": round(float(ps[-1]), 6), "koe_gap": round(float(ps[-1] - ps[-2]), 6), "agree": l1 == k1,
                      "train_sim": round(sim, 6), "length": len(x), "lex_overlap": round(lex, 6), "complex_flags": ";".join(flags)})
    S.write_csv(S.OUT / "features.csv", feats)
    leak["internal_rows"] = dict(collections.Counter(r["set"] for r in rows))
    S.dump_json(S.OUT / "leakage_audit.json", leak)
    print(S.dumps({k: v for k, v in leak.items()}))


def S25_load_kbmc():
    return S.S25.load_kbmc()


if __name__ == "__main__":
    main()
