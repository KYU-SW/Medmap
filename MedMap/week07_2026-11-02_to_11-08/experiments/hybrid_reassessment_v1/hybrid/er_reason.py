"""ER-Reason 평가 준비 코드(승인 전 실데이터 실행 없음). 네트워크 호출 없음. 승인 기록이 없으면 파일을 열지 않는다.
열 이름은 PhysioNet 공개 설명 기준이며 실제 파일 헤더·형식은 승인 후 확인해야 한다(UNKNOWN)."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from .schema import AssertedBy, DataClass, DiagnosisAssertion, DxStatus, EvidenceItem, EvidenceKind, Polarity, Provenance, ReasonerInput, ReferenceLabel

SCT_TEST_COLS = {"encounterkey", "One_Sentence_Extracted"} | {f"differential_{i}" for i in range(1, 6)} | {f"evidence_{i}" for i in range(1, 6)}
SCT_REASON_COLS = {"encounterkey", "differential", "evidence", "dxupdate", "rationale", "dxtrajectory"}
FORBIDDEN_MODEL_FIELDS = {"dxupdate", "rationale", "dxtrajectory", "Rule_Out", "Decision_Factors", "Treatment_Plan", "primaryeddiagnosisname"}
SPLIT_SALT = "MEDMAP_ER_REASON_SPLIT_V1"
SPLITS = ((0.40, "DEVELOPMENT"), (0.60, "VALIDATION"), (1.01, "HELD_OUT_TEST"))


class ApprovalMissing(RuntimeError):
    pass


def check_approval(path: Path) -> dict:
    """사용자가 승인 후 직접 만드는 기록 파일. 코드가 만들지 않는다."""
    p = Path(path)
    if not p.exists():
        raise ApprovalMissing("승인 기록 없음 — 데이터 파일을 열지 않음")
    rec = json.loads(p.read_text(encoding="utf-8"))
    for k in ("physionet_access_granted_on", "version", "dua_reviewed_on", "external_llm_allowed", "approved_by_user"):
        if k not in rec:
            raise ApprovalMissing(f"승인 기록 항목 없음: {k}")
    if rec["version"] != "1.1.0" or rec["approved_by_user"] is not True:
        raise ApprovalMissing("승인 기록 내용 불충분")
    return rec


def split_of(encounterkey: str) -> str:
    """사례 단위 고정 분할. 같은 사례의 모든 단계·가설은 같은 분할."""
    v = int(hashlib.sha256(f"{SPLIT_SALT}|{encounterkey}".encode()).hexdigest()[:8], 16) / 2**32
    return next(name for cut, name in SPLITS if v < cut)


def _read(path: Path, need: set) -> list:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        miss = need - set(rd.fieldnames or [])
        if miss:
            raise ValueError(f"SCHEMA_MISMATCH 없는 열 {sorted(miss)}")
        return list(rd)


def build_items(sct_test: Path, sct_reasoning: Path, approval: Path, data_class: DataClass = DataClass.RESTRICTED) -> tuple:
    """(입력, 정답). 입력에는 정답·근거 설명·최종 진단이 들어가지 않는다.
    문항 = sct_reasoning 한 행(사례·감별진단·증거). 시간 단계는 sct_test 의 evidence_n 순서. evidence 문자열이 일치하지 않는 행은 unmatched 로 보고."""
    check_approval(approval)
    tests = {r["encounterkey"]: r for r in _read(Path(sct_test), SCT_TEST_COLS)}
    inputs, refs, unmatched = [], [], []
    for n, r in enumerate(_read(Path(sct_reasoning), SCT_REASON_COLS)):
        t = tests.get(r["encounterkey"])
        step = None
        if t:
            ev = [t.get(f"evidence_{i}", "") for i in range(1, 6)]
            step = next((i for i, x in enumerate(ev, 1) if x and x.strip() == r["evidence"].strip()), None)
        if t is None or step is None:
            unmatched.append(n)
            continue
        key = r["encounterkey"]
        prov = Provenance("er_reason.sct_test", f"sct_test:{hashlib.sha256(key.encode()).hexdigest()[:12]}#evidence_{step}", data_class)
        prior = tuple(EvidenceItem(f"{key}:e{i}", key, EvidenceKind.OTHER, t[f"evidence_{i}"], Provenance("er_reason.sct_test", f"prior#{i}", data_class), available_at=float(i)) for i in range(1, step) if t.get(f"evidence_{i}"))
        e = EvidenceItem(f"{key}:e{step}", key, EvidenceKind.OTHER, r["evidence"], prov, available_at=float(step), polarity=Polarity.UNKNOWN)
        h = DiagnosisAssertion(f"{key}:h{n}", key, r["differential"], DxStatus.DIFFERENTIAL_DIAGNOSIS, AssertedBy.DATASET_ANNOTATION, 0.0, Provenance("er_reason.sct_test", f"differential:{n}", data_class))
        iid = f"{key}|{n}"
        inputs.append(ReasonerInput(iid, key, h, e, t["One_Sentence_Extracted"], prior, float(step), data_class))
        refs.append(ReferenceLabel(iid, key, int(float(r["dxupdate"])), group=f"step{step}", split=split_of(key)))
    return inputs, refs, {"n_rows_unmatched": len(unmatched), "n_cases": len({r.case_id for r in refs}), "n_items": len(refs)}
