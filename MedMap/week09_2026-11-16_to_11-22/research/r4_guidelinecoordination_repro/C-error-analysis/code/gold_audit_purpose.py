"""SUBAGENT C - 원문에 '血糖控制/降糖'(혈당 조절 목적) 한정어가 있는데 condition 에 혈당 관련 술어가 없는 규칙 목록.
SGLT2i 는 혈당 목적 외(신장·심장 보호) 적응증이 있어, 목적 한정어 소실 시 신장·심부전 권고와 거짓 충돌 가능(가설)."""
import json, re
from pathlib import Path
import pandas as pd
ROOT = Path("/home/<user>/medmap-guidelinecoordination-repro-20261118")
rules = json.loads((ROOT / "upstream/GuidelineCoordination/rules_gold.json").read_text())
rows = []
for r in rules:
    q = r["provenance"][0]["quote"]; c = r["condition"]
    if re.search(r"血糖控制|改善血糖|降糖治疗|控制血糖", q):
        rows.append({"id": r["id"], "condition": c, "subjects": "|".join(r["action"]["subjects"]),
                     "permission": r["action"]["permission"],
                     "has_glycemic_pred": bool(re.search(r"glyc|glucose|hba1c", c)),
                     "restrictive": r["action"]["permission"] in {"avoid", "contraindicate", "stop", "caution"},
                     "sglt2_subject": any("gliflozin" in s or "sglt2" in s for s in r["action"]["subjects"]),
                     "quote": q})
df = pd.DataFrame(rows)
df.to_csv(ROOT / "C-error-analysis/gold_audit_glycemic_purpose.csv", index=False, encoding="utf-8-sig")
print("quote_with_glycemic_purpose", len(df))
print("no_glycemic_pred", int((~df.has_glycemic_pred).sum()))
print("no_glycemic_pred & restrictive & sglt2", int(((~df.has_glycemic_pred) & df.restrictive & df.sglt2_subject).sum()))
print("with_glycemic_pred", int(df.has_glycemic_pred.sum()))
