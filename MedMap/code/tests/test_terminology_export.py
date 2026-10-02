"""정본 → 파생 파일 sync 테스트.

`scripts/export_web_terminology.py` 를 다시 돌린 결과가 커밋된 파생 파일과 byte 단위로 같아야 한다.
실패하면: ~/ai_env/bin/python scripts/export_web_terminology.py 실행 후 diff 를 검토해 함께 커밋한다.
"""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import export_web_terminology as exporter  # noqa: E402
from medmap.terminology import CANONICAL_PATH  # noqa: E402

OUTPUTS = exporter.build_outputs()


class ExportSyncTests(unittest.TestCase):
    def test_01_expected_output_set(self):
        self.assertEqual(set(OUTPUTS), {exporter.WEB_OUT, exporter.QUESTION_LABELS, exporter.INITIAL_CATALOG,
                                        exporter.WEB_INITIAL_COPY})

    def test_02_committed_files_equal_fresh_export(self):
        for path, content in OUTPUTS.items():
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertEqual(path.read_bytes(), content.encode("utf-8"))

    def test_03_export_is_deterministic(self):
        self.assertEqual(OUTPUTS, exporter.build_outputs())

    def test_04_web_file_has_ok_entries_only_and_source_hash(self):
        web = json.loads(OUTPUTS[exporter.WEB_OUT])
        doc = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
        self.assertEqual(web["source_sha256"], hashlib.sha256(CANONICAL_PATH.read_bytes()).hexdigest())
        for section in ("diseases", "evidence_short", "values"):
            ok = {k: v["label_ko"] for k, v in doc[section].items() if v["status"] == "ok"}
            self.assertEqual(web[section], ok)
        self.assertEqual(web["questions"], {k: v["text_ko"] for k, v in doc["evidence_questions"].items()
                                            if v["status"] == "ok"})
        drafts = {v["draft_ko"] for s in ("diseases", "evidence_short", "values", "evidence_questions") for v in doc[s].values()
                  if v["status"] == "review_needed"}
        text = OUTPUTS[exporter.WEB_OUT]
        for draft in drafts:
            self.assertNotIn(f'"{draft}"', text)

    def test_05_legacy_mirrors_match_canonical(self):
        doc = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
        labels = json.loads(OUTPUTS[exporter.QUESTION_LABELS])
        self.assertEqual(labels["questions"], {k: v["text_ko"] for k, v in doc["evidence_questions"].items()
                                               if v["status"] == "ok"})
        self.assertEqual(labels["values"], {k: v["label_ko"] for k, v in doc["values"].items() if v["status"] == "ok"})
        for key in ("unknown_choice_label", "yes_label", "no_label"):
            self.assertEqual(labels[key], doc["answer_labels"][key])
        initial = json.loads(OUTPUTS[exporter.INITIAL_CATALOG])
        for item in initial["items"]:
            self.assertEqual(item["label_ko"], doc["evidence_short"][item["evidence_id"]]["label_ko"])
            if item["detail_source"] == "question_labels_ko":
                self.assertEqual(item["detail_ko"], doc["evidence_questions"][item["evidence_id"]]["text_ko"])
        self.assertEqual(OUTPUTS[exporter.WEB_INITIAL_COPY], OUTPUTS[exporter.INITIAL_CATALOG])

    def test_06_check_mode_passes_on_clean_tree(self):
        run = subprocess.run([sys.executable, str(ROOT / "scripts" / "export_web_terminology.py"), "--check"],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
