"""STEP28.5 공통 — Korean-English Dual Symptom Concept Retrieval(연구용). STEP20–28 산출물·모델·색인은 읽기만 한다.

재사용(read-only): STEP28 ontology 색인(index/ontology_index.sqlite, HPO 2026-09-01·SNOMED INT 20260901·UMLS 2026AA) ·
 STEP28 검증기(validate_concept_candidates.validate) · STEP27 POLICY_D 라우터(Linear+KoELECTRA 특징) · 제품 매퍼(read-only) · terminology_ko.json ·
 DDXPlus release_evidences.json(영어 이름·값 의미).
제외: UMLS MDRKOR(MedDRA 한국어, SRL 3) · KCD5(SRL 3) · 이용 조건 미확인 자료. 신규 다운로드·외부 API·번역 API 없음.
로컬 다국어 모델: xlm-roberta-base(STEP28 gate 실패, hit@5 1.2% → 재사용 안 함) · siglip2-base-patch16-224 텍스트 인코더(이번에 같은 gate 로 검사).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S28_DIR = REPO / "exp/step28_open_vocabulary_symptom_expansion"
sys.path.insert(0, str(S28_DIR / "scripts"))
import s28_common as S28  # noqa: E402

S27, S26, S23 = S28.S27, S28.S26, S28.S23
DATA, OUT, DOCS, LOGS, INDEX = STEP / "data", STEP / "outputs", STEP / "docs", STEP / "logs", STEP / "index"
for _d in (DATA, OUT, DOCS, LOGS, INDEX):
    _d.mkdir(exist_ok=True)
read_csv, write_csv, sha256, norm, nospace, rnd, load_json, dump_json, dumps = (S28.read_csv, S28.write_csv, S28.sha256, S28.norm, S28.nospace,
                                                                                S28.rnd, S28.load_json, S28.dump_json, S28.dumps)
ONT_DB = S28.INDEX / "ontology_index.sqlite"
SIGLIP = Path.home() / ".cache/huggingface/hub/models--google--siglip2-base-patch16-224/snapshots/75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2"
EVID = S28.MAIN / "data/ddxplus/en/release_evidences.json"
COND = S28.MAIN / "data/ddxplus/en/release_conditions.json"


def wcsv(path, rows, fields=None):
    import csv
    fields = fields or (list(rows[0]) if rows else ["empty"])
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def ko_key(s: str) -> str:
    """한국어 비교 키: 공백·구두점 제거."""
    return re.sub(r"[\s·,./()\[\]~?!'\"-]+", "", s or "")


def evidences():
    return json.loads(EVID.read_text(encoding="utf-8"))
