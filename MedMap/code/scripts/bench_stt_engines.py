"""STT 엔진 비교 benchmark: A(HF transformers Whisper, 현 제품) vs B(faster-whisper/CTranslate2), 같은 모델·같은 샘플.

REALTIME_FIRST 판정용. 한 번에 한 엔진만(별도 프로세스·별도 venv) 실행한다. GPU 는 wait_for_resources --check OK 일 때만.
  A: ~/ai_env/bin/python scripts/bench_stt_engines.py --engine a --out logs/rt_b_bench_a.json
  B: ~/stt_ct2_env/bin/python scripts/bench_stt_engines.py --engine b --compute int8_float16 \
       --model-dir ~/models/faster-whisper-large-v3-turbo --out logs/rt_b_bench_b_int8.json

측정(숫자 + 합성 샘플의 전사문만. 합성 TTS 문장이라 개인정보 없음):
  cold      : 모델 로드 ms + 첫 decode ms
  partial   : 각 샘플의 0.5 s 간격 prefix decode ms (streaming 재디코드 비용) + 긴 발화(샘플 4개 이어붙임) prefix
  final     : 샘플 전체 decode ms (warm, 3회)
  T_partial : 단일 GPU 큐 가상 시계 재생 — 100 ms 패킷, tick = max(min_tick, 1.2×직전 decode), 오디오 시점 τ 가 처음 담긴
              partial 이 나오는 시각 − τ. decode 시간은 실제 호출 측정값. (브라우저 캡처·네트워크·렌더 제외)
  VRAM      : nvidia-smi 사용량(로드 전·후·decode 중 최대)
  accuracy  : 참조 문장 대비 CER(공백·문장부호 제거), 전사문
오프라인: A 는 HF 캐시에서, B 는 --model-dir 로컬 경로에서만 로드한다(HF_HUB_OFFLINE=1 권장 — OFFLINE_ON_PREM_FIRST).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(os.path.expanduser("~/stt_bench/ko_symptoms"))
SR = 16000


def vram_mib() -> int:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip().splitlines()
    return int(out[0]) if out else -1


class VramPeak:
    def __init__(self):
        self.peak = vram_mib()
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.is_set():
            self.peak = max(self.peak, vram_mib())
            time.sleep(0.05)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join()


def load_wav(path: Path) -> np.ndarray:
    import wave
    with wave.open(str(path)) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1 and w.getsampwidth() == 2, path
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0


def load_resampled(path: Path) -> np.ndarray:
    """16 kHz mono 가 아닌 WAV 도 같은 방식(PyAV)으로 16 kHz mono float32 로 — 두 venv 모두 av 가 있다."""
    import av
    with av.open(str(path)) as c:
        res = av.AudioResampler(format="flt", layout="mono", rate=SR)
        out = []
        for frame in c.decode(audio=0):
            for r in res.resample(frame):
                out.append(r.to_ndarray().reshape(-1))
        for r in res.resample(None):
            out.append(r.to_ndarray().reshape(-1))
    x = np.concatenate(out).astype(np.float32)
    assert np.abs(x).max() <= 1.5, "PyAV scale guard"
    return x


def norm(text: str) -> str:
    return re.sub(r"[\s\.,!?·~\-\"'“”‘’]", "", text)


def cer(ref: str, hyp: str) -> float:
    r, h = norm(ref), norm(hyp)
    d = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, hc in enumerate(h, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (rc != hc))
    return d[len(h)] / max(1, len(r))


def pct(xs, q):
    return round(float(np.percentile(xs, q)), 1) if len(xs) else None


def make_engine(args):
    started = time.perf_counter()
    if args.engine == "a":
        sys.path.insert(0, str(ROOT))
        from medmap import speech
        t = speech.WhisperTranscriber()
        t._ensure_loaded()
        load_ms = (time.perf_counter() - started) * 1000
        return (lambda x: t.transcribe(x)), load_ms, {"impl": "hf-transformers pipeline fp16", "model": "openai/whisper-large-v3-turbo"}
    from faster_whisper import WhisperModel
    model = WhisperModel(os.path.expanduser(args.model_dir), device="cuda", compute_type=args.compute, local_files_only=True)
    load_ms = (time.perf_counter() - started) * 1000

    def run(x):
        segments, _ = model.transcribe(x, language="ko", task="transcribe", beam_size=1, best_of=1, temperature=0.0,
                                       condition_on_previous_text=False, vad_filter=False, without_timestamps=True)
        return "".join(s.text for s in segments).strip()
    return run, load_ms, {"impl": f"faster-whisper {__import__('faster_whisper').__version__} ctranslate2 "
                                  f"{__import__('ctranslate2').__version__} {args.compute} greedy",
                          "model": os.path.expanduser(args.model_dir)}


def timed(fn, x):
    t = time.perf_counter()
    text = fn(x)
    return text, (time.perf_counter() - t) * 1000


def simulate_t_partial(fn, audio: np.ndarray, min_tick_ms: float, packet_ms: int = 100):
    """가상 시계: 패킷 k 는 시각 (k+1)·100 ms 에 도착. GPU 는 한 번에 하나. tick 이 되면 그때까지 도착한 오디오 전체를 decode."""
    n_packets = int(np.ceil(len(audio) / (SR * packet_ms / 1000)))
    end_ms = n_packets * packet_ms
    t = 0.0
    last_start = -1e9
    tick = min_tick_ms
    emits = []                                        # (emit_time_ms, audio_ms_covered)
    while t < end_ms:
        arrived = min(end_ms, int(t // packet_ms) * packet_ms)
        if arrived >= 300 and t - last_start >= tick:
            _, d = timed(fn, audio[: int(arrived * SR / 1000)])
            last_start = t
            t += d
            emits.append((t, arrived))
            tick = max(min_tick_ms, 1.2 * d)
        else:
            t = max(t + 1, min(last_start + tick, (int(t // packet_ms) + 1) * packet_ms))
    lat = []
    for tau in range(300, end_ms + 1, packet_ms):
        shown = [e for e, a in emits if a >= tau]
        if shown:
            lat.append(shown[0] - tau)
    return lat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["a", "b"], required=True)
    ap.add_argument("--compute", default="int8_float16")
    ap.add_argument("--model-dir", default="~/models/faster-whisper-large-v3-turbo")
    ap.add_argument("--ticks", default="150,200,250,300,400")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    refs = json.loads((SAMPLES / "sentences.json").read_text(encoding="utf-8"))
    audios = [load_wav(SAMPLES / f"s{i + 1:02d}.wav") for i in range(len(refs))]
    long_audio = np.concatenate(audios[:4])
    tts = ROOT / "stt" / "samples" / "medmap_tts_test.wav"

    vram_before = vram_mib()
    with VramPeak() as vp:
        fn, load_ms, meta = make_engine(args)
        vram_loaded = vram_mib()
        _, first_ms = timed(fn, audios[0])
        # partial prefix decode
        partial_ms, long_partial_ms = [], []
        for a in audios:
            for cut in np.arange(0.5, len(a) / SR, 0.5):
                partial_ms.append(timed(fn, a[: int(cut * SR)])[1])
        for cut in np.arange(1.0, len(long_audio) / SR, 1.0):
            long_partial_ms.append((round(float(cut), 1), round(timed(fn, long_audio[: int(cut * SR)])[1], 1)))
        # final decode + accuracy
        final_ms, rows = [], []
        for ref, a in zip(refs, audios):
            texts = []
            for _ in range(3):
                text, ms = timed(fn, a)
                final_ms.append(ms)
                texts.append(text)
            rows.append({"ref": ref, "hyp": texts[-1], "cer": round(cer(ref, texts[-1]), 4),
                         "stable_across_runs": len(set(texts)) == 1, "duration_s": round(len(a) / SR, 2)})
        # simulated T_partial (7.7 s TTS sample + long utterance)
        sim = {}
        tts_audio = load_resampled(tts) if tts.exists() else None
        for tick in [float(x) for x in args.ticks.split(",")]:
            lat = []
            for a in [x for x in (tts_audio, long_audio) if x is not None]:
                lat += simulate_t_partial(fn, a, tick)
            sim[str(int(tick))] = {"p50": pct(lat, 50), "p95": pct(lat, 95), "n": len(lat)}
    result = {
        "engine": args.engine, **meta, "when": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cold": {"load_ms": round(load_ms, 1), "first_decode_ms": round(first_ms, 1)},
        "vram_mib": {"before": vram_before, "after_load": vram_loaded, "peak": vp.peak, "delta_peak": vp.peak - vram_before},
        "partial_decode_ms": {"p50": pct(partial_ms, 50), "p95": pct(partial_ms, 95), "n": len(partial_ms)},
        "long_utterance_partial_decode_ms": long_partial_ms,
        "final_decode_ms": {"p50": pct(final_ms, 50), "p95": pct(final_ms, 95), "n": len(final_ms)},
        "simulated_T_partial_ms_by_min_tick": sim,
        "accuracy": {"mean_cer": round(float(np.mean([r["cer"] for r in rows])), 4), "rows": rows},
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("engine", "cold", "vram_mib", "partial_decode_ms", "final_decode_ms",
                                              "simulated_T_partial_ms_by_min_tick")}, ensure_ascii=False))
    print("mean_cer", result["accuracy"]["mean_cer"])


if __name__ == "__main__":
    main()
