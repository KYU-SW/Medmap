"""Write every sentence the intake tests and recordings feed the rules, with the Python result, as the answer file
the TypeScript port must match exactly (apps/web/src/intake/golden.json).

Sentences come from: every extract_intake call the API tests make, both transcripts of each scored recording
(local-cache/stt-samples/results_*.jsonl, when present) and the recording scripts.

    cd apps/api
    .venv\\Scripts\\python.exe -m scripts.export_intake_golden
"""

from datetime import date
import json
from pathlib import Path
import re
import sys

import pytest

from app.services import intake_extractor

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "apps" / "web" / "src" / "intake" / "golden.json"
SAMPLES = ROOT / "local-cache" / "stt-samples"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    seen: dict[tuple[str, str | None], None] = {}
    original = intake_extractor.extract_intake

    def recording(text: str, reference_date: date | None = None):
        seen[(text, reference_date.isoformat() if reference_date else None)] = None
        return original(text, reference_date)

    # Patched before pytest imports the tests, so their "from ... import extract_intake" gets the recorder.
    intake_extractor.extract_intake = recording
    code = pytest.main(["-q", "-p", "no:cacheprovider", str(ROOT / "apps" / "api" / "tests")])
    intake_extractor.extract_intake = original
    if code != 0:
        print("tests failed; answer file not written")
        return 1

    for results in sorted(SAMPLES.glob("results_*.jsonl")):
        for line in results.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            for key in ("device", "turbo"):
                if row.get(key):
                    seen[(row[key], "2026-10-09")] = None
    for scripts in sorted(SAMPLES.glob("scripts_*.txt")):
        for body in re.findall(r"^\d+ \(.*?\)\n(.+)", scripts.read_text(encoding="utf-8"), re.M):
            seen[(body, "2026-10-09")] = None

    cases = [
        {
            "text": text,
            "reference_date": reference,
            "result": original(text, date.fromisoformat(reference) if reference else None).model_dump(mode="json"),
        }
        for text, reference in seen
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(cases)} cases -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
