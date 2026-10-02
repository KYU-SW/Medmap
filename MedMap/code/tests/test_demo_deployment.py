"""P2-7 demo deployment 계약 — opt-in 정적 서빙(same-origin)·STT prewarm. 기본 동작은 그대로.

계약: docs/superpowers/plans/2026-09-27-medmap-demo-deployment.md
실제 Whisper 는 로드하지 않는다(가짜 loader, GPU 없음).
실행: ~/ai_env/bin/python -m unittest tests.test_demo_deployment -v
"""
import sys
import tempfile
import threading
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from medmap import api as api_module
from medmap import speech


def make_dist(tmp: Path, with_index: bool = True) -> Path:
    dist = tmp / "dist"
    (dist / "assets").mkdir(parents=True)
    if with_index:
        (dist / "index.html").write_text("<!doctype html><title>MedMap</title><div id=root></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('medmap')", encoding="utf-8")
    return dist


class WebDistTests(unittest.TestCase):
    def test_default_app_does_not_serve_static(self):
        # MEDMAP_SERVE_WEB_DIST 미설정(테스트 환경) → 현재와 같이 / 는 404
        self.assertIsNone(api_module.WEB_DIST)
        response = TestClient(api_module.app).get("/")
        self.assertEqual(response.status_code, 404)

    def test_mount_serves_index_and_assets_without_shadowing_api_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = make_dist(Path(tmp))
            app = FastAPI()

            @app.get("/health")
            def health():
                return {"status": "ok"}

            @app.post("/v1/echo")
            def echo(body: dict):
                return body

            api_module.mount_web_dist(app, dist)
            client = TestClient(app)
            root = client.get("/")
            self.assertEqual(root.status_code, 200)
            self.assertIn("<title>MedMap</title>", root.text)
            self.assertEqual(client.get("/assets/app.js").text, "console.log('medmap')")
            self.assertEqual(client.get("/health").json(), {"status": "ok"})
            self.assertEqual(client.post("/v1/echo", json={"a": 1}).json(), {"a": 1})
            self.assertEqual(client.get("/nope.js").status_code, 404)
            # 잘못된 method 는 정적 파일로 삼켜지지 않고 기존처럼 405/404 를 유지한다
            self.assertEqual(client.post("/health").status_code, 405)
            self.assertNotEqual(client.get("/v1/echo").status_code, 200)
            self.assertNotIn("<title>MedMap</title>", client.get("/v1/echo").text)

    def test_mount_fails_loudly_without_index_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = make_dist(Path(tmp), with_index=False)
            with self.assertRaises(ValueError):
                api_module.mount_web_dist(FastAPI(), dist)
            with self.assertRaises(ValueError):
                api_module.mount_web_dist(FastAPI(), Path(tmp) / "missing")


class PrewarmTests(unittest.TestCase):
    def test_prewarm_loads_in_background_thread(self):
        loaded = threading.Event()
        caller = {}

        def loader():
            caller["thread"] = threading.current_thread()
            loaded.set()
            return lambda *a, **k: {"text": "ok"}

        transcriber = speech.WhisperTranscriber(loader=loader)
        thread = speech.start_prewarm(transcriber)
        thread.join(timeout=5)
        self.assertTrue(loaded.is_set())
        self.assertIs(caller["thread"], thread)
        self.assertIsNot(thread, threading.main_thread())
        self.assertTrue(thread.daemon)
        self.assertIsNotNone(transcriber._pipeline)

    def test_prewarm_failure_is_swallowed_and_retryable(self):
        calls = {"n": 0}

        def loader():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("CUDA out of memory")
            return lambda *a, **k: {"text": "ok"}

        transcriber = speech.WhisperTranscriber(loader=loader)
        with self.assertLogs("medmap.speech", level="WARNING") as logs:
            speech.start_prewarm(transcriber).join(timeout=5)
        self.assertIsNone(transcriber._pipeline)
        self.assertTrue(any("prewarm" in line for line in logs.output))
        transcriber._ensure_loaded()          # 첫 요청 때 기존 lazy load 가 다시 시도
        self.assertEqual(calls["n"], 2)
        self.assertIsNotNone(transcriber._pipeline)

    def test_lifespan_prewarms_only_when_flag_set(self):
        fake = speech.WhisperTranscriber(loader=lambda: (lambda *a, **k: {"text": "ok"}))
        with patch.object(api_module, "STT_PREWARM", False), \
                patch.object(speech, "start_prewarm") as start:
            with TestClient(api_module.app):
                pass
            start.assert_not_called()
        with patch.object(api_module, "STT_PREWARM", True), \
                patch.object(speech, "get_transcriber", return_value=fake):
            with TestClient(api_module.app) as client:
                self.assertTrue(client.get("/health").json()["engine_ready"])
                for _ in range(50):
                    if fake._pipeline is not None:
                        break
                    threading.Event().wait(0.1)
            self.assertIsNotNone(fake._pipeline)


if __name__ == "__main__":
    unittest.main()
