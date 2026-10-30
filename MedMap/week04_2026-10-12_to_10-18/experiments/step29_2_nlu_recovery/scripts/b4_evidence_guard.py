"""STEP29.2 §7 B4 가드 재설계(STEP27 B4·STEP28.8 P5·STEP29.1 mention_context_validator 원본 무수정 — 호출만).
B4 단독(ko_tier MODEL_B4) 자동 연결을 '모델만 근거인가'로 막지 않고, 원문 증상 구문의 근거를 함께 본다. 특정 문장·정답 목록 하드코딩 없음.

정책(같은 입력·같은 파이프라인 v3 위에서 가드만 다름):
 공통(B0–B3): STEP29.1 EVIDENCE_IDEOPHONE_MISSING 은 근거 용어의 반복형 시간·정도 부사(점점·가끔가끔 등)를 의성·의태어로 세지 않게 보정
   ('다리가 점점 붓고 있어요' 근거 때문에 '다리가 부어요' 가 막히던 문제). 그 외 STEP29.1 가드(PAIN_PREDICATE_MISMATCH·LEXICAL_OVERLAP_ZERO) 그대로.
 B0 = 공통 + MODEL_ONLY_NO_CUE 없음
 B1 = 공통 + STEP29.1 MODEL_ONLY_NO_CUE 그대로(엄격)
 B2 = B0 + 증상 근거 선택 가드: B4 단독 연결은 아래를 모두 만족할 때만 자동 수락, 아니면 UNCERTAIN(원 concept 은 guard_blocked_concept 에 보존)
      e1 술어: 단위에 내용 용언(VV·VA·XSV·XSA)이 있음(증상 서술 형태 — 명사 조각만이면 불충분)
      e2 비증상 문맥 없음: 단위 명사 중 약물·검사·치료·질환(STEP27 NON_TYPE) 없음 → 있으면 B4_NON_SYMPTOM_CONTEXT
      e3 논항: 논항 명사(조사가 붙거나 끝에 오는 명사 — 술어 어간 '시작하·혼절하'·비유 '물처럼' 제외)가 모두 신체 부위·신체 기능/분비물·증상 명사·
         시점·사람·위치(안쪽·전)·정도어 중 하나이거나, 반복형 의성·의태어가 있음(세상이 빙글빙글) — 그 밖의 대상 명사(화장실·물·날씨 등)가 논항이면 근거 부족
      e4 모델 일치: STEP27 라우터 특징을 단위 문장으로 다시 계산 — 선형·KoELECTRA top1 일치 AND KoELECTRA 확신도 ≥ 0.95 AND 비증상 확률 < 0.5
      e1–e4 중 하나라도 실패 → B4_EVIDENCE_INSUFFICIENT(실패 항목은 b4_guard_detail — 사유 문자열은 평가 코드의 고정 이름과 같게)
 B3 = B2 + 의미 충돌 보류: 단위(또는 문장)의 어휘 단서가 B4 concept 과 혼동 쌍으로 충돌하면 B4_SEMANTIC_CONFLICT 로 보류
      어지럼 단서(어지·어질·아찔·핑 돌·빙글·빙빙·휘청) ↔ confusion·loc · 오심 단서(메스꺼·울렁·미식·느글·구역) ↔ vomiting(구토 단서 없음) ·
      구토 단서(토하·토했·게워·구토, 양태 없음) ↔ nausea · 사지 떨림(떨리/떨려 + 손·팔·다리, 추위 단서 없음) ↔ chills · 코피 ↔ hemoptysis·hematemesis ·
      목 부위(목구멍·편도·인후·목이/목) 가 문장에 있고 단위에 다른 부위 없음 ↔ pain(sore_throat 와 충돌)
모든 정책: 원문·원 concept·근거(b4_evidence) 보존, 막히면 requires_confirmation True·모델 입력 불가."""
from __future__ import annotations

import re

import s292_common as S
import mention_context_validator as MCV
from evaluative_negation_scope import FUNC_N, body
from extract_symptom_spans import kiwi
from semantic_conflict_guard import EV_RE, REDUP, ideophones

