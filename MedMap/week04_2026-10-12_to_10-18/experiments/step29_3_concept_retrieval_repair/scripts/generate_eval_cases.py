"""STEP29.3 §11 평가 세트(의미 구조 → 문장, NLU·검색기 실행 없음). 평가 전 1회 생성(있으면 덮어쓰지 않음).

방법(사전 고정, 2026-10-14):
 1 증상 항목(ITEM) = 의미(허용 concept·금지 concept·기준 표현 anchor) + 표면 재료(앞부분 형태소 + 술어 어간). 정답은 항목 의미에서만 부여.
 2 활용형 실현 = kiwi.join(형태소 결합 — 표면 생성 도구, NLU 규칙 아님)으로 현재·과거(+시점어)·'-고'+이어짐·'-어서'+이어짐·'-는/은데요'·'-네요'·'-거든요'·부정('-지 않아요').
   같은 항목의 활용형 = 형태 변화 묶음(morph_group). 부정형은 assertion ABSENT 정답.
 3 문맥 구조: 주체(가족/본인) · 시점 혼합(과거 A + 현재 B) · 복수 증상('-고' 연결) · 약물·질환·검사 혼합 · 비증상·부위 단독 · SILVER · 미지원 · 복합(가래+기침 등).
 4 분리: DEV / FROZEN 은 증상 표현(항목)·이어짐 문장·시점어·주체어·고정 문장 목록이 모두 다르다. 같은 의미 범주(구토/토혈/오심, 목/인후, 떨림/오한 …)는 양쪽에 있되 표현이 다름.
 5 중복 제거: 기존 노출 자료(pilot 274·STEP29 계약 68·STEP29.1 계약 42·전향 231·STEP23 학습·SILVER442·WEAKNON903·STEP29.2 DEV·HOLDOUT)와 ko_key 일치 문장 제외,
   DEV↔FROZEN 문자열·항목·고정 문장 겹침 0 확인. 새 표현이 기존 자료와 얼마나 다른지(문자 3-gram 최대 Jaccard)를 case 마다 기록.
 사람 검증 Gold 아님(합성). 정답 mention 형식 = STEP29.2 contract_check_v3 와 같음(anchor·concept_any(None = EXISTING 금지 허용)·forbid·assertion_any·
 temporality_any·current_status_any·experiencer_any·optional·safety) + case 필드 category·morph_group·variant·ambiguity(의미 구별 위험 범주).
"""
from __future__ import annotations

import json
import random

import s293_common as S
from extract_symptom_spans import kiwi

