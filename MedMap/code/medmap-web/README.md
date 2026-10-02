# MedMap Web (Natural Intake 기능 검증 UI)

기능 검증용 최소 UI다. 최종 디자인이 아니다(디자인 작업 PAUSED, 2026-09-25).

## 실행

```bash
# API — data/ 와 exp/step16b_next_information_validation/model_k*.pkl 이 있는 체크아웃/worktree 에서
# (모델 파일은 git 에 없음. 이 worktree(~/medmap-worktrees/natural-intake)는 ~/medmap 을 가리키는 읽기전용 symlink 로 가지고 있다)
cd ~/medmap-worktrees/natural-intake && ~/ai_env/bin/python -m uvicorn medmap.api:app --host 127.0.0.1 --port 8000
# UI
cd ~/medmap-worktrees/natural-intake/medmap-web && npm ci && npm run dev   # http://127.0.0.1:5173
```

## 흐름

자유 텍스트 → `POST /v1/intake/extract`(후보만) → 사용자 확인(있음/없음/빼기) → initial 결정
→ 부족분 bootstrap(한 번에 한 문항) → `POST /v1/session/start`(initial 1 + 정확히 3) → 기존 IG 질문

- initial: 확인된 POSITIVE 중 initial 가능(96개) 1개면 그것, 2개 이상이면 "가장 불편한 증상" 선택, 0개면 자주 쓰는 8개 + 검색. NEGATIVE·과거력은 initial 불가.
- start feature는 확인된 POSITIVE와 bootstrap의 known 답(있음/없음)뿐이다(STEP17A 검증 범위).
- additional: initial 제외 확인 POSITIVE를 발화 순서로 앞 3개. 나머지 POSITIVE는 cache(`sessionStorage['medmap.intakeCache']`, `{evidence_id, status}`만). 엔진이 그 질문을 실제로 제안할 때만 `/session/answer`로 적용(질문 예산 1 사용).
- bootstrap: 부족분 = 3 − additional. 순서 E_91 → E_53 → E_66, 예비 E_201 → E_175 → E_88(STEP17A 고정), initial·확인된 POSITIVE는 건너뜀. **확인된 NEGATIVE가 이 frozen 순서 안에 있고 실제로 그 지점까지 걸어서 도달하면** 다시 묻지 않고 그 NEGATIVE를 해당 질문의 답으로 재사용한다(known 1개로 세고 `/session/start` 본문에 포함, cache에서 제외). 도달하기 전에 부족분이 이미 채워졌거나 frozen 목록 밖이면 그대로 cache에 남는다(rev3). "잘 모르겠어요"는 기록만 하고 개수에 넣지 않으며 다음 질문으로 넘어간다. 재사용 가능한 확인 NEGATIVE를 포함해도 남은 질문으로 부족분을 채울 수 없으면 `START_INCOMPLETE` — `/session/start`를 부르지 않는다.
- 원문은 extract 요청 본문에만 쓰이고 서버·브라우저 저장소 어디에도 저장·로그되지 않는다. 입력(나이·성별·원문)·후보·확인·initial·bootstrap 답은 intake 화면이 살아 있는 동안 React 메모리에만 있고(draft 소유는 `NaturalIntakeScreen`, `FreeTextInput`은 controlled), `/session/start` 성공이나 [처음부터 다시]로 화면을 떠나면 사라진다.
- `START_INCOMPLETE`는 오류가 아니다(frozen bootstrap/backup으로 exact-k3 known 답을 아직 확보하지 못한 상태). "진료 질문을 시작하려면 몇 가지 정보를 더 확인해야 합니다." + 지금까지 입력·확인한 내용을 그대로 보여주고, [답변 다시 확인하기]는 "잘 모르겠어요"로 답한 질문만 원래 순서로 다시 보여준다(기본 선택 없음, 있음/없음을 누른 경우만 교체, 새 질문·순서 변경 없음). 교체로 3개가 채워지면 바로 `/start`, 남은 frozen 예비 질문이 있으면 이어서 묻고, 그대로면 "현재 확인된 정보만으로는 다음 상담 질문을 시작하기 어렵습니다."(입력 유지). 입력 초기화는 [처음부터 다시]를 누를 때만.

