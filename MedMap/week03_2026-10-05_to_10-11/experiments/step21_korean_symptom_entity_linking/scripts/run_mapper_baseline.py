"""STEP21 BASELINE_MAPPER(추가): 현재 MedMap 제품의 Natural Intake 매퍼(medmap/intake, v1.2, 정규식 alias + 부정 scope)를
읽기 전용으로 호출한다. 코드·alias 는 수정하지 않는다. evidence → canonical concept(label space 밖 evidence 는 'NONCORE:E_x').
status: POSITIVE→present, NEGATIVE→absent. 시점·화자 구분 없음. 매퍼는 HIGH 만 반환 → confidence 1.0/0.0.
출력: outputs/mapper_predictions.csv
"""
import json
import sys

import el_common as c

sys.path.insert(0, str(c.REPO))
from medmap.intake import mapper  # noqa: E402


def main():
    ev2c = c.label_space()
    m = mapper.IntakeMapper(evidences_json=c.DDX_EVIDENCES)   # worktree 에는 data/ 가 없어 원본 경로 전달
    rows = []
    for g in c.load_gold():
        res = m.extract(g["text_ko"])
        preds, seen = [], set()
        for r in res:
            cid = ev2c.get(r["evidence_id"], "NONCORE:" + r["evidence_id"])
            st = "present" if r["status"] == "POSITIVE" else "absent"
            if (cid, st) in seen:
                continue
            seen.add((cid, st))
            preds.append({"concept": cid, "status": st, "score": 1.0, "matched": r["matched_text"], "evidence_id": r["evidence_id"]})
        order = []
        for p in preds:
            if p["concept"] not in order:
                order.append(p["concept"])
        rows.append({"utterance_id": g["utterance_id"], "split": g["split"], "text_ko": g["text_ko"],
                     "pred_mentions": json.dumps(preds, ensure_ascii=False), "ranked_top5": ";".join(order[:5]),
                     "top1": order[0] if order else "", "confidence": 1.0 if preds else 0.0})
    c.write_csv(c.OUT / "mapper_predictions.csv", rows)
    print("mapper: predicted", sum(1 for r in rows if r["top1"]), "/", len(rows))


if __name__ == "__main__":
    main()
