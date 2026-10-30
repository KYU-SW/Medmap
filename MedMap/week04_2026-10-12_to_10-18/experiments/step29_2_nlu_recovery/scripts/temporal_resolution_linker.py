"""STEP29.2 §5 시간·해소 연결(원문 근거만, 추측 금지). 과거 사건(temporality·assertion)은 바꾸지 않고 현재 상태를 별도 필드로 둔다.
 current_status ∈ {UNSPECIFIED, RESOLVED, IMPROVING, PERSISTING} · resolution = {cue_text, cue_start, cue_end, basis, strength, certainty}.

해소 단서 절(문장 분리 뒤 STEP29 절 단위, 전체 원문 오프셋):
 RES_EVAL     평가 술어(괜찮·멀쩡, 부정 없음)                        → RESOLVED · strength MODERATE · certainty POSSIBLE
 RES_HEALED   '낫다' 과거(나았·낫았) — '다·완전히·싹·거의' 동반 STRONG, 아니면 MODERATE → RESOLVED
 RES_STOPPED  멈추·멎·없어지·사라지·가라앉 과거(부정 없음)            → RESOLVED · MODERATE
 RES_NONE     '증상' 명사 + 없(부정 존재)                             → RESOLVED · STRONG · certainty PROBABLE
 IMPROVE      좋아지·나아지·줄어들(부정 없음, '다 나았' 아님 — kiwi 분석 차이로 원문 패턴도 확인) → IMPROVING(완전 해소 아님) · WEAK
 RES_PAINNEG  주어 없는 부정 통증 술어(안 아파·안 쑤셔) + 시점 대비어   → 통증류 대상만 RESOLVED · MODERATE
 단서 절 조건: 내용 명사가 시점어·상태어(ALLOWED_N)뿐(다른 부위·대상 명사가 있으면 단서 아님 — '머리는 괜찮아요' 는 그 부위의 평가형 부정) ·
   그 절에 단서 외 증상 concept mention 없음(RES_PAINNEG 의 부위 없는 통증 mention 은 단서로 흡수).
대상(문맥 연결 근거 필요):
 단서 절이 문장 안 첫 절이 아니면 → 같은 문장 앞 절들의 증상 mention · 첫 절이면 → 바로 앞 문장의 증상 mention.
 대상 조건: assertion PRESENT · is_symptom · (대상 시점 PAST 또는 대상 문장에 시점어(onset) 또는 단서 절에 시점 대비어 지금·오늘·이제·요즘·현재).
 대상이 없으면 아무것도 바꾸지 않고 context 에 기록(단서 절의 concept 없는 mention 은 문맥으로 이동 — 증상 부정 생성 안 함).
같은 concept·같은 부위 뒤 부정: 앞 mention PRESENT(PAST 또는 앞 문장) + 뒤 같은 concept 또는 같은 부위 명사의 ABSENT/평가형 부정 + 뒤 절 시점 대비어
 → 앞 mention RESOLVED(SAME_CONCEPT_LATER_ABSENT / SAME_SITE_LATER_NORMAL, MODERATE). 뒤 mention 은 현재 ABSENT 그대로 유지.
단위 안 개선: '속쓰림은 나아졌어요' → IMPROVING · '기침은 다 나았어요' → RESOLVED(IMPROVEMENT_IN_UNIT / HEALED_IN_UNIT).
개선 부정(STEP29.1 NEGATED_IMPROVEMENT, '열이 안 내려요') → PERSISTING."""
from __future__ import annotations

import re

import s292_common  # noqa: F401  (경로)
from evaluative_negation import NEGW, eval_predicate
from extract_symptom_spans import kiwi

POS = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "EXISTING_SUBTYPE", "NEW_ONTOLOGY_CANDIDATE")
ALLOWED_N = {"어제", "오늘", "지금", "이제", "그제", "그저께", "아까", "몸", "상태", "컨디션", "증상", "그거", "그것", "그건", "저", "제", "나", "좀", "많이", "다", "거의",
             "요즘", "현재", "아침", "저녁", "밤", "주", "일", "지난주", "어젯밤", "조금", "완전", "전부", "이번", "며칠", "요새"}
CONTRAST = re.compile(r"(지금|오늘|이제|요즘|요새|현재)")
PAIN_LIKE = {"pain", "sore_throat", "heartburn", "EV:E_38", "EV:E_205", "EV:E_144", "EV:E_9", "EV:E_206", "EV:E_175", "EV:E_14"}
PAIN_PRED = re.compile(r"(아프|아파|아팠|쑤시|쑤셔|결리|결려|욱신|따가|따갑|쓰리|쓰려)")
HEAL_STRONG = {"다", "완전히", "싹", "거의", "전부", "완전"}
IMPROVE_V = ("좋아지", "나아지", "줄어들", "덜하")
STOP_V = ("멈추", "멎", "없어지", "사라지", "가라앉")


