"""EXP-02 동결 판독문 분류(v2·v3b)를 EXP-03 증거로 연결 — EXP-02 코드는 읽기 전용 import(수정 없음).

보존: 급성(ACUTE_POS) · 만성/지속(CHRONIC_OR_PERSISTENT, 'PE 없음' 아님) · 명시 음성(NEGATIVE) · 불확실(UNCERTAIN) ·
      판정 보류/언급 없음(NO_MENTION) · v2/v3b 문장 유형(uncertainty_status) · 출처 · 이용 가능 시각.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

EXP02 = Path(os.environ.get("EXP03_EXP02") or Path(__file__).resolve().parents[1] / "exp02_mimic_graph")
if str(EXP02) not in sys.path:
    sys.path.insert(0, str(EXP02))

import ext_pe_eval_v3 as E3  # noqa: E402  (동결 v3b·v2 분류기, 수정 금지)

from reassess import Evidence  # noqa: E402

PRED_TO_CLASS = {"PRED_ACUTE_POS": "ACUTE_POS", "PRED_CHRONIC_OR_PERSISTENT": "CHRONIC_OR_PERSISTENT",
                 "PRED_UNCERTAIN": "UNCERTAIN", "PRED_NEGATIVE": "NEGATIVE", "PRED_NO_MENTION": "NO_MENTION"}
CLASS_TO_STATUS = {"ACUTE_POS": "POSITIVE", "CHRONIC_OR_PERSISTENT": "POSITIVE", "NEGATIVE": "NEGATIVE",
                   "UNCERTAIN": "UNCERTAIN", "NO_MENTION": "NOT_ASSESSABLE"}


def classify(text: str, variant: str = "v3b") -> tuple[str, str]:
    pred, cats = E3.predict_variant(text, variant)
    return PRED_TO_CLASS[pred], "/".join(cats)


def report_evidence(event_id, encounter_id, text, observed_at, available_at, order_ref="", variant="v3b",
                    supersedes=None, revision_id="r1", source_reference=None) -> Evidence:
    cls, cats = classify(text, variant)
    return Evidence(event_id, encounter_id, "IMAGING_REPORT", f"radiology_report_{variant}",
                    source_reference if source_reference is not None else f"synthetic:{event_id}",
                    observed_at, available_at, available_at, CLASS_TO_STATUS[cls], concept="CONCEPT:ctpa_filling_defect",
                    uncertainty_status=f"{variant}:{cats}", pe_class=cls, order_ref=order_ref,
                    revision_id=revision_id, supersedes=supersedes)
