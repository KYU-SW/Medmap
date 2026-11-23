"""연구용 모델 점수 생성·변경 추적·반사실 비교·출처 그래프.

원칙
- 점수는 USABLE 근거 하나와 의사가 지정한 진단 가설 한 쌍마다 독립적으로 낸다. 여러 점수를 더하거나 평균내지 않는다.
- HELD/EXCLUDED 근거에는 점수를 만들지 않는다(NOT_ASSESSED + 사유). 평가 보류 ≠ 0점(변화 없음).
- 모델이 없으면 MODEL_UNAVAILABLE. 가짜 점수를 만들지 않는다.
- 설명문은 사건 기록과 사유 코드에서 결정론적으로 만든다(의학적 인과 설명 없음).
"""
from __future__ import annotations

import sys

from .replay import Replay, replay

REASON_KO = {
    "EVIDENCE_ORDERED_ONLY": "검사 요청만 있고 결과가 없어 평가하지 않았습니다.",
    "EVIDENCE_PENDING": "결과 대기 중이어서 평가하지 않았습니다(음성으로 처리하지 않음).",
    "EVIDENCE_NOT_YET_AVAILABLE": "결과 기록은 있으나 조회 시점에 아직 이용 가능하지 않아 평가하지 않았습니다.",
    "TIME_UNKNOWN": "결과의 이용 가능 시각을 알 수 없어 평가를 보류했습니다.",
    "SOURCE_UNKNOWN": "결과 기록의 출처를 확인할 수 없어 평가를 보류했습니다.",
    "CONFLICTING_VERSIONS": "정정 연결 없이 서로 다른 결과 버전이 있어 평가를 보류했습니다.",
    "LINEAGE_INVALID": "정정 계보(이전 버전 연결)에 오류가 있어 평가를 보류했습니다.",
    "PATIENT_ID_CONFLICT": "같은 자료 계보에 서로 다른 환자 ID 가 있어 평가를 보류했습니다.",
    "EVIDENCE_CANCELLED": "검사가 취소되어 근거로 쓰지 않았습니다.",
    "EVIDENCE_INVALID": "결과가 무효 처리되어 근거로 쓰지 않았습니다.",
    "DUPLICATE_EVIDENCE": "이미 반영된 같은 자료의 중복 기록이라 독립 근거로 세지 않았습니다.",
    "PATIENT_MISMATCH": "다른 환자의 기록이 이 환자 수신 묶음에 섞여 있어 제외했습니다.",
    "NOT_LINKED_TO_HYPOTHESIS": "시나리오에서 이 진단 가설과 연결 태그가 지정되지 않은 기록이라 이 가설 평가에 쓰지 않았습니다(엔진의 의학적 판정 아님).",
    "DUPLICATE_OF_SUPERSEDED_VERSION": "다른 계보에서 이미 정정으로 대체된 이전 버전과 같은 자료(정정 전 내용의 재전송)라 쓰지 않았습니다.",
    "NEWER_VERSION_NOT_YET_AVAILABLE": "더 새 버전 기록이 있으나 아직 이용 가능하지 않아 현재 버전을 사용했습니다.",
    "NEWER_VERSION_TIME_UNKNOWN": "이 결과를 대체하는 새 버전 기록이 있으나 이용 가능 시각을 몰라 어느 버전이 유효한지 정할 수 없어 평가를 보류했습니다.",
    "MODEL_UNAVAILABLE": "모델을 사용할 수 없어 점수를 내지 않았습니다.",
}


