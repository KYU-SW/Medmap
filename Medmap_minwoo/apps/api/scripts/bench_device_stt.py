"""Comparison test: Android's on-device speech recognizer (DeviceSttPlugin) on 16 kHz WAV files.

Each file is written into the recognizer at real speaking speed over USB, so the timings are what a patient
would see: when captions appear while speaking, and how long the final text takes after the last word.
"""

from argparse import ArgumentParser
import asyncio
import json
from pathlib import Path

import websockets

from scripts.bench_phone_stt import adb, pcm16_base64, PORT, connect_page


async def call(socket_url: str, method: str, options: dict) -> dict:
    expression = f"Capacitor.nativePromise('DeviceStt', '{method}', {json.dumps(options)}).then(JSON.stringify)"
    async with websockets.connect(socket_url, max_size=None) as socket:
        await socket.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                      "params": {"expression": expression, "awaitPromise": True, "returnByValue": True}}))
        while True:
            reply = json.loads(await socket.recv())
            if reply.get("id") == 1:
                result = reply["result"]
                if "exceptionDetails" in result:
                    raise RuntimeError(result["exceptionDetails"].get("exception", {}).get("description", result))
                return json.loads(result["result"]["value"])


LIVE_JS = """(async () => {
  const D = Capacitor.registerPlugin('DeviceStt');
  const bytes = Uint8Array.from(atob(%s), (c) => c.charCodeAt(0));
  const captions = [];
  const t0 = performance.now();
  const handle = await D.addListener('caption', (e) => captions.push([(performance.now() - t0) / 1000, e.text]));
  await D.start();
  for (let i = 0; i < bytes.length; i += 8192) {  // 4096 samples = 0.256 s, like the app's audio callback
    let s = ''; for (const b of bytes.subarray(i, i + 8192)) s += String.fromCharCode(b);
    D.push({ pcm16: btoa(s) });
    const due = t0 + ((i + 8192) / 32000) * 1000;
    await new Promise((r) => setTimeout(r, Math.max(0, due - performance.now())));
  }
  const stoppedAt = performance.now();
  const result = await D.stop();
  const stop_seconds = (performance.now() - stoppedAt) / 1000;
  handle.remove();
  return JSON.stringify({ captions, final: result.transcript, stop_seconds });
})()"""


async def live(socket_url: str, pcm16: str) -> dict:
    async with websockets.connect(socket_url, max_size=None) as socket:
        await socket.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
            "expression": LIVE_JS % json.dumps(pcm16), "awaitPromise": True, "returnByValue": True}}))
        while True:
            reply = json.loads(await socket.recv())
            if reply.get("id") == 1:
                result = reply["result"]
                if "exceptionDetails" in result:
                    raise RuntimeError(result["exceptionDetails"].get("exception", {}).get("description", result))
                return json.loads(result["result"]["value"])


def main() -> int:
    parser = ArgumentParser(description="안드로이드 기기 내 음성 인식을 녹음 파일로 실제 말 속도에 맞춰 시험합니다.")
    parser.add_argument("wavs", type=Path, nargs="*")
    parser.add_argument("--download", action="store_true", help="기기에 한국어 오프라인 모델 설치를 요청한다")
    parser.add_argument("--live", action="store_true",
                        help="앱과 같은 방식(start/push/stop, 0.256초 조각을 말 속도로)으로 시험한다")
    args = parser.parse_args()
    socket_url = connect_page()
    print("지원:", asyncio.run(call(socket_url, "support", {})))
    if args.download:
        asyncio.run(call(socket_url, "download", {}))
        print("한국어 모델 설치를 요청했습니다. 폰 화면을 확인해 주세요.")
    for wav in args.wavs:
        if args.live:
            r = asyncio.run(asyncio.wait_for(live(socket_url, pcm16_base64(wav)), 120))
            first = f"{r['captions'][0][0]:.1f}초" if r["captions"] else "없음"
            print(f"{wav.name}: 첫 자막 {first} | 자막 {len(r['captions'])}번 | 종료 후 확정 {r['stop_seconds']:.2f}초")
            print(f"  최종: {r['final']}")
            continue
        try:
            r = asyncio.run(asyncio.wait_for(call(socket_url, "recognize", {"pcm16": pcm16_base64(wav), "realtime": True}), 120))
        except Exception as error:  # report and continue with the next file
            print(f"{wav.name}: 실패 {error}")
            continue
        partials = r["partials"]
        first = f"{partials[0]['t']:.1f}초" if partials else "없음"
        print(f"{wav.name}: 녹음 {r['audio_seconds']:.1f}초 | 첫 자막 {first} | 자막 {len(partials)}번 | "
              f"마지막 말 뒤 최종까지 {r['final_after_end']:.1f}초\n  최종: {r['final']}")
        for p in partials[:: max(1, len(partials) // 4)]:
            print(f"    {p['t']:4.1f}초 자막: {p['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
