# Realtime streaming STT — execution ledger

## Task 7 test contract (확정: 2026-09-30, 구현 전)

`useStreamingStt({ onFinal, capture, connect, transcribeLegacy, raf, now })` → `{ state, partial: {stable, unstable}, transport, sttState, error, start(), stop() }`

| # | 계약 | 테스트 |
|---|---|---|
| C1 | **PARTIAL/FINAL 분리**: partial 은 `partial` 상태에만 들어가고 `onFinal` 을 절대 부르지 않는다. `onFinal` 은 final 메시지로만 호출된다. 이 hook 은 STT 경로 외 API(세션·매퍼)를 호출하지 않는다 | `partial is UI-only…` |
| C2 | **stale partial 방지**: (a) 이미 final 이 전달된 utt 의 partial 은 무시 (b) 같은 utt 에서 audio_ms 가 이전보다 작은(늦게 도착한) partial 은 무시 (c) rAF 로 병합해 프레임당 한 번만 반영 | `stale partials are dropped…`, `partials are merged per animation frame` |
| C3 | **utterance 간 상태 격리**: final 이 오면 partial 을 비우고 다음 utt 로 넘어간다. 같은 utt 의 final 중복은 한 번만 전달. legacy 강등 시에는 **마지막으로 전달된 final 이후 오디오만** 보낸다(중복 텍스트 없음) | `final is delivered once per utterance and resets partial`, `mid-stream failure sends only audio after the last delivered final` |
| C4 | **WS→HTTP→legacy**: connect(WS→HTTP 는 transport 모듈 책임) 가 reject 하면 transport='legacy' 로 계속 녹음하고, stop 시 WAV 를 `transcribeLegacy` 로 1회 보내 `onFinal`. 스트림 중 error 메시지·연결 끊김·stop 후 final 미도착(타임아웃)도 legacy 로 강등 | `connect failure → legacy…`, `mid-stream failure…`, `stop timeout → legacy` |
| C5 | **feature flag OFF 시 기존 동작 보존**: `FreeTextInput` 은 `/v1/stt/status` 가 streaming:false 이거나 실패하거나 AudioWorklet 이 없으면 기존 `VoiceInput` 을 그대로 렌더(기존 테스트 전부 통과) | `FreeTextInput.test.jsx` 추가 케이스 3개 |
| C6 | textarea 에는 FINAL 만(기존 `joinTranscript`), partial 은 별도 줄 | `StreamingVoiceInput`/`FreeTextInput` 케이스 |
| C7 | 캡처 실패(unsupported/permission) 는 `error` 로 노출(부모가 기존 문구) | `capture failure surfaces error` |

## M1 measurement (2026-09-30 19:11–19:13, GPU uncontended: before 0 % / 635 MiB, after 21 % / 2780 MiB)
Conditions: headless Chromium 1246 + fake mic (TTS 7.72 s), server on same PC (8010, dist), engine A (HF whisper-large-v3-turbo fp16, tick ≥400 ms), warm (first WS run excluded). Raw: `logs/rt_m1_e2e_perf.json` (numbers only).

| metric | p50 | p95 | target | verdict |
|---|---|---|---|---|
| T_partial WS (5 runs, 383 audio points) | 474.8 | 751.1 | 300–600 | p50 OK, **p95 +151 ms** |
| T_final WS (stop click → FINAL render) | 470.3 | 495.8 | ≤500 | OK (margin 4 ms) |
| T_partial HTTP (1 run) | 699.3 | – | 300–600 | miss |
| T_final HTTP | 494.9 | – | ≤500 | OK |
| T_final legacy | 837.8 | – | fallback | ref |

Earlier server-only runs: run A (uncontended, old per-partial metric) partial decode p50 277 / p95 417; run B **INVALID** (launched during WAIT).
Analysis: T_partial ≈ U(0, tick) + queue + decode + render; decode ≈ 270–400 ms per tick (HF Whisper encodes a padded 30 s window regardless of audio length — 추정, to verify in B benchmark), tick cannot be < decode (single GPU queue) → worst ≈ 2×decode ≈ 600–800 ms = observed p95. A-only tuning can shave tens of ms, not the ~2× needed → **M1 = 부분 통과; B (faster-whisper/CT2) benchmark required before M2** (target not lowered).

