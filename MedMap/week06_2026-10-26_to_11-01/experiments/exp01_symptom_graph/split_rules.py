"""EXP-01(EXP-MAI-001) 분할 규칙과 검증 절차. 실데이터 실행은 RG RUN 이후에만.

- TRAIN16 / HOLDOUT: STEP16B s16b_core.split_key·is_holdout 를 import 해서 그대로 사용(복사·수정 금지).
- HOLDOUT → SELECT / FINAL: int(sha256("EXP01|"+row_index)[:8],16) % 2  (0=SELECT, 1=FINAL).
- SELECT_SMOKE: SELECT 중 sha256("EXP01SMOKE|"+row_index) 오름차순 앞 1,000건(파이프라인 점검·EXPLORATORY 비교 전용).
- 검증: 기대 STEP16B 행 수·holdout_row_index_sha256 일치, 세 집합 서로소, 합집합 = 전체,
  프로필 중복률 보고(TRAIN16∩FINAL, SELECT∩FINAL). 프로필 = (AGE, SEX, INITIAL_EVIDENCE, EVIDENCES) — 호출자가 만든다(manifest rev2).
"""
from __future__ import annotations

import hashlib
import sys

S16B_DIR = "/home/<user>/medmap/exp/step16b_next_information_validation"
EXPECTED_S16B = {
    "source_rows": 1025602, "train_rows": 820939, "holdout_rows": 204663,
    "holdout_row_index_sha256": "c277844ba35fcc1c170ffccc176b4a3692d11f1cffe25b4a4f5ad0d3eb38f77f",
}
SMOKE_N = 1000


class SplitInvalid(Exception):
    pass


def s16b_core():
    if S16B_DIR not in sys.path:
        sys.path.insert(0, S16B_DIR)
    import s16b_core  # noqa: PLC0415
    return s16b_core


def is_holdout16(row_index, age, sex, pathology, evidences) -> bool:
    c = s16b_core()
    return c.is_holdout(c.split_key(row_index, age, sex, pathology, evidences))


def exp01_half(row_index: int) -> str:
    return "SELECT" if int(hashlib.sha256(f"EXP01|{row_index}".encode()).hexdigest()[:8], 16) % 2 == 0 else "FINAL"


def assign(rows):
    """rows: iterable of (row_index, age, sex, pathology, evidences_str) → {row_index: TRAIN16|SELECT|FINAL}"""
    out = {}
    for ri, age, sex, path, ev in rows:
        out[ri] = exp01_half(ri) if is_holdout16(ri, age, sex, path, ev) else "TRAIN16"
    return out


def smoke_subset(select_indices, n: int = SMOKE_N) -> list:
    key = lambda ri: hashlib.sha256(f"EXP01SMOKE|{ri}".encode()).hexdigest()  # noqa: E731
    return sorted(select_indices, key=key)[:n]


def index_sha(indices) -> str:
    return hashlib.sha256(",".join(map(str, sorted(indices))).encode()).hexdigest()


def verify(assignment: dict, profiles: dict, expected: dict | None = None) -> dict:
    """assignment: row_index → split, profiles: row_index → (AGE,SEX,INITIAL_EVIDENCE,EVIDENCES) (manifest rev2+; 테스트는 임의 튜플).
    expected 가 주어지면 STEP16B 수치 불일치 시 SplitInvalid."""
    groups = {k: {ri for ri, s in assignment.items() if s == k} for k in ("TRAIN16", "SELECT", "FINAL")}
    tr, se, fi = groups["TRAIN16"], groups["SELECT"], groups["FINAL"]
    if (tr & se) or (tr & fi) or (se & fi):
        raise SplitInvalid("EXP01_SPLIT_NOT_DISJOINT")
    if len(tr) + len(se) + len(fi) != len(assignment):
        raise SplitInvalid("EXP01_SPLIT_NOT_COVERING")
    holdout = se | fi
    rep = {"train_rows": len(tr), "select_rows": len(se), "final_rows": len(fi),
           "holdout_row_index_sha256": hashlib.sha256(",".join(map(str, sorted(holdout))).encode()).hexdigest(),
           "select_index_sha256": index_sha(se), "final_index_sha256": index_sha(fi)}
    if expected is not None:
        if len(assignment) != expected["source_rows"] or len(tr) != expected["train_rows"] \
                or len(holdout) != expected["holdout_rows"] \
                or rep["holdout_row_index_sha256"] != expected["holdout_row_index_sha256"]:
            raise SplitInvalid("EXP01_STEP16B_SPLIT_MISMATCH")
    p_tr = {profiles[i] for i in tr}
    p_se = {profiles[i] for i in se}
    rep["final_profile_in_train16_rate"] = sum(profiles[i] in p_tr for i in fi) / max(len(fi), 1)
    rep["final_profile_in_select_rate"] = sum(profiles[i] in p_se for i in fi) / max(len(fi), 1)
    rep["final_novel_rows"] = sum(profiles[i] not in p_tr for i in fi)
    return rep


class FinalGuard:
    """FINAL 접근 1회 제한(manifest rev2 test_population).
    잠금 파일(JSON {"config_sha256": ...}) 이 없거나, 실행 config SHA 와 다르거나, 이미 사용됐으면 거부.
    retry_environmental=True 는 지표 파일이 하나도 없을 때만 같은 config 로 1회 재시도 허용."""

    def __init__(self, lock_path, used_marker_path):
        self.lock_path, self.used = lock_path, used_marker_path

    def acquire(self, config_sha256: str, retry_environmental: bool = False, metrics_written: bool = False) -> None:
        import json  # noqa: PLC0415
        import os  # noqa: PLC0415
        if not os.path.exists(self.lock_path):
            raise SplitInvalid("EXP01_FINAL_BEFORE_FREEZE")
        with open(self.lock_path, encoding="utf-8") as fh:
            locked = json.load(fh).get("config_sha256")
        if locked != config_sha256:
            raise SplitInvalid("EXP01_FINAL_CONFIG_MISMATCH")
        if os.path.exists(self.used):
            with open(self.used, encoding="utf-8") as fh:
                prev = fh.read().split()
            ok_retry = (retry_environmental and not metrics_written
                        and prev == ["used", config_sha256])
            if not ok_retry:
                raise SplitInvalid("EXP01_FINAL_ALREADY_USED")
            with open(self.used, "a", encoding="utf-8") as fh:
                fh.write("retry_environmental\n")
            return
        with open(self.used, "x", encoding="utf-8") as fh:
            fh.write(f"used {config_sha256}\n")
