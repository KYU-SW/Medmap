"""STEP29.2 평가(연구용 엔지니어링 지표 — 임상 정확도 아님). 지표·분모·게이트는 NLU 구현 전 고정(data/prereg_gates.json, 2026-10-13).

실행: evaluate_nlu.py dev   → DEV(개발 세트) + 노출 회귀 세트, 모든 정책 — 정책 선택용(outputs/dev_policy_metrics.json)
      evaluate_nlu.py final → HOLDOUT(최초 실행) + DEV + 노출 회귀 + 약한 외부, 모든 정책 — 공식(outputs/eval_summary.json 등).
      final 은 prereg_gates.json(검사기·데이터·채점·지표 SHA)과 policy_freeze.json(정책 코드 SHA·선택 정책)이 현재 파일과 같을 때만 실행.
정책: S29 = STEP29 NLU_P5(원본) · S291 = STEP29.1 P5(원본) · V3_B0–B3 = STEP29.2 파이프라인 v3 + B4 가드 변형(B0 없음 · B1 STEP29.1 엄격 · B2 증상 근거 선택 · B3 B2+의미 충돌 보류).

[새 합성 세트 지표 — 세트(DEV/HOLDOUT)마다 따로, 합치지 않음. 분모 명시]
 RAW_PRESERVATION       입력 중 source_text 그대로 + 모든 raw_span == text[s:e]
 OFFSET_VALID           mention 중 0≤s<e≤len · raw_span 일치
 SPAN_BOUNDARY_VALIDITY 증상 mention(NON_SYMPTOM 제외) 중 정답 문장 하나 안에 있는 비율(문장 경계를 넘으면 실패)
 ASR_SENTENCE_SEGMENTATION 마침표 없는(N) 다문장 case 의 정답 내부 경계(2번째 문장부터 시작 위치) 대비 정책 문장 분할 경계 F1
                        (경계 차이 구간이 공백·채움말뿐이면 일치). S29·S291 = STEP29 clause_segmenter 문장(SF) · V3 = asr_sentence_segmenter
 MULTI_SPAN_RETENTION   정답 EXISTING concept mention ≥2 인 case 의 그 mention(optional 제외) 중 올바른 concept 의 EXISTING 로 정렬된 비율
 CONCEPT_COVERAGE       모든 case 의 정답 EXISTING concept mention(optional 제외) 중 올바른 concept EXISTING 로 정렬된 비율
 CONCEPT_PRECISION      시스템 EXISTING mention 중 그 case 정답 concept 합집합 안인 비율(정답 concept 없는 case 의 EXISTING 은 모두 오답)
 NEGATION_SCOPE         정렬된 정답 mention 중 assertion 일치
 EVALUATIVE_NEGATION    범주 EVAL_NEG case 중 오류 0 case 비율
 TEMPORALITY            정렬된 정답 mention(temporality_any 있음) 중 사건 시점 일치
 RESOLUTION_LINKING     정답 current_status 가 RESOLVED/IMPROVING 만인 mention(분모 = 정답 수, 정렬 실패 포함) 중 정렬·상태 일치·assertion PRESENT(사건 보존) 비율
 RESOLUTION_FALSE_LINK  정답 current_status 에 RESOLVED·IMPROVING 이 없는 mention 인데 시스템이 RESOLVED/IMPROVING 으로 둔 수
 EXPERIENCER            정렬된 정답 mention 중 experiencer 일치
 UNSUPPORTED_AUTO_LINK  no_existing_link case(미지원·SILVER·혼동 None) 중 EXISTING mention 이 있는 case 수 / 그 case 수
 SEMANTIC_VIOLATIONS    검사기 v6 위반이 있는 입력 수
 PUNCTUATION_PAIR_CONSISTENCY 같은 pair_id 의 P·N BASE 두 입력의 구조 요약(contract_check_v3.signature) 일치 비율
 OVER_SPLIT             SINGLE·SHORT_ASR·REPETITION 외 정답 mention 1개 case 에서 증상(POS) mention ≥2 인 case 수
 PROPAGATION_ERRORS     정답 SCOPE/사건 보존 PRESENT mention 이 ABSENT 로 된 수(부정·해소 전파) · NEG_POSITIVE · OTHER_POSITIVE(안전)
 METAMORPHIC            NEG_SCOPE(부정 추가 전후 다른 증상 요약 동일) · TEMPORAL(해소 추가 후 사건 PRESENT·과거 보존) · EXPERIENCER(타인 PATIENT 양성 0) ·
                        MULTI(모든 anchor 추출) · MODIFIER(정답 concept 유지) · UNSUP(EXISTING 0) — 각 통과 수/대상 수
 B4_GUARD_CORRECT_BLOCKS / WRONG_BLOCKS  B4 단독 가드 사유로 막힌 mention 중 막힌 concept 이 정답 합집합 밖(올바른 차단) / 안(정답 차단)
[노출 회귀 세트 — STEP29.1 evaluate_nlu 와 같은 정의, 시스템 출력은 legacy_view(current_status RESOLVED → temporality RESOLVED) 로 채점]
 pilot 274: multi_retention(분모 80) · assertion·시점·주체 일치 · wrong_concept · unsupported_auto(should_link False 28 중) · REGRESSION168 precision·coverage(분모 168)
 STEP29 계약 68 실패 수 · STEP29.1 계약 42 통과 수 · STEP29.1 전향적 231 통과 수 · B4 가드 정답/오답 차단(pilot)
[약한 외부] SILVER442 UNKNOWN·UNCERTAIN 비율 · WEAKNON903 증상 양성 입력 수
[안전 게이트 원자료] G5 = HOLDOUT PROPAGATION + NEG_POSITIVE + 노출(계약 NEG unsafe·42 MODEL_POSITIVE_FORBIDDEN·pilot absent→POSITIVE) ·
 G6 = HOLDOUT OTHER_POSITIVE + 노출(계약 OTHER unsafe·pilot 타인 PATIENT eligible) · G7 = 신규·하위·SILVER mention eligible(전 입력) · G10 = 사유 없는 UNCERTAIN/UNKNOWN
"""
from __future__ import annotations