## 한국어 표시 용어

- 정본 `medmap/data/terminology_ko.json`(질환 49·evidence 짧은 표시명 223·질문 전문 221(선택 가능 전부)·value 199)만 편집하고 `~/ai_env/bin/python scripts/export_web_terminology.py`로 `src/generated/terminology_ko.json`·`medmap/data/question_labels_ko.json`·initial 카탈로그를 생성한다(생성물 직접 편집 금지, `--check`로 동기 확인).
- 화면은 내부 ID(질환 class·E_*·V_*)로 조회한다: `src/terminology/labels.js`의 `diseaseLabel`·`evidenceShortLabel`·`questionText`·`valueLabel`. bootstrap 문구도 `questionText`. 세션·API 요청은 항상 내부 ID.
- 서버 질문·선택지 문구(QuestionPresenter)와 요약 질환 표시명(TerminologyLabelProvider)도 같은 정본에서 온다.

## 데이터

- `src/intake/initialCatalog.json` = `medmap/data/initial_evidence_ko.json` 사본(`npm run sync:initial`). 표시·검색용, 매퍼 alias 아님.
- 폴더 이름에 `data`를 쓰지 않는다 — 루트 `.gitignore`의 `data/`가 무시한다.

## 음성 입력(STT)

- 자유입력칸 아래 [🎙 말하기] → 브라우저 MediaRecorder(webm/opus 우선, 32 kbps, 최대 60초) → `POST /v1/stt/transcribe`(raw binary body, Content-Type의 `;` 앞 base MIME으로 판정: webm·ogg·wav·x-wav·mp4·mpeg) → 전사문이 입력칸에 들어간다.
- STT는 speech → text만 한다. 매퍼·세션을 호출하지 않고, 자동 제출하지 않는다. 사용자가 고친 뒤 [확인하기]를 눌러야 기존 흐름이 이어진다.
- 기존 입력이 있으면 덮어쓰지 않고 줄바꿈으로 덧붙인다. 기존 문장이 `.!?`나 `요/다/죠`로 끝나지 않으면 매퍼 문장 경계를 위해 `.`을 보충한다.
- 서버: 2 MB 스트리밍 상한(초과 즉시 413), 60초 초과 413, 무음·빈 오디오 422, 지원 외 형식 415, 모델 로드·GPU 메모리 실패 503. 오디오·전사문은 메모리에서만 처리하고 저장·로그하지 않는다.
- Whisper(openai/whisper-large-v3-turbo, 로컬 HF 캐시)는 첫 STT 요청 때 로드된다(API 시작을 늦추지 않음). 로드 후 VRAM 약 +1.8~2.1 GB. `MEDMAP_STT_DEVICE=cpu`로 CPU 강제 가능.
- 음성 입력이 실패해도 텍스트 입력은 그대로 쓸 수 있다.

## 오류·재시도·새로고침