POLICIES = ("V3_B0", "V3_B1", "V3_B2", "V3_B3")
TIME_N = {"어제", "오늘", "지금", "이제", "그제", "그저께", "아까", "아침", "저녁", "밤", "새벽", "요즘", "주", "주째", "일", "번", "때", "동안", "계속", "며칠", "한번", "처음"}
PERSON_N = {"저", "제", "나", "애", "아이", "엄마", "아빠", "남편", "아내", "동생", "아버지", "어머니", "할머니", "할아버지", "아들", "딸", "언니", "형", "누나", "오빠",
            "동료", "친구", "사람", "가족", "식구"}
RELATIONAL = {"안쪽", "바깥쪽", "위쪽", "아래쪽", "위", "아래", "앞", "뒤", "옆", "전", "후", "쪽", "끝", "가운데", "사이", "양쪽", "왼쪽", "오른쪽"}
DEGREE = {"조금", "약간", "많이", "좀", "계속", "자꾸", "한번", "번"}
EXTRA_BODY = {"팔다리", "종아리", "온몸", "세상", "눈앞", "위산", "목구멍", "편도", "체온", "변", "물집"}
DIZZY = re.compile(r"(어지|어질|아찔|핑\s*돌|빙글|빙빙|휘청)")
NAUSEA = re.compile(r"(메스꺼|메스껍|울렁|미식|느글|(?<!헛)구역)")
VOMIT = re.compile(r"(토하|토했|토해|게워|구토(?![감기])|오바이트)")
MODAL = re.compile(r"(것\s*만?\s*같|듯|할\s*것|싶)")
COLD = re.compile(r"(오한|춥|추워|으슬|한기)")
LIMB = re.compile(r"(손|팔|다리|입술|눈꺼풀)")
THROAT = re.compile(r"(목구멍|편도|인후|목이|목\s)")
NON_IDEO = {"점점", "자꾸자꾸", "가끔가끔", "조금조금", "계속계속", "하나하나", "차츰차츰", "더더", "종종", "번번", "때때", "곳곳", "다다"}   # 반복형 시간·정도 부사(의성·의태어 아님)
_FEAT: dict[str, dict] = {}
USE_CACHE = True   # 지연 측정 시 False


def router_features(text: str) -> dict:
    if not USE_CACHE or text not in _FEAT:
        from p5_normalizer_adapter import engine
        f = engine().R.router.features(text)
        _FEAT[text] = {k: f[k] for k in ("koe_top1", "koe_conf", "lin_top1", "lin_margin", "agree", "p_non", "train_sim")}
    return _FEAT[text]


def evidence(m: dict) -> dict:
    unit = m.get("unit_text") or m["raw_span"]
    toks = kiwi().tokenize(unit)
    nouns = [t.form for t in toks if t.tag.startswith("NN") and t.tag != "NNB"]
    pred = any(t.tag.startswith(("VV", "VA", "XSV", "XSA")) for t in toks)
    non = [n for n in nouns if S.S28.non_type(n) in ("drug", "test", "treatment", "disease")]

    def ok_noun(n):
        if n in body() or n in FUNC_N or n in EXTRA_BODY or n in TIME_N or n in PERSON_N or n in RELATIONAL or n in DEGREE or S.S28.symptom_cue(n):
            return True
        return len(n) >= 2 and n[-1] in "이가은는을를" and ok_noun(n[:-1])   # kiwi 가 1음절 명사+조사를 한 명사로 묶는 경우('변이')
    # 논항 명사 = 조사·끝으로 이어지는 명사. 바로 뒤가 용언·파생 접미(시작하·혼절하·미식거리)면 술어 어간, '처럼·같이·만큼' 이면 비유 — 논항 아님
    args = []
    for i, t in enumerate(toks):
        if not (t.tag.startswith("NN") and t.tag != "NNB"):
            continue
        nx = toks[i + 1] if i + 1 < len(toks) else None
        if nx is not None and (nx.tag.startswith(("XSV", "XSA", "VV")) or nx.form in ("처럼", "같이", "만큼")):
            continue
        args.append(t.form)
    foreign = [n for n in args if not ok_noun(n) and not re.fullmatch(r"\d+", n)]
    ide = sorted(ideophones(unit))
    f = router_features(unit)
    model_ok = bool(f["agree"]) and f["koe_conf"] >= 0.95 and f["p_non"] < 0.5
    return {"predicate": pred, "non_symptom_nouns": non, "foreign_nouns": foreign, "ideophones": ide, "argument_ok": not foreign or bool(ide),
            "model_ok": model_ok, "router": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in f.items()}}


