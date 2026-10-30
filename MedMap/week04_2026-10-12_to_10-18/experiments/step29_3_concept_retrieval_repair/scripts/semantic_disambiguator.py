"""STEP29.3 §8 의미 구별 계층(문자열 유사도가 아니라 술어·부위·양태·동반 단서로 판단). decide(unit, sentence) → 제안 또는 None.
제안 = {"concept", "status", "basis", "ontology_id"(SILVER 일 때)}. 단서가 부족하면 None(검색기 결과 유지 — 임의 concept 부여 금지).

 VOMIT_FAMILY   단위에 구토 어휘(토하·토했·토해·토할·게워·오바이트·구토(감·기 제외))
   · 혈액 단서('피'(코피 제외)·'혈') + 기침 없음 → hematemesis(VOMIT_WITH_BLOOD)
   · 양태('…ㄹ 것 (만) 같'·'듯'·'뻔'·'토하고 싶') → nausea(MODAL_VOMIT = 실제 구토 아님)
   · 그 외 → vomiting(ACTUAL_VOMIT). '토하다' 만으로 토혈 확정 금지.
 HEMOPTYSIS     기침 또는 가래 + 혈액 단서 → hemoptysis(BLOOD_WITH_COUGH_OR_SPUTUM)
 SPUTUM         가래 + 술어, 혈액 없음 → cough(SPUTUM_PART_OF_COUGH — cough 표준 표현에 가래 포함)
 NECK_THROAT    목·뒷목·목덜미 + 통증·불편 술어(아프·뻐근·결리·쑤시·당기·따끔·칼칼·붓)
   · 문장에 인후 단서(침·삼키·목구멍·편도·인후·목 안·따끔·칼칼·목소리·쉰) → sore_throat
   · 경부 단서(뒷목·목덜미·목 뒤·고개·움직·돌리·뻐근·결리·당기) → pain(EXISTING_COMPOSITE, 부위 경부)
   · 단서 없음('목이 아파요') → None(검색기 결과 유지 — 표준 표현 기준 연결은 그대로, 임의 확정 안 함)
 GI_SENSATION   속·명치·위 + (쓰리·쓰려·화끈·타는·따가) → heartburn(BURNING) · + (울렁·메스꺼·미식·느글·구역(헛 제외)) → nausea(QUEASY)
 TREMOR_CHILLS  떨리·떨려·떨림 + 손·손가락·팔·다리·입술·눈꺼풀, 문장에 추위 단서 없음 → SILVER 떨림(HP:0002378 손 / HP:0001337 그 외, NEW_ONTOLOGY_CANDIDATE)
   · 추위 단서(춥·추워·으슬·오한·한기) 또는 몸·온몸 + 떨림 → chills(COLD_SHIVER)
 DIZZY          어지러·어지럽·어지럼·어질어질·어찔·아찔·핑 돌·빙빙·빙글 → dizziness(DIZZY_LEXEME) — '정신이 오락가락'·'헷갈' 은 제외(혼동 쪽)
 DEFICIT        (팔·다리·손·발 + 힘) + 없·빠지·안 들어가 → limb_weakness · (기운·기력 또는 몸·온몸 + 힘) + 없·빠지 → fatigue(결핍 표현 = 증상 호소)
 NON_SYMPTOM_CONTEXT 환경 주어(날씨·기온·바람·방·에어컨) + 춥·추워·쌀쌀·덥 → 증상 아님 · '…ㄴ지/는지 헷갈리·모르' → 인식 표현(혼동 증상 아님)"""
from __future__ import annotations

import re

