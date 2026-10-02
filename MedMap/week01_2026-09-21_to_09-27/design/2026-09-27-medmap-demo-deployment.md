# MedMap P2-7 demo deployment — 계약 (2026-09-27)

브랜치 `feat/demo-deployment` (worktree `~/medmap-worktrees/demo-deployment`, master `407dba2` 기준). HANDOFF §15-3 P2-7. 사용자 2026-09-27 "프로젝트 완성까지 이어서 진행, 자원 양보, 묻지 말 것".

## 고정 (변경 금지)
- 기존 7개 endpoint(health, session/start·answer·resume·summary, intake/extract, stt/transcribe)의 request/response 의미 무변경. 새 기능은 전부 opt-in env, 기본값 = 현재 동작.
- STT 기본 동작 = 첫 요청 때 lazy load(lifespan 에서 로드하지 않음) 유지. 오디오·전사문 저장·로그 금지 유지.
- 외부 publish·클라우드·유료 서비스·LAN 노출 실행 없음(이 세션은 127.0.0.1 로만 검증). frozen 매퍼·startPlan 무수정. 새 의존성 없음(Starlette StaticFiles 는 기존 설치분).

## 변경
1. `MEDMAP_SERVE_WEB_DIST=<dir>`: API 라우트를 모두 등록한 뒤 `/` 에 `StaticFiles(directory=dir, html=True)` mount → `medmap-web/dist` 를 API 와 same-origin 으로 서빙(프론트 BASE='' 그대로, CORS 불필요). dir 에 `index.html` 이 없으면 서버 시작 시 즉시 실패(조용한 404 방지). 미설정 시 mount 없음(`GET /` = 404, 현재와 동일).
2. `MEDMAP_STT_PREWARM=1`: lifespan 에서 **백그라운드 daemon thread** 로 Whisper 로드 시작(서버 시작·health 를 막지 않음). 실패는 로그(코드만)만 남기고 삼킴 → 첫 요청 때 기존 lazy load 가 다시 시도. 미설정 시 현재와 동일. GPU 를 쓰므로 실행 전 `wait_for_resources.sh --check` 는 운영자 책임(스크립트가 안내).
3. `scripts/demo_serve.sh`: `npm run build` → 자체 서명 인증서(없을 때만, `~/.medmap-demo-cert/`, repo 밖) → `uvicorn --ssl-keyfile/--ssl-certfile` + `MEDMAP_SERVE_WEB_DIST`. 기본 `--host 127.0.0.1 --port 8443`. `--lan` 은 0.0.0.0 바인딩(모바일 실기기 마이크 확인용, 사용자가 직접 실행) — 이 세션은 실행하지 않음. `--prewarm` 은 STT prewarm.

## 테스트
- 백엔드(`tests/test_demo_deployment.py`, 가짜 transcriber, GPU 없음): 기본 app 은 `/` 404 · mount 함수: index/asset 서빙, 먼저 등록된 API 라우트가 가려지지 않음, index.html 없으면 ValueError · prewarm: 백그라운드 로드 성공, 실패 시 예외 전파 없음 + 이후 재시도 가능, lifespan 이 flag 일 때만 prewarm 호출, 기본 lifespan 은 transcriber 를 만들지 않음.
- 실서버: dist same-origin(http 127.0.0.1) 으로 기존 text e2e(natural-intake·flow-hardening·summary) · https(자체 서명) 에서 `/health`·`/` 200 과 브라우저 `isSecureContext`·`navigator.mediaDevices` 존재 확인. 실기기 모바일 음성·prewarm 실측은 GPU idle + 사용자 실기기 필요 → 미검증으로 보고.
