"""공식 영문 배포본 5개 다운로드. Python 표준 라이브러리만 사용합니다."""
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
URL = "https://api.figshare.com/v2/articles/22687585/versions/2"

def digest(path):
    h = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

if __name__ == "__main__":
    with urllib.request.urlopen(URL, timeout=60) as response:
        metadata = json.load(response)
    (ROOT / "source_manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print("License:", metadata["license"], flush=True)
    for item in metadata["files"]:
        target = DATA / item["name"]
        expected = item["computed_md5"]
        if target.exists() and digest(target) == expected:
            print("Verified:", target.name, flush=True)
            continue
        print("Downloading:", target.name, item["size"], "bytes", flush=True)
        temporary = target.with_suffix(target.suffix + ".part")
        with urllib.request.urlopen(item["download_url"], timeout=120) as source:
            with temporary.open("wb") as destination:
                while block := source.read(1024 * 1024):
                    destination.write(block)
        if temporary.stat().st_size != item["size"] or digest(temporary) != expected:
            raise ValueError("Download verification failed: " + target.name)
        temporary.replace(target)
    print("All five files verified.", flush=True)