- Notice의 [다시 시도]는 마지막으로 실패한 요청(start·answer·resume)을 같은 인자로 다시 보낸다(stateless라 안전, 처리 중 버튼 비활성). extract 실패는 재시도 버튼 없이 안내만 하고 입력칸 문장은 유지된다.
- 시작 전(서버 세션 없음) intake 화면 위에 "아직 저장된 상담이 아닙니다. 이 단계에서 새로고침하면 입력한 내용이 사라질 수 있습니다."를 작게 표시한다. 잃을 입력이 있을 때만 `beforeunload`로 브라우저 기본 확인창을 띄우고(custom 문구 없음), start 성공·reset·화면 unmount 시 제거한다. 시작 전 입력은 새로고침 후 복구하지 않는다(의도, 저장하지 않으므로).
- 새로고침 시 resume이 네트워크 오류·5xx로 실패하면 저장된 세션을 지우지 않고 [다시 시도]로 복원한다. 4xx(세션 무효)는 조용히 폐기한다.
- 음성 전사 중에는 [확인하기]가 비활성화된다(전사가 버려지지 않도록). 탭에서 첫 전사 전에는 "처음 한 번은 약 10초 정도 걸릴 수 있습니다." 안내가 보인다.
- 요약 화면은 `POST /v1/session/summary {session}`(stateless, `medmap/clinical_summary.py` 결과 `medmap-clinical-summary-v1`)로 PatientState 기준 요약을 받는다. 새로고침으로 복원돼도 같은 세션으로 다시 받으므로 답한 항목이 유지된다. 세션에 반영되지 않은 intake NEGATIVE·bootstrap "잘 모르겠어요"·전사문은 요약에 없다. 요약 요청이 네트워크 오류·5xx면 세션을 보존하고 [다시 시도], 4xx면 resume과 같이 폐기한다.

## 알려진 미검증

- start에는 확인된 POSITIVE와 bootstrap의 known 답만 넣는다. 확인된 NEGATIVE는 frozen bootstrap 순서에서 walk가 실제로 도달한 경우에만 그 질문의 답으로 재사용되며(STEP17A R2/R3가 그 항목에서 공개하는 답과 같은 형태), 그 외 NEGATIVE는 cache로 가서 기존 IG 답변 경로(STEP16B 범위)로 들어간다. UNKNOWN은 start에서 배제한다.
- 사용자가 잘못 확인한 양성의 영향은 미검증이다.
- 4개 이상 확인 시 "발화 순서 앞 3개"는 UI heuristic이며 검증된 규칙이 아니다.
- STEP17A 수치(R3 top1 0.849)는 시뮬레이터 결과이며 실제 사용자 정확도가 아니다.
- bootstrap '잘 모르겠어요' 뒤 예비 질문으로 넘어가는 흐름은 STEP17A 시뮬레이션(UNKNOWN 없음)에 대응 조건이 없다.
- STT 실측은 TTS 합성 음성 1개(7.7초)뿐이다. 실제 사람 발화·소음·사투리·Safari(mp4/aac 녹음) 정확도는 미측정.
- Whisper는 무음·잡음에서 없는 문장을 만들 수 있다. 무음 거부 + 자동 제출 금지 + 확인 화면이 방어선이다.

## 데모 실행(한 주소, HTTPS)

