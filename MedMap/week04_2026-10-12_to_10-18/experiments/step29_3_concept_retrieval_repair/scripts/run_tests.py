"""tests/test_*.py(unittest) 실행 → outputs/unit_tests.json(파일별 tests·failures·errors·실패 메시지) + 테스트 문장과 HOLDOUT 문장 겹침 검사."""
import io
import json
import re
import sys
import unittest
from pathlib import Path

T = Path(__file__).resolve().parents[1] / "tests"
sys.path.insert(0, str(T))
res = {}
for f in sorted(T.glob("test_*.py")):
    suite = unittest.defaultTestLoader.loadTestsFromName(f.stem)
    buf = io.StringIO()
    r = unittest.TextTestRunner(stream=buf, verbosity=1).run(suite)
    res[f.stem] = {"tests": r.testsRun, "failures": len(r.failures), "errors": len(r.errors),
                   "messages": [str(x[1])[-600:] for x in r.failures + r.errors]}
import s293_common as S  # noqa: E402

hold = {S.ko_key(c["text"]) for c in json.loads((S.DATA / "frozen_evaluation_cases.json").read_text(encoding="utf-8"))["cases"]}
strs = {s for f in T.glob("test_*.py") for s in re.findall(r'"([가-힣][^"]{1,40})"', f.read_text(encoding="utf-8"))}
overlap = sorted(s for s in strs if S.ko_key(s) in hold)
out = Path(__file__).resolve().parents[1] / "outputs/unit_tests.json"
out.write_text(json.dumps({"by_file": res, "test_strings_in_frozen": overlap}, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: (v["tests"], v["failures"], v["errors"]) for k, v in res.items()}, ensure_ascii=False), "holdout_overlap", overlap)
