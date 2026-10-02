"""실제 사람 발화 녹음 → VAD threshold 비교 replay 용 16 kHz mono WAV + 정답 manifest.

입력 폴더(저장소 밖, 예: ~/medmap-data/stt_human/raw/)에 녹음 파일(m4a·webm·wav·mp3 등 PyAV 가 여는 형식)과
`manifest.json` 을 둔다. 형식:
  {"recordings": [{"id": "r01", "file": "r01.m4a",
                   "sentences": ["어제부터 배가 아팠어요.", "열이 삼십팔 도 오 부까지 올랐어요."],
                   "numbers": [{"sentence": 1, "accept": ["38.5", "38도5부", "삼십팔도오부"]}]}]}
  sentences = 녹음에서 실제로 읽은 문장(문장 끝 = 자연스럽게 쉰 곳). numbers.accept = 맞다고 볼 표기들(공백·문장부호 무시).
출력 폴더(기본 <입력>/../prepared/)에 <id>.wav(16 kHz mono s16le) + manifest.json(wav 절대경로·길이 추가).
오디오·전사문을 로그에 남기지 않는다(파일 id·길이·개수만 출력). 녹음 원본은 수정하지 않는다.

실행: ~/ai_env/bin/python scripts/stt_replay_prepare.py <입력 폴더> [--out <출력 폴더>]
"""
from __future__ import annotations

import argparse
import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from medmap.speech import SR, decode_audio  # noqa: E402


def validate(manifest: dict) -> list[dict]:
    recs = manifest.get("recordings")
    if not isinstance(recs, list) or not recs:
        raise ValueError("manifest.recordings 가 비어 있음")
    seen = set()
    for r in recs:
        if not isinstance(r.get("id"), str) or not r["id"] or r["id"] in seen:
            raise ValueError("id 누락·중복")
        seen.add(r["id"])
        if not isinstance(r.get("file"), str) or not isinstance(r.get("sentences"), list) or not r["sentences"]:
            raise ValueError(f"{r['id']}: file/sentences 필요")
        for n in r.get("numbers", []):
            if not (0 <= int(n["sentence"]) < len(r["sentences"])) or not n.get("accept"):
                raise ValueError(f"{r['id']}: numbers 항목 오류")
            if n.get("span") and n["span"] not in r["sentences"][int(n["sentence"])]:
                raise ValueError(f"{r['id']}: numbers.span 이 문장에 없음")
    return recs


def write_wav(path: Path, pcm: np.ndarray) -> None:
    data = (np.clip(pcm, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    tmp = path.with_suffix(".wav.tmp")
    with wave.open(str(tmp), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(data)
    tmp.replace(path)                                            # 임시 파일 → 검증 후 교체(쓰기 실패 시 기존 파일 보존)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out")
    args = ap.parse_args()
    src = Path(args.src).expanduser().resolve()
    out = Path(args.out).expanduser().resolve() if args.out else src.parent / "prepared"
    recs = validate(json.loads((src / "manifest.json").read_text(encoding="utf-8")))
    out.mkdir(parents=True, exist_ok=True)
    prepared = []
    for r in recs:
        path = src / r["file"]
        if not path.exists():                                    # 확장자가 다르면 같은 id 파일을 찾는다(r01.wav·r01.webm …)
            found = sorted(q for q in src.glob(f"{r['id']}.*") if q.suffix.lower() not in (".json", ".txt", ".tmp"))
            if len(found) != 1:
                raise FileNotFoundError(f"{r['id']}: 녹음 파일 없음 또는 여러 개({len(found)})")
            path = found[0]
        pcm, duration = decode_audio(path.read_bytes())
        wav = out / f"{r['id']}.wav"
        write_wav(wav, pcm)
        prepared.append({**r, "wav": str(wav), "duration_s": round(duration, 3)})
        print(f"{r['id']} duration_s={duration:.2f} sentences={len(r['sentences'])} numbers={len(r.get('numbers', []))}")
    (out / "manifest.json").write_text(json.dumps({"recordings": prepared}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"prepared={len(prepared)} out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
