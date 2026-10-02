"""Transcribe one local audio file without starting the web API."""

from argparse import ArgumentParser
from pathlib import Path
import sys

from app.services.stt_service import FasterWhisperService, resolve_hotwords


def parse_args():
    parser = ArgumentParser(description="한국어 음성 파일을 글자로 변환합니다.")
    parser.add_argument("audio", type=Path, help="변환할 음성 파일")
    parser.add_argument("--model", default="turbo", help="Whisper 모델 이름")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--compute-type", default=None)
    parser.add_argument(
        "--hotwords",
        default=None,
        help='Whisper 힌트 단어. "medical"이면 의료 용어 목록을 쓴다. 같은 파일로 켜고 끈 결과를 비교한다.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.audio.is_file():
        print(f"음성 파일을 찾을 수 없습니다: {args.audio}", file=sys.stderr)
        return 2

    compute_type = args.compute_type or ("float16" if args.device == "cuda" else "int8")
    service = FasterWhisperService(
        model_name=args.model,
        device=args.device,
        compute_type=compute_type,
        hotwords=resolve_hotwords(args.hotwords),
    )
    result = service.transcribe(args.audio.read_bytes(), "application/octet-stream")
    print(result.text)
    print(
        f"language={result.language}, duration={result.duration_seconds}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