def _neg_near(toks, k):
    return any((t.form, t.tag) in NEGW for t in toks[max(0, k - 2):k] + toks[k + 1:k + 3])


def cue_of(cl) -> dict | None:
    """절이 해소 단서인지와 종류·강도(명사 조건은 호출자가 확인)."""
    toks = cl["tokens"]
    forms = [t.form for t in toks]
    i = eval_predicate(toks)
    if i is not None and not _neg_near(toks, i):
        return {"kind": "RES_EVAL", "status": "RESOLVED", "strength": "MODERATE"}
    txt = cl["text"]
    negtxt = bool(re.search(r"(안\s|않|못\s)", txt))
    if not negtxt:   # kiwi 가 '좋아지' 를 좋(VA)+아+지(VX) 로 나누므로 원문 패턴으로도 확인
        if re.search(r"(좋아지|좋아졌|나아지|나아졌|줄어들|줄었|덜해)", txt):
            return {"kind": "IMPROVE", "status": "IMPROVING", "strength": "WEAK"}
        if re.search(r"(멈췄|멈추었|멎었|없어졌|사라졌|가라앉았)", txt):
            return {"kind": "RES_STOPPED", "status": "RESOLVED", "strength": "MODERATE"}
    for k, t in enumerate(toks):
        if t.tag.startswith("VV") and (t.form in ("낫", "낳") or t.form.startswith("나았")) and not _neg_near(toks, k):
            return {"kind": "RES_HEALED", "status": "RESOLVED", "strength": "STRONG" if HEAL_STRONG & set(forms[:k]) else "MODERATE"}
        if t.tag.startswith("VV") and t.form.startswith(STOP_V) and not _neg_near(toks, k):
            return {"kind": "RES_STOPPED", "status": "RESOLVED", "strength": "MODERATE"}
        if t.tag.startswith("VV") and t.form.startswith(IMPROVE_V) and not _neg_near(toks, k):
            return {"kind": "IMPROVE", "status": "IMPROVING", "strength": "WEAK"}
    if "증상" in forms and any(t.form == "없" and t.tag.startswith("VA") for t in toks):
        return {"kind": "RES_NONE", "status": "RESOLVED", "strength": "STRONG"}
    if PAIN_PRED.search(cl["text"]) and any((t.form, t.tag) in (("안", "MAG"),) or (t.form == "않" and t.tag == "VX") for t in toks):
        return {"kind": "RES_PAINNEG", "status": "RESOLVED", "strength": "MODERATE"}
    return None


def _nouns(toks):
    return [t.form for t in toks if (t.tag.startswith("NN") and t.tag != "NNB") or t.tag == "NP"]


def _site(m):
    toks = kiwi().tokenize(m.get("unit_text") or m["raw_span"])
    ns = [t.form for t in toks if t.tag.startswith("NN") and t.tag != "NNB"]
    return ns[0] if ns else None


