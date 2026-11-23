"""시간 정책: 이용 가능 시각 기준 공개, 정정, 진단 상태 이력, 검사 상태. 미래 정보를 과거 판단에 쓰지 않는다."""
from __future__ import annotations

from .schema import DiagnosisAssertion, EvidenceItem, TestEvent, TestStatus


def visible_evidence(items, as_of: float) -> list:
    """as_of 까지 이용 가능한 증거. available_at 없음·시각 역전은 제외. 이용 가능한 정정이 있으면 원본은 그때부터 무효."""
    usable = [e for e in items if e.available_at is not None and e.available_at <= as_of
              and not (e.observed_at is not None and e.available_at < e.observed_at)]
    corrected = {e.supersedes for e in usable if e.supersedes}
    return sorted((e for e in usable if e.evidence_id not in corrected), key=lambda e: (e.available_at, e.evidence_id))


def diagnosis_state(assertions, as_of: float) -> list:
    """as_of 시점에 유효한 진단 진술. 이전 진술은 지우지 않고 대체 관계로 숨긴다. 시각 없는 진술은 제외."""
    known = [a for a in assertions if a.asserted_at is not None and a.asserted_at <= as_of]
    replaced = {a.supersedes for a in known if a.supersedes}
    return sorted((a for a in known if a.assertion_id not in replaced), key=lambda a: (a.asserted_at, a.assertion_id))


_EVENTS = {"ORDER", "COLLECT", "RESULT", "REVIEW", "CANCEL", "CORRECT"}


def test_status(events, test_id: str, as_of: float) -> TestStatus:
    """검사 상태. 기록이 전혀 없으면 UNKNOWN(시행 안 함이 아님). NOT_ORDERED 는 '주문 목록 전체를 확인했다'는 근거가 있을 때만 호출자가 지정."""
    ev = [e for e in events if e.test_id == test_id]
    if not ev:
        return TestStatus.UNKNOWN
    if any(e.event not in _EVENTS for e in ev):
        return TestStatus.UNKNOWN
    timed = sorted((e for e in ev if e.at is not None and e.at <= as_of), key=lambda e: e.at)
    if not timed:
        return TestStatus.UNKNOWN if any(e.at is None for e in ev) else TestStatus.NOT_ORDERED
    state = TestStatus.UNKNOWN
    for e in timed:
        if e.event == "ORDER":
            state = TestStatus.ORDERED
        elif e.event == "COLLECT":
            state = TestStatus.PENDING
        elif e.event in ("RESULT", "CORRECT"):
            state = TestStatus.RESULT_AVAILABLE            # 정정 결과는 다시 확인이 필요
        elif e.event == "REVIEW":
            if state in (TestStatus.RESULT_AVAILABLE, TestStatus.REVIEWED):
                state = TestStatus.REVIEWED
        elif e.event == "CANCEL":
            state = TestStatus.CANCELLED
    return state


def is_duplicate_candidate(events, test_id: str, as_of: float) -> bool:
    """이미 주문·대기·결과·확인 상태면 중복 후보. 의학적 재검사 필요성은 판단하지 않음."""
    return test_status(events, test_id, as_of) in (TestStatus.ORDERED, TestStatus.PENDING, TestStatus.RESULT_AVAILABLE, TestStatus.REVIEWED)


def leakage_violations(inp) -> list:
    """입력 자체의 미래 정보 검사: 평가 증거·이전 증거가 as_of 이후이면 위반."""
    if inp.as_of is None:
        return []
    bad = []
    for e in (inp.evidence, *inp.prior_evidence):
        if e.available_at is None or e.available_at > inp.as_of:
            bad.append(e.evidence_id)
    return bad
