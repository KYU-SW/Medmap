"""STEP29 시점·시간 범위. 규칙(사전 고정):
 onset_text  = 절 원문에서 '(어제|오늘|그제|그저께|아까|방금|작년|올해|최근|요즘|지난 주/달/번/밤/해/주말|N 시간/일/주(일)/달/개월/년 전)(부터|에는|에도|에|는|까지)?'
 duration_text = 'N(일|주|달…)째|동안' · 일주일째 · 며칠째 · 잠깐 · 한참   frequency_text = 가끔·자주·때때로·종종·매일·늘·항상·밤마다·아침마다·하루에 N번
 과거 = 선어말어미 EP 었/았/였 또는 과거 시점어(어제·아까·지난·작년·그제·그저께·예전·N 전) · 현재 단서 = 지금·요즘·현재·오늘
 temporality: 해소 단서 적용 → RESOLVED · ('부터'·계속·째) & 과거형 아님 → ONGOING · 과거 → PAST · 용언 있음 → CURRENT · 그 외 UNKNOWN
 해소 단서(증상 없는 뒤 절, 같은 문장) = 괜찮·나았·나아졌·내렸·좋아졌·없어졌·멈췄·멎었·사라졌 → 바로 앞 절 단위들 RESOLVED
 time_scope: 같은 절에 시점어 → CLAUSE · 같은 문장 앞 절에만 시점어 → UNCERTAIN(onset_text 복사 안 함, inherited_onset_candidate 로만) · 없음 → NONE
 기준 시각이 주어지지 않으면 상대 시점 원문만 보존(날짜 계산 안 함)."""
from __future__ import annotations

import re

N = r"(?:[0-9]+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|며칠|몇)"
U = r"(?:시간|일|주일|주|달|개월|년)"
ONSET = re.compile(rf"((?:어제|오늘|그제|그저께|아까|방금|작년|올해|최근|요즘|지난\s?(?:주|달|번|밤|해|주말)|{N}\s?{U}\s?전)(?:부터|에는|에도|에|는|까지)?)")
DURATION = re.compile(rf"({N}\s?{U}?\s?(?:째|동안)|일주일째|며칠째|잠깐|한참)")
FREQ = re.compile(r"(가끔|자주|때때로|종종|매일|늘|항상|밤마다|아침마다|하루에\s?\S+\s?번)")
PAST_WORD = re.compile(rf"(어제|아까|지난|작년|그제|그저께|예전|{N}\s?{U}\s?전)")
CUR_WORD = re.compile(r"(지금|요즘|현재|오늘)")
RESOLVE = re.compile(r"(괜찮|나았|나아졌|내렸|좋아졌|없어졌|멈췄|멎었|사라졌)")
PRED = {"VV", "VA", "VA-I", "VV-I", "VV-R", "VA-R", "VX", "VCP", "VCN"}


def analyze(unit_text: str, toks) -> dict:
    on, du, fr = ONSET.search(unit_text), DURATION.search(unit_text), FREQ.search(unit_text)
    past = any(t.tag == "EP" and t.form in ("었", "았", "였", "었었", "았었") for t in toks) or bool(PAST_WORD.search(unit_text) and not (on and "부터" in on.group(1)))
    cur = bool(CUR_WORD.search(unit_text))
    ongoing = bool((on and "부터" in on.group(1)) or "계속" in unit_text or (du and "째" in du.group(1)))
    has_pred = any(t.tag in PRED or t.tag in ("XSV", "XSA") for t in toks)   # '기침해요' = 기침 + 하(XSV)
    if ongoing and not any(t.tag == "EP" for t in toks):
        tmp = "ONGOING"
    elif past and not cur:
        tmp = "PAST"
    elif has_pred:
        tmp = "CURRENT"
    else:
        tmp = "UNKNOWN"
    return {"temporality": tmp, "onset_text": on.group(1) if on else None, "duration_text": du.group(1) if du else None,
            "frequency_text": fr.group(1) if fr else None, "has_time_expr": bool(on or du or fr or cur)}


def resolution_cue(clause_text: str) -> bool:
    return bool(RESOLVE.search(clause_text))