- `scripts/demo_serve.sh`(저장소 루트): `npm run build` → 자체 서명 인증서(처음 한 번, 저장소 밖 `~/.medmap-demo-cert/`, 30일) → API가 `medmap-web/dist`를 같은 주소에서 서빙(`MEDMAP_SERVE_WEB_DIST`). 기본 `https://127.0.0.1:8443`, 이 PC에서만 열림. vite·CORS 불필요.
- 옵션: `--http`(http://127.0.0.1:8000) · `--no-build` · `--prewarm`(서버 시작 직후 Whisper를 백그라운드 로드 — 첫 음성 대기 약 10초 제거, GPU 사용. `wait_for_resources.sh --check`가 WAIT면 자동으로 prewarm 없이 시작) · `--lan`(0.0.0.0 바인딩, 같은 네트워크의 휴대폰 마이크 확인용 — 인증서 경고를 한 번 수락해야 함, 직접 실행할 때만) · `PORT=`.
- 휴대폰 마이크는 HTTPS(보안 컨텍스트)에서만 열린다. WSL에서 `--lan`은 Windows 포트 포워딩·방화벽 설정이 추가로 필요할 수 있다(미검증).
- 오래 띄울 때: `nohup scripts/demo_serve.sh > logs/demo_$(date +%Y%m%d_%H%M).log 2>&1 &` 후 `~/scripts/ram_guard.sh <PID> 90 60 <log>`. 스크립트가 `exec`로 uvicorn이 되므로 `$!`가 곧 서버 PID.
- 환경변수만 쓸 때: `MEDMAP_SERVE_WEB_DIST=<dist>`(index.html 없으면 시작 실패), `MEDMAP_STT_PREWARM=1`. 둘 다 미설정이면 기존과 동일(`/`는 404, STT는 첫 요청 때 로드).

## 테스트

- `npm test` — vitest 전체
- `node e2e/natural-intake.e2e.mjs` — 실서버 스모크(API·vite 실행 중일 때). 캐시된 playwright 경로를 기본으로 쓰며, 다른 경로를 쓰려면 `PLAYWRIGHT_PATH=/path/to/playwright node e2e/natural-intake.e2e.mjs`로 덮어쓸 수 있다.
- `node e2e/voice-intake.e2e.mjs` — 실서버 음성 스모크(Chromium 가짜 마이크, 실제 Whisper). GPU가 다른 작업에 쓰이지 않을 때만 실행.
- `node e2e/flow-hardening.e2e.mjs` — 실서버 흐름 스모크(E NEGATIVE 재사용, F UNKNOWN·START_INCOMPLETE, F-RECOVER 답변 다시 확인하기·beforeunload, 새로고침 resume, API 오류 재시도). GPU 불필요.
- `node e2e/summary.e2e.mjs` — 실서버 요약 스모크(정상·요약 새로고침·상담 중 새로고침·요약 API 500 재시도). GPU 불필요.
- `node e2e/demo-https.e2e.mjs` — `scripts/demo_serve.sh` 실행 중일 때 데모 스모크(https·보안 컨텍스트·마이크 API·same-origin·IG 질문까지). GPU 불필요. 주소는 `MEDMAP_DEMO`로 덮어쓸 수 있다. 다른 e2e도 `MEDMAP_WEB=https://…`가 아니라 `MEDMAP_WEB=http://127.0.0.1:8000`(`--http`)이면 dist 서빙으로 그대로 돈다.
- `node e2e/english-audit.e2e.mjs` — 실서버 화면 영어 노출 감사(고정 seed 경로 `WALKS`(기본 12) × 390/1280px, 후보·initial·검색·bootstrap·IG·후보·요약). 허용: MedMap·병기 약어. 결과 `OUT_DIR/english_audit.json`, 성공 `ENGLISH_AUDIT_OK USER_VISIBLE_ENGLISH=0`. GPU 불필요.

## 실시간 음성·성능 회귀 gate(REALTIME_FIRST)
- 실시간 받아쓰기: `scripts/demo_serve.sh --stt-streaming`(로컬 STT worker + VAD, GPU 바쁘면 기존 음성 입력). 오프라인 배포: `docs/offline_deployment.md`
- 지연 e2e(GPU 필요, `~/scripts/wait_for_resources.sh --check` 단독 실행 후): `e2e/realtime-stt.e2e.mjs`(T_partial·T_final_vad·T_prep·CER), `e2e/doctor-latency.e2e.mjs`(T_next, CPU)
- 목표: T_partial p95 ≤ 600 · T_final_vad p95 ≤ 500 · T_prep ≤ 300 · T_next warm ≤ 500 ms. **목표는 낮추지 않는다.**
- 회귀 gate: `python scripts/perf_gate.py collect ... --out <current.json>` → `python scripts/perf_gate.py compare --baseline exp/perf_baseline/2026-10-01_realtime.json --current <current.json>`
  (0 PERF_OK · 2 PERF_REGRESSION: p95 +20 % 이면서 +10 ms 초과, 새 목표 초과, CER +0.01, 지표 누락 · 3 INVALID_CONTENDED: 측정 시작 GPU util > 30 %). baseline 이 이미 목표를 넘는 지표는 `known_target_miss` 로 표시(현재 T_final_vad — M2 열림).
