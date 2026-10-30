#!/usr/bin/env python3
"""EXP-SN-NBI-002 B0d 매핑 정찰(reconnaissance) — radiology_detail 의 exam 어휘만 추출.

LOCAL ONLY. 코호트·진단 class·시각·보고서 본문(radiology.csv.gz text)을 전혀 읽지 않는다.
radiology_detail 의 field_name·field_value(exam_name·exam_code·cpt_code 만)·note_id·subject_id 만 사용.
출력(b0d/exam_vocab.json, credentialed 파생 어휘 — 공개 저장소 반출 금지):
  - field_name 어휘
  - 넓은 정찰 키워드에 걸리는 exam_name 중 note ≥ K_MIN ∧ subject ≥ K_MIN 인 것만(건수 없음, 억제 수만)
  - 그 exam_name 별로 함께 나온 cpt_code·exam_code(각각 note ≥ K_MIN 인 것만, 건수 없음)
  - note 당 exam_name·cpt_code 개수 구간(중복 처리 설계용, 전체 데이터 기준 거친 구간)
매핑 결정에 class별·환자별 빈도를 쓰지 않는다. stdout = 요약 1줄.
"""
import csv
import gzip
import json
import os
import re
import sys

K_MIN = 11  # small-cell 억제(어휘 노출 하한)
RECON = re.compile(r"\bcta?\b|\bct\W|chest|thora|pulm|lung|embol|angio|v/q|ventilat|perfusion|coronar|cardiac|heart")
KEEP = {"exam_name", "exam_code", "cpt_code"}


def main(path, out):
    fields = set()
    per_note = {}  # note_id -> {"subj":..., "exam_name": set, "exam_code": set, "cpt_code": set}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        h = next(rd)
        i_note, i_subj, i_f, i_v = (h.index(c) for c in ("note_id", "subject_id", "field_name", "field_value"))
        for r in rd:
            f = r[i_f]
            fields.add(f)
            if f not in KEEP:
                continue
            n = per_note.setdefault(r[i_note], {"subj": r[i_subj], "exam_name": set(), "exam_code": set(),
                                                 "cpt_code": set()})
            n[f].add(r[i_v].strip())
    name_notes, name_subj, name_cpt, name_code = {}, {}, {}, {}
    mult = {"exam_name": {}, "cpt_code": {}}
    for n in per_note.values():
        for f in mult:
            k = min(len(n[f]), 3)
            mult[f][k] = mult[f].get(k, 0) + 1
        for e in n["exam_name"]:
            if not RECON.search(e.lower()):
                continue
            name_notes[e] = name_notes.get(e, 0) + 1
            name_subj.setdefault(e, set()).add(n["subj"])
            for c in n["cpt_code"]:
                name_cpt.setdefault(e, {}).setdefault(c, 0)
                name_cpt[e][c] += 1
            for c in n["exam_code"]:
                name_code.setdefault(e, {}).setdefault(c, 0)
                name_code[e][c] += 1
    kept = sorted(e for e in name_notes if name_notes[e] >= K_MIN and len(name_subj[e]) >= K_MIN)
    vocab = {
        "k_min": K_MIN, "recon_regex": RECON.pattern, "field_names": sorted(fields),
        "suppressed_recon_names": len(name_notes) - len(kept),
        "exam_names": {e: {"cpt_codes": sorted(c for c, v in name_cpt.get(e, {}).items() if v >= K_MIN),
                           "exam_codes": sorted(c for c, v in name_code.get(e, {}).items() if v >= K_MIN)}
                       for e in kept},
        "per_note_multiplicity_bucket": {f: {str(k): ("GE_1000" if v >= 1000 else "LT_1000")
                                             for k, v in sorted(m.items())} for f, m in mult.items()},
    }
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(vocab, f, indent=1, sort_keys=True)
    print(f"B0D_VOCAB OK kept={len(kept)} suppressed={vocab['suppressed_recon_names']}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
