"""EXP-01 유효성 검사(manifest rev5 secondary_metrics·failure_criterion). 위반은 Exp01Invalid.

(a) 근거 집합 일치: 우도·특징에 들어간 (질문, 답) == observe 로 받은 답 중 들어가야 할 것
(b) 독립 참조 점수기: 관측 집합만으로 그래프 사후확률을 다시 계산해 수치 대조(1e-9)
(c) 숨은 기록 누출: 묻지 않은 자식 없는 이진 근거 1개를 뒤집은 복제 사례와 경로·순위 비교
(d) 정적 검사: 탐색기·우도 모듈 소스에 금지 문자열·평가 모듈 import 가 없어야 함
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import numpy as np

from core import NA, Exp01Invalid, run_case
from searchers import GraphSearcher, expected_used

STATIC_FORBIDDEN = ("release_conditions", "severity", "DIFFERENTIAL", "PATHOLOGY", "release_validate", "release_test")
STATIC_FORBIDDEN_IMPORTS = ("metrics", "severity_eval")
SEARCH_MODULES = ("searchers.py", "likelihood.py")   # core.py 는 금지 키 목록 자체를 담으므로 제외


def check_evidence_set(searcher) -> None:
    st = searcher.stats()
    used = set(st["used"])
    if isinstance(searcher, GraphSearcher):
        exp = expected_used(st["observed"], searcher.use_negative)
    else:   # A·B: 받은 답 전부가 모델 인코딩·트리 경로에 들어가야 한다(그 밖의 근거는 없어야 한다)
        exp = {(q, a) for q, a in st["observed"].items()}
    if used != exp:
        raise Exp01Invalid(f"EXP01_EVIDENCE_SET_MISMATCH:extra={sorted(used - exp)[:3]},missing={sorted(exp - used)[:3]}")


def reference_logpost(lik, observed: dict, use_negative: bool) -> np.ndarray:
    """그래프 계열 독립 참조 점수기 — 탐색기 코드를 쓰지 않고 관측만으로 다시 계산."""
    lp = np.log(lik.prior).astype(np.float64)
    for q, ans in observed.items():
        if ans == NA or ans == ("UNKNOWN",):      # 모름(응답 잡음 민감도)은 우도 미반영(manifest ablations)
            continue
        if ans == ("NEG",) and not use_negative:
            continue
        for a in ans:
            lp = lp + np.log(lik.table[q][:, lik.col[q][a]])
    return lp


def check_reference(searcher, lik, tol=1e-9) -> None:
    ref = reference_logpost(lik, searcher.stats()["observed"], searcher.use_negative)
    if not np.allclose(ref, searcher.scores(), atol=tol, rtol=0):
        raise Exp01Invalid("EXP01_REFERENCE_SCORER_MISMATCH")


def leaf_binary_unasked(sem, asked: set, key: str):
    """자식 없는 이진 근거 중 묻지 않은 것 1개를 사례 키 해시로 고정 선택."""
    has_child = set(sem.parent.values())
    opts = sorted((q for q in sem.qids if sem.dtype[q] == "B" and q not in has_child and q not in asked
                   and sem.safe.get(q, True)), key=lambda q: int(q[2:]))
    if not opts:
        return None
    return opts[int(hashlib.sha256(f"EXP01LEAK|{key}".encode()).hexdigest()[:8], 16) % len(opts)]


def check_hidden_leak(make_searcher, sem, case: dict, budget: int, key: str, wd=None) -> bool | None:
    """True=통과, None=뒤집을 대상 없음. 위반이면 Exp01Invalid."""
    tr1, s1 = run_case(make_searcher(), sem, case["initial"], case["age"], case["sex"], case["tokens"], budget, wd)
    q = leaf_binary_unasked(sem, set(tr1.asked) | {case["initial"]}, key)
    if q is None:
        return None
    toks = list(case["tokens"])
    base = {t.partition("_@_")[0] for t in toks}
    toks = [t for t in toks if t.partition("_@_")[0] != q] if q in base else toks + [q]
    tr2, s2 = run_case(make_searcher(), sem, case["initial"], case["age"], case["sex"], toks, budget, wd)
    if tr1.asked != tr2.asked or not np.array_equal(s1.scores(), s2.scores()):
        raise Exp01Invalid(f"EXP01_HIDDEN_RECORD_LEAK:{q}")
    return True


def static_check(src_dir: Path, modules=SEARCH_MODULES) -> None:
    for m in modules:
        text = (Path(src_dir) / m).read_text(encoding="utf-8")
        import io
        import tokenize
        toks = [t for t in tokenize.generate_tokens(io.StringIO(text).readline) if t.type != tokenize.COMMENT]
        code_only = tokenize.untokenize(toks)                      # 인라인 주석 포함 모든 주석 제거(독립 감사 MINOR)
        tree = ast.parse(text)
        doc_ranges = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and ast.get_docstring(node):
                doc_ranges.add(ast.get_docstring(node))
        for ds in doc_ranges:
            code_only = code_only.replace(ds, "")
        for s in STATIC_FORBIDDEN:
            if s in code_only:
                raise Exp01Invalid(f"EXP01_STATIC_FORBIDDEN:{m}:{s}")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for n in names:
                if n.split(".")[0] in STATIC_FORBIDDEN_IMPORTS:
                    raise Exp01Invalid(f"EXP01_STATIC_FORBIDDEN_IMPORT:{m}:{n}")