import collections
import copy
import json
import re
import sys

import s292_common as S
from contract_check import check as check29
from contract_check import load as load29
from contract_check_v2 import check as check2
from contract_check_v3 import EXISTING, POS, a_ok, align, check, concept_view, event_view, signature, status_view
from evaluator_v6 import evaluate as v6eval
from evaluator_v6 import evaluator_sha

EXP_ASSERT = {"present": "PRESENT", "absent": "ABSENT", "uncertain": "POSSIBLE", "historical": "PRESENT"}
B4_REASONS = ("MODEL_ONLY_NO_CUE", "B4_EVIDENCE_INSUFFICIENT", "B4_SEMANTIC_CONFLICT", "B4_NON_SYMPTOM_CONTEXT")
FILL = re.compile(r"^[\s.]*(그리고|근데|음|어)?[\s.]*$")


def legacy_view(o: dict) -> dict:
    o = copy.deepcopy(o)
    for m in o["mentions"]:
        if m.get("current_status") == "RESOLVED":
            m["temporality"] = "RESOLVED"
    return o


def load_new(name):
    return json.loads((S.DATA / name).read_text(encoding="utf-8"))


def boundary_f1(cases, spans_fn):
    tp = fp = fn = 0
    for c in cases:
        if c["punct"] != "N" or c["n_gold_sentences"] < 2:
            continue
        t = c["text"]
        gold = [s for s, _ in c["gold_sentences"][1:]]
        pred = [s for s, _ in spans_fn(t)[1:]]
        used = set()
        for p in pred:
            j = next((i for i, gb in enumerate(gold) if i not in used and FILL.match(t[min(p, gb):max(p, gb)])), None)
            if j is None:
                fp += 1
            else:
                used.add(j)
                tp += 1
        fn += len(gold) - len(used)
    pr = tp / (tp + fp) if tp + fp else 1.0
    rc = tp / (tp + fn) if tp + fn else 1.0
    return {"f1": S.rnd(2 * pr * rc / (pr + rc)) if pr + rc else 0.0, "precision": S.rnd(pr), "recall": S.rnd(rc), "tp": tp, "fp": fp, "fn": fn}