## B benchmark (2026-09-30 19:40–19:47, GPU uncontended, sequential A → B int8_float16 → B float16, HF_HUB_OFFLINE=1)
Env: A = ~/ai_env (HF transformers fp16), B = ~/stt_ct2_env (faster-whisper 1.2.1, ctranslate2 4.8.2, cuBLAS 12.9, cuDNN 9.27; model ~/models/faster-whisper-large-v3-turbo 1.6 GB, loaded local_files_only). ~/ai_env unchanged.
Samples: 12 synthetic Korean symptom sentences (Windows SAPI Heami, 16 kHz, ~/stt_bench/ko_symptoms) + medmap_tts_test (7.7 s) + 15 s concat. Raw: logs/rt_b_bench_{a,b_int8,b_fp16}.json.

| | A (HF fp16) | B int8_float16 | B float16 |
|---|---|---|---|
| cold load / first decode ms | 8419 / 1439 | 2827 / 456 | 1767 / 456 |
| VRAM Δpeak MiB | 2208 | **1163** | 1959 |
| partial decode p50/p95 ms (prefixes ≤6 s) | 239 / 383 | **191 / 230** | 209 / 251 |
| prefix decode at 5 / 10 / 15 s | 288 / 446 / 771 | 205 / 248 / 352 | 253 / 265 / 368 |
| final decode p50/p95 ms | 257 / 313 | **203 / 239** | 215 / 244 |
| simulated server T_partial p50/p95 (min tick 150–400) | 525–593 / 1025–1378 | **346–388 / 560–582** | 376–404 / 582–612 |
| mean CER (12 sentences) | 0.029 | 0.029 | 0.029 |

- Correction: earlier guess "A decode ≈ fixed cost (30 s window)" is **wrong** — A decode grows with length (181 ms @1 s → 771 ms @15 s); B grows much less (162 → 352 ms).
- Accuracy: identical CER; A≠B on 2/12 ("삐"→ A "비" / B-int8 "귀", both wrong; spacing only). **Both engines drop "오 분" in "삼십팔 도 오 분"(38.5 °C → "38도")** — clinically relevant number loss, engine-independent (TTS phrasing; 확인 필요 with real speech).
- Simulated T_partial excludes browser capture/network/render → end-to-end B not yet measured.

## M1 re-measure — B-int8 **integrated end-to-end** (2026-09-30 20:05–20:11, GPU uncontended before start: 1 % / 637 MiB)
Actual path: headless Chromium 1246 fake mic → AudioWorklet → WS/HTTP → MedMap API (~/ai_env, `MEDMAP_STT_ENGINE=ct2`) → Unix socket (0600) → local STT worker (~/stt_ct2_env, faster-whisper int8_float16, persistent, prewarmed) → back → render. Same sample/conditions as the A baseline (TTS 7.72 s). Raw: `logs/rt_m1b_20260930_2005/` (numbers only).
**This is an end-to-end measurement — not the standalone simulation above.**

| metric (warm) | A e2e (baseline) | **B e2e** | target |
|---|---|---|---|
| T_partial WS p50 / p95 (A 5 runs n=383; B 12 runs n=944) | 475 / 751 | **399 / 631** | p95 ≤ 600 → **miss by 31 ms** |
| T_final WS p50 / p95 | 470 / 496 | **259 / 304** | ≤ 500 ✓ |
| T_partial HTTP p50 / p95 (B 4 runs n=316) | 699 (1 run) | 514 / 815 | miss |
| T_final HTTP p50 / p95 | 495 | 226 / 245 | ✓ |
| T_final legacy (HF /transcribe) | 838 | 1262 / 1824 (2 runs, HF shares GPU with worker) | fallback |
| T_final worker-down → legacy (1 run) | – | 612, FINAL once (no duplicate) | fallback |
| cold (first WS run) T_partial p50/p95 · T_final | – | 406 / 621 · 305 (worker prewarmed at start) | |

T_partial breakdown (B WS warm, per audio point, p50 / p95; tail mean at ≥p90):
tick_wait 209 / 418 (tail 408) · server 206 / 244 (tail 223) = held 0.2 + queue 0 + decode 206/244 (worker 205/243 + IPC 0.4/0.5) · network 0.8 / 0.9 · render 0.4 / 0.5.
→ **Bottleneck = server partial tick floor `PARTIAL_TICK_MS = 400`** (chosen for engine A). CT2 decode ~205 ms, IPC/network/render < 2 ms. HTTP adds 300 ms batching (network p50 102 / p95 145) + tick.
Resources: worker cold load 2485 ms + prewarm 420 ms; VRAM idle 637 → +worker 1667 (+1030 MiB) → +HF legacy fallback prewarmed 3458 (+1791) → peak 3802 MiB; GPU util median 19 % / max 100 %; worker RSS ≤ 1451 MiB, CPU median 79 % of one core; server RSS ≤ 1594 MiB, CPU 3.9 %.
Offline/local: worker and server had **0** non-loopback TCP connections (ss sampled every 5 s); worker IPC = 1 persistent Unix-socket connection; models loaded with HF_HUB_OFFLINE=1 / local_files_only.
Correctness: 19/19 runs REALTIME_STT_E2E_OK — expected phrase present exactly once (no FINAL duplication), no /v1/session or /v1/intake calls during speech, 390/1280 no overflow; worker kill → error → legacy FINAL once.
**Verdict M1: PARTIAL PASS** — every functional/privacy/fallback item passes and T_final passes with margin; T_partial p95 631 ms > 600 ms. Target not lowered. Proposed next optimization (not applied): tick floor 400 → ~200 ms (dynamic `max(floor, 1.2×decode)` ≈ 245 ms with B) — expected tick_wait p95 ≈ 250 → T_partial p95 ≈ 500 ms (estimate; costs higher GPU duty while speaking); HTTP batch 300 → 100 ms.

