"""STEP29.3 §3·§4 P5 검색 실패 분해(노출 회귀 자료 — STEP29.2 HOLDOUT 의 V3_B0 미연결·오연결 + 지시문 3절 회귀 사례). R0(STEP29.2 V3_B0) 출력과 P5 단독 출력을 다시 계산해
원인 범주(중복 가능)를 규칙으로 붙인다. 출력: outputs/failure_taxonomy.csv(입력·정답 mention 단위) + outputs/failure_taxonomy_summary.json(원인별·입력별 집계).
 SPAN_BOUNDARY_ERROR   시점 표현('지난주에' 등)이 비증상 조각으로 잘리고 정답 mention 이 없음 / 시점어를 가리면 연결됨
 MORPHOLOGICAL_VARIANT 정답 mention 이 미연결인데 표준 질의(부정 제거·은/는→이/가·어미 표준화)로 같은 정답 concept 이 검색됨
 SEMANTIC_AMBIGUITY    검색기 사유 CONCEPT_AMBIGUITY(후보 둘 이상 충돌, 예 구토↔토혈)
 ANATOMICAL_AMBIGUITY  검색기 근거 NECK_AMBIGUOUS(목 = 인후/경부)
 LEXICAL_VARIANT       NO_KOREAN_MATCH 이고 표준 질의로도 미연결(사전에 없는 표현)
 MODIFIER_LOSS         STEP29/29.1 의성어 가드(IDEOPHONE_*)가 원인
 MODEL_FALLBACK_ERROR  오연결이 B4 모델 경로(MODEL_B4)
 PARTIAL_STRING_MATCH  오연결 근거 등급 PHRASE/BOUNDARY
 FALSE_NON_SYMPTOM     정답 증상이 NON_SYMPTOM 으로 처리
 UNSUPPORTED_CONCEPT   정답이 77 밖(SILVER·미지원)
 ONTOLOGY_RELATION_ERROR 회귀 사례에서 허용 밖 concept 이 EXACT 근거로 연결(사전 대응 오류)
 NON_SYMPTOM_AUTO_LINK 비증상 문장(날씨·인식 표현)에 증상 concept 연결
단계(stage): P5(검색기) · NLU(STEP29 단위·구문) · GUARD(가드). 수정 범위: STEP29.3 어댑터에서 가능 / P5 원본 수정 필요(금지)."""
import collections
import json

import s293_common as S
import nlu_pipeline_v3 as V3
from contract_check_v3 import align
from korean_morphological_normalizer import canonical_query, mask_time
from p5_normalizer_adapter import p5


def classify(text, g, m, models):
    cats = []
    if m is None:
        ms, ph = mask_time(text)
        if ph and any(r["status"] in S.EXISTING and r.get("canonical_id") in g["concept_any"] for r in p5(ms.strip())):
            cats.append("SPAN_BOUNDARY_ERROR")
        else:
            cats.append("SPAN_BOUNDARY_ERROR" if ph else "NLU_DROPPED")
        return cats, "P5" if ph else "NLU"
    reason, tier = str(m.get("reason") or ""), m.get("ko_tier")
    ev = " ".join(m.get("ko_evidence") or [])
    if m["status"] == "NON_SYMPTOM":
        cats.append("FALSE_NON_SYMPTOM")
    if "CONCEPT_AMBIGUITY" in reason:
        cats.append("SEMANTIC_AMBIGUITY")
    if "NECK" in ev or "NECK" in reason:
        cats.append("ANATOMICAL_AMBIGUITY")
    if any("IDEOPHONE" in r for r in m.get("guard_reasons") or []):
        cats.append("MODIFIER_LOSS")
    if m["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM") and not m.get("guard_reasons"):
        q = canonical_query(m.get("unit_text") or m["raw_span"], True)
        if q and any(r["status"] in S.EXISTING and r.get("canonical_id") in g["concept_any"] for r in p5(q)):
            cats.append("MORPHOLOGICAL_VARIANT")
        elif "NO_KOREAN_MATCH" in reason or tier in ("NONE", None):
            cats.append("LEXICAL_VARIANT")
    if m["status"] in S.EXISTING and m.get("canonical_id") not in g["concept_any"]:
        cats.append("MODEL_FALLBACK_ERROR" if tier == "MODEL_B4" else "PARTIAL_STRING_MATCH" if tier in ("PHRASE", "BOUNDARY") else "ONTOLOGY_RELATION_ERROR")
    if not any(c in models for c in g["concept_any"] if c):
        cats.append("UNSUPPORTED_CONCEPT")
    stage = "GUARD" if m.get("guard_reasons") else "P5"
    return cats or ["OTHER"], stage


