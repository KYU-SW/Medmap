"""STEP29.1 공통 — Context-Aware Clinical NLU Repair(연구용). STEP20–29 코드·산출물은 import·읽기만(protect_check 로 확인).
금지: LLM·외부 API·다운로드·설치·재학습·P5/STEP29 원본 수정·제품/PatientState/49질환 모델 변경·덮어쓰기·MDRKOR·commit/push·사후 판정 변경."""
from __future__ import annotations

import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S29_DIR = REPO / "exp/step29_korean_clinical_nlu"
sys.path.insert(0, str(S29_DIR / "scripts"))
import s29_common as S29  # noqa: E402

S288_DIR, S287_DIR, S28_DIR, S27_DIR, S21_DIR, S23_DIR = S29.S288_DIR, S29.S287_DIR, S29.S28_DIR, S29.S27_DIR, S29.S21_DIR, S29.S23_DIR
S28 = S29.S28
DATA, OUT, DOCS, LOGS = STEP / "data", STEP / "outputs", STEP / "docs", STEP / "logs"
for _d in (DATA, OUT, DOCS, LOGS):
    _d.mkdir(exist_ok=True)
read_csv, sha256, nospace, rnd, load_json, dump_json, dumps, wcsv, ko_key, stem_key = (
    S29.read_csv, S29.sha256, S29.nospace, S29.rnd, S29.load_json, S29.dump_json, S29.dumps, S29.wcsv, S29.ko_key, S29.stem_key)