SEED = 20261014
PAT, OTH = ["PATIENT"], ["OTHER_PERSON", "MULTIPLE"]
NOW = ["CURRENT", "ONGOING"]
# 항목: id → (split, concept_any, forbid, anchor, 앞 형태소, 술어 어간, ambiguity 범주, optional)
ITEMS = {
    # ---- DEV ----
    "d_vomit": ("DEV", ["vomiting"], ["hematemesis", "nausea"], "토", [("계속", "MAG")], ("토하", "VV"), "VOMIT_FAMILY", False),
    "d_vomit2": ("DEV", ["vomiting"], ["hematemesis", "nausea"], "구토", [("구토", "NNG"), ("를", "JKO")], ("하", "VV"), "VOMIT_FAMILY", False),
    "d_modal": ("DEV", ["nausea", None], ["vomiting", "hematemesis"], "토", [("토하", "VV"), ("을", "ETM"), ("것", "NNB")], ("같", "VA"), "VOMIT_FAMILY", False),
    "d_nausea": ("DEV", ["nausea"], ["vomiting", "heartburn"], "미식", [("속", "NNG"), ("이", "JKS")], ("미식거리", "VV"), "GI_SENSATION", False),
    "d_hemat": ("DEV", ["hematemesis", None], ["nausea", "hemoptysis"], "피", [("피", "NNG"), ("를", "JKO")], ("토하", "VV"), "VOMIT_FAMILY", False),
    "d_throat": ("DEV", ["sore_throat"], [], "목", [("침", "NNG"), ("을", "JKO"), ("삼키", "VV"), ("을", "ETM"), ("때", "NNG"), ("목", "NNG"), ("이", "JKS")], ("아프", "VA"), "NECK_THROAT", False),
    "d_neck": ("DEV", ["pain", None], ["sore_throat"], "뒷목", [("뒷목", "NNG"), ("이", "JKS")], ("뻐근하", "VA"), "NECK_THROAT", False),
    "d_neckplain": ("DEV", ["sore_throat", "pain", None], [], "목", [("목", "NNG"), ("이", "JKS")], ("아프", "VA"), "NECK_THROAT", True),
    "d_heartburn": ("DEV", ["heartburn", "pain"], ["nausea"], "명치", [("명치", "NNG"), ("가", "JKS")], ("쓰리", "VA"), "GI_SENSATION", False),
    "d_chills": ("DEV", ["chills"], [], "으슬", [("몸", "NNG"), ("이", "JKS"), ("으슬으슬", "MAG")], ("떨리", "VV"), "TREMOR_CHILLS", False),
    "d_tremor": ("DEV", [None, "HP:0001337", "HP:0002378"], ["chills"], "손가락", [("손가락", "NNG"), ("이", "JKS"), ("덜덜", "MAG")], ("떨리", "VV"), "TREMOR_CHILLS", True),
    "d_dizzy": ("DEV", ["dizziness", "EV:E_82"], [], "어질", [], ("어질어질하", "VA"), None, False),
    "d_dysp": ("DEV", ["dyspnea", "EV:E_75"], [], "숨", [("숨", "NNG"), ("이", "JKS"), ("턱턱", "MAG")], ("막히", "VV"), None, False),
    "d_fever": ("DEV", ["fever"], [], "열", [("열", "NNG"), ("이", "JKS"), ("펄펄", "MAG")], ("나", "VV"), None, False),
    "d_diarrhea": ("DEV", ["diarrhea"], [], "설사", [("설사", "NNG"), ("를", "JKO"), ("자꾸", "MAG")], ("하", "VV"), None, False),
    "d_sputum": ("DEV", ["cough"], [], "가래", [("가래", "NNG"), ("가", "JKS"), ("자꾸", "MAG")], ("나오", "VV"), None, False),
    "d_fatigue": ("DEV", ["fatigue", "EV:E_175"], [], "기운", [("기운", "NNG"), ("이", "JKS"), ("하나", "NR"), ("도", "JX")], ("없", "VA"), None, False),
    "d_palp": ("DEV", ["palpitations"], ["pain"], "두근", [("심장", "NNG"), ("이", "JKS")], ("두근두근하", "VV"), None, False),
    # ---- FROZEN ----
    "f_vomit": ("FROZEN", ["vomiting"], ["hematemesis", "nausea"], "게워", [("다", "MAG")], ("게워내", "VV"), "VOMIT_FAMILY", False),
    "f_vomit2": ("FROZEN", ["vomiting"], ["hematemesis", "nausea"], "오바이트", [], ("오바이트하", "VV"), "VOMIT_FAMILY", False),
    "f_vomit3": ("FROZEN", ["vomiting"], ["hematemesis", "nausea"], "토", [("또", "MAG")], ("토하", "VV"), "VOMIT_FAMILY", False),
    "f_modal": ("FROZEN", ["nausea", None], ["vomiting", "hematemesis"], "토", [("토하", "VV"), ("을", "ETM"), ("것", "NNB"), ("만", "JX")], ("같", "VA"), "VOMIT_FAMILY", False),
    "f_nausea": ("FROZEN", ["nausea"], ["vomiting", "heartburn"], "느글", [("속", "NNG"), ("이", "JKS")], ("느글거리", "VV"), "GI_SENSATION", False),
    "f_hemat": ("FROZEN", ["hematemesis", None], ["nausea", "hemoptysis"], "피", [("피", "NNG"), ("를", "JKO"), ("왈칵", "MAG")], ("토하", "VV"), "VOMIT_FAMILY", False),
    "f_throat": ("FROZEN", ["sore_throat"], [], "목", [("목", "NNG"), ("안", "NNG"), ("이", "JKS")], ("따끔거리", "VV"), "NECK_THROAT", False),
    "f_neck": ("FROZEN", ["pain", None], ["sore_throat"], "목", [("목", "NNG"), ("뒤", "NNG"), ("가", "JKS")], ("아프", "VA"), "NECK_THROAT", False),
    "f_neck2": ("FROZEN", ["pain", None], ["sore_throat"], "목덜미", [("목덜미", "NNG"), ("가", "JKS")], ("결리", "VV"), "NECK_THROAT", False),
    "f_neckplain": ("FROZEN", ["sore_throat", "pain", None], [], "목", [("목", "NNG"), ("도", "JX")], ("아프", "VA"), "NECK_THROAT", True),
    "f_heartburn": ("FROZEN", ["heartburn", "pain", None], ["nausea"], "화끈", [("속", "NNG"), ("이", "JKS")], ("화끈거리", "VV"), "GI_SENSATION", False),
    "f_chills": ("FROZEN", ["chills"], [], "덜덜", [("춥", "VA"), ("어서", "EC"), ("몸", "NNG"), ("이", "JKS"), ("덜덜", "MAG")], ("떨리", "VV"), "TREMOR_CHILLS", False),
    "f_tremor": ("FROZEN", [None, "HP:0001337", "HP:0002378"], ["chills"], "손", [("손", "NNG"), ("이", "JKS"), ("바들바들", "MAG")], ("떨리", "VV"), "TREMOR_CHILLS", True),
    "f_dizzy": ("FROZEN", ["dizziness", "EV:E_82"], [], "빙빙", [("눈앞", "NNG"), ("이", "JKS"), ("빙빙", "MAG")], ("돌", "VV"), None, False),
    "f_dysp": ("FROZEN", ["dyspnea", "EV:E_75"], [], "숨", [("숨", "NNG"), ("쉬", "VV"), ("기", "ETN"), ("가", "JKS")], ("힘들", "VA"), None, False),
    "f_fever": ("FROZEN", ["fever"], [], "열", [("열", "NNG"), ("이", "JKS")], ("오르", "VV"), None, False),
    "f_diarrhea": ("FROZEN", ["diarrhea"], [], "변", [("물", "NNG"), ("같", "VA"), ("은", "ETM"), ("변", "NNG"), ("을", "JKO")], ("보", "VV"), None, False),
    "f_cough": ("FROZEN", ["cough"], [], "기침", [("밤", "NNG"), ("마다", "JX"), ("기침", "NNG"), ("이", "JKS")], ("심하", "VA"), None, False),
    "f_fatigue": ("FROZEN", ["fatigue", "EV:E_175", "limb_weakness"], [], "기력", [("온몸", "NNG"), ("에", "JKB"), ("기력", "NNG"), ("이", "JKS")], ("없", "VA"), None, False),
    "f_palp": ("FROZEN", ["palpitations"], ["pain"], "벌렁", [("가슴", "NNG"), ("이", "JKS")], ("벌렁벌렁하", "VV"), None, False),
}
CTX = {
    "DEV": {"time": "어제", "go_tail": "병원에 왔어요", "seo_tail": "왔어요", "other": "엄마가", "me": "제가", "now": "지금은",
            "fixed_non": ["혈압약 처방을 받았어요", "날씨가 정말 추워요", "심장 쪽이요", "머리 주위요", "검사 결과 들으러 왔어요", "위염 진단을 받았어요"],
            "mix": [("두통약을 먹었는데 머리가 계속 아파요", "머리", ["pain"]), ("위염이 있는데 명치가 아파요", "명치", ["pain", "heartburn"])],
            "silver": [("코피가 났어요", "코피", "HP:0000421"), ("재채기가 나와요", "재채기", "SCTID:76067001")],
            "unsup": ["눈이 침침해요", "머리카락이 많이 빠져요"],
            "compound": [("가래가 끓는 기침을 해요", [("기침", ["cough"], [])]), ("열이 나면서 기침도 해요", [("열", ["fever"], []), ("기침", ["cough"], [])])]},
    "FROZEN": {"time": "그저께", "go_tail": "회사를 쉬었어요", "seo_tail": "누워 있었어요", "other": "아들이", "me": "저도", "now": "요즘은",
               "fixed_non": ["혈관성 편두통 진단을 받았어요", "감기약을 먹고 있어요", "가슴 부근이요", "왼쪽 팔이요", "위내시경 결과는 정상이래요", "기침약을 처방받았어요",
                             "날씨가 많이 쌀쌀해요"],
               "mix": [("천식 진단을 받았는데 숨이 차요", "숨", ["dyspnea"]), ("진통제를 먹어도 허리가 아파요", "허리", ["pain"]),
                       ("고혈압 약을 먹는데 어지러워요", "어지", ["dizziness", "EV:E_82"])],
               "silver": [("재채기가 계속 나와요", "재채기", "SCTID:76067001"), ("코피가 주르륵 났어요", "코피", "HP:0000421"), ("밤에 잠을 못 자요", "잠", "HP:0100785")],
               "unsup": ["귀에서 삐 소리가 나요", "손톱이 자꾸 갈라져요", "입안이 바싹 말라요"],
               "compound": [("누런 가래가 나오는 기침을 해요", [("기침", ["cough"], [])]), ("피가 섞인 가래가 나와요", [("가래", ["hemoptysis", None], ["hematemesis"])]),
                            ("열이 나면서 오한이 들어요", [("열", ["fever"], []), ("오한", ["chills"], [])])]},
}
END = {"pres": [("어요", "EF")], "past": [("었", "EP"), ("어요", "EF")], "go": [("고", "EC")], "seo": [("어서", "EC")], "nde": [("는데요", "EF")],
       "ne": [("네요", "EF")], "geo": [("거든요", "EF")], "neg": [("지", "EC"), ("않", "VX"), ("어요", "EF")]}


