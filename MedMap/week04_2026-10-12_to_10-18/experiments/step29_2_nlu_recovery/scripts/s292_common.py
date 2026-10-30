"""STEP29.2 공통 — MedMap Clinical NLU Recovery & ASR Robustness(연구용). STEP20–29.1 코드·산출물은 import·읽기만(protect_check 로 SHA 확인).
금지: LLM·외부 API·다운로드·설치·재학습·B4/P5/STEP29/29.1 원본 수정·제품/PatientState/49질환 모델 변경·덮어쓰기·MDRKOR·commit/push·사후 판정 변경."""
from __future__ import annotations

import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S291_DIR = REPO / "exp/step29_1_context_nlu_repair"
sys.path.insert(0, str(S291_DIR / "scripts"))
import s291_common as S291  # noqa: E402

# 이전 단계 scripts 와 같은 이름(evaluate_nlu·protect_check·run_tests 등)이 있으므로 이 단계 scripts 를 맨 앞에 둔다(이전 코드가 import 하는 이름과는 겹치지 않음)
sys.path.insert(0, str(STEP / "scripts"))

S29 = S291.S29
S29_DIR, S288_DIR, S28_DIR, S27_DIR, S21_DIR, S23_DIR = S291.S29_DIR, S291.S288_DIR, S291.S28_DIR, S291.S27_DIR, S291.S21_DIR, S291.S23_DIR
S28 = S291.S28
DATA, OUT, DOCS, LOGS = STEP / "data", STEP / "outputs", STEP / "docs", STEP / "logs"
for _d in (DATA, OUT, DOCS, LOGS):
    _d.mkdir(exist_ok=True)
read_csv, sha256, nospace, rnd, load_json, dump_json, dumps, wcsv, ko_key, stem_key = (
    S291.read_csv, S291.sha256, S291.nospace, S291.rnd, S291.load_json, S291.dump_json, S291.dumps, S291.wcsv, S291.ko_key, S291.stem_key)
EXISTING = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")
POS = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "EXISTING_SUBTYPE", "NEW_ONTOLOGY_CANDIDATE")


def models() -> set[str]:
    return {r["canonical_id"] for r in read_csv(S28.DATA / "existing_concept_inventory.csv")}