def new_set_metrics(cases, outs, rel, spans_fn):
    by_id = {c["id"]: (c, o) for c, o in zip(cases, outs)}
    m = collections.Counter()
    errs = []
    sig = {}
    b4c = b4w = 0
    for c, o in zip(cases, outs):
        t = c["text"]
        m["inputs"] += 1
        m["raw_ok"] += o["source_text"] == t and all(x["raw_span"] == t[x["span_start"]:x["span_end"]] for x in o["mentions"])
        for x in o["mentions"]:
            m["mentions"] += 1
            m["offset_ok"] += isinstance(x["span_start"], int) and 0 <= x["span_start"] < x["span_end"] <= len(t) and x["raw_span"] == t[x["span_start"]:x["span_end"]]
            if x.get("status") != "NON_SYMPTOM":
                m["sym_mentions"] += 1
                m["span_in_sentence"] += any(a <= x["span_start"] and x["span_end"] <= b for a, b in c["gold_sentences"])
            if x.get("guard_blocked_concept") and any(r in B4_REASONS for r in x.get("guard_reasons") or []):
                union = {cc for g in c["mentions"] for cc in g["concept_any"] if cc}
                if x["guard_blocked_concept"] in union:
                    b4w += 1
                else:
                    b4c += 1
        es = check(c, o)
        m["cases_pass"] += not es
        m[f"cat_n:{c['category']}"] += 1
        m[f"cat_pass:{c['category']}"] += not es
        for e in es:
            m[f"err:{e['type']}"] += 1
            m["propagation"] += bool(e.get("propagation"))
            m["neg_positive"] += e["type"] == "ASSERTION" and bool(e.get("unsafe"))
            m["other_positive"] += e["type"] == "EXPERIENCER" and bool(e.get("unsafe"))
            errs.append({"id": c["id"], "category": c["category"], "text": t, **{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
                                                                                    for k, v in e.items()}})
        v6 = v6eval(o)
        m["v6_violation_inputs"] += bool(v6)
        for x in v6:
            errs.append({"id": c["id"], "category": c["category"], "text": t, "type": "V6_" + x["violation"], "got": f"{x['concept']}|{x['raw_span']}"})
        ex = [x for x in o["mentions"] if x.get("status") in EXISTING]
        union = {cc for g in c["mentions"] for cc in g["concept_any"] if cc}
        m["sys_existing"] += len(ex)
        m["sys_existing_correct"] += sum(1 for x in ex if x["canonical_id"] in union)
        req = [g for g in c["mentions"] if not g.get("optional") and any(cc for cc in g["concept_any"])]
        pairs = align(c, o["mentions"])
        for g, idx in pairs:
            x = o["mentions"][idx] if idx is not None else None
            okc = x is not None and x.get("status") in EXISTING and x.get("canonical_id") in g["concept_any"]
            if g in req:
                m["cov_n"] += 1
                m["cov_ok"] += okc
                if len(req) >= 2:
                    m["multi_n"] += 1
                    m["multi_ok"] += okc
            cs = set(g.get("current_status_any") or [])
            if cs and cs <= {"RESOLVED", "IMPROVING"}:   # 분모 = 정답 기준(정렬 실패도 실패)
                m["res_n"] += 1
                m["res_ok"] += x is not None and status_view(x) in cs and x.get("assertion") == "PRESENT"
            if x is None:
                continue
            m["aligned"] += 1
            m["neg_ok"] += a_ok(x, g["assertion_any"])
            m["exp_ok"] += x.get("experiencer") in g["experiencer_any"]
            if g.get("temporality_any"):
                m["temp_n"] += 1
                m["temp_ok"] += event_view(x) in g["temporality_any"]
            if not (cs & {"RESOLVED", "IMPROVING"}) and status_view(x) in ("RESOLVED", "IMPROVING"):
                m["res_false"] += 1
        if c.get("no_existing_link"):
            m["unsup_n"] += 1
            m["unsup_auto"] += bool(ex)
        if c["category"] not in ("SINGLE", "SHORT_ASR", "REPETITION") and len(c["mentions"]) == 1 and \
                sum(1 for x in o["mentions"] if x.get("status") in POS) >= 2:
            m["over_split"] += 1
        if c["variant"] == "BASE":
            sig.setdefault(c["pair_id"], {})[c["punct"]] = signature(o)
    pairs = [v for v in sig.values() if "P" in v and "N" in v]
    meta = collections.Counter()
    for r in rel:
        c, o = by_id[r["variant"]]
        meta[f"{r['type']}_n"] += 1
        ok = False
        if r["type"] == "NEG_SCOPE":
            cb, ob = by_id[r["base"]]
            pick = lambda oo: sorted((concept_view(x), x.get("assertion"), x.get("experiencer")) for x in oo["mentions"]  # noqa: E731
                                     if r["anchor"] in (x.get("raw_span") or "") and x.get("status") != "NON_SYMPTOM")
            ok = bool(pick(ob)) and pick(ob) == pick(o)
        elif r["type"] == "TEMPORAL":
            xs = [x for x in o["mentions"] if r["anchor"] in (x.get("raw_span") or "") and x.get("status") != "NON_SYMPTOM"]
            ok = bool(xs) and all(x.get("assertion") == "PRESENT" and event_view(x) == "PAST" for x in xs[:1])
        elif r["type"] == "EXPERIENCER":
            oth = [g for g in c["mentions"] if g.get("safety") == "OTHER"]
            ok = not any(x.get("experiencer") == "PATIENT" and (x.get("model_input") or {}).get("eligible") and x["model_input"].get("polarity") == "POSITIVE"
                         and any(g["anchor"] in (x.get("raw_span") or "") for g in oth) for x in o["mentions"])
        elif r["type"] == "MULTI":
            ok = all(any(a in (x.get("raw_span") or "") or a in (x.get("unit_text") or "") for x in o["mentions"] if x.get("status") in POS) for a in r["anchors"])
        elif r["type"] == "MODIFIER":
            ok = not check(c, o)
        elif r["type"] == "UNSUP":
            ok = not any(x.get("status") in EXISTING for x in o["mentions"])
        meta[f"{r['type']}_pass"] += ok
    f1 = boundary_f1(cases, spans_fn)
    q = lambda a, b: S.rnd(m[a] / m[b]) if m[b] else None  # noqa: E731
    res = {"n_inputs": m["inputs"], "n_mentions": m["mentions"], "RAW_PRESERVATION": q("raw_ok", "inputs"), "OFFSET_VALID": q("offset_ok", "mentions"),
           "SPAN_BOUNDARY_VALIDITY": q("span_in_sentence", "sym_mentions"), "ASR_SENTENCE_SEGMENTATION": f1,
           "MULTI_SPAN_RETENTION": q("multi_ok", "multi_n"), "multi_n": m["multi_n"], "CONCEPT_COVERAGE": q("cov_ok", "cov_n"), "coverage_n": m["cov_n"],
           "CONCEPT_PRECISION": q("sys_existing_correct", "sys_existing"), "precision_n": m["sys_existing"],
           "NEGATION_SCOPE": q("neg_ok", "aligned"), "aligned_n": m["aligned"],
           "EVALUATIVE_NEGATION": q("cat_pass:EVAL_NEG", "cat_n:EVAL_NEG"), "evaluative_n": m["cat_n:EVAL_NEG"],
           "TEMPORALITY": q("temp_ok", "temp_n"), "temporality_n": m["temp_n"], "RESOLUTION_LINKING": q("res_ok", "res_n"), "resolution_n": m["res_n"],
           "RESOLUTION_FALSE_LINK": m["res_false"], "EXPERIENCER": q("exp_ok", "aligned"),
           "UNSUPPORTED_AUTO_LINK": f"{m['unsup_auto']}/{m['unsup_n']}", "unsupported_auto": m["unsup_auto"], "unsupported_n": m["unsup_n"],
           "SEMANTIC_VIOLATIONS": m["v6_violation_inputs"], "PUNCTUATION_PAIR_CONSISTENCY": S.rnd(sum(v["P"] == v["N"] for v in pairs) / len(pairs)) if pairs else None,
           "punct_pairs_n": len(pairs), "OVER_SPLIT": m["over_split"], "PROPAGATION_ERRORS": m["propagation"], "NEG_POSITIVE": m["neg_positive"],
           "OTHER_POSITIVE": m["other_positive"], "CASE_PASS_RATE": q("cases_pass", "inputs"), "B4_GUARD_CORRECT_BLOCKS": b4c, "B4_GUARD_WRONG_BLOCKS": b4w,
           "by_category_pass": {k.split(":", 1)[1]: f"{m['cat_pass:' + k.split(':', 1)[1]]}/{m[k]}" for k in sorted(m) if k.startswith("cat_n:")},
           "errors_by_type": {k.split(":", 1)[1]: m[k] for k in sorted(m) if k.startswith("err:")},
           "metamorphic": {t: f"{meta[t + '_pass']}/{meta[t + '_n']}" for t in ("NEG_SCOPE", "TEMPORAL", "EXPERIENCER", "MULTI", "MODIFIER", "UNSUP") if meta[t + "_n"]}}
    return res, errs