def realize(pre, stem, v):
    e = END[v]
    if v == "nde" and stem[1] == "VA":
        e = [("은데요", "EF")]
    return kiwi().join(list(pre) + [stem] + e)


def gm(it, assertion, temp=None, exp=PAT, safety=None, optional=None):
    sp, cs, fb, anc, pre, stem, amb, opt = ITEMS[it]
    return {"anchor": anc, "concept_any": cs, "forbid": fb, "assertion_any": assertion if isinstance(assertion, list) else [assertion], "temporality_any": temp,
            "current_status_any": None, "experiencer_any": exp, "optional": opt if optional is None else optional, "safety": safety}


def pres_a(it):
    return ["PRESENT", "POSSIBLE"] if it.endswith("modal") else ["PRESENT"]


def build():
    cases = []
    rng = random.Random(SEED)
    for split in ("DEV", "FROZEN"):
        c = CTX[split]
        its = [k for k, v in ITEMS.items() if v[0] == split]
        for it in its:
            sp, cs, fb, anc, pre, stem, amb, opt = ITEMS[it]
            g = f"{split}:{it}"
            forms = {v: realize(pre, stem, v) for v in END}
            add = lambda cat, var, text, ms, **fl: cases.append({"split": split, "category": cat, "item": it, "morph_group": g if cat == "MORPH" else None,  # noqa: E731
                                                                  "variant": var, "ambiguity": amb, "text": text, "mentions": ms, **fl})
            add("MORPH", "pres", forms["pres"], [gm(it, pres_a(it), NOW)])
            add("MORPH", "past", c["time"] + " " + forms["past"], [gm(it, pres_a(it), ["PAST"])], no_model_positive=True)
            add("MORPH", "go", forms["go"] + " " + c["go_tail"], [gm(it, pres_a(it))])
            add("MORPH", "seo", forms["seo"] + " " + c["seo_tail"], [gm(it, pres_a(it))])
            add("MORPH", "nde", forms["nde"], [gm(it, pres_a(it))])
            add("MORPH", "ne", forms["ne"], [gm(it, pres_a(it))])
            add("MORPH", "geo", forms["geo"], [gm(it, pres_a(it))])
            if not it.endswith("modal"):
                add("NEGATION", "neg", forms["neg"], [gm(it, ["ABSENT", "ABSENT_LOW"], None, PAT, "NEG", optional=True)], no_model_positive=True)
            add("EXPERIENCER", "other", c["other"] + " " + forms["pres"], [gm(it, pres_a(it), None, OTH, "OTHER")], no_model_positive=True)
            add("EXPERIENCER", "me", c["me"] + " " + forms["pres"], [gm(it, pres_a(it), None, PAT)])
        # 복수 증상('-고' 연결) · 시점 혼합(과거 A + 현재 B): 같은 split 항목 쌍, ambiguity 없는 지원 항목끼리 + 의미 범주 항목 일부
        pairs = [(a, b) for a in its for b in its if a != b and ITEMS[a][3] != ITEMS[b][3] and not (set(ITEMS[a][1]) & set(ITEMS[b][1]) - {None})
                 and not ITEMS[a][7] and not ITEMS[b][7]]
        rng.shuffle(pairs)
        for a, b in pairs[:24]:
            fa, fb_ = realize(ITEMS[a][4], ITEMS[a][5], "go"), realize(ITEMS[b][4], ITEMS[b][5], "pres")
            cases.append({"split": split, "category": "MULTI", "item": f"{a}+{b}", "morph_group": None, "variant": "go+pres", "ambiguity": None,
                          "text": fa + " " + fb_, "mentions": [gm(a, pres_a(a), None, PAT, "SCOPE"), gm(b, pres_a(b), None, PAT, "SCOPE")]})
        for a, b in pairs[24:40]:
            fa, fb_ = realize(ITEMS[a][4], ITEMS[a][5], "past"), realize(ITEMS[b][4], ITEMS[b][5], "pres")
            cases.append({"split": split, "category": "TEMPORAL", "item": f"{a}+{b}", "morph_group": None, "variant": "past+now", "ambiguity": None,
                          "text": c["time"] + "는 " + fa + " " + c["now"] + " " + fb_, "mentions": [gm(a, pres_a(a), ["PAST"]), gm(b, pres_a(b), NOW)]})
        for t in c["fixed_non"]:
            cases.append({"split": split, "category": "NON_SYMPTOM", "item": t, "morph_group": None, "variant": "fixed", "ambiguity": "NON_SYMPTOM", "text": t,
                          "mentions": [], "no_existing_link": True, "no_symptom_negation": True, "no_model_positive": True})
        for t, anc, cs in c["mix"]:
            cases.append({"split": split, "category": "MIXED_NON_SYMPTOM", "item": t, "morph_group": None, "variant": "fixed", "ambiguity": None, "text": t,
                          "mentions": [{"anchor": anc, "concept_any": cs, "forbid": [], "assertion_any": ["PRESENT"], "temporality_any": None, "current_status_any": None,
                                        "experiencer_any": PAT, "optional": False, "safety": None}]})
        for t, anc, cid in c["silver"]:
            cases.append({"split": split, "category": "SILVER", "item": t, "morph_group": None, "variant": "fixed", "ambiguity": None, "text": t,
                          "mentions": [{"anchor": anc, "concept_any": [None, cid], "forbid": [], "assertion_any": ["PRESENT"], "temporality_any": None,
                                        "current_status_any": None, "experiencer_any": PAT, "optional": True, "safety": None}],
                          "silver_id": cid, "no_existing_link": True, "no_model_positive": True})
        for t in c["unsup"]:
            cases.append({"split": split, "category": "UNSUPPORTED", "item": t, "morph_group": None, "variant": "fixed", "ambiguity": None, "text": t, "mentions": [],
                          "no_existing_link": True, "no_model_positive": True})
        for t, ms in c["compound"]:
            cases.append({"split": split, "category": "COMPOUND", "item": t, "morph_group": None, "variant": "fixed", "ambiguity": None, "text": t,
                          "mentions": [{"anchor": a, "concept_any": cs, "forbid": fb, "assertion_any": ["PRESENT"], "temporality_any": None, "current_status_any": None,
                                        "experiencer_any": PAT, "optional": None in cs, "safety": None} for a, cs, fb in ms]})
    return cases


