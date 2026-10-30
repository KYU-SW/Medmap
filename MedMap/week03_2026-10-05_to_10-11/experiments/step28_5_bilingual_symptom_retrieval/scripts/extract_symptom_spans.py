"""STEP28.5 증상 구문 추출(사전 고정 규칙). 완전한 NLU 아님 — 부정·시점·주체는 '잃지 않고 전달'만 한다(STEP29 대상).

방법 K(기본) = kiwipiepy 0.23.2(로컬 설치, 오프라인) 형태소:
 1 절 분리: 종결어미(EF)·연결어미(EC)·문장부호(SF·SP) 뒤에서 자른다. 단 EC 가 '-어/아/게/지'(보조용언 연결: 아파 죽겠어요, 하지 않아요)면 자르지 않는다.
 2 절마다: 명사구 = 연속 명사류(NNG·NNP·XR·SL·NR, 접미 XSN 포함) 중 마지막 덩어리(핵어 = 마지막 명사) · 술어 = 첫 용언(VV·VA·VA-I·VV-I·XSA·XSV 앞 명사 포함)
    부정 = 없(VA)·않(VX)·안(MAG)·못(MAG)·아니(VCN) · 시점 = 시간 명사(어제·오늘·요즘 …)+부터/전/동안 · 주체 = 친족 명사 + 주격/보조사
 3 술어 분류(PRED_CLASS): PAIN(아프·쑤시·결리·욱신·뻐근·쓰리·따갑·저리) · OCCUR(나·있·생기·들) · ABSENT(없) · OTHER(그 외 용언 = 증상 서술어 자체, 예 메스껍·차·토하)
 4 검색 구문: 명사구 있음 → OCCUR/ABSENT/없음: 명사구 · PAIN: '명사구 통증'(부위+통증) · OTHER: '명사구 + 용언 원형'(숨 차다) / 명사구 없음 → 용언 원형(메스껍다)
 5 명사·용언이 하나도 없으면 SPAN_EXTRACTION_FAILURE(원문 유지)
 [변경 기록] 접두사(XPN, 예 고-혈압) 를 다음 명사에 붙이는 처리는 smoke('고혈압' → '혈압')를 본 뒤 추가한 일반 파싱 수정. 시점 표현은 그 절에만 붙이고
  temporal_scope_confirmed=False 로 남긴다(다른 절로의 적용 범위 판단은 STEP29).
방법 R(대조) = 형태소 없이 STEP27 조사 제거(stem_key) 한 덩어리(STEP28 방식). 절 분리·술어 분류 없음.
원문 위치: 각 구문의 char start/end(입력 기준)·절 원문 보존.
"""
from __future__ import annotations

import re

import s285_common as S

NOUN = {"NNG", "NNP", "XR", "SL", "NR", "NNB"}
PRED = {"VV", "VA", "VA-I", "VV-I", "VV-R", "VA-R"}
PAIN = re.compile(r"^(아프|쑤시|결리|욱신|뻐근|쓰리|따갑|저리|시리|당기|땡기)")
OCCUR = re.compile(r"^(나|있|생기|들|오)$")
TIME_N = re.compile(r"^(어제|오늘|그제|그저께|요즘|최근|아까|지난|어젯밤|아침|저녁|밤|새벽|며칠|일주일|한달|작년|올해|예전|전|동안|부터)$")
KIN = re.compile(r"^(엄마|아빠|어머니|아버지|아이|애|남편|아내|딸|아들|친구|동생|언니|오빠|형|누나|할머니|할아버지|부모)$")
NEG_TOK = {("없", "VA"), ("않", "VX"), ("안", "MAG"), ("못", "MAG"), ("못하", "VX"), ("아니", "VCN")}
NO_CUT_EC = re.compile(r"^(어|아|게|지|여|고서)$")

_KIWI = None


def kiwi():
    global _KIWI
    if _KIWI is None:
        from kiwipiepy import Kiwi
        _KIWI = Kiwi()
    return _KIWI


def lemma(tok) -> str:
    return tok.form + "다"


def clauses(toks):
    cur, out = [], []
    for i, t in enumerate(toks):
        cur.append(t)
        cut = t.tag in ("SF", "SP", "EF") or (t.tag == "EC" and not NO_CUT_EC.match(t.form))
        if cut:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [c for c in out if any(x.tag in NOUN or x.tag in PRED or x.tag in ("XSA", "XSV") for x in c)]


