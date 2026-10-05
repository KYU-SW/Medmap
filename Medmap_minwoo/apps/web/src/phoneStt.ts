import { Capacitor, registerPlugin } from "@capacitor/core";

type WhisperPlugin = {
  transcribe(options: { pcm16: string; threads?: number }): Promise<{
    transcript: string;
    load_seconds: number;
    processing_seconds: number;
    audio_seconds: number;
  }>;
  status(): Promise<{ modelReady: boolean; modelPath: string }>;
};

// Inside the Android app speech is transcribed on the phone (WhisperPlugin.java).
export const usesPhoneStt = Capacitor.isNativePlatform();
export const Whisper = registerPlugin<WhisperPlugin>("Whisper");

// The app has no web server of its own; until the intake rules move to the phone, it reaches the
// PC API through `adb reverse tcp:8000 tcp:8000` (docs/ANDROID_APP.md).
export const API_BASE = usesPhoneStt ? "http://localhost:8000" : "";

// 16 kHz float samples → little-endian 16-bit PCM, base64 for the plugin bridge.
export function pcm16Base64(chunks: Float32Array[]): string {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const pcm = new DataView(new ArrayBuffer(length * 2));
  let offset = 0;
  for (const chunk of chunks) {
    for (const sample of chunk) {
      const clamped = Math.max(-1, Math.min(1, sample));
      pcm.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
      offset += 2;
    }
  }
  const bytes = new Uint8Array(pcm.buffer);
  let binary = "";
  for (let start = 0; start < bytes.length; start += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(start, start + 0x8000));
  }
  return btoa(binary);
}
