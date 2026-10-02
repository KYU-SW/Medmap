"""Clinical Summary 의 LabelProvider 훅에 한국어 용어 정본을 연결하는 선택형 provider 테스트.

기본 PresenterLabelProvider 동작(질환 영문 + is_fallback=True)은 그대로 두고, TerminologyLabelProvider 를 쓸 때만
질환 표시명이 한국어가 된다. 계산 규칙(top3·순서·확률)은 불변.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medmap import EvidenceCatalog, PatientState, positive
from medmap.clinical_summary import PresenterLabelProvider, TerminologyLabelProvider, build_clinical_summary

CATALOG = EvidenceCatalog()
STATE = PatientState.new(30, "F", "E_53", {"E_91": positive()})
TOP3 = [("URTI", 0.4), ("Pulmonary neoplasm", 0.2), ("Anemia", 0.1)]


class TerminologyLabelProviderTests(unittest.TestCase):
    def test_01_korean_disease_names_with_internal_name_kept(self):
        cands = build_clinical_summary(STATE, "k3", TOP3, labels=TerminologyLabelProvider(CATALOG))["diagnosis_candidates"]
        self.assertEqual([c["name"] for c in cands], ["URTI", "Pulmonary neoplasm", "Anemia"])
        self.assertEqual(cands[0]["display_name"], "상기도 감염")
        self.assertFalse(cands[0]["is_fallback"])
        self.assertEqual(cands[1]["display_name"], "폐 종양")                 # 2026-09-27 직역 확정(이전 review_needed)
        self.assertFalse(cands[1]["is_fallback"])
        self.assertTrue(all(not c["is_fallback"] for c in cands))
        self.assertEqual([c["probability"] for c in cands], [0.4, 0.2, 0.1])

    def test_02_default_provider_unchanged(self):
        cands = build_clinical_summary(STATE, "k3", TOP3, labels=PresenterLabelProvider(CATALOG))["diagnosis_candidates"]
        self.assertEqual(cands[0]["display_name"], "URTI")
        self.assertTrue(cands[0]["is_fallback"])

    def test_03_other_labels_identical_to_presenter_provider(self):
        a = build_clinical_summary(STATE, "k3", TOP3, labels=TerminologyLabelProvider(CATALOG))
        b = build_clinical_summary(STATE, "k3", TOP3, labels=PresenterLabelProvider(CATALOG))
        a.pop("diagnosis_candidates"); b.pop("diagnosis_candidates")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
