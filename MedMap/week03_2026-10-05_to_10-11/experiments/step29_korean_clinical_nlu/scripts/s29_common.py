"""STEP29 공통 — Korean Clinical NLU(연구용). STEP20–28.8 코드·산출물은 import·읽기만(protect_check 로 SHA 확인).
금지: LLM·외부 API·다운로드·패키지 설치·재학습·P5 원본 수정·제품/PatientState/49질환 모델 변경·기존 산출물 덮어쓰기·MDRKOR·commit/push."""
from __future__ import annotations

import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S288_DIR = REPO / "exp/step28_8_korean_retrieval_repair"
sys.path.insert(0, str(S288_DIR / "scripts"))
import s288_common as S288  # noqa: E402

S287_DIR, S286_DIR, S285_DIR, S28_DIR, S27_DIR, S21_DIR, S23_DIR = (S288.S287_DIR, S288.S286_DIR, S288.S285_DIR, S288.S28_DIR, S288.S27_DIR,
                                                                    S288.S21_DIR, S288.S23_DIR)
S28 = S288.S28
DATA, OUT, DOCS, LOGS = STEP / "data", STEP / "outputs", STEP / "docs", STEP / "logs"
for _d in (DATA, OUT, DOCS, LOGS):
    _d.mkdir(exist_ok=True)
read_csv, sha256, nospace, rnd, load_json, dump_json, dumps, wcsv, ko_key, stem_key = (
    S288.read_csv, S288.sha256, S288.nospace, S288.rnd, S288.load_json, S288.dump_json, S288.dumps, S288.wcsv, S288.ko_key, S288.stem_key)
