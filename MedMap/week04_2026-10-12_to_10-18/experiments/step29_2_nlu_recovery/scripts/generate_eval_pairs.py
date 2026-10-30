"""STEP29.2 §9·§10 — 새 합성 평가 세트(의미 구조 먼저 → 문장 생성, NLU 실행 없음). 평가 전 1회 생성(있으면 덮어쓰지 않음).

방법(사전 고정, 2026-10-13):
 1 의미 구조(structure) = 문장 목록 × 각 문장의 슬롯(증상 상태·주체·시점·평가형·해소·비증상). 정답(gold)은 슬롯 의미에서만 부여한다 — NLU 출력·규칙을 쓰지 않는다.
 2 표면 실현(frame) = 문장 연결 방식(문장 나열 / 연결어미 '-고'·'-는데') + 어휘(시점어·주체어·약물·질환·해소 표현·의성어 문장).
   문장 나열형은 같은 의미로 '마침표 있음(P)' / '마침표 없음(N)' 두 버전을 만든다(pair_id 공유). 연결어미형은 한 문장이라 끝 마침표 유무 쌍.
 3 분리: 개발용(DEV)과 최종 평가용(HOLDOUT)은 frame(연결 틀) · 어휘 목록(시점어·주체어·약물·질환·검사·해소 표현·의성어 문장·미지원·SILVER 표현)이 겹치지 않는다.
   증상 조합(struct_key = 구조 + 증상 튜플)은 seed 해시로 한쪽에만 배정. 문자열(ko_key) 중복은 양쪽·기존 노출 자료와 모두 제외.
 4 난이도 변형(HOLDOUT·DEV 각각): 띄어쓰기 제거 · 채움말('음'·'그리고') · 조사 생략 짧은 전사형 · 반복 — 마침표 없음 버전 기준.
 5 metamorphic 묶음: PUNCT(P↔N) · NEG_SCOPE · TEMPORAL · EXPERIENCER · MULTI · MODIFIER · UNSUP — 같은 split 안 case id 로 연결.
 기존 노출 자료(제외 대상): pilot_gold 274 · STEP29 계약 68 · STEP29.1 계약 42 · STEP29.1 전향적 231 · STEP23 학습 표현 · SILVER442 · WEAKNON903.
 사람 검증 Gold 아님(HUMAN_VERIFIED_GOLD = 0). 합성 템플릿 정답.

정답 mention 필드: anchor(원문 부분 문자열) · concept_any(허용 concept, None = EXISTING 자동 연결 금지) · assertion_any · temporality_any(사건 시점) ·
 current_status_any(RESOLVED / IMPROVING / UNSPECIFIED / PERSISTING) · experiencer_any · optional(추출 안 돼도 됨, 추출되면 검사) · safety(NEG / OTHER / SCOPE).
 assertion 'ABSENT_LOW' = ABSENT 이면서 assertion_certainty LOW(확인 필요). case flags: no_symptom_mentions · no_symptom_negation · no_model_positive · no_existing_link.
"""
from __future__ import annotations

import hashlib
import json
import random

import s292_common as S

