"""Score run_recordings results against the scripts that were read aloud.

The scripts file holds one script per block: a line starting with its number, then the text on the next line.
Each recording is matched to the most similar script. The script's facts (symptoms with presence, onset, severity,
count and trend; medicines; allergies; history) are the answer; on-device and turbo facts are compared with them.
turbo's spelled-out numbers are turned into digits with the app's own function (apps/web/src/transcriptCheck.ts).

    cd apps/api
    .venv\\Scripts\\python.exe -m scripts.eval_recordings results.jsonl scripts.txt
"""

from argparse import ArgumentParser
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import subprocess
import sys

from app.services.intake_extractor import extract_intake

TRANSCRIPT_CHECK = Path(__file__).resolve().parents[2] / "web" / "src" / "transcriptCheck.ts"


def digits(texts: list[str]) -> list[str]:
    """The app shows turbo's text through spokenNumbersToDigits; Node runs the TypeScript as is."""
    program = (
        f"import {{ spokenNumbersToDigits }} from {json.dumps(TRANSCRIPT_CHECK.as_uri())};"
        "let input = ''; process.stdin.on('data', (chunk) => input += chunk);"
        "process.stdin.on('end', () => console.log(JSON.stringify(JSON.parse(input).map(spokenNumbersToDigits))));"
    )
    result = subprocess.run(["node", "--input-type=module", "-e", program], input=json.dumps(texts),
                            capture_output=True, check=True, text=True, encoding="utf-8")
    return json.loads(result.stdout)


def facts(text: str) -> dict[str, set]:
    result = extract_intake(text)
    return {
        "symptoms": {(s.name, s.status, s.onset, s.severity, s.frequency, s.trend) for s in result.symptoms},
        "medications": set(result.medications),
        "allergies": set(result.allergies),
        "history": set(result.medical_history),
    }


def merged(device: str, turbo: str) -> dict[str, set]:
    """What the review screen holds after "모두 반영": the on-device facts with what turbo heard differently.

    Mirrors factChanges and resolveVerification (apps/web): symptoms turbo heard are added or take turbo's
    presence, onset and any severity, count or trend turbo heard; nothing only the on-device text heard is
    dropped; a medicine, allergy or past condition is removed only when turbo heard another name in its place.
    """
    quick, careful = extract_intake(device), extract_intake(turbo)
    symptoms = {s.name: s for s in quick.symptoms}
    for after in careful.symptoms:
        before = symptoms.get(after.name)
        if before is None:
            symptoms[after.name] = after
        else:
            details = {key: getattr(after, key) for key in ("severity", "frequency", "trend") if getattr(after, key)}
            symptoms[after.name] = before.model_copy(update={"status": after.status, "onset": after.onset, **details})
    lists = {}
    for key, field in (("medications", "medications"), ("allergies", "allergies"), ("history", "medical_history")):
        mine, theirs = getattr(quick, field), getattr(careful, field)
        added = [item for item in theirs if item not in mine]
        lists[key] = set(added + ([item for item in mine if item in theirs] if added else mine))
    return {
        "symptoms": {(s.name, s.status, s.onset, s.severity, s.frequency, s.trend) for s in symptoms.values()},
        **lists,
    }


def differences(answer: dict[str, set], got: dict[str, set]) -> list[str]:
    lines = []
    for key in answer:
        missing, extra = sorted(answer[key] - got[key]), sorted(got[key] - answer[key])
        if missing or extra:
            lines.append(f"{key}: 빠짐 {missing} / 다름 {extra}")
    return lines


def main() -> int:
    parser = ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("results", type=Path)
    parser.add_argument("scripts", type=Path)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    scripts = dict(re.findall(r"^(\d+)\b.*\n(.+)$", args.scripts.read_text(encoding="utf-8"), re.M))
    rows = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row, turbo in zip(rows, digits([row["turbo"] for row in rows])):
        row["turbo"] = turbo
    counts = {"device": 0, "turbo": 0, "merged": 0}
    for row in rows:
        number, script = max(scripts.items(), key=lambda item: SequenceMatcher(None, item[1], row["turbo"]).ratio())
        answer = facts(script)
        print(f"### {row['recording']} = 문구 {number} ({row['audio_seconds']:.0f}s, turbo {row['turbo_seconds']:.1f}s)")
        for engine in counts:
            got = merged(row["device"], row["turbo"]) if engine == "merged" else facts(row[engine])
            problems = differences(answer, got)
            counts[engine] += len(problems)
            print(f"  {engine}: {'OK' if not problems else ' | '.join(problems)}")
    print("틀린 항목 수:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
