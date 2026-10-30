"""STEP29.3 공통 — Clinical Concept Retrieval & Semantic Disambiguation(연구용). STEP20–29.2 코드·산출물은 import·읽기만(protect_check 로 확인).
금지: LLM·외부 API·다운로드·설치·재학습·P5/B4/STEP29.x 원본 수정·제품/Doctor/8010/PatientState/49질환 모델 변경·덮어쓰기·MDRKOR·commit/push·사후 판정 변경."""
from __future__ import annotations

import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S292_DIR = REPO / "exp/step29_2_nlu_recovery"
sys.path.insert(0, str(S292_DIR / "scripts"))
import s292_common as S292  # noqa: E402

# 이전 단계 scripts 와 같은 이름을 피하되, 혹시 겹쳐도 이 단계 scripts 가 먼저 잡히도록 맨 앞에 둔다
sys.path.insert(0, str(STEP / "scripts"))

S291_DIR, S29_DIR, S28_DIR, S27_DIR, S21_DIR, S23_DIR = S292.S291_DIR, S292.S29_DIR, S292.S28_DIR, S292.S27_DIR, S292.S21_DIR, S292.S23_DIR
S28 = S292.S28
DATA, OUT, DOCS, LOGS = STEP / "data", STEP / "outputs", STEP / "docs", STEP / "logs"
for _d in (DATA, OUT, DOCS, LOGS):
    _d.mkdir(exist_ok=True)
read_csv, sha256, nospace, rnd, load_json, dump_json, dumps, wcsv, ko_key = (
    S292.read_csv, S292.sha256, S292.nospace, S292.rnd, S292.load_json, S292.dump_json, S292.dumps, S292.wcsv, S292.ko_key)
EXISTING, POS, models = S292.EXISTING, S292.POS, S292.models