SEED = 20261013
# ---------------- 증상 어휘(개념 슬롯) — DEV/HOLDOUT 공용(기존 77 concept 의 기본 표현), 표면 틀·문맥 어휘는 분리 ----------------
# key: (concept_any, anchor, pres, go, nde, neg, neg_nde, past, past_nde, past_go, cont, hedge, dneg, bare, site)
L = {
    "cough": (["cough"], "기침", "기침이 나요", "기침이 나고", "기침이 나는데", "기침은 안 나요", "기침은 안 나는데", "기침이 났어요", "기침이 났는데", "기침이 났고",
              "기침이 계속 나요", "기침이 나는 것 같기도 해요", "기침이 안 나는 건 아니에요", "기침 나요", None),
    "fever": (["fever"], "열", "열이 나요", "열이 나고", "열이 나는데", "열은 없어요", "열은 없는데", "열이 났어요", "열이 났는데", "열이 났고",
              "열이 계속 나요", "열이 있는 것 같기도 해요", "열이 없는 건 아니에요", "열 나요", None),
    "dyspnea": (["dyspnea"], "숨", "숨이 차요", "숨이 차고", "숨이 찬데", "숨은 안 차요", "숨은 안 찬데", "숨이 찼어요", "숨이 찼는데", "숨이 찼고",
                "숨이 계속 차요", "숨이 찬 것 같기도 해요", "숨이 안 차는 건 아니에요", "숨 차요", None),
    "head": (["pain"], "머리", "머리가 아파요", "머리가 아프고", "머리가 아픈데", "머리는 안 아파요", "머리는 안 아픈데", "머리가 아팠어요", "머리가 아팠는데",
             "머리가 아팠고", "머리가 계속 아파요", "머리가 아픈 것 같기도 해요", "머리가 안 아픈 건 아니에요", "머리 아파요", "머리"),
    "abd": (["pain"], "배", "배가 아파요", "배가 아프고", "배가 아픈데", "배는 안 아파요", "배는 안 아픈데", "배가 아팠어요", "배가 아팠는데", "배가 아팠고",
            "배가 계속 아파요", "배가 아픈 것 같기도 해요", "배가 안 아픈 건 아니에요", "배 아파요", "배"),
    "throat": (["sore_throat", "pain"], "목", "목이 아파요", "목이 아프고", "목이 아픈데", "목은 안 아파요", "목은 안 아픈데", "목이 아팠어요", "목이 아팠는데",
               "목이 아팠고", "목이 계속 아파요", "목이 아픈 것 같기도 해요", "목이 안 아픈 건 아니에요", "목 아파요", "목"),
    "chest": (["pain"], "가슴", "가슴이 아파요", "가슴이 아프고", "가슴이 아픈데", "가슴은 안 아파요", "가슴은 안 아픈데", "가슴이 아팠어요", "가슴이 아팠는데",
              "가슴이 아팠고", "가슴이 계속 아파요", "가슴이 아픈 것 같기도 해요", "가슴이 안 아픈 건 아니에요", "가슴 아파요", "가슴"),
    "nausea": (["nausea"], "메스", "속이 메스꺼워요", "속이 메스껍고", "속이 메스꺼운데", "속은 안 메스꺼워요", "속은 안 메스꺼운데", "속이 메스꺼웠어요",
               "속이 메스꺼웠는데", "속이 메스꺼웠고", "속이 계속 메스꺼워요", "속이 메스꺼운 것 같기도 해요", "속이 안 메스꺼운 건 아니에요", "속 메스꺼워요", None),
    "diarrhea": (["diarrhea"], "설사", "설사를 해요", "설사를 하고", "설사를 하는데", "설사는 안 해요", "설사는 안 하는데", "설사를 했어요", "설사를 했는데",
                 "설사를 했고", "설사를 계속 해요", "설사를 하는 것 같기도 해요", "설사를 안 하는 건 아니에요", "설사해요", None),
    "dizzy": (["dizziness"], "어지", "어지러워요", "어지럽고", "어지러운데", "어지럽지는 않아요", "어지럽지는 않은데", "어지러웠어요", "어지러웠는데", "어지러웠고",
              "계속 어지러워요", "어지러운 것 같기도 해요", "안 어지러운 건 아니에요", "어지러워요", None),
    "vomit": (["vomiting"], "토", "자꾸 토해요", "자꾸 토하고", "자꾸 토하는데", "토하지는 않아요", "토하지는 않는데", "토했어요", "토했는데", "토했고",
              "계속 토해요", None, "안 토하는 건 아니에요", "토했어요", None),
    "fatigue": (["fatigue", "EV:E_175"], "피곤", "피곤해요", "피곤하고", "피곤한데", "피곤하지는 않아요", "피곤하지는 않은데", "피곤했어요", "피곤했는데", "피곤했고",
                "계속 피곤해요", "피곤한 것 같기도 해요", "안 피곤한 건 아니에요", "피곤해요", None),
    "chills": (["chills"], "오한", "오한이 나요", "오한이 나고", "오한이 나는데", "오한은 없어요", "오한은 없는데", "오한이 났어요", "오한이 났는데", "오한이 났고",
               "오한이 계속 나요", "오한이 있는 것 같기도 해요", "오한이 없는 건 아니에요", "오한 나요", None),
    "palp": (["palpitations"], "두근", "가슴이 두근거려요", "가슴이 두근거리고", "가슴이 두근거리는데", "가슴이 두근거리지는 않아요", "가슴이 두근거리지는 않는데",
             "가슴이 두근거렸어요", "가슴이 두근거렸는데", "가슴이 두근거렸고", "가슴이 계속 두근거려요", "가슴이 두근거리는 것 같기도 해요",
             "가슴이 안 두근거리는 건 아니에요", "가슴 두근거려요", None),
    "swell": (["swelling"], "다리", "다리가 부어요", "다리가 붓고", "다리가 붓는데", "다리는 안 부어요", "다리는 안 붓는데", "다리가 부었어요", "다리가 부었는데",
              "다리가 부었고", "다리가 계속 부어요", "다리가 부은 것 같기도 해요", "다리가 안 붓는 건 아니에요", "다리 부었어요", None),
    "heartburn": (["heartburn", "pain"], "쓰", "속이 쓰려요", "속이 쓰리고", "속이 쓰린데", "속은 안 쓰려요", "속은 안 쓰린데", "속이 쓰렸어요", "속이 쓰렸는데",
                  "속이 쓰렸고", "속이 계속 쓰려요", "속이 쓰린 것 같기도 해요", "속이 안 쓰린 건 아니에요", "속 쓰려요", None),
    "weak": (["limb_weakness"], "힘", "다리에 힘이 없어요", "다리에 힘이 없고", "다리에 힘이 없는데", None, None, "다리에 힘이 없었어요", "다리에 힘이 없었는데",
             "다리에 힘이 없었고", "다리에 계속 힘이 없어요", "다리에 힘이 없는 것 같기도 해요", None, "다리 힘이 없어요", None),
    "appetite": (["decreased_appetite", "EV:E_174"], "입맛", "입맛이 없어요", "입맛이 없고", "입맛이 없는데", None, None, "입맛이 없었어요", "입맛이 없었는데",
                 "입맛이 없었고", "입맛이 계속 없어요", "입맛이 없는 것 같기도 해요", None, "입맛 없어요", None),
}
F = {n: i for i, n in enumerate(("concept", "anchor", "pres", "go", "nde", "neg", "neg_nde", "past", "past_nde", "past_go", "cont", "hedge", "dneg", "bare", "site"))}
CLASH = [{"head", "abd", "throat", "chest", "palp"}, {"nausea", "heartburn"}, {"swell", "weak"}]   # 같은 단어(가슴·속·다리)·같은 concept 동시 사용 금지
SITES = ["head", "abd", "throat", "chest"]

