"""테스트가 실제 구현 오류를 잡는지 확인하는 소규모 변이 검사(핵심 성질당 1개). 원본은 바꾸지 않고 임시 사본에서 실행.
실행: ~/ai_env/bin/python -B tests/mutation_check.py <임시 폴더>"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
MUTANTS = [
    ("M01 미기록=음성", "st = obs.status if obs else Status.NOT_RECORDED\n    eid", "st = obs.status if obs else Status.NEGATIVE\n    eid"),
    ("M02 지지 = 경로 수(중복 계산)", "return len(self.support_groups)", "return sum(1 for p in self.paths if p.state == 'SUPPORTS')"),
    ("M03 DEPENDS_ON 무시", 'for r in ("DEPENDS_ON", "IS_A") for x in', 'for r in ("IS_A",) for x in'),
    ("M04 AND 에서 미확정=참", "states and all(s == RuleState.SATISFIED for s in states)", "states and all(s != RuleState.UNMET for s in states)"),
    ("M05 적용 조건 무시", "gate_state == RuleState.UNMET, tuple(body)", "False, tuple(body)"),
    ("M06 반박 관계=뒷받침", 'if e.rel == "ARGUES_AGAINST":\n            st', 'if False:\n            st'),
    ("M07 재계산이 규칙 경유 누락", 'elif k == "RULE" or e.rel in ("DEPENDS_ON", "IS_A"):', 'elif e.rel in ("DEPENDS_ON", "IS_A"):'),
    ("M08 설명 부족을 충돌로", "conflicting = de.conflicts\n", "conflicting = de.conflicts + tuple(p for p in de.paths if p.state in ('NEGATED', 'UNKNOWN'))\n"),
    ("M09 음성만으로 질환 제거", "            out[d] = eval_disease(g, d, view, rule_cache)\n",
     "            out[d] = eval_disease(g, d, view, rule_cache)\n            if out[d].negated and not out[d].support_nodes:\n                del out[d]\n"),
    ("M10 시점 무시(미래 정보)", "view = with_is_a(g, pr.view(as_of))\n    rule_cache", "view = with_is_a(g, pr.view(float('inf')))\n    rule_cache"),
    ("M11 범주값 불일치=일치", 'if obs.value in spec["values"] else', 'if True else'),
    ("M12 적용 조건을 설명 대상에 포함", 'if outs and all(e.rel in ("GATES", "DEPENDS_ON") for e in outs):', 'if False:'),
    ("M13 IS_A 의존 묶음 누락(중복 계산)", 'for r in ("DEPENDS_ON", "IS_A") for x in', 'for r in ("DEPENDS_ON",) for x in'),
    ("M14 IS_A 를 하위로도 전파", '            for e in g.out_edges(cur, "IS_A"):\n', '            for e in [type(x)(x.dst, x.rel, x.src, x.tier, x.source, x.spec) for x in g.in_edges(cur, "IS_A")]:\n'),
    ("M15 하위 개념 연결을 설명 불가로", '        elif narrower:\n', '        elif False:\n'),
]


def run_tests(d: Path):
    dev = sorted((SRC / "outputs").glob("dev_cases_*/dev_cases.json"))[-1]
    env = dict(os.environ, EXP01B_MAIN_AI=str(SRC.parent / "main_ai"), EXP01B_DEV_CASES=str(dev))
    return subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-k", "T0", "-k", "test_real"],
                          cwd=d, capture_output=True, text=True, env=env, timeout=300)


def main(tmp: Path) -> int:
    ctrl = tmp / "CONTROL"
    if ctrl.exists():
        shutil.rmtree(ctrl)
    shutil.copytree(SRC, ctrl, ignore=shutil.ignore_patterns("outputs", "__pycache__"))
    r = run_tests(ctrl)
    print(f"CONTROL(변이 없음): {'PASS' if r.returncode == 0 else 'FAIL'} ({r.stderr.strip().splitlines()[-1]})")
    if r.returncode != 0:
        print(r.stderr[-2000:])
        return 2                                   # 대조가 실패하면 변이 결과는 무효
    fails = 0
    for name, old, new in MUTANTS:
        d = tmp / name.split()[0]
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(SRC, d, ignore=shutil.ignore_patterns("outputs", "__pycache__"))
        f = d / "graph_engine.py"
        s = f.read_text(encoding="utf-8")
        if s.count(old) != 1:
            print(f"{name}: PATTERN_NOT_UNIQUE({s.count(old)})")
            fails += 1
            continue
        f.write_text(s.replace(old, new), encoding="utf-8")
        try:
            r = run_tests(d)
        except subprocess.TimeoutExpired:
            print(f"{name}: TIMEOUT(검출로 세지 않음)", flush=True)
            fails += 1
            continue
        tail = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ""
        killed = r.returncode != 0 and "ImportError" not in r.stderr and "SyntaxError" not in r.stderr
        print(f"{name}: {'KILLED' if killed else 'SURVIVED'} ({tail})", flush=True)
        fails += not killed
    print(f"survived_or_invalid={fails}/{len(MUTANTS)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
