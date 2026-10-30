"""STEP29.1 PROSPECTIVE_SYNTHETIC 생성(NLU 실행 없음, 평가 전 1회 — 있으면 덮어쓰지 않음).
방법: 증상 활용형 표(10 concept × 현재·부정·과거 및 연결형 '-고'·'-는데')와 주체·시점 슬롯을 템플릿으로 조합. 정답은 **슬롯 의미**(어떤 활용형·주체·시점을 넣었는지)에서
 부여하고 NLU 규칙을 쓰지 않는다. 기존 자료(pilot_gold·STEP29/29.1 계약·STEP23 학습·REGRESSION·SILVER442·WEAKNON903)와 ko_key 완전 중복 문장은 제외.
 seed 20261011 로 템플릿별 층화 표본. 사람 검증 Gold 아님(합성).
정답 형식 = 계약과 같음(anchor·concept_any·assertion_any·temporality_any·experiencer_any, 문장 단위 must_not_auto·no_symptom_mentions·no_model_positive)."""
import json
import random

import s291_common as S

SYM = [  # concept, anchor, 현재, 현재-고, 현재-는데, 부정, 부정-는데, 과거, 과거-는데
    ("cough", "기침", "기침이 나요", "기침이 나고", "기침이 나는데", "기침은 안 나요", "기침은 안 나는데", "기침이 났어요", "기침이 났는데"),
    ("fever", "열", "열이 나요", "열이 나고", "열이 나는데", "열은 없어요", "열은 없는데", "열이 났어요", "열이 났는데"),
    ("dyspnea", "숨", "숨이 차요", "숨이 차고", "숨이 찬데", "숨은 안 차요", "숨은 안 찬데", "숨이 찼어요", "숨이 찼는데"),
    ("pain", "머리", "머리가 아파요", "머리가 아프고", "머리가 아픈데", "머리는 안 아파요", "머리는 안 아픈데", "머리가 아팠어요", "머리가 아팠는데"),
    ("pain", "배", "배가 아파요", "배가 아프고", "배가 아픈데", "배는 안 아파요", "배는 안 아픈데", "배가 아팠어요", "배가 아팠는데"),
    ("nausea", "메스", "속이 메스꺼워요", "속이 메스껍고", "속이 메스꺼운데", "메스껍지는 않아요", "메스껍지는 않은데", "속이 메스꺼웠어요", "속이 메스꺼웠는데"),
    ("diarrhea", "설사", "설사를 해요", "설사를 하고", "설사를 하는데", "설사는 안 해요", "설사는 안 하는데", "설사를 했어요", "설사를 했는데"),
    ("dizziness", "어지", "어지러워요", "어지럽고", "어지러운데", "어지럽지는 않아요", "어지럽지는 않은데", "어지러웠어요", "어지러웠는데"),
    ("vomiting", "구토", "구토를 해요", "구토를 하고", "구토를 하는데", "구토는 안 해요", "구토는 안 하는데", "구토를 했어요", "구토를 했는데"),
    ("cough", "가래", "가래가 끓어요", "가래가 끓고", "가래가 끓는데", "가래는 없어요", "가래는 없는데", "가래가 끓었어요", "가래가 끓었는데"),
]
OTHER = ["엄마가 ", "아이가 ", "남편이 ", "동생이 ", "아버지가 "]
DRUG = ["기침약", "해열제", "진통제", "소화제", "감기약", "두통약"]
DIS = ["고혈압", "당뇨", "천식", "위염", "비염", "통풍"]


def josa(w, a, b):
    ch = w[-1]
    return a if (ord(ch) - 0xAC00) % 28 else b


def mm(s, assertion, temp, exp, i=None):
    c = s[0] if s[1] != "가래" else None
    concept = [s[0]] if s[1] != "가래" else ["cough", None]
    return {"anchor": s[1], "concept_any": concept, "assertion_any": [assertion], "temporality_any": temp, "experiencer_any": exp, "forbid": []}


