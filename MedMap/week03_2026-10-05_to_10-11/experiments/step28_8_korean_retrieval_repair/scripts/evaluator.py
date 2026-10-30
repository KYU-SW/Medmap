"""STEP28.8 의미 구별 검사기 v3(EVALUATOR_VERSION). 정책 평가 전에 validate_evaluator.py 로 정답 세트 대조 → SHA 고정.

출발점 = STEP28.7 탐색 v2(STEP28.6 원형 + 명사 '떨림'). v3 변경(정책 평가 전, 정답 대조로 결정):
 - 구토 단서에 '토해'·'오바이트' 추가, 단 양태 표현('…할 것 같다'·'…듯') 이 있으면 구토 규칙 적용 안 함('토할 것 같아요' = 오심, gold)
 - 양태에 '…고 싶다' 포함(STEP23 '토하고 싶은 느낌이 듭니다' = nausea)
 - '구토감'·'구토기' 는 구토 단서가 아님(STEP23 학습 '구토감' = nausea)
 - '헛구역' 은 오심 단서가 아님(REGRESSION168 '헛구역질만 계속 나요' gold = vomiting)
규칙(입력 원문 + 결과 concept 집합 → 위반 목록):
 EPISTAXIS_AS_HEMOPTYSIS/HEMATEMESIS : '코피' 인데 hemoptysis·hematemesis
 VOMITING_AS_NAUSEA                  : 구토 단서(양태 없음)인데 nausea 만(vomiting 없음)
 NAUSEA_AS_VOMITING                  : 메스꺼·메스껍·오심·구역(헛구역 제외)인데 vomiting 만(nausea 없음)
 TREMOR_AS_CHILLS                    : 명사 '떨림' 이 있고 오한·춥·추워·으슬 문맥 없이 chills
 HYPERTENSION_AS_SYMPTOM             : '고혈압' 인데 증상 concept
 ANTITUSSIVE_AS_COUGH                : 억제제·기침약·진해제 인데 cough
"""
from __future__ import annotations

import re
from pathlib import Path

EVALUATOR_VERSION = "v3"
MODAL = re.compile(r"(것\s*같|듯|할\s*것|싶)")
VOMIT = re.compile(r"(구토(?![감기])|토하|토했|토해|오바이트)")
NAUSEA = re.compile(r"(메스꺼|메스껍|오심|(?<!헛)구역)")


def violations(text: str, concepts) -> list[str]:
    raw = text or ""
    x = re.sub(r"\s+", "", raw)
    cs = {c for c in concepts if c}
    v = []
    if "코피" in x and {"hemoptysis", "hematemesis"} & cs:
        v.append("EPISTAXIS_AS_HEMOPTYSIS/HEMATEMESIS")
    if VOMIT.search(x) and not MODAL.search(raw) and "nausea" in cs and "vomiting" not in cs:
        v.append("VOMITING_AS_NAUSEA")
    if NAUSEA.search(x) and "vomiting" in cs and "nausea" not in cs:
        v.append("NAUSEA_AS_VOMITING")
    if "떨림" in x and not re.search(r"(오한|춥|추워|으슬)", x) and "chills" in cs:
        v.append("TREMOR_AS_CHILLS")
    if "고혈압" in x and cs:
        v.append("HYPERTENSION_AS_SYMPTOM")
    if re.search(r"(억제제|기침약|진해제)", x) and "cough" in cs:
        v.append("ANTITUSSIVE_AS_COUGH")
    return v


def evaluator_sha() -> str:
    import hashlib
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