# ---------------- split 별 문맥 어휘(겹치지 않음) ----------------
V = {
    "DEV": {"past_t": ["어제", "아까"], "onset_t": ["어제부터", "사흘 전부터"], "now_t": ["지금은", "오늘은"],
            "other_subj": ["엄마가", "남편이"], "other_topic": ["엄마는", "남편은"], "me_topic": ["저는"], "both": ["저랑 엄마 둘 다"],
            "drug": [("기침약을", "먹었는데", "먹었어요"), ("진통제를", "먹었는데", "먹었어요")], "dis": [("고혈압이", "있는데", "있어요"), ("당뇨가", "있는데", "있어요")],
            "res_mod": ["지금은 괜찮아요"], "res_strong": ["다 나았어요"], "res_pain": ["이제 안 아파요"], "improve": ["많이 좋아졌어요"],
            "nonsym": ["검사 결과는 괜찮아요", "혈압약을 먹고 있어요", "병원에 다녀왔어요"], "nonsym_eval": ["검사 결과는 괜찮아요"],
            "appetite_eval": ["입맛은 괜찮은 편이에요"], "unsure_eval": [("head", "머리는 괜찮은지 잘 모르겠어요")],
            "persist": [("fever", "열이 계속 안 떨어져요", "열")],
            "modifier": [("머리가 지끈지끈 아파요", ["pain"], "머리"), ("박동성 두통이 있어요", ["pain"], "두통"), ("속이 울렁울렁해요", ["nausea"], "울렁"),
                         ("목이 따끔따끔해요", ["sore_throat", "pain"], "목"), ("몸이 으슬으슬 추워요", ["chills"], "으슬"), ("배가 콕콕 쑤셔요", ["pain"], "배")],
            "confusable": [("아까 두 번 토했어요", ["vomiting"], "토", None), ("토할 것만 같아요", ["nausea"], "토", None),
                           ("기침할 때 피가 섞여 나와요", ["hemoptysis"], "피", None), ("코피가 났어요", [None, "HP:0000421"], "코피", ["hemoptysis", "hematemesis"]),
                           ("손가락이 떨려요", [None, "HP:0001337", "HP:0002378"], "떨", ["chills"]), ("으슬으슬 떨려요", ["chills"], "떨", None)],
            "silver": [("재채기가 자꾸 나요", "재채기", "SCTID:76067001"), ("코피가 또 났어요", "코피", "HP:0000421")],
            "unknown": [("발톱이 자꾸 부러져요", "발톱"), ("머리카락이 많이 빠져요", "머리카락"), ("입술이 자주 터져요", "입술")],
            "filler": ["음 ", "그리고 "]},
    "HOLDOUT": {"past_t": ["그저께", "지난주에", "어젯밤에"], "onset_t": ["그저께부터", "며칠 전부터"], "now_t": ["이제는", "요즘은"],
                "other_subj": ["아이가", "아버지가", "동생이"], "other_topic": ["아이는", "아버지는", "동생은"], "me_topic": ["저는", "전"], "both": ["저랑 동생 둘 다"],
                "drug": [("해열제를", "먹었는데", "먹었어요"), ("소화제를", "먹었는데", "먹었어요"), ("감기약을", "먹었는데", "먹었어요")],
                "dis": [("천식이", "있는데", "있어요"), ("위염이", "있는데", "있어요"), ("비염이", "있는데", "있어요")],
                "res_mod": ["오늘은 괜찮아요", "이제는 괜찮아요"], "res_strong": ["지금은 증상이 없어요", "이제 다 나았어요"], "res_pain": ["지금은 안 아파요"],
                "improve": ["좀 나아졌어요", "지금은 조금 나아졌어요"],
                "nonsym": ["피검사 결과는 괜찮대요", "작년에 건강검진을 받았어요", "날씨가 많이 추워요", "엑스레이는 괜찮았어요"],
                "nonsym_eval": ["피검사 결과는 괜찮대요", "엑스레이는 괜찮았어요"],
                "appetite_eval": ["밥맛은 괜찮아요", "식욕은 괜찮아요"], "unsure_eval": [("abd", "배는 괜찮은 건지 모르겠어요"), ("throat", "목은 괜찮은지 헷갈려요")],
                "persist": [("cough", "기침이 안 멈춰요", "기침"), ("diarrhea", "설사가 안 멎어요", "설사")],
                "modifier": [("머리가 욱신욱신 아파요", ["pain"], "머리"), ("회전성 어지럼증이 있어요", ["dizziness"], "어지럼"),
                             ("속이 울렁거리고 메스꺼워요", ["nausea"], "울렁"), ("목이 칼칼하고 아파요", ["sore_throat", "pain"], "목"),
                             ("가슴이 콩닥콩닥 뛰어요", ["palpitations"], "콩닥"), ("눈앞이 핑 돌아요", ["dizziness"], "핑"), ("배가 살살 아파요", ["pain"], "배"),
                             ("몸이 덜덜 떨리고 추워요", ["chills"], "추워")],
                "confusable": [("점심 먹고 다 토했어요", ["vomiting"], "토", None), ("속이 안 좋아서 토할 것만 같아요", ["nausea"], "토", None),
                               ("기침하면 피가 같이 나와요", ["hemoptysis"], "피", ["hematemesis"]), ("코피가 자꾸 나요", [None, "HP:0000421"], "코피", ["hemoptysis", "hematemesis"]),
                               ("피를 토했어요", ["hematemesis"], "피", ["hemoptysis"]), ("손이 계속 떨려요", [None, "HP:0001337", "HP:0002378"], "떨", ["chills"]),
                               ("추워서 온몸이 떨려요", ["chills"], "떨", None)],
                "silver": [("재채기를 계속 해요", "재채기", "SCTID:76067001"), ("코를 심하게 골아요", "코", "HP:0025267"), ("밤에 잠이 안 와요", "잠", "HP:0100785")],
                "unknown": [("손톱 색이 이상하게 변했어요", "손톱"), ("귀가 먹먹해요", "귀"), ("딸꾹질이 안 멈춰요", "딸꾹질"), ("피부가 너무 건조해요", "피부")],
                "filler": ["어 ", "그리고 ", "근데 "]},
}
NOW = ["CURRENT", "ONGOING"]
PAT, OTH = ["PATIENT"], ["OTHER_PERSON", "MULTIPLE"]
NOTRES = ["UNSPECIFIED", "PERSISTING"]
ALL_A = ["PRESENT", "ABSENT", "POSSIBLE", "UNKNOWN", "ABSENT_LOW"]


def g(k, assertion, temp=None, cur=None, exp=PAT, optional=False, safety=None, concept=None, anchor=None):
    return {"anchor": anchor or L[k][F["anchor"]], "concept_any": concept or L[k][F["concept"]], "assertion_any": assertion if isinstance(assertion, list) else [assertion],
            "temporality_any": temp, "current_status_any": cur, "experiencer_any": exp, "optional": optional, "safety": safety}


def f(k, field):
    return L[k][F[field]]


def ok_combo(ks):
    if len(set(ks)) < len(ks):
        return False
    if len({tuple(L[k][0]) for k in ks}) < len(ks) and any(L[a][0] == L[b][0] for a in ks for b in ks if a != b):
        return False
    return not any(len(set(ks) & c) >= 2 for c in CLASH)


def site_word(k):
    return L[k][F["site"]]


def topic(w):
    return w + ("은" if (ord(w[-1]) - 0xAC00) % 28 else "는")


