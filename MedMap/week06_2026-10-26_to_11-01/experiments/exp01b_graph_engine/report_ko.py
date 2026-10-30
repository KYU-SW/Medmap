"""추론 결과 객체 → 한국어 보고 / JSON. 문장은 결과 필드에서만 만든다(고정 예시 출력 없음)."""
from __future__ import annotations

from graph_engine import Inference, MedGraph, WDAssessment

STATE_KO = {"SUPPORTS": "뒷받침", "CONFLICTS": "명시적 충돌", "NEGATED": "음성(경로 불충족, 질환 유지)",
            "UNMET": "규칙 불충족(질환 유지)", "UNKNOWN": "판단 보류", "DISABLED": "비활성(적용 조건 불충족, 가역)",
            "NO_CONFLICT": "반박 근거 음성"}
CLS_KO = {"WD_PATH_NOT_SATISFIED": "현재 진단으로 가는 경로는 있으나 조건 미충족·미확정",
          "EXPLAINED_BY_OTHER": "현재 진단으로 설명 부족(다른 후보가 설명)",
          "UNEXPLAINED_IN_GRAPH": "그래프 안 어떤 질환으로도 설명되지 않음",
          "NARROWER_CONCEPT_LINKED": "판단 불가 — 질환에는 더 구체적인 하위 개념만 연결(하위 개념 확인 필요)"}


def _lbl(g: MedGraph, n: str) -> str:
    return f"{g.nodes[n].label}[{n}]" if n in g.nodes else n


def _hops(g: MedGraph, hops) -> str:
    return " → ".join(f"{_lbl(g, s)} -{r}-> {_lbl(g, d)}" for s, r, d, _, _ in hops)


