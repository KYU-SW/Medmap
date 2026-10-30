"""STEP29.1 P4 — 해소·시점 범위(원문 근거만, 추측 금지). 규칙(평가 전 고정):
 해소 단서 절 = 개념 있는 mention 이 없는 절 + 평가 술어(괜찮·멀쩡, 부정 없음) 또는 개선 술어(나아지·좋아지·없어지·사라지·멈추·멎·내리·가라앉, 부정 없음)
   + 내용 명사가 시점어·몸·상태·컨디션·증상·이제·지금 류뿐(다른 대상 명사 '검사 결과' 등이 있으면 해소 단서 아님)
   그런 절에서 STEP29 가 만든 개념 없는 mention 은 문맥으로 돌린다(mention 제거, context 에 기록).
 대상 = 같은 문장 바로 앞 절의 증상 mention(개념 미연결 증상 포함, 비증상 제외), 없으면(단서 절이 문장 첫 절일 때만) 바로 앞 문장 마지막 절 — assertion PRESENT 인 것만
   → temporality RESOLVED, resolution{cue_text, cue_start, cue_end, basis, certainty POSSIBLE}. 단서 절에 다른 증상이 있으면 적용 안 함.
 같은 단위 안 개선 술어(부정 없음, '속쓰림은 나아졌어요') → RESOLVED(IMPROVEMENT_IN_UNIT)
 같은 concept 이 앞에서 PAST·PRESENT, 뒤에서 ABSENT(현재) → 앞 mention RESOLVED(SAME_CONCEPT_LATER_ABSENT)
 해소 대상이 불명확(앞에 개념 mention 없음, 예 '이제 괜찮아요' 단독)하면 아무것도 바꾸지 않는다."""
from __future__ import annotations

import s291_common  # noqa: F401  (경로)

from evaluative_negation import NEGW, eval_predicate, improve_predicate

POS = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "EXISTING_SUBTYPE", "NEW_ONTOLOGY_CANDIDATE")
ALLOWED_N = {"어제", "오늘", "지금", "이제", "그제", "그저께", "아까", "몸", "상태", "컨디션", "증상", "그거", "그것", "그건", "저", "제", "나", "좀", "많이", "다", "거의", "요즘",
             "현재", "아침", "저녁", "밤", "주", "일"}


def cue_clause(cl) -> bool:
    toks = cl["tokens"]
    i = eval_predicate(toks)
    j = improve_predicate(toks) if i is None else None
    k = i if i is not None else j
    if k is None:
        return False
    if any((t.form, t.tag) in NEGW for t in toks[k + 1:k + 3]) or any((t.form, t.tag) in NEGW for t in toks[max(0, k - 2):k]):
        return False
    nouns = [t.form for t in toks if t.tag.startswith("NN") and t.tag != "NNB"] + [t.form for t in toks if t.tag == "NP"]
    return all(n in ALLOWED_N for n in nouns)


def apply(text: str, mentions: list[dict], clauses: list[dict]) -> tuple[list[dict], list[dict]]:
    def in_clause(m, cl):
        return cl["start"] <= m["span_start"] < cl["end"]
    ctx = []
    keep = []
    cue_idx = set()
    for ci, cl in enumerate(clauses):
        if cl["kind"] != "NORMAL":
            continue
        cms = [m for m in mentions if in_clause(m, cl)]
        if any(m["status"] in POS for m in cms):
            continue
        if cue_clause(cl):
            cue_idx.add(ci)
    for m in mentions:
        ci = next((i for i, cl in enumerate(clauses) if in_clause(m, cl)), None)
        if ci in cue_idx and m["status"] not in POS:
            ctx.append({"dropped_mention_as_context": m["raw_span"], "start": m["span_start"]})
            continue
        keep.append(m)
    for ci in sorted(cue_idx):
        cl = clauses[ci]
        same = [i for i in range(ci - 1, -1, -1) if clauses[i]["sentence_index"] == cl["sentence_index"] and clauses[i]["kind"] == "NORMAL"]
        tgt_cl, basis = None, None
        for i in same[:1]:
            if any(m.get("is_symptom") and m["status"] != "NON_SYMPTOM" and in_clause(m, clauses[i]) for m in keep):
                tgt_cl, basis = i, "SAME_SENTENCE_PREV_CLAUSE"
        if tgt_cl is None and not same:
            prev = [i for i in range(ci - 1, -1, -1) if clauses[i]["sentence_index"] == cl["sentence_index"] - 1 and clauses[i]["kind"] == "NORMAL"]
            for i in prev[:1]:
                if any(m.get("is_symptom") and m["status"] != "NON_SYMPTOM" and in_clause(m, clauses[i]) for m in keep):
                    tgt_cl, basis = i, "PREV_SENTENCE_LAST_CLAUSE"
        if tgt_cl is None:
            ctx.append({"resolution_cue_without_target": cl["text"], "start": cl["start"]})
            continue
        for m in keep:
            if in_clause(m, clauses[tgt_cl]) and m.get("is_symptom") and m["status"] != "NON_SYMPTOM" and m["assertion"] == "PRESENT":
                m.update(temporality="RESOLVED", resolution={"cue_text": cl["text"], "cue_start": cl["start"], "cue_end": cl["end"], "basis": basis, "certainty": "POSSIBLE"})
    for m in keep:
        if m["status"] in POS and m["assertion"] == "PRESENT" and m["temporality"] != "RESOLVED":
            from extract_symptom_spans import kiwi
            toks = kiwi().tokenize(m.get("unit_text") or m["raw_span"])
            ii = improve_predicate(toks)
            if ii is not None and not any((t.form, t.tag) in NEGW for t in toks[max(0, ii - 2):ii + 3]):
                m.update(temporality="RESOLVED", resolution={"cue_text": m.get("unit_text"), "basis": "IMPROVEMENT_IN_UNIT", "certainty": "POSSIBLE"})
    for a_i, a in enumerate(keep):
        for b in keep[a_i + 1:]:
            ca = a.get("canonical_id") or a.get("ontology_id")
            if ca and ca == (b.get("canonical_id") or b.get("ontology_id")) and a["assertion"] == "PRESENT" and a["temporality"] in ("PAST",) \
                    and b["assertion"] == "ABSENT" and b["temporality"] in ("CURRENT", "ONGOING", "UNKNOWN"):
                a.update(temporality="RESOLVED", resolution={"cue_text": b["raw_span"], "cue_start": b["span_start"], "basis": "SAME_CONCEPT_LATER_ABSENT", "certainty": "POSSIBLE"})
    return keep, ctx
