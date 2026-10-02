"""OFFLINE_ON_PREM_FIRST 배포 자산 검사: 런타임에 필요한 모델·런타임·프론트가 로컬에 다 있는지, 프론트가 외부 URL 을 부르지 않는지.

GPU·네트워크를 쓰지 않는다(파일 확인 + 각 venv 에서 import 만, CUDA_VISIBLE_DEVICES='' · 오프라인 환경변수).
연결 시도 0 의 실제 검증은 scripts/release_offline_check.sh(네트워크 차단 + worker GPU) 가 맡는다 — 이 스크립트는 그 전 단계.

실행: source scripts/offline_env.sh && ~/ai_env/bin/python scripts/offline_assets_check.py [--json out.json]
종료 코드: 0 = OFFLINE_ASSETS_OK, 1 = 빠진 것 있음(목록 출력)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = re.compile(r"""https?://[^\s"'`)<>\\]+""")
# 문자열로만 존재하고 네트워크로 불리지 않는 것: XML 네임스페이스, React 오류 안내 링크(콘솔 문구)
ALLOWED_URL_PREFIXES = ("http://www.w3.org/", "https://react.dev/errors/")
TEXT_SUFFIXES = {".html", ".js", ".mjs", ".css", ".json", ".webmanifest", ".svg", ".txt"}
HF_WHISPER_REPO = "openai/whisper-large-v3-turbo"


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def check_frontend(dist: Path) -> dict:
    result = {"name": "frontend_dist", "path": str(dist)}
    if not (dist / "index.html").is_file():
        return {**result, "ok": False, "detail": "index.html 없음(npm run build 필요)"}
    found = set()
    for path in dist.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            for url in URL.findall(path.read_text(encoding="utf-8", errors="replace")):
                if not url.startswith(ALLOWED_URL_PREFIXES):
                    found.add(url)
    return {**result, "ok": not found, "external_urls": sorted(found), "bytes": _size(dist),
            "detail": "외부 URL 없음" if not found else f"외부 URL {len(found)}개"}


def check_ct2_model(model_dir: Path) -> dict:
    required = ["model.bin", "config.json", "tokenizer.json"]
    missing = [name for name in required if not (model_dir / name).is_file()]
    if not any((model_dir / v).is_file() for v in ("vocabulary.json", "vocabulary.txt")):
        missing.append("vocabulary.json|txt")
    return {"name": "ct2_whisper_model", "path": str(model_dir), "ok": not missing, "missing": missing,
            "bytes": _size(model_dir) if model_dir.is_dir() else 0, "detail": "ok" if not missing else f"없음: {missing}"}


def check_hf_whisper(hf_home: Path, repo: str = HF_WHISPER_REPO) -> dict:
    snapshots = hf_home / "hub" / ("models--" + repo.replace("/", "--")) / "snapshots"
    need = ["config.json", "preprocessor_config.json", "tokenizer.json"]
    for snap in sorted(snapshots.glob("*")) if snapshots.is_dir() else []:
        weights = any((snap / w).exists() for w in ("model.safetensors", "pytorch_model.bin"))
        if weights and all((snap / n).exists() for n in need):
            blobs = snap.parent.parent / "blobs"                 # snapshots/ 는 blobs 를 가리키는 링크 — 두 번 세지 않는다
            return {"name": "hf_whisper_cache", "path": str(snap), "ok": True, "bytes": _size(blobs if blobs.is_dir() else snap),
                    "detail": "legacy fallback 모델 캐시 있음"}
    return {"name": "hf_whisper_cache", "path": str(snapshots), "ok": False, "detail": f"{repo} 캐시 스냅샷 없음(HF_HOME 확인)"}


def check_python_imports(python: str, modules: list[str], extra_code: str = "", name: str = "python_env") -> dict:
    code = "import importlib,sys\nbad=[]\nfor m in %r:\n    try: importlib.import_module(m)\n    except Exception as e: bad.append(m)\nprint('MISSING:'+','.join(bad))\n%s" % (modules, extra_code)
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": "", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "ORT_DISABLE_TELEMETRY": "1"}
    if not Path(python).exists():
        return {"name": name, "ok": False, "detail": f"interpreter 없음: {python}"}
    try:
        out = subprocess.run([python, "-c", code], capture_output=True, text=True, timeout=120, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": name, "ok": False, "detail": type(exc).__name__}
    missing_line = next((line for line in out.stdout.splitlines() if line.startswith("MISSING:")), None)
    if out.returncode != 0 or missing_line is None:
        return {"name": name, "ok": False, "detail": f"rc={out.returncode}"}
    missing = [m for m in missing_line[len("MISSING:"):].split(",") if m]
    extra = [line for line in out.stdout.splitlines() if line.startswith("EXTRA:")]
    extra_ok = all(line.endswith("=1") for line in extra)
    return {"name": name, "python": python, "ok": not missing and extra_ok, "missing": missing, "extra": extra,
            "detail": "ok" if not missing and extra_ok else f"없음: {missing} {extra}"}


def overall(results: list[dict]) -> bool:
    return all(r.get("ok") for r in results)


def run_all() -> list[dict]:
    worker_py = os.environ.get("MEDMAP_WORKER_PYTHON", str(Path.home() / "stt_ct2_env/bin/python"))
    server_py = os.environ.get("MEDMAP_SERVER_PYTHON", sys.executable)
    worker_extra = ("import os\nfrom faster_whisper.utils import get_assets_path\n"
                    "print('EXTRA:silero_onnx=%d' % os.path.exists(os.path.join(get_assets_path(),'silero_vad_v6.onnx')))\n"
                    "import site\nsp=site.getsitepackages()[0]\n"
                    "print('EXTRA:cublas=%d' % os.path.isdir(os.path.join(sp,'nvidia/cublas/lib')))\n"
                    "print('EXTRA:cudnn=%d' % os.path.isdir(os.path.join(sp,'nvidia/cudnn/lib')))\n")
    server_extra = ("import os, kiwipiepy_model\n"
                    "print('EXTRA:kiwi_model=%d' % os.path.isdir(os.path.dirname(kiwipiepy_model.__file__)))\n")
    return [
        check_frontend(ROOT / "medmap-web" / "dist"),
        check_ct2_model(Path(os.environ.get("MEDMAP_CT2_MODEL_DIR", str(Path.home() / "models/faster-whisper-large-v3-turbo")))),
        check_hf_whisper(Path(os.environ.get("HF_HOME", str(Path.home() / ".cache/huggingface")))),
        check_python_imports(worker_py, ["numpy", "ctranslate2", "faster_whisper", "onnxruntime"], worker_extra, "worker_venv"),
        check_python_imports(server_py, ["fastapi", "uvicorn", "torch", "transformers", "av", "numpy", "kiwipiepy"],
                             server_extra, "server_venv"),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args()
    offline_env = {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "ORT_DISABLE_TELEMETRY")}
    results = run_all()
    for r in results:
        print(f"{'OK  ' if r['ok'] else 'FAIL'} {r['name']:18s} {r.get('detail', '')}"
              + (f"  ({r['bytes'] / 1e9:.2f} GB)" if r.get("bytes") else ""))
    env_ok = all(v == "1" for v in offline_env.values())
    print(f"{'OK  ' if env_ok else 'WARN'} offline_env        {offline_env}  (source scripts/offline_env.sh)")
    if args.json:
        Path(args.json).write_text(json.dumps({"results": results, "offline_env": offline_env}, ensure_ascii=False, indent=1))
    ok = overall(results)
    print("OFFLINE_ASSETS_OK" if ok else "OFFLINE_ASSETS_MISSING")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
