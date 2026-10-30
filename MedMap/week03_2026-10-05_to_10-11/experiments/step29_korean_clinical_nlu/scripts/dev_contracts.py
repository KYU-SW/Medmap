"""개발 루프 전용(평가 아님): 계약 68 을 NLU_P5 로 돌려 실패만 출력 → logs/dev_contracts.txt"""
import sys

from clinical_nlu_pipeline import analyze
from contract_check import check, load

lvl = sys.argv[1] if len(sys.argv) > 1 else "NLU_P5"
n = 0
for c in load()["contracts"]:
    e = check(c, analyze(c["text"], lvl))
    if e:
        n += 1
        print(c["id"], c["category"], c["text"], "|", [(x["type"], x.get("anchor"), x.get("got")) for x in e])
print("FAILED_CONTRACTS", n)
