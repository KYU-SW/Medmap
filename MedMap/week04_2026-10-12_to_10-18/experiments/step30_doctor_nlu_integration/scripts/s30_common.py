"""STEP30 공통 — MedMap Clinical NLU ↔ Doctor 연구용 통합(연구 시뮬레이션). 제품은 읽기·in-process 재사용만.
금지: 제품(~/medmap master)·PatientState·Doctor UI·8010/8020/5190 서버·49질환 모델 변경 · STEP20–29.3 원본 수정 · LLM·외부 API·다운로드·설치·재학습 ·
      신규 SILVER 개념 모델 입력 · 의사 확인 전 모델 입력 · commit/push · 사후 판정 변경."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]                                   # ~/medmap-worktrees/symptom-ontology
S293_DIR = REPO / "exp/step29_3_concept_retrieval_repair"
S28_DIR = REPO / "exp/step28_open_vocabulary_symptom_expansion"
PRODUCT = Path(os.environ.get("MEDMAP_PRODUCT_ROOT", str(Path.home() / "medmap")))   # master(읽기 전용)
DATA, OUT, DOCS, LOGS, PREVIEW = STEP / "data", STEP / "outputs", STEP / "docs", STEP / "logs", STEP / "preview"
for _d in (DATA, OUT, DOCS, LOGS, PREVIEW):
    _d.mkdir(exist_ok=True)

NLU_POLICY = "R2"                                        # STEP29.3 SELECTED_POLICY(data/policy_freeze.json)
SCHEMA_VERSION = "step30-doctor-review-v0"
RESEARCH_BANNER = {"research_simulation": True, "clinical_validation": "NONE", "human_verified_gold": 0,
                   "production_ready": False, "note": "연구용 통합 시뮬레이션 — 임상 정확도·안전성 검증 아님"}

_NLU = None
_PRODUCT_LOADED = False


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def dumps(o) -> str:
    return json.dumps(o, ensure_ascii=False, indent=1, sort_keys=False, default=str)


def dump_json(path, o) -> None:
    Path(path).write_text(dumps(o) + "\n", encoding="utf-8")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_csv(path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows: list[dict], fields: list[str] | None = None) -> None:
    fields = fields or (list(rows[0]) if rows else [])
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def nospace(s: str) -> str:
    return "".join(str(s).split())


def nlu():
    """STEP29.3 R2 진입점(step29_2_adapter.analyze). 원본 무수정 import."""
    global _NLU
    if _NLU is None:
        sys.path.insert(0, str(S293_DIR / "scripts"))
        import s293_common  # noqa: F401  (이전 단계 경로 설정)
        import step29_2_adapter as A
        sys.path.insert(0, str(STEP / "scripts"))      # 이 단계 scripts 가 먼저 잡히도록
        _NLU = A
    return _NLU


def product():
    """제품 패키지(medmap) import — 읽기·in-process 호출만. 서버·파일을 바꾸지 않는다."""
    global _PRODUCT_LOADED
    if not _PRODUCT_LOADED:
        sys.path.insert(0, str(PRODUCT))
        _PRODUCT_LOADED = True
    import medmap  # noqa: F401
    return sys.modules["medmap"]


def inventory() -> dict:
    """기존 77 concept(STEP28 existing_concept_inventory). SNOMED·UMLS 열은 읽어도 산출물에 쓰지 않는다."""
    keep = ("canonical_id", "canonical_name", "ddxplus_evidence_ids", "evidence_label_ko", "hpo_ids", "model_supported", "attributes")
    return {r["canonical_id"]: {k: r[k] for k in keep} for r in read_csv(S28_DIR / "data/existing_concept_inventory.csv")}