# ---------------- 구조 정의: 각 구조 = (이름, 범주, 문장 생성 함수) ; 함수(ks, v, frame, rng) → (sentences | None, mentions, flags) ----------------
# frame 'SENT' = 문장 나열(P/N 쌍), 'CONN' = 연결어미 한 문장(끝 마침표 쌍). DEV/HOLDOUT 이 쓰는 frame 은 STRUCT_FRAMES 에서 분리.

def s_single(ks, v, fr, r):
    k = ks[0]
    if fr == "PRES":
        return [f(k, "pres")], [g(k, "PRESENT", NOW)], {}
    if fr == "ONSET":
        return [r.choice(v["onset_t"]) + " " + f(k, "pres")], [g(k, "PRESENT", NOW)], {}
    if fr == "PAST":
        return [r.choice(v["past_t"]) + " " + f(k, "past")], [g(k, "PRESENT", ["PAST"], NOTRES)], {"no_model_positive": True}
    if fr == "NEG":
        return [f(k, "neg")], [g(k, "ABSENT", None, None, PAT, False, "NEG")], {"no_model_positive": True}


def s_two(ks, v, fr, r):
    a, b = ks
    ms = [g(a, "PRESENT", NOW, None, PAT, False, "SCOPE"), g(b, "PRESENT", NOW, None, PAT, False, "SCOPE")]
    if fr == "SENT":
        return [f(a, "pres"), f(b, "pres")], ms, {}
    if fr == "CONN_GO":
        return [f(a, "go") + " " + f(b, "pres")], ms, {}
    if fr == "SENT_ONSET":
        return [r.choice(v["onset_t"]) + " " + f(a, "pres"), f(b, "pres")], ms, {}
    if fr == "CONN_NDE":
        return [f(a, "nde") + " " + f(b, "pres")], ms, {}


def s_three(ks, v, fr, r):
    a, b, c = ks
    ms = [g(x, "PRESENT", NOW, None, PAT, False, "SCOPE") for x in ks]
    if fr == "SENT":
        return [f(a, "pres"), f(b, "pres"), f(c, "pres")], ms, {}
    if fr == "CONN_MIX":
        return [f(a, "go") + " " + f(b, "pres"), f(c, "pres")], ms, {}
    if fr == "CONN_GO2":
        return [f(a, "go") + " " + f(b, "go") + " " + f(c, "pres")], ms, {}
    if fr == "SENT_NEG_LAST":
        if f(c, "neg") is None:
            return None
        return [f(a, "pres"), f(b, "pres"), f(c, "neg")], ms[:2] + [g(c, "ABSENT", None, None, PAT, False, "NEG")], {}


def s_negpos(ks, v, fr, r):
    a, b = ks
    if f(a, "neg") is None:
        return None
    ms = [g(a, "ABSENT", None, None, PAT, False, "NEG"), g(b, "PRESENT", NOW, None, PAT, False, "SCOPE")]
    if fr == "SENT":
        return [f(a, "neg"), f(b, "pres")], ms, {}
    if fr == "CONN_NDE":
        return [f(a, "neg_nde") + " " + f(b, "pres")], ms, {}
    if fr == "SENT_POSNEG":
        return [f(b, "pres"), f(a, "neg")], [ms[1], ms[0]], {}
    if fr == "SENT_NEG_NOW":
        return [f(a, "neg"), r.choice(v["now_t"]) + " " + f(b, "pres")], ms, {}


def s_evalpos(ks, v, fr, r):
    a, b = ks   # a = 부위(평가형 부정), b = 다른 증상
    if site_word(a) is None:
        return None
    ev = g(a, ["ABSENT", "ABSENT_LOW", "POSSIBLE"], None, None, PAT, True, None, L[a][0] + [None], site_word(a))
    pos = g(b, "PRESENT", NOW, NOTRES, PAT, False, "SCOPE")
    if fr == "SENT":
        return [topic(site_word(a)) + " 괜찮아요", f(b, "pres")], [ev, pos], {}
    if fr == "CONN_NDE":
        return [topic(site_word(a)) + " 괜찮은데 " + f(b, "pres")], [ev, pos], {}
    if fr == "SENT_POS_FIRST":   # 증상 뒤 다른 부위 정상 — 해소로 연결하면 안 됨
        return [f(b, "pres"), topic(site_word(a)) + " 괜찮아요"], [pos, ev], {}
    if fr == "CONN_GO":
        return [topic(site_word(a)) + " 괜찮고 " + f(b, "pres")], [ev, pos], {}


def s_resolve(ks, v, fr, r):
    k = ks[0]
    past = r.choice(v["past_t"]) + " " + f(k, "past")
    if fr == "MOD":
        return [past, r.choice(v["res_mod"])], [g(k, "PRESENT", ["PAST"], ["RESOLVED"])], {"no_model_positive": True, "resolution_strength": "MODERATE"}
    if fr == "STRONG":
        return [past, r.choice(v["res_strong"])], [g(k, "PRESENT", ["PAST"], ["RESOLVED"])], {"no_model_positive": True, "resolution_strength": "STRONG"}
    if fr == "PAIN":
        if k not in SITES:
            return None
        return [past, r.choice(v["res_pain"])], [g(k, "PRESENT", ["PAST"], ["RESOLVED"])], {"no_model_positive": True}
    if fr == "IMPROVE":
        return [past, r.choice(v["improve"])], [g(k, "PRESENT", ["PAST"], ["IMPROVING"])], {}


def s_resolve_multi(ks, v, fr, r):
    a, b = ks
    t = r.choice(v["past_t"])
    ms = [g(a, "PRESENT", ["PAST"], ["RESOLVED", "UNSPECIFIED"]), g(b, "PRESENT", ["PAST"], ["RESOLVED"])]
    if fr == "SENT":
        return [t + " " + f(a, "past_go") + " " + f(b, "past"), r.choice(v["res_mod"] + v["res_strong"])], ms, {"no_model_positive": True}


def s_pastnow(ks, v, fr, r):
    a, b = ks   # 과거 a + 현재 다른 증상 b(해소 아님 — 시점 대비 통제)
    ms = [g(a, "PRESENT", ["PAST"], NOTRES), g(b, "PRESENT", NOW, NOTRES)]
    t, n = r.choice(v["past_t"]), r.choice(v["now_t"])
    if fr == "SENT":
        return [t + " " + f(a, "past"), n + " " + f(b, "pres")], ms, {}
    if fr == "CONN_NDE":
        return [t + " " + f(a, "past_nde") + " " + n + " " + f(b, "pres")], ms, {}


