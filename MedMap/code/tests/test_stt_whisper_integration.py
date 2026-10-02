"""실제 Whisper(openai/whisper-large-v3-turbo) 로드·GPU/CPU 추론 통합 테스트.

기본적으로 항상 skip 된다. 다음 조건을 모두 만족해야만 실행된다:
  - 환경변수 `MEDMAP_STT_REAL=1`
  - `stt/samples/medmap_tts_test.wav` 존재(read-only symlink, 이 테스트는 쓰지 않는다)

GPU 게이트(docs/superpowers/plans/2026-09-26-medmap-stt.md): 다른 세션이 GPU를 학습에 쓰고 있는 동안은
`MEDMAP_STT_REAL=1`로 이 파일을 실행하지 않는다. `nvidia-smi --query-compute-apps=pid --format=csv,noheader`가
비어 있고 `utilization.gpu`가 낮을 때만 사용자 승인 하에 실행한다. 이 세션은 이 플래그를 켜서 실행하지 않았다.

실행(조건 충족 시에만, 사용자 승인 후):
  MEDMAP_STT_REAL=1 ~/ai_env/bin/python -m unittest tests.test_stt_whisper_integration -v
"""
import os
import sys
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

SAMPLE_WAV = ROOT / "stt" / "samples" / "medmap_tts_test.wav"
REAL_ENABLED = os.environ.get("MEDMAP_STT_REAL") == "1"


@unittest.skipUnless(REAL_ENABLED, "MEDMAP_STT_REAL=1 이 아니면 skip(GPU 게이트, 기본 비활성)")
@unittest.skipUnless(SAMPLE_WAV.exists(), f"sample wav not found: {SAMPLE_WAV}")
class WhisperRealIntegrationTests(unittest.TestCase):
    """실제 모델 로드 + 실제 추론. unittest 디스커버리 기본 실행에서는 항상 skip."""

    def test_01_transcribes_sample_wav_via_endpoint(self):
        from fastapi.testclient import TestClient

        from medmap import api as api_module

        data = SAMPLE_WAV.read_bytes()
        with TestClient(api_module.app) as client:
            response = client.post("/v1/stt/transcribe", content=data,
                                   headers={"content-type": "audio/wav"})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(set(body), {"transcript", "duration_s", "language"})
        self.assertEqual(body["language"], "ko")
        self.assertGreater(len(body["transcript"]), 0)
        self.assertGreater(body["duration_s"], 0.0)

    def test_02_speech_module_transcribes_directly(self):
        from medmap import speech

        x, duration = speech.decode_audio(SAMPLE_WAV.read_bytes())
        speech.check_speech(x, duration)
        transcriber = speech.WhisperTranscriber()
        text = transcriber.transcribe(x)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)


if __name__ == "__main__":
    unittest.main()
