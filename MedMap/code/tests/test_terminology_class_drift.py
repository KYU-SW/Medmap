"""Class drift guard: 정본 diseases key 집합 == k3 모델 classes_.

모델을 재학습·교체해 class 가 바뀌면 이 테스트가 실패한다 → 정본 diseases 를 먼저 맞춘다.
모델 파일은 git 에 없다(worktree 는 read-only symlink). 파일이 없을 때만 skip 한다.
"""
import copy
import json
import pickle
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medmap import config
from medmap.terminology import CANONICAL_PATH, Terminology

MODEL_K3 = Path(config.MODEL_PATHS["k3"])


@unittest.skipUnless(MODEL_K3.exists(), f"model file absent: {MODEL_K3} (worktree 는 ~/medmap 의 pkl symlink 필요)")
class ClassDriftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MODEL_K3, "rb") as fh:
            cls.classes = [str(c) for c in pickle.load(fh).classes_]

    def test_01_canonical_disease_keys_equal_k3_classes(self):
        drift = Terminology().disease_key_drift(self.classes)
        self.assertEqual(drift, {"missing": [], "extra": []})
        self.assertEqual(len(self.classes), 49)

    def test_02_drift_is_detected_both_ways(self):
        doc = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
        changed = copy.deepcopy(doc)
        removed = self.classes[0]
        changed["diseases"].pop(removed)
        changed["diseases"]["Not A Model Class"] = {"label_ko": "가짜", "status": "ok", "source": "standard_term",
                                                    "umls_kor_crosscheck": None}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "terminology_ko.json"
            path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
            drift = Terminology(path).disease_key_drift(self.classes)
        self.assertEqual(drift, {"missing": [removed], "extra": ["Not A Model Class"]})


if __name__ == "__main__":
    unittest.main()