def s_pastother(ks, v, fr, r):
    a, b = ks   # 과거 a + 다른 부위 정상(평가형) — a 를 해소로 연결하면 안 됨
    if site_word(b) is None:
        return None
    ms = [g(a, "PRESENT", ["PAST"], NOTRES), g(b, ["ABSENT", "ABSENT_LOW", "POSSIBLE"], None, None, PAT, True, None, L[b][0] + [None], site_word(b))]
    if fr == "SENT":
        return [r.choice(v["past_t"]) + " " + f(a, "past"), topic(site_word(b)) + " 괜찮아요"], ms, {}


def s_cue_alone(ks, v, fr, r):
    return [r.choice(v["res_mod"])], [], {"no_symptom_mentions": True, "no_symptom_negation": True}


def s_other(ks, v, fr, r):
    k = ks[0]
    if fr == "SUBJ":
        return [r.choice(v["other_subj"]) + " " + f(k, "pres")], [g(k, "PRESENT", NOW, None, OTH, False, "OTHER")], {"no_model_positive": True}


def s_switch(ks, v, fr, r):
    a, b = ks
    o, me = r.choice(v["other_topic"]), r.choice(v["me_topic"])
    ms = [g(a, "PRESENT", NOW, None, OTH, False, "OTHER"), g(b, "PRESENT", NOW, None, PAT)]
    if fr == "SENT":
        return [o + " " + f(a, "pres"), me + " " + f(b, "pres")], ms, {}
    if fr == "CONN_GO":
        return [o + " " + f(a, "go") + " " + me + " " + f(b, "pres")], ms, {}
    if fr == "SENT_ME_FIRST":
        return [me + " " + f(b, "pres"), o + " " + f(a, "pres")], [ms[1], ms[0]], {}


def s_both(ks, v, fr, r):
    k = ks[0]
    return [r.choice(v["both"]) + " " + f(k, "pres")], [g(k, "PRESENT", NOW, None, ["MULTIPLE", "PATIENT"])], {}


def s_hedge(ks, v, fr, r):
    k = ks[0]
    if fr == "HEDGE":
        if f(k, "hedge") is None:
            return None
        return [f(k, "hedge")], [g(k, ["POSSIBLE"], None, None)], {}
    if fr == "HEDGE_TIME":
        if f(k, "hedge") is None:
            return None
        return [r.choice(v["onset_t"]) + " " + f(k, "hedge")], [g(k, ["POSSIBLE"], None, None)], {}
    if fr == "DNEG":
        if f(k, "dneg") is None:
            return None
        return [f(k, "dneg")], [g(k, ["PRESENT", "POSSIBLE"], None, None)], {}


def s_unsure_eval(ks, v, fr, r):
    k, txt = r.choice(v["unsure_eval"])
    return [txt], [g(k, ["POSSIBLE", "UNKNOWN", "ABSENT_LOW"], None, None, PAT, True, None, L[k][0] + [None], site_word(k))], {}


def s_appetite_eval(ks, v, fr, r):
    txt = r.choice(v["appetite_eval"])
    anc = "맛" if "맛" in txt else "식욕"
    return [txt], [g("appetite", ["ABSENT", "ABSENT_LOW", "POSSIBLE"], None, None, PAT, True, None, ["decreased_appetite", "EV:E_174", None], anc)], {"no_model_positive": True}


def s_nonsym(ks, v, fr, r):
    return [r.choice(v["nonsym"])], [], {"no_symptom_mentions": True, "no_symptom_negation": True}


def s_nonsym_sym(ks, v, fr, r):
    k = ks[0]
    return [r.choice(v["nonsym_eval"]), f(k, "cont")], [g(k, "PRESENT", NOW, NOTRES, PAT, False, "SCOPE")], {}


def s_drug(ks, v, fr, r):
    k = ks[0]
    d = r.choice(v["drug"])
    if fr == "CONN":
        return [d[0] + " " + d[1] + " " + f(k, "cont")], [g(k, "PRESENT", NOW, NOTRES)], {}
    if fr == "SENT":
        return [d[0] + " " + d[2], f(k, "cont")], [g(k, "PRESENT", NOW, NOTRES)], {}


def s_disease(ks, v, fr, r):
    k = ks[0]
    d = r.choice(v["dis"])
    if fr == "CONN":
        return [d[0] + " " + d[1] + " " + f(k, "pres")], [g(k, "PRESENT", NOW)], {}
    if fr == "SENT":
        return [d[0] + " " + d[2], f(k, "pres")], [g(k, "PRESENT", NOW)], {}


def s_persist(ks, v, fr, r):
    k, txt, anc = r.choice(v["persist"])
    return [txt], [g(k, "PRESENT", None, ["PERSISTING", "UNSPECIFIED"], PAT, False, None, None, anc)], {}


def s_modifier(ks, v, fr, r):
    txt, cs, anc = r.choice(v["modifier"])
    return [txt], [{"anchor": anc, "concept_any": cs, "assertion_any": ["PRESENT"], "temporality_any": None, "current_status_any": None, "experiencer_any": PAT,
                    "optional": False, "safety": None}], {"modifier": True}


def s_confusable(ks, v, fr, r):
    txt, cs, anc, forbid = r.choice(v["confusable"])
    m = {"anchor": anc, "concept_any": cs, "assertion_any": ["PRESENT"], "temporality_any": None, "current_status_any": None, "experiencer_any": PAT,
         "optional": None in cs, "safety": None, "forbid": forbid or []}
    return [txt], [m], {"no_existing_link": cs == [None] or cs[0] is None}


def s_silver(ks, v, fr, r):
    txt, anc, cid = r.choice(v["silver"])
    return [txt], [{"anchor": anc, "concept_any": [None, cid], "assertion_any": ["PRESENT"], "temporality_any": None, "current_status_any": None, "experiencer_any": PAT,
                    "optional": True, "safety": None}], {"no_existing_link": True, "no_model_positive": True}


