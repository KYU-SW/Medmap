"""STEP21-1: dictionary(기존 MedMap 한국어 자원) 와 pilot gold(별도 작성 test 표현) 를 분리해 만든다.

DICTIONARY = 기존 terminology_ko.json(evidence_short label, evidence_questions) · initial_evidence_ko.json · question_labels_ko.json
             → STEP20 core symptom 87개 evidence 만, canonical concept id 로 연결.
GOLD       = data/pilot_source_utterances.tsv (Claude 가 2026-10-08 작성한 합성 표현; 실제 환자 발화 아님)
누수 검사   = (1) 사전과 정규화 완전일치 (2) 사전과 near-duplicate(difflib ≥ 0.80) → 평가에서 제거
             (3) gold 내부 near-duplicate(≥ 0.85) 가 dev/test 에 갈리면 같은 split 으로 이동
             (4) 정답 concept 의 사전 stem 이 문장에 그대로 들어 있으면 lexical_exposure=seen(암기 성능), 아니면 novel(일반화 성능)
split      = group 안 원본 순서 index % 3 == 0 → dev(threshold 선택용), 나머지 test
출력: data/dictionary_expressions.csv, data/pilot_gold.csv, data/leakage_report.json
"""
import json
from collections import defaultdict
from difflib import SequenceMatcher

import el_common as c

NEAR_DICT = 0.80
NEAR_GOLD = 0.85


def build_dictionary(ev2c):
    t = json.load(open(c.TERMINOLOGY_KO, encoding="utf-8"))
    ini = json.load(open(c.INITIAL_KO, encoding="utf-8"))
    ql = json.load(open(c.QLABELS_KO, encoding="utf-8"))
    rows = []

    def add(expr, eid, source_type, source):
        expr = expr.strip()
        if expr and eid in ev2c:
            st = c.dict_stems(expr)
            rows.append({"expression": expr, "stem": st[0], "stem_alt": st[1] if len(st) > 1 else "",
                         "concept_id": ev2c[eid], "evidence_id": eid,
                         "source_type": source_type, "source": source})
    import re
    for eid, v in t["evidence_short"].items():
        lab = v.get("label_ko", "")
        add(lab, eid, "terminology", "terminology_ko.evidence_short")
        for part in re.split(r"[·/()]|\s또는\s", lab):        # 'A·B', 'A(B)' 의 구성 표현
            if part.strip() and part.strip() != lab:
                add(part, eid, "terminology", "terminology_ko.evidence_short(part)")
    for eid, v in t["evidence_questions"].items():
        add(v.get("text_ko", ""), eid, "existing_medmap", "terminology_ko.evidence_questions")
    for it in ini["items"]:
        add(it.get("label_ko", ""), it["evidence_id"], "existing_medmap", "initial_evidence_ko.label")
        add(it.get("detail_ko", ""), it["evidence_id"], "existing_medmap", "initial_evidence_ko.detail")
    for eid, v in ql["questions"].items():
        add(v if isinstance(v, str) else v.get("text_ko", ""), eid, "existing_medmap", "question_labels_ko.questions")
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: (r["concept_id"], r["evidence_id"], r["expression"], r["source"])):
        k = (r["stem"], r["concept_id"])
        if k in seen or not r["stem"]:
            continue
        seen.add(k)
        out.append(r)
    return out


def parse_gold(code):
    if code.strip() == "-":
        return []
    ms = []
    for part in code.split(";"):
        part = part.strip()
        subj = "other" if part.startswith("o:") else "patient"
        part = part[2:] if subj == "other" else part
        ms.append({"concept": part[:-1], "status": c.STATUS[part[-1]], "subject": subj})
    return ms


def parse_attrs(s):
    out = defaultdict(dict)
    for kv in filter(None, s.split("|")):
        k, v = kv.split("=", 1)
        concept, key = k.split(".", 1)
        out[concept][key] = v
    return dict(out)


