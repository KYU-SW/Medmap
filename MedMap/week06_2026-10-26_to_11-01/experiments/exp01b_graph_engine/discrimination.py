"""질환 판별 정렬(그래프 구조 특이도) + 현재 진단 비교 출력 4분류. 37회차 고정 규칙 — 새 환자 결과를 보고 바꾸지 않는다.

[정렬 spec — 계산식 고정]
  환자 근거 묶음 g(엔진 support_groups: 같은 노드·같은 source·IS_A 의존 1 묶음, 중복 계산 없음)가 질환 d 를 지지할 때,
    reach_clin(g) = g 의 노드 또는 그 IS_A 상위 개념에서 DisMech SUGGESTS 간선(등급 DISMECH_*)이 닿는 질환 집합
    reach_all(g)  = 같은 방식, DisMech + HSDN SUGGESTS 간선 전체
    S_clin(d) = Σ_{g: 묶음 최고 등급 ≥ 1(DisMech)} 1 / |reach_clin(g)|
    S_all(d)  = Σ_{g: 모든 지지 묶음} 1 / |reach_all(g)|
  정렬 키 = (−S_clin, −S_all), 값은 소수 9자리 반올림 후 비교. 동점은 그대로 동점(평가에서 비관적·낙관적 둘 다 보고).
  의미: 그래프 안 4질환 중 몇 개와 연결되는지에 따른 '상대적 구분 기여'. 실제 임상 특이도·확률이 아니다.
  질환 제거 없음(지지 0 이면 점수 0). HSDN 과 DisMech 는 S_clin 에서 분리(HSDN 은 S_all 에만).
  학습·가중치 조정·임계값 없음.

[현재 진단 비교 4분류]
  A 현재 진단 지지 근거(묶음 수)
  B 다른 질환과 연결되지만 현재 진단 지식에는 없는 근거(EXPLAINED_BY_OTHER) — 추가 검토 가능 소견, 의학적 불일치 확정 아님
  C 그래프에 관계 자체가 없는 근거(UNEXPLAINED_IN_GRAPH) + 하위 개념만 연결(NARROWER_CONCEPT_LINKED) — 의료 지식 부족, 반박 아님
  D 출처가 검증된 반박 관계의 충돌(CONFLICTS) — 실제 그래프에는 반박 관계가 없어 판단 불가(NO_KNOWLEDGE)
  재검토 신호 = B ≥ 1 또는 D ≥ 1. 지식 부족 표시 = C ≥ 1. 둘을 섞지 않는다.
"""
from __future__ import annotations

from graph_engine import GRADE, Inference, MedGraph, WDAssessment, isa_closure

CLINICAL_CLASSES = {k for k, v in GRADE.items() if v >= 1}
ALL_CLASSES = set(GRADE)


def reach(g: MedGraph, nodes, classes) -> set:
    out = set()
    for n in nodes:
        for m in isa_closure(g, n):
            for e in g.out_edges(m, "SUGGESTS"):
                if e.spec_dict().get("evidence_class") in classes and g.nodes[e.dst].kind == "DISEASE":
                    out.add(e.dst)
    return out


def spec_scores(g: MedGraph, inf: Inference) -> dict:
    """질환 → {S_clin, S_all, groups:[(묶음, 등급, |reach_clin|, |reach_all|)]}."""
    out = {}
    for d, de in inf.diseases.items():
        rows, s_clin, s_all = [], 0.0, 0.0
        for grp, grade in zip(de.support_groups, de.group_grades or [""] * len(de.support_groups)):
            kc, ka = len(reach(g, grp, CLINICAL_CLASSES)), len(reach(g, grp, ALL_CLASSES))
            if GRADE.get(grade, -1) >= 1 and kc:
                s_clin += 1.0 / kc
            if ka:
                s_all += 1.0 / ka
            rows.append((sorted(grp), grade, kc, ka))
        out[d] = {"S_clin": round(s_clin, 9), "S_all": round(s_all, 9), "groups": rows}
    return out


def spec_key(sc: dict) -> tuple:
    return (-sc["S_clin"], -sc["S_all"])


def wd_categories(a: WDAssessment) -> dict:
    cls = [c for _, c, *_ in a.unexplained]
    B = cls.count("EXPLAINED_BY_OTHER")
    C = cls.count("UNEXPLAINED_IN_GRAPH") + cls.count("NARROWER_CONCEPT_LINKED")
    D = len(a.conflicting)
    return {"A_support_paths": len(a.supporting), "B_other_disease_only": B, "C_knowledge_gap": C,
            "C_no_relation": cls.count("UNEXPLAINED_IN_GRAPH"), "C_narrower_only": cls.count("NARROWER_CONCEPT_LINKED"),
            "D_verified_conflict": D, "D_status": "CHECKED" if a.conflict_knowledge == "CHECKED" else "판단 불가(반박 관계 없음)",
            "wd_path_not_satisfied": cls.count("WD_PATH_NOT_SATISFIED"),
            "review_signal": B > 0 or D > 0, "knowledge_gap_flag": C > 0}