def assess(rp: Replay, model) -> dict:
    """rp 의 각 근거 → 평가 행. model 은 DModel 또는 None."""
    rows = []
    for it in rp.items:
        row = {"lineage_id": it.lineage_id, "item": it.item, "state": it.state, "reasons": list(it.reasons),
               "used_event_id": it.used.event_id if it.used else None, "used_content": it.used.content if it.used else None, "assessment": None}
        if it.state != "USABLE":
            row["assessment"] = {"status": "NOT_ASSESSED", "reasons": list(it.reasons)}
        elif model is None or getattr(model, "pipe", None) is None:
            row["assessment"] = {"status": "MODEL_UNAVAILABLE", "error": getattr(model, "error", None) if model else "모델 없음"}
        else:
            try:
                out = model.predict(rp.case.hypothesis_text, it.used.content)
                row["assessment"] = {"status": "SCORED", "score": out["score"], "probs": out["probs"], "model_id": model.model_id}
            except Exception as ex:                               # noqa: BLE001
                row["assessment"] = {"status": "MODEL_UNAVAILABLE", "error": f"{type(ex).__name__}: {ex}"[:200]}
        row["explanation"] = explain_item(it, row["assessment"])
        rows.append(row)
    return {"as_of": rp.as_of.isoformat(), "hypothesis": rp.case.hypothesis_text, "rows": rows,
            "n_usable": sum(r["state"] == "USABLE" for r in rows), "n_held": sum(r["state"] == "HELD" for r in rows),
            "n_excluded": sum(r["state"] == "EXCLUDED" for r in rows), "n_scored": sum(r["assessment"]["status"] == "SCORED" for r in rows),
            "aggregation": "없음 — 근거별 독립 연구용 점수(합산·평균·순위화하지 않음)",
            "label": "연구용 모델 점수 — ER-REASON 전문가 점수 예측 모델 출력, 임상 판단 아님. 평가 보류는 0점(변화 없음)과 다름"}


def explain_item(it, a) -> str:
    if it.state == "USABLE":
        u = it.used
        base = f"{u.source} 기록 {u.event_id}({'정정본' if u.status == 'CORRECTED' else '결과'})을 사용했습니다."
        if u.prev_version_id:
            base += f" 이전 버전 {u.prev_version_id} 대신 이 버전을 사용했습니다."
        extra = " ".join(REASON_KO.get(r, r) for r in it.reasons)
        if a and a["status"] == "MODEL_UNAVAILABLE":
            extra += " " + REASON_KO["MODEL_UNAVAILABLE"]
        return (base + " " + extra).strip()
    msg = " ".join(REASON_KO.get(r, r) for r in it.reasons if not r.startswith("LINEAGE:"))
    det = [r.split(":", 1)[1] for r in it.reasons if r.startswith("LINEAGE:")]
    if det:
        msg += f" (계보 오류: {', '.join(det)})"
    if it.duplicate_of:
        msg += f" (먼저 반영된 계보: {it.duplicate_of})"
    return msg


def diff(a: dict, b: dict) -> list:
    """두 평가 결과(assess 출력)의 계보별 차이 + 결정론적 설명."""
    ra, rb = {r["lineage_id"]: r for r in a["rows"]}, {r["lineage_id"]: r for r in b["rows"]}
    out = []
    for lid in sorted(set(ra) | set(rb)):
        x, y = ra.get(lid), rb.get(lid)
        if x is None:
            out.append({"lineage_id": lid, "change": "NEW_RECORD", "before": None, "after": _brief(y),
                        "explanation": f"이전 조회 시점에는 이 계보의 기록이 시스템에 없었습니다. 현재: {y['explanation']}"})
            continue
        if y is None:
            out.append({"lineage_id": lid, "change": "NOT_PRESENT_NOW", "before": _brief(x), "after": None,
                        "explanation": "현재 조회 시점에는 이 계보의 기록이 아직 시스템에 없습니다(과거 시점으로 되돌린 경우)."})
            continue
        bx, by = _brief(x), _brief(y)
        if bx == by:
            continue
        if x["used_event_id"] and y["used_event_id"] and x["used_event_id"] != y["used_event_id"]:
            ch, ex = "VERSION_CHANGED", f"사용 버전이 {x['used_event_id']} → {y['used_event_id']} 로 바뀌었습니다. {y['explanation']}"
        elif x["state"] != "USABLE" and y["state"] == "USABLE":
            ch, ex = "BECAME_USABLE", f"이전 시점: {x['explanation']} 현재 시점: {y['explanation']}"
        elif x["state"] == "USABLE" and y["state"] != "USABLE":
            ch, ex = "NO_LONGER_USABLE", f"이전 시점에는 사용했으나 현재는 사용하지 않습니다. {y['explanation']}"
        else:
            ch, ex = "STATUS_CHANGED", f"이전: {x['explanation']} 현재: {y['explanation']}"
        out.append({"lineage_id": lid, "change": ch, "before": bx, "after": by, "explanation": ex})
    return out