## Clinical Numeric Information Safety (recorded 2026-09-30, no new algorithm in M1)
- Finding: A and B both transcribed synthetic "체온은 삼십팔 도 오 분" as "38도 분" — 38.5 °C lost ".5". TTS phrasing may be the cause (확인 필요); not an STT fail verdict on its own.
- Real human microphone test plan (M3, before any clinical claim): 체온 37.5/38.5/39.2도 in "삼십팔 점 오 도", "삼십팔 도 오 부", "38.5도", "38도 반 정도"; 횟수 한/두/세/열 번 ("오늘 구토를 두 번 했어요"); 기간 이틀/3일/일주일/2주; 시간 30분/한 시간 반/2시간; 용량 한 알/두 알/하루 세 번/500mg/5mL; 활력징후 "혈압 120에 80", "맥박 110", "산소포화도 94%". Record per phrase: exact transcript (A and B), numeric value preserved yes/no.
- Future safety layer candidates (not now): numeric entity detection, STT confidence, raw-vs-structured cross-check, emphasized confirmation for sentences with numbers.

## M1 optimization re-measure — tick floor 200 ms + HTTP batch 100 ms, HF fallback on-demand (2026-09-30 20:34–20:38)
Change (commit `14b9ac5`): `PARTIAL_TICK_MS` 400 → 200 (dynamic `max(floor, 1.2×decode)` kept) · HTTP chunk `batchMs` 300 → 100 · HF legacy fallback **not prewarmed** (no `MEDMAP_STT_PREWARM`; loaded on first `/v1/stt/transcribe`). Same path, sample (TTS 7.72 s), run plan (WS 13 incl. 1 warm-up · HTTP 4 · legacy 2 · worker-down 1), browser, runner as the 20:05 run. GPU at start: gpu_apps 0, util 21 %→3 %, 615 MiB (wait_for_resources OK 2/2). Raw: `logs/rt_m1c_20260930_2034/` (numbers only).

| metric | before (20:05, tick 400 · batch 300 · HF prewarmed) | **after** | target |
|---|---|---|---|
| T_partial WS warm p50 / p95 (12 runs) | 399 / 631 (n=944) | **316 / 465** (n=960) | p95 ≤ 600 ✓ |
| T_final WS warm p50 / p95 | 259 / 304 | **308 / 432** | ≤ 500 ✓ (**regression +128 ms p95**, see below) |
| T_partial HTTP p50 / p95 (4 runs) | 514 / 815 | **398 / 515** (n=321) | ✓ |
| T_final HTTP p50 / p95 | 226 / 245 | 317 / 400 | ✓ |
| cold first WS run T_partial p50/p95 · T_final | 406 / 621 · 305 | 316 / 477 · 463 | |
| T_final legacy (HF /transcribe) run 1 / run 2 | 1262 / 1824 (prewarmed) | **8782 (HF cold load)** / 548 | fallback |
| T_final worker-down → legacy (1 run, HF already loaded by legacy runs) | 612 | 645 | fallback |
| transcript quality: CER vs sample text (space/punct removed), all 19+1 runs | not measured (phrase check only) | **0.000** (mean = max = 0) | |