def exposed():
    keys, texts = set(), []
    def add(t):
        keys.add(S.ko_key(t))
        texts.append(t)
    for r in S.read_csv(S.S21_DIR / "data/pilot_gold.csv"):
        add(r["text_ko"])
    for p in (S.S29_DIR / "data/synthetic_nlu_contracts.json", S.S291_DIR / "data/contract_cases.json", S.S291_DIR / "data/prospective_synthetic_cases.json"):
        for c in json.loads(p.read_text(encoding="utf-8"))["contracts"]:
            add(c["text"])
    for p in (S.S292_DIR / "data/dev_pairs.json", S.S292_DIR / "data/frozen_holdout_pairs.json"):
        for c in json.loads(p.read_text(encoding="utf-8"))["cases"]:
            add(c["text"])
    for r in S.read_csv(S.S23_DIR / "data/expanded_train_expressions.csv"):
        add(r["expression"])
    for r in S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv"):
        add(r["raw_expression"])
    for r in S.read_csv(S.S28_DIR / "outputs/weak_non_check.csv"):
        add(r["text"])
    return keys, texts


def grams(t):
    x = S.nospace(t)
    return {x[i:i + 3] for i in range(max(1, len(x) - 2))}


def main():
    Pd, Pf = S.DATA / "development_cases.json", S.DATA / "frozen_evaluation_cases.json"
    if Pd.exists() or Pf.exists():
        print("exists")
        return
    keys, texts = exposed()
    G = [grams(t) for t in texts]
    idx = {}
    for i, g in enumerate(G):
        for x in g:
            idx.setdefault(x, []).append(i)
    allc = build()
    seen, cases, dropped = set(), [], 0
    for c in allc:
        k = S.ko_key(c["text"])
        if k in keys or k in seen:
            dropped += 1
            continue
        seen.add(k)
        g = grams(c["text"])
        cand = {i for x in g for i in idx.get(x, [])}
        c["max_jaccard_to_exposed"] = round(max((len(g & G[i]) / len(g | G[i]) for i in cand), default=0.0), 3)
        for m in c["mentions"]:
            assert m["anchor"] in c["text"], (c["text"], m["anchor"])
        cases.append(c)
    for i, c in enumerate(cases):
        c["id"] = f"{c['split'][0]}{i + 1:04d}"
    dev = [c for c in cases if c["split"] == "DEV"]
    fro = [c for c in cases if c["split"] == "FROZEN"]
    leak = {"text": len({S.ko_key(c["text"]) for c in dev} & {S.ko_key(c["text"]) for c in fro}),
            "item": len({c["item"] for c in dev} & {c["item"] for c in fro}),
            "context_vocab": sorted(set(map(str, CTX["DEV"].values())) & set(map(str, CTX["FROZEN"].values())))}
    for P, part, name in ((Pd, dev, "DEV"), (Pf, fro, "FROZEN")):
        js = [c["max_jaccard_to_exposed"] for c in part]
        S.dump_json(P, {"method": __doc__, "seed": SEED, "split": name, "n_cases": len(part), "dropped_exposed_or_dup": dropped, "split_leak_check": leak,
                        "by_category": {k: sum(1 for c in part if c["category"] == k) for k in sorted({c["category"] for c in part})},
                        "novelty_max_jaccard_to_exposed": {"mean": round(sum(js) / len(js), 3), "ge_0.8": sum(j >= 0.8 for j in js), "n": len(js)},
                        "human_verified_gold": 0, "cases": part})
    S.wcsv(S.DATA / "evaluation_manifest.csv", [
        {"set": "DEV29_3", "class": "NEW_SYNTHETIC_DEV", "n": len(dev), "sha256": S.sha256(Pd), "use": "검색 규칙 개발·정책 선택"},
        {"set": "FROZEN29_3", "class": "NEW_SYNTHETIC_FROZEN", "n": len(fro), "sha256": S.sha256(Pf), "use": "정책 동결 후 1회 공식 평가"},
        {"set": "STEP29_2_HOLDOUT1052", "class": "EXPOSED_REGRESSION", "n": 1052, "sha256": S.sha256(S.S292_DIR / "data/frozen_holdout_pairs.json"),
         "use": "STEP29.2 와 같은 입력 비교(노출)"},
        {"set": "PILOT274/REGRESSION168", "class": "EXPOSED_REGRESSION", "n": 274, "sha256": S.sha256(S.S21_DIR / "data/pilot_gold.csv"), "use": "노출 회귀"},
        {"set": "SPEC_REGRESSION_CASES", "class": "EXPOSED_REGRESSION", "n": None, "sha256": "data/regression_cases.json", "use": "G3 의미 구별 회귀(지시문 3절 예시)"},
        {"set": "WEAKNON903", "class": "WEAK_EXTERNAL", "n": 903, "sha256": S.sha256(S.S28_DIR / "outputs/weak_non_check.csv"), "use": "약한 음성(자동 연결 수)"}])
    print(S.dumps({"dev": len(dev), "frozen": len(fro), "dropped": dropped, "leak": leak}))


if __name__ == "__main__":
    main()
