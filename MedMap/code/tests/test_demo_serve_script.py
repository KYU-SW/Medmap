"""scripts/demo_serve.sh --dry-run: 오프라인 환경 적용, --stt-streaming 의 worker 기동 계획, GPU 바쁠 때 fail-safe.

프로세스·빌드·인증서를 만들지 않는다(--dry-run). GPU 확인은 가짜 스크립트(WAIT_FOR_RESOURCES)로 대신한다.
실행: ~/ai_env/bin/python -m unittest tests.test_demo_serve_script
"""
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "demo_serve.sh"


def fake_check(directory, rc):
    path = Path(directory) / f"check_{rc}.sh"
    path.write_text(f"#!/usr/bin/env bash\necho fake\nexit {rc}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def dry(*args, check_rc=0):
    with tempfile.TemporaryDirectory() as d:
        env = {**os.environ, "WAIT_FOR_RESOURCES": fake_check(d, check_rc)}
        for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "ORT_DISABLE_TELEMETRY"):
            env.pop(key, None)
        out = subprocess.run(["bash", str(SCRIPT), "--dry-run", "--no-build", *args], capture_output=True, text=True,
                             timeout=30, env=env, cwd=ROOT)
    return out.returncode, out.stdout + out.stderr


class DemoServeDryRunTest(unittest.TestCase):
    def test_default_applies_offline_env_and_keeps_legacy_voice(self):
        rc, out = dry("--http")
        self.assertEqual(rc, 0, out)
        for line in ("HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1", "ORT_DISABLE_TELEMETRY=1"):
            self.assertIn(line, out)
        self.assertIn("stt_streaming=off", out)
        self.assertNotIn("worker:", out)
        self.assertIn("--no-proxy-headers", out)

    def test_streaming_plans_worker_then_ct2_server(self):
        rc, out = dry("--http", "--stt-streaming", check_rc=0)
        self.assertEqual(rc, 0, out)
        self.assertIn("stt_streaming=on", out)
        self.assertIn("worker:", out)
        self.assertIn("stt_worker.py", out)
        self.assertIn("MEDMAP_STT_ENGINE=ct2", out)
        self.assertIn("MEDMAP_STT_STREAMING=1", out)
        self.assertLess(out.index("worker:"), out.index("server:"))

    def test_streaming_falls_back_to_legacy_when_gpu_busy(self):
        rc, out = dry("--http", "--stt-streaming", check_rc=1)
        self.assertEqual(rc, 0, out)
        self.assertIn("stt_streaming=off", out)
        self.assertIn("GPU busy", out)
        self.assertNotIn("worker:", out)

    def test_unknown_option_rejected(self):
        rc, _ = dry("--bogus")
        self.assertEqual(rc, 2)



def fake_python(directory, name, body):
    path = Path(directory) / name
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


class DemoServeRealPathWithFakesTest(unittest.TestCase):
    """dry-run 이 아닌 실제 경로: 가짜 worker·가짜 서버 python 으로 기동 순서·환경·정리만 확인(GPU·모델 없음)."""

    def run_script(self, worker_body):
        with tempfile.TemporaryDirectory() as d:
            marker = Path(d) / "server_env.txt"
            self.pid_file = Path(d) / "worker.pid"
            worker = fake_python(d, "worker_py", 'if [ "$1" = "-c" ]; then echo /nonexistent; exit 0; fi\n'
                                 + f'echo $$ > {self.pid_file}\n' + worker_body)
            server = fake_python(d, "server_py", f'env | grep -E "^(MEDMAP_STT_|HF_HUB_OFFLINE|ORT_DISABLE)" | sort > {marker}\n'
                                 + f'echo "ARGS $*" >> {marker}\n')
            env = {**os.environ, "WAIT_FOR_RESOURCES": fake_check(d, 0), "MEDMAP_WORKER_PYTHON": worker, "PYTHON": server,
                   "MEDMAP_STT_WORKER_SOCKET": str(Path(d) / "w.sock"), "PORT": "18999"}
            out = subprocess.run(["bash", str(SCRIPT), "--no-build", "--http", "--stt-streaming"], capture_output=True, text=True,
                                 timeout=120, env=env, cwd=ROOT)
            server_env = marker.read_text() if marker.exists() else ""
            self.worker_pid = int(self.pid_file.read_text()) if self.pid_file.exists() else None
        return out, server_env

    def test_worker_ready_then_streaming_server_and_worker_cleaned_up(self):
        out, server_env = self.run_script('echo "worker ready load_ms=1"; exec sleep 60\n')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("STT worker ready", out.stdout)
        self.assertIn("MEDMAP_STT_ENGINE=ct2", server_env)
        self.assertIn("MEDMAP_STT_STREAMING=1", server_env)
        self.assertIn("HF_HUB_OFFLINE=1", server_env)
        self.assertIn("ORT_DISABLE_TELEMETRY=1", server_env)
        self.assertIn("--no-proxy-headers", server_env)       # X-Forwarded-For 로 접속 주소(인계 기기별 잠금)를 바꾸지 못하게
        self.assertIsNotNone(self.worker_pid)
        self.assertFalse(Path(f"/proc/{self.worker_pid}").exists())                          # 서버가 끝나면 그 worker 도 정리(PID 로 확인)

    def test_worker_failure_falls_back_to_legacy_voice(self):
        out, server_env = self.run_script("echo boom; exit 3\n")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("did not become ready", out.stderr)
        self.assertNotIn("MEDMAP_STT_ENGINE=ct2", server_env)
        self.assertNotIn("MEDMAP_STT_STREAMING=1", server_env)
        self.assertIn("HF_HUB_OFFLINE=1", server_env)
        self.assertIn("--no-proxy-headers", server_env)


if __name__ == "__main__":
    unittest.main()
