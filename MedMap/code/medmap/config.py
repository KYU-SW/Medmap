"""MedMap 제품 코드 설정: STEP16B에서 검증된 산출물 경로만 참조한다(수정·재학습 없음)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "ddxplus" / "en"
EVIDENCES_JSON = DATA_DIR / "release_evidences.json"

STEP16B_DIR = ROOT / "exp" / "step16b_next_information_validation"
IG_TABLE_NPZ = STEP16B_DIR / "ig_table_step16b_train.npz"
MODEL_PATHS = {"k3": STEP16B_DIR / "model_k3.pkl", "k5": STEP16B_DIR / "model_k5.pkl", "k10": STEP16B_DIR / "model_k10.pkl"}
MODEL_CONTEXTS = ("k3", "k5", "k10")

# STEP16B 사전등록에서 제외된 질문(결과 확인 후 재투입 금지)
EXCLUDED_QUESTIONS = ("E_134", "E_152")
# 런타임에서 절대 읽지 않는 경로(연구 봉인)
FORBIDDEN_PATHS = (DATA_DIR / "release_validate_patients", DATA_DIR / "release_test_patients", DATA_DIR / "release_conditions.json")
IG_ALPHA = 1.0
DEFAULT_MAX_QUESTIONS = 3


class MedMapForbiddenPath(Exception):
    pass


def check_path(path) -> Path:
    p = Path(path).resolve()
    if p in {q.resolve() for q in FORBIDDEN_PATHS}:
        raise MedMapForbiddenPath(f"MEDMAP_FORBIDDEN_PATH:{p.name}")
    return p