def _brief(r):
    a = r["assessment"]
    return {"state": r["state"], "reasons": r["reasons"], "used_event_id": r["used_event_id"], "assessment_status": a["status"],
            "score": a.get("score")}


def counterfactual(store, case, as_of, model, exclude_event_id: str) -> dict:
    """기술 검사: 기록 하나를 빼고 다시 계산하면 시스템 출력이 어떻게 바뀌는가(임상적 원인 주장 아님)."""
    base = assess(replay(store, case, as_of), model)
    alt = assess(replay(store, case, as_of, exclude_event_ids=[exclude_event_id]), model)
    return {"excluded_event_id": exclude_event_id, "changes": diff(base, alt),
            "note": "이 기록을 제외했을 때 시스템 출력 차이(기술 검사). 이 기록이 임상 판단의 원인이라는 뜻이 아님"}


def provenance_graph(rp: Replay) -> dict:
    """기존 v4 그래프 컨테이너(hybrid4.graphs.Graph, 읽기 전용 재사용)로 출처·정정 그래프 구성 → 노드·간선 목록."""
    from hybrid4.graphs import Graph
    g = Graph(f"provenance_{rp.case.patient_id}@{rp.as_of.isoformat()}")
    g.node(f"PT:{rp.case.patient_id}", "PATIENT")
    g.node(f"HYP:{rp.case.hypothesis_id}", "HYPOTHESIS", text=rp.case.hypothesis_text)
    for it in rp.items:
        ln = f"LIN:{it.lineage_id}"
        g.node(ln, "EVIDENCE_LINEAGE", item=it.item, state=it.state, reasons=",".join(it.reasons))
        if "PATIENT_MISMATCH" in it.reasons:                                  # 다른 환자 기록: 환자 근거가 아니라 수신 묶음에 들어온 기록(1차 심사 반영)
            fid = f"FEED:{it.versions[0][0].feed_id}"
            g.node(fid, "FEED")
            g.edge(fid, "RECEIVED_IN_FEED", ln)
        else:
            g.edge(f"PT:{rp.case.patient_id}", "HAS_EVIDENCE", ln)
        for e, role in it.versions:
            rn = f"REC:{e.event_id}"
            g.node(rn, "RECORD", status=e.status, role=role, source=e.source or "출처 모름")
            g.edge(ln, "HAS_VERSION", rn)
        for e, _ in it.versions:
            if e.prev_version_id and f"REC:{e.prev_version_id}" in g.nodes:
                g.edge(f"REC:{e.event_id}", "CORRECTS", f"REC:{e.prev_version_id}")
        if it.state == "USABLE":
            g.edge(f"REC:{it.used.event_id}", "INPUT_TO_AI_FOR", f"HYP:{rp.case.hypothesis_id}")
    return {"stats": g.stats(), "nodes": list(g.nodes.values()),
            "edges": [e for v in g.out.values() for e in v]}


def kg_status() -> dict:
    """기존 지식그래프 관계 검증 상태(그래프 미검증 관계로 판단을 만들지 않음을 표시)."""
    exp = __import__("pathlib").Path(__file__).resolve().parents[2]
    p = exp / "medmap_graph_shift_pilot" / "src"
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
    try:
        from graph_change import kg_relation_status
        return kg_relation_status()
    except Exception as ex:                                       # noqa: BLE001
        return {"state": "KG_STATUS_UNAVAILABLE", "error": repr(ex)[:200]}
