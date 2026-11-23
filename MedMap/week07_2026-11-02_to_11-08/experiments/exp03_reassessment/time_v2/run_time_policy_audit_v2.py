"""EXP-MAI-003 (EXP-03-TIME v2) 실제 MIMIC 시간 정책 집계 — 실행은 rg-gate RUN + 사용자 명시 승인 후에만(작성 2026-11-03, 미실행).

v1(time_v1/run_time_policy_audit.py, 보존) 대비: 안전 검사 2계층(A 구현 불변식 / B 독립 데이터 감사) · 고유 기록 분모 ·
환자 수 병기 · 정책별 flag·등급·PROXY·APPROX · 포함률 직접 산출 · STRICT×S1/S2 대응 교차표 · 보완 마스킹 · 코드·입력 SHA ·
예외 시 단계·오류 유형 코드만 기록(식별자 비출력) · 비CTA 영상 증거 미투입 · addendum 규칙.
출력: 공개 집계 JSON 1개(또는 ABORT JSON). 체류별 결과 파일은 만들지 않음(v2 에서 정식 제외).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import json
import platform
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pandas as pd  # noqa: E402

import disclosure_v2 as DS  # noqa: E402  (공개 보호 — 검증은 disclosure_verifier 가 독립 수행)
import disclosure_verifier as DV  # noqa: E402  (독립 역산 검증 — 보호 코드·묶음 G 를 쓰지 않음)
import independent_audit as IA  # noqa: E402
import public_v2 as PB  # noqa: E402
import records_v2 as RV  # noqa: E402
from records_v2 import EXP02, EXP03, TP  # noqa: E402
from reassess import PE, assess, effective_evidence  # noqa: E402

PROTOCOL_VERSION = "PROTOCOL_TIME_v2.md (2026-11-04, time_v2 §5-1·§9-3·§12)"
POLS = list(TP.POLICIES)
STRICT, S1, S2 = POLS
TS = ("T0", "T1", "T2")
SRC_OF = {"lab": "lab", "radiology": "rad", "triage": "triage", "ecg_machine": "ecg"}
REF_PREFIX = {"lab": "hosp.labevents:", "rad": "note.radiology:", "ecg": "ecg.machine_measurements:", "triage": "ed.triage:"}
FLAGS = ("OK", "POST_ED", "UNKNOWN_AVAILABILITY", "TIME_CONFLICT", "NOT_IDENTIFIABLE", "EXCLUDED_BY_POLICY", "APPROX_INTIME")
STATES = ("NO_HYPOTHESIS", "CONFLICT", "SUPPORTED", "INSUFFICIENT", "UNKNOWN", "PENDING")
FROZEN = EXP02 / "outputs/ext_pe_v3_freeze_20261030_1802/ext_pe_v3_freeze.json"
ENGINE = EXP03.parent / "exp01b_graph_engine"
INPUTS = ("cohort.parquet", "labs.parquet", "radiology.parquet", "ecg.parquet")
CATS = ("NO_HYPOTHESIS", "CONFLICT_R2", "SUPPORTED_R1", "SUPPORTED_R7", "INSUFFICIENT_R3", "INSUFFICIENT_NO_DECISIVE",
        "UNKNOWN_R4R5", "PENDING")
DECISIVE_CATS = ("CONFLICT_R2", "SUPPORTED_R1")
SUMMARY_OF = {"NO_HYPOTHESIS": "NO_HYPOTHESIS", "CONFLICT_R2": "CONFLICT", "SUPPORTED_R1": "SUPPORTED", "SUPPORTED_R7": "SUPPORTED",
              "INSUFFICIENT_R3": "INSUFFICIENT", "INSUFFICIENT_NO_DECISIVE": "INSUFFICIENT", "UNKNOWN_R4R5": "UNKNOWN", "PENDING": "PENDING"}
STAGE = {"name": "init"}
KEY_DTYPES: dict = {}


def category(a) -> str:
    """요약 상태 + 근거(교차표 범주). SUPPORTED 는 결정 증거(R1) 유무로, INSUFFICIENT 는 R3 유무로 나눔."""
    d = a.flags.get("decisive", False)
    return {"NO_HYPOTHESIS": "NO_HYPOTHESIS", "CONFLICT": "CONFLICT_R2", "UNKNOWN": "UNKNOWN_R4R5", "PENDING": "PENDING",
            "SUPPORTED": "SUPPORTED_R1" if d else "SUPPORTED_R7",
            "INSUFFICIENT": "INSUFFICIENT_R3" if d else "INSUFFICIENT_NO_DECISIVE"}[a.summary]


def code_files() -> dict:
    fs = {f"time_v2/{n}": HERE / n for n in ("records_v2.py", "independent_audit.py", "public_v2.py", "run_time_policy_audit_v2.py",
                                             "PROTOCOL_TIME_v2.md", "disclosure_v2.py", "disclosure_verifier.py", "disclosure_schema.py",
                                             "build_relations_v3.py", "relation_discovery_v2.py", "synth_random_v2.py", "verify_counted_run.py")}
    if RELATIONS_DEFAULT.exists():
        fs[f"time_v2/disclosure_relations/{RELATIONS_DEFAULT.name}"] = RELATIONS_DEFAULT
    fs["time_v1/time_policy.py"] = EXP03 / "time_v1/time_policy.py"
    fs["reassess.py"] = EXP03 / "reassess.py"
    fs["ct_bridge.py"] = EXP03 / "ct_bridge.py"
    for n in ("mimic_adapter.py", "mimic_paths.py", "ext_pe_eval.py", "pe_rules_v3.py", "ext_pe_eval_v3.py"):
        fs[f"exp02/{n}"] = EXP02 / n
    for p in sorted(ENGINE.glob("*.py")):
        fs[f"exp01b/{p.name}"] = p
    return fs


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def code_sha() -> dict:
    return {k: sha(p) for k, p in code_files().items()}


_GRAPH_SOURCES: dict = {}


def graph_sources() -> dict:
    """EXP-01b 그래프 지식 파일 버전(SHA·커밋·데이터 버전)만 — 경로·라이선스 문자열·UMLS 내용 비출력(M-graph-prov). 프로세스당 1회."""
    if _GRAPH_SOURCES:
        return dict(_GRAPH_SOURCES)
    from knowledge_real_kg import build_real_graph
    _, meta = build_real_graph(extra_hp_nodes=("HP:0410174", "HP:0033106", "HP:0003565"), discriminators=True)
    keep = ("sha256", "commit", "data_version", "version_line")
    _GRAPH_SOURCES.update({n: {k: v for k, v in d.items() if k in keep} for n, d in meta.get("sources", {}).items()})
    return dict(_GRAPH_SOURCES)


def frozen_ok() -> bool:
    fz = json.loads(FROZEN.read_text(encoding="utf-8"))
    return all(sha(EXP02 / f) == h for f, h in fz["code_sha256"].items())


def load_detail(path: Path | None, note_ids: set) -> pd.DataFrame | None:
    if path is None:
        return None
    keep = []
    if str(path).endswith(".parquet"):
        it = [pd.read_parquet(path)]
    else:
        it = pd.read_csv(path, chunksize=500_000, dtype=str, usecols=["note_id", "field_name", "field_value"])
    for ch in it:
        ch = ch[ch["field_name"].isin(["parent_note_id", "addendum_note_id"])]
        keep.append(ch[ch["note_id"].astype(str).isin(note_ids)][["note_id", "field_name", "field_value"]].astype(str))
    return pd.concat(keep, ignore_index=True) if keep else None


def native_of(P, event_id: str):
    pid = event_id.split("-")[0] if event_id.startswith("triage:") else event_id
    src, nat = P.native[pid]
    return src, nat, pid


RELATIONS_DEFAULT = HERE / "disclosure_relations" / "relations_v3_schema.json"
SEALED_ROOT = "/home/<user>/medmap_exp02_sealed"
EXP02_PUBLIC = EXP02 / "outputs/extract_v2_20261030_1139/extract_v2_public.json"   # 이미 공개된 EXP-02 집계(읽기 전용)
RG_ROOT = Path(os.environ.get("EXP03_RG_ROOT") or HERE.parents[2])
RG_TOOL = Path.home() / ".claude/research-guardian/bin/rg.py"
EXP_ID = "EXP-MAI-003"
COUNTED_MARKER = HERE / "outputs" / "EXP_MAI_003_COUNTED_RUN_USED"
TIME_AUDIT_PUBLIC = RG_ROOT / "exp/exp03_reassessment/outputs/mimic_time_audit_20261103_1013/mimic_time_audit_public.json"
EXTERNAL_MAP = {"stays/cohort_stays": "union_stays", "stays/cohort_patients": "union_subjects", "records/lab/input_rows": "lab_rows_target",
                "records/radiology/input_rows": "radiology_rows", "records/ecg/input_rows": "ecg_rows"}


def external_public_values(path: Path = EXP02_PUBLIC, time_audit: Path = TIME_AUDIT_PUBLIC) -> dict:
    """공개 결합 대상 값은 손으로 적지 않고 EXP-02 공개 파일에서 읽는다(봉인 영역 아님). 이미 공개된 시간 감사와 값이 어긋나면 실행 거부."""
    pub = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {c: int(pub[k]) for c, k in EXTERNAL_MAP.items()}
    ta = json.loads(Path(time_audit).read_text(encoding="utf-8"))
    for c, k in (("stays/cohort_stays", "stays_union"), ("records/lab/input_rows", "lab_target_items_rows"),
                 ("records/radiology/input_rows", "radiology_all_rows"), ("records/ecg/input_rows", "ecg_rows")):
        if int(ta[k]) != out[c]:
            raise RuntimeError("PUBLIC_AGGREGATES_DISAGREE")
    return out


def gate_authorization(root: Path, code_manifest: Path) -> list:
    """실행 권한 판단. review_status·마지막 gate 판정·protocol lock·동결 코드 목록만 본다.
    deviations.yaml 의 APPROVED 는 '변경 기록'일 뿐 — 읽지 않으며 실행 권한이 되지 않는다. 반환 = 거부 사유 이름 목록(빈 목록 = 허용)."""
    import subprocess
    import yaml
    exp = Path(root) / ".research-guardian" / "experiments" / EXP_ID
    mp = exp / "manifest.yaml"
    if not mp.exists():
        return ["MANIFEST_MISSING"]
    m = yaml.safe_load(mp.read_text(encoding="utf-8")) or {}
    why = []
    if m.get("review_status") != "RUN":
        why.append("REVIEW_STATUS_NOT_RUN")
    gates = [a for a in (m.get("audit_trail") or []) if a.get("kind") == "gate"]
    if not gates or gates[-1].get("verdict") != "RUN":
        why.append("LAST_GATE_NOT_RUN")
    elif not (Path(root) / str(gates[-1].get("report"))).exists():
        why.append("GATE_REPORT_MISSING")
    if not (exp / "protocol.lock.json").exists():
        why.append("PROTOCOL_NOT_LOCKED")
    else:
        q = subprocess.run([sys.executable, str(RG_TOOL), "check", "--root", str(root), "--exp", EXP_ID], capture_output=True, text=True)
        if q.returncode != 0 or q.stdout.strip() != "OK":
            why.append("PROTOCOL_LOCK_MISMATCH")
    frozen = m.get("code_sha_manifest_sha256")
    if not frozen or not Path(code_manifest).exists() or sha(Path(code_manifest)) != frozen:
        why.append("CODE_MANIFEST_NOT_THE_REVIEWED_ONE")
    return why


def claim_counted_run(marker: Path, info: dict) -> None:
    """실행 전 1회 사용 표지 생성(O_EXCL — 이미 있으면 FileExistsError). 실패한 실행도 표지를 지우지 않는다."""
    marker.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)


def authorize_counted_run(a) -> None:
    """실제 자료 실행 경로의 유일한 관문. 거부 시 자료를 읽기 전에 종료."""
    why = gate_authorization(RG_ROOT, Path(a.code_sha_manifest))
    if why:
        raise SystemExit("GATE_NOT_AUTHORIZED " + ",".join(why))
    if COUNTED_MARKER.exists():
        raise SystemExit("COUNTED_RUN_ALREADY_USED — 재실행 거부")
    claim_counted_run(COUNTED_MARKER, {"experiment": EXP_ID, "claimed_at": datetime.now().isoformat(timespec="seconds"), "out_dir": Path(a.out).name,
                                       "internal_dir": Path(a.internal_out).name, "code_sha_manifest_sha256": sha(Path(a.code_sha_manifest))})


def write_run_record(out_dir: Path, internal_dir: Path, code_manifest: Path) -> None:
    """사후 검증용 무결성 표지. 건수·식별자 없음(파일 SHA·이름만)."""
    pub = out_dir / "time_policy_audit_v2_public.json"
    rec = {"experiment": EXP_ID, "finished_at": datetime.now().isoformat(timespec="seconds"), "public_sha256": sha(pub), "public_name": pub.name,
           "internal_dir_name": internal_dir.name, "internal_sha256": {n: sha(internal_dir / n) for n in ("INTERNAL_AGGREGATES.json", "DISCLOSURE_INTERNAL.json")},
           "code_sha_manifest_sha256": sha(code_manifest), "protocol_version": PROTOCOL_VERSION}
    (out_dir / "RUN_RECORD.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")


def run(src: Path, out_dir: Path, detail_path: Path | None = None, limit: int | None = None,
        expected_code_sha: dict | None = None, pseudo=None, relations_path: Path | None = None,
        internal_dir: Path | None = None, publish: bool = True, withhold_all: bool = False, external_public: dict | None = None) -> dict:
    """publish=False: 정확 집계(INTERNAL)만 만들고 반환(공개 파일 없음) — 관계 발견(relation_discovery_v2, 합성 자료 전용)용."""
    STAGE["name"] = "out_dir"
    out_dir.mkdir(parents=True, exist_ok=False)                       # 시작 시점에 충돌 확인
    v = Counter()
    STAGE["name"] = "code_sha"
    csha = code_sha()
    if expected_code_sha is not None:
        bad = [k for k in set(csha) | set(expected_code_sha) if csha.get(k) != expected_code_sha.get(k)]
        if bad:                                                        # 0 건을 키로 넣으면 Counter 가 참이 됨(정상 실행 ABORT 버그)
            v["code_sha_mismatch"] += len(bad)
    if v:
        return _write(out_dir, {"stage": STAGE["name"], "violations": dict(v)}, abort=True)
    STAGE["name"] = "load"
    co = pd.read_parquet(src / "cohort.parquet")
    labs = pd.read_parquet(src / "labs.parquet")
    rad = pd.read_parquet(src / "radiology.parquet", columns=["note_id", "subject_id", "note_type", "charttime", "storetime", "exam_name"])
    ecg = pd.read_parquet(src / "ecg.parquet", columns=["study_id", "ed_stay_id", "ecg_time_ext"])
    if limit:
        co = co.head(limit)
    detail = load_detail(detail_path, set(rad["note_id"].astype(str)))
    ex = rad["exam_name"].fillna("").astype(str).str.upper()
    cand = set(rad.loc[(ex.str.startswith("CT") | (ex.str.strip() == "")) & rad["note_id"].notna(), "note_id"].astype(str))   # 키 결측 행 제외(결측은 dedupe 가 집계)
    tx = pd.read_parquet(src / "radiology.parquet", columns=["note_id", "text"], filters=[("note_id", "in", sorted(cand))]) \
        if cand else pd.DataFrame(columns=["note_id", "text"])
    texts = dict(zip(tx["note_id"].astype(str), tx["text"]))
    del tx
    KEY_DTYPES.clear()
    KEY_DTYPES.update({"cohort.stay_id": str(co["stay_id"].dtype), "cohort.subject_id": str(co["subject_id"].dtype),
                       "labs.labevent_id": str(labs["labevent_id"].dtype), "labs.subject_id": str(labs["subject_id"].dtype),
                       "radiology.note_id": str(rad["note_id"].dtype), "radiology.subject_id": str(rad["subject_id"].dtype),
                       "ecg.study_id": str(ecg["study_id"].dtype), "ecg.ed_stay_id": str(ecg["ed_stay_id"].dtype)})
    STAGE["name"] = "prepare"
    prep = RV.prepare(co, labs, rad, ecg, detail, lambda n: texts.get(n) or "", pseudo)
    texts.clear()
    STAGE["name"] = "independent_audit_init"
    ia = IA.IndependentAudit(co, labs, rad, ecg, detail, prep.cls)
    v.update(ia.reconcile(prep.audit))
    for s, k in (("lab", "attributed"), ("radiology", "attributed"), ("ecg", "matched")):
        if prep.audit[s]["input_rows"] > 0 and prep.audit[s][k] == 0:
            v[f"B_zero_match_guard_{s}"] += 1                          # 키 dtype 공통 오류 의심 — 두 계층이 같이 0 이면 대조로 못 잡음
    if v:
        return _write(out_dir, {"stage": STAGE["name"], "violations": dict(v)}, abort=True)

    STAGE["name"] = "evaluate"
    E = _Acc()
    P = prep.pseudo
    for sid, stay in prep.stays.items():
        recs = prep.per_stay.get(sid, [])
        subj = stay.subject_id
        T = {"T0": stay.intime, "T1": min(stay.intime + 180, stay.outtime), "T2": stay.outtime}
        den = Counter()
        for r in recs:
            s = SRC_OF[r.source]
            if s == "triage":
                continue
            den[s] += 1
        n_tri = sum(r.source == "triage" for r in recs)
        den["triage"] = int(n_tri > 0)
        for s, n in den.items():
            E.den[s] += n
        E.eval_stays.add(sid)
        E.eval_patients.add(subj)
        res = {}
        for p in POLS:
            b = TP.build(stay, [stay], recs, p, [("h1", PE, stay.intime)])
            v["A_attribution_inconsistent"] += b.audit["AMBIGUOUS_STAY"] + b.audit["OTHER_OR_NO_STAY"]
            E.rejected_no_source[p] += b.audit["REJECTED_NO_SOURCE"]
            E.corr_not_in_tl[p] += b.audit["CORRECTION_TARGET_NOT_IN_TIMELINE"]
            for r in recs:
                ti = TP.time_info(r, stay, p)
                s = SRC_OF[r.source]
                E.flag[p][f"{s}:{ti.flag}"] += 1
                E.grade[p][f"{s}:{ti.grade}"] += 1
                if ti.grade == TP.C:
                    E.c_input[p][s] += 1
            for e in b.timeline.evidence:
                if e.encounter_id != sid:
                    v["A_cross_stay_evidence"] += 1
                if not e.source_reference:
                    v["A_missing_source"] += 1
                s, nat, pid = native_of(P, e.event_id)
                if e.source_reference != REF_PREFIX[s] + pid:
                    v["A_source_reference_untraceable"] += 1
            fam = defaultdict(set)
            for e in b.timeline.evidence:
                if e.source_type == "radiology":
                    _, nat, _ = native_of(P, e.event_id)
                    fam[prep.links.get(nat, nat)].add(e.event_id)
            seq = []
            for k in TS:
                t = T[k]
                u = TP.used_at(b, t)
                used = []
                srcs = Counter()
                tri_used = 0
                for i in u:
                    s, nat, _ = native_of(P, i)
                    ti = b.meta[i]
                    used.append((s, nat, ti.available_at))
                    if s == "triage":
                        tri_used += 1
                    else:
                        srcs[s] += 1
                    if ti.grade == TP.C and not (p == S1 and s == "triage" and ti.approx):
                        v["A_C_used_outside_policy"] += 1
                    if ti.grade == TP.C:
                        E.c_used[p][k] += 1
                    E.proxy[p][k] += ti.proxy
                    E.approx[p][k] += ti.approx
                v.update(ia.check_stay(sid, p, t, used))
                if p == S1 and tri_used != n_tri:
                    v["B_triage_allowed_not_used"] += 1
                for s, n in srcs.items():
                    E.used[p][k][s] += n
                E.used[p][k]["triage"] += int(tri_used > 0)
                E.tri_ev_used[p][k] += tri_used
                if u:
                    E.any_stays[p][k].add(sid)
                    E.any_pat[p][k].add(subj)
                pend = [e for e in b.timeline.evidence if e.observed_at is not None and e.available_at is not None
                        and e.observed_at <= t < e.available_at]
                E.pend_rec[p][k] += len(pend)
                if any(e.evidence_type == "IMAGING_REPORT" for e in pend):
                    E.pend_cta_stays[p][k].add(sid)
                a = assess(b.timeline, t)
                if a.key() != assess(b.timeline.truncated(t), t).key():
                    v["A_leakage_assess_neq_truncated"] += 1
                v["A_relation_after_T"] += sum(r[5] is None or r[5] > t for r in a.relations)
                v["A_alert_after_T"] += sum(x["available_at"] is None or x["available_at"] > t for x in a.alerts)
                eff = {e.event_id for e in effective_evidence(b.timeline, t)[0]}
                v["A_addendum_family_double_effective"] += sum(len(m & eff) > 1 for m in fam.values())
                if any(e.event_id in eff and e.uncertainty_status == "ADDENDUM_UNLINKED" for e in b.timeline.evidence):
                    E.unl_stays[p][k].add(sid)
                    E.unl_pat[p][k].add(subj)
                al = frozenset((x["rule"], x["event_id"]) for x in a.alerts)
                E.state[p][k][a.summary].add(sid)
                E.state_pat[p][k][a.summary].add(subj)
                for rule in {x["rule"] for x in a.alerts}:
                    E.alert_stays[p][k][rule].add(sid)
                    E.alert_pat[p][k][rule].add(subj)
                cat = category(a)
                E.cat[p][k][cat].add(sid)
                E.cat_pat[p][k][cat].add(subj)
                seq.append((a.summary, al, cat))
            res[p] = seq
            if seq[0][0] != seq[2][0]:
                E.chg[p]["summary_T0_vs_T2"].add(sid); E.chg_pat[p]["summary_T0_vs_T2"].add(subj)
            if len({x[0] for x in seq}) > 1:
                E.chg[p]["summary_any_checkpoint"].add(sid); E.chg_pat[p]["summary_any_checkpoint"].add(subj)
            if seq[0][1] != seq[2][1]:
                E.chg[p]["alerts_T0_vs_T2"].add(sid); E.chg_pat[p]["alerts_T0_vs_T2"].add(subj)
            if len({x[1] for x in seq}) > 1:
                E.chg[p]["alerts_any_checkpoint"].add(sid); E.chg_pat[p]["alerts_any_checkpoint"].add(subj)
        for px in (S1, S2):
            for i, k in enumerate(TS):
                a0, ax = res[STRICT][i], res[px][i]
                E.xtab[px][k][(a0[2], ax[2])].add(sid)
                E.xtab_pat[px][k][(a0[2], ax[2])].add(subj)
                if a0[0] != ax[0]:
                    E.diff[px][k]["summary"].add(sid); E.diff_pat[px][k]["summary"].add(subj)
                if a0[1] != ax[1]:
                    E.diff[px][k]["alerts"].add(sid); E.diff_pat[px][k]["alerts"].add(subj)
        if any(v.values()):
            break                                                     # 중단 조건 — 즉시 멈춤
    v.update(ia.finish())
    v = Counter({k: n for k, n in v.items() if n})
    if v:
        return _write(out_dir, {"stage": STAGE["name"], "violations": dict(v)}, abort=True)
    STAGE["name"] = "public"
    in_sha = {n: sha(src / n) for n in INPUTS}
    if detail_path is not None:
        in_sha[Path(detail_path).name] = sha(Path(detail_path))
    if not publish:
        X, _, _, n_eval = build_exact(prep, E)
        if internal_dir is not None:
            write_internal(Path(internal_dir), render(dict(X), X, n_eval), X)
        return {"status": "INTERNAL_ONLY", "flat": {"/".join(map(str, k)): int(v) for k, v in X.items()}}
    rp = Path(relations_path) if relations_path is not None else RELATIONS_DEFAULT
    relations = DV.load_relations(rp) if rp.exists() else None
    if relations is not None and external_public is not None:          # 실제 실행: EXP-02 공개값과 이번 입력이 달라지면 결합 모형이 틀림 → 전부 비공개
        relations["external_known"] = dict(external_public)
    res = public(prep, E, ia, relations, internal_dir, withhold_all, external_public)
    res["disclosure_check"]["relations_file_sha256"] = sha(rp) if rp.exists() else None
    res.update({"created": datetime.now().isoformat(timespec="seconds"), "protocol_version": PROTOCOL_VERSION,
                "source_dir_name": src.name, "limit": limit, "input_key_dtypes": KEY_DTYPES,
                "code_sha256": csha, "input_sha256": in_sha, "graph_kb_sources": graph_sources(),
                "software": {"python": platform.python_version(), "pandas": pd.__version__,
                             "numpy": __import__("numpy").__version__, "pyarrow": __import__("pyarrow").__version__},
                "simulated_wd": "PE 가설, set_at = ED intime, provenance SIMULATED_WD",
                "safety_checks": {"layer_A_implementation_invariants(정책 강제로 0 — 실증 근거 아님)": SAFETY_A, "layer_A_note": SAFETY_A_NOTE,
                                  "layer_B_independent_data_audit(원 parquet 별도 경로 — 관찰 0)": SAFETY_B,
                                  "violations": 0, "NOT_VERIFIABLE": IA.NOT_VERIFIABLE},
                "ext_pe_overlap_note": "extract_v2 radiology 와 Ext-PE 문서 중복(EXP-02 공개 집계 9,580) — Ext-PE 라벨 미연결·정확도 미산출·Ext-PE CSV 미사용 → TEST 재평가 아님",
                "interpretation": "시스템 동작 기술 — 임상 정확도·오진 탐지 아님. 포함률이 높은 정책이 더 우수하다는 뜻 아님. "
                                  "사전 정의 셀은 전부 내부 정확 집계로 산출, 공개는 disclosure_check 통과분만."})
    STAGE["name"] = "disclosure_recheck"                                # 임시 이름으로 쓰고 다시 읽어 독립 재검사 → 통과 시에만 공개 이름으로 교체
    res["status"] = "DONE"
    pub_file = out_dir / "time_policy_audit_v2_public.json"
    tmp_file = out_dir / ".time_policy_audit_v2_public.json.unchecked"
    tmp_file.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    rr = RECHECK_RELATIONS.get("rel")
    re = DV.verify_file(tmp_file, rr) if rr is not None else {"status": DV.NOT_VERIFIABLE}
    if re["status"] != DV.VERIFIED:
        tmp_file.unlink()
        return _write(out_dir, {"stage": STAGE["name"], "violations": {"DISCLOSURE_RECHECK_" + re["status"]: 1}}, abort=True)
    tmp_file.replace(pub_file)
    return res


SAFETY_A = ["A_leakage_assess_neq_truncated", "A_relation_after_T", "A_alert_after_T", "A_C_used_outside_policy",
            "A_cross_stay_evidence", "A_missing_source", "A_attribution_inconsistent", "A_addendum_family_double_effective",
            "A_source_reference_untraceable"]
SAFETY_B = ["B_used_not_allowed", "B_allowed_not_used", "B_available_at_ne_raw_storetime", "B_subject_mismatch",
            "B_record_used_in_multiple_stays", "B_ecg_used", "B_triage_outside_S1", "B_triage_available_not_intime",
            "B_triage_allowed_not_used(완전성 기준 = 어댑터 파생 증거 수, 공유 입력)",
            "B_reconcile_*(lab·radiology: 입력 행·결측 키·고유 키·중복·유지·귀속·AMBIGUOUS·미귀속·연결·CTA 입력 + 항등식 / ECG: matched)",
            "B_zero_match_guard(귀속·매칭 0 이면 키 dtype 공통 오류 의심)"]
SAFETY_A_NOTE = ("A_source_reference_untraceable 는 파이프라인 가명표로 계산(독립 아님). addendum 대체 정확성은 A(가족 동시 유효)로만 검사, B 미검사. "
                 "공개 건수 linked_addendum_stay_ne_parent_stay·linked_addendum_parent_ambiguous_or_unattributed 는 파이프라인 집계(B 는 그 결과인 귀속·AMBIGUOUS·CTA 입력만 대조)")


def _dd(f):
    return defaultdict(f)


class _Acc:
    def __init__(self):
        self.den = Counter()
        self.eval_stays, self.eval_patients = set(), set()
        self.rejected_no_source, self.corr_not_in_tl = Counter(), Counter()
        self.flag = _dd(Counter); self.grade = _dd(Counter); self.c_input = _dd(Counter)
        self.c_used = _dd(Counter); self.proxy = _dd(Counter); self.approx = _dd(Counter)
        self.used = _dd(lambda: _dd(Counter)); self.tri_ev_used = _dd(Counter)
        self.any_stays = _dd(lambda: _dd(set)); self.any_pat = _dd(lambda: _dd(set))
        self.pend_rec = _dd(Counter); self.pend_cta_stays = _dd(lambda: _dd(set))
        self.unl_stays = _dd(lambda: _dd(set)); self.unl_pat = _dd(lambda: _dd(set))
        self.state = _dd(lambda: _dd(lambda: _dd(set))); self.state_pat = _dd(lambda: _dd(lambda: _dd(set)))
        self.cat = _dd(lambda: _dd(lambda: _dd(set))); self.cat_pat = _dd(lambda: _dd(lambda: _dd(set)))
        self.alert_stays = _dd(lambda: _dd(lambda: _dd(set))); self.alert_pat = _dd(lambda: _dd(lambda: _dd(set)))
        self.chg = _dd(lambda: _dd(set)); self.chg_pat = _dd(lambda: _dd(set))
        self.xtab = _dd(lambda: _dd(lambda: _dd(set))); self.xtab_pat = _dd(lambda: _dd(lambda: _dd(set)))
        self.diff = _dd(lambda: _dd(lambda: _dd(set))); self.diff_pat = _dd(lambda: _dd(lambda: _dd(set)))


def public(prep, E: _Acc, ia, relations=None, internal_dir: Path | None = None, withhold_all: bool = False,
           external_public: dict | None = None) -> dict:
    """INTERNAL_AGGREGATES(정확값, 로컬 보안 영역) 과 PUBLIC_AGGREGATES(보호 후 공개) 분리 — PROTOCOL_TIME_v2 §9.
    1) build_exact: 정확값 X(경로 → 정수)·heuristic 묶음 G·환자 짝 PAT (계산 로직은 기존 그대로)
    2) disclosure_v2.protect: heuristic 보완 마스킹 → 독립 검증기(disclosure_verifier) 역산 검사 → 실패·검증 불가 표 PUBLIC_WITHHELD
    3) render: 비율·차이·주석 붙여 중첩 dict. 내부 정확값은 지우거나 덮어쓰지 않음."""
    X, G, PAT, n_eval = build_exact(prep, E)
    internal = render({k: v for k, v in X.items()}, X, n_eval)
    if internal_dir is not None:
        write_internal(Path(internal_dir), internal, X)
    ext_mismatch = external_public is not None and any(int(X.get(tuple(c.split("/")), -1)) != v for c, v in external_public.items())
    pub, report = DS.protect(X, G, PAT, relations, withhold_all=withhold_all or ext_mismatch)
    internal_only = report.pop("_internal_only", None)
    report.pop("_relations_used", None)
    if ext_mismatch:
        report["external_public_mismatch"] = "이번 입력과 EXP-02 공개값 불일치 — 결합 모형 불성립, 전 자료 표 비공개"
    RECHECK_RELATIONS["rel"] = DV.restrict_to_truth(relations, {"/".join(map(str, k)): int(v) for k, v in X.items()})[0] \
        if relations is not None else None                             # 재검사 관계는 보호 코드와 별도로 run 이 직접 구성
    if internal_dir is not None:
        dp = Path(internal_dir) / "DISCLOSURE_INTERNAL.json"
        dp.write_text(json.dumps({"report": report, "internal_only": internal_only}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        os.chmod(dp, 0o600)
    out = render(pub, X, n_eval)
    out["disclosure_check"] = report
    return out


RECHECK_RELATIONS: dict = {}


def write_internal(d: Path, internal: dict, X: dict):
    """정확 집계를 로컬 보안 영역에만 저장(권한 700). 식별자·원문·시각 없음, 건수만. 세션은 실제 자료 실행 결과를 열지 않음."""
    if (d / "INTERNAL_AGGREGATES.json").exists():
        raise FileExistsError("INTERNAL_AGGREGATES 이미 있음 — 덮어쓰지 않음")     # 원본 내부 집계 보존(§9-2)
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    flat = {"/".join(map(str, k)): int(v) for k, v in X.items()}
    (d / "INTERNAL_AGGREGATES.json").write_text(json.dumps({"tree": internal, "flat": flat}, ensure_ascii=False, indent=1, default=str),
                                                encoding="utf-8")
    os.chmod(d / "INTERNAL_AGGREGATES.json", 0o600)


def build_exact(prep, E: _Acc):
    """정확값 트리(X: 경로 → 정수) + 항등식 묶음(G) → (보호 단계로 넘김). 비율·차이는 render 에서.
    묶음 = '합/같음이 다른 곳에 공개되는 칸들'. 과잉 포함 묶음은 정확한 항등식 묶음이 함께 있을 때만 안전(그때는 더 가릴 뿐).
    triage derived_evidence 가 낀 묶음은 시각 불명 체류분 포함이라 정확 항등식 아님(비공개 양이 없어 과잉 포함으로만 작용).
    체류 칸이 가려지면 짝 환자 칸도 가림."""
    X, G, PAT = {}, [], []
    srcs = ("lab", "rad", "triage", "ecg")
    n_eval = len(E.eval_stays)

    def put(path, n, pat=None):
        X[path] = int(n)
        if pat is not None:
            X[path[:-1] + ("patients",)] = int(pat)
            PAT.append((path, path[:-1] + ("patients",)))

    # 1) 체류
    for k, n in prep.audit["stays"].items():
        put(("stays", k), n)
    put(("stays", "evaluated_stays"), n_eval)
    put(("stays", "evaluated_patients"), len(E.eval_patients))
    n_cohort_patients = len(set(prep.subj_of_stay.values()))
    put(("stays", "cohort_patients"), n_cohort_patients)
    put(("stays", "patients_without_evaluable_stay"), n_cohort_patients - len(E.eval_patients))   # 내부 전용 — 공개하면 외부 값과 결합 역산
    PAT.append((("stays", "evaluated_stays"), ("stays", "evaluated_patients")))                   # 평가 체류가 가려지면 평가 환자도 가림
    G += [[("stays", "cohort_stays"), ("stays", "time_defined"), ("stays", "time_undefined")],
          [("stays", "time_defined"), ("stays", "evaluated_stays")],
          [("stays", "cohort_patients"), ("stays", "evaluated_patients"), ("stays", "patients_without_evaluable_stay")]]
    # 2) 원천별 기록
    for s in ("lab", "radiology", "ecg", "triage"):
        for k, n in prep.audit[s].items():
            if isinstance(n, (int, float)) and not isinstance(n, bool):
                put(("records", s, k), n)

    def R(s, *ks):
        return [("records", s, k) for k in ks]

    def pre(s, p):
        return [k for k in X if len(k) == 3 and k[0] == "records" and k[1] == s and k[2].startswith(p)]
    for s in ("lab", "radiology", "ecg"):
        G.append(R(s, "input_rows", "missing_key_rows", "unique_keys", "dup_extra_rows"))
        G.append(R(s, "unique_keys", "kept_unique", "dup_key_groups_time_conflict"))
    for s in ("lab", "radiology"):
        G.append(R(s, "kept_unique", "attributed", "ambiguous", "unattributed"))
    G.append(R("ecg", "kept_unique", "no_stay_key", "stay_key_not_in_cohort", "on_time_undefined_stay", "matched"))
    G.append(R("radiology", "kept_unique") + pre("radiology", "type:"))
    G.append(R("radiology", "kept_unique") + pre("radiology", "note_type:"))
    for t in RV.TYPES:
        G.append(R("radiology", f"type:{t}", f"attributed:{t}", f"ambiguous:{t}", f"unattributed:{t}"))
    for p in ("attributed", "ambiguous", "unattributed"):
        G.append(R("radiology", p) + pre("radiology", p + ":"))
    G.append(R("radiology", "attributed:CTA") + pre("radiology", "class:"))
    G.append(R("radiology", "attributed:CTA", "cta_input", "addendum_linked_no_decisive_not_input"))
    G.append(R("radiology", "link_pairs_both_fields", "verified_links", "child_multiple_parents", "child_not_AR", "parent_not_in_extract", "link_subject_mismatch"))
    G.append(R("radiology", "addendum_linked_replacing") + pre("radiology", "replace_pair:"))
    G.append(R("radiology", "addendum_linked_no_decisive_not_input") + pre("radiology", "nomention_addendum_parent_class:"))
    G.append(R("triage", "rows") + [("stays", "cohort_stays")])
    G.append(R("triage", "rows_on_time_undefined_stay") + [("stays", "time_undefined")])
    G.append(R("triage", "rows", "rows_with_derived_evidence"))
    # 3) 포함률 분모(같은 양 = 같은 묶음)
    for s in srcs:
        put(("denominator", s), E.den[s])
    put(("denominator", "pooled"), sum(E.den[s] for s in srcs))
    G += [[("denominator", "lab"), ("records", "lab", "attributed")], [("denominator", "rad"), ("records", "radiology", "cta_input")],
          [("denominator", "ecg"), ("records", "ecg", "matched")],
          [("denominator", "triage"), ("records", "triage", "rows_with_derived_evidence")],
          [("denominator", "pooled")] + [("denominator", s) for s in srcs]]
    srcden = {"lab": ("denominator", "lab"), "rad": ("denominator", "rad"), "ecg": ("denominator", "ecg"),
              "triage": ("records", "triage", "derived_evidence")}
    # 4) 정책별 flag·등급·C
    for p in POLS:
        for s in srcs:
            fl = [("flags_by_policy", p, f"{s}:{f}") for f in FLAGS]
            gr = [("grades_by_policy", p, f"{s}:{g}") for g in (TP.A, TP.B, TP.C)]
            for path in fl:
                put(path, E.flag[p][path[2]])
            for path in gr:
                put(path, E.grade[p][path[2]])
            put(("C_candidates_vs_used", p, "C_input_by_source", s), E.c_input[p][s])
            G += [[srcden[s]] + fl, [srcden[s]] + gr, [("C_candidates_vs_used", p, "C_input_by_source", s), gr[2]]]
        for k in TS:
            put(("C_candidates_vs_used", p, "C_used", k), E.c_used[p][k])
    # 5) 사용
    for p in POLS:
        for k in TS:
            u = E.used[p][k]
            for s in srcs:
                put(("usage", p, k, "used", s), u[s])
            put(("usage", p, k, "used", "pooled"), sum(u[s] for s in srcs))
            G.append([("usage", p, k, "used", x) for x in srcs + ("pooled",)])
            put(("usage", p, k, "stays_with_any_used", "stays"), len(E.any_stays[p][k]), len(E.any_pat[p][k]))
            put(("usage", p, k, "triage_derived_evidence_used"), E.tri_ev_used[p][k])
            put(("usage", p, k, "PROXY_used(evidence)"), E.proxy[p][k])
            put(("usage", p, k, "APPROX_used(evidence)"), E.approx[p][k])
            put(("usage", p, k, "observed_le_T_lt_available(records)"), E.pend_rec[p][k])
            put(("usage", p, k, "stays_cta_performed_not_yet_available"), len(E.pend_cta_stays[p][k]))
            put(("usage", p, k, "stays_with_unlinked_AR_effective", "stays"), len(E.unl_stays[p][k]), len(E.unl_pat[p][k]))
            G.append([("usage", p, k, "PROXY_used(evidence)"), ("usage", p, k, "used", "rad")])   # 같은 양(2칸)
        put(("usage", p, "rejected_no_source"), E.rejected_no_source[p])
        put(("usage", p, "correction_target_not_in_timeline"), E.corr_not_in_tl[p])
    # 5-1) 정책·시점 간 정의상 같은 양(lab 은 세 정책 동일 등급 A, rad 은 STRICT=S1, S1 triage 는 intime 근사라 T 불변).
    #      같은 양은 2칸 사슬로 표현 — '정확히 1개면 보완' 규칙이 사슬을 따라 전파돼 하나라도 가려지면 전부 가려짐(3칸 묶음은 2칸에서 멈춤)
    def eq_chain(ps):
        return [[ps[i], ps[i + 1]] for i in range(len(ps) - 1)]
    # 일반 규칙(5차 gate S-eq-scope-rad): 정책이 달라도 같은 원천·같은 flag/등급/C 입력 칸, 같은 원천·같은 T 의 사용 칸은
    # 전부 세 정책 사슬로 묶음. 정의상 같은 것(lab 전부, rad UNKNOWN·TIME_CONFLICT, 등급·C 입력 등)은 보호되고,
    # 정의상 다른 것(예: rad OK vs S2 EXCLUDED)은 더 가릴 뿐(0 칸은 보완 대상 아님).
    for k in TS:
        for s_ in srcs:
            G.extend(eq_chain([("usage", p, k, "used", s_) for p in POLS]))
        G.extend(eq_chain([("usage", p, k, "PROXY_used(evidence)") for p in POLS]))
    for p in POLS:
        for k in TS:
            G.extend(eq_chain([("usage", p, k, "APPROX_used(evidence)"), ("usage", p, k, "triage_derived_evidence_used"),
                               ("C_candidates_vs_used", p, "C_used", k)]))
        G.extend(eq_chain([("usage", p, k, "used", "triage") for k in TS]))
    for s_ in srcs:
        for f in FLAGS:
            G.extend(eq_chain([("flags_by_policy", p, f"{s_}:{f}") for p in POLS]))
        for g in (TP.A, TP.B, TP.C):
            G.extend(eq_chain([("grades_by_policy", p, f"{s_}:{g}") for p in POLS]))
        G.extend(eq_chain([("C_candidates_vs_used", p, "C_input_by_source", s_) for p in POLS]))
    # 6) 상태·범주·알림·변화
    for p in POLS:
        for k in TS:
            for s in STATES:
                put(("states", p, k, s, "stays"), len(E.state[p][k][s]), len(E.state_pat[p][k][s]))
            for c in CATS:
                put(("categories", p, k, c, "stays"), len(E.cat[p][k][c]), len(E.cat_pat[p][k][c]))
            G.append([("stays", "evaluated_stays")] + [("states", p, k, s, "stays") for s in STATES])
            G.append([("stays", "evaluated_stays")] + [("categories", p, k, c, "stays") for c in CATS])
            for s, cs in (("SUPPORTED", ("SUPPORTED_R1", "SUPPORTED_R7")), ("INSUFFICIENT", ("INSUFFICIENT_R3", "INSUFFICIENT_NO_DECISIVE")),
                          ("CONFLICT", ("CONFLICT_R2",)), ("UNKNOWN", ("UNKNOWN_R4R5",)), ("PENDING", ("PENDING",)),
                          ("NO_HYPOTHESIS", ("NO_HYPOTHESIS",))):
                G.append([("states", p, k, s, "stays")] + [("categories", p, k, c, "stays") for c in cs])
            for r in ("AL1_NEW_CONFLICT", "AL2_SUPPORT_RETRACTED"):
                put(("states", p, k, "alerts", r, "stays"), len(E.alert_stays[p][k][r]), len(E.alert_pat[p][k][r]))
        for c in ("summary_T0_vs_T2", "summary_any_checkpoint", "alerts_T0_vs_T2", "alerts_any_checkpoint"):
            put(("states", p, "changes", c, "stays"), len(E.chg[p][c]), len(E.chg_pat[p][c]))
    # 7) 대응 교차표(범주 = 요약 상태 + 근거), 결정 상태 상실·획득
    for px in (S1, S2):
        for k in TS:
            cell = {}
            for a in CATS:
                for b in CATS:
                    path = ("paired_crosstab_vs_STRICT", px, k, f"STRICT={a}|{px}={b}", "stays")
                    put(path, len(E.xtab[px][k][(a, b)]), len(E.xtab_pat[px][k][(a, b)]))
                    cell[(a, b)] = path
            for a in CATS:
                G.append([("categories", STRICT, k, a, "stays")] + [cell[(a, b)] for b in CATS])
            for b in CATS:
                G.append([("categories", px, k, b, "stays")] + [cell[(a, b)] for a in CATS])
            off = [cell[(a, b)] for a in CATS for b in CATS if a != b]
            for d in ("summary", "alerts"):
                put(("paired_crosstab_vs_STRICT", px, k, "differs", d, "stays"), len(E.diff[px][k][d]), len(E.diff_pat[px][k][d]))
            G.append([("paired_crosstab_vs_STRICT", px, k, "differs", "summary", "stays")] + off)            # 상위집합(과잉 포함)
            G.append([("paired_crosstab_vs_STRICT", px, k, "differs", "summary", "stays")] +             # 정확한 항등식
                     [cell[(a, b)] for a in CATS for b in CATS if SUMMARY_OF[a] != SUMMARY_OF[b]])
            for name, rows, cols in (("decisive_lost(STRICT 결정 → 비결정)", DECISIVE_CATS, [c for c in CATS if c not in DECISIVE_CATS]),
                                     ("decisive_gained(STRICT 비결정 → 결정)", [c for c in CATS if c not in DECISIVE_CATS], DECISIVE_CATS)):
                cs = [(a, b) for a in rows for b in cols]
                st = set().union(*(E.xtab[px][k][c] for c in cs))
                pt = set().union(*(E.xtab_pat[px][k][c] for c in cs))
                path = ("paired_crosstab_vs_STRICT", px, k, name, "stays")
                put(path, len(st), len(pt))
                G.append([path] + [cell[c] for c in cs])
    # 7-1) 병합 범주(공개 2순위): 원천·정책별 flag 를 3범주로(정확값 합 — 세부 flag 표를 못 내도 이 표는 검증 후 공개 가능)
    for p in POLS:
        for s in srcs:
            for mname, fs in DS.MERGED_FLAGS.items():
                put(("flags_merged", p, f"{s}:{mname}"), sum(X[("flags_by_policy", p, f"{s}:{f}")] for f in fs))
    return X, G, PAT, n_eval


def render(pub: dict, X: dict, n_eval: int) -> dict:
    """공개값(또는 정확값) dict → 비율·차이·주석을 붙인 중첩 dict. 비율 출처(분자·분모 경로)를 ratio_sources 로 함께 기록(독립 검증용)."""
    pub = dict(pub)
    srcs = ("lab", "rad", "triage", "ecg")
    ratio_sources = {}
    hidden = lambda v: v is None or PB.is_masked(v)                     # PUBLIC_WITHHELD 도 문자열 → 가림 취급
    # 8) 비율·정책 간 차이(반올림 전 정확값으로 계산)
    exact_rate = {}
    for p in POLS:
        for k in TS:
            for s in srcs + ("pooled",):
                num, den = ("usage", p, k, "used", s), ("denominator", s)
                pub[("usage", p, k, "rate", s)] = PB.NA if hidden(pub.get(num)) or hidden(pub.get(den)) or X[den] == 0 else round(X[num] / X[den], 4)
                ratio_sources["/".join(("usage", p, k, "rate", s))] = ["/".join(num), "/".join(den)]
                exact_rate[(p, k, s)] = None if hidden(pub.get(num)) or hidden(pub.get(den)) or X[den] == 0 else X[num] / X[den]
            sp = ("usage", p, k, "stays_with_any_used", "stays")
            ev = ("stays", "evaluated_stays")
            pub[("usage", p, k, "stays_with_any_used", "stay_rate")] = PB.NA if hidden(pub.get(sp)) or hidden(pub.get(ev)) or n_eval == 0 \
                else round(X[sp] / n_eval, 4)
            ratio_sources["/".join(sp[:-1] + ("stay_rate",))] = ["/".join(sp), "/".join(ev)]
    for px in (S1, S2):
        for k in TS:
            for s in srcs + ("pooled",):
                a, b = exact_rate[(px, k, s)], exact_rate[(STRICT, k, s)]
                pub[("rate_diff_vs_STRICT", px, k, s)] = PB.NA if a is None or b is None else round(a - b, 4)
                ratio_sources["/".join(("rate_diff_vs_STRICT", px, k, s))] = ["/".join(("usage", px, k, "rate", s)),
                                                                              "/".join(("usage", STRICT, k, "rate", s))]
    out = {"ratio_sources": ratio_sources}
    for path, val in pub.items():
        d = out
        for key in path[:-1]:
            d = d.setdefault(key, {})
        d[path[-1]] = val
    out.setdefault("records", {})["units"] = {"lab": "고유 labevent_id", "radiology": "고유 note_id(문서)", "ecg": "고유 study_id",
                               "triage": "triage 행(=체류) — derived_evidence 는 파생 증거 수(별도 단위)"}
    out.setdefault("denominator", {})["definition"] = ("lab=귀속 고유 labevent_id · rad=귀속 CTA 입력 문서 · triage=파생 증거 있는 triage 행 · "
                                        "ecg=귀속 고유 study_id · pooled=네 분모 합(단위 혼합 참고값 — 해석은 원천별 우선)")
    out["unit_notes"] = {"flags_by_policy·grades_by_policy·C_input": "lab·rad·ecg = 귀속 고유 기록, triage = 파생 증거 단위",
                         "usage.used.triage": "triage 행(파생 증거 1개 이상 사용된 체류)",
                         "rate_diff_vs_STRICT": "정책 P 비율 − STRICT 비율(같은 T·같은 원천, 반올림 전 계산 후 4자리), 마스킹 칸 포함 시 계산 불가",
                         "S2_note": "S2 는 영상이 타임라인에 들어가지 않아 rad 관련 observed≤T<available·CTA 미이용 체류·미연결 AR 유효 체류는 정의상 0",
                         "stays_block": "stays.time_undefined·t1_equals_t2 는 체류 수만(환자 병기 없음 — 한계)",
                         "stays_with_unlinked_AR_effective": "T 시점 유효 증거에 미연결 AR(자기 charttime 귀속 단독 판독)이 포함된 체류(+환자) — 이전 방문 addendum 유입 가능성의 상한 규모",
                         "categories": "요약 상태 + 근거. 결정 상태 = CONFLICT_R2·SUPPORTED_R1. SUPPORTED_R7 = 결정 증거 없이 R7 지지. "
                                       "S2 의 SUPPORTED_R7 은 EXP-01b 그래프상 0(lab 노드 SUGGESTS→PE 간선 없음, 2026-11-03 확인 시점 KB = graph_kb_sources). 실행 결과가 0 이 아니면 결과를 고치지 않고 그대로 보고(주석이 틀린 것)"}
    out["masking"] = ("1단계(heuristic): 1–9 '<10' · 항등식 묶음 보완 마스킹 MASKED_COMPLEMENT · 체류 칸이 가려지면 짝 환자 칸도 가림. "
                      "2단계: 독립 검증기(disclosure_verifier — 스키마·프로토콜 선언 관계 + 선형계획 범위 검사)가 역산 위험을 검사, "
                      "실패·검증 불가 표는 PUBLIC_WITHHELD. 세부 표(T3)는 외부 공개 제외. 환자 수는 평가·코호트 전체만 공개(집합 관계는 선형 검증 범위 밖). "
                      "마스킹·비공개 칸 포함 비율·차이 = 계산 불가. 검증 범위·한계는 disclosure_check")
    return out


def _write(out_dir: Path, res: dict, abort: bool) -> dict:
    res["status"] = "ABORT" if abort else "DONE"
    if abort:
        res["violations"] = {k: PB.cell(n) for k, n in res.get("violations", {}).items()}
        res["note"] = "중단 조건 위반 — 결과 무효. 위반 항목 이름·건수만 기록(식별자 없음)"
    name = "ABORT_time_policy_audit_v2.json" if abort else "time_policy_audit_v2_public.json"
    (out_dir / name).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-code-sha", default=None, help="gate RUN 직후 동결용: 코드 SHA-256 JSON 만 쓰고 종료(자료 읽지 않음)")
    ap.add_argument("--src", default=None, help="봉인 추출 폴더(extract_v2_20261030_1139)")
    ap.add_argument("--rad-detail", default=None, help="radiology_detail.csv.gz 로컬 경로(addendum 연결) — 없으면 전 AR 미연결")
    ap.add_argument("--out", default=None)
    ap.add_argument("--code-sha-manifest", default=None, help="gate 동결 시 만든 CODE_SHA256.json — 불일치 시 ABORT")
    ap.add_argument("--internal-out", default=None, help="INTERNAL_AGGREGATES 저장 폴더 — 봉인 영역(/home/<user>/medmap_exp02_sealed/) 아래만 허용")
    ap.add_argument("--relations", default=None, help="동결 관계 파일(기본 time_v2/disclosure_relations/relations_v2.json)")
    ap.add_argument("--withhold-all", action="store_true", help="자료 표 전부 비공개(내부 정확 집계만)")
    ap.add_argument("--i-have-user-approval", action="store_true", help="rg-gate RUN + 사용자 명시 승인 후에만")
    a = ap.parse_args(argv)
    if a.write_code_sha:
        o = Path(a.write_code_sha)
        if o.exists():
            raise SystemExit("이미 있음 — 덮어쓰지 않음")
        o.write_text(json.dumps(code_sha(), indent=1, sort_keys=True), encoding="utf-8")
        print("CODE_SHA_WRITTEN")
        return
    if not a.src or not a.out:
        raise SystemExit("--src·--out 필요")
    if not a.i_have_user_approval:
        raise SystemExit("승인 플래그 없음 — 실행하지 않음(rg-gate RUN + 사용자 명시 승인 필요)")
    if not a.code_sha_manifest:
        raise SystemExit("--code-sha-manifest 필수(승인 실행) — gate 동결 코드 대조 없이 실행하지 않음")
    if not a.internal_out or not str(Path(a.internal_out).resolve()).startswith(SEALED_ROOT + "/") \
            or Path(a.internal_out).name.startswith("extract"):
        raise SystemExit("--internal-out 필수 — 봉인 영역 아래 새 폴더만, EXP-02 동결 추출 폴더 금지(정확 집계는 공개 폴더에 두지 않음)")
    if not a.rad_detail:
        raise SystemExit("--rad-detail 필수(승인 실행) — 없으면 모든 addendum 이 미연결로 처리됨")
    authorize_counted_run(a)                                          # gate RUN·lock·동결 코드 확인 후 1회 사용 표지(자료 읽기 전)
    try:
        STAGE["name"] = "frozen_check"
        if not frozen_ok():
            print("ABORT stage=frozen_check type=FROZEN_SHA_MISMATCH")
            sys.exit(3)
        exp = json.loads(Path(a.code_sha_manifest).read_text(encoding="utf-8"))
        res = run(Path(a.src), Path(a.out), Path(a.rad_detail) if a.rad_detail else None, expected_code_sha=exp,
                  relations_path=Path(a.relations) if a.relations else None, internal_dir=Path(a.internal_out),
                  withhold_all=a.withhold_all, external_public=external_public_values())
    except SystemExit:
        raise
    except BaseException as e:                                        # 메시지·traceback 비출력(식별자 포함 가능)
        print(f"ABORT stage={STAGE['name']} type={type(e).__name__}")
        sys.exit(4)
    if res["status"] == "ABORT":
        print(f"ABORT stage={res.get('stage')} violations={sorted(res['violations'])}")
        sys.exit(3)
    write_run_record(Path(a.out), Path(a.internal_out), Path(a.code_sha_manifest))
    print("DONE")


if __name__ == "__main__":
    main()
