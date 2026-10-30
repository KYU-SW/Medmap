"""STEP28.8 공통 — Korean Retrieval Repair & Evaluation Gate(연구용). 기존 STEP20–28.7 코드·산출물은 읽기만(원본 SHA 는 protect_check 로 확인).

재사용(read-only import): STEP28.5 Retriever·extract_kiwi·kiwi · STEP28.7 SafeOfflineRetriever.combine·SilverTable · STEP27 B4 라우터 · STEP28 색인.
금지: LLM·외부 API·다운로드(pip 포함)·재학습·제품/PatientState/49질환 모델 변경·기존 산출물 덮어쓰기·MDRKOR·commit/push.
"""
from __future__ import annotations

import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S287_DIR = REPO / "exp/step28_7_mapping_quality_validation"
sys.path.insert(0, str(S287_DIR / "scripts"))
import s287_common as S287  # noqa: E402

S286_DIR, S285_DIR, S28_DIR, S27_DIR = S287.S286_DIR, S287.S285_DIR, S287.S28_DIR, S287.S27_DIR
S28 = S287.S28
S21_DIR, S23_DIR = REPO / "exp/step21_korean_symptom_entity_linking", REPO / "exp/step23_korean_expression_expansion"
DATA, OUT, DOCS, LOGS = STEP / "data", STEP / "outputs", STEP / "docs", STEP / "logs"
for _d in (DATA, OUT, DOCS, LOGS):
    _d.mkdir(exist_ok=True)
read_csv, sha256, norm, nospace, rnd, load_json, dump_json, dumps, wcsv, ko_key, stem_key = (
    S287.read_csv, S287.sha256, S287.norm, S287.nospace, S287.rnd, S287.load_json, S287.dump_json, S287.dumps, S287.wcsv, S287.ko_key, S287.stem_key)
