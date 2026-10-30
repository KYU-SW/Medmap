"""STEP29.2 채점(새 합성 세트 DEV/HOLDOUT 공용, 평가 전 고정). NLU 출력 스키마 차이는 view 함수로만 맞춘다(정답은 바꾸지 않음).

view(정책 간 같은 기준):
 assertion_view : ABSENT + assertion_certainty LOW → 'ABSENT_LOW'(정답 ABSENT 에도 일치로 인정 — 더 보수적인 부정), 그 외 assertion 그대로
 event_view     : temporality(사건 시점). 이전 정책(STEP29·29.1)은 해소를 temporality=RESOLVED 로 덮어썼으므로 RESOLVED → 'PAST' 로 본다
 status_view    : current_status(STEP29.2 필드), 없으면 temporality=RESOLVED → 'RESOLVED', 그 외 'UNSPECIFIED'
 concept_view   : EXISTING_* → canonical_id · NEW/SUBTYPE → ontology_id(없으면 canonical_id) · 그 외 None
정렬: 정답 mention 순서대로, 아직 안 쓴 시스템 mention(NON_SYMPTOM 제외) 중 raw_span 이 anchor 포함 → unit_text 가 anchor 포함 → concept 이 concept_any 안인 EXISTING.
오류 종류: NOT_EXTRACTED(optional 제외) · WRONG_CONCEPT · FORBIDDEN_CONCEPT · ASSERTION · TEMPORALITY · CURRENT_STATUS · EXPERIENCER ·
 UNEXPECTED_SYMPTOM(no_symptom_mentions) · SYMPTOM_NEGATION_CREATED(no_symptom_negation: 증상 mention ABSENT 생성) · MODEL_POSITIVE_FORBIDDEN(no_model_positive) ·
 EXISTING_LINK_FORBIDDEN(no_existing_link) · EXTRA_WRONG_CONCEPT(정답 concept 합집합 밖 EXISTING mention).
안전 표시: PROPAGATION(정답 safety SCOPE 또는 사건 보존 대상 PRESENT 인데 ABSENT·ABSENT_LOW) · NEG_POSITIVE(정답 NEG 인데 모델 POSITIVE) · OTHER_POSITIVE(정답 OTHER 인데 PATIENT·eligible POSITIVE)."""
from __future__ import annotations

EXISTING = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")
POS = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "EXISTING_SUBTYPE", "NEW_ONTOLOGY_CANDIDATE")
PRESERVE_CATS = ("RESOLUTION", "TEMPORAL_CONTROL")


def assertion_view(m):
    if m.get("assertion") == "ABSENT" and m.get("assertion_certainty") == "LOW":
        return "ABSENT_LOW"
    return m.get("assertion")


def event_view(m):
    t = m.get("temporality")
    return "PAST" if t == "RESOLVED" else t


def status_view(m):
    if m.get("current_status"):
        return m["current_status"]
    return "RESOLVED" if m.get("temporality") == "RESOLVED" else "UNSPECIFIED"


def concept_view(m):
    if m.get("status") in EXISTING:
        return m.get("canonical_id")
    if m.get("status") in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE"):
        return m.get("ontology_id") or m.get("canonical_id")
    return None


def a_ok(m, want):
    a = assertion_view(m)
    return a in want or (a == "ABSENT_LOW" and "ABSENT" in want)


def align(case, ms):
    cand = [i for i, m in enumerate(ms) if m.get("status") != "NON_SYMPTOM"]
    used, pairs = set(), []
    for g in case["mentions"]:
        idx = next((i for i in cand if i not in used and g["anchor"] in (ms[i].get("raw_span") or "")), None)
        if idx is None:
            idx = next((i for i in cand if i not in used and g["anchor"] in (ms[i].get("unit_text") or "")), None)
        if idx is None:
            idx = next((i for i in cand if i not in used and ms[i].get("status") in EXISTING and ms[i].get("canonical_id") in g["concept_any"]), None)
        if idx is not None:
            used.add(idx)
        pairs.append((g, idx))
    return pairs


