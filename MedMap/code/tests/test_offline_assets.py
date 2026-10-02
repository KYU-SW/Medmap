"""오프라인 배포 자산 검사(scripts/offline_assets_check.py) — 임시 폴더로 각 검사 함수의 통과·실패를 확인한다.

실행: ~/ai_env/bin/python -m unittest tests.test_offline_assets
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import offline_assets_check as oac


def touch(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class FrontendCheckTest(unittest.TestCase):
    def test_bundle_without_external_urls_passes_and_namespace_strings_are_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            dist = Path(d)
            touch(dist / "index.html", '<script type="module" src="/assets/index.js"></script>')
            touch(dist / "assets/index.js", 'createElementNS("http://www.w3.org/2000/svg");throw Error("https://react.dev/errors/"+e)')
            result = oac.check_frontend(dist)
        self.assertTrue(result["ok"], result)

    def test_cdn_font_or_api_url_fails_and_is_listed(self):
        with tempfile.TemporaryDirectory() as d:
            dist = Path(d)
            touch(dist / "index.html", '<link href="https://fonts.googleapis.com/css2?family=Noto" rel="stylesheet">')
            touch(dist / "assets/index.js", 'fetch("https://api.example.com/v1/x")')
            result = oac.check_frontend(dist)
        self.assertFalse(result["ok"])
        self.assertIn("https://fonts.googleapis.com/css2?family=Noto", result["external_urls"])
        self.assertIn("https://api.example.com/v1/x", result["external_urls"])

    def test_missing_build_fails(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(oac.check_frontend(Path(d) / "dist")["ok"])


class ModelCheckTest(unittest.TestCase):
    def test_ct2_model_requires_weights_config_tokenizer(self):
        with tempfile.TemporaryDirectory() as d:
            m = Path(d)
            for name in ("model.bin", "config.json", "tokenizer.json", "vocabulary.json"):
                touch(m / name)
            self.assertTrue(oac.check_ct2_model(m)["ok"])
            (m / "model.bin").unlink()
            result = oac.check_ct2_model(m)
        self.assertFalse(result["ok"])
        self.assertIn("model.bin", result["missing"])

    def test_hf_whisper_snapshot_in_cache(self):
        with tempfile.TemporaryDirectory() as d:
            hf = Path(d)
            snap = hf / "hub/models--openai--whisper-large-v3-turbo/snapshots/abc"
            for name in ("config.json", "model.safetensors", "preprocessor_config.json", "tokenizer.json"):
                touch(snap / name)
            self.assertTrue(oac.check_hf_whisper(hf)["ok"])
            self.assertFalse(oac.check_hf_whisper(Path(d) / "empty")["ok"])


class PythonEnvCheckTest(unittest.TestCase):
    def test_imports_checked_in_the_target_interpreter(self):
        self.assertTrue(oac.check_python_imports(sys.executable, ["json", "sqlite3"])["ok"])
        bad = oac.check_python_imports(sys.executable, ["json", "surely_not_installed_medmap_x"])
        self.assertFalse(bad["ok"])
        self.assertIn("surely_not_installed_medmap_x", bad["detail"])

    def test_extra_condition_zero_fails(self):
        self.assertTrue(oac.check_python_imports(sys.executable, ["json"], "print('EXTRA:silero_onnx=1')")["ok"])
        self.assertFalse(oac.check_python_imports(sys.executable, ["json"], "print('EXTRA:silero_onnx=0')")["ok"])

    def test_missing_interpreter_fails(self):
        self.assertFalse(oac.check_python_imports("/nonexistent/python", ["json"])["ok"])


class ReportTest(unittest.TestCase):
    def test_overall_fails_if_any_check_fails(self):
        self.assertTrue(oac.overall([{"name": "a", "ok": True}, {"name": "b", "ok": True}]))
        self.assertFalse(oac.overall([{"name": "a", "ok": True}, {"name": "b", "ok": False}]))


if __name__ == "__main__":
    unittest.main()
