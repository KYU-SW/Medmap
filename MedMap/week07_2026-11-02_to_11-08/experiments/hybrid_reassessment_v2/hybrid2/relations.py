"""검증 관계 카탈로그 적재·검사·적용. 방향 관계는 인용·출처·적용 조건이 없으면 적재 실패. 수치·확률을 만들지 않는다."""
from __future__ import annotations

import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "knowledge" / "evidence_relations.json"
RELATIONS = {"ASSOCIATED_WITH", "SUPPORTS_HYPOTHESIS", "WEAKENS_HYPOTHESIS", "EVALUATES_HYPOTHESIS", "DIFFERENTIAL_OF", "INSUFFICIENT_EVIDENCE", "UNCERTAIN_RELATIONSHIP"}
DIRECTIONS = {"SUPPORT", "WEAKEN", "NO_CLEAR_EFFECT", "UNCERTAIN", "INSUFFICIENT_EVIDENCE", "NOT_APPLICABLE"}
VERIFIED = {"SOURCE_TEXT_CHECKED", "SOURCE_TEXT_CHECKED_SCOPE_DIFFERENT"}


class CatalogError(ValueError):
    pass


def validate(cat: dict) -> dict:
    src = cat["sources"]
    for r in cat["relations"]:
        for k in ("id", "hypothesis", "finding", "relation", "by_context", "applicability", "evidence", "verification"):
            if not r.get(k) and k not in ("by_context",):
                raise CatalogError(f"{r.get('id')}: {k} 없음")
        if r["relation"] not in RELATIONS:
            raise CatalogError(f"{r['id']}: 관계 값 오류")
        if r["verification"] not in VERIFIED:
            raise CatalogError(f"{r['id']}: 검증 상태 오류")
        for e in r["evidence"]:
            if e["source"] not in src or not e.get("location") or not e.get("quote") or not e.get("summary"):
                raise CatalogError(f"{r['id']}: 근거 필드 없음")
        for c in r["by_context"]:
            if c["direction"] not in DIRECTIONS:
                raise CatalogError(f"{r['id']}: 방향 값 오류")
            if c["direction"] == "SUPPORT" and r["relation"] != "SUPPORTS_HYPOTHESIS":
                raise CatalogError(f"{r['id']}: SUPPORT 는 SUPPORTS_HYPOTHESIS 관계만")
            if c["direction"] == "WEAKEN" and r["relation"] != "WEAKENS_HYPOTHESIS":
                raise CatalogError(f"{r['id']}: WEAKEN 은 WEAKENS_HYPOTHESIS 관계만")
    return cat


def load(path: Path = CATALOG) -> dict:
    return validate(json.loads(Path(path).read_text(encoding="utf-8")))


def lookup(cat: dict, hypothesis: str, finding: str) -> dict | None:
    return next((r for r in cat["relations"] if r["hypothesis"] == hypothesis and r["finding"] == finding), None)


def apply(rel: dict, ctx: dict) -> dict:
    """맥락 규칙 순서대로 적용. 필요한 맥락이 없어 어느 규칙도 확정되지 않으면 INSUFFICIENT_EVIDENCE + 부족 항목."""
    missing = []
    for rule in rel["by_context"]:
        ok, need = True, []
        for k, vals in rule["when"].items():
            v = ctx.get(k)
            if v is None:
                need.append(k)
                ok = False
            elif v not in vals:
                ok = False
                need = []
                break
        if ok:
            return {"direction": rule["direction"], "note": rule.get("note", ""), "missing_context": []}
        missing += need
    miss = sorted(set(missing) & set(rel.get("requires_context", ())) | {k for k in rel.get("requires_context", ()) if ctx.get(k) is None})
    if miss:
        return {"direction": "INSUFFICIENT_EVIDENCE", "note": "적용 조건 확인 불가", "missing_context": miss}
    return {"direction": "NOT_APPLICABLE", "note": "관계의 적용 범위 밖", "missing_context": []}
