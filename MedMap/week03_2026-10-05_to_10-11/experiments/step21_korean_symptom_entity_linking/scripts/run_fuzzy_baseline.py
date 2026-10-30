"""STEP21 BASELINE_FUZZY: 패키지 설치 없이 문자 유사도로 concept 순위.

expression e 와 문장 u(둘 다 공백 제거)에 대해:
  containment(e,u) = |bigram(e) ∩ bigram(u)| / |bigram(e)|          — e 의 글자쌍이 u 에 얼마나 들어 있나(0~1)
  window_sim(e,u)  = max difflib.SequenceMatcher ratio(e, u[i:i+len(e)+d]), d∈{-1,0,+1}  — 가장 비슷한 구간의 편집 유사도(0~1)
  token_overlap    = e 의 어절 앞 2글자가 u 어절 앞 2글자와 겹치는 비율(동점 처리용)
  fused            = (containment + window_sim) / 2                  — concept 점수는 그 concept 표현들의 최대값
문장 길이의 1.5배를 넘는 긴 사전 표현(질문문)은 window_sim 을 계산하지 않고 containment 만 쓴다(fused = containment/2).
score 는 확률이 아니다. threshold(T_high/T_low/T_multi)는 evaluate 단계에서 dev split 으로만 정한다.
출력: outputs/fuzzy_predictions.csv (상위 5개 concept 과 점수)
"""
import json
from difflib import SequenceMatcher

import el_common as c


def tok2(s):
    return {w[:2] for w in c.norm(s).split() if w}


def score_expr(e_ns, e_raw, u_ns, u_raw):
    be = c.char_ngrams(e_ns)
    if not be:
        return 0.0, 0.0, 0.0
    cont = len(be & c.char_ngrams(u_ns)) / len(be)
    if cont == 0:
        return 0.0, 0.0, 0.0
    win = 0.0
    if len(e_ns) <= 1.5 * len(u_ns):
        L = len(e_ns)
        for d in (-1, 0, 1):
            w = max(1, L + d)
            for i in range(0, max(1, len(u_ns) - w + 1)):
                win = max(win, SequenceMatcher(None, e_ns, u_ns[i:i + w]).ratio())
    te = tok2(e_raw)
    tov = len(te & tok2(u_raw)) / len(te) if te else 0.0
    return (cont + win) / 2, cont, tov


def predict(text, dic):
    u_ns = c.nospace(text)
    best = {}
    for d in dic:
        for s in filter(None, (d["stem"], d["stem_alt"])):
            f, cont, tov = score_expr(s, d["expression"], u_ns, text)
            key = d["concept_id"]
            if (f, tov) > best.get(key, (0.0, 0.0, ""))[:2]:
                best[key] = (f, tov, d["expression"])
    ranked = sorted(best.items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0]))[:5]
    return [{"concept": k, "status": "present", "score": round(v[0], 4), "token_overlap": round(v[1], 4),
             "matched": v[2]} for k, v in ranked]


def main():
    dic = c.load_dictionary()
    rows = []
    for g in c.load_gold():
        top = predict(g["text_ko"], dic)
        rows.append({"utterance_id": g["utterance_id"], "split": g["split"], "text_ko": g["text_ko"],
                     "ranked_top5_scored": json.dumps(top, ensure_ascii=False),
                     "ranked_top5": ";".join(t["concept"] for t in top), "top1": top[0]["concept"] if top else "",
                     "confidence": top[0]["score"] if top else 0.0})
    c.write_csv(c.OUT / "fuzzy_predictions.csv", rows)
    print("fuzzy: rows", len(rows))


if __name__ == "__main__":
    main()
