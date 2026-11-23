"""v5-2A.1 PatientGraph521 상속(원본 무수정): 입력 호출 이력(input_log)만 추가 — 가상 비교에서 같은 입력을 다시 쌓기 위함.
그래프 모드 수집은 v5-2A.1 graph 경로(compare521·declarations_graph)와 v4 그래프 추론기를 그대로 쓴다."""
from __future__ import annotations

from hybrid521.graphs import PatientGraph521


class PatientGraph522(PatientGraph521):
    def __init__(self, patient_id: str, patient_sex: str = "UNKNOWN"):
        super().__init__(patient_id, patient_sex)
        self.input_log = []

    def add_episode(self, ep):
        super().add_episode(ep)
        if hasattr(self, "input_log"):
            self.input_log.append(("episode", ep))

    def add_hypothesis_spec(self, s):
        super().add_hypothesis_spec(s)
        self.input_log.append(("hypothesis", s))

    def add_record52(self, doc, episode_id=None, source_event_id=None, derived_from=(), exact_duplicate_of=None):
        if doc.supersedes and doc.supersedes not in self.docs:
            # v4 add_record 는 docs·그래프 노드를 먼저 넣은 뒤 CORRECTS 간선에서 KeyError → 그래프/평면 불일치(부분 입력). 입력 전에 거부.
            raise KeyError(f"CORRECTION_PARENT_MISSING: {doc.supersedes} — 상태 변경 없이 거부")
        super().add_record52(doc, episode_id, source_event_id, derived_from, exact_duplicate_of)
        self.input_log.append(("record", doc, episode_id, source_event_id, tuple(derived_from), exact_duplicate_of))

    def add_observation52(self, o, episode_id=None, source_event_id=None, derived_from=()):
        super().add_observation52(o, episode_id, source_event_id, derived_from)
        self.input_log.append(("observation", o, episode_id, source_event_id, tuple(derived_from)))

    def declare_meta(self, record_key, source_event_id=None, derived_from=(), exact_duplicate_of=None):
        super().declare_meta(record_key, source_event_id, derived_from, exact_duplicate_of)
        self.input_log.append(("declare", record_key, source_event_id, tuple(derived_from), exact_duplicate_of))

    def add_test_order(self, test_id, test_kind, event, at, episode_id=None):
        super().add_test_order(test_id, test_kind, event, at, episode_id)
        self.input_log.append(("test", test_id, test_kind, event, at, episode_id))