def extract_kiwi(text: str) -> list[dict]:
    toks = kiwi().tokenize(text)
    spans = []
    for c in clauses(toks):
        nouns, groups, pred, neg, temporal, subj = [], [], None, False, [], "PATIENT_OR_UNSTATED"
        prefix = None
        for j, t in enumerate(c):
            if t.tag == "XPN":
                prefix = t
                continue
            if t.tag in NOUN and prefix is not None:
                t = type("T", (), {"form": prefix.form + t.form, "tag": t.tag, "start": prefix.start, "len": t.start + t.len - prefix.start})()
            prefix = None
            if t.tag in NOUN or t.tag == "XSN":
                if TIME_N.match(t.form):
                    temporal.append(t.form)
                    continue
                if KIN.match(t.form):
                    subj = "OTHER_PERSON(" + t.form + ")"
                    continue
                if t.tag == "XSN" and nouns:
                    nouns[-1] = (nouns[-1][0] + t.form, nouns[-1][1], t.start + t.len)
                else:
                    if groups and nouns and t.start > nouns[-1][2] + 1:
                        pass
                    nouns.append((t.form, t.start, t.start + t.len))
            elif t.tag == "JX" and t.form == "부터":
                temporal.append("부터")
            if (t.form, t.tag) in NEG_TOK:
                neg = True
            if pred is None and (t.tag in PRED or t.tag in ("XSA", "XSV")):
                if t.tag in ("XSA", "XSV") and nouns:
                    pred = type("P", (), {"form": nouns[-1][0] + t.form, "start": nouns[-1][1], "len": t.start + t.len - nouns[-1][1], "tag": t.tag})()
                    nouns = nouns[:-1]
                elif t.tag in PRED:
                    pred = t
        # 명사구 = 술어 앞의 마지막 연속 명사 덩어리(공백 1칸 이내)
        np_toks = []
        for nform, s0, e0 in nouns:
            if pred is not None and s0 >= pred.start:
                break
            if np_toks and s0 > np_toks[-1][2] + 1:
                np_toks = []
            np_toks.append((nform, s0, e0))
        if not np_toks and nouns and pred is None:
            np_toks = nouns[-1:]
        np_text = " ".join(x[0] for x in np_toks)
        if pred is None:
            pc = "NONE"
        elif (pred.form, getattr(pred, "tag", "")) == ("없", "VA"):
            pc = "ABSENT"
        elif PAIN.match(pred.form):
            pc = "PAIN"
        elif OCCUR.match(pred.form):
            pc = "OCCUR"
        else:
            pc = "OTHER"
        if not np_text and pred is None:
            continue
        if np_text:
            query = np_text + " 통증" if pc == "PAIN" else np_text + " " + lemma(pred) if pc == "OTHER" else np_text
        else:
            query = lemma(pred)
        s0 = min([x[1] for x in np_toks] + ([pred.start] if pred is not None else []))
        e0 = max([x[2] for x in np_toks] + ([pred.start + pred.len] if pred is not None else []))
        spans.append({"method": "KIWI", "span_text": text[s0:e0], "start": s0, "end": e0, "clause_text": text[c[0].start:c[-1].start + c[-1].len],
                      "noun_phrase": np_text, "head_noun": np_toks[-1][0] if np_toks else "", "predicate": lemma(pred) if pred is not None else "",
                      "pred_class": pc, "query_ko": query, "polarity": "NEGATIVE" if neg else "POSITIVE_OR_UNSTATED",
                      "temporal": ";".join(temporal), "temporal_scope_confirmed": False, "subject": subj})
    if not spans:
        return [{"method": "KIWI", "span_text": text, "start": 0, "end": len(text), "clause_text": text, "noun_phrase": "", "head_noun": "", "predicate": "",
                 "pred_class": "NONE", "query_ko": "", "polarity": "", "temporal": "", "subject": "", "failure": "SPAN_EXTRACTION_FAILURE"}]
    return spans


def extract_rule(text: str) -> list[dict]:
    st = S.S28.josa_strip(S.norm(text))
    return [{"method": "RULE", "span_text": text, "start": 0, "end": len(text), "clause_text": text, "noun_phrase": st, "head_noun": st.split()[-1] if st else "",
             "predicate": "", "pred_class": "NONE", "query_ko": st, "polarity": "", "temporal": "", "subject": ""}]


def main():
    sil = S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv")
    smoke = ["코피가 나요", "머리가 아파요", "열이 없어요", "숨이 차요", "토했어요", "메스꺼워요", "목이 아파요", "고혈압", "결핵",
             "어제부터 코피가 나고 머리가 아파요. 열은 없어요."]
    rows = []
    for src, texts in (("SILVER442", [r["raw_expression"] for r in sil]), ("SMOKE", smoke)):
        for t in texts:
            k, r = extract_kiwi(t), extract_rule(t)
            for i, sp in enumerate(k):
                rows.append({"set": src, "input": t, "n_spans_kiwi": len(k), "span_idx": i, **{f"kiwi_{a}": sp.get(a, "") for a in
                             ("span_text", "start", "end", "noun_phrase", "head_noun", "predicate", "pred_class", "query_ko", "polarity", "temporal", "subject", "failure")},
                             "rule_query": r[0]["query_ko"], "head_agree": S.ko_key(sp["head_noun"]) == S.ko_key(r[0]["head_noun"])})
    S.wcsv(S.DATA / "span_extraction.csv", rows)
    sv = [r for r in rows if r["set"] == "SILVER442"]
    import collections
    summ = {"silver_rows": len(sv), "silver_inputs": len({r["input"] for r in sv}), "kiwi_failures": sum(bool(r["kiwi_failure"]) for r in sv),
            "multi_span_inputs": len({r["input"] for r in sv if int(r["n_spans_kiwi"]) > 1}),
            "pred_class": dict(collections.Counter(r["kiwi_pred_class"] for r in sv)),
            "kiwi_vs_rule_head_agree": S.rnd(sum(r["head_agree"] for r in sv) / len(sv))}
    S.dump_json(S.OUT / "span_extraction_summary.json", summ)
    print(S.dumps(summ))
    for r in rows:
        if r["set"] == "SMOKE":
            print(r["input"], "|", r["kiwi_span_text"], "|", r["kiwi_query_ko"], r["kiwi_pred_class"], r["kiwi_polarity"], r["kiwi_temporal"], "| rule:", r["rule_query"])


if __name__ == "__main__":
    main()
