"""한국어 표시 용어 정본(medmap/data/terminology_ko.json) + loader 테스트.

표시 전용이다: 내부 ID(질환 class·E_*·V_*)는 key 로만 쓰고, review_needed 의 draft 는 어디로도 나가지 않는다.
실행: ~/ai_env/bin/python -m unittest tests.test_terminology
"""
import ast
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medmap import DiagnosisEngine, EvidenceCatalog, config
from medmap.terminology import CANONICAL_PATH, DisplayLabel, Terminology

CATALOG = EvidenceCatalog()
CLASSES = [str(c) for c in DiagnosisEngine(CATALOG, "k3").model.classes_]
RAW = json.loads(config.EVIDENCES_JSON.read_text())
LABELED_VALUES = {c for v in RAW.values() for c in (v.get("value_meaning") or {})}
NUMERIC_SCALE = {e for e, v in RAW.items() if v["data_type"] != "B" and not v.get("value_meaning")}
TERMS = Terminology()
DOC = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
LATIN_ALLOWED = {"HIV", "BMI", "cm"}
# 한국어 표시문 안에 괄호 병기로만 허용하는 약어(단독 사용 금지 — test_33 이 한국어 본문 동반을 확인)
ABBREV_ALLOWED = LATIN_ALLOWED | {"COPD", "NSAID", "NOAC", "ST", "OSA"}


class CanonicalFileTests(unittest.TestCase):
    def test_01_sections_and_schema(self):
        self.assertEqual(DOC["schema"], "medmap.terminology_ko/1")
        for key in ("version", "answer_labels", "diseases", "evidence_short", "evidence_questions", "values"):
            self.assertIn(key, DOC)

    def test_02_every_entry_is_ok_with_text_or_review_needed_with_draft_only(self):
        for section, text_key in (("diseases", "label_ko"), ("evidence_short", "label_ko"),
                                  ("evidence_questions", "text_ko"), ("values", "label_ko")):
            for key, entry in DOC[section].items():
                with self.subTest(section=section, key=key):
                    self.assertIn(entry["status"], ("ok", "review_needed"))
                    self.assertTrue(entry.get("source"))
                    if entry["status"] == "ok":
                        self.assertTrue(entry[text_key].strip())
                        self.assertNotIn("draft_ko", entry)
                    else:
                        self.assertNotIn(text_key, entry)          # draft 가 표시 필드에 섞이지 않는다
                        self.assertTrue(entry["draft_ko"].strip())
                        self.assertTrue(entry.get("review_reason"))

    def test_03_disease_keys_equal_model_classes(self):
        self.assertEqual(len(CLASSES), 49)
        self.assertEqual(set(DOC["diseases"]), set(CLASSES))

    def test_04_evidence_short_covers_all_223(self):
        self.assertEqual(set(DOC["evidence_short"]), set(CATALOG.ids))
        self.assertEqual(len(DOC["evidence_short"]), 223)

    def test_05_values_cover_all_labeled_codes(self):
        self.assertEqual(set(DOC["values"]), LABELED_VALUES)
        self.assertEqual(len(LABELED_VALUES), 199)
        self.assertEqual(NUMERIC_SCALE, {"E_56", "E_58", "E_59", "E_132", "E_134", "E_136"})

    def test_06_question_keys_are_real_evidence(self):
        self.assertTrue(set(DOC["evidence_questions"]) <= set(CATALOG.ids))

    def test_07_short_labels_are_noun_phrases(self):
        for key, entry in DOC["evidence_short"].items():
            label = entry.get("label_ko") or entry["draft_ko"]
            with self.subTest(key=key, label=label):
                self.assertNotRegex(label, r"[?？.。]$")
                self.assertLessEqual(len(label), 24)
                latin = set(re.findall(r"[A-Za-z]+", label))
                self.assertTrue(latin <= LATIN_ALLOWED, latin)

    def test_08_disease_crosscheck_is_boolean_flag_only(self):
        for key, entry in DOC["diseases"].items():
            with self.subTest(key=key):
                self.assertIn(entry["umls_kor_crosscheck"], (True, False, None))
                self.assertEqual(set(entry) - {"label_ko", "draft_ko", "status", "source", "umls_kor_crosscheck",
                                               "review_reason", "note"}, set())