def exposed_metrics(analyze_fn, policy):
    c29 = load29()["contracts"]
    cnew = json.loads((S.S291_DIR / "data/contract_cases.json").read_text(encoding="utf-8"))["contracts"]
    pros = json.loads((S.S291_DIR / "data/prospective_synthetic_cases.json").read_text(encoding="utf-8"))["contracts"]
    pilot = S.read_csv(S.S21_DIR / "data/pilot_gold.csv")
    regg = {r["text"]: r["gold_concept"] for r in S.read_csv(S.S27_DIR / "outputs/routing_features.csv") if r["set"] in ("INT_DEV_CORE", "INT_REGRESSION_CORE")}
    models = S.models()
    m = collections.Counter()
    errs = []
    raw = off = nm = ni = 0
    allm = []
    for sn, rows in (("C29", c29), ("NEW42", cnew), ("PROS231", pros)):
        for c in rows:
            o = analyze_fn(c["text"], policy)
            ni += 1
            raw += o["source_text"] == c["text"] and all(x["raw_span"] == c["text"][x["span_start"]:x["span_end"]] for x in o["mentions"])
            allm += o["mentions"]
            lo = legacy_view(o)
            es = check29(c, lo) if sn == "C29" else check2(c, lo)
            m[f"{sn}_n"] += 1
            m[f"{sn}_pass"] += not es
            for e in es:
                if sn in ("C29", "NEW42"):
                    m["g5"] += (e["type"] == "NEGATION" and bool(e.get("unsafe"))) or e["type"] == "MODEL_POSITIVE_FORBIDDEN"
                    m["g6"] += e["type"] == "EXPERIENCER" and bool(e.get("unsafe"))
                errs.append({"set": sn, "text": c["text"], "type": e["type"], "got": str(e.get("got")), "anchor": e.get("anchor")})
    pm = collections.Counter()
    b4c = b4w = 0
    for r in pilot:
        t = r["text_ko"]
        o = analyze_fn(t, policy)
        ni += 1
        raw += o["source_text"] == t and all(x["raw_span"] == t[x["span_start"]:x["span_end"]] for x in o["mentions"])
        allm += o["mentions"]
        o = legacy_view(o)
        golds = json.loads(r["gold_mentions"] or "[]")
        gm = [g for g in golds if g["concept"] in models]
        gset = {g["concept"] for g in golds}
        ex = [x for x in o["mentions"] if x["status"] in EXISTING]
        for x in o["mentions"]:
            if x.get("guard_blocked_concept") and any(rr in B4_REASONS for rr in x.get("guard_reasons") or []):
                if x["guard_blocked_concept"] in gset:
                    b4w += 1
                else:
                    b4c += 1
                errs.append({"set": "PILOT_B4_BLOCK", "text": t, "type": "B4_BLOCK_" + ("WRONG(정답 차단)" if x["guard_blocked_concept"] in gset else "CORRECT(오답 차단)"),
                             "got": f"{x['guard_blocked_concept']}|{x.get('unit_text')}|{';'.join(x.get('guard_reasons') or [])}"})
        used = set()
        for g in gm:
            pm["n"] += 1
            pm["multi_n"] += len(gm) >= 2
            i = next((k for k, x in enumerate(ex) if k not in used and x["canonical_id"] == g["concept"]), None)
            if i is None:
                errs.append({"set": "PILOT", "text": t, "type": "MISSED_OR_UNMAPPED", "got": g["concept"]})
                continue
            used.add(i)
            x = ex[i]
            pm["matched"] += 1
            pm["multi_matched"] += len(gm) >= 2
            wa = EXP_ASSERT.get(g.get("status"), "PRESENT")
            hist = g.get("status") == "historical"
            other = g.get("subject", "patient") != "patient"
            pm["a_ok"] += x["assertion"] == wa
            pm["t_ok"] += (x["temporality"] in ("PAST", "RESOLVED")) == hist
            pm["e_ok"] += (x["experiencer"] in ("OTHER_PERSON", "MULTIPLE")) == other
            if x["assertion"] != wa:
                errs.append({"set": "PILOT", "text": t, "type": "NEGATION", "got": f"{g['concept']}:{g.get('status')}→{x['assertion']}({x.get('assertion_basis')})"})
            if g.get("status") == "absent" and x["assertion"] == "PRESENT" and x["model_input"]["polarity"] == "POSITIVE":
                m["g5"] += 1
            if other and x["experiencer"] == "PATIENT" and x["model_input"]["eligible"]:
                m["g6"] += 1
        for x in ex:
            if x["canonical_id"] not in gset:
                pm["wrong"] += 1
                errs.append({"set": "PILOT", "text": t, "type": "WRONG_CONCEPT", "got": f"{x['canonical_id']}|{x['raw_span']}"})
        if r["should_link"] == "False":
            pm["un"] += 1
            pm["ua"] += bool(ex)
        if t in regg and ex:
            pm["ra"] += 1
            pm["rc"] += ex[0]["canonical_id"] == regg[t]
    for x in allm:
        nm += 1
        off += isinstance(x["span_start"], int) and 0 <= x["span_start"] < x["span_end"] <= len(x["source_text"]) and x["raw_span"] == x["source_text"][x["span_start"]:x["span_end"]]
    res = {"inputs": ni, "raw_ok": raw, "mentions": nm, "offset_ok": off,
           "pilot_multi_retention": S.rnd(pm["multi_matched"] / pm["multi_n"]), "pilot_multi_n": pm["multi_n"], "pilot_retention": S.rnd(pm["matched"] / pm["n"]),
           "pilot_assertion_agreement": S.rnd(pm["a_ok"] / pm["matched"]), "pilot_temporality_agreement": S.rnd(pm["t_ok"] / pm["matched"]),
           "pilot_experiencer_agreement": S.rnd(pm["e_ok"] / pm["matched"]), "pilot_wrong_concept_mentions": pm["wrong"],
           "pilot_unsupported_auto": pm["ua"], "pilot_unsupported_n": pm["un"], "reg_precision": S.rnd(pm["rc"] / pm["ra"]) if pm["ra"] else None,
           "reg_coverage": S.rnd(pm["ra"] / len(regg)), "reg_n": len(regg), "C29_failed": m["C29_n"] - m["C29_pass"], "NEW42_pass": m["NEW42_pass"],
           "PROS231_pass": m["PROS231_pass"], "B4_GUARD_CORRECT_BLOCKS(pilot)": b4c, "B4_GUARD_WRONG_BLOCKS(pilot)": b4w, "G5_exposed": m["g5"], "G6_exposed": m["g6"],
           "G7_mentions": sum(1 for x in allm if (x["status"] in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE") or x.get("evidence_sources") == "SILVER")
                              and (x.get("model_input") or {}).get("eligible")),
           "G10_mentions": sum(1 for x in allm if (x["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM") and not (x.get("reason") or x.get("guard_reasons"))) or not x["raw_span"])}
    return res, errs


def weak_metrics(analyze_fn, policy):
    sil = [r["raw_expression"] for r in S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv")]
    wn = [r["text"] for r in S.read_csv(S.S28_DIR / "outputs/weak_non_check.csv")]
    silm, wpos, allm, raw = [], 0, [], 0
    for t in sil:
        o = analyze_fn(t, policy)
        silm += o["mentions"]
        allm += o["mentions"]
        raw += o["source_text"] == t and all(x["raw_span"] == t[x["span_start"]:x["span_end"]] for x in o["mentions"])
    for t in wn:
        o = analyze_fn(t, policy)
        allm += o["mentions"]
        wpos += any(x["status"] in POS for x in o["mentions"])
        raw += o["source_text"] == t and all(x["raw_span"] == t[x["span_start"]:x["span_end"]] for x in o["mentions"])
    return {"inputs": len(sil) + len(wn), "raw_ok": raw, "silver_unknown_uncertain_rate": S.rnd(sum(x["status"] in ("UNKNOWN_SYMPTOM", "UNCERTAIN") for x in silm) / len(silm)),
            "weaknon_positive_inputs": wpos, "weaknon_n": len(wn),
            "G7_mentions": sum(1 for x in allm if (x["status"] in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE") or x.get("evidence_sources") == "SILVER")
                               and (x.get("model_input") or {}).get("eligible")),
            "G10_mentions": sum(1 for x in allm if (x["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM") and not (x.get("reason") or x.get("guard_reasons"))) or not x["raw_span"])}


def prereg_ok(final: bool) -> dict:
    pre = S.load_json(S.DATA / "prereg_gates.json")
    st = {"gates_scripts": all(S.sha256(S.STEP / "scripts" / n) == h for n, h in pre["frozen_scripts"].items()),
          "data": all(S.sha256(S.DATA / n) == h for n, h in pre["frozen_data"].items()), "evaluator_v6": evaluator_sha() == pre["evaluator_v6_sha256"]}
    if final:
        pf = S.load_json(S.DATA / "policy_freeze.json")
        st["policy_scripts"] = all(S.sha256(S.STEP / "scripts" / n) == h for n, h in pf["frozen_scripts"].items())
        st["selected_policy"] = pf["SELECTED_POLICY"]
    return st


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dev"
    st = prereg_ok(mode == "final")
    assert all(v for k, v in st.items() if k != "selected_policy"), f"동결 이후 변경 — 평가 중단 {st}"
    import nlu_pipeline_v3 as N
    pols = list(N.POLICIES)
    sets = [("DEV", load_new("dev_pairs.json"))] + ([("HOLDOUT", load_new("frozen_holdout_pairs.json"))] if mode == "final" else [])
    M, E = {}, []
    for P in pols:
        M[P] = {}
        for name, d in sets:
            cases = d["cases"]
            outs = [N.analyze(c["text"], P) for c in cases]
            res, errs = new_set_metrics(cases, outs, d["metamorphic"], lambda t, P=P: N.sentence_spans(t, P))
            M[P][name] = res
            E += [{"policy": P, "set": name, **e} for e in errs]
        res, errs = exposed_metrics(N.analyze, P)
        M[P]["EXPOSED"] = res
        E += [{"policy": P, **e} for e in errs]
        if mode == "final":
            M[P]["WEAK"] = weak_metrics(N.analyze, P)
        print(P, "done", flush=True)
    tag = "final" if mode == "final" else "dev"
    S.dump_json(S.OUT / ("eval_summary.json" if tag == "final" else "dev_policy_metrics.json"), {"mode": tag, "prereg_status": st, "metrics": M,
                                                                                                    "evaluator_sha256": evaluator_sha()})
    S.wcsv(S.OUT / ("eval_errors.csv" if tag == "final" else "dev_errors.csv"), E)
    keys = ("CONCEPT_PRECISION", "CONCEPT_COVERAGE", "MULTI_SPAN_RETENTION", "NEGATION_SCOPE", "PUNCTUATION_PAIR_CONSISTENCY", "RESOLUTION_LINKING",
            "RESOLUTION_FALSE_LINK", "PROPAGATION_ERRORS", "UNSUPPORTED_AUTO_LINK", "SEMANTIC_VIOLATIONS", "CASE_PASS_RATE")
    for P in pols:
        for name, _ in sets:
            print(P, name, S.dumps({k: M[P][name][k] for k in keys}))
        print(P, "EXPOSED", S.dumps({k: M[P]["EXPOSED"][k] for k in ("pilot_multi_retention", "pilot_assertion_agreement", "reg_precision", "reg_coverage",
                                                                       "pilot_unsupported_auto", "B4_GUARD_CORRECT_BLOCKS(pilot)", "B4_GUARD_WRONG_BLOCKS(pilot)",
                                                                       "G5_exposed", "G6_exposed", "PROS231_pass", "NEW42_pass", "C29_failed")}))


if __name__ == "__main__":
    main()