def check(case: dict, out: dict) -> list[dict]:
    ms = out["mentions"]
    errs = []
    union = {c for g in case["mentions"] for c in g["concept_any"] if c}
    for g, idx in align(case, ms):
        if idx is None:
            if not g.get("optional"):
                errs.append({"type": "NOT_EXTRACTED", "anchor": g["anchor"]})
            continue
        m = ms[idx]
        c = concept_view(m)
        ok_c = c in g["concept_any"] or (m.get("status") not in EXISTING and None in g["concept_any"]) or \
            (m.get("status") == "EXISTING_SUBTYPE" and m.get("canonical_id") in g["concept_any"])
        if not ok_c:
            errs.append({"type": "WRONG_CONCEPT", "anchor": g["anchor"], "got": c, "status": m.get("status")})
        if m.get("status") in EXISTING and c in (g.get("forbid") or []):
            errs.append({"type": "FORBIDDEN_CONCEPT", "anchor": g["anchor"], "got": c})
        if not a_ok(m, g["assertion_any"]):
            prop = "PRESENT" in g["assertion_any"] and assertion_view(m) in ("ABSENT", "ABSENT_LOW") and \
                (g.get("safety") == "SCOPE" or case.get("category") in PRESERVE_CATS)
            neg_pos = g.get("safety") == "NEG" and m.get("assertion") == "PRESENT" and (m.get("model_input") or {}).get("polarity") == "POSITIVE"
            errs.append({"type": "ASSERTION", "anchor": g["anchor"], "got": assertion_view(m), "want": g["assertion_any"], "propagation": prop, "unsafe": neg_pos})
        if g.get("temporality_any") and event_view(m) not in g["temporality_any"]:
            errs.append({"type": "TEMPORALITY", "anchor": g["anchor"], "got": event_view(m), "want": g["temporality_any"]})
        if g.get("current_status_any") and status_view(m) not in g["current_status_any"]:
            errs.append({"type": "CURRENT_STATUS", "anchor": g["anchor"], "got": status_view(m), "want": g["current_status_any"]})
        if m.get("experiencer") not in g["experiencer_any"]:
            mi = m.get("model_input") or {}
            errs.append({"type": "EXPERIENCER", "anchor": g["anchor"], "got": m.get("experiencer"), "want": g["experiencer_any"],
                         "unsafe": g.get("safety") == "OTHER" and m.get("experiencer") == "PATIENT" and bool(mi.get("eligible")) and mi.get("polarity") == "POSITIVE"})
    sym = [m for m in ms if m.get("status") in POS]
    if case.get("no_symptom_mentions") and sym:
        errs.append({"type": "UNEXPECTED_SYMPTOM", "got": [concept_view(m) for m in sym]})
    if case.get("no_symptom_negation"):
        neg = [m["raw_span"] for m in ms if m.get("is_symptom") and m.get("status") != "NON_SYMPTOM" and m.get("assertion") == "ABSENT"]
        if neg:
            errs.append({"type": "SYMPTOM_NEGATION_CREATED", "got": neg})
    if case.get("no_model_positive"):
        pos = [m["raw_span"] for m in ms if (m.get("model_input") or {}).get("eligible") and m["model_input"].get("polarity") == "POSITIVE"]
        if pos:
            errs.append({"type": "MODEL_POSITIVE_FORBIDDEN", "got": pos})
    if case.get("no_existing_link"):
        ex = [m.get("canonical_id") for m in ms if m.get("status") in EXISTING]
        if ex:
            errs.append({"type": "EXISTING_LINK_FORBIDDEN", "got": ex})
    for m in ms:
        if m.get("status") in EXISTING and m.get("canonical_id") not in union and not case.get("no_existing_link"):
            errs.append({"type": "EXTRA_WRONG_CONCEPT", "got": f"{m.get('canonical_id')}|{m.get('raw_span')}"})
    return errs


def signature(out: dict) -> list:
    """마침표 쌍 비교용 구조 요약(오프셋 제외). NON_SYMPTOM 제외."""
    return sorted((str(concept_view(m)), str(m.get("status") if concept_view(m) is None else "C"), str(assertion_view(m)), str(event_view(m)),
                   str(status_view(m)), str(m.get("experiencer"))) for m in out["mentions"] if m.get("status") != "NON_SYMPTOM")