def gen():
    out = []
    PAT, OTH = ["PATIENT"], ["OTHER_PERSON", "MULTIPLE"]
    NOWT = ["CURRENT", "ONGOING"]
    for s in SYM:
        out.append(("T1_PRESENT", s[2], [mm(s, "PRESENT", NOWT, PAT)], {}))
        out.append(("T1_PRESENT_ONSET", "어제부터 " + s[2], [mm(s, "PRESENT", ["ONGOING", "CURRENT"], PAT)], {}))
        out.append(("T1_ABSENT", s[5], [mm(s, "ABSENT", NOWT, PAT)], {"no_model_positive": True}))
        out.append(("T1_PAST", "지난주에 " + s[7], [mm(s, "PRESENT", ["PAST", "RESOLVED"], PAT)], {"no_model_positive": True}))
        for o in OTHER:
            out.append(("T1_OTHER", o + s[2], [mm(s, "PRESENT", NOWT, OTH)], {"no_model_positive": True}))
        out.append(("T4_RESOLVED", s[7] + " 오늘은 괜찮아요.", [mm(s, "PRESENT", ["RESOLVED"], PAT)], {"no_model_positive": True}))
        for d in DRUG:
            out.append(("T6_DRUG_SYM", d + josa(d, "을", "를") + " 먹었는데 " + s[2], [mm(s, "PRESENT", NOWT, PAT)], {}))
        for d in DIS:
            out.append(("T6_DIS_SYM", d + josa(d, "이", "가") + " 있는데 " + s[2], [mm(s, "PRESENT", NOWT, PAT)], {}))
    for a in SYM:
        for b in SYM:
            if a[1] == b[1] or a[0] == b[0]:
                continue
            out.append(("T2_BOTH", a[3] + " " + b[2], [mm(a, "PRESENT", NOWT, PAT), mm(b, "PRESENT", NOWT, PAT)], {}))
            out.append(("T2_NEG_POS", a[6] + " " + b[2], [mm(a, "ABSENT", NOWT, PAT), mm(b, "PRESENT", NOWT, PAT)], {}))
            out.append(("T2_PAST_NOW", a[8] + " 지금은 " + b[2], [mm(a, "PRESENT", ["PAST"], PAT), mm(b, "PRESENT", NOWT, PAT)], {}))
            out.append(("T3_SWITCH", "엄마는 " + a[3] + " 저는 " + b[2], [mm(a, "PRESENT", NOWT, OTH), mm(b, "PRESENT", NOWT, PAT)], {}))
            out.append(("T4_CONTROL", a[7] + " 오늘은 " + b[2], [mm(a, "PRESENT", ["PAST"], PAT), mm(b, "PRESENT", NOWT, PAT)], {}))
    for d in DRUG:
        out.append(("T6_DRUG_ONLY", d + josa(d, "을", "를") + " 먹었어요", [], {"no_symptom_mentions": True}))
    for d in DIS:
        out.append(("T6_DIS_ONLY", d + josa(d, "이", "가") + " 있어요", [], {"no_symptom_mentions": True}))
    return out


def main():
    P = S.DATA / "prospective_synthetic_cases.json"
    if P.exists():
        print("exists", S.sha256(P)[:16])
        return
    seen = set()
    for r in S.read_csv(S.S21_DIR / "data/pilot_gold.csv"):
        seen.add(S.ko_key(r["text_ko"]))
    for f in (S.S29_DIR / "data/synthetic_nlu_contracts.json", S.DATA / "contract_cases.json"):
        for c in json.loads(f.read_text(encoding="utf-8"))["contracts"]:
            seen.add(S.ko_key(c["text"]))
    for r in S.read_csv(S.S23_DIR / "data/expanded_train_expressions.csv"):
        seen.add(S.ko_key(r["expression"]))
    for r in S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv"):
        seen.add(S.ko_key(r["raw_expression"]))
    for r in S.read_csv(S.S28_DIR / "outputs/weak_non_check.csv"):
        seen.add(S.ko_key(r["text"]))
    allc = [x for x in gen() if S.ko_key(x[1]) not in seen]
    rng = random.Random(20261011)
    by = {}
    for x in allc:
        by.setdefault(x[0], []).append(x)
    quota = {"T2_BOTH": 30, "T2_NEG_POS": 30, "T2_PAST_NOW": 25, "T3_SWITCH": 25, "T4_CONTROL": 20, "T1_OTHER": 20, "T6_DRUG_SYM": 15, "T6_DIS_SYM": 15}
    pick = []
    for k, lst in sorted(by.items()):
        rng.shuffle(lst)
        pick += lst[:quota.get(k, len(lst))]
    cases = [{"id": f"PS{i + 1:03d}", "template": t, "text": txt, "mentions": ms, "must_not_auto": [], "no_symptom_mentions": o.get("no_symptom_mentions", False),
              "max_symptom_mentions": None, "no_model_positive": o.get("no_model_positive", False), "forbid_assertion": []} for i, (t, txt, ms, o) in enumerate(pick)]
    S.dump_json(P, {"label": "PROSPECTIVE_SYNTHETIC — 템플릿 슬롯 정답(NLU 규칙 미사용), 기존 자료와 문장 중복 제외, 사람 검증 아님", "method": __doc__, "seed": 20261011,
                    "excluded_duplicates": len(gen()) - len(allc), "by_template": {k: sum(1 for c in cases if c["template"] == k) for k in sorted(by)}, "contracts": cases})
    print(len(cases), S.sha256(P)[:16])


if __name__ == "__main__":
    main()
