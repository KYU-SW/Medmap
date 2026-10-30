"""§12 평가 문장 중복 확인(NLU 실행 전). INTEGRATION_NEW 문장이 이전 단계(STEP20–29.3) data/ 의 어떤 문자열과도 같지 않은지(공백 제거 비교) 확인.
출력: outputs/case_overlap.json. 겹치면 실패(종료 코드 1) — 평가 실행 전에 문장을 바꾼다."""
from __future__ import annotations

import csv
import json
import sys

import s30_common as S


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def main():
    csv.field_size_limit(1 << 30)
    seen, nfiles = set(), 0
    for d in sorted((S.REPO / "exp").iterdir()):
        if not (d.is_dir() and d.name.startswith("step2") and d.name != S.STEP.name):
            continue
        for f in list(d.rglob("data/**/*.json")) + list(d.rglob("data/**/*.csv")) + list(d.rglob("data/*.json")) + list(d.rglob("data/*.csv")):
            try:
                if f.suffix == ".json":
                    ss = strings(json.loads(f.read_text(encoding="utf-8")))
                else:
                    with open(f, encoding="utf-8", newline="") as fh:
                        ss = [c for row in csv.reader(fh) for c in row]
            except Exception:
                continue
            nfiles += 1
            for s in ss:
                if 3 <= len(s) <= 200:
                    seen.add(S.nospace(s))
    cases = S.load_json(S.DATA / "integration_contract_cases.json")["cases"]
    hits = [{"id": c["id"], "set": c["set"], "text": c["text"]} for c in cases if S.nospace(c["text"]) in seen]
    new_hits = [h for h in hits if h["set"] == "INTEGRATION_NEW"]
    res = {"prior_files_scanned": nfiles, "prior_unique_strings": len(seen), "cases": len(cases),
           "overlap_all": hits, "overlap_integration_new": new_hits, "PASS": not new_hits,
           "note": "REGRESSION_EXPOSED(지시문 §11 사례)는 노출 회귀용 — 겹쳐도 됨. INTEGRATION_NEW 만 겹치면 안 됨(완전 일치·공백 제거 기준, 의미 유사는 미검사)."}
    S.dump_json(S.OUT / "case_overlap.json", res)
    print(S.dumps({k: res[k] for k in ("prior_files_scanned", "prior_unique_strings", "PASS")}), [h["id"] for h in hits])
    sys.exit(0 if res["PASS"] else 1)


if __name__ == "__main__":
    main()