def s_unknown(ks, v, fr, r):
    txt, anc = r.choice(v["unknown"])
    return [txt], [], {"no_existing_link": True, "no_model_positive": True}


def s_repeat(ks, v, fr, r):
    k = ks[0]
    if fr == "ONSET":
        return [r.choice(v["onset_t"]) + " " + f(k, "pres"), f(k, "cont")], [g(k, "PRESENT", NOW)], {"repetition": True}
    return [f(k, "pres"), f(k, "cont")], [g(k, "PRESENT", NOW)], {"repetition": True}


def s_bare(ks, v, fr, r):
    a, b = ks
    return [f(a, "bare"), f(b, "bare")], [g(a, "PRESENT", None), g(b, "PRESENT", None)], {"short_asr": True}


STRUCTS = {  # 이름: (범주, 함수, 증상 수, DEV frames, HOLDOUT frames)
    "S1_SINGLE": ("SINGLE", s_single, 1, ["PRES", "PAST"], ["ONSET", "NEG"]),
    "S2_TWO": ("MULTI2", s_two, 2, ["SENT", "CONN_GO"], ["SENT_ONSET", "CONN_NDE"]),
    "S3_THREE": ("MULTI3", s_three, 3, ["SENT", "CONN_MIX"], ["CONN_GO2", "SENT_NEG_LAST"]),
    "S4_NEGPOS": ("NEG_SCOPE", s_negpos, 2, ["SENT", "CONN_NDE"], ["SENT_POSNEG", "SENT_NEG_NOW"]),
    "S6_EVALPOS": ("EVAL_NEG", s_evalpos, 2, ["SENT", "CONN_NDE"], ["SENT_POS_FIRST", "CONN_GO"]),
    "S7_RESOLVE": ("RESOLUTION", s_resolve, 1, ["MOD", "STRONG", "PAIN", "IMPROVE"], ["MOD", "STRONG", "PAIN", "IMPROVE"]),
    "S7M_RESOLVE_MULTI": ("RESOLUTION", s_resolve_multi, 2, [], ["SENT"]),
    "S9_PASTNOW": ("TEMPORAL_CONTROL", s_pastnow, 2, ["SENT"], ["SENT", "CONN_NDE"]),
    "S9B_PASTOTHER": ("TEMPORAL_CONTROL", s_pastother, 2, ["SENT"], ["SENT"]),
    "S7C_CUE_ALONE": ("RESOLUTION", s_cue_alone, 0, ["X"], ["X"]),
    "S12_OTHER": ("EXPERIENCER", s_other, 1, ["SUBJ"], ["SUBJ"]),
    "S12_SWITCH": ("EXPERIENCER", s_switch, 2, ["SENT", "CONN_GO"], ["SENT_ME_FIRST", "SENT"]),
    "S14_BOTH": ("EXPERIENCER", s_both, 1, ["X"], ["X"]),
    "S18_HEDGE": ("HEDGE_DNEG", s_hedge, 1, ["HEDGE"], ["HEDGE_TIME", "DNEG"]),
    "S15_UNSURE_EVAL": ("EVAL_NEG", s_unsure_eval, 0, ["X"], ["X"]),
    "S17_APPETITE_EVAL": ("EVAL_NEG", s_appetite_eval, 0, ["X"], ["X"]),
    "S16_NONSYM": ("NON_SYMPTOM", s_nonsym, 0, ["X"], ["X"]),
    "S16B_NONSYM_SYM": ("NON_SYMPTOM", s_nonsym_sym, 1, ["SENT"], ["SENT"]),
    "S20_DRUG": ("NON_SYMPTOM", s_drug, 1, ["CONN"], ["SENT", "CONN"]),
    "S21_DISEASE": ("NON_SYMPTOM", s_disease, 1, ["CONN"], ["SENT", "CONN"]),
    "S11_PERSIST": ("TEMPORAL_CONTROL", s_persist, 0, ["X"], ["X"]),
    "S22_MODIFIER": ("MODIFIER", s_modifier, 0, ["X"], ["X"]),
    "S26_CONFUSABLE": ("CONFUSABLE", s_confusable, 0, ["X"], ["X"]),
    "S23_SILVER": ("SILVER", s_silver, 0, ["X"], ["X"]),
    "S24_UNKNOWN": ("UNKNOWN", s_unknown, 0, ["X"], ["X"]),
    "S25_REPEAT": ("REPETITION", s_repeat, 1, ["X"], ["ONSET"]),
    "S27_BARE": ("SHORT_ASR", s_bare, 2, [], ["SENT"]),
}
QUOTA = {"DEV": {1: 6, 2: 6, 3: 4, 0: 4}, "HOLDOUT": {1: 10, 2: 12, 3: 8, 0: 8}}   # frame 당 증상 조합 표본 수(증상 수별)
QUOTA_X = {"DEV": {"S22_MODIFIER": 6, "S26_CONFUSABLE": 6, "S23_SILVER": 2, "S24_UNKNOWN": 3, "S16_NONSYM": 3},
           "HOLDOUT": {"S22_MODIFIER": 8, "S26_CONFUSABLE": 7, "S23_SILVER": 3, "S24_UNKNOWN": 4, "S16_NONSYM": 4, "S7_RESOLVE": 14}}


def assign(struct, ks) -> str:
    h = int(hashlib.sha256(f"{SEED}|{struct}|{'+'.join(ks)}".encode()).hexdigest(), 16)
    return "DEV" if h % 3 == 0 else "HOLDOUT"


def join(sents, punct):
    text, spans = "", []
    for i, s in enumerate(sents):
        if i:
            text += ". " if punct == "P" else " "
        spans.append([len(text), len(text) + len(s)])
        text += s
    if punct == "P":
        text += "."
    return text, spans


def combos(n, r):
    keys = sorted(L)
    if n == 0:
        return [()]
    out = []
    if n == 1:
        out = [(k,) for k in keys]
    elif n == 2:
        out = [(a, b) for a in keys for b in keys if ok_combo([a, b])]
    else:
        out = [(a, b, c) for a in keys for b in keys for c in keys if ok_combo([a, b, c])]
    r.shuffle(out)
    return out


