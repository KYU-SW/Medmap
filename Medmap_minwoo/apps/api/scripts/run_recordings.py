"""Run recorded audio (m4a, wav, ...) through the phone app's on-device recognizer and turbo, as the record screen does.

The phone must be connected with USB debugging and its screen on (docs/ANDROID_APP.md). Each recording is converted to
16 kHz mono WAV next to the output file, streamed live to the on-device recognizer, then transcribed by turbo.

    cd apps/api
    .venv\\Scripts\\python.exe -m scripts.run_recordings results.jsonl "..\\..\\local-cache\\stt-samples\\녹음 1.m4a" ...
"""

from argparse import ArgumentParser
import asyncio
import json
from pathlib import Path
import sys
import wave

import av
import numpy as np

from scripts.bench_device_stt import live
from scripts.bench_phone_stt import connect_page, pcm16_base64, transcribe


def to_wav(source: Path, target: Path) -> None:
    container = av.open(str(source))
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    chunks = [out.to_ndarray().reshape(-1) for frame in container.decode(audio=0) for out in resampler.resample(frame)]
    chunks += [out.to_ndarray().reshape(-1) for out in resampler.resample(None)]
    with wave.open(str(target), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(np.concatenate(chunks).astype("<i2").tobytes())


def main() -> int:
    parser = ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path, help="JSON lines file to write, one row per recording")
    parser.add_argument("recordings", type=Path, nargs="+")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    wav_dir = args.output.parent / "wav"
    wav_dir.mkdir(exist_ok=True)
    socket_url = connect_page()
    rows = []
    for recording in args.recordings:
        wav = wav_dir / f"{recording.stem}.wav"
        to_wav(recording, wav)
        pcm = pcm16_base64(wav)
        device = asyncio.run(asyncio.wait_for(live(socket_url, pcm), 300))
        turbo = asyncio.run(asyncio.wait_for(transcribe(socket_url, pcm), 300))
        rows.append({
            "recording": recording.name, "audio_seconds": turbo["audio_seconds"],
            "device": device["final"], "device_stop_seconds": device["stop_seconds"],
            "turbo": turbo["transcript"], "turbo_seconds": turbo["processing_seconds"],
        })
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    args.output.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
