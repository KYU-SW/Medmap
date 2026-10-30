"""STEP21 BASELINE_EXACT: 정규화 문장(공백 제거) 안에 사전 stem 이 그대로 있으면 그 concept.
순위 = 일치한 stem 길이(긴 것 우선). status 는 항상 present(부정·시점·화자 처리 없음 — 그대로 기록).
confidence = 1.0(일치) / 0.0(없음) → 정책상 AUTO_ACCEPT 또는 ABSTAIN 두 단계뿐.
출력: outputs/exact_predictions.csv
"""
import json

import el_common as c


def predict(text, dic):
    u = c.nospace(text)
    best = {}
    for d in dic:
        for s in (d["stem"], d["stem_alt"]):
            if s and s in u and len(s) > best.get(d["concept_id"], ("", 0))[1]:
                best[d["concept_id"]] = (d["expression"], len(s))
    ranked = sorted(best.items(), key=lambda kv: (-kv[1][1], kv[0]))
    preds = [{"concept": k, "status": "present", "score": 1.0, "matched": v[0]} for k, v in ranked]
    return preds, [k for k, _ in ranked][:5], (1.0 if preds else 0.0)


def main():
    dic = c.load_dictionary()
    rows = []
    for g in c.load_gold():
        preds, top, conf = predict(g["text_ko"], dic)
        rows.append({"utterance_id": g["utterance_id"], "split": g["split"], "text_ko": g["text_ko"],
                     "pred_mentions": json.dumps(preds, ensure_ascii=False), "ranked_top5": ";".join(top),
                     "top1": top[0] if top else "", "confidence": conf})
    c.write_csv(c.OUT / "exact_predictions.csv", rows)
    print("exact: predicted", sum(1 for r in rows if r["top1"]), "/", len(rows))


if __name__ == "__main__":
    main()