T_partial breakdown (WS warm, p50 / p95): tick_wait 93 / 209 (was 209 / 418) · server 216 / 261 = decode 216 / 261 (worker 215 / 260 + IPC 0.4 / 0.6) · held 0.3 / 0.5 · queue 0 / 0 · network 0.9 / 1.1 · render 0.4 / 0.5. HTTP network 55 / 100 (was 102 / 145). Bottleneck is now CT2 decode (~215 ms).
T_final regression cause (WS warm final breakdown, median / max): stop→recv 308 / 474 (was 259 / 309); **FINAL queue wait 64 / 228 ms (was 31 / 66)** — with a 200 ms floor a partial decode is more often in flight when stop arrives, and the worker decodes serially, so FINAL waits for it; decode 228 / 262 unchanged; FINAL reuse 3/12. Not silently accepted: still ≤ 500, but candidate fix for a later milestone = on stop, drop/abandon the in-flight partial result and give FINAL priority (worker is serial, so a cancel needs worker support) — not applied.
Resources: worker cold load 4200 ms + prewarm 511 ms (was 2485 + 420; first load after other GPU work, 확인 필요 whether disk cache). VRAM idle 615 → +worker 1646 (+1031) → +server without HF 1646 (+0) → during WS/HTTP 1645–1774 (worker only) → HF loaded on first legacy request: peak 3789, 2759 after → **HF stays resident after the first on-demand load until server restart** (no idle unload implemented). GPU util while streaming: median 44.5 % (was 18 %), p95 82 %, max 100 % — the 200 ms floor roughly doubles GPU duty while speaking. Worker RSS ≤ 1431 MiB, server RSS ≤ 1597 MiB. server/worker logs: 0 error lines.
Offline/local: 0 non-loopback TCP connections (worker·server, ss every 5 s); 1 Unix-socket connection.
Correctness: 19/19 main runs + worker-down REALTIME_STT_E2E_OK (phrase exactly once, no session/intake calls while speaking, 390/1280 no overflow, worker kill → legacy FINAL once).
Known limit (recorded, not fixed): **HF fallback cold load ≈ 8.2 s** (legacy run 1 T_final 8782 ms) when the fallback is used for the first time — to be improved in a separate fallback architecture.
**Verdict M1: PASS** — T_partial WS p95 465 ≤ 600 (e2e, measured), T_final p95 432 ≤ 500, HTTP p95 515 / 400, all functional/privacy/fallback items pass. Targets not lowered. Open items carried forward: T_final regression (+128 ms p95, FINAL waits behind in-flight partial), GPU duty ×2.5, HF fallback cold load ~8 s and no unload after use.