class LoaderTests(unittest.TestCase):
    def test_10_ok_disease_returns_korean(self):
        label = TERMS.disease("Pneumonia")
        self.assertEqual(label, DisplayLabel("Pneumonia", "폐렴", False, "ok"))

    def test_11_review_needed_disease_returns_english_not_draft(self):
        # 실데이터 review_needed 는 0 이 될 수 있으므로 합성 정본으로 draft 비누출을 고정한다.
        doc = json.loads(json.dumps(DOC))
        doc["diseases"]["Pneumonia"] = {"draft_ko": "초안 폐렴", "status": "review_needed", "source": "standard_term",
                                        "review_reason": "test", "umls_kor_crosscheck": None}
        doc["evidence_short"]["E_201"] = {"draft_ko": "초안 기침", "status": "review_needed", "source": "test",
                                          "review_reason": "test"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.json"
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            terms = Terminology(path)
        label = terms.disease("Pneumonia")
        self.assertEqual((label.label, label.is_fallback, label.status), ("Pneumonia", True, "review_needed"))
        short = terms.evidence_short("E_201")
        self.assertEqual((short.label, short.is_fallback), (None, True))
        self.assertEqual([r["key"] for r in terms.review_needed()], ["Pneumonia", "E_201"])

    def test_12_unknown_disease_is_missing_fallback(self):
        self.assertEqual(TERMS.disease("Nope"), DisplayLabel("Nope", "Nope", True, "missing"))

    def test_13_evidence_short_and_value_and_question(self):
        self.assertEqual(TERMS.evidence_short("E_201").label, "기침")
        self.assertFalse(TERMS.evidence_short("E_201").is_fallback)
        self.assertEqual(TERMS.value("V_0").label, "북아프리카")
        missing = TERMS.value("V_nope", "orig")
        self.assertEqual((missing.label, missing.is_fallback, missing.status), ("orig", True, "missing"))
        english_q = next(e for e in CATALOG.ids if e not in DOC["evidence_questions"])
        q = TERMS.question(english_q, CATALOG.question(english_q).text)
        self.assertTrue(q.is_fallback)
        self.assertEqual(q.label, CATALOG.question(english_q).text)
        self.assertFalse(TERMS.question("E_91", "x").is_fallback)

    def test_14_review_needed_short_label_has_no_label(self):
        pending = [k for k, v in DOC["evidence_short"].items() if v["status"] == "review_needed"]
        for eid in pending:
            label = TERMS.evidence_short(eid)
            self.assertIsNone(label.label)
            self.assertTrue(label.is_fallback)

    def test_15_invalid_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "t.json"
            bad.write_text(json.dumps({"schema": "wrong"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "MEDMAP_TERMINOLOGY_INVALID"):
                Terminology(bad)
            leak = dict(DOC)
            leak["diseases"] = {"X": {"status": "review_needed", "label_ko": "x", "draft_ko": "x",
                                      "source": "standard_term", "review_reason": "r", "umls_kor_crosscheck": None}}
            bad.write_text(json.dumps(leak), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "MEDMAP_TERMINOLOGY_INVALID"):
                Terminology(bad)

    def test_16_coverage_numbers_are_consistent(self):
        cov = TERMS.coverage(CLASSES, CATALOG.ids, sorted(LABELED_VALUES))
        for part in ("diseases", "evidence_short", "values"):
            c = cov[part]
            self.assertEqual(c["translated"] + c["review_needed"] + c["missing"], c["total"])
            self.assertEqual(c["missing"], 0)
        self.assertEqual(cov["diseases"]["total"], 49)
        self.assertEqual(cov["diseases"]["fallback_english"], cov["diseases"]["review_needed"])
        self.assertEqual(cov["evidence_short"]["total"], 223)
        self.assertEqual(cov["values"]["total"], 199)
        q = cov["question_text"]
        self.assertEqual(q["korean"] + q["english_remaining"], 223)

    def test_17_loader_is_isolated_from_engine_and_mapper(self):
        tree = ast.parse((ROOT / "medmap" / "terminology.py").read_text(encoding="utf-8"))
        imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        for forbidden in ("intake", "next_information", "diagnosis", "patient_state", "question_presentation"):
            self.assertFalse(any(forbidden in m for m in imported), (forbidden, imported))

    def test_18_mapper_files_unchanged_since_freeze(self):
        diff = subprocess.run(["git", "diff", "--stat", "2372e2f", "--", "medmap/intake/"], cwd=ROOT,
                              capture_output=True, text=True)
        if diff.returncode != 0:
            self.skipTest("git history unavailable")
        self.assertEqual(diff.stdout.strip(), "")


class CompletionCoverageTests(unittest.TestCase):
    """C 완료 기준: 일반 사용자 경로에서 영어 fallback 0(제외 질문 E_134·E_152 만 질문 전문 없음)."""

    def test_30_all_diseases_korean(self):
        cov = TERMS.coverage(CLASSES, CATALOG.ids, sorted(LABELED_VALUES))["diseases"]
        self.assertEqual((cov["total"], cov["translated"], cov["review_needed"], cov["fallback_english"]), (49, 49, 0, 0))

    def test_31_all_short_labels_and_values_korean(self):
        cov = TERMS.coverage(CLASSES, CATALOG.ids, sorted(LABELED_VALUES))
        self.assertEqual((cov["evidence_short"]["translated"], cov["evidence_short"]["review_needed"]), (223, 0))
        self.assertEqual((cov["values"]["translated"], cov["values"]["review_needed"]), (199, 0))

    def test_32_every_selectable_question_has_korean_text(self):
        selectable = set(CATALOG.selectable_ids())
        self.assertEqual(set(CATALOG.ids) - selectable, set(config.EXCLUDED_QUESTIONS))
        ok = {k for k, v in DOC["evidence_questions"].items() if v["status"] == "ok"}
        self.assertEqual(selectable - ok, set())
        self.assertEqual(len(selectable), 221)
        q = TERMS.coverage(CLASSES, CATALOG.ids, sorted(LABELED_VALUES))["question_text"]
        self.assertEqual((q["korean"], q["review_needed"], q["english_remaining"]), (221, 0, 2))   # 남은 2 = 제외 질문

    def test_33_display_text_has_no_bare_english(self):
        texts = [(f"q:{k}", v["text_ko"]) for k, v in DOC["evidence_questions"].items() if v["status"] == "ok"]
        texts += [(f"d:{k}", v["label_ko"]) for k, v in DOC["diseases"].items() if v["status"] == "ok"]
        texts += [(f"s:{k}", v["label_ko"]) for k, v in DOC["evidence_short"].items() if v["status"] == "ok"]
        texts += [(f"v:{k}", v["label_ko"]) for k, v in DOC["values"].items() if v["status"] == "ok"]
        for key, text in texts:
            with self.subTest(key=key, text=text):
                latin = set(re.findall(r"[A-Za-z]+", text))
                self.assertTrue(latin <= ABBREV_ALLOWED, latin)
                self.assertRegex(text, r"[가-힣]")                     # 약어만 있는 표시문 금지

    def test_34_question_text_is_a_question(self):
        for key, entry in DOC["evidence_questions"].items():
            if entry["status"] != "ok":
                continue
            with self.subTest(key=key):
                self.assertRegex(entry["text_ko"], r"[?？)]$|습니다\.$")

    def test_35_presenter_serves_korean_for_every_selectable_question(self):
        from medmap.question_presentation import QuestionPresenter
        presenter = QuestionPresenter(CATALOG)
        fallback = [e for e in CATALOG.selectable_ids() if presenter.present(e).to_dict()["is_fallback"]]
        self.assertEqual(fallback, [])


class HumanGateDecisionTests(unittest.TestCase):
    """2026-09-27 사용자 human gate 확정 문구(임의 변경 금지 — 바꾸려면 새 human gate)."""

    def test_40_approved_wording(self):
        short = {"E_150": "대변·방귀 배출 가능 여부", "E_112": "들숨 때 쌕쌕거림 또는 기침 뒤 거친 숨소리",
                 "E_77": "색이 있거나 양이 많아진 가래", "E_9": "림프절(멍울) 부음·통증",
                 "E_51": "설사 또는 배변 횟수 증가", "E_65": "삼키기 어려움·삼킬 때 걸리는 느낌"}
        for key, label in short.items():
            with self.subTest(key=key):
                self.assertEqual(TERMS.evidence_short(key).label, label)
        self.assertEqual(TERMS.question("E_194").label, "숨을 들이쉴 때 쇳소리처럼 높은 소리가 나나요?")
        shown = [v.get("text_ko", "") for v in DOC["evidence_questions"].values()]      # 표시문만(note 제외)
        self.assertFalse([t for t in shown if "그렁거림" in t])


class PresenterIntegrationTests(unittest.TestCase):
    """QuestionPresenter 는 무수정 — 정본에서 생성된 question_labels_ko.json 을 통해 E_204 값이 한국어가 된다."""

    def test_20_e204_choices_are_korean(self):
        from medmap.question_presentation import QuestionPresenter
        view = QuestionPresenter(CATALOG).present("E_204").to_dict()
        coded = [c for c in view["choices"] if c["value"] is not None]
        self.assertEqual(len(coded), 12)
        self.assertTrue(all(not c["is_fallback"] for c in coded))
        self.assertIn("동남아시아", [c["label"] for c in coded])
        self.assertFalse(view["is_fallback"])                # 질문 전문도 한국어(QUESTION_KO_COMPLETION 완료)
        self.assertIn("해외여행", view["question_ko"])

    def test_21_all_labeled_value_choices_have_korean(self):
        from medmap.question_presentation import QuestionPresenter
        presenter = QuestionPresenter(CATALOG)
        for evidence_id in CATALOG.selectable_ids():
            for choice in presenter.present(evidence_id).to_dict()["choices"]:
                if choice["original_label"]:
                    self.assertFalse(choice["is_fallback"], (evidence_id, choice["value"]))


if __name__ == "__main__":
    unittest.main()