def render_ko(g: MedGraph, inf: Inference, wd: WDAssessment | None = None, transitions=None, title="",
              compact: bool = False, rank_key: str = "support") -> str:
    """compact=True: 판단 보류 경로·판단 불가 근거는 개수와 앞 8개만(긴 실제 지식 그래프용)."""
    order = ("임상 소견 근거 묶음 수 → 전체 묶음 수(공출현만 있는 묶음은 둘째 기준)" if rank_key == "graded"
             else "독립 지지 묶음 수")
    L = [f"## {title}" if title else "## 추론 결과", f"- 그래프: {g.name} · 기준 시점 as_of={inf.as_of}",
         f"- 정렬 = {order}. 확률·진단 확정 아님. 모든 질환 노드 유지(제거 없음).", ""]
    L.append("| 순위 | 질환 | 독립 지지 묶음 | 임상 소견 묶음 | 공출현만 묶음 | 지지 근거(묶음:최고 등급) | 충돌 | 음성/불충족 | 판단 보류 | 비활성 | 독립성 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for i, x in enumerate(inf.ranking(rank_key), 1):
        gr = list(x.group_grades) or [""] * len(x.support_groups)
        groups = " / ".join("{" + ", ".join(sorted(s)) + "}" + (f":{c}" if c else "")
                            for s, c in zip(x.support_groups, gr)) or "-"
        L.append(f"| {i} | {_lbl(g, x.disease)} | {x.n_support} | {x.n_clinical} | {x.n_cooccurrence_only} | {groups} | "
                 f"{len(x.conflicts)} | {len(x.negated)} | {len(x.unknown)} | {len(x.disabled)} | {x.independence} |")
    if inf.positive_out_of_graph:
        L.append(f"\n- 그래프에 없는 양성 근거(지식 없음 → 추론 불가): {', '.join(inf.positive_out_of_graph)}")
    L.append("\n### 경로별 근거 추적")
    for x in inf.ranking(rank_key):
        L.append(f"- **{_lbl(g, x.disease)}**")
        hidden = 0
        for p in x.paths:
            if compact and p.state == "UNKNOWN":
                hidden += 1
                continue
            srcs = "; ".join(sorted({h[3] for h in p.hops}))
            ec = getattr(p, "evidence_class", "")
            L.append(f"  - [{STATE_KO.get(p.state, p.state)}]{' [' + ec + ']' if ec else ''} {_hops(g, p.hops)} · 조건: {p.detail} · "
                     f"근거ID: {', '.join(p.evidence_ids) or '-'} · 출처: {srcs}")
        if hidden:
            L.append(f"  - [판단 보류 경로 {hidden}개 생략 — 근거 미기록·미검사·불확실]")
    if transitions:
        L.append("\n### 재계산으로 바뀐 경로")
        for t in transitions:
            L.append(f"- {t.path_id}: {STATE_KO.get(t.before, t.before)} → {STATE_KO.get(t.after, t.after)} ({t.kind})")
    if wd is not None:
        L.append(f"\n### 의사 현재 진단 비교: {_lbl(g, wd.working_dx)} — {wd.status}")
        if wd.note:
            L.append(f"- {wd.note}")
        if wd.status == "ASSESSED":
            from discrimination import wd_categories
            c = wd_categories(wd)
            L.append(f"- 4분류: A 지지 경로 {c['A_support_paths']} · B 다른 질환만 연결(추가 검토 가능, 불일치 확정 아님) {c['B_other_disease_only']} · "
                     f"C 의료 지식 부족(반박 아님) {c['C_knowledge_gap']} · D 검증된 반박 {c['D_verified_conflict']}({c['D_status']}) → "
                     f"재검토 신호 {'있음' if c['review_signal'] else '없음'} / 지식 부족 표시 {'있음' if c['knowledge_gap_flag'] else '없음'}")
            L.append("- 뒷받침 근거: " + ("; ".join(f"{', '.join(_lbl(g, n) for n in p.evidence_nodes)} "
                                                 f"(경로 {p.path_id})" for p in wd.supporting) or "없음"))
            L.append("- 설명 부족 근거: " + ("; ".join(
                f"{_lbl(g, n)} = {CLS_KO[c]}" + (f" → {', '.join(_lbl(g, o) for o in others)}" if others else "")
                for n, c, others, _ in wd.unexplained) or "없음"))
            if wd.conflict_knowledge == "NO_KNOWLEDGE":
                L.append("- 명시적 충돌 근거: 판단 불가(이 그래프에 현재 진단을 반박하는 관계가 없음 → 근거 부족)")
            else:
                L.append("- 명시적 충돌 근거: " + ("; ".join(f"{', '.join(_lbl(g, n) for n in p.evidence_nodes)} "
                                                     f"(출처 {p.hops[-1][3]})" for p in wd.conflicting) or "없음(확인됨)"))
            und = wd.undetermined[:8] if compact else wd.undetermined
            more = f" … 외 {len(wd.undetermined) - len(und)}개" if len(und) < len(wd.undetermined) else ""
            L.append(f"- 아직 확인하지 않아 판단할 수 없는 근거({len(wd.undetermined)}): " + ("; ".join(
                f"{_lbl(g, n)} ({st}, 경로 {pid}" + (f", 확인 가능 검사 {', '.join(_lbl(g, t) for t in tests)}" if tests else "") + ")"
                for n, st, pid, tests in und) or "없음") + more)
            if getattr(wd, "tests_available", ()):
                L.append("- 현재 진단 확인에 쓸 수 있는 검사(지식원 기재, 환자 결과 없음): "
                         + "; ".join(_lbl(g, t) for t, _ in wd.tests_available))
            L.append("- 추가 검토 후보: " + ("; ".join(f"{_lbl(g, d)}: {' / '.join(r)}" for d, r in wd.review_candidates)
                                       or "없음"))
    return "\n".join(L)


def to_json(inf: Inference, wd: WDAssessment | None = None, transitions=None, rank_key: str = "support") -> dict:
    def p(x):
        return {"path_id": x.path_id, "rel": x.rel, "state": x.state, "evidence_nodes": list(x.evidence_nodes),
                "evidence_ids": list(x.evidence_ids), "detail": x.detail, "evidence_class": x.evidence_class,
                "hops": [{"src": s, "rel": r, "dst": d, "source": so, "tier": t} for s, r, d, so, t in x.hops]}
    out = {"graph": inf.graph_name, "as_of": inf.as_of,
           "rank_key": rank_key,
           "ranking": [{"disease": x.disease, "n_support_groups": x.n_support, "n_clinical_groups": x.n_clinical,
                        "n_cooccurrence_only_groups": x.n_cooccurrence_only, "group_grades": list(x.group_grades),
                        "support_groups": [sorted(s) for s in x.support_groups], "independence": x.independence,
                        "paths": [p(y) for y in x.paths]} for x in inf.ranking(rank_key)],
           "positive_out_of_graph": list(inf.positive_out_of_graph)}
    if transitions is not None:
        out["transitions"] = [{"path_id": t.path_id, "before": t.before, "after": t.after, "kind": t.kind}
                              for t in transitions]
    if wd is not None:
        out["working_dx"] = {"dx": wd.working_dx, "status": wd.status, "note": wd.note,
                             "supporting": [p(x) for x in wd.supporting],
                             "unexplained": [{"node": n, "class": c, "explained_by": list(o), "wd_links": list(lk)}
                                             for n, c, o, lk in wd.unexplained],
                             "conflict_knowledge": wd.conflict_knowledge,
                             "conflicting": [p(x) for x in wd.conflicting],
                             "undetermined": [{"node": n, "status": s, "path": pid, "tests": list(t)}
                                              for n, s, pid, t in wd.undetermined],
                             "review_candidates": [{"disease": d, "reasons": list(r)} for d, r in wd.review_candidates]}
    return out
