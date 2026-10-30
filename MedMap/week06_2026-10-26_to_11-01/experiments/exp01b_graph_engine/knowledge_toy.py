"""구현 검증용 가상 관계(TOY 등급). 실제 의학 지식이 아니다 — 모든 이름에 '가상' 표기, 출처 = 'TOY'.

이 그래프가 시험하는 구조: 다중 경로(같은 질환 노드 공유), AND/OR 규칙, 적용 조건(GATES),
범주값·수치 임계치 조건, 반박(ARGUES_AGAINST), 위험인자, 검사 → 소견(YIELDS), 알려진 근거 의존(DEPENDS_ON).
"""
from __future__ import annotations

from graph_engine import MedGraph

TOY = "TOY: 구현 시험용 가상 관계(의학 지식 아님)"


def build_toy_graph() -> MedGraph:
    g = MedGraph("TOY_v1")
    for d, ko in [("TA", "가상질환A"), ("TB", "가상질환B"), ("TC", "가상질환C"), ("TD", "가상질환D")]:
        g.add_node(d, "DISEASE", ko, "TOY", TOY)
    for s, ko in [("s1", "가상증상1(첫 증상)"), ("s2", "가상증상2"), ("s3", "가상증상3(범주: 부위 L/R)"),
                  ("s4", "가상증상4"), ("s5", "가상증상5(s1 에 의존)"), ("s6", "가상증상6"), ("s7", "가상증상7")]:
        g.add_node(s, "SYMPTOM", ko, "TOY", TOY)
    g.add_node("f1", "FINDING", "가상소견1(수치, u/L)", "TOY", TOY)
    g.add_node("f2", "FINDING", "가상소견2", "TOY", TOY)
    g.add_node("T1", "TEST", "가상검사1", "TOY", TOY)
    g.add_node("T2", "TEST", "가상검사2", "TOY", TOY)
    g.add_node("g1", "HISTORY", "가상병력1(규칙 R1 적용 조건)", "TOY", TOY)
    g.add_node("r1", "RISK_FACTOR", "가상위험인자1", "TOY", TOY)
    g.add_node("R1", "RULE", "가상규칙R1: s2 AND f1≥500 (적용 조건 g1)", "TOY", TOY, op="AND", gate_op="AND")
    g.add_node("R2", "RULE", "가상규칙R2: s6 OR f2", "TOY", TOY, op="OR")

    # 첫 증상 s1 → 세 질환(같은 질환 노드에 여러 경로로 도달하는 출발점)
    for d in ("TA", "TB", "TC"):
        g.add_edge("s1", "SUGGESTS", d, "TOY", TOY)
    g.add_edge("s2", "SUGGESTS", "TB", "TOY", TOY)
    g.add_edge("s3", "SUGGESTS", "TA", "TOY", TOY, values=("L",))
    g.add_edge("s3", "SUGGESTS", "TC", "TOY", TOY, values=("R",))
    g.add_edge("s4", "ARGUES_AGAINST", "TA", "TOY", TOY)
    g.add_edge("s4", "SUGGESTS", "TC", "TOY", TOY)
    g.add_edge("s5", "SUGGESTS", "TC", "TOY", TOY)
    g.add_edge("s5", "DEPENDS_ON", "s1", "TOY", TOY)
    g.add_edge("s7", "SUGGESTS", "TD", "TOY", TOY)
    g.add_edge("r1", "RISK_FACTOR_FOR", "TD", "TOY", TOY)
    g.add_edge("T1", "YIELDS", "f1", "TOY", TOY)
    g.add_edge("T2", "YIELDS", "f2", "TOY", TOY)
    # R1(AND): s2 양성 그리고 f1 ≥ 500 u/L, 적용 조건 g1 양성 → TB
    g.add_edge("s2", "PART_OF", "R1", "TOY", TOY)
    g.add_edge("f1", "PART_OF", "R1", "TOY", TOY, threshold=(">=", 500.0, "u/L"))
    g.add_edge("g1", "GATES", "R1", "TOY", TOY)
    g.add_edge("R1", "SUGGESTS", "TB", "TOY", TOY)
    # R2(OR): s6 또는 f2 → TA
    g.add_edge("s6", "PART_OF", "R2", "TOY", TOY)
    g.add_edge("f2", "PART_OF", "R2", "TOY", TOY)
    g.add_edge("R2", "SUGGESTS", "TA", "TOY", TOY)
    return g
