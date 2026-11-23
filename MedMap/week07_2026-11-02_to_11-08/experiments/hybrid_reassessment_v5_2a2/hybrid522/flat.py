"""평면표 모드 실행: v5-2A.1 평면 비교·meta_log 선언 행·v4 평면 추론기로 같은 세 이력을 만든다(규칙은 comparator 공용)."""
from __future__ import annotations

from . import comparator as CM


def run_flat(pg, as_ofs: list) -> dict:
    return CM.run(pg, as_ofs, "flat")


def run_graph(pg, as_ofs: list) -> dict:
    return CM.run(pg, as_ofs, "graph")
