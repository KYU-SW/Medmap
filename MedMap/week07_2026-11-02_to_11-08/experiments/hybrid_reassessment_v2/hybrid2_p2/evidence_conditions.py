"""P2 호환 계층: (1) 임상 맥락 값의 출처 구분, (2) D-dimer 검사 조건, (3) 진단 가설의 대상 에피소드·시점 확인.
공통 스키마(hybrid.schema)는 수정하지 않는다. 민감도·확률·기준값을 만들지 않는다. 확인 안 되면 None(=부족 맥락)."""
from __future__ import annotations

import re

from . import clinical_context as CC

CLINICAL, SYNTHETIC = "CLINICAL", "SYNTHETIC_ASSUMPTION"
MODES = {CLINICAL, SYNTHETIC}
RECORD, PHYSICIAN, PATIENT, ASSUMED, UNSPECIFIED, NONE = "RECORD", "PHYSICIAN_CONFIRMED", "PATIENT_REPORTED", "SYNTHETIC_ASSUMPTION", "UNSPECIFIED_SOURCE", "NOT_AVAILABLE"
SOURCES = {RECORD, PHYSICIAN, PATIENT, ASSUMED}
GATED = ("suspected", "pretest", "clinical_phase", "ddimer_assay", "ddimer_cutoff")   # 방향 판단 조건이 되는 값
UNKNOWN_VALUES = {None, "UNKNOWN", "UNKNOWN_CONTEXT", ""}

HIGH, MODERATE, POC = "HIGH_SENSITIVITY", "MODERATE_SENSITIVITY", "POINT_OF_CARE"
FIXED, AGE, YEARS, STATED = "FIXED", "AGE_ADJUSTED", "YEARS", "STATED_REFERENCE"
R_DD = re.compile(r"\bd-?\s?dimers?\b", re.I)
R_HIGH = re.compile(r"\b(?:ELISA(?:-derived)?|highly sensitive)\b", re.I)          # ESC §4.4: ELISA·ELISA 유래 민감도 ≥95%
R_MODERATE = re.compile(r"\bmoderately sensitive\b", re.I)
R_AGE = re.compile(r"\bage[- ]adjusted\b", re.I)
R_YEARS = re.compile(r"\bYEARS\b")                                                   # 대문자 규칙명만
R_FIXED = re.compile(r"\bfixed (?:cut-?off|threshold)\b", re.I)
R_STATED = re.compile(r"\b(?:cut-?off|threshold)\b|\breference (?:range|value|limit)\b|<\s*\d", re.I)
NEAR = 60


def normalize_context(ctx: dict) -> dict:
    """입력 맥락 → 판단에 쓸 값. 값은 {'value', 'source'} 또는 단일 값(출처 미지정).
    CLINICAL(기본): RECORD·PHYSICIAN_CONFIRMED 만 사용. SYNTHETIC_ASSUMPTION: 가정·출처 미지정 값도 사용하되 표시.
    환자 보고 값은 임상 확률·의심 여부·검사 조건으로 쓰지 않는다."""
    mode = ctx.get("mode", CLINICAL)
    if mode not in MODES:
        raise ValueError(f"알 수 없는 mode: {mode}")
    values = {k: v for k, v in ctx.items() if k not in GATED and k != "mode"}
    prov, assumed = {}, []
    for k in GATED:
        raw = ctx.get(k)
        val, src = (raw.get("value"), raw.get("source", UNSPECIFIED)) if isinstance(raw, dict) else (raw, UNSPECIFIED if raw not in UNKNOWN_VALUES else NONE)
        if src not in SOURCES | {UNSPECIFIED, NONE}:
            raise ValueError(f"{k}: 알 수 없는 출처 {src}")
        if val in UNKNOWN_VALUES:
            val, src = None, NONE
        used = val is not None and (src in (RECORD, PHYSICIAN) or (mode == SYNTHETIC and src in (ASSUMED, UNSPECIFIED)))
        values[k] = val if used else None
        prov[k] = {"value": val, "source": src, "used": used}
        if used and src in (ASSUMED, UNSPECIFIED):
            assumed.append(k)
    return {"mode": mode, "values": values, "provenance": prov, "assumed_keys": assumed}


def _near(sentence: str, pat: re.Pattern) -> bool:
    return any(abs(m.start() - d.start()) <= NEAR for m in pat.finditer(sentence) for d in R_DD.finditer(sentence))


def ddimer_conditions(sentence: str, ctx: dict) -> dict:
    """문장(D-dimer 언급 주변) 우선, 없으면 출처가 인정된 입력값. 검사 수치로 검사법을 추정하지 않는다."""
    assay = POC if CC.R_POC.search(sentence) else HIGH if _near(sentence, R_HIGH) else MODERATE if _near(sentence, R_MODERATE) else None
    cutoff = AGE if _near(sentence, R_AGE) else YEARS if _near(sentence, R_YEARS) else FIXED if _near(sentence, R_FIXED) else STATED if _near(sentence, R_STATED) else None
    return {"assay": assay or ctx.get("ddimer_assay"), "assay_basis": "SENTENCE_TEXT" if assay else "INPUT_CONTEXT" if ctx.get("ddimer_assay") else "NOT_STATED",
            "cutoff": cutoff or ctx.get("ddimer_cutoff"), "cutoff_basis": "SENTENCE_TEXT" if cutoff else "INPUT_CONTEXT" if ctx.get("ddimer_cutoff") else "NOT_STATED"}


def target_check(ctx: dict, phase: str) -> dict:
    """가설 대상(hypothesis_target): {'diagnosis_episode_id', 'kind', 'hypothesis_target_time'}.
    kind: CURRENT_EVALUATION(현재 의심 평가) / PAST_EPISODE(과거 에피소드가 실제 있었나) / RECURRENCE(현재 새 PE·재발).
    반환 phase(필요 시 대체), result(None 이면 관계 적용 계속)."""
    t = ctx.get("hypothesis_target")
    if not t:
        return {"phase": phase, "result": None}
    kind, obs = t.get("kind"), ctx.get("evidence_observed_at")
    if kind not in ("CURRENT_EVALUATION", "PAST_EPISODE", "RECURRENCE"):
        raise ValueError(f"알 수 없는 hypothesis_target.kind: {kind}")
    if kind == "RECURRENCE" and phase in (CC.SUSPECTED, CC.UNKNOWN):
        return {"phase": CC.RECURRENCE, "result": None}
    if kind == "PAST_EPISODE":
        tt = t.get("hypothesis_target_time")
        if obs is None or tt is None:
            return {"phase": phase, "result": {"direction": "INSUFFICIENT_EVIDENCE", "note": "대상 에피소드와 근거의 관찰 시점을 연결할 수 없음",
                                              "missing_context": [k for k, v in (("evidence_observed_at", obs), ("hypothesis_target_time", tt)) if v is None]}}
        if obs > tt:
            return {"phase": phase, "result": {"direction": "NOT_APPLICABLE", "note": "대상 에피소드 판단 시점 이후 관찰된 결과는 그 에피소드 진단을 재판정하지 않음", "missing_context": []}}
    return {"phase": phase, "result": None}
