"""STEP28.7 공통 — Ontology Mapping Quality & Safety Validation(연구용, SILVER). 기존 STEP20–28.6 산출물·코드는 읽기만 한다.

재사용(read-only): STEP28.6 SILVER 대응표·연결 결과·감사·격리 검사(exp/step28_6_llm_assisted_linking) · STEP28.5 한국어 검색기(KO_ONLY) ·
 STEP28 ontology 색인·검증기 · STEP27 POLICY_D 라우터(B4) · STEP27 합성 regression(INT_DEV_CORE 59 + INT_REGRESSION_CORE 109, gold 있음).
금지: LLM·외부 API 호출, 다운로드, 재학습, 제품 코드·PatientState 변경, 기존 산출물 덮어쓰기, MDRKOR·KCD5.
LOCAL_ONLY: SNOMED·UMLS 문자열이 들어가는 산출물(.gitignore) — 공개·push 금지.
"""
from __future__ import annotations

import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S286_DIR = REPO / "exp/step28_6_llm_assisted_linking"
sys.path.insert(0, str(S286_DIR / "scripts"))
import s286_common as S286  # noqa: E402

S285, S28 = S286.S285, S286.S28
S285_DIR, S28_DIR = S286.S285_DIR, S286.REPO / "exp/step28_open_vocabulary_symptom_expansion"
S27_DIR = S28.S27_DIR
WS = S286.WS
DATA, OUT, DOCS, LOGS = STEP / "data", STEP / "outputs", STEP / "docs", STEP / "logs"
for _d in (DATA, OUT, DOCS, LOGS):
    _d.mkdir(exist_ok=True)
read_csv, sha256, norm, nospace, rnd, load_json, dump_json, dumps, wcsv, ko_key = (S286.read_csv, S286.sha256, S286.norm, S286.nospace, S286.rnd,
                                                                                    S286.load_json, S286.dump_json, S286.dumps, S286.wcsv, S286.ko_key)
stem_key = S28.stem_key
ONT_DB = S286.ONT_DB
CHUNK = S286.CHUNK
GRADES = ("G3_SILVER_AUDITED", "G2_SILVER_AGREED", "G1_SINGLE_AUTHOR", "REJECTED")
ISOLATION_FAIL_SESSIONS = None   # analyze_isolation_failures 가 STEP28.6 검사 파일에서 읽는다(하드코딩 안 함)


def chunk_of(manifest_ids: list[str]) -> dict[str, str]:
    """STEP28.6 prepare_authoring_inputs 와 같은 순서·크기(230)로 id → 조각(cNN)."""
    return {i: f"c{k // CHUNK + 1:02d}" for k, i in enumerate(manifest_ids)}


def isolation_by_session() -> dict[str, bool]:
    d = load_json(S286_DIR / "outputs/authoring_isolation_check.json")
    return {k: v["PASS"] for k, v in d["sessions"].items()}


def row_isolation(author: str, chunk: str, sess: dict[str, bool]) -> str:
    k = f"author_{author}_{chunk}"
    if k not in sess:
        return "ISOLATION_UNVERIFIED"
    return "ISOLATION_PASS" if sess[k] else "ISOLATION_FAIL"