def exposed_keys():
    seen = set()
    for r in S.read_csv(S.S21_DIR / "data/pilot_gold.csv"):
        seen.add(S.ko_key(r["text_ko"]))
    for p in (S.S29_DIR / "data/synthetic_nlu_contracts.json", S.S291_DIR / "data/contract_cases.json", S.S291_DIR / "data/prospective_synthetic_cases.json"):
        for c in json.loads(p.read_text(encoding="utf-8"))["contracts"]:
            seen.add(S.ko_key(c["text"]))
    for r in S.read_csv(S.S23_DIR / "data/expanded_train_expressions.csv"):
        seen.add(S.ko_key(r["expression"]))
    for r in S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv"):
        seen.add(S.ko_key(r["raw_expression"]))
    for r in S.read_csv(S.S28_DIR / "outputs/weak_non_check.csv"):
        seen.add(S.ko_key(r["text"]))
    return seen


def build():
    seen = exposed_keys()
    cases, dropped = [], {"exposed_duplicate": 0, "internal_duplicate": 0, "none_frame": 0}
    used = set()
    for split in ("DEV", "HOLDOUT"):
        v = V[split]
        rng = random.Random(f"{SEED}-{split}")
        for sname, (cat, fn, n, dev_fr, hold_fr) in STRUCTS.items():
            frames = dev_fr if split == "DEV" else hold_fr
            for fr in dict.fromkeys(frames):
                q = QUOTA_X[split].get(sname, QUOTA[split][n] if n else 1)
                cs = [c for c in combos(n, rng) if n == 0 or assign(sname, c) == split]
                k = 0
                for ks in cs:
                    if k >= q:
                        break
                    if sname in ("S22_MODIFIER", "S26_CONFUSABLE", "S23_SILVER", "S24_UNKNOWN", "S16_NONSYM", "S7C_CUE_ALONE", "S15_UNSURE_EVAL",
                                 "S17_APPETITE_EVAL", "S11_PERSIST"):
                        pool = {"S22_MODIFIER": v["modifier"], "S26_CONFUSABLE": v["confusable"], "S23_SILVER": v["silver"], "S24_UNKNOWN": v["unknown"],
                                "S16_NONSYM": v["nonsym"], "S7C_CUE_ALONE": v["res_mod"] + v["res_strong"], "S15_UNSURE_EVAL": v["unsure_eval"],
                                "S17_APPETITE_EVAL": v["appetite_eval"], "S11_PERSIST": v["persist"]}[sname]
                        items = list(range(len(pool)))
                        for i in items:
                            r2 = random.Random(f"{SEED}-{split}-{sname}-{i}")
                            r2.choice = lambda seq, i=i: seq[i % len(seq)]   # 항목 i 를 결정적으로 고름
                            res = fn((), v, fr, r2)
                            if res is None:
                                continue
                            emit(cases, split, sname, cat, fr, (f"ITEM{i}",), res, seen, used, dropped)
                        break
                    r2 = random.Random(f"{SEED}-{split}-{sname}-{fr}-{'+'.join(ks)}")
                    res = fn(list(ks), v, fr, r2)
                    if res is None:
                        dropped["none_frame"] += 1
                        continue
                    if emit(cases, split, sname, cat, fr, ks, res, seen, used, dropped):
                        k += 1
    return cases, dropped


def emit(cases, split, sname, cat, fr, ks, res, seen, used, dropped) -> bool:
    sents, ms, flags = res
    if any(x is None or "None" in x for x in sents):   # 그 증상에 해당 활용형 없음(예 '힘이 없어요' 부정형) → 생성 안 함
        dropped["none_frame"] += 1
        return False
    pid = f"{split[0]}-{sname}-{fr}-{'+'.join(ks)}"
    variants = [("P", "BASE"), ("N", "BASE")]
    texts = []
    for punct, var in variants:
        t, sp = join(sents, punct)
        texts.append((punct, var, t, sp))
    if len(sents) >= 2 or sname in ("S2_TWO", "S3_THREE", "S4_NEGPOS"):
        # 난이도 변형(마침표 없음 기준): 채움말 · 띄어쓰기 제거(문장마다 첫 공백)
        fill = V[split]["filler"]
        h = int(hashlib.sha256(pid.encode()).hexdigest(), 16)
        fl = fill[h % len(fill)]
        fs = [fl + sents[0]] + sents[1:] if fl.strip() != "그리고" else [sents[0]] + [fl + s for s in sents[1:]]
        t, sp = join(fs, "N")
        if t not in {x[2] for x in texts}:
            texts.append(("N", "FILLER", t, sp))
        if h % 2 == 0:
            ns = [s.replace(" ", "", 1) if " " in s else s for s in sents]
            t, sp = join(ns, "N")
            if t not in {x[2] for x in texts}:
                texts.append(("N", "SPACING", t, sp))
    keys = [S.ko_key(t) for *_, t, _ in texts]
    if any(k in seen for k in keys):
        dropped["exposed_duplicate"] += 1
        return False
    if any(k in used for k in keys):
        dropped["internal_duplicate"] += 1
        return False
    used.update(keys)
    for punct, var, t, sp in texts:
        for m in ms:
            assert m["anchor"] in t, (t, m["anchor"])
        cases.append({"split": split, "structure": sname, "category": cat, "frame": f"{sname}:{fr}", "struct_key": f"{sname}|{'+'.join(ks)}", "pair_id": pid,
                      "punct": punct, "variant": var, "text": t, "gold_sentences": sp, "n_gold_sentences": len(sp), "mentions": ms, **flags})
    return True


