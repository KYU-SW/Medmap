"""한국어 표시 용어 정본 → 파생 파일 결정적 export.

정본: medmap/data/terminology_ko.json (편집은 여기서만)
생성(직접 편집 금지):
  1. medmap-web/src/generated/terminology_ko.json   — 웹 조회용. ok 항목만(diseases·evidence_short·values·questions) + source_sha256
  2. medmap/data/question_labels_ko.json            — QuestionPresenter·매퍼 테스트가 읽는 기존 형식. questions/values/답 라벨을 정본에서
  3. medmap/data/initial_evidence_ko.json           — 기존 파일의 용어 필드만 교체: label_ko(96), detail_source=="question_labels_ko" 인 detail_ko
  4. medmap-web/src/intake/initialCatalog.json      — 3 의 byte 사본(기존 sync-initial-catalog.mjs 와 같은 결과)
형식: json.dumps(indent=1, ensure_ascii=False), 끝 개행 없음(기존 두 파일의 형식과 byte 동일).

실행: ~/ai_env/bin/python scripts/export_web_terminology.py          # 쓰기
      ~/ai_env/bin/python scripts/export_web_terminology.py --check  # 불일치 시 exit 1, 쓰지 않음
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medmap.terminology import CANONICAL_PATH, Terminology  # noqa: E402

WEB_OUT = ROOT / "medmap-web" / "src" / "generated" / "terminology_ko.json"
QUESTION_LABELS = ROOT / "medmap" / "data" / "question_labels_ko.json"
INITIAL_CATALOG = ROOT / "medmap" / "data" / "initial_evidence_ko.json"
WEB_INITIAL_COPY = ROOT / "medmap-web" / "src" / "intake" / "initialCatalog.json"


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)


def _ok(doc: dict, section: str, field: str = "label_ko") -> dict:
    return {k: v[field] for k, v in doc[section].items() if v["status"] == "ok"}


def build_outputs() -> dict:
    """{Path: str} — 디스크를 쓰지 않는다. 기존 파일은 용어 이외 필드(header·rank 등)만 읽는다."""
    terms = Terminology(CANONICAL_PATH)          # 형식 검증 포함
    doc = terms.doc
    web = {
        "schema": "medmap.web_terminology_ko/1",
        "generated_by": "scripts/export_web_terminology.py",
        "source": "medmap/data/terminology_ko.json",
        "source_version": doc["version"],
        "source_sha256": hashlib.sha256(CANONICAL_PATH.read_bytes()).hexdigest(),
        "note": "생성물 — 직접 편집 금지. status ok 항목만 포함(review_needed·미등록은 내부 ID/원문 fallback).",
        "diseases": _ok(doc, "diseases"),
        "evidence_short": _ok(doc, "evidence_short"),
        "values": _ok(doc, "values"),
        "questions": _ok(doc, "evidence_questions", "text_ko"),
    }

    legacy = json.loads(QUESTION_LABELS.read_text(encoding="utf-8"))
    labels = {key: legacy[key] for key in ("schema", "source", "note")}
    labels["questions"] = _ok(doc, "evidence_questions", "text_ko")
    labels["values"] = _ok(doc, "values")
    labels.update(doc["answer_labels"])
    labels = {key: labels[key] for key in ("schema", "source", "note", "questions", "values",
                                           "unknown_choice_label", "yes_label", "no_label")}

    initial = json.loads(INITIAL_CATALOG.read_text(encoding="utf-8"))
    short = _ok(doc, "evidence_short")
    questions = _ok(doc, "evidence_questions", "text_ko")
    for item in initial["items"]:
        evidence_id = item["evidence_id"]
        if evidence_id not in short:
            raise ValueError(f"MEDMAP_TERMINOLOGY_INVALID:initial_without_ok_short_label:{evidence_id}")
        item["label_ko"] = short[evidence_id]
        if item["detail_source"] == "question_labels_ko":
            if evidence_id not in questions:
                raise ValueError(f"MEDMAP_TERMINOLOGY_INVALID:initial_detail_without_question:{evidence_id}")
            item["detail_ko"] = questions[evidence_id]
    initial_text = _dump(initial)

    return {WEB_OUT: _dump(web), QUESTION_LABELS: _dump(labels), INITIAL_CATALOG: initial_text,
            WEB_INITIAL_COPY: initial_text}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    outputs = build_outputs()
    stale = [p for p, text in outputs.items() if not p.exists() or p.read_bytes() != text.encode("utf-8")]
    for path in stale:
        print(("STALE " if args.check else "WRITE ") + str(path.relative_to(ROOT)))
    if args.check:
        return 1 if stale else 0
    for path in stale:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(outputs[path].encode("utf-8"))
    print(f"ok ({len(stale)} written, {len(outputs) - len(stale)} unchanged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