def main():
    ev2c = c.label_space()
    dic = build_dictionary(ev2c)
    c.write_csv(c.DATA / "dictionary_expressions.csv", dic)
    src = c.read_csv(c.DATA / "pilot_source_utterances.tsv")
    valid = set(ev2c.values())
    by_group = defaultdict(int)
    gold, removed = [], []
    dic_ns = [(c.nospace(d["expression"]), d) for d in dic]
    for i, r in enumerate(src, 1):
        uid = f"U{i:03d}"
        ms = parse_gold(r["gold"])
        for m in ms:
            assert m["concept"] in valid, (uid, m)
        u_ns = c.nospace(r["text"])
        # (1)(2) 사전 누수
        leak = ""
        for d_ns, d in dic_ns:
            if u_ns == d_ns or u_ns == d["stem"]:
                leak = f"EXACT_IN_DICTIONARY:{d['expression']}"
                break
            if SequenceMatcher(None, u_ns, d_ns).ratio() >= NEAR_DICT:
                leak = f"NEAR_DUPLICATE_OF_DICTIONARY:{d['expression']}"
                break
        idx = by_group[r["group"]]
        by_group[r["group"]] += 1
        pat = [m for m in ms if m["subject"] == "patient"]
        pat_concepts = sorted({m["concept"] for m in pat})
        stems = {x for d in dic if d["concept_id"] in pat_concepts for x in (d["stem"], d["stem_alt"]) if x}
        exposure = "seen" if any(s and s in u_ns for s in stems) else ("novel" if pat_concepts else "n/a")
        primary = pat[0] if pat else None
        row = {
            "utterance_id": uid, "text_ko": r["text"], "group": r["group"], "utt_type": r["utt_type"], "tier": r["tier"],
            "split": "dev" if idx % 3 == 0 else "test",
            "source_type": "synthetic_paraphrase",
            "provenance": "Claude-authored 2026-10-08 for STEP21 pilot; not real patient speech; not copied from MedMap resources",
            "gold_mentions": json.dumps(ms, ensure_ascii=False),
            "patient_concepts": ";".join(pat_concepts),
            "primary_concept": primary["concept"] if primary else "",
            "primary_name": c.PILOT_NAMES.get(primary["concept"], primary["concept"]) if primary else "",
            "primary_status": primary["status"] if primary else "",
            "secondary_concepts": ";".join(m["concept"] + ":" + m["status"] for m in pat[1:]),
            "other_person_concepts": ";".join(m["concept"] for m in ms if m["subject"] == "other"),
            "attributes": json.dumps(parse_attrs(r["attrs"]), ensure_ascii=False),
            "should_link": bool(pat_concepts),
            "ambiguity_flag": r["ambiguous"] == "1",
            "reason": r["note"],
            "has_negation": any(m["status"] == "absent" for m in pat),
            "has_temporal": any(m["status"] == "historical" for m in pat),
            "has_uncertain": any(m["status"] == "uncertain" for m in pat),
            "has_other_person": any(m["subject"] == "other" for m in ms),
            "is_multi": len(pat_concepts) >= 2,
            "lexical_exposure": exposure,
            "leakage_check": leak or "OK",
        }
        (removed if leak else gold).append(row)
    # (3) gold 내부 near-duplicate 가 dev/test 에 갈리면 test 로 이동
    moved = []
    for a in gold:
        for b in gold:
            if a["utterance_id"] < b["utterance_id"] and a["split"] != b["split"] and \
                    SequenceMatcher(None, c.nospace(a["text_ko"]), c.nospace(b["text_ko"])).ratio() >= NEAR_GOLD:
                for x in (a, b):
                    if x["split"] == "dev":
                        x["split"] = "test"
                        moved.append(x["utterance_id"])
    c.write_csv(c.DATA / "pilot_gold.csv", gold)
    if removed:
        c.write_csv(c.DATA / "leakage_removed.csv", removed)
    pilot_in_gold = sorted({m["concept"] for g in gold for m in json.loads(g["gold_mentions"])} & set(c.PILOT))
    rep = {
        "dictionary_expressions": len(dic), "dictionary_concepts": len({d["concept_id"] for d in dic}),
        "dictionary_by_source": {s: sum(1 for d in dic if d["source"] == s) for s in sorted({d["source"] for d in dic})},
        "source_utterances": len(src), "removed_for_leakage": len(removed),
        "removed_examples": [(r["text_ko"], r["leakage_check"]) for r in removed],
        "gold_utterances": len(gold), "moved_to_test_for_internal_near_duplicates": sorted(set(moved)),
        "split": {s: sum(1 for g in gold if g["split"] == s) for s in ("dev", "test")},
        "tier": {t: sum(1 for g in gold if g["tier"] == t) for t in "ABCD"},
        "lexical_exposure": {e: sum(1 for g in gold if g["lexical_exposure"] == e) for e in ("seen", "novel", "n/a")},
        "pilot_concepts_in_gold": pilot_in_gold, "n_pilot_concepts": len(pilot_in_gold),
        "other_person_utterances": sum(1 for g in gold if g["has_other_person"]),
        "negation_utterances": sum(1 for g in gold if g["has_negation"]),
        "temporal_utterances": sum(1 for g in gold if g["has_temporal"]),
        "multi_utterances": sum(1 for g in gold if g["is_multi"]),
        "should_not_link_utterances": sum(1 for g in gold if not g["should_link"]),
        "source_type": {"synthetic_paraphrase": len(gold), "existing_medmap": 0, "existing_patient_companion": 0,
                        "note": "friend Patient Companion repo is not local (user decision 2026-10-04: not imported)"},
        "thresholds": {"near_dictionary_difflib": NEAR_DICT, "near_gold_difflib": NEAR_GOLD},
    }
    json.dump(rep, open(c.DATA / "leakage_report.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != "removed_examples"}, ensure_ascii=False))
    print("removed:", rep["removed_examples"])


if __name__ == "__main__":
    main()
