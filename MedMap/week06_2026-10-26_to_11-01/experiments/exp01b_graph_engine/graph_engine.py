"""EXP-01b 의료 관계 그래프 추론 엔진(최소 구현, 탐색 단계 — 성능 주장 없음).

재사용(수정 없이 import): exp/main_ai/common/evidence_graph.py
  - Status(5상태), RuleState(SATISFIED/UNMET/INDETERMINATE), Observation(관측 레코드),
    PatientGraph(append-only 저장 + view(as_of) 시점 질의).
새로 구현(이 파일):
  - MedGraph: 노드 1개 공유·유형 있는 간선·간선 출처/등급(REAL/TOY) 필수·유형 호환 검사.
  - EvidenceRecord / PatientRecord: 근거 고유 ID·출처·발생/확인 시점·원래 값·단위·정정 이력.
  - 3값 논리 조건 평가(상태·범주값·수치 임계치), 규칙 노드(AND/OR) + 적용 조건(GATES).
  - infer(): 그래프 간선을 따라 근거 → (규칙) → 질환 경로를 평가, 다중 경로 통합, 근거 중복 방지.
  - assess_working_dx(): 의사 현재 진단의 뒷받침/설명 부족/명시적 충돌/판단 불가/추가 검토 후보 분리.
  - ReasoningSession: 새 근거 입력 시 영향받는 질환만 그래프 순회로 찾아 재계산, 경로 상태 전이(재활성화 등) 기록.

원칙
  - 미기록(NOT_RECORDED)·미검사(NOT_TESTED)·불확실(UNCERTAIN)은 음성이 아니다 → 조건은 INDETERMINATE.
  - 음성 답변은 해당 경로를 NEGATED 로 표시할 뿐 질환을 제거하지 않는다. 모든 질환 노드는 항상 출력된다.
  - 규칙 적용 조건이 명시적으로 불충족(UNMET)일 때만 그 규칙 경로를 DISABLED(가역). 매 호출 재평가.
  - 같은 근거 노드는 경로가 여러 개여도 1번만 센다. 같은 source_id·알려진 DEPENDS_ON 은 한 묶음.
    서로 다른 묶음 사이의 독립성은 지식에 근거가 없으므로 '독립성 미확인'으로 표시한다(곱셈·합산 확률 없음).
  - 이 엔진은 확률을 만들지 않는다. 정렬 키는 '독립 지지 묶음 수'이며 확률·진단 확정이 아니다.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.dont_write_bytecode = True                       # 동결 폴더(exp/main_ai)에 캐시 파일을 만들지 않음
_MAIN_AI = Path(os.environ.get("EXP01B_MAIN_AI", Path(__file__).resolve().parents[1] / "main_ai"))
if str(_MAIN_AI) not in sys.path:
    sys.path.insert(0, str(_MAIN_AI))

from common.evidence_graph import Observation, PatientGraph, RuleState, Status  # noqa: E402  (재사용)

# ───────────────────────── 그래프 구조 ─────────────────────────

NODE_KINDS = {"DISEASE", "SYMPTOM", "FINDING", "TEST", "RISK_FACTOR", "HISTORY", "RULE"}
EVIDENCE_KINDS = {"SYMPTOM", "FINDING", "RISK_FACTOR", "HISTORY"}
TIERS = {"REAL", "TOY"}

# 관계 유형 → (허용 출발 유형, 허용 도착 유형). 연산 의미는 infer() 참고.
REL_KINDS = {
    "SUGGESTS": (EVIDENCE_KINDS | {"RULE"}, {"DISEASE"}),        # 뒷받침
    "ARGUES_AGAINST": (EVIDENCE_KINDS, {"DISEASE"}),             # 양성이면 명시적 충돌
    "RISK_FACTOR_FOR": ({"RISK_FACTOR", "HISTORY"}, {"DISEASE"}),  # 위험인자(뒷받침, 역할 구분)
    "PART_OF": (EVIDENCE_KINDS, {"RULE"}),                       # 규칙 본문 조건
    "GATES": (EVIDENCE_KINDS, {"RULE"}),                         # 규칙 적용 조건
    "YIELDS": ({"TEST"}, {"FINDING"}),                           # 검사 → 소견
    "DEPENDS_ON": (EVIDENCE_KINDS, EVIDENCE_KINDS),              # 알려진 근거 의존(중복 계산 방지)
    "IS_A": (EVIDENCE_KINDS, EVIDENCE_KINDS),                    # 하위 개념 → 상위 개념(온톨로지). 하위 양성 ⇒ 상위 양성만 유도
    "EVALUATES": ({"TEST"}, {"DISEASE"}),                        # 검사 → 질환(확인 가능 검사 안내, 점수 없음)
    "DIFFERENTIAL_OF": ({"DISEASE"}, {"DISEASE"}),               # 지식원이 명시한 감별 관계(추가 검토 후보 안내, 점수 없음)
}


@dataclass(frozen=True)
class Node:
    node_id: str
    kind: str
    label: str
    tier: str
    source: str
    attrs: tuple = ()                 # 규칙 노드: (("op","AND"),("gate_op","AND"))

    def attr(self, key, default=None):
        return dict(self.attrs).get(key, default)


@dataclass(frozen=True)
class Edge:
    src: str
    rel: str
    dst: str
    tier: str
    source: str                       # 출처(빈 문자열 금지)
    spec: tuple = ()                  # 조건 명세: required / values / threshold

    def spec_dict(self) -> dict:
        return dict(self.spec)


class MedGraph:
    """노드는 id 당 1개(경로마다 복제하지 않음). 간선은 출발/도착 색인 둘 다 유지."""

    def __init__(self, name: str):
        self.name = name
        self.nodes: dict[str, Node] = {}
        self.out: dict[str, list[Edge]] = {}
        self.inc: dict[str, list[Edge]] = {}

    def add_node(self, node_id, kind, label, tier, source, **attrs) -> Node:
        if kind not in NODE_KINDS:
            raise ValueError(f"unknown node kind {kind}")
        if tier not in TIERS:
            raise ValueError(f"unknown tier {tier}")
        if not source:
            raise ValueError(f"node {node_id}: source required")
        prev = self.nodes.get(node_id)
        if prev is not None:
            if prev.kind != kind or prev.tier != tier:
                raise ValueError(f"node conflict: {node_id}")
            return prev                                  # 같은 노드 재등록 = 공유(중복 생성 없음)
        n = Node(node_id, kind, label, tier, source, tuple(sorted(attrs.items())))
        self.nodes[node_id] = n
        self.out[node_id] = []
        self.inc[node_id] = []
        return n

    def add_edge(self, src, rel, dst, tier, source, **spec) -> Edge:
        if src not in self.nodes or dst not in self.nodes:
            raise KeyError(f"edge endpoints must exist: {src} -> {dst}")
        if rel not in REL_KINDS:
            raise ValueError(f"unknown relation {rel}")
        ok_src, ok_dst = REL_KINDS[rel]
        if self.nodes[src].kind not in ok_src or self.nodes[dst].kind not in ok_dst:
            raise ValueError(f"relation {rel} not allowed: {self.nodes[src].kind} -> {self.nodes[dst].kind}")
        if tier not in TIERS:
            raise ValueError(f"unknown tier {tier}")
        if not source:
            raise ValueError("edge source required")
        if tier == "TOY" and "REAL" in (self.nodes[src].tier, self.nodes[dst].tier):
            raise ValueError("TOY relation must not attach to REAL knowledge nodes")
        if tier == "REAL" and "TOY" in (self.nodes[src].tier, self.nodes[dst].tier):
            raise ValueError("REAL relation must not attach to TOY nodes")
        e = Edge(src, rel, dst, tier, source, tuple(sorted(spec.items())))
        if e in self.out[src]:
            return e
        self.out[src].append(e)
        self.inc[dst].append(e)
        return e

    def out_edges(self, node_id, rel=None) -> list[Edge]:
        return [e for e in self.out.get(node_id, []) if rel is None or e.rel == rel]

    def in_edges(self, node_id, rel=None) -> list[Edge]:
        return [e for e in self.inc.get(node_id, []) if rel is None or e.rel == rel]

    def diseases(self) -> list[str]:
        return sorted(n for n, v in self.nodes.items() if v.kind == "DISEASE")

    def remove_edge(self, edge: Edge) -> None:
        """테스트용(간선 제거 시 결과가 바뀌는지 = 그래프가 실제 연산에 쓰이는지 확인)."""
        self.out[edge.src].remove(edge)
        self.inc[edge.dst].remove(edge)


# ───────────────────────── 환자 근거 ─────────────────────────

@dataclass(frozen=True)
class EvidenceRecord(Observation):
    """Observation(재사용) + 근거 고유 ID·단위·정정 대상. value 는 원래 값(문자열 그대로)."""
    evidence_id: str = ""
    unit: str | None = None
    supersedes: str | None = None


class PatientRecord:
    """PatientGraph(append-only) 위에 근거 ID 고유성·정정 이력 규칙을 더한다. 기존 기록은 삭제하지 않는다."""

    def __init__(self, patient_id: str, age=None, sex=None, working_dx=None):
        self.pg = PatientGraph(patient_id)
        self.age = age                 # 미제공이면 None 그대로(임의 대체 없음)
        self.sex = sex
        self.working_dx = working_dx
        self._by_id: dict[str, EvidenceRecord] = {}

    def add(self, rec: EvidenceRecord) -> None:
        if not rec.evidence_id:
            raise ValueError("evidence_id required")
        if rec.evidence_id in self._by_id:
            raise ValueError(f"duplicate evidence_id {rec.evidence_id}")
        if not rec.source_id:
            raise ValueError("source_id required")
        if rec.supersedes is not None:
            old = self._by_id.get(rec.supersedes)
            if old is None:
                raise KeyError(f"supersedes unknown evidence {rec.supersedes}")
            if old.node_id != rec.node_id:
                raise ValueError("correction must target the same node")
            if rec.recorded_at <= old.recorded_at:          # view() 는 recorded_at 최신을 택하므로 엄격히 이후
                raise ValueError("correction must be recorded after the original")
        self._by_id[rec.evidence_id] = rec
        self.pg.add(rec)

    def view(self, as_of: float) -> dict:
        return self.pg.view(as_of)

    def history(self, node_id: str) -> list[EvidenceRecord]:
        return [o for o in self.pg.observations if o.node_id == node_id]

    def all_records(self) -> list[EvidenceRecord]:
        return list(self.pg.observations)


def from_medmap_input(patient_id: str, data: dict, recorded_at: float = 0.0) -> PatientRecord:
    """기존 MedMap 입력 형식(나이·성별·첫 증상·이진 질문·범주형 질문·추가 답변) → PatientRecord.
    data 키: age, sex, initial_evidence, binary{node: 'POSITIVE'|'NEGATIVE'|'UNCERTAIN'|'NOT_TESTED'},
             categorical{node: value}, extra[EvidenceRecord kwargs], working_dx.
    없는 키는 만들지 않는다(그 노드는 NOT_RECORDED 로 남음)."""
    pr = PatientRecord(patient_id, data.get("age"), data.get("sex"), data.get("working_dx"))
    k = 0

    def nid():
        nonlocal k
        k += 1
        return f"{patient_id}-e{k:03d}"

    if data.get("initial_evidence"):
        pr.add(EvidenceRecord(data["initial_evidence"], Status.POSITIVE, f"{patient_id}-q-initial", recorded_at,
                              recorded_at, "patient_report", evidence_id=nid()))
    for node, st in (data.get("binary") or {}).items():
        pr.add(EvidenceRecord(node, Status(st), f"{patient_id}-q-{node}", recorded_at, recorded_at,
                              "patient_report", evidence_id=nid()))
    for node, val in (data.get("categorical") or {}).items():
        pr.add(EvidenceRecord(node, Status.POSITIVE, f"{patient_id}-q-{node}", recorded_at, recorded_at,
                              "patient_report", value=str(val), evidence_id=nid()))
    for kw in data.get("extra") or []:
        kw = dict(kw)
        kw["status"] = Status(kw["status"])
        kw.setdefault("evidence_id", nid())
        pr.add(EvidenceRecord(**kw))
    return pr


# ───────────────────────── 조건 평가(3값 논리) ─────────────────────────

UNKNOWN_STATES = (Status.UNCERTAIN, Status.NOT_TESTED, Status.NOT_RECORDED)


@dataclass(frozen=True)
class LeafEval:
    node_id: str
    state: RuleState
    status: Status
    reason: str
    evidence_id: str | None
    edge_source: str


def eval_leaf(edge: Edge, view: dict) -> LeafEval:
    """간선 명세(required/values/threshold)를 환자 관측에 적용. 미기록·미검사·불확실 → INDETERMINATE."""
    spec = edge.spec_dict()
    node = edge.src
    obs = view.get(node)
    st = obs.status if obs else Status.NOT_RECORDED
    eid = getattr(obs, "evidence_id", None) if obs else None
    required = Status(spec.get("required", "POSITIVE"))

    def out(state, reason):
        return LeafEval(node, state, st, reason, eid, edge.source)

    if st in UNKNOWN_STATES:
        return out(RuleState.INDETERMINATE, f"{st.value}: 판단 보류")
    if st == Status.NEGATIVE and spec.get("negative_uninformative"):
        return out(RuleState.INDETERMINATE, "음성이지만 지식원이 '음성은 정보 없음'으로 명시 — 판단 보류")
    if required == Status.NEGATIVE:
        return out(RuleState.SATISFIED, "명시적 음성 확인") if st == Status.NEGATIVE else \
            out(RuleState.UNMET, "음성이 필요하나 양성")
    if st == Status.NEGATIVE:
        return out(RuleState.UNMET, "명시적 음성")
    # st == POSITIVE
    if "values" in spec:
        if obs.value is None:
            return out(RuleState.INDETERMINATE, "범주값 미기록")
        return out(RuleState.SATISFIED, f"범주값 {obs.value} 일치") if obs.value in spec["values"] else \
            out(RuleState.UNMET, f"범주값 {obs.value} 불일치(필요 {list(spec['values'])})")
    if "threshold" in spec:
        op, thr, unit = spec["threshold"]
        if obs.value is None or getattr(obs, "unit", None) is None:
            return out(RuleState.INDETERMINATE, "수치·단위 미기록")
        if obs.unit != unit:
            return out(RuleState.INDETERMINATE, f"단위 불일치({obs.unit}≠{unit}) — 변환 규칙 없음")
        try:
            v = float(obs.value)
        except ValueError:
            return out(RuleState.INDETERMINATE, f"수치 해석 불가({obs.value})")
        ok = {">=": v >= thr, ">": v > thr, "<=": v <= thr, "<": v < thr}[op]
        return out(RuleState.SATISFIED if ok else RuleState.UNMET, f"{obs.value} {obs.unit} {op} {thr}: {ok}")
    return out(RuleState.SATISFIED, "양성")


def combine(op: str, states: list) -> RuleState:
    if op == "AND":
        if any(s == RuleState.UNMET for s in states):
            return RuleState.UNMET
        return RuleState.SATISFIED if states and all(s == RuleState.SATISFIED for s in states) \
            else RuleState.INDETERMINATE
    if op == "OR":
        if any(s == RuleState.SATISFIED for s in states):
            return RuleState.SATISFIED
        return RuleState.UNMET if states and all(s == RuleState.UNMET for s in states) \
            else RuleState.INDETERMINATE
    if op.startswith("ATLEAST:"):                    # k 개 이상 충족(예: 4 중 2 진단 기준)
        k = int(op.split(":")[1])
        sat = sum(s == RuleState.SATISFIED for s in states)
        und = sum(s == RuleState.INDETERMINATE for s in states)
        if sat >= k:
            return RuleState.SATISFIED
        return RuleState.UNMET if sat + und < k else RuleState.INDETERMINATE
    raise ValueError(f"unknown op {op}")


@dataclass(frozen=True)
class RuleEval:
    rule_id: str
    body_state: RuleState
    gate_state: RuleState
    disabled: bool                    # 적용 조건 명시적 불충족 → 경로 비활성(가역)
    body_leaves: tuple
    gate_leaves: tuple


def eval_rule(g: MedGraph, rule_id: str, view: dict) -> RuleEval:
    node = g.nodes[rule_id]
    body = [eval_leaf(e, view) for e in g.in_edges(rule_id, "PART_OF")]
    gates = [eval_leaf(e, view) for e in g.in_edges(rule_id, "GATES")]
    body_state = combine(node.attr("op", "AND"), [x.state for x in body])
    gate_state = combine(node.attr("gate_op", "AND"), [x.state for x in gates]) if gates else RuleState.SATISFIED
    return RuleEval(rule_id, body_state, gate_state, gate_state == RuleState.UNMET, tuple(body), tuple(gates))


# ───────────────────────── 질환별 경로 평가 ─────────────────────────

# 근거 등급(확인 수준의 순서, 확률 아님). 개수와 섞지 않는다: 묶음 하나에는 최고 등급 하나만 붙인다.
GRADE = {"LITERATURE_QUOTE_IN_TEXT": 3, "DISMECH_QUOTE_IN_ABSTRACT": 3, "DISMECH_PMID_QUOTE_UNVERIFIED": 2, "DISMECH_NO_REF": 1,
         "HSDN_LITERATURE_COOCCURRENCE": 0}

@dataclass(frozen=True)
class PathEval:
    path_id: str
    disease: str
    rel: str                          # SUGGESTS / RISK_FACTOR_FOR / ARGUES_AGAINST / RULE
    state: str                        # SUPPORTS / CONFLICTS / NEGATED / UNMET / UNKNOWN / DISABLED / NO_CONFLICT
    evidence_nodes: tuple             # 이 경로가 실제로 쓴 근거 노드
    hops: tuple                       # ((src, rel, dst, source, tier), ...)
    detail: str
    evidence_ids: tuple = ()
    evidence_class: str = ""          # 지식원 근거 등급(간선 spec), 없으면 빈 값


@dataclass
class DiseaseEval:
    disease: str
    paths: list
    support_nodes: tuple = ()
    support_groups: tuple = ()        # 독립 묶음(frozenset 들)
    independence: str = "N/A"         # N/A / UNVERIFIED (묶음 2개 이상이면 독립성 근거 없음)
    conflicts: tuple = ()
    negated: tuple = ()
    unknown: tuple = ()
    disabled: tuple = ()
    group_grades: tuple = ()          # 묶음별 최고 근거 등급 이름(support_groups 와 같은 순서)

    @property
    def n_support(self) -> int:
        return len(self.support_groups)

    @property
    def n_clinical(self) -> int:
        """임상 소견 근거(지식원 소견 주석)로 뒷받침되는 묶음 수. 공출현만 있는 묶음·등급 없는(가상) 묶음 제외."""
        return sum(1 for g in self.group_grades if GRADE.get(g, -1) >= 1)

    @property
    def n_cooccurrence_only(self) -> int:
        return sum(1 for g in self.group_grades if g == "HSDN_LITERATURE_COOCCURRENCE")


def _test_hops(g: MedGraph, node: str, obs) -> tuple:
    """소견이 검사 기록에서 왔으면 검사 → 소견 간선(다단계 경로)을, IS_A 로 유도된 양성이면 하위 → 상위 간선을 경로에 포함."""
    if obs is None:
        return ()
    if obs.source_type == "derived_is_a":
        return tuple(obs.provenance_hops)
    if obs.source_type != "test":
        return ()
    return tuple((e.src, e.rel, e.dst, e.source, e.tier) for e in g.in_edges(node, "YIELDS"))


@dataclass(frozen=True)
class DerivedRecord(EvidenceRecord):
    """IS_A 로 유도된 양성(원 기록의 evidence_id·source_id 그대로 → 같은 근거 묶음, 이중 계산 없음)."""
    provenance_hops: tuple = ()


def with_is_a(g: MedGraph, view: dict) -> dict:
    """하위 개념 양성 → IS_A 간선을 따라 상위 개념 양성 유도. 상위 개념에 직접 기록이 있으면 직접 기록 우선.
    음성·미확정은 전파하지 않는다(상위 음성 ⇒ 하위 음성 같은 역방향 추론도 하지 않음)."""
    out = dict(view)
    for n, o in view.items():
        if o.status != Status.POSITIVE or n not in g.nodes:
            continue
        stack = [(n, ())]
        while stack:
            cur, hops = stack.pop()
            for e in g.out_edges(cur, "IS_A"):
                h = hops + ((e.src, e.rel, e.dst, e.source, e.tier),)
                if e.dst not in out:
                    out[e.dst] = DerivedRecord(e.dst, Status.POSITIVE, o.source_id, o.observed_at, o.recorded_at,
                                               "derived_is_a", value=o.value, provenance=f"IS_A from {n}",
                                               evidence_id=getattr(o, "evidence_id", ""), provenance_hops=h)
                stack.append((e.dst, h))
    return out


def eval_disease(g: MedGraph, d: str, view: dict, rule_cache: dict) -> DiseaseEval:
    paths: list[PathEval] = []
    for e in g.in_edges(d):
        hop = (e.src, e.rel, e.dst, e.source, e.tier)
        if e.rel == "SUGGESTS" and g.nodes[e.src].kind == "RULE":
            r = rule_cache.get(e.src) or eval_rule(g, e.src, view)
            rule_cache[e.src] = r
            leaves = r.body_leaves + r.gate_leaves
            leaf_hops = tuple((x.node_id, "PART_OF", e.src, x.edge_source, e.tier) for x in r.body_leaves) + \
                tuple((x.node_id, "GATES", e.src, x.edge_source, e.tier) for x in r.gate_leaves)
            detail = "; ".join(f"{x.node_id}={x.state.value}({x.reason})" for x in leaves)
            if r.disabled:
                st, used = "DISABLED", ()
            elif r.body_state == RuleState.SATISFIED:
                st = "SUPPORTS"
                used = tuple(x.node_id for x in r.body_leaves if x.state == RuleState.SATISFIED)
                if r.gate_state == RuleState.INDETERMINATE:
                    detail = "[적용 조건 미확정] " + detail
            elif r.body_state == RuleState.UNMET:
                st, used = "UNMET", ()
            else:
                st, used = "UNKNOWN", ()
            ids = tuple(x.evidence_id for x in r.body_leaves if x.node_id in used and x.evidence_id)
            extra = sum((_test_hops(g, n, view.get(n)) for n in used), ())
            rt = g.nodes[e.src].attr("rule_type")
            if rt:
                detail = f"[{rt}] " + detail
            paths.append(PathEval(f"{e.src}->{d}", d, "RULE", st, used, extra + leaf_hops + (hop,), detail, ids,
                                  e.spec_dict().get("evidence_class", "")))
            continue
        if e.rel not in ("SUGGESTS", "RISK_FACTOR_FOR", "ARGUES_AGAINST"):
            continue
        leaf = eval_leaf(e, view)
        hops = _test_hops(g, e.src, view.get(e.src)) + (hop,)
        ids = (leaf.evidence_id,) if leaf.evidence_id else ()
        if e.rel == "ARGUES_AGAINST":
            st = {RuleState.SATISFIED: "CONFLICTS", RuleState.UNMET: "NO_CONFLICT",
                  RuleState.INDETERMINATE: "UNKNOWN"}[leaf.state]
        else:
            st = {RuleState.SATISFIED: "SUPPORTS", RuleState.UNMET: "NEGATED",
                  RuleState.INDETERMINATE: "UNKNOWN"}[leaf.state]
        used = (e.src,) if st in ("SUPPORTS", "CONFLICTS") else ()
        ec = e.spec_dict().get("evidence_class", "")
        pid = f"{e.src}-{e.rel}->{d}" + (f"#{ec}" if ec else "")      # 같은 두 노드 사이 지식원별 간선 구분
        paths.append(PathEval(pid, d, e.rel, st, used, hops, leaf.reason, ids, ec))
    return _aggregate(g, d, paths, view)


def _aggregate(g: MedGraph, d: str, paths: list, view: dict) -> DiseaseEval:
    support_nodes = sorted({n for p in paths if p.state == "SUPPORTS" for n in p.evidence_nodes})  # 노드 중복 제거
    # 묶음: 같은 source_id 또는 알려진 DEPENDS_ON 간선 → union-find
    parent = {n: n for n in support_nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    by_src: dict = {}
    for n in support_nodes:
        o = view.get(n)
        if o is not None:
            by_src.setdefault(o.source_id, []).append(n)
        for e in [x for r in ("DEPENDS_ON", "IS_A") for x in g.out_edges(n, r) + g.in_edges(n, r)]:   # 알려진 의존·상하위 개념
            other = e.dst if e.src == n else e.src
            if other in parent:
                union(n, other)
    for ns in by_src.values():
        for x in ns[1:]:
            union(ns[0], x)
    groups: dict = {}
    for n in support_nodes:
        groups.setdefault(find(n), set()).add(n)
    sg = tuple(sorted((frozenset(v) for v in groups.values()), key=lambda s: sorted(s)))
    grades = []
    for grp in sg:
        cls = [p.evidence_class for p in paths if p.state == "SUPPORTS" and grp & set(p.evidence_nodes)]
        grades.append(max(cls, key=lambda c: GRADE.get(c, -1)) if cls else "")
    de = DiseaseEval(
        d, paths, tuple(support_nodes), sg, "UNVERIFIED" if len(sg) > 1 else "N/A",
        tuple(p for p in paths if p.state == "CONFLICTS"),
        tuple(p for p in paths if p.state in ("NEGATED", "UNMET")),
        tuple(p for p in paths if p.state == "UNKNOWN"),
        tuple(p for p in paths if p.state == "DISABLED"))
    de.group_grades = tuple(grades)
    return de


@dataclass
class Inference:
    graph_name: str
    as_of: float
    diseases: dict                    # id → DiseaseEval (모든 질환 노드, 제거 없음)
    positive_in_graph: tuple
    positive_out_of_graph: tuple      # 그래프에 없는 양성 근거(지식 없음 → 추론 불가)

    def ranking(self, key: str = "support") -> list:
        """support(기본): 독립 지지 묶음 수 ↓, 충돌 수 ↑. graded: 임상 소견 근거 묶음 수 ↓ → 전체 묶음 수 ↓ → 충돌 ↑
        (공출현만 있는 묶음은 둘째 기준으로만). 확률·진단 아님."""
        if key == "graded":
            return sorted(self.diseases.values(),
                          key=lambda x: (-x.n_clinical, -x.n_support, len(x.conflicts), x.disease))
        return sorted(self.diseases.values(), key=lambda x: (-x.n_support, len(x.conflicts), x.disease))


def infer(g: MedGraph, pr: PatientRecord, as_of: float, only=None, prev: Inference | None = None) -> Inference:
    view = with_is_a(g, pr.view(as_of))
    rule_cache: dict = {}
    targets = set(g.diseases()) if only is None else set(only)
    out = {} if prev is None else dict(prev.diseases)
    for d in g.diseases():
        if d in targets or d not in out:
            out[d] = eval_disease(g, d, view, rule_cache)
    pos = sorted(n for n, o in view.items() if o.status == Status.POSITIVE and not isinstance(o, DerivedRecord))
    return Inference(g.name, as_of, out, tuple(n for n in pos if n in g.nodes),
                     tuple(n for n in pos if n not in g.nodes))


# ───────────────────────── 재계산 범위(그래프 순회) ─────────────────────────

def affected_diseases(g: MedGraph, changed_nodes) -> set:
    """바뀐 근거 노드에서 간선을 따라 도달하는 질환(직접·규칙 경유·DEPENDS_ON 이웃 포함)."""
    seen, stack, out = set(), list(changed_nodes), set()
    while stack:
        n = stack.pop()
        if n in seen or n not in g.nodes:
            continue
        seen.add(n)
        for e in g.out_edges(n):
            k = g.nodes[e.dst].kind
            if k == "DISEASE":
                out.add(e.dst)
            elif k == "RULE" or e.rel in ("DEPENDS_ON", "IS_A"):
                stack.append(e.dst)
        for e in g.in_edges(n, "DEPENDS_ON"):
            stack.append(e.src)
    return out


@dataclass(frozen=True)
class Transition:
    path_id: str
    before: str
    after: str

    @property
    def kind(self) -> str:
        if self.before == "DISABLED" and self.after != "DISABLED":
            return "REACTIVATED"
        if self.after == "DISABLED" and self.before != "DISABLED":
            return "DISABLED"
        return "CHANGED"


class ReasoningSession:
    def __init__(self, g: MedGraph, pr: PatientRecord, as_of: float):
        self.g, self.pr = g, pr
        self.current = infer(g, pr, as_of)
        self.log: list = []

    def update(self, records, as_of: float):
        changed = set()
        for r in records:
            self.pr.add(r)
            changed.add(r.node_id)
        aff = affected_diseases(self.g, changed)
        new = infer(self.g, self.pr, as_of, only=aff, prev=self.current)
        trans = []
        for d in aff:
            b = {p.path_id: p.state for p in self.current.diseases[d].paths}
            a = {p.path_id: p.state for p in new.diseases[d].paths}
            for pid in sorted(set(a) | set(b)):
                if a.get(pid) != b.get(pid):
                    trans.append(Transition(pid, b.get(pid, "-"), a.get(pid, "-")))
        self.log.append({"as_of": as_of, "changed_nodes": sorted(changed), "recomputed": sorted(aff),
                         "transitions": trans})
        self.current = new
        return new, trans, aff


# ───────────────────────── 의사 현재 진단 비교 ─────────────────────────

@dataclass
class WDAssessment:
    working_dx: str
    status: str                       # ASSESSED / INFERENCE_IMPOSSIBLE
    supporting: tuple = ()            # PathEval
    unexplained: tuple = ()           # (node, 분류, 설명하는 다른 질환들)
    conflicting: tuple = ()           # PathEval
    conflict_knowledge: str = ""      # CHECKED / NO_KNOWLEDGE(충돌 판단용 관계 없음 → 근거 부족)
    undetermined: tuple = ()          # (node, status, 관련 경로, 확인 가능한 검사)
    review_candidates: tuple = ()     # (disease, 이유)
    out_of_graph: tuple = ()
    note: str = ""
    tests_available: tuple = ()       # (검사 노드, 출처) — EVALUATES 간선, 환자 결과 없음


def _structural_links(g: MedGraph, node: str, d: str) -> list:
    """node 에서 질환 d 로 가는 그래프 경로 종류(직접 간선 또는 규칙 경유)."""
    out = []
    for e in g.out_edges(node):
        if e.dst == d:
            out.append(e.rel)
        elif g.nodes[e.dst].kind == "RULE" and any(x.dst == d for x in g.out_edges(e.dst, "SUGGESTS")):
            out.append(f"{e.rel}:{e.dst}")
    return out


def assess_working_dx(g: MedGraph, inf: Inference, pr: PatientRecord, wd: str) -> WDAssessment:
    if wd not in g.nodes or g.nodes[wd].kind != "DISEASE":
        return WDAssessment(wd, "INFERENCE_IMPOSSIBLE", out_of_graph=inf.positive_out_of_graph,
                            note="현재 진단이 그래프에 없음 — 비교 불가")
    view = with_is_a(g, pr.view(inf.as_of))
    de = inf.diseases[wd]
    supporting = tuple(p for p in de.paths if p.state == "SUPPORTS")
    conflicting = de.conflicts
    used = set(de.support_nodes) | {n for p in conflicting for n in p.evidence_nodes}
    unexplained = []
    pos_set = set(inf.positive_in_graph)
    for n in inf.positive_in_graph:
        # 자기·상위 개념, 또는 환자에게 양성인 하위 개념(같은 증상의 더 구체적 기록)이 쓰였으면 설명됨
        rel_nodes = isa_closure(g, n) | (isa_descendants(g, n) & pos_set)
        if rel_nodes & used or g.nodes[n].kind not in EVIDENCE_KINDS:
            continue
        outs = g.out_edges(n)
        if outs and all(e.rel in ("GATES", "DEPENDS_ON") for e in outs):
            continue                                  # 규칙 적용 조건(관계 유형 = 조건)은 설명 대상 근거가 아님
        clo = rel_nodes
        links = [lk for m in sorted(clo) for lk in _structural_links(g, m, wd)]
        others = tuple(sorted(x for x, v in inf.diseases.items() if x != wd and clo & set(v.support_nodes)))
        narrower = tuple(sorted({e.dst for c in isa_descendants(g, n) for e in g.out_edges(c, "SUGGESTS")
                                 if g.nodes[e.dst].kind == "DISEASE"}))
        if links:
            cls = "WD_PATH_NOT_SATISFIED"        # 경로는 있으나 조건 미충족·비활성·미확정
        elif others:
            cls = "EXPLAINED_BY_OTHER"           # 현재 진단으로는 설명 부족, 다른 후보가 설명
        elif narrower:
            cls = "NARROWER_CONCEPT_LINKED"      # 질환에는 더 구체적인 하위 개념만 연결 — 하위 개념 확인 전 판단 불가
            others = narrower
        else:
            cls = "UNEXPLAINED_IN_GRAPH"         # 그래프 안 어떤 질환도 설명하지 못함
        unexplained.append((n, cls, others, tuple(links)))
    undetermined = []
    for p in de.paths:
        if p.state not in ("UNKNOWN", "DISABLED"):
            continue
        for h in p.hops:
            n = h[0]
            if n in g.nodes and g.nodes[n].kind in EVIDENCE_KINDS:
                o = view.get(n)
                st = o.status if o else Status.NOT_RECORDED
                if st in UNKNOWN_STATES:
                    tests = tuple(sorted(e.src for e in g.in_edges(n, "YIELDS")))
                    undetermined.append((n, st.value, p.path_id, tests))
    undetermined = tuple(sorted(set(undetermined)))
    has_against = bool(g.in_edges(wd, "ARGUES_AGAINST"))
    review = {}
    for n, cls, others, _ in unexplained:
        for o in others:
            if o == wd:
                continue                                  # 현재 진단 자신은 추가 검토 후보가 아님(하위 개념 확인은 판단 불가 목록)
            if cls == "NARROWER_CONCEPT_LINKED":
                review.setdefault(o, []).append(f"근거 {n} 의 하위 개념이 연결됨(하위 개념 확인 필요)")
            else:
                review.setdefault(o, []).append(f"현재 진단으로 설명 부족한 근거 {n} 을(를) 설명")
    for x in inf.ranking():
        if x.disease == wd:
            continue
        if x.n_clinical > de.n_clinical:
            review.setdefault(x.disease, []).append(f"임상 소견 근거 묶음 {x.n_clinical} > 현재 진단 {de.n_clinical}")
        elif x.n_support > de.n_support:
            review.setdefault(x.disease, []).append(
                f"독립 지지 묶음 {x.n_support} > 현재 진단 {de.n_support}"
                + (f"(차이는 공출현만 있는 묶음 포함, 임상 소견 묶음 {x.n_clinical} vs {de.n_clinical})"
                   if x.n_cooccurrence_only else ""))
    if conflicting:
        for x in inf.ranking():
            if x.disease != wd and x.n_support > 0:
                review.setdefault(x.disease, []).append("현재 진단에 명시적 충돌 근거가 있어 대안 검토")
    for e in g.out_edges(wd, "DIFFERENTIAL_OF"):
        review.setdefault(e.dst, []).append(f"지식원 감별 목록(현재 진단 항목에 기재): {e.source}")
    for e in g.in_edges(wd, "DIFFERENTIAL_OF"):
        review.setdefault(e.src, []).append(f"지식원 감별 목록(상대 질환 항목에 기재): {e.source}")
    tests = tuple(sorted((e.src, e.source) for e in g.in_edges(wd, "EVALUATES")))
    return WDAssessment(wd, "ASSESSED", supporting, tuple(unexplained), conflicting,
                        "CHECKED" if has_against else "NO_KNOWLEDGE", undetermined,
                        tuple((k, tuple(dict.fromkeys(v))) for k, v in sorted(review.items())),
                        inf.positive_out_of_graph, tests_available=tests)


def isa_descendants(g: MedGraph, n: str) -> set:
    """IS_A 로 n 에 도달하는 하위 개념(n 제외)."""
    seen, stack = set(), [e.src for e in g.in_edges(n, "IS_A")]
    while stack:
        c = stack.pop()
        if c not in seen:
            seen.add(c)
            stack += [e.src for e in g.in_edges(c, "IS_A")]
    return seen


def isa_closure(g: MedGraph, n: str) -> set:
    """n 과 IS_A 로 도달하는 모든 상위 개념."""
    seen, stack = set(), [n]
    while stack:
        c = stack.pop()
        if c in seen:
            continue
        seen.add(c)
        stack += [e.dst for e in g.out_edges(c, "IS_A")]
    return seen
