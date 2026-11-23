"""평면 규칙표 기준선. 그래프와 같은 정규화 관계 원본·같은 조건 평가 함수(reason.evaluate_one)·같은 출력 형식.
관계는 (결과 상태, 진단) 키의 표, 환자 증거는 행 목록. 그래프 순회 대신 키 조회·필드 필터를 쓴다. 기능을 일부러 빼지 않는다
(출처·조건 구조·에피소드 필드·시간 공개 정책 모두 같은 값)."""
from __future__ import annotations


class FlatRuleTable:
    def __init__(self, relations: list):
        from .graphs import association_rows
        self.assoc = {(a["concept_node"], a["diagnosis"]) for a in association_rows()}    # 그래프와 같은 표시 전용 연관
        self.rows = list(relations)
        self.index = {}
        for r in self.rows:
            self.index.setdefault((r["finding"], r["target_diagnosis"]), []).append(r)
        from .graphs import EvidenceGraph
        self.diagnoses = {r["target_diagnosis"] for r in self.rows} | {n for n, v in EvidenceGraph().nodes.items() if v["kind"] == "DISEASE"}   # 그래프 A 와 같은 질환 범위

    def lookup(self, finding, diagnosis):
        return self.index.get((finding, diagnosis), [])

    def has_diagnosis(self, concept):
        return concept in self.diagnoses


def flat_episode_rows(pg, episode_id, as_of):
    """환자 그래프에서 내보낸 행을 필드로 걸러 쓴다(같은 추출 결과, 같은 시간 공개 정책)."""
    rows = pg.export_rows()
    vis = set(pg.visible_records(as_of))
    ev = [e for e in rows["evidence"] if e["diagnosis_episode_id"] == episode_id and e["source_record_id"] in vis]
    facts = [f for fid, f in ((k, v) for k, v in pg.g.nodes.items() if v["kind"] == "CONTEXT_FACT") if rows["fact_episode"].get(fid) == episode_id and f["source_record_id"] in vis]
    unresolved = [e for e in rows["evidence"] if e["diagnosis_episode_id"] == "UNRESOLVED_EPISODE_LINK" and e["source_record_id"] in vis]
    recs = {v["doc_id"] for v in pg.g.nodes.values() if v["kind"] == "SOURCE_RECORD" and v["diagnosis_episode_id"] == episode_id}
    texts = " ".join(pg.docs[d].text for d in vis if d in recs)
    return ev, facts, unresolved, texts
