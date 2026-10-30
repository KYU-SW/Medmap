#!/usr/bin/env python3
"""EXP-SN-NBI-002 B0d exam_name → 영상 개념 매핑 고정 도구.

입력 = b0d/exam_vocab.json(정찰 어휘: exam_name·cpt·exam_code, 건수 없음, 코호트·class·시각·본문 미사용).
규칙(사전 고정, exam_name 대문자 정확 문자열에 대한 접두 정규식 — 보고서 본문·indication·결과 문구 미사용):
  IMAGING_CTA_CHEST : ^CTA CHEST\\b   (흉부 CT 혈관조영, 관상동맥 CTA 제외 — 'CTA CORONARY …'는 접두가 다름)
  IMAGING_CHEST_CT  : ^CT CHEST\\b    (진단 흉부 CT 조영/비조영/조영 전후/종양 table)
정찰 어휘에 PE 전용 이름(pulmonary·PE protocol·embol 계열 CTA)이 없으므로 CTPA 를 메타데이터로 분리할 수 없다 →
IMAGING_CTA_CHEST 는 'CTPA 와 호환되는 흉부 CTA(대동맥 등 다른 적응증 포함)'로만 정의한다.
출력 = b0d/exam_map.json(개념별 정확 이름 목록 + 제외 이름의 사유 범주). 실행 시 b0d_availability.py 가 같은 규칙을
radiology_detail 전체 exam_name 에 다시 적용해 이 목록과 다르면 INVALID(exam_map_mismatch).
"""
import json
import os
import re
import sys

RULES = {
    "IMAGING_CTA_CHEST": re.compile(r"^CTA CHEST\b"),
    "IMAGING_CHEST_CT": re.compile(r"^CT CHEST\b"),
}
# 제외 사유 범주(정찰 어휘 중 규칙에 안 걸린 이름의 설명용 — 판정에 쓰지 않음, 순서대로 첫 일치)
EXCLUDE_REASONS = [
    ("CORONARY_OR_CARDIAC", re.compile(r"CORONARY|CARDIAC")),
    ("LUNG_CANCER_SCREENING", re.compile(r"SCREENING|\bLCS\b")),
    ("PROCEDURE_OR_GUIDANCE", re.compile(r"\bBX\b|GUID|DRAIN|ABLATION|EMBOLIZ|CATH|NEEDLE|CENTESIS|CHOLANG|ANGIOP|"
                                         r"FISTULO|INS |ANGIOGRAM|RFA|TUBE|STEREOTAXIS|PLCT|PLACEMENT")),
    ("CHEST_RADIOGRAPH_OR_FLUORO", re.compile(r"^CHEST|PORT|FLUORO|^RIB|SERIES|^TRAUMA|THORACIC SINGLE VIEW")),
    ("MR_OR_US", re.compile(r"^MR|\bU\.S\.|^US\b")),
    ("OTHER_CT_BODY_REGION", re.compile(r"^(CT|CTA|PORTABLE HEAD CT|ED )")),
]


def concept_of(name):
    return sorted(c for c, rx in RULES.items() if rx.search(name.strip().upper()))


def main(vocab_path, out_path):
    names = sorted(json.load(open(vocab_path, encoding="utf-8"))["exam_names"])
    acc = {c: sorted(n for n in names if c in concept_of(n)) for c in RULES}
    excl = {}
    for n in names:
        if concept_of(n):
            continue
        r = next((k for k, rx in EXCLUDE_REASONS if rx.search(n.upper())), "OTHER")
        excl.setdefault(r, []).append(n)
    out = {"rules": {c: rx.pattern for c, rx in RULES.items()}, "accepted": acc,
           "excluded_by_reason": {k: sorted(v) for k, v in sorted(excl.items())},
           "note": "exam_name only (radiology_detail field_name='exam_name' on RR notes); report text, indication, "
                   "impression, cpt_code and exam_code are not used for concept assignment"}
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print("B0D_EXAM_MAP " + " ".join(f"{c}={len(v)}" for c, v in acc.items()))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
