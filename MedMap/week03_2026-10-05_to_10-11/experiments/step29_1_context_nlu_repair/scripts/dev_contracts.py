"""개발 루프 전용(평가 아님): 새 계약 42 를 지정 단계로 돌려 실패만 출력."""
import json
import sys

import s291_common as S
from contract_check_v2 import check
from nlu_pipeline_v2 import analyze

lvl = sys.argv[1] if len(sys.argv) > 1 else "P5"
n = 0
for c in json.loads((S.DATA / "contract_cases.json").read_text(encoding="utf-8"))["contracts"]:
    e = check(c, analyze(c["text"], lvl))
    if e:
        n += 1
        print(c["id"], c["category"], c["text"], "|", [(x["type"], x.get("anchor"), x.get("got")) for x in e])
print("FAILED", n)
