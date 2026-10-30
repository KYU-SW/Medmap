"""STEP20 진입점. 두 단계:
  python audit_symptom_mapping.py inventory  → outputs/symptom_inventory.csv (DDXPlus 증상 110 확정, 110/113/223 assert)
  python audit_symptom_mapping.py summary    → (HPO·UMLS·SNOMED 감사 후) coverage · 확장 · 표현층 · 질환 겹침 · 보조 KB · 대표 증상 · manifest
"""
import sys

import pandas as pd

import common as c
import summary_stage


def inventory():
    sym = c.load_symptoms()
    ko = c.load_terminology_ko()
    short, questions, values = ko["evidence_short"], ko["evidence_questions"], ko["values"]
    rows = []
    for eid in sorted(sym, key=lambda k: int(k.split("_")[1])):
        v = sym[eid]
        pv = v["possible-values"]
        if v["data_type"] == "B":
            values_en = "yes/no"
        elif v["value_meaning"]:
            values_en = "; ".join(f"{p}={v['value_meaning'][p]['en']}" for p in pv if p in v["value_meaning"])
        else:
            values_en = "; ".join(str(p) for p in pv)
        rows.append({
            "evidence_id": eid,
            "label_en": v["question_en"],          # DDXPlus 에는 별도 영문 label 이 없다 — 질문문이 정본 표현
            "label_ko": (short.get(eid) or {}).get("label_ko", ""),
            "question_en": v["question_en"],
            "question_ko": (questions.get(eid) or {}).get("text_ko", ""),
            "data_type": {"B": "binary", "C": "categorical", "M": "multichoice"}[v["data_type"]],
            "n_possible_values": len(pv),
            "possible_values": values_en,
            "n_values_with_ko": sum(1 for p in pv if isinstance(p, str) and (values.get(p) or {}).get("label_ko")),
            "default_value": v["default_value"],
            "code_question": v["code_question"],
            "is_sub_question": v["code_question"] != eid,
            "source": "ddxplus/en/release_evidences.json",
        })
    df = pd.DataFrame(rows)
    assert len(df) == 110 and df["evidence_id"].is_unique and df["evidence_id"].str.match(r"^E_\d+$").all()
    c.write_csv(df, "symptom_inventory.csv")
    print("symptom_inventory.csv", len(df), df["data_type"].value_counts().to_dict(),
          "sub_questions", int(df["is_sub_question"].sum()), "ko_missing", int((df["label_ko"] == "").sum()))


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "inventory"
    if stage == "inventory":
        inventory()
    elif stage == "summary":
        summary_stage.run()
    else:
        raise SystemExit(f"unknown stage {stage}")