def apply(text: str, mentions: list[dict], clauses: list[dict]) -> tuple[list[dict], list[dict]]:
    def in_cl(m, cl):
        return cl["start"] <= m["span_start"] < cl["end"]

    for m in mentions:
        m.setdefault("current_status", "UNSPECIFIED")
        if "NEGATED_IMPROVEMENT" in str(m.get("assertion_basis")):
            m["current_status"] = "PERSISTING"
    ctx = []
    cues = {}
    for ci, cl in enumerate(clauses):
        if cl["kind"] != "NORMAL":
            continue
        c = cue_of(cl)
        if not c:
            continue
        if not all(n in ALLOWED_N for n in _nouns(cl["tokens"])):
            continue
        cms = [m for m in mentions if in_cl(m, cl) and m["status"] in POS]
        if c["kind"] == "RES_PAINNEG":
            if any(m.get("canonical_id") not in PAIN_LIKE for m in cms):
                continue
        elif cms:
            continue
        cues[ci] = c
    keep = []
    for m in mentions:
        ci = next((i for i, cl in enumerate(clauses) if in_cl(m, cl)), None)
        if ci in cues and (m["status"] not in POS or cues[ci]["kind"] == "RES_PAINNEG"):
            m["_cue_clause"] = ci
        keep.append(m)
    absorbed = set()
    for ci in sorted(cues):
        cl, c = clauses[ci], cues[ci]
        same = [i for i in range(ci - 1, -1, -1) if clauses[i]["sentence_index"] == cl["sentence_index"] and clauses[i]["kind"] == "NORMAL"]
        if same:
            tcls, basis = same, "SAME_SENTENCE_PREV_CLAUSES"
        else:
            tcls = [i for i in range(ci - 1, -1, -1) if clauses[i]["sentence_index"] == cl["sentence_index"] - 1]
            basis = "PREV_SENTENCE"
        contrast = bool(CONTRAST.search(cl["text"]))
        tg = []
        for m in keep:
            if m.get("_cue_clause") is not None:
                continue
            if not any(in_cl(m, clauses[i]) for i in tcls):
                continue
            if not (m.get("is_symptom") and m["status"] != "NON_SYMPTOM" and m["assertion"] == "PRESENT"):
                continue
            if not (m.get("temporality") == "PAST" or m.get("onset_text") or contrast):
                continue
            if c["kind"] == "RES_PAINNEG" and not (m.get("canonical_id") in PAIN_LIKE or PAIN_PRED.search(m.get("unit_text") or "")):
                continue
            tg.append(m)
        if not tg:
            ctx.append({"resolution_cue_without_target": cl["text"], "start": cl["start"], "kind": c["kind"]})
            continue
        absorbed.add(ci)
        for m in tg:
            m["current_status"] = c["status"]
            m["resolution"] = {"cue_text": cl["text"], "cue_start": cl["start"], "cue_end": cl["end"], "basis": basis, "cue_kind": c["kind"], "strength": c["strength"],
                               "certainty": "PROBABLE" if c["strength"] == "STRONG" else "POSSIBLE"}
    out = []
    for m in keep:
        ci = m.pop("_cue_clause", None)
        if ci is not None and (m["status"] not in POS or ci in absorbed):
            ctx.append({"dropped_mention_as_context": m["raw_span"], "start": m["span_start"], "reason": "RESOLUTION_CUE_CLAUSE"})
            continue
        out.append(m)
    # 같은 concept·부위 뒤 부정 → 앞 mention 해소
    for ai, a in enumerate(out):
        if not (a.get("is_symptom") and a["assertion"] == "PRESENT" and a["current_status"] == "UNSPECIFIED"):
            continue
        for b in out[ai + 1:]:
            if b["assertion"] not in ("ABSENT",) or b.get("sentence_index", 0) == a.get("sentence_index", 0) and a.get("temporality") != "PAST":
                continue
            if not CONTRAST.search(b.get("unit_text") or b["raw_span"]) and a.get("temporality") != "PAST":
                continue
            ca, cb = a.get("canonical_id") or a.get("ontology_id"), b.get("canonical_id") or b.get("ontology_id")
            same_c = ca and ca == cb
            same_s = _site(a) and _site(a) == _site(b) and (cb is None or cb == ca)
            if same_c or same_s:
                a["current_status"] = "RESOLVED"
                a["resolution"] = {"cue_text": b["raw_span"], "cue_start": b["span_start"], "cue_end": b["span_end"],
                                   "basis": "SAME_CONCEPT_LATER_ABSENT" if same_c else "SAME_SITE_LATER_NORMAL", "cue_kind": "LATER_ABSENT", "strength": "MODERATE",
                                   "certainty": "POSSIBLE"}
                break
    # 단위 안 개선·치유
    for m in out:
        if m["status"] in POS and m["assertion"] == "PRESENT" and m["current_status"] == "UNSPECIFIED":
            toks = kiwi().tokenize(m.get("unit_text") or m["raw_span"])
            ut = m.get("unit_text") or m["raw_span"]
            if not re.search(r"(안\s|않|못\s)", ut) and re.search(r"(좋아지|좋아졌|나아지|나아졌|줄어들|줄었)", ut):
                m.update(current_status="IMPROVING", resolution={"cue_text": ut, "basis": "IMPROVEMENT_IN_UNIT", "cue_kind": "IMPROVE", "strength": "WEAK",
                                                                "certainty": "POSSIBLE"})
                continue
            for k, t in enumerate(toks):
                if t.tag.startswith("VV") and t.form.startswith(IMPROVE_V) and not _neg_near(toks, k):
                    m.update(current_status="IMPROVING", resolution={"cue_text": m.get("unit_text"), "basis": "IMPROVEMENT_IN_UNIT", "cue_kind": "IMPROVE",
                                                                    "strength": "WEAK", "certainty": "POSSIBLE"})
                    break
                if t.tag.startswith("VV") and (t.form in ("낫",) or t.form.startswith(STOP_V)) and not _neg_near(toks, k):
                    m.update(current_status="RESOLVED", resolution={"cue_text": m.get("unit_text"), "basis": "HEALED_IN_UNIT", "cue_kind": "RES_HEALED",
                                                                   "strength": "MODERATE", "certainty": "POSSIBLE"})
                    break
    return out, ctx
