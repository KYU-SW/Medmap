"""EXP-01(EXP-MAI-001) 실행기 — 독립 감사(2026-10-27) M1~M6 반영판.

실행 인자는 설정 파일(JSON)에서만 읽는다(M6). 실데이터 분할(SELECT_SMOKE/SELECT/FINAL)은 RG RUN + --approved 필요.
FINAL 은 잠금 파일 {"config_sha256": 실행 잠금 해시, "config_path": 동결 config} 와 FinalGuard 를 통과해야 하고,
끝나면 확인적 분석(confirm.final_analysis)을 바로 계산해 comparisons.csv·final_judgement.json 을 쓴다(M2).
SELECT 는 τ 선택 규칙(metrics.select_tau)을 적용해 tau_selection.json 을 쓴다(M3). SMOKE 의 τ 표는 EXPLORATORY.
산출물 7종 + summary.json 은 artifacts.write_all (M5).

사용(worktree 루트):
  ~/ai_env/bin/python exp/main_ai/exp01_symptom_graph/run_exp01.py --config <cfg.json> --out <새 폴더> [--approved]
  FINAL: ... --config <동결 cfg> --final-lock <lock.json> --approved --out <새 폴더>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import artifacts  # noqa: E402
import checks  # noqa: E402
import metrics as mt  # noqa: E402
from core import NEG, NoisySimulator, run_case  # noqa: E402
from searchers import BaselineASearcher, GraphSearcher, TreeSearcher  # noqa: E402

GRAPH = ("C", "PA", "PB_REL", "PB", "PC")
TAU_GRID = (1e-2, 1e-3, 1e-4)
WD_MODES = ("WD_CORRECT", "WD_MODEL", "WD_MODEL_WRONG", "WD_RANDOM_WRONG")
RG = Path.home() / ".claude/research-guardian/bin/rg.py"
ROOT = HERE.parents[2]
CODE_SCOPE = HERE.parent                                   # exp/main_ai (manifest 잠금 범위)
SPLITS = ("SYNTHETIC", "SELECT_SMOKE", "SELECT", "FINAL")
DEFAULT_CONFIG = {
    "experiment_id": "EXP-MAI-001", "budgets": [3, 5, 10], "seeds": [42, 43, 44], "taus": list(TAU_GRID),
    "leak_check": True,
    "noise": {"budget": 5, "models": ["C", "PA"],
              "modes": [["flip", 0.05], ["flip", 0.10], ["uncertain", 0.05], ["uncertain", 0.10]]},
}


def load_config(path) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    if cfg.get("experiment_id") != "EXP-MAI-001" or cfg.get("split") not in SPLITS:
        raise SystemExit("EXP01_BAD_CONFIG")
    if cfg["split"] == "FINAL":
        if "tau_selected" not in cfg:
            raise SystemExit("EXP01_FINAL_CONFIG_NEEDS_TAU_SELECTED")
        cfg["taus"] = [None if cfg["tau_selected"] == "TAU_FAIL" else float(cfg["tau_selected"])]
    if list(cfg["seeds"]) != [42, 43, 44]:
        raise SystemExit("EXP01_SEEDS_MUST_BE_42_43_44")      # H3b(manifest) 요건, 순서 고정(트리 seed = 42)
    if cfg["split"] == "SELECT" and [float(x) for x in cfg["taus"]] != list(TAU_GRID):
        raise SystemExit("EXP01_SELECT_TAUS_MUST_BE_GRID")
    if cfg["split"] in ("SELECT", "FINAL"):                  # 사전등록 요건을 코드로 강제(재감사 N2)
        if cfg.get("leak_check") is not True:
            raise SystemExit("EXP01_LEAK_CHECK_REQUIRED")
        if list(cfg["budgets"]) != [3, 5, 10]:
            raise SystemExit("EXP01_BUDGETS_MUST_BE_3_5_10")
    check_parallel(cfg.get("parallel"))
    return cfg


def check_parallel(par):
    """실행 방식(2026-10-28 병렬화). 결과에 영향 없는 실행 인자 — 설정 JSON 에서만(M6). 없으면 기존 직렬 경로."""
    if par is None:
        return
    if (not isinstance(par, dict) or set(par) != {"workers", "chunk_cases"}
            or not all(type(par[k]) is int for k in par) or not 1 <= par["workers"] <= 12 or par["chunk_cases"] < 1):
        raise SystemExit("EXP01_BAD_PARALLEL_CONFIG")


def wd_for(mode, case, classes, a_rank, seed):
    """WD 생성. DIFFERENTIAL 미사용. PATHOLOGY 는 오답 조건 정의에만."""
    truth = case["truth"]
    if mode == "WD_CORRECT":
        return truth
    if mode == "WD_MODEL":
        return a_rank[0]
    if mode == "WD_MODEL_WRONG":
        return next(c for c in a_rank if c != truth)
    others = [c for c in classes if c != truth]
    return others[int(hashlib.sha256(f"{seed}|{case['row_index']}".encode()).hexdigest()[:8], 16) % len(others)]


def _ranks_all(sc):
    """각 질환의 비관적 순위(평가 전용)."""
    sc = np.asarray(sc, dtype=np.float64)
    return np.array([1 + int((sc > v).sum()) + int((sc == v).sum() - 1) for v in sc])


def evaluate(cases, sem, lik, classes, budgets, taus, seeds=(42, 43, 44), tree=None, a_factory=None, wd_rank=None,
             leak_check=True, aref=None, noise=None, counters=None):
    """사례별 기록. 탐색기에는 initial·age·sex·wd 만 간다(differential·novel·truth 는 평가 전용).
    taus 에 None 이 있으면 PB(None)=가지치기 없음, PC(None)=PB_REL+WD (TAU_FAIL 경로, M3)."""
    cidx = {c: i for i, c in enumerate(classes)}
    counters = counters if counters is not None else {"aref_steps": 0, "reference_steps": 0}
    recs = []
    for case in cases:
        t = cidx[case["truth"]]
        rank0 = wd_rank(case) if wd_rank is not None else None
        for Q in budgets:
            plans = [(m, None, None, None, None) for m in ("C", "PA", "PB_REL")]
            plans += [("PB", None, None, tv, None) for tv in taus]
            if rank0 is not None:
                for tv in taus:
                    for mode in WD_MODES:
                        for sd in (seeds if mode == "WD_RANDOM_WRONG" else seeds[:1]):
                            plans.append(("PC", mode, (sd, wd_for(mode, case, classes, rank0, sd)), tv, None))
            if tree is not None:
                plans.append(("B", None, None, None, None))
            if a_factory is not None:
                plans.append(("A", None, None, None, None))
            if noise and Q == noise["budget"]:
                for m in noise["models"]:
                    for md, p in noise["modes"]:
                        plans.append((m, None, None, None, (md, p)))
            for model, mode, wdinfo, tau, nz in plans:
                if model in GRAPH:
                    make = (lambda m=model, ut=tau, q=Q: GraphSearcher(lik, sem, m, q, ut))
                elif model == "B":
                    make = (lambda q=Q: TreeSearcher(tree[0], tree[1], tree[2], len(classes), q))
                else:
                    make = (lambda q=Q: BaselineASearcher(a_factory, q))
                wd = wdinfo[1] if wdinfo else None
                st_ = {"first5": None, "check_s": 0.0, "prev": None, "neg_e": 0, "neg_h": 0, "init_top1": None}
                def on_step(s, k, st=st_):
                    c0 = time.perf_counter()
                    sc = s.scores()
                    if st["first5"] is None and mt.in_topk(sc, t, 5):
                        st["first5"] = k
                    if isinstance(s, GraphSearcher):
                        checks.check_reference(s, lik)
                        counters["reference_steps"] += 1
                        if k == 0:
                            st["init_top1"] = classes[int(np.argmax(sc))]
                        if k > 0 and st["prev"] is not None:
                            q_last = list(s.observed)[-1]
                            if s.observed[q_last] == NEG and q_last in lik.p_pos:
                                hi = np.where(lik.p_pos[q_last] >= 0.9)[0]
                                if len(hi):
                                    st["neg_e"] += 1
                                    st["neg_h"] += int(_ranks_all(sc)[hi].mean() > _ranks_all(st["prev"])[hi].mean())
                        st["prev"] = sc
                    elif aref is not None and isinstance(s, BaselineASearcher):
                        aref.check_step(s, case["age"], case["sex"])
                        counters["aref_steps"] += 1
                    st["check_s"] += time.perf_counter() - c0
                sim = None
                if nz is not None:
                    sim = NoisySimulator(sem, case["tokens"], nz[0], nz[1], str(case["row_index"]))
                t0 = time.perf_counter()
                tr, s = run_case(make(), sem, case["initial"], case["age"], case["sex"], case["tokens"], Q, wd,
                                 on_step=on_step, sim=sim)
                ms = (time.perf_counter() - t0 - st_["check_s"]) * 1000          # 검사 시간 제외(MINOR)
                if nz is None:
                    checks.check_evidence_set(s)
                sc = s.scores()
                rank = mt.truth_rank_pessimistic(sc, t)
                post = s.posterior()
                oh = np.zeros(len(classes))
                oh[t] = 1
                gap = float(sc[t] - sc.max()) if model in GRAPH else None
                wterm = mt.wrong_termination_tree(sc, t) if model == "B" else None
                leak = "SKIP"
                if leak_check and nz is None:
                    res = checks.check_hidden_leak(make, sem, case, Q, f"{case['row_index']}|{model}|{Q}", wd)
                    leak = "PASS" if res else "NA"                         # 위반이면 예외로 중단(MINOR: 의미 명시)
                ranks = _ranks_all(sc)
                diff = case.get("differential")
                dr = (float(sum(p for n, p in diff if n in cidx and ranks[cidx[n]] <= 8)) / max(sum(p for _, p in diff), 1e-12)
                      if diff else None)
                stt = s.stats()
                recs.append({
                    "row_index": case["row_index"], "truth": case["truth"], "model": model, "budget": Q,
                    "wd_mode": mode, "seed": wdinfo[0] if wdinfo else None, "tau": tau,
                    "noise": None if nz is None else f"{nz[0]}:{nz[1]}", "rank": rank, "top1": rank <= 1,
                    "top3": rank <= 3, "top5": rank <= 5, "in8": rank <= 8, "p_top1": float(post.max()),
                    "top1_correct": bool(int(np.argmax(post)) == t), "brier": float(((post - oh) ** 2).sum()),   # ECE 정답 = argmax(통계 gate5 MINOR)
                    "n_questions": len(tr.asked), "first_top5_step": st_["first5"], "counter": stt.get("counter"),
                    "ms": ms, "truth_gap": gap, "wrong_term": wterm, "prune_steps": stt.get("prune_steps"),
                    "cand_steps": stt.get("cand_steps"), "reactivations": stt.get("reactivations"),
                    "neg_events": st_["neg_e"] if model in GRAPH else None,
                    "neg_hits": st_["neg_h"] if model in GRAPH else None, "init_top1": st_["init_top1"], "wd": wd,
                    "diff_recall": dr, "novel": case.get("novel"), "age": case["age"], "sex": case["sex"], "leak": leak})
    return recs


def summarize(recs, severe: frozenset, taus=()):
    """기술 통계(예비·선택 평가용). 확인적 판정 아님 — artifacts.metrics_rows 와 같다."""
    return artifacts.metrics_rows(recs, severe, taus)


def rg_status_ok():
    out = subprocess.run([sys.executable, str(RG), "status", "--exp", "EXP-MAI-001", "--json"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    try:
        st = json.loads(out)
    except json.JSONDecodeError:
        return False
    return st.get("review_status") == "RUN" and st.get("lock", {}).get("state") == "OK"


def rg_lock_state():
    out = subprocess.run([sys.executable, str(RG), "status", "--exp", "EXP-MAI-001", "--json"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    try:
        st = json.loads(out)
    except json.JSONDecodeError:
        return None
    return {"review_status": st.get("review_status"), "lock": st.get("lock")}


def package_versions():
    import pandas
    import scipy
    import sklearn
    return {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pandas.__version__,
            "scikit_learn": sklearn.__version__, "scipy": scipy.__version__}


def run_real(cfg):
    """실데이터 배선. TRAIN16 결정 트리 학습·STEP16B 모델 로드가 여기서 일어난다(승인된 실행에서만)."""
    import pickle

    import data
    import repro
    import severity_eval
    from aref import AReference
    from likelihood import GraphLikelihood
    from searchers import build_b_features, encode_b, fit_baseline_b
    split = cfg["split"]
    c, df, asg, rep, classes, prior = data.load_all()
    sem = c.Semantics()
    lik = GraphLikelihood.from_npz(data.IG_NPZ, sem.answer_space, prior)
    if lik.classes != classes:
        raise RuntimeError("EXP01_CLASS_ORDER_MISMATCH")
    names, ev_index = build_b_features(sem)
    trn = df[df.row_index.map(lambda r: asg[int(r)] == "TRAIN16")]
    X = np.stack([encode_b(names, {t.partition("_@_")[0] for t in toks}, ag, sx).astype(np.uint8)
                  for toks, ag, sx in zip(trn.tokens, trn.AGE, trn.SEX)])
    tree = fit_baseline_b(X, trn.PATHOLOGY.values, classes, seed=42)               # manifest seed 42 고정
    if str(Path.home() / "medmap") not in sys.path:
        sys.path.insert(0, str(Path.home() / "medmap"))
    from medmap.diagnosis import DiagnosisEngine
    from medmap.evidence import EvidenceCatalog
    from medmap.next_information import NextInformationEngine
    from medmap.patient_state import PatientState
    cat = EvidenceCatalog()
    engines = {k: DiagnosisEngine(cat, k) for k in ("k3", "k5", "k10")}
    def a_factory(ctx, max_q):
        return NextInformationEngine(engines[ctx], cat, max_questions=max_q)
    def wd_rank(case):
        st = PatientState.new(age=case["age"], sex=case["sex"], initial_evidence=case["initial"])
        return [c_ for c_, _ in engines["k3"].diagnose(st).ranking]
    models = {k: pickle.load(open(c.guarded_path(f"{data.sr.S16B_DIR}/model_k{k}.pkl"), "rb")) for k in (3, 5, 10)}
    z = np.load(data.IG_NPZ, allow_pickle=True)
    aref = AReference(c, sem, models, {k: z[k] for k in z.files if k != "__classes__"}, classes)   # M1
    tprof = data.train_profiles(df, asg)
    cs = list(data.cases(df, asg, split, tprof))
    severe = severity_eval.load_severe()
    repro_report = None
    if split == "SELECT_SMOKE":
        ref = repro.load_reference({x["row_index"] for x in cs})
        repro_report = repro.check(repro.make_predict(c, sem, models, classes), cs, ref)
    counters = {"aref_steps": 0, "reference_steps": 0}
    par_info = None
    if cfg.get("parallel") is None:
        recs = evaluate(cs, sem, lik, classes, cfg["budgets"], cfg["taus"], tuple(cfg["seeds"]),
                        tree=(tree, names, ev_index), a_factory=a_factory, wd_rank=wd_rank,
                        leak_check=cfg.get("leak_check", True), aref=aref, noise=cfg.get("noise"), counters=counters)
    else:
        import gc

        import parallel
        del df, trn, X, tprof, asg                     # 작업자에게 전체 데이터프레임이 복제되지 않게 fork 전에 해제
        gc.collect()
        recs, counters, _, par_info = parallel.evaluate_parallel(
            sorted(cs, key=lambda x: x["row_index"]), cfg["parallel"]["workers"], cfg["parallel"]["chunk_cases"],
            budgets=cfg["budgets"], taus=cfg["taus"], seeds=tuple(cfg["seeds"]), tree=(tree, names, ev_index),
            a_factory=a_factory, wd_rank=wd_rank, leak_check=cfg.get("leak_check", True), aref=aref,
            noise=cfg.get("noise"), sem=sem, lik=lik, classes=classes, progress=parallel.log)
        cs = sorted(cs, key=lambda x: x["row_index"])
    split_man = dict(rep)
    split_man["evaluated_split"] = split
    split_man["evaluated_rows"] = len(cs)
    split_man["evaluated_index_sha256"] = data.profile_hash([x["row_index"] for x in cs])
    split_man["severe_n_by_disease"] = {d: sum(1 for x in cs if x["truth"] == d) for d in sorted(severe)}
    split_man["severe_diseases_n_ge_100"] = sum(1 for v in split_man["severe_n_by_disease"].values() if v >= 100)
    split_man["novel_rows"] = sum(1 for x in cs if x["novel"])
    import data as _d
    extra = {"baseline_a_repro_step16b_path": repro_report, "baseline_a_eval_path_checks": counters["aref_steps"],
             "baseline_a_eval_path_max_abs_diff": aref.max_abs_diff,
             "graph_reference_checks": counters["reference_steps"],
             "input_sha256": {"release_train_patients": _d.TRAIN_SHA256, "release_evidences.json": _d.EVIDENCES_SHA256,
                              "verified": True}}
    if par_info is not None:
        extra["parallel"] = par_info
    return recs, severe, prior, classes, lik, split_man, extra, severity_eval.condition_edges()


OUTPUTS = HERE / "outputs"                                  # 실행 산출물 루트(FINAL 시도 흔적 검사 범위)
FINAL_ATTEMPT_FILE = "final_attempt.json"
FINAL_LEDGER = "FINAL_ATTEMPTS.jsonl"
FINAL_STATUS_FILE = "final_status.jsonl"                    # 시도 상태 기록(STARTED/EVALUATED/FAILED/COMPLETED, 진행 로그)
FINAL_PRE_METRIC_FILES = frozenset({FINAL_ATTEMPT_FILE, "run_meta.json", FINAL_STATUS_FILE})  # manifest: run_meta·진행 로그 외 = 지표
FINAL_LOCK_FILE = "FINAL.lock"                              # 운영체제 파일 잠금(flock) — FINAL 허가~프로세스 끝까지 보유
_FINAL_LOCK: dict = {}
_FINAL_RUN: dict = {}


def _is_env_error(e) -> bool:
    """사전등록 '환경 이유' 로 인정하는 실패(분류표 고정): 메모리 부족·작업자 비정상 종료·구간 시간 초과·
    자원 계열 OSError(ENOSPC·ENOMEM·EIO·EMFILE·ENFILE·EDQUOT·EAGAIN·ETIMEDOUT). 파일 없음·권한 등 설정성 OSError 는 비환경."""
    import errno
    from concurrent.futures.process import BrokenProcessPool
    if isinstance(e, (MemoryError, BrokenProcessPool, TimeoutError)):
        return True
    if isinstance(e, (FileNotFoundError, PermissionError, IsADirectoryError, NotADirectoryError)):
        return False
    env_errno = {errno.ENOSPC, errno.ENOMEM, errno.EIO, errno.EMFILE, errno.ENFILE, errno.EDQUOT, errno.EAGAIN,
                 errno.ETIMEDOUT}
    return isinstance(e, OSError) and e.errno in env_errno


def _proc_start(pid):
    """프로세스 시작 시각(/proc/<pid>/stat 22번째) — PID 재사용과 구분. 없으면 None."""
    try:
        with open(f"/proc/{int(pid)}/stat", encoding="utf-8") as fh:
            return fh.read().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError, ValueError, TypeError):
        return None


def final_status_append(d, event, **kw):
    """시도 상태를 append-only 로 기록(flush+fsync). 지우거나 고치지 않는다."""
    rec = {"event": event, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "pid": os.getpid(), **kw}
    with open(Path(d) / FINAL_STATUS_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def final_status_read(d):
    """상태 기록 목록. 파일 없음 → [], 판독 불가 → None."""
    p = Path(d) / FINAL_STATUS_FILE
    if not p.exists():
        return []
    try:
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    except ValueError:
        return None


def final_lock_acquire(root):
    """FINAL 허가 구간을 운영체제 파일 잠금으로 직렬화(같은 outputs 루트의 다른 프로세스는 즉시 거부). 프로세스 종료 시 커널이 해제.
    같은 프로세스 안의 재호출은 이미 잡은 잠금을 그대로 쓴다."""
    import fcntl
    root = Path(root).resolve()
    if _FINAL_LOCK.get("root") == root:
        return
    if not root.is_dir():
        raise SystemExit("EXP01_FINAL_OUTPUTS_ROOT_MISSING")
    fd = os.open(root / FINAL_LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise SystemExit("EXP01_FINAL_LOCKED_BY_ANOTHER_PROCESS") from None
    try:
        same = os.fstat(fd).st_ino == os.stat(root / FINAL_LOCK_FILE).st_ino   # 잠금 파일 바꿔치기·삭제 감지(리뷰 MINOR-1)
    except OSError:
        same = False
    if not same:
        os.close(fd)
        raise SystemExit("EXP01_FINAL_LOCK_FILE_REPLACED")
    _FINAL_LOCK.update(root=root, fd=fd)


def final_lock_release():
    fd = _FINAL_LOCK.pop("fd", None)
    _FINAL_LOCK.pop("root", None)
    if fd is not None:
        os.close(fd)


def final_retry_check(ev, reason):
    """환경 오류 재시도 허가 조건(manifest test_population). 모두 충족해야 (None, 근거), 아니면 (거부 코드, None).
    이전 시도마다: 결과 파일 없음 · 표지·상태 판독 가능 · 그 프로세스 종료됨 · 마지막 상태 FAILED 이고 환경 오류."""
    if not reason or not str(reason).strip():
        return "EXP01_FINAL_RETRY_NEEDS_REASON", None
    if ev["metrics_written"]:
        return "EXP01_FINAL_RETRY_METRICS_EXIST", None
    if not ev["attempts"]:
        return "EXP01_FINAL_RETRY_NO_ATTEMPT_RECORD", None              # 시도 기록 없음 = 상태 불명
    evidence = []
    for d in ev["attempts"]:
        try:
            att = json.loads((Path(d) / FINAL_ATTEMPT_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return f"EXP01_FINAL_RETRY_STATE_UNCLEAR:NO_ATTEMPT_FILE:{Path(d).name}", None
        st = final_status_read(d)
        if st is None:
            return f"EXP01_FINAL_RETRY_STATE_UNCLEAR:STATUS_UNREADABLE:{Path(d).name}", None
        if att.get("pid") is None or att.get("proc_start") is None:
            return f"EXP01_FINAL_RETRY_STATE_UNCLEAR:NO_PID:{Path(d).name}", None
        same_proc_done = att["pid"] == os.getpid() and _FINAL_RUN.get("dir") is None   # 이 프로세스에서 이미 끝난 시도(main 은 동기)
        if _proc_start(att["pid"]) == att["proc_start"] and not same_proc_done:
            return f"EXP01_FINAL_RETRY_PREVIOUS_IN_PROGRESS:{Path(d).name}", None
        last = st[-1] if st else {}
        if last.get("event") == "COMPLETED":
            return f"EXP01_FINAL_RETRY_PREVIOUS_COMPLETED:{Path(d).name}", None
        if last.get("event") != "FAILED":
            return f"EXP01_FINAL_RETRY_STATE_UNCLEAR:{last.get('event')}:{Path(d).name}", None   # 강제 종료 등
        if last.get("environmental") is not True:
            return f"EXP01_FINAL_RETRY_NOT_ENVIRONMENTAL:{last.get('error_type')}:{Path(d).name}", None
        evidence.append({"attempt": str(d), "failed": last})
    return None, evidence


def final_evidence(outputs_root) -> dict:
    """이전 FINAL 시도 흔적을 출력 폴더에서 실제로 검사(독립 검증 M-1, manifest test_population).
    시도 폴더 = 장부(FINAL_ATTEMPTS.jsonl)에 적힌 폴더 ∪ final_attempt.json 이 있는 폴더 ∪ run_meta/summary 의 split 이 FINAL 인 폴더.
    metrics_written = 시도 폴더에 run_meta·시도 표지 외 파일이 하나라도 있음. 판독 불가·장부 손상·장부 폴더 소실은 True(안전 쪽 차단)."""
    root = Path(outputs_root)
    paths, written, why = set(), False, []
    ledger = root / FINAL_LEDGER
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                paths.add(Path(json.loads(line)["out"]).resolve())
            except (ValueError, KeyError, TypeError):
                written = True
                why.append("LEDGER_UNREADABLE")
    for d in (sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []):
        if (d / FINAL_ATTEMPT_FILE).exists():
            paths.add(d.resolve())
            continue
        for f in ("run_meta.json", "summary.json"):
            fp = d / f
            if not fp.exists():
                continue
            try:
                j = json.loads(fp.read_text(encoding="utf-8"))
                sp = j.get("split") if f == "run_meta.json" else j.get("meta", {}).get("split")
            except (ValueError, AttributeError, OSError):
                written = True
                why.append(f"UNREADABLE:{d.name}/{f}")
                continue
            if sp == "FINAL":
                paths.add(d.resolve())
    for d in sorted(paths):
        if not d.is_dir():
            written = True
            why.append(f"ATTEMPT_DIR_MISSING:{d}")
            continue
        extra = sorted(p.name for p in d.iterdir() if p.name not in FINAL_PRE_METRIC_FILES)
        if extra:
            written = True
            why.append(f"METRIC_FILES:{d.name}:{','.join(extra[:5])}")
    return {"attempts": [str(p) for p in sorted(paths)], "metrics_written": written, "why": why}


def final_gate(a, cfg_path, out, used_marker=None, outputs_root=None):
    """FINAL: 잠금 파일 대조(config 경로·실행 잠금 해시) + 외부 코드 clean + 이전 시도 흔적 검사 + FinalGuard 1회(M6)
    → 통과하면 데이터 적재 전에 출력 폴더·시도 표지·장부를 먼저 만든다(이후 어느 단계에서 죽어도 흔적이 남음)."""
    import lockhash
    import split_rules as sr
    if not a.final_lock:
        raise SystemExit("EXP01_FINAL_NEEDS_LOCK")
    root = Path(outputs_root or OUTPUTS).resolve()
    if Path(out).resolve().parent != root:                       # outputs 바로 아래만(다른 위치·중첩 폴더로 흔적 검사를 피하는 경로 차단)
        raise SystemExit("EXP01_FINAL_OUT_OUTSIDE_OUTPUTS")
    lock = json.loads(Path(a.final_lock).read_text(encoding="utf-8"))
    if Path(lock["config_path"]).resolve() != Path(cfg_path).resolve():
        raise SystemExit("EXP01_FINAL_CONFIG_NOT_LOCKED_ONE")
    if "outputs_root" not in lock or Path(lock["outputs_root"]).resolve() != root:   # 코드 사본·다른 outputs 로 우회 차단(N3)
        raise SystemExit("EXP01_FINAL_LOCK_OUTPUTS_ROOT_MISMATCH")
    h = lockhash.run_lock_hash(lock["config_path"], CODE_SCOPE)
    if not h["external_clean"]:
        raise SystemExit("EXP01_EXTERNAL_CODE_DIRTY")
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    sel_run = Path(cfg["tau_selection_run"])                    # 설계 gate5 MAJOR 2: 마지막 SELECT 와 같은 코드인지
    sel_meta = json.loads((sel_run / "run_meta.json").read_text(encoding="utf-8"))
    sel_tau = json.loads((sel_run / "tau_selection.json").read_text(encoding="utf-8"))
    if sel_meta.get("split") != "SELECT" or sel_tau.get("source_split") != "SELECT":
        raise SystemExit("EXP01_FINAL_TAU_NOT_FROM_SELECT")
    if (None if cfg["tau_selected"] == "TAU_FAIL" else float(cfg["tau_selected"])) != sel_tau["tau"]:
        raise SystemExit("EXP01_FINAL_TAU_MISMATCH")
    for part in ("code", "external", "models", "medmap_head"):
        cur = json.loads(json.dumps(h["parts"][part]))      # JSON 왕복으로 형태 통일(튜플→리스트, 설계 gate6 MAJOR)
        if sel_meta["run_lock"]["parts"][part] != cur:
            raise SystemExit(f"EXP01_FINAL_CODE_DIFFERS_FROM_SELECT:{part}")
    final_lock_acquire(root)                                    # 이후 흔적 검사·사용 기록·시도 표지는 잠금 안에서(N1)
    ev = final_evidence(root)
    marker = Path(used_marker or (root / "FINAL_USED"))
    if ev["attempts"] and not marker.exists():                 # 흔적은 있는데 사용 기록이 없음 = 상태 불명 → 차단
        raise SystemExit("EXP01_FINAL_EVIDENCE_WITHOUT_USED_MARKER")
    retry_evidence = None
    if a.retry_environmental:
        err, retry_evidence = final_retry_check(ev, getattr(a, "retry_reason", None))
        if err:
            raise SystemExit(err)
    guard = sr.FinalGuard(a.final_lock, str(marker))
    guard.acquire(h["lock_sha256"], retry_environmental=a.retry_environmental, metrics_written=ev["metrics_written"])
    out = Path(out)
    out.mkdir(parents=True)                                      # 시도 표지·장부를 평가 전에 남김
    att = {"out": str(out.resolve()), "lock_sha256": h["lock_sha256"], "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "retry_environmental": bool(a.retry_environmental), "previous_attempts": ev["attempts"],
           "pid": os.getpid(), "proc_start": _proc_start(os.getpid()),
           "retry_reason": getattr(a, "retry_reason", None) if a.retry_environmental else None,
           "retry_evidence": retry_evidence}
    with open(out / FINAL_ATTEMPT_FILE, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(att, ensure_ascii=False, indent=1, default=str))
        fh.flush()
        os.fsync(fh.fileno())
    final_status_append(out, "STARTED", retry_environmental=bool(a.retry_environmental))
    _FINAL_RUN["dir"] = out
    with open(root / FINAL_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(att, ensure_ascii=False, default=str) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return h


def make_final_config(select_run, out_path) -> dict:
    """SELECT 의 tau_selection.json → FINAL 동결 config(사용자가 잠그기 전 검토용). 실행하지 않는다."""
    sel = json.loads(Path(select_run, "tau_selection.json").read_text(encoding="utf-8"))
    if sel.get("source_split") != "SELECT":
        raise SystemExit("EXP01_TAU_FROM_NON_SELECT")
    cfg = dict(DEFAULT_CONFIG, split="FINAL",
               tau_selected="TAU_FAIL" if sel["tau"] is None else sel["tau"], tau_selection_run=str(select_run))
    meta_p = Path(select_run, "run_meta.json")
    if meta_p.exists():                                   # 실행 방식(병렬)은 SELECT 와 같게(결과 무관 인자)
        par = json.loads(meta_p.read_text(encoding="utf-8")).get("config", {}).get("parallel")
        if par is not None:
            cfg["parallel"] = par
    Path(out_path).write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    return cfg


def make_final_lock(final_cfg_path, lock_path, outputs_root=None) -> dict:
    """FINAL 잠금 파일 작성(사용자 검토·승인 후 1회). {config_sha256: 실행 잠금 해시, config_path, outputs_root}. 실행하지 않는다."""
    import lockhash
    body = {"config_sha256": lockhash.run_lock_hash(final_cfg_path, CODE_SCOPE)["lock_sha256"],
            "config_path": str(Path(final_cfg_path).resolve()), "outputs_root": str(Path(outputs_root or OUTPUTS).resolve())}
    with open(lock_path, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(body, ensure_ascii=False, indent=1))
    return body


def main():
    """FINAL 시도 상태 기록 래퍼: 예외는 FAILED(예외 종류·환경 오류 여부), 정상 종료는 COMPLETED 로 남기고 잠금을 푼다."""
    try:
        _main()
    except BaseException as e:
        d = _FINAL_RUN.get("dir")
        if d is not None:
            import traceback
            final_status_append(d, "FAILED", error_type=type(e).__name__, error=str(e)[:500],
                                environmental=_is_env_error(e), traceback=traceback.format_exc()[-2000:])
        raise
    else:
        if _FINAL_RUN.get("dir") is not None:
            final_status_append(_FINAL_RUN["dir"], "COMPLETED")
    finally:
        _FINAL_RUN.clear()
        final_lock_release()


def _main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None, help="SYNTHETIC 외에는 필수. budgets·seeds·taus·split 은 여기서만")
    ap.add_argument("--split", default=None, choices=SPLITS, help="--config 없을 때 SYNTHETIC 전용")
    ap.add_argument("--out", required=True)
    ap.add_argument("--approved", action="store_true", help="사용자 실행 승인(실데이터 분할 필수)")
    ap.add_argument("--final-lock", default=None)
    ap.add_argument("--retry-environmental", action="store_true")
    ap.add_argument("--retry-reason", default=None, help="환경 오류 재시도 사유(필수, 시도 표지·장부에 기록)")
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit("EXP01_OUT_EXISTS(덮어쓰기 금지)")
    if a.config:
        cfg = load_config(a.config)
    elif a.split == "SYNTHETIC":
        cfg = dict(DEFAULT_CONFIG, split="SYNTHETIC")
    else:
        raise SystemExit("EXP01_CONFIG_REQUIRED")
    checks.static_check(HERE)
    t0 = time.time()
    lock = None
    final = None
    tau_sel = None
    if cfg["split"] == "SYNTHETIC":
        import synth
        from likelihood import GraphLikelihood
        sem, classes, prior, table, P = synth.make_world()
        lik = GraphLikelihood(table, sem.answer_space, classes, prior)
        cases = synth.sample_cases(sem, classes, P, 200)
        extra, edges = {}, None
        if cfg.get("parallel") is None:
            recs = evaluate(cases, sem, lik, classes, cfg["budgets"], cfg["taus"], tuple(cfg["seeds"]),
                            wd_rank=lambda c: list(np.array(classes)[np.argsort(-prior)]),
                            leak_check=cfg["leak_check"], noise=cfg["noise"])
        else:
            import parallel
            recs, _, _, extra["parallel"] = parallel.evaluate_parallel(
                cases, cfg["parallel"]["workers"], cfg["parallel"]["chunk_cases"], budgets=cfg["budgets"],
                taus=cfg["taus"], seeds=tuple(cfg["seeds"]), wd_rank=lambda c: list(np.array(classes)[np.argsort(-prior)]),
                leak_check=cfg["leak_check"], noise=cfg["noise"], sem=sem, lik=lik, classes=classes)
        severe = frozenset(classes[:2])
        split_man = {"evaluated_split": "SYNTHETIC", "evaluated_rows": len(cases)}
    else:
        if not (a.approved and rg_status_ok()):
            raise SystemExit("EXP01_NOT_AUTHORIZED: RG RUN·lock OK 와 --approved 필요")
        import lockhash
        run_lock = lockhash.run_lock_hash(a.config, CODE_SCOPE)      # 모든 실데이터 실행(설계 gate5 MAJOR 2)
        if cfg["split"] == "FINAL":
            lock = final_gate(a, a.config, out)
        recs, severe, prior, classes, lik, split_man, extra, edges = run_real(cfg)
        if _FINAL_RUN.get("dir") is not None:
            final_status_append(_FINAL_RUN["dir"], "EVALUATED", n_records=len(recs))
        extra["run_lock"] = run_lock
        extra["rg_status"] = rg_lock_state()
    out.mkdir(parents=True, exist_ok=cfg["split"] == "FINAL")    # FINAL 은 final_gate 가 이미 만듦(시도 표지)
    if cfg["split"] in ("SELECT", "SELECT_SMOKE", "SYNTHETIC") and None not in cfg["taus"]:
        tau_sel = mt.select_tau(artifacts.tau_stats(recs, severe, cfg["taus"]), cfg["taus"])
        tau_sel["source_split"] = cfg["split"]
        tau_sel["use"] = "τ 선택(공식)" if cfg["split"] == "SELECT" else "EXPLORATORY — τ 선택에 쓰지 않음"
    if cfg["split"] == "FINAL":
        import pandas as pd

        import confirm
        artifacts.write_per_case(recs, out / "per_case.parquet")   # 분석 예외가 나도 사례 기록은 남김(통계 gate5 권고)
        final = confirm.final_analysis(recs, severe, cfg["taus"][0], tuple(cfg["seeds"]))
        (out / "final_judgement.json").write_text(json.dumps(final, ensure_ascii=False, indent=1, default=str),
                                                  encoding="utf-8")
    meta = {"split": cfg["split"], "config": cfg,
            "config_sha256": hashlib.sha256(Path(a.config).read_bytes()).hexdigest() if a.config else None,
            "n_records": len(recs), "elapsed_s": round(time.time() - t0, 2),
            "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            "packages": package_versions(),
            "final_lock": None if lock is None else {"lock_sha256": lock["lock_sha256"],
                                                      "external_clean": lock["external_clean"]},
            "note": {"SYNTHETIC": "가상 세계 점검, 성능 주장 아님", "SELECT_SMOKE": "예비 평가(EXPLORATORY), 판정·선택 금지",
                     "SELECT": "τ 선택용 평가, 통계적 성공 판정 금지", "FINAL": "확인적 1회"}[cfg["split"]], **extra}
    artifacts.write_all(out, recs, severe, cfg["taus"], prior, classes, lik, split_man, meta, final=final,
                        cond_edges=edges, tau_selection=tau_sel)
    print(f"END rc=0 records={len(recs)} out={out}")


if __name__ == "__main__":
    main()