def main():
    models = S.models()
    hold = {c["id"]: c for c in json.loads((S.S292_DIR / "data/frozen_holdout_pairs.json").read_text(encoding="utf-8"))["cases"]}
    errs = [e for e in S.read_csv(S.S292_DIR / "outputs/eval_errors.csv") if e["policy"] == "V3_B0" and e["set"] == "HOLDOUT"
            and e["type"] in ("NOT_EXTRACTED", "WRONG_CONCEPT")]
    rows, seen = [], set()
    for e in errs:
        c = hold[e["id"]]
        if (c["id"], e["anchor"]) in seen:
            continue
        seen.add((c["id"], e["anchor"]))
        o = V3.analyze(c["text"], "V3_B0")
        for g, idx in align(c, o["mentions"]):
            if g["anchor"] != e["anchor"]:
                continue
            m = o["mentions"][idx] if idx is not None else None
            cats, stage = classify(c["text"], g, m, models)
            fix = "ADAPTER" if set(cats) & {"SPAN_BOUNDARY_ERROR", "MORPHOLOGICAL_VARIANT", "SEMANTIC_AMBIGUITY", "ANATOMICAL_AMBIGUITY", "FALSE_NON_SYMPTOM"} else "P5_SOURCE_OR_LEXICON"
            rows.append({"source": "STEP29_2_HOLDOUT(노출)", "id": c["id"], "text": c["text"], "anchor": g["anchor"], "gold": "/".join(map(str, g["concept_any"])),
                         "r0_status": m["status"] if m else "NOT_EXTRACTED", "r0_concept": (m or {}).get("canonical_id"), "r0_reason": (m or {}).get("reason"),
                         "r0_tier": (m or {}).get("ko_tier"), "categories": ";".join(cats), "stage": stage, "fix_scope": fix})
            break
    rc = S.load_json(S.DATA / "regression_cases.json")["cases"]
    for c in rc:
        o = V3.analyze(c["text"], "V3_B0")
        for m in o["mentions"]:
            bad = m["status"] in S.EXISTING and (m.get("canonical_id") in c["forbidden"] or not c["allowed"] or m.get("canonical_id") not in c["allowed"])
            unk = m.get("is_symptom") and m["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM") and c["allowed"]
            if not (bad or unk):
                continue
            cats = []
            if bad:
                cats.append("NON_SYMPTOM_AUTO_LINK" if not c["allowed"] else ("MODEL_FALLBACK_ERROR" if m.get("ko_tier") == "MODEL_B4" else "ONTOLOGY_RELATION_ERROR"))
            if unk:
                cats += classify(c["text"], {"concept_any": c["allowed"]}, m, models)[0]
            rows.append({"source": "SPEC_REGRESSION(노출)", "id": "", "text": c["text"], "anchor": m["raw_span"], "gold": "/".join(c["allowed"]) or "(EXISTING 금지)",
                         "r0_status": m["status"], "r0_concept": m.get("canonical_id"), "r0_reason": m.get("reason"), "r0_tier": m.get("ko_tier"),
                         "categories": ";".join(cats), "stage": "P5", "fix_scope": "ADAPTER"})
    S.wcsv(S.OUT / "failure_taxonomy.csv", rows)
    by_cause = collections.Counter(x for r in rows for x in r["categories"].split(";"))
    by_input = collections.Counter(r["categories"] for r in rows)
    S.dump_json(S.OUT / "failure_taxonomy_summary.json", {"n_rows(정답 mention·사례 단위)": len(rows), "by_cause(중복 포함)": dict(by_cause.most_common()),
                                                          "by_input_category_combo": dict(by_input.most_common()), "by_stage": dict(collections.Counter(r["stage"] for r in rows)),
                                                          "by_fix_scope": dict(collections.Counter(r["fix_scope"] for r in rows)), "rules": __doc__})
    print(S.dumps({"rows": len(rows), "by_cause": dict(by_cause.most_common())}))


if __name__ == "__main__":
    main()