def conflict(m: dict) -> str | None:
    c = m.get("canonical_id")
    unit = m.get("unit_text") or m["raw_span"]
    x = re.sub(r"\s+", "", unit)
    sent = m.get("source_sentence") or ""
    if c in ("confusion", "loc") and DIZZY.search(unit):
        return "DIZZINESS_CUE_vs_" + c
    if c == "vomiting" and NAUSEA.search(x) and not VOMIT.search(x):
        return "NAUSEA_CUE_vs_vomiting"
    if c == "nausea" and VOMIT.search(x) and not MODAL.search(unit):
        return "VOMIT_CUE_vs_nausea"
    if c == "chills" and re.search(r"(떨리|떨려)", x) and LIMB.search(x) and not COLD.search(sent):
        return "LIMB_TREMOR_vs_chills"
    if c in ("hemoptysis", "hematemesis") and "코피" in x:
        return "EPISTAXIS_vs_" + c
    if c == "pain" and THROAT.search(sent + " ") and not any(n in body() and n not in ("목", "목구멍", "편도") for n in
                                                              [t.form for t in kiwi().tokenize(unit) if t.tag.startswith("NN")]):
        return "THROAT_SITE_vs_pain"
    return None


def _block(m: dict, reasons: list[str], ev: dict | None = None) -> dict:
    out = {**m, "status": "UNCERTAIN", "guard_blocked_concept": m.get("guard_blocked_concept") or m["canonical_id"], "canonical_id": None, "display": [],
           "requires_confirmation": True, "usable_by_disease_model": False, "model_supported": False,
           "guard_reasons": list(m.get("guard_reasons") or []) + reasons}
    if ev is not None:
        out["b4_evidence"] = ev
    return out


def ideophone_missing(m: dict) -> bool:
    """STEP29.1 EVIDENCE_IDEOPHONE_MISSING 과 같은 판정이되, 근거 용어의 반복형 시간·정도 부사(점점 등)는 의성·의태어로 세지 않는다."""
    unit = m.get("unit_text") or m["raw_span"]
    terms = [mm.group(3) for e in m.get("ko_evidence") or [] for mm in [EV_RE.match(e)] if mm]
    if not terms:
        return False
    ide = [{x.group(1) for x in REDUP.finditer(t) if x.group(0) not in NON_IDEO} for t in terms]
    return all(ide) and not any(any(stem in unit for stem in st) for st in ide)


def apply(m: dict, policy: str) -> dict:
    g = MCV.apply(m)
    added = [r for r in (g.get("guard_reasons") or []) if r not in (m.get("guard_reasons") or [])]
    if "EVIDENCE_IDEOPHONE_MISSING" in added and not ideophone_missing(m):   # v3 공통 보정(B0–B3): '점점' 등 부사 오인 제거
        added = [r for r in added if r != "EVIDENCE_IDEOPHONE_MISSING"]
        g = _block(m, added) if added else m
    if policy == "V3_B1":
        return g
    other = [r for r in added if r != "MODEL_ONLY_NO_CUE"]
    if other:
        return _block(m, other)
    if policy == "V3_B0":
        return m
    if m.get("status") not in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE") or m.get("ko_tier") != "MODEL_B4":
        return m
    ev = evidence(m)
    if ev["non_symptom_nouns"]:
        return _block(m, ["B4_NON_SYMPTOM_CONTEXT"], ev)
    fail = [k for k in ("predicate", "argument_ok", "model_ok") if not ev[k]]
    if fail:
        return {**_block(m, ["B4_EVIDENCE_INSUFFICIENT"], ev), "b4_guard_detail": "/".join(fail)}
    if policy == "V3_B3":
        cf = conflict(m)
        if cf:
            return {**_block(m, ["B4_SEMANTIC_CONFLICT"], ev), "b4_guard_detail": cf}
    return {**m, "b4_evidence": ev}
