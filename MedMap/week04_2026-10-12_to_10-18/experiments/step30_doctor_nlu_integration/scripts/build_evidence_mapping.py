"""§7 기존 223 evidence ↔ NLU concept 연구용 변환표(평가 실행 전 고정). 출력: data/evidence_mapping_candidates.csv(+ .sha256)

규칙(엔지니어링 초안 — 의사 검증 0):
 - 대상 = STEP28 existing_concept_inventory 77 concept 의 ddxplus_evidence_ids 각 행 + STEP28.7 감사 SILVER concept(신규·하위) 행.
 - conversion_allowed = True 는 '증상 존재(binary POSITIVE)'를 그 evidence 질문 하나에 1:1 로 옮길 수 있을 때만:
     · evidence 가 카탈로그에 있고 binary(B)·제외 질문 아님·부모 질문 없음(code_question == 자기 자신)
     · concept 의 일반형 질문이 하나로 정해짐(1:N concept 은 GENERIC_RULES 에 적은 일반형 질문만 허용, 나머지는 SUBTYPE_OR_QUALIFIED)
     · 일반형이 둘 이상이거나 모든 질문이 한정형(횟수·상황·한쪽 등)이면 변환 안 함(NO_UNIQUE_GENERIC_TARGET)
 - 부위(E_55)·성상(E_54)·강도(E_56) 같은 값 질문은 변환 안 함(VALUE_REQUIRES_CLINICIAN): '머리' 하나가 이마·정수리·뒤통수·관자놀이 등 여러 값에 걸침.
 - 신규·하위 SILVER concept 은 관련 기존 evidence 가 있어도 변환 안 함(코피 → E_178 자동 통합 금지 등).
 - SNOMED·UMLS 문자열·ID·semantic type 은 이 표에 쓰지 않는다(HPO ID·이름만)."""
from __future__ import annotations

import json

import s30_common as S

# 1:N concept 의 일반형 질문(질문 원문으로 판단: 한정어가 없는 'Do you have …?' 형). 여기에 없는 1:N concept 은 변환 안 함.
GENERIC_RULES = {
    "cough": ("E_201", "E_201 'Do you have a cough?' = 일반형. E_77(색 있는·많은 가래)·E_203(심한 기침 발작)은 한정형"),
    "dyspnea": ("E_66", "E_66 '숨이 차거나 숨쉬기 어려움' = 일반형. E_64(약간의 활동에도)·E_67(자다가 깸)은 한정형"),
    "pain": ("E_53", "E_53 '상담 이유와 관련된 통증이 어딘가 있음' = 일반형(부위는 자식 E_55 값 — 변환 안 함). E_14(가만히 있어도 가슴 통증)은 한정형"),
    "palpitations": ("E_155", "E_155 '심장이 빠르거나 불규칙하게 뜀' = 일반형. E_164(매우 불규칙)은 한정형"),
}
NO_GENERIC = {
    "decreased_appetite": "E_32(식욕 감소)·E_161(식욕 저하 또는 조기 포만) 두 질문 모두 일반 식욕 저하를 포함 — 하나로 정할 근거 없음",
    "fatigue": "E_88(일상생활 불가 수준)·E_89(지속 피로·비회복성 수면) 모두 한정형",
    "limb_weakness": "E_84(양팔·양다리)·E_176(한쪽/얼굴 포함, 과거 포함) 모두 한정형 — 부위·측성 확인 필요",
    "vomiting": "E_166(기침 뒤 구토)·E_211(여러 번 구토) 모두 한정형 — 1회 구토를 옮길 질문 없음",
}


