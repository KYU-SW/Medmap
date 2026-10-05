"""Compare the server STT (faster-whisper) with whisper.cpp, the engine planned for the phone.

For each audio file it prints both transcripts, their processing times and the symptoms the
intake rules find in each, so we can see whether the phone model changes what gets recorded.
Recordings stay in local-cache/ (outside Git); nothing is saved.
"""

from argparse import ArgumentParser
from pathlib import Path
import subprocess
import sys
import tempfile
from time import perf_counter

import av

from app.services.intake_extractor import extract_intake
from app.services.stt_service import FasterWhisperService

ROOT = Path(__file__).resolve().parents[3]
WHISPER_CPP = ROOT / "local-cache" / "whisper-cpp"
AUDIO_SUFFIXES = {".m4a", ".mp3", ".wav", ".webm", ".ogg", ".aac", ".flac", ".mp4"}


def parse_args():
    parser = ArgumentParser(description="faster-whisper와 whisper.cpp의 한국어 변환 결과를 비교합니다.")
    parser.add_argument("samples", type=Path, nargs="?", default=ROOT / "local-cache" / "stt-samples")
    parser.add_argument("--cli", type=Path, default=WHISPER_CPP / "bin" / "Release" / "whisper-cli.exe")
    parser.add_argument("--model", type=Path, default=WHISPER_CPP / "models" / "ggml-large-v3-turbo-q5_0.bin")
    parser.add_argument("--threads", type=int, default=4, help="휴대폰과 비슷하게 맞추려면 4 정도로 둔다")
    parser.add_argument("--prompt", default=None, help="whisper.cpp에 줄 예시 문장(숫자·약 이름 표기 유도). 켜고 끈 결과를 비교한다")
    return parser.parse_args()


def to_wav16k(source: Path, target: Path) -> float:
    """whisper.cpp reads 16 kHz mono WAV only. Returns the audio length in seconds."""
    samples = 0
    with av.open(str(source)) as reader, av.open(str(target), "w", format="wav") as writer:
        stream = writer.add_stream("pcm_s16le", rate=16000, layout="mono")
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in reader.decode(audio=0):
            for out in resampler.resample(frame):
                samples += out.samples
                writer.mux(stream.encode(out))
        for out in resampler.resample(None):
            samples += out.samples
            writer.mux(stream.encode(out))
        writer.mux(stream.encode(None))
    return samples / 16000


def whisper_cpp(cli: Path, model: Path, wav: Path, threads: int, prompt: str | None) -> str:
    command = [str(cli), "-m", str(model), "-f", str(wav), "-l", "ko", "-bs", "5", "-t", str(threads), "-nt", "-np"]
    if prompt:
        command += ["--prompt", prompt]
    result = subprocess.run(
        command,
        capture_output=True, check=True, encoding="utf-8", errors="replace",
    )
    return " ".join(line.strip() for line in result.stdout.splitlines() if line.strip())


def symptom_names(text: str) -> list[str]:
    return [f"{item.name}({item.status})" for item in extract_intake(text).symptoms]


def main() -> int:
    args = parse_args()
    for path in (args.cli, args.model):
        if not path.is_file():
            print(f"파일을 찾을 수 없습니다: {path}", file=sys.stderr)
            return 2
    files = sorted(p for p in args.samples.iterdir() if p.suffix.lower() in AUDIO_SUFFIXES) if args.samples.is_dir() else []
    if not files:
        print(f"비교할 음성 파일이 없습니다: {args.samples}", file=sys.stderr)
        return 2

    server = FasterWhisperService(model_name="turbo", device="cpu", compute_type="int8")
    same = 0
    with tempfile.TemporaryDirectory() as work:
        for audio in files:
            wav = Path(work) / f"{audio.stem}.wav"
            seconds = to_wav16k(audio, wav)

            started = perf_counter()
            server_text = server.transcribe(audio.read_bytes(), "application/octet-stream").text
            server_time = perf_counter() - started
            started = perf_counter()
            phone_text = whisper_cpp(args.cli, args.model, wav, args.threads, args.prompt)
            phone_time = perf_counter() - started

            server_symptoms, phone_symptoms = symptom_names(server_text), symptom_names(phone_text)
            same += server_symptoms == phone_symptoms
            print(f"=== {audio.name} ({seconds:.1f}초)")
            print(f"  서버  {server_time:5.1f}초 | {server_text}")
            print(f"  폰용  {phone_time:5.1f}초 | {phone_text}")
            print(f"  증상  서버 {server_symptoms}")
            print(f"        폰용 {phone_symptoms}  {'같음' if server_symptoms == phone_symptoms else '다름'}")
    print(f"\n증상 정리 결과가 같은 파일: {same}/{len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
