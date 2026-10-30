"""tests/ 전체 unittest 실행(pytest 없음 — 설치 금지). 출력: outputs/unit_tests.json(시간 값 없음 — 재현 비교용)."""
from __future__ import annotations

import io
import sys
import unittest

import s30_common as S


def main():
    sys.path.insert(0, str(S.STEP / "tests"))
    suite = unittest.defaultTestLoader.discover(str(S.STEP / "tests"), pattern="test_*.py")
    buf = io.StringIO()
    res = unittest.TextTestRunner(stream=buf, verbosity=2).run(suite)
    names = sorted(line.split(" ... ")[0] for line in buf.getvalue().splitlines() if " ... " in line)
    out = {"tests_run": res.testsRun, "failures": [str(t[0]) for t in res.failures], "errors": [str(t[0]) for t in res.errors],
           "PASS": res.wasSuccessful(), "tests": names, "files": sorted(p.name for p in (S.STEP / "tests").glob("test_*.py"))}
    S.dump_json(S.OUT / "unit_tests.json", out)
    print(S.dumps({k: out[k] for k in ("tests_run", "failures", "errors", "PASS")}))
    sys.exit(0 if out["PASS"] else 1)


if __name__ == "__main__":
    main()
