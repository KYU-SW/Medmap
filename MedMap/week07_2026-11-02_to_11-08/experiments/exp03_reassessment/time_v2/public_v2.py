"""EXP-03-TIME v2 공개 출력 규칙(PROTOCOL_TIME_v2.md §9): 1–9 → '<10', 보완 마스킹, 마스킹 칸이 들어간 비율 = '계산 불가'.

보완 마스킹: 합이 공개되는 묶음(group) 안에 마스킹 칸이 정확히 1개면, 그 묶음에서 가장 작은 비마스킹 양수 칸도 가린다(MASKED_COMPLEMENT).
묶음이 바뀌지 않을 때까지 반복(교차표는 행·열 묶음을 함께 넣음).
묶음 종류: (1) 합 항등식(합이 공개되는 칸들) (2) 정의상 같은 양 — 반드시 2칸 사슬로 넣는다(3칸 이상 한 묶음이면 2칸에서 보완이 멈춰 남은 칸이 값을 드러냄).
"""
from __future__ import annotations

SMALL = 10
COMPLEMENT = "MASKED_COMPLEMENT"
NA = "계산 불가"


def small(n: int) -> bool:
    return 0 < int(n) < SMALL


def suppress(cells: dict, groups: list) -> dict:
    """cells: 키 → 정확 정수. groups: [키 목록] (각 묶음의 합이 다른 곳에 공개됨). 반환 키 → 공개값."""
    masked = {k for k, v in cells.items() if small(v)}
    comp = set()
    changed = True
    while changed:
        changed = False
        for g in groups:
            g = [k for k in g if k in cells]
            m = [k for k in g if k in masked or k in comp]
            if len(m) == 1:
                cand = sorted((cells[k], str(k)) for k in g if k not in masked and k not in comp and cells[k] > 0)
                if cand:
                    k = next(k for k in g if str(k) == cand[0][1])
                    comp.add(k)
                    changed = True
    return {k: (f"<{SMALL}" if k in masked else COMPLEMENT if k in comp else int(v)) for k, v in cells.items()}


def is_masked(v) -> bool:
    return isinstance(v, str)


def ratio(num_pub, den_pub, num: int, den: int):
    """공개 분자·분모 중 하나라도 마스킹이면 계산 불가. 분모 0 도 계산 불가."""
    if is_masked(num_pub) or is_masked(den_pub) or den == 0:
        return NA
    return round(num / den, 4)


def cell(n: int):
    return f"<{SMALL}" if small(n) else int(n)