## M2 — server VAD (Silero v6 ONNX in the worker venv) e2e (2026-09-30)
Decision (user, 2026-09-30): reuse `~/stt_ct2_env` (faster-whisper's bundled `silero_vad_v6.onnx` + onnxruntime 1.30 CPU) — **no install, `~/ai_env` unchanged**. Implementation: `6196f5e` (worker `vad` op with per-connection state, not blocked by decode lock; pure `Endpointer` start ≥96 ms / end ≥600 ms silence; 300 ms pre-roll; no decode outside speech; hallucination guard when speech ratio < 0.3; VAD failure → manual stop) + `e79010e` (fixes below). Silero streaming check (CPU): frame-by-frame = batch (max diff 0.0), 0.084 ms/frame; sample has an ≈830 ms pause between its two sentences → 2 utterances expected at 600 ms.

**🚨 OFFLINE violation found and fixed.** First M2 run (`logs/rt_m2_20260930_2206/`, 22:06–22:09) recorded 6 ESTABLISHED HTTPS connections from the **worker** (PID 1412070; server was 1412127) to 52.168.117.169:443 and 20.184.175.{1,7}:443. Cause: onnxruntime official Linux builds ship 1DS telemetry **ON by default** (onnxruntime/Privacy.md). Fix `e79010e`: `ORT_DISABLE_TELEMETRY=1` forced in worker `main()` and before `import onnxruntime` + `disable_telemetry_events()`; test proves the env is set at import time (mutation: removing it fails the test). Verification: 45 s CPU VAD process → 0 external TCP; re-run below → 0. Local telemetry store `~/.cache/Microsoft/DeveloperTools/.onnxruntime/` (deviceid created 2026-09-07, before this project used ORT — other projects also use onnxruntime) **not deleted** (shared). 확인 필요: db mtime changed 22:21:40 (after the 45 s check, before the re-run) — likely WAL checkpoint at process exit; whether anything is sent at exit is not covered by 5 s ss sampling → verify with a network-level block during offline packaging.
Also fixed (review finding): VAD requests are split into ≤1 s batches — a single WS/HTTP chunk > 2 s used to get BAD_REQUEST from the worker and permanently disable VAD for that stream.

Re-measure after fixes (`logs/rt_m2_20260930_2222/`, 22:22–22:26, GPU at start 4 % / 625 MiB, same runner/sample/run plan as M1c; HF fallback on-demand):

| metric | M1c (manual stop) | **M2 (server VAD)** | target |
|---|---|---|---|
| T_partial WS warm p50 / p95 | 316 / 465 (all packets) | **279 / 424** (n=720, packets inside VAD speech spans only) | ≤ 600 ✓ |
| T_partial HTTP p50 / p95 | 398 / 515 | 306 / 514 | ✓ |
| **T_final_vad** (speech end → FINAL shown; spec §5 definition) WS p50 / p95 (24 utterances) | – (not applicable) | **832 / 932** | ≤ 500 ✗ |
| T_final_vad HTTP p50 / p95 (8) | – | 865 / 966 | ✗ |
| T_final stop click → FINAL (after auto finals, the manual FINAL is empty) WS p50 / p95 | 308 / 432 | 17 / 18 | |
| auto VAD FINALs per run | – | **2 in every run** (12 WS + 4 HTTP) | 2 |
| transcript CER (all runs) | 0.000 | **0.000** — two FINALs joined, phrase exactly once (no duplication/loss) | |
| legacy T_final run 1 (HF cold) / run 2 | 8782 / 548 | 5124 / 648 | fallback |
| worker-down → legacy (status vad = manual) | 645 | 630 | fallback |
| GPU util median while streaming · VRAM worker only / peak after HF | 44.5 % · 1646 / 3789 | 40 % · 1653 / 3788 | |
| external TCP (worker + server) | 0 | **0** | 0 |

T_partial breakdown (WS, p50/p95): tick_wait 93 / 209 · decode 187 / 236 · queue 0 / 0 · network 0.9 / 1.0.
T_final_vad composition: silence threshold 600 ms (19 frames = 608 ms) + frame/packet granularity + FINAL decode ~190–240 ms → ~830 ms. **This misses the ≤500 ms target structurally while silence_ms = 600** (the silence wait alone exceeds 500). Target not lowered. Options (not applied, need real-speech data — plan Task 12 step 2): (a) speculative FINAL: start the final decode at ~200–250 ms of silence and commit it when the 600 ms end is confirmed (cuts decode off the critical path → ≈ 610–650 ms, still > 500); (b) shorter silence (~250–300 ms) + speculative FINAL (≈ 300–350 ms) with the risk of splitting mid-sentence pauses (FINALs are joined losslessly, but mapper sees fragments); (c) keep 600 ms and define the VAD path's UX differently — requires user decision.
**Verdict M2: functional PASS / latency PARTIAL** — speech-stop detection, automatic FINALs, no duplication/loss, CER 0, manual stop coexistence, VAD-failure and worker-down fallbacks, offline 0 connections all pass; T_final (speech end → FINAL) 832/932 ms > 500 ms. Real-speech silence tuning (Task 12 step 2) not done — needs the user. M3 not started.

## M2 speculative FINAL predecode + OFFLINE release gate + threshold tooling (2026-09-30 23:11–23:20)
Commit `a8713b3`. Predecode: after 96 ms of silence inside an utterance the server decodes a FINAL candidate from the utterance snapshot (speech + short tail) through the FINAL-priority queue; the result stays in server memory — **no message, no FINAL, no state change before the VAD endpoint**; speech resuming drops (and cancels) the candidate; at the endpoint (or a manual stop during silence) the candidate becomes the FINAL (`srv_ms.predecoded`). Partials pause while a candidate is pending. Tests: candidate computed but nothing shown before the endpoint, no extra decode at the endpoint, dropped on resumed speech, manual stop uses it (mutations: early emit / no drop / ignore candidate → all fail).

**OFFLINE release gate** `scripts/release_offline_check.sh`: `unshare -rn` (no root) + lo + dummy default route (blackhole: nothing leaves the PC) + `ss -tunap` every 0.2 s incl. 5 s after shutdown + positive control (deliberate connect to 203.0.113.7 must be detected). Worker + server + browser e2e (WS/HTTP/legacy + worker-down) run inside.
| run | product non-loopback attempts | e2e | verdict |
|---|---|---|---|
| fixed worker (`logs/release_offline_20260930_231138/`) | **0** | main 0 · workerdown 0 | **RELEASE_OFFLINE_OK** |
| negative control: pre-fix worker `6196f5e` (`logs/release_offline_20260930_231256/`) | **354** (python worker: repeated DNS queries to the WSL resolver 10.255.255.254:53 — telemetry endpoint lookups, blackholed) | 0 · 0 | **RELEASE_OFFLINE_FAIL** (gate works) |
Positive control detected in both runs. → the gate catches native-library telemetry that 5 s host sampling alone could miss (exit-time 확인 필요 from the previous section is now covered: 5 s post-shutdown sampling, 0).

M2 e2e with predecode (TTS sample, threshold 600, `logs/rt_m2_20260930_2314/`, 0 external TCP):
| metric | M2 without predecode | **with predecode** |
|---|---|---|
| T_final_vad WS p50 / p95 (24) | 832 / 932 | **606 / 608** |
| T_final_vad HTTP p50 / p95 (8) | 865 / 966 | 607 / 607 |
| predecoded FINALs | – | 24/24 WS, 8/8 HTTP |
| T_partial WS p50 / p95 | 279 / 424 | 288 / 458 |
| CER · auto FINALs per run | 0 · 2 | 0 · 2 |
→ FINAL decode is off the critical path; T_final_vad ≈ silence threshold + ~6 ms. **≤ 500 needs a threshold below ~490 ms**; which one must be decided on real speech (false endpoints).

Threshold tooling (commit `a8713b3`): `scripts/stt_replay_prepare.py` (any audio → 16 kHz WAV + answer manifest), `medmap-web/e2e/stt-vad-replay.e2e.mjs` (browser fake-mic replay; per recording: false endpoints = FINAL boundary not at a sentence end ±2 chars, missed endpoints = sentence end without a boundary, delayed end = last sentence closed only by manual stop, T_final_vad, CER/del/ins/sub, duplicate FINAL, numeric accept-list), scorer unit tests `node --test e2e/replayScore.check.mjs` (5), `scripts/stt_vad_sweep.sh` (worker once, server per threshold, status `vad_silence_ms` verified).
**Tool smoke only — synthetic TTS, NOT decision evidence** (`logs/rt_vadsweep_20260930_2317/`, 2 files, 1 repeat, 4 internal sentence ends): T_final_vad p50/p95 — 300: 356/406 · 350: 308/397 · 400: 397/489 · 450: 490/512 · 600: 606/606; false endpoints 0/4 and missed 0/4 at every threshold (TTS has no hesitations); numeric 4/5 at every threshold (the known "삼십팔 도 오 분" → "38도" loss, threshold-independent); CER 0.049.
Real human recordings: none exist on this PC (all local audio = SAPI TTS). Recording kit written to `C:\Users\<user>\Desktop\medmap_stt_rec\` (12 scripts incl. hesitations "…" and numeric phrases + answer manifest). **M2 stays open until the real-speech sweep.**

## M2b preparation — recording kit v2, Kiwi turn completion, pause census (2026-10-01 00:00–00:25) — **no threshold / policy values decided**
- **Recording kit v2** (`C:\Users\<user>\Desktop\medmap_stt_rec\`, v1 moved to `v1_old\`): 32 answers to doctor questions — short answers ×6, full sentences ×2, connective ×3, hesitation ×2, thinking pauses ×3 (incl. a pause inside "삼십팔 점… 오 도"), long 2–3 sentences ×2, numbers ×8 (37.5/38.5 °C, 120/80, 94 %, 500 mg, 6 h, 하루 세 번, 두 알, 30분, 2시간, 110), fast ×3 / slow ×2, natural Q&A ×2. Manifest has category/speed/question and numeric `span` (validated).
- **Turn completion** `medmap/stt_turn.py` (commit `0f3fff7`): Kiwi (kiwipiepy 0.23.2 **already in ~/ai_env — no install**, LGPL v3, model bundled; offline run verified; 0.06 ms/call, load 0.66 s, +~500 MB RSS) last-morpheme classes complete / continuing / incomplete / ambiguous / unknown + regex fallback (Kiwi failure / MEDMAP_STT_TURN_KIWI=0). Classes only, no waits. On the kit's reference text: 49/49 pause points consistent (no mid-sentence pause classed complete; every sentence end complete or ambiguous) — reference text, not STT output.
- **Pause census** (MEDMAP_STT_PAUSE_CENSUS=1, off by default): one log line per in-speech pause — duration, resumed/censored, completion class of the last partial and of the predecode candidate, candidate == partial, candidate ready time; numbers/codes only (0 transcript text in logs, checked). `scripts/stt_pause_census.py` tables per class (pauses < 96 ms excluded and counted). Sweep token `census` = endpoint 1500 ms + census.
- **Correction**: `medmap.*` loggers have **no handler** → every `medmap.stt_stream` INFO line (final/vad_failed/…) was dropped in all earlier runs; earlier "server log 0 error lines" only covered uvicorn output. First census run produced 0 lines. Fixed (`c55a2a9`): census mode attaches a stderr handler to stt_stream/stt_turn only; product logging unchanged; test checks the real output path (assertLogs alone could not catch it).
- Replay scorer: numeric split (FINAL boundary inside a number span), "…" normalised, T_partial, predecode reuse/discard rates (server now reports per-utterance `spec_discarded`), per-category table, manual-correction proxy.
- **OFFLINE release gate with Kiwi loaded** (`logs/release_offline_20261001_002*`): product attempts 0, Kiwi pause lines 30, `RELEASE_OFFLINE_OK`.
- TTS tool smoke of census (`logs/rt_vadsweep_20261001_0022*`, **synthetic — not decision evidence**): 19 pauses, 13 were < 96 ms word gaps; at the 832 ms sentence gap the last partial was classed incomplete (it lagged behind the audio) while the predecode candidate was complete → partial-vs-candidate "stability" is weak (0.167); **candidate ready 307 / 507 ms (p50/p95) after pause start** → a 300–350 ms fast endpoint is not reachable unless the candidate is ready earlier (start at the first silent frame and/or not queue behind an in-flight partial) — design input for STEP B, measure on real speech. Also: at a 1500 ms endpoint T_partial p95 rises (1245) because packets in within-utterance pauses have no new partial while a candidate is pending — T_partial should exclude pause packets (to fix in the scorer before STEP A).

## M4 — streaming FINAL → mapper candidates prepared ('확인 대기') (2026-10-01, commit `0ce07a3`)
Behaviour: after each streaming FINAL is appended, the full textarea text is sent to the stateless `/v1/intake/extract` (not `session.extract` — no app pending/error, no session, no storage); latest request wins (generation counter); the list "확인 대기 중인 증상 후보" shows Korean labels only (no status, no source text, no buttons). [확인하기] with unchanged text reuses the prepared candidates (no second extract) → the existing confirmation step (user still confirms; PatientState only after start). Typing changes the text → list hidden → normal extract. Prepare failure is silent → normal extract. **Legacy VoiceInput path unchanged** (STT-1 contract: no extract before 확인하기 — the first implementation broke it and the existing integration test caught it; prepare is now streaming-only).
Contract change (planned in M4, reported): on the **streaming** path the mapper is called once per FINAL before 확인하기 (speculative, stateless).
Tests: hook 5 + screen 4 (FINAL→list→no re-extract, typing→hidden→one extract, late first response discarded, failure silent) + mutations (no reuse / stale list / no prepare → all fail); vitest 280, backend 348 (skip 5).
CPU regression e2e (flag off, `logs/regress_m4_*`): natural-intake E2E_OK · FLOW_E2E_OK · SUMMARY_E2E_OK · ENGLISH_AUDIT_OK (USER_VISIBLE_ENGLISH=0) · DOCTOR_E2E_OK.
Browser e2e (`logs/rt_m2_20261001_0147/`, GPU uncontended at start, VAD 600 ms, 0 external TCP): every WS/HTTP run showed the list, extract calls = 2 = number of FINALs, **0 extra extract on 확인하기**, confirm step reached.
| metric | WS (12 warm) | HTTP (4) | target |
|---|---|---|---|
| **T_prep** (FINAL shown → candidate list shown) p50 / p95 | **3.8 / 5.0 ms** | 3.6 / 4.7 | ≤ 300 ✓ |
| extract request round trip p50 / p95 | 2.8 / 3.2 | 2.3 / 3.0 | |
| T_partial p50 / p95 · T_final_vad p50 / p95 · CER | 277 / 420 · 606 / 626 · 0 | 306 / 492 · 607 / 608 · 0 | |
Verdict M4: **PASS** (functional + T_prep). The rule-based mapper is ~3 ms, so preparation is effectively free; the end-to-end wait is dominated by the endpoint (M2, open).

## M5 — Doctor real-time loop T_next (2026-10-01 01:54, commit `0490bc9`)
Instrumentation only (no behaviour change): `useDoctorSession.answer` marks `doctor_answer_click` when the request is actually sent and `doctor_answer_response` on success; `NextInformationSection` marks `doctor_next_render` (questions_used only) when a new view is painted (useLayoutEffect). Test: marks in order click → response → render per answer, numbers only (mutation-free check: key whitelist). vitest 281.
e2e `doctor-latency.e2e.mjs`: fixed doctor-mode HIT path (#/handoff → #/doctor → 건너뛰기 → 3 answers), 20 runs (new browser context each, 390/1280 alternating), server restarted before the run (CPU only, port 8012). Conditions: 12 cores, load avg 0.39→0.58, GPU 21 % / 289 MiB (not used). Raw `logs/rt_m5_20261001_0154/`.
| T_next (answer click → updated candidates + next question / budget message painted) | p50 | p95 | max | n |
|---|---|---|---|---|
| **warm** (runs 2–20) | **15.6** | **16.4** | 17.2 | 57 |
| click → response | 15.0 | 15.5 | 16.6 | 57 |
| — server (Resource Timing requestStart→responseStart) | 3.8 | 4.2 | 4.7 | 57 |
| response → render | 0.6 | 0.8 | 1.1 | 57 |
| first run after server restart (3 answers) | 15.4 | 15.9 | 16.0 | 3 |
Per question (warm p95): q1 16.7 · q2 15.7 · q3 (budget reached) 15.8.
Target ≤ 500 ms warm: **met with a wide margin → M5 PASS**. Notes: (1) "cold" here is not a cold server path — the handoff/doctor view requests before the first answer already exercise the engine; server process start itself was not measured. (2) ~10 ms of click→response is outside the server and HTTP (http total 4.6 ms) — client-side request preparation before fetch starts; cause not analysed (확인 필요), irrelevant to the target. (3) Speech path end-to-end is dominated by the endpoint (T_final_vad ≈ 606 ms at 600 ms threshold, M2 open); mapper preparation (M4) ~5 ms and doctor answer loop ~16 ms add little.

## Offline packaging — no-GPU parts (2026-10-01, commit `99e494a`; GPU parts deferred: another session has GPU priority until ~10-02 04:00)
- `scripts/offline_env.sh`: HF_HUB/TRANSFORMERS/HF_DATASETS offline, HF + onnxruntime telemetry off, DO_NOT_TRACK, local paths (CT2 model, worker/server python, HF_HOME). Sourced by `demo_serve.sh` and `release_offline_check.sh`. `speech.py` untouched (HF Whisper resolves from the local cache because of the offline env).
- `scripts/offline_assets_check.py` (no GPU/network): this PC → **OFFLINE_ASSETS_OK** — frontend 0 external URLs (only XML namespace / React error-link strings), CT2 model 1.62 GB, HF Whisper cache 1.62 GB, worker venv imports + Silero ONNX + cublas/cudnn, server venv imports + Kiwi model. Tests 9 (incl. CDN/API URL detection, missing weights, extra-condition=0).
- `demo_serve.sh --stt-streaming`: GPU check → worker (LD_LIBRARY_PATH, socket) → wait "worker ready" (90 s) → ct2 streaming server; worker stopped when the server exits; GPU busy or worker not ready → legacy voice (fail-safe). `--dry-run` prints the plan. Behaviour change: the default demo now always runs with the offline env (a missing model fails instead of downloading). Tests 6: dry-run default/streaming/GPU-busy/bad option + real path with fake worker/server (ready → ct2 env, worker PID gone after server exit; worker failure → legacy). Mutation (no worker cleanup) → fails; its orphan fake worker was identified by the test env marker and killed.
- Smoke (CPU, port 8013): default `--http` demo served index 200, status streaming=false/engine hf, server process env HF_HUB_OFFLINE=1 · TRANSFORMERS_OFFLINE=1 · ORT_DISABLE_TELEMETRY=1; stopped, port freed.
- Not run (GPU): `demo_serve.sh --stt-streaming` real start, release gate re-run with the new env file. Open: bundle form (venv copy / container / installer) and target hardware — user decision; Kiwi LGPL v3 distribution terms (확인 필요). Doc: `docs/offline_deployment.md`.

## M6 — performance regression gate framework (2026-10-01, no GPU used)
`scripts/perf_gate.py` (collect / compare) over the browser e2e outputs; server-only `bench_realtime.py` (plan Task 16) **not built yet** (needs GPU; e2e is the closer-to-user measurement). Rules: regression = p95 > baseline × 1.2 **and** +10 ms (noise guard for 5–16 ms metrics); new target miss (baseline met the target) fails; baseline already over target → `known_target_miss` listed, worse still fails via the relative rule; CER +0.01 fails; missing metric fails; GPU util > 30 % at measurement start → `INVALID_CONTENDED` (exit 3). Tests 10 + mutations (no abs slack / no known-miss exception / no contention refusal → all fail).
**Baseline** `exp/perf_baseline/2026-10-01_realtime.json` (10 metrics, uncontended: GPU 0 % at start) from the M4 e2e (`logs/rt_m2_20261001_0147`, commit `0ce07a3`) + M5 e2e (`logs/rt_m5_20261001_0154`, `0490bc9`): T_partial p95 WS 420 / HTTP 492 · T_final_vad p95 WS 626 / HTTP 608 (**known target miss, M2 open**) · T_final (stop) 17 / 18 · CER 0 / 0 · T_prep 5 · T_next 16.4.
Real-data check: the pre-predecode M2 run (`logs/rt_m2_20260930_2222`) as current → **PERF_REGRESSION** (T_final_vad WS 626→932, HTTP 608→966; T_prep missing), exit 2. Self-compare → PERF_OK.
Open: server-only bench, CI hook (run the gate after each realtime e2e), rebaseline after M2 threshold decision.
