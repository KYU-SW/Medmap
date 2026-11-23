"""v5-2A PatientGraph52 상속(원본 무수정). 추가:
- 같은 기록 ID 중복 입력 거부
- 메타데이터 선언 이력(meta_log) 보존 + 나중 선언(declare_meta: 순환·사건 ID 충돌 같은 잘못된 메타데이터도 그대로 기록)
- 없는 부모 기록을 가리키는 파생 선언은 MISSING_SOURCE_RECORD 자리 노드로 보존(부분 출처)
- v5-2A 계층이 같은 기록의 선언을 그래프(첫 사건 간선)·평면표(마지막 선언)에서 다르게 읽지 않도록, 평면 meta 도 '첫 사건·모든 파생'으로 맞춤
선언 수집은 그래프 간선 순회로만 한다(평면표는 flat.py 에서 meta_log 행으로)."""
from __future__ import annotations

from hybrid52 import dependency as DP
from hybrid52.graphs import PatientGraph52

from . import comparator as CM


class PatientGraph521(PatientGraph52):
    def __init__(self, patient_id: str, patient_sex: str = "UNKNOWN"):
        super().__init__(patient_id, patient_sex)
        self.meta_log = []

    def add_record52(self, doc, episode_id=None, source_event_id=None, derived_from=(), exact_duplicate_of=None):
        if doc.doc_id in self.docs:
            raise ValueError(f"DUPLICATE_RECORD_ID: {doc.doc_id} 이미 입력됨(덮어쓰지 않음)")
        super().add_record52(doc, episode_id, source_event_id, derived_from, exact_duplicate_of)

    def add_observation52(self, o, episode_id=None, source_event_id=None, derived_from=()):
        if any(x.obs_id == o.obs_id for x in self.obs):
            raise ValueError(f"DUPLICATE_RECORD_ID: {o.obs_id} 이미 입력됨(덮어쓰지 않음)")
        super().add_observation52(o, episode_id, source_event_id, derived_from)

    def declare_meta(self, record_key, source_event_id=None, derived_from=(), exact_duplicate_of=None):
        nid = f"REC:{record_key}" if f"REC:{record_key}" in self.g.nodes else record_key
        if nid not in self.g.nodes:
            raise KeyError(record_key)
        self._meta(nid, DP.RecordMeta(record_key, source_event_id, tuple(derived_from), exact_duplicate_of))

    def _nid(self, key):
        if f"REC:{key}" in self.g.nodes or key in self.g.nodes:
            return super()._nid(key)
        self.g.node(key, "MISSING_SOURCE_RECORD", record_key=key)
        return key

    def _meta(self, nid, m):
        prev = self.meta.get(m.record_key)
        self.meta_log.append(m.as_row())
        super()._meta(nid, m)
        if prev is not None:                                              # 그래프 _meta_from_graph(첫 사건·모든 파생·첫 중복)와 같게
            self.meta[m.record_key] = DP.RecordMeta(m.record_key, prev.source_event_id or m.source_event_id,
                                                    tuple(dict.fromkeys(prev.derived_from + m.derived_from)), prev.exact_duplicate_of or m.exact_duplicate_of)

    # ---------- 그래프 순회 ----------
    def declarations_graph(self) -> tuple:
        rows, known = [], set()
        for nid, n in self.g.nodes.items():
            if n["kind"] not in ("SOURCE_RECORD", "LAB_OBSERVATION"):
                continue
            key = self._key(nid)
            if n["kind"] == "SOURCE_RECORD" or n.get("source_type") == "STRUCTURED_LAB":
                known.add(key)
            for e in self.g.outs(nid, "FROM_SOURCE_EVENT"):
                rows.append({"record_key": key, "source_event_id": self.g.nodes[e["dst"]]["source_event_id"]})
            for e in self.g.outs(nid, "DERIVED_FROM_RECORD"):
                rows.append({"record_key": key, "derived_from": [self._key(e["dst"])]})
            for e in self.g.outs(nid, "EXACT_DUPLICATE_OF"):
                rows.append({"record_key": key, "exact_duplicate_of": self._key(e["dst"])})
        return rows, known

    def compare521(self, as_of: float) -> dict:
        return CM.compare521(self, as_of, "graph")
