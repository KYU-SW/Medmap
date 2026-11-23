"""평면표: 같은 메타데이터 선언(meta_log 행)과 같은 기록 목록을 행으로 읽는다. 그룹화 규칙은 comparator 공용."""
from __future__ import annotations

from . import comparator as CM


def declarations_flat(pg) -> tuple:
    known = set(pg.docs) | {o.obs_id for o in pg.obs if o.source_type == "STRUCTURED_LAB"}
    return [dict(r) for r in pg.meta_log], known


def compare521_flat(pg, as_of: float) -> dict:
    return CM.compare521(pg, as_of, "flat")
