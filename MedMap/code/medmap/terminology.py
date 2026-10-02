"""한국어 표시 용어 정본 loader (presentation only).

정본: `medmap/data/terminology_ko.json` — 질환 표시명 · evidence 짧은 표시명 · 질문 전문 · value 표시명 · 답 라벨.
- 내부 ID(모델 질환 class 문자열, E_*, V_*)는 key 로만 쓰고 바꾸지 않는다. 모델·PatientState·IG·매퍼와 무관하다.
- `status == "ok"` 항목만 한국어를 돌려준다. `review_needed` 항목은 `draft_ko` 만 가지며 이 모듈은 draft 를 절대 반환하지 않는다.
- 런타임 번역·LLM 호출 없음. 파생 파일(question_labels_ko.json 등)은 `scripts/export_web_terminology.py` 가 이 정본에서 생성한다.
설계: docs/superpowers/plans/2026-09-26-medmap-korean-terminology.md (Revision 2)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CANONICAL_PATH = Path(__file__).resolve().parent / "data" / "terminology_ko.json"
SCHEMA = "medmap.terminology_ko/1"
SECTIONS = {"diseases": "label_ko", "evidence_short": "label_ko", "evidence_questions": "text_ko",
            "values": "label_ko"}
STATUSES = ("ok", "review_needed")


@dataclass(frozen=True)
class DisplayLabel:
    key: str                 # 내부 ID 그대로
    label: str | None        # 화면 문자열(한국어 또는 fallback). 짧은 표시명 fallback 은 None
    is_fallback: bool        # True = ok 한국어가 없어 원문(또는 None)을 씀
    status: str              # "ok" | "review_needed" | "missing"


def _invalid(detail: str) -> ValueError:
    return ValueError(f"MEDMAP_TERMINOLOGY_INVALID:{detail}")


def validate(doc: dict) -> None:
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise _invalid("schema")
    labels = doc.get("answer_labels")
    if not isinstance(labels, dict) or not all(labels.get(k) for k in ("unknown_choice_label", "yes_label", "no_label")):
        raise _invalid("answer_labels")
    for section, text_key in SECTIONS.items():
        entries = doc.get(section)
        if not isinstance(entries, dict):
            raise _invalid(section)
        for key, entry in entries.items():
            status = entry.get("status") if isinstance(entry, dict) else None
            if status not in STATUSES or not entry.get("source"):
                raise _invalid(f"{section}:{key}:status/source")
            if status == "ok":
                if not str(entry.get(text_key) or "").strip() or "draft_ko" in entry:
                    raise _invalid(f"{section}:{key}:ok")
            elif text_key in entry or not str(entry.get("draft_ko") or "").strip() or not entry.get("review_reason"):
                raise _invalid(f"{section}:{key}:review_needed")


class Terminology:
    def __init__(self, path=None):
        self.path = Path(path or CANONICAL_PATH)
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise _invalid(f"read:{exc.__class__.__name__}") from exc
        validate(doc)
        self.doc = doc
        self.answer_labels = dict(doc["answer_labels"])

    # ---- 조회 ----
    def _lookup(self, section: str, key: str, fallback):
        entry = self.doc[section].get(key)
        if entry is None:
            return DisplayLabel(key, fallback, True, "missing")
        if entry["status"] == "ok":
            return DisplayLabel(key, entry[SECTIONS[section]], False, "ok")
        return DisplayLabel(key, fallback, True, entry["status"])

    def disease(self, name: str) -> DisplayLabel:
        """질환 표시명. ok 가 아니면 모델 class 명(영문) 그대로."""
        return self._lookup("diseases", name, name)

    def evidence_short(self, evidence_id: str) -> DisplayLabel:
        """evidence 짧은 표시명(명사구). ok 가 아니면 label=None."""
        return self._lookup("evidence_short", evidence_id, None)

    def question(self, evidence_id: str, fallback: str | None = None) -> DisplayLabel:
        """질문 전문. 없으면 호출자가 준 원문(영문) fallback."""
        return self._lookup("evidence_questions", evidence_id, fallback)

    def value(self, code: str, fallback: str | None = None) -> DisplayLabel:
        return self._lookup("values", code, fallback)

    # ---- 감사 ----
    def review_needed(self) -> list[dict]:
        return [{"section": section, "key": key, "draft_ko": entry["draft_ko"], "review_reason": entry["review_reason"]}
                for section in SECTIONS for key, entry in self.doc[section].items()
                if entry["status"] == "review_needed"]

    def disease_key_drift(self, disease_classes) -> dict:
        """정본 diseases key 와 모델 class 집합의 차이. 둘 다 빈 목록이어야 정상."""
        classes, keys = set(disease_classes), set(self.doc["diseases"])
        return {"missing": sorted(classes - keys), "extra": sorted(keys - classes)}

    def _count(self, section: str, keys) -> dict:
        keys = list(keys)
        entries = self.doc[section]
        ok = sum(1 for k in keys if entries.get(k, {}).get("status") == "ok")
        review = sum(1 for k in keys if entries.get(k, {}).get("status") == "review_needed")
        return {"total": len(keys), "translated": ok, "review_needed": review, "missing": len(keys) - ok - review,
                "extra_keys": sorted(set(entries) - set(keys))}

    def coverage(self, disease_classes, evidence_ids, value_codes) -> dict:
        diseases = self._count("diseases", disease_classes)
        diseases["fallback_english"] = diseases["total"] - diseases["translated"]
        questions = self._count("evidence_questions", evidence_ids)
        return {
            "diseases": diseases,
            "evidence_short": self._count("evidence_short", evidence_ids),
            "values": self._count("values", value_codes),
            "question_text": {"total": questions["total"], "korean": questions["translated"],
                              "review_needed": questions["review_needed"],
                              "english_remaining": questions["total"] - questions["translated"]},
        }
