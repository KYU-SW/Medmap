"""Natural Intake v1: 한국어 자유문장 → DDXPlus evidence 후보(deterministic, 진단 엔진과 분리)."""
from .mapper import AliasValidationError, IntakeMapper, extract, load_aliases, load_negative_policy, normalize

__all__ = ["AliasValidationError", "IntakeMapper", "extract", "load_aliases", "load_negative_policy", "normalize"]