VOMIT = re.compile(r"(토하|토했|토해|토할|게워|오바이트|구토(?![감기]))")
BLOOD = re.compile(r"((?<!코)피|혈(?!압))")
MODAL = re.compile(r"(토할\s*것\s*(만\s*)?같|토할\s*듯|토할\s*뻔|토하고\s*싶|게워낼\s*것\s*같)")
NECK = re.compile(r"(뒷목|목덜미|목\s*뒤|목)")
NECK_PRED = re.compile(r"(아프|아파|아팠|아픈|뻐근|결리|결려|결렸|쑤시|쑤셔|당기|당겨|따끔|칼칼|붓|부어|부었)")
THROAT_CUE = re.compile(r"(침|삼키|삼킬|목구멍|편도|인후|목\s*안|따끔|칼칼|목소리|쉰)")
NECKPAIN_CUE = re.compile(r"(뒷목|목덜미|목\s*뒤|고개|움직|돌리|뻐근|결리|결려|결렸|당기|당겨)")
GI_SITE = re.compile(r"(속|명치|위가|위는|위도)")
BURN = re.compile(r"(쓰리|쓰려|쓰렸|쓰린|화끈|타는|따가|따갑)")
QUEASY = re.compile(r"(울렁|메스꺼|메스껍|미식|느글|(?<!헛)구역)")
TREMOR = re.compile(r"(떨리|떨려|떨렸|떨림)")
LIMB = re.compile(r"(손가락|손|팔|다리|입술|눈꺼풀)")
COLD = re.compile(r"(춥|추워|추웠|으슬|오한|한기)")
ENV = re.compile(r"(날씨|기온|바람|방이|방은|에어컨|밖이|밖은)")
ENV_PRED = re.compile(r"(춥|추워|추웠|쌀쌀|덥|더워|서늘)")
DIZZY = re.compile(r"(어지러|어지럽|어지럼|어질어질|어찔|아찔|핑\s*돌|빙빙|빙글)")
DEFICIT_N = re.compile(r"(기운|기력)")
LIMB_POWER = re.compile(r"(팔|다리|팔다리|손|발).{0,4}힘")
DEFICIT_P = re.compile(r"(없|빠지|빠져|빠졌|안\s*들어가|떨어지|떨어졌)")
EPISTEMIC = re.compile(r"(ㄴ지|는지|은지|인지|건지)\s*(잘\s*)?(헷갈|모르)")


def non_symptom_context(unit: str, sentence: str) -> str | None:
    if ENV.search(unit) and ENV_PRED.search(unit):
        return "ENVIRONMENT_STATEMENT"
    if re.search(r"(헷갈|모르)", unit) and EPISTEMIC.search(sentence):
        return "EPISTEMIC_UNCERTAINTY"
    return None


def decide(unit: str, sentence: str) -> dict | None:
    u = unit or ""
    x = re.sub(r"\s+", "", u)
    if VOMIT.search(x):
        if BLOOD.search(x) and "기침" not in x:
            return {"concept": "hematemesis", "status": "EXISTING_CANONICAL", "basis": "VOMIT_WITH_BLOOD"}
        if MODAL.search(u):
            return {"concept": "nausea", "status": "EXISTING_CANONICAL", "basis": "MODAL_VOMIT"}
        return {"concept": "vomiting", "status": "EXISTING_CANONICAL", "basis": "ACTUAL_VOMIT"}
    if ("기침" in x or "가래" in x) and BLOOD.search(x):
        return {"concept": "hemoptysis", "status": "EXISTING_CANONICAL", "basis": "BLOOD_WITH_COUGH_OR_SPUTUM"}
    if "가래" in x and re.search(r"(나오|나와|나왔|끓|생기|생겨|많|있)", x):
        return {"concept": "cough", "status": "EXISTING_CANONICAL", "basis": "SPUTUM_PART_OF_COUGH"}
    if NECK.search(u) and NECK_PRED.search(x):
        if THROAT_CUE.search(sentence or u):
            return {"concept": "sore_throat", "status": "EXISTING_CANONICAL", "basis": "THROAT_CUE"}
        if NECKPAIN_CUE.search(sentence or u):
            return {"concept": "pain", "status": "EXISTING_COMPOSITE", "basis": "NECK_REGION_CUE", "site": "경부"}
        return None
    if GI_SITE.search(u):
        if BURN.search(x):
            return {"concept": "heartburn", "status": "EXISTING_CANONICAL", "basis": "BURNING"}
        if QUEASY.search(x):
            return {"concept": "nausea", "status": "EXISTING_CANONICAL", "basis": "QUEASY"}
    if DIZZY.search(x) and not re.search(r"(정신이\s*오락가락|헷갈)", u):
        return {"concept": "dizziness", "status": "EXISTING_CANONICAL", "basis": "DIZZY_LEXEME"}
    if DEFICIT_P.search(u) and (DEFICIT_N.search(x) or "힘" in x):
        if LIMB_POWER.search(x):
            return {"concept": "limb_weakness", "status": "EXISTING_CANONICAL", "basis": "LIMB_POWER_DEFICIT"}
        if DEFICIT_N.search(x) or re.search(r"(몸|온몸).{0,4}힘", x):
            return {"concept": "fatigue", "status": "EXISTING_CANONICAL", "basis": "ENERGY_DEFICIT"}
    if TREMOR.search(x):
        if COLD.search(re.sub(r"\s+", "", sentence or u)) or re.search(r"(온몸|몸이|몸도|몸은)", u):
            return {"concept": "chills", "status": "EXISTING_CANONICAL", "basis": "COLD_SHIVER"}
        if LIMB.search(x):
            hand = re.search(r"손", x) is not None
            return {"concept": None, "status": "NEW_ONTOLOGY_CANDIDATE", "basis": "LIMB_TREMOR", "ontology_id": "HP:0002378" if hand else "HP:0001337"}
    return None
