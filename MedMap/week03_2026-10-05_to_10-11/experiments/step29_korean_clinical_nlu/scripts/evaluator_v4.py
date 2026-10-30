"""STEP29 의미 구별 검사기 v4(STEP28.8 evaluator.py v3 의 별도 복사본 — v3 파일은 그대로). 정책 평가 전 validate_evaluator_v4.py 로 정답 대조 후 SHA 고정.

v3 규칙 전부 + v4 추가(STEP28.8 에서 확인된 빈틈 — 노출 사례 기반):
 MODAL_VOMIT_AS_VOMITING     : 구토 단서(+'토할') + 양태(것 같·듯·할 것·싶)인데 vomiting 만(nausea 없음) — '토할 것 같아요' 는 오심 쪽
 LIMB_TREMOR_AS_CHILLS       : 떨리/떨려/떨림 + 손·팔·다리·입술·눈꺼풀(턱 제외 — STEP23 '턱이 달달달 떨려요' = chills), 추위 문맥(오한·춥·추워·으슬·한기) 없이 chills
 BODY_PART_PHRASE_AS_SYMPTOM : 입력 전체가 '<명사> 부분/쪽/부위/근처/주위' 뿐인데 증상 concept
일반화 성능 주장 안 함(규칙이 알려진 사례에서 나옴).
"""
from __future__ import annotations

import re
from pathlib import Path

import evaluator as V3

EVALUATOR_VERSION = "v4"
COLD = re.compile(r"(오한|춥|추워|으슬|한기)")


def violations(text: str, concepts) -> list[str]:
    v = list(V3.violations(text, concepts))
    raw = text or ""
    x = re.sub(r"\s+", "", raw)
    cs = {c for c in concepts if c}
    if re.search(r"(토할|토하|토해|구토(?![감기])|오바이트)", x) and V3.MODAL.search(raw) and "vomiting" in cs and "nausea" not in cs:
        v.append("MODAL_VOMIT_AS_VOMITING")
    if re.search(r"(떨리|떨려|떨림)", x) and re.search(r"(손|팔|다리|입술|눈꺼풀)", x) and not COLD.search(x) and "chills" in cs:
        v.append("LIMB_TREMOR_AS_CHILLS")
    if re.fullmatch(r"\s*[가-힣]+\s*(부분|쪽|부위|근처|주위)\s*[.?!]?\s*", raw) and cs:
        v.append("BODY_PART_PHRASE_AS_SYMPTOM")
    return v


def evaluator_sha() -> str:
    import hashlib
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
