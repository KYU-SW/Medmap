"""STEP28.6 공통 — LLM-Assisted Korean-English Medical Concept Linking(연구용, SILVER).

격리 작성: ~/medmap_step28_6_ws/ 안에서만 `claude -p --restricted --tools Read,Write`(MCP·connector 없음). 작성자 A = opus, B = sonnet(서로 독립 세션).
작성자에게 보내는 것: 한국어 표현 문자열(id 포함)과 지시문뿐. 모델 예측·MedMap 77 목록·ontology 문자열(UMLS·SNOMED)·MDRKOR 는 보내지 않는다.
감사자에게 보내는 것: 한국어 표현 + HPO id·이름·정의(HPO 는 공개 라이선스). SNOMED·UMLS 문자열은 보내지 않는다.
재사용(read-only): STEP28 ontology 색인·검증기(validate_concept_candidates) · STEP28.5 결과(비교용).
"""
from __future__ import annotations

import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S285_DIR = REPO / "exp/step28_5_bilingual_symptom_retrieval"
sys.path.insert(0, str(S285_DIR / "scripts"))
import s285_common as S285  # noqa: E402

S28 = S285.S28
WS = Path.home() / "medmap_step28_6_ws"
DATA, OUT, DOCS, LOGS = STEP / "data", STEP / "outputs", STEP / "docs", STEP / "logs"
for _d in (DATA, OUT, DOCS, LOGS):
    _d.mkdir(exist_ok=True)
read_csv, sha256, norm, nospace, rnd, load_json, dump_json, dumps, wcsv, ko_key = (S285.read_csv, S285.sha256, S285.norm, S285.nospace, S285.rnd,
                                                                                    S285.load_json, S285.dump_json, S285.dumps, S285.wcsv, S285.ko_key)
ONT_DB = S285.ONT_DB
CHUNK = 230
EXPR_TYPES = ("SYMPTOM_OR_SIGN", "DISEASE_OR_DIAGNOSIS", "ANATOMY", "DRUG_OR_TREATMENT", "TEST_OR_PROCEDURE", "OTHER", "UNCLEAR")
AUDIT_LABELS = ("EXACT", "BROADER", "NARROWER", "RELATED_ONLY", "WRONG", "UNCLEAR")