def main():
    P = S.product()
    from medmap import config
    raw = json.loads(config.EVIDENCES_JSON.read_text())
    excluded = set(config.EXCLUDED_QUESTIONS)
    inv = S.inventory()
    rows = []
    for cid, r in sorted(inv.items()):
        eids = [e for e in r["ddxplus_evidence_ids"].split(";") if e]
        for e in eids:
            ev = raw.get(e)
            base = {"nlu_concept_id": cid, "nlu_concept_name": r["canonical_name"], "concept_scope": "EXISTING_77", "ddxplus_evidence_id": e,
                    "evidence_question_en": (ev or {}).get("question_en", "")[:120], "evidence_data_type": (ev or {}).get("data_type", ""),
                    "evidence_parent": (ev or {}).get("code_question", ""), "hpo_ids": r["hpo_ids"]}
            reasons = []
            if ev is None:
                reasons.append("EVIDENCE_NOT_IN_CATALOG")
            else:
                if ev["data_type"] != "B":
                    reasons.append("NON_BINARY_VALUE_REQUIRED")
                if ev["code_question"] != e:
                    reasons.append(f"PARENT_QUESTION:{ev['code_question']}")
                if e in excluded:
                    reasons.append("EXCLUDED_QUESTION")
            if len(eids) == 1:
                rel = "SAME_CONCEPT" if cid.startswith("EV:") else "SAME_CONCEPT(KO_CANONICAL)"
                why = "inventory 1:1"
            elif cid in GENERIC_RULES:
                g, why = GENERIC_RULES[cid]
                rel = "GENERIC_QUESTION" if e == g else "SUBTYPE_OR_QUALIFIED"
                if e != g:
                    reasons.append("QUALIFIED_QUESTION_NOT_GENERIC")
            else:
                rel, why = "AMBIGUOUS_1toN", NO_GENERIC.get(cid, "1:N 일반형 미정")
                reasons.append("NO_UNIQUE_GENERIC_TARGET")
            ok = not reasons
            rows.append({**base, "relation_type": rel, "model_compatibility": "MODEL_FEATURE" if ev is not None else "NOT_IN_MODEL",
                         "mapping_confidence": ("INVENTORY_1to1" if len(eids) == 1 else ("RULE_GENERIC" if rel == "GENERIC_QUESTION" else "NONE")),
                         "validation_status": "ENGINEERING_DRAFT_UNVERIFIED(의사 검증 0)",
                         "conversion_allowed": ok, "conversion_target": f"{e}=POSITIVE" if ok else "",
                         "conversion_reason": (why if ok else ";".join(reasons) + " | " + why)})
    # 부위 값 질문(E_55): pain + site 는 값 변환 안 함 — 근거 행
    site = raw["E_55"]
    rows.append({"nlu_concept_id": "pain+anatomical_site", "nlu_concept_name": "Pain site (attribute)", "concept_scope": "EXISTING_77_ATTRIBUTE",
                 "ddxplus_evidence_id": "E_55", "evidence_question_en": site["question_en"], "evidence_data_type": site["data_type"],
                 "evidence_parent": site["code_question"], "hpo_ids": "", "relation_type": "ATTRIBUTE_VALUE", "model_compatibility": "MODEL_FEATURE",
                 "mapping_confidence": "NONE", "validation_status": "ENGINEERING_DRAFT_UNVERIFIED(의사 검증 0)", "conversion_allowed": False,
                 "conversion_target": "", "conversion_reason": "VALUE_REQUIRES_CLINICIAN | 부위 값 165개(머리 = 이마 V_89·정수리 V_62·뒤통수 V_25·후두부 V_124·관자놀이 V_166/V_167 등) — 자동 선택 금지"})
    # SILVER(STEP28.7 감사) 신규·하위 concept: 변환 안 함
    for r in S.read_csv(S.REPO / "exp/step28_7_mapping_quality_validation/data/audited_concepts.csv"):
        rel = r["relation_to_existing"]
        related = r.get("related_canonical") or ""
        tgt = inv.get(related, {}).get("ddxplus_evidence_ids", "") if related else ""
        rows.append({"nlu_concept_id": r["concept_id"], "nlu_concept_name": r["preferred_label"], "concept_scope": "SILVER_" + (r["final_class"] or "?"),
                     "ddxplus_evidence_id": tgt, "evidence_question_en": "", "evidence_data_type": "", "evidence_parent": "", "hpo_ids": r["concept_id"] if r["concept_id"].startswith("HP:") else "",
                     "relation_type": rel or "NEW_INDEPENDENT_CONCEPT", "model_compatibility": "NOT_MODEL_FEATURE",
                     "mapping_confidence": "SILVER(LLM 대응·감사, 사람 검증 0)", "validation_status": "SILVER_UNVERIFIED",
                     "conversion_allowed": False, "conversion_target": "",
                     "conversion_reason": ("SILVER_SUBTYPE_NO_AUTO_MERGE(관련 기존 evidence " + tgt + " 에 자동 통합 금지)") if tgt else "SILVER_NEW_CONCEPT_NOT_IN_MODEL"})
    fields = ["nlu_concept_id", "nlu_concept_name", "concept_scope", "ddxplus_evidence_id", "evidence_question_en", "evidence_data_type", "evidence_parent", "hpo_ids",
              "relation_type", "model_compatibility", "mapping_confidence", "validation_status", "conversion_allowed", "conversion_target", "conversion_reason"]
    out = S.DATA / "evidence_mapping_candidates.csv"
    S.write_csv(out, rows, fields)
    (S.DATA / "evidence_mapping_candidates.csv.sha256").write_text(S.sha256(out) + "\n")
    n_ok = sum(1 for r in rows if r["conversion_allowed"])
    print("rows", len(rows), "allowed", n_ok, "existing77 rows", sum(1 for r in rows if r["concept_scope"] == "EXISTING_77"))


if __name__ == "__main__":
    main()