def metamorphic(cases):
    """같은 split 안 관계(구조 정의에서 결정, NLU 미사용). PUNCT 는 pair_id 로 별도 계산."""
    by = {}
    for c in cases:
        if c["variant"] == "BASE":
            by.setdefault((c["split"], c["structure"], c["struct_key"].split("|")[1], c["punct"]), []).append(c)
    rel = []
    for c in cases:
        if c["variant"] != "BASE" or c["punct"] != "N":
            continue
        ks = c["struct_key"].split("|")[1].split("+")
        sp = c["split"]
        if c["structure"] == "S4_NEGPOS" and len(ks) == 2:   # 부정 추가 → 다른 증상 불변: base = S2(a,b) 의 b
            for b2 in by.get((sp, "S2_TWO", f"{ks[0]}+{ks[1]}", "N"), [])[:1]:
                rel.append({"type": "NEG_SCOPE", "base": b2["id"], "variant": c["id"], "anchor": L[ks[1]][F["anchor"]]})
        if c["structure"] == "S7_RESOLVE":   # 해소 추가 → 과거 사건 보존(PRESENT·PAST)
            rel.append({"type": "TEMPORAL", "variant": c["id"], "anchor": c["mentions"][0]["anchor"]})
        if c["structure"] in ("S12_OTHER", "S12_SWITCH"):
            rel.append({"type": "EXPERIENCER", "variant": c["id"]})
        if c["structure"] in ("S2_TWO", "S3_THREE"):
            rel.append({"type": "MULTI", "variant": c["id"], "anchors": [m["anchor"] for m in c["mentions"]]})
        if c["structure"] == "S22_MODIFIER":
            rel.append({"type": "MODIFIER", "variant": c["id"]})
        if c["structure"] in ("S24_UNKNOWN", "S23_SILVER"):
            rel.append({"type": "UNSUP", "variant": c["id"]})
    return rel


def main():
    Pd, Ph = S.DATA / "dev_pairs.json", S.DATA / "frozen_holdout_pairs.json"
    if Pd.exists() or Ph.exists():
        print("exists", S.sha256(Pd)[:16] if Pd.exists() else "-", S.sha256(Ph)[:16] if Ph.exists() else "-")
        return
    cases, dropped = build()
    for i, c in enumerate(cases):
        c["id"] = f"{c['split'][0]}{i + 1:04d}"
    rel = metamorphic(cases)
    dev = [c for c in cases if c["split"] == "DEV"]
    hold = [c for c in cases if c["split"] == "HOLDOUT"]
    # 분리 검사: 문자열·struct_key·frame·문맥 어휘
    forms = sorted({x for k in L for x in L[k][2:14] if x}, key=len, reverse=True)

    def tmpl(t):
        for x in forms:
            t = t.replace(x, "<S>")
        return t
    tp = {tmpl(c["text"]) for c in dev if c["punct"] == "P"}
    th = {tmpl(c["text"]) for c in hold if c["punct"] == "P"}
    leak = {"template(증상 표현 → <S> 치환 후 동일)": sorted(tp & th), "text": len({S.ko_key(c["text"]) for c in dev} & {S.ko_key(c["text"]) for c in hold}),
            "struct_key": len({c["struct_key"] for c in dev if not c["struct_key"].split("|")[1].startswith("ITEM")} & {c["struct_key"] for c in hold}),
            "frame_name_shared(문맥 어휘는 split 별로 다름)": sorted({c["frame"] for c in dev} & {c["frame"] for c in hold}),
            "context_vocab": sorted(set(json.dumps(x, ensure_ascii=False) for k in V["DEV"] for x in V["DEV"][k] if k not in ("me_topic", "filler"))
                                    & set(json.dumps(x, ensure_ascii=False) for k in V["HOLDOUT"] for x in V["HOLDOUT"][k] if k not in ("me_topic", "filler")))}
    meta = {"method": __doc__, "seed": SEED, "dropped": dropped, "split_leak_check": leak, "human_verified_gold": 0,
            "label": "SYNTHETIC_TEMPLATE(의미 구조 → 문장, 정답 = 슬롯 의미). 사람 검증 Gold 아님"}
    for P, part, name in ((Pd, dev, "DEV"), (Ph, hold, "HOLDOUT")):
        S.dump_json(P, {**meta, "split": name, "n_cases": len(part), "n_pairs": len({c["pair_id"] for c in part}),
                        "by_category": {k: sum(1 for c in part if c["category"] == k) for k in sorted({c["category"] for c in part})},
                        "metamorphic": [x for x in rel if x["variant"][0] == name[0]], "cases": part})
    S.wcsv(S.DATA / "evaluation_manifest.csv", [
        {"set": "DEV_PAIRS", "class": "NEW_SYNTHETIC_DEV", "n": len(dev), "sha256": S.sha256(Pd), "use": "규칙 개발·정책 선택(B0–B3)"},
        {"set": "HOLDOUT_PAIRS", "class": "NEW_SYNTHETIC_HOLDOUT", "n": len(hold), "sha256": S.sha256(Ph), "use": "정책 동결 후 1회 공식 평가(선택에 사용 금지)"},
        {"set": "PILOT274", "class": "EXPOSED_REGRESSION", "n": 274, "sha256": S.sha256(S.S21_DIR / "data/pilot_gold.csv"), "use": "노출 회귀(STEP29 비교 기준 수치)"},
        {"set": "STEP29_CONTRACTS68", "class": "EXPOSED_REGRESSION", "n": 68, "sha256": S.sha256(S.S29_DIR / "data/synthetic_nlu_contracts.json"), "use": "노출 회귀"},
        {"set": "STEP29_1_CONTRACTS42", "class": "EXPOSED_REGRESSION", "n": 42, "sha256": S.sha256(S.S291_DIR / "data/contract_cases.json"), "use": "노출 회귀"},
        {"set": "STEP29_1_PROSPECTIVE231", "class": "EXPOSED_REGRESSION", "n": 231, "sha256": S.sha256(S.S291_DIR / "data/prospective_synthetic_cases.json"),
         "use": "노출 회귀(STEP29.1 결과 본 자료)"},
        {"set": "SILVER442", "class": "WEAK_EXTERNAL", "n": 442, "sha256": S.sha256(S.S28_DIR / "data/external_silver_expansion.csv"), "use": "약한 양성"},
        {"set": "WEAKNON903", "class": "WEAK_EXTERNAL", "n": 903, "sha256": S.sha256(S.S28_DIR / "outputs/weak_non_check.csv"), "use": "약한 음성"}])
    print(S.dumps({"dev": len(dev), "holdout": len(hold), "dropped": dropped, "leak": leak, "meta_rel": len(rel)}))


if __name__ == "__main__":
    main()
