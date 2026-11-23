"""네 접근과 기존 엔진 기준선의 공통 Reasoner 계약. 지식·규칙이 없으면 기권한다(임시 추론 금지).

- BaselineEngineAdapter: EXP-03 reassess.relation 을 그대로 호출(수정 없음, 기준선)
- GraphReasoner(B): EXP-01b 실제 그래프의 SUGGESTS 경로만. 그래프에 약화 간선이 없어 WEAKEN 을 낼 수 없음
- RulesReasoner(A): 규칙 등록부. 현재 등록 규칙 = EXP-03 R1~R5(시스템 정의, 임상 검증 아님)만
- LLMReasoner(C): 클라이언트 주입식. 기본 비활성. 제한 자료는 외부 전송 불가
- HybridReasoner(D): 위 구성요소 조합. 임의 가중치 없음, 충돌은 UNCERTAIN
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .schema import (Citation, DataClass, Effect, EvidenceKind, OutcomeStatus, Polarity, ReasonerInput, ReasonerOutput, abstain, not_implemented)
from .temporal import leakage_violations

EXP = Path(os.environ.get("HYBRID_EXP_ROOT") or Path(__file__).resolve().parents[2])
_EXP03 = EXP / "exp03_reassessment"


def _ra():
    if str(_EXP03) not in sys.path:
        sys.path.insert(0, str(_EXP03))
    import reassess
    return reassess


def _guard(inp: ReasonerInput, name: str) -> ReasonerOutput | None:
    if leakage_violations(inp):
        return abstain(inp.item_id, name, "TEMPORAL_INPUT_VIOLATION")
    if not inp.hypothesis.usable_as_hypothesis():
        return abstain(inp.item_id, name, "HYPOTHESIS_NOT_USABLE")
    return None


def _engine_status(e) -> str:
    return {Polarity.PRESENT: "POSITIVE", Polarity.ABSENT: "NEGATIVE"}.get(e.polarity, "NOT_ASSESSABLE")


_ENGINE_TYPE = {EvidenceKind.SYMPTOM: "SYMPTOM", EvidenceKind.SIGN: "SYMPTOM", EvidenceKind.VITAL: "VITAL", EvidenceKind.LAB: "LAB",
                EvidenceKind.IMAGING_REPORT: "IMAGING_REPORT"}


def _to_engine(inp: ReasonerInput, pe_class: str = ""):
    ra = _ra()
    e = inp.evidence
    t = e.available_at if e.available_at is not None else 0.0
    return ra.Evidence(e.evidence_id, inp.case_id, _ENGINE_TYPE[e.kind], e.provenance.source_type, e.provenance.source_ref, e.observed_at, e.recorded_at, t,
                       _engine_status(e), concept=e.concept_id, pe_class=pe_class)


class BaselineEngineAdapter:
    """기존 엔진 그대로. 진단 개념·증거 개념이 이미 엔진 어휘에 있을 때만 답한다. 자유 문장을 해석하지 않는다."""
    name = "E0_EXISTING_ENGINE"

    def assess(self, inp: ReasonerInput) -> ReasonerOutput:
        g = _guard(inp, self.name)
        if g:
            return g
        e = inp.evidence
        if not inp.hypothesis.concept_id:
            return abstain(inp.item_id, self.name, "HYPOTHESIS_NOT_IN_ENGINE_VOCABULARY")
        if e.kind not in _ENGINE_TYPE:
            return abstain(inp.item_id, self.name, "EVIDENCE_KIND_NOT_SUPPORTED")
        if e.kind == EvidenceKind.IMAGING_REPORT:
            from ct_bridge import classify
            ev = _to_engine(inp, classify(e.text, "v3b")[0])
        else:
            if not e.concept_id:
                return abstain(inp.item_id, self.name, "EVIDENCE_NOT_MAPPED")
            ev = _to_engine(inp)
        rel, rule = _ra().relation(ev, inp.hypothesis.concept_id)
        mapped = {"SUPPORTS": Effect.SUPPORT, "CONFLICTS": Effect.CONTRADICTION, "NOT_CONFIRM_ACUTE": Effect.UNCERTAIN, "UNKNOWN": Effect.UNCERTAIN,
                  "NO_EFFECT": Effect.NO_CLEAR_EFFECT}.get(rel)
        if mapped is None:
            return abstain(inp.item_id, self.name, f"ENGINE_{rel}", (rule,))
        return ReasonerOutput(inp.item_id, self.name, OutcomeStatus.ANSWERED, mapped, reason_code=f"ENGINE_{rule}",
                              citations=(Citation("RULE", f"EXP-03:{rule}"), Citation("INPUT_EVIDENCE", e.provenance.source_ref, e.text)),
                              used_evidence_ids=(e.evidence_id,), flags=("NOT_CLINICALLY_VALIDATED",))


class GraphReasoner:
    """B. EXP-01b 그래프 SUGGESTS 경로만 사용. 동시 출현 수준 간선이 섞여 있어 SUPPORT 는 '관계 있음' 수준, 약화 판단 불가."""
    name = "B_GRAPH"

    def assess(self, inp: ReasonerInput) -> ReasonerOutput:
        g = _guard(inp, self.name)
        if g:
            return g
        e = inp.evidence
        if not inp.hypothesis.concept_id or not e.concept_id:
            return abstain(inp.item_id, self.name, "NOT_MAPPED_TO_GRAPH")
        gr = _ra().graph()
        edge = [x for x in gr.out_edges(e.concept_id, "SUGGESTS") if x.dst == inp.hypothesis.concept_id] if e.concept_id in gr.nodes else []
        if not edge:
            return abstain(inp.item_id, self.name, "NO_GRAPH_PATH")
        if e.polarity != Polarity.PRESENT:
            return abstain(inp.item_id, self.name, "NEGATIVE_OR_UNKNOWN_NOT_DEFINED_IN_GRAPH")
        return ReasonerOutput(inp.item_id, self.name, OutcomeStatus.ANSWERED, Effect.SUPPORT, reason_code="GRAPH_SUGGESTS",
                              citations=(Citation("KNOWLEDGE", f"{e.concept_id}->{inp.hypothesis.concept_id}", str(edge[0].source)[:120]),
                                         Citation("INPUT_EVIDENCE", e.provenance.source_ref, e.text)),
                              used_evidence_ids=(e.evidence_id,), flags=("GRAPH_ASSOCIATION_NOT_CAUSAL",))


@dataclass(frozen=True)
class RegisteredRule:
    rule_id: str
    validation_status: str                  # GUIDELINE_VERIFIED·SYSTEM_DEFINED·PROPOSED
    source: str


class RulesReasoner:
    """A. 등록된 규칙만 실행. 현재 등록 = EXP-03 영상 규칙(시스템 정의). PE·영상 밖은 기권. 임의 규칙 추가 금지."""
    name = "A_RULES"
    REGISTRY = {r.rule_id: r for r in (RegisteredRule("EXP03-R1", "SYSTEM_DEFINED", "EXP-03 PROTOCOL §4"), RegisteredRule("EXP03-R2", "SYSTEM_DEFINED", "EXP-03 PROTOCOL §4"),
                                       RegisteredRule("EXP03-R3", "SYSTEM_DEFINED", "EXP-03 PROTOCOL §4"), RegisteredRule("EXP03-R4", "SYSTEM_DEFINED", "EXP-03 PROTOCOL §4"),
                                       RegisteredRule("EXP03-R5", "SYSTEM_DEFINED", "EXP-03 PROTOCOL §4"))}

    def assess(self, inp: ReasonerInput) -> ReasonerOutput:
        g = _guard(inp, self.name)
        if g:
            return g
        e = inp.evidence
        if e.kind != EvidenceKind.IMAGING_REPORT or inp.hypothesis.concept_id != _ra().PE:
            return abstain(inp.item_id, self.name, "NO_REGISTERED_RULE")
        from ct_bridge import classify
        rel, rule = _ra().relation(_to_engine(inp, classify(e.text, "v3b")[0]), inp.hypothesis.concept_id)
        eff = {"SUPPORTS": Effect.SUPPORT, "CONFLICTS": Effect.CONTRADICTION, "NOT_CONFIRM_ACUTE": Effect.UNCERTAIN, "UNKNOWN": Effect.UNCERTAIN}.get(rel)
        if eff is None:
            return abstain(inp.item_id, self.name, f"RULE_{rel}")
        r = self.REGISTRY[f"EXP03-{rule}"]
        return ReasonerOutput(inp.item_id, self.name, OutcomeStatus.ANSWERED, eff, reason_code=r.rule_id, citations=(Citation("RULE", r.rule_id, r.source), Citation("INPUT_EVIDENCE", e.provenance.source_ref, e.text)),
                              used_evidence_ids=(e.evidence_id,), flags=(r.validation_status,))


class LLMRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMPolicy:
    """기본: 호출 안 함. 제한 자료는 approved_local_runtime=True 이고 사용자·DUA 승인 기록이 있어야만 로컬 실행 가능. 외부 전송 경로 없음."""
    enabled: bool = False
    is_local_runtime: bool = False
    restricted_data_approval_ref: str = ""


class LLMReasoner:
    """C. client(prompt 구성 입력) -> dict 주입. 저장소에 실제 클라이언트 없음 → 기본 NOT_IMPLEMENTED.
    출력은 근거 문구가 입력 원문에 그대로 있을 때만 수용(자동 검증 가능한 범위)."""
    name = "C_LLM_RETRIEVAL"

    def __init__(self, client=None, policy: LLMPolicy = LLMPolicy()):
        self.client, self.policy = client, policy

    def assess(self, inp: ReasonerInput) -> ReasonerOutput:
        g = _guard(inp, self.name)
        if g:
            return g
        if not self.policy.enabled or self.client is None:
            return not_implemented(inp.item_id, self.name, "LLM_DISABLED_NO_CLIENT")
        if inp.data_class == DataClass.RESTRICTED and not (self.policy.is_local_runtime and self.policy.restricted_data_approval_ref):
            return abstain(inp.item_id, self.name, "RESTRICTED_DATA_NOT_SENT")
        raw = self.client(dict(item_id=inp.item_id, hypothesis=inp.hypothesis.diagnosis_label, evidence=inp.evidence.text, context=inp.context_summary,
                               prior=[e.text for e in inp.prior_evidence]))
        return self._validate(inp, raw)

    def _validate(self, inp: ReasonerInput, raw: dict) -> ReasonerOutput:
        try:
            eff = Effect(raw["effect"])
            grade = raw.get("grade")
            quote = raw["evidence_quote"]
            if grade is not None:
                grade = int(grade)
        except (KeyError, ValueError, TypeError):
            return abstain(inp.item_id, self.name, "LLM_OUTPUT_INVALID")
        if not quote or quote not in inp.evidence.text:
            return abstain(inp.item_id, self.name, "LLM_ATTRIBUTION_NOT_IN_INPUT")
        if grade not in (None, -2, -1, 0, 1, 2):
            return abstain(inp.item_id, self.name, "LLM_OUTPUT_INVALID")
        return ReasonerOutput(inp.item_id, self.name, OutcomeStatus.ANSWERED, eff, grade=grade, reason_code="LLM", citations=(Citation("INPUT_EVIDENCE", inp.evidence.provenance.source_ref, quote),),
                              claims=tuple(raw.get("claims", ())), used_evidence_ids=(inp.evidence.evidence_id,), flags=("LLM_UNVERIFIED",))


class HybridReasoner:
    """D. 결정 규칙은 사전 고정: 규칙 답 > (LLM·그래프 일치) > 단일 근거 + 표시, 방향 충돌은 UNCERTAIN. 가중 평균 없음."""
    name = "D_HYBRID"

    def __init__(self, rules=None, graph=None, llm=None):
        self.rules, self.graph, self.llm = rules or RulesReasoner(), graph or GraphReasoner(), llm or LLMReasoner()

    def assess(self, inp: ReasonerInput) -> ReasonerOutput:
        g = _guard(inp, self.name)
        if g:
            return g
        parts = {r.name: r.assess(inp) for r in (self.rules, self.graph, self.llm)}
        ans = {k: v for k, v in parts.items() if v.status == OutcomeStatus.ANSWERED}
        if not ans:
            return abstain(inp.item_id, self.name, "NO_COMPONENT_ANSWERED", tuple(f"{k}:{v.reason_code}" for k, v in parts.items()))
        sign = {Effect.SUPPORT: 1, Effect.WEAKEN: -1, Effect.CONTRADICTION: -1}
        dirs = {sign[v.effect] for v in ans.values() if v.effect in sign}
        cit = tuple(c for v in ans.values() for c in v.citations)
        if len(dirs) > 1:
            return ReasonerOutput(inp.item_id, self.name, OutcomeStatus.ANSWERED, Effect.UNCERTAIN, reason_code="COMPONENT_CONFLICT", citations=cit,
                                  used_evidence_ids=(inp.evidence.evidence_id,), flags=tuple(f"{k}:{v.effect.value}" for k, v in ans.items()))
        pick = parts[self.rules.name] if self.rules.name in ans else next(iter(ans.values()))
        return ReasonerOutput(inp.item_id, self.name, OutcomeStatus.ANSWERED, pick.effect, grade=pick.grade, reason_code="VIA_" + pick.reasoner, citations=cit, claims=pick.claims,
                              used_evidence_ids=(inp.evidence.evidence_id,), flags=pick.flags + tuple(f"{k}:{v.status.value}" for k, v in parts.items()))
