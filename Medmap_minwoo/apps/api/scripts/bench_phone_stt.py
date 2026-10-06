"""Time on-phone transcription in the real Android app without tapping the screen.

The debug app allows WebView remote debugging, so over USB this script calls the same
`Whisper.transcribe` the record screen uses, with 16 kHz mono WAV files from the PC, and prints
the transcript and timings. The phone must be connected with USB debugging (docs/ANDROID_APP.md).
"""

from argparse import ArgumentParser
import asyncio
import base64
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import wave

import websockets

ADB = Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
PORT = 9222


def adb(*args: str) -> str:
    return subprocess.run([str(ADB), *args], capture_output=True, check=True, text=True).stdout.strip()


def pcm16_base64(path: Path) -> str:
    with wave.open(str(path)) as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (16000, 1, 2):
            raise SystemExit(f"16 kHz mono 16-bit WAV only: {path}")
        return base64.b64encode(audio.readframes(audio.getnframes())).decode()


async def transcribe(socket_url: str, pcm16: str, method: str = "transcribe") -> dict:
    expression = (
        f"Capacitor.nativePromise('Whisper', '{method}', "
        f"{{pcm16: {json.dumps(pcm16)}}}).then(JSON.stringify)"
    )
    async with websockets.connect(socket_url, max_size=None) as socket:
        await socket.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": expression, "awaitPromise": True, "returnByValue": True},
        }))
        while True:
            reply = json.loads(await socket.recv())
            if reply.get("id") == 1:
                result = reply["result"]
                if "exceptionDetails" in result:
                    raise RuntimeError(result["exceptionDetails"].get("text", result))
                return json.loads(result["result"]["value"])


def connect_page() -> str:
    """Brings the app to the front and returns the debugging socket of its web view."""
    # The app must be in front: in the background Android moves it to the slow cores.
    adb("shell", "am", "start", "-W", "-n", "kr.medmap.app/.MainActivity")
    pid = adb("shell", "pidof", "kr.medmap.app")
    adb("forward", f"tcp:{PORT}", f"localabstract:webview_devtools_remote_{pid}")
    for _ in range(20):  # the web view opens its debugging socket a moment after the activity starts
        try:
            pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
            break
        except OSError:
            time.sleep(0.5)
    else:
        raise SystemExit("앱 화면에 연결하지 못했습니다. 디버그 빌드인지 확인해 주세요.")
    return next(page["webSocketDebuggerUrl"] for page in pages if page.get("type") == "page")


def main() -> int:
    parser = ArgumentParser(description="실제 안드로이드 앱에서 폰 안 음성 변환 시간을 잽니다.")
    parser.add_argument("wavs", type=Path, nargs="+", help="16kHz 모노 WAV 파일")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument(
        "--caption", action="store_true",
        help="말하는 중 자막을 흉내 낸다: 녹음을 1.5초씩 늘려 가며 작은 모델(preview)로 변환한다",
    )
    args = parser.parse_args()

    socket_url = connect_page()

    for _ in range(args.repeat):
        for wav in args.wavs:
            if args.caption:
                pcm = base64.b64decode(pcm16_base64(wav))
                step = 16000 * 2 * 3 // 2  # 1.5 s of 16-bit samples
                for end in range(step, len(pcm) + step, step):
                    part = base64.b64encode(pcm[:end]).decode()
                    caption = asyncio.run(asyncio.wait_for(transcribe(socket_url, part, "preview"), timeout=60))
                    print(f"  자막 {min(end, len(pcm)) / 32000:4.1f}초까지 → {caption['processing_seconds']:.1f}초 | {caption['transcript']}")
            result = asyncio.run(asyncio.wait_for(transcribe(socket_url, pcm16_base64(wav)), timeout=180))
            print(
                f"{wav.name}: 녹음 {result['audio_seconds']:.1f}초 → 변환 {result['processing_seconds']:.1f}초 "
                f"(불러오기 {result['load_seconds']:.1f}초, {result.get('model', '')}) | {result['transcript']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
