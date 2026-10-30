"""EXP-00 그래프 스키마 초안: 증상·질환·검사 관계 그래프 + 환자 관측 + 평가 규칙.

이번 단계 범위 = 스키마와 상태 전이의 정합성. 확률 추론·학습은 없다.

설계 원칙(EXP-00 graph_design.md 와 동일)
  - 관측 상태 5종: POSITIVE / NEGATIVE / UNCERTAIN / NOT_TESTED / NOT_RECORDED.
    UNCERTAIN·NOT_TESTED·NOT_RECORDED 는 절대 NEGATIVE 로 취급하지 않는다.
  - 관측은 append-only. 시점 질의(as_of)는 recorded_at <= as_of 인 관측만 본다(미래 정보 누출 방지).
  - 같은 source_id(같은 검사 1회에서 파생된 여러 기록)는 독립 근거 1개로만 센다.
  - 규칙 평가 결과(근거 충족도)와 질환 확률은 별개 값이다. 이 모듈은 확률을 만들지 않는다.
  - 가지치기 = '평가 규칙의 하위 작업 비활성화'. 질환 노드는 삭제하지 않는다.
    필수 적용 조건이 명시적으로 NEGATIVE 일 때만 UNMET → 하위 작업 비활성. 새 관측이 오면 재평가로 재활성.
  - 질환·검사 노드는 그래프에서 1개만 존재(여러 증상 경로가 같은 노드를 공유).
  - 의사 Working Diagnosis 는 탐색 기준(부분그래프 우선순위)일 뿐 다른 후보를 지우지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    UNCERTAIN = "UNCERTAIN"
    NOT_TESTED = "NOT_TESTED"
    NOT_RECORDED = "NOT_RECORDED"


class NodeType(str, Enum):
    SYMPTOM = "SYMPTOM"
    HISTORY = "HISTORY"
    DISEASE = "DISEASE"
    SUBTYPE = "SUBTYPE"
    TEST = "TEST"
    FINDING = "FINDING"


class Rel(str, Enum):
    SUGGESTS = "SUGGESTS"            # 증상 → 질환 (방향성 있는 연관, 인과 아님)
    ARGUES_AGAINST = "ARGUES_AGAINST"
    EVALUATED_BY = "EVALUATED_BY"    # 질환 → 검사
    YIELDS = "YIELDS"                # 검사 → 소견
    SUBTYPE_OF = "SUBTYPE_OF"
    PARENT_QUESTION = "PARENT_QUESTION"


class RuleState(str, Enum):
    SATISFIED = "SATISFIED"
    UNMET = "UNMET"                  # 필수 조건이 명시적으로 불충족
    INDETERMINATE = "INDETERMINATE"  # 판단 불가(미검사·미기록·불확실 포함)


@dataclass(frozen=True)
class Observation:
    node_id: str
    status: Status
    source_id: str                   # 같은 검사·같은 문서에서 파생된 기록은 같은 source_id
    observed_at: float               # 임상적 발생 시각(예: charttime)
    recorded_at: float               # 시스템에 알려진 시각(예: storetime) — 누출 판단 기준
    source_type: str = "patient_report"
    value: str | None = None
    provenance: str | None = None    # 원문 위치 포인터(원문 자체는 저장하지 않음)


@dataclass(frozen=True)
class Criterion:
    node_id: str
    required_status: Status = Status.POSITIVE


@dataclass(frozen=True)
class Condition:
    """AND/OR 조건. items 는 Criterion 또는 Condition."""
    op: str                          # "AND" | "OR"
    items: tuple


@dataclass
class Rule:
    rule_id: str
    disease_id: str
    applicability: Condition         # 적용 조건(불충족이 명시적일 때만 하위 작업 비활성)
    subtasks: tuple = ()             # 예: 추가 질문·검사 노드 id
    subtype_id: str | None = None
    stage: str | None = None


@dataclass
class KnowledgeGraph:
    nodes: dict = field(default_factory=dict)        # id → NodeType
    edges: set = field(default_factory=set)          # (src, Rel, dst)

    def add_node(self, node_id: str, ntype: NodeType) -> None:
        prev = self.nodes.get(node_id)
        if prev is not None and prev != ntype:
            raise ValueError(f"node type conflict: {node_id}")
        self.nodes[node_id] = ntype

    def add_edge(self, src: str, rel: Rel, dst: str) -> None:
        if src not in self.nodes or dst not in self.nodes:
            raise KeyError("edge endpoints must exist")
        self.edges.add((src, rel, dst))

    def neighbors(self, src: str, rel: Rel | None = None) -> set:
        return {d for s, r, d in self.edges if s == src and (rel is None or r == rel)}

    def diseases_from_symptoms(self, symptom_ids) -> set:
        out = set()
        for s in symptom_ids:
            out |= self.neighbors(s, Rel.SUGGESTS)
        return out


@dataclass
class PatientGraph:
    patient_id: str
    observations: list = field(default_factory=list)

    def add(self, obs: Observation) -> None:
        self.observations.append(obs)       # append-only, 덮어쓰기 없음

    def view(self, as_of: float) -> dict:
        """node_id → 최신 관측(recorded_at <= as_of). 없으면 NOT_RECORDED 로 해석."""
        latest: dict = {}
        for o in self.observations:
            if o.recorded_at > as_of:
                continue
            cur = latest.get(o.node_id)
            if cur is None or (o.recorded_at, o.observed_at) >= (cur.recorded_at, cur.observed_at):
                latest[o.node_id] = o
        return latest

    def status(self, node_id: str, as_of: float) -> Status:
        o = self.view(as_of).get(node_id)
        return o.status if o else Status.NOT_RECORDED

    def independent_evidence(self, as_of: float, status: Status = Status.POSITIVE) -> dict:
        """source_id 별로 묶은 독립 근거. 같은 검사에서 파생된 여러 기록은 1개."""
        groups: dict = {}
        for o in self.view(as_of).values():
            if o.status == status:
                groups.setdefault(o.source_id, set()).add(o.node_id)
        return groups


def evaluate(cond, pg: PatientGraph, as_of: float) -> RuleState:
    if isinstance(cond, Criterion):
        st = pg.status(cond.node_id, as_of)
        if st == cond.required_status:
            return RuleState.SATISFIED
        explicit_opposite = (
            (cond.required_status == Status.POSITIVE and st == Status.NEGATIVE)
            or (cond.required_status == Status.NEGATIVE and st == Status.POSITIVE)
        )
        return RuleState.UNMET if explicit_opposite else RuleState.INDETERMINATE
    states = [evaluate(x, pg, as_of) for x in cond.items]
    if cond.op == "AND":
        if any(s == RuleState.UNMET for s in states):
            return RuleState.UNMET
        return RuleState.SATISFIED if all(s == RuleState.SATISFIED for s in states) else RuleState.INDETERMINATE
    if cond.op == "OR":
        if any(s == RuleState.SATISFIED for s in states):
            return RuleState.SATISFIED
        return RuleState.UNMET if all(s == RuleState.UNMET for s in states) else RuleState.INDETERMINATE
    raise ValueError(f"unknown op {cond.op}")


def _leaves(cond) -> list:
    if isinstance(cond, Criterion):
        return [cond]
    out = []
    for x in cond.items:
        out += _leaves(x)
    return out


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    disease_id: str
    state: RuleState
    active_subtasks: tuple
    inactive_subtasks: tuple
    satisfaction: float              # 충족된 leaf 비율 — 확률이 아님


def apply_rules(rules, pg: PatientGraph, as_of: float) -> list:
    """규칙별 상태와 하위 작업 활성 여부. 질환 후보 집합은 건드리지 않는다."""
    out = []
    for r in rules:
        st = evaluate(r.applicability, pg, as_of)
        leaves = _leaves(r.applicability)
        sat = sum(evaluate(c, pg, as_of) == RuleState.SATISFIED for c in leaves) / max(len(leaves), 1)
        if st == RuleState.UNMET:
            out.append(RuleResult(r.rule_id, r.disease_id, st, (), tuple(r.subtasks), sat))
        else:
            out.append(RuleResult(r.rule_id, r.disease_id, st, tuple(r.subtasks), (), sat))
    return out


def candidate_set(kg: KnowledgeGraph, pg: PatientGraph, as_of: float, working_dx: str | None = None) -> list:
    """증상 기반 후보(상향식) ∪ 의사 WD(하향식 기준). WD 는 우선순위만 앞으로, 다른 후보 삭제 없음.
    부정 증상만으로 질환을 빼지 않는다."""
    positives = [n for n, o in pg.view(as_of).items()
                 if o.status == Status.POSITIVE and kg.nodes.get(n) in (NodeType.SYMPTOM, NodeType.HISTORY)]
    cands = sorted(kg.diseases_from_symptoms(positives))
    if working_dx is not None:
        if working_dx not in kg.nodes:
            raise KeyError("working diagnosis not in graph")
        cands = [working_dx] + [c for c in cands if c != working_dx]
    return cands
