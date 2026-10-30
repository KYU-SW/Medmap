# EXP-SN-CORE-001 preflight-01 (2026-10-02, RG RUN f58848463d34 이후, ck-v0 작성 전)

## 1. 실행 수단 변경 사유
- 계획서 rev3: Claude Code 서브에이전트 `.claude/agents/ck-*.md`(Read·Write 제한)
- 실측: 실행 중 세션에 새 에이전트 정의가 반영되지 않음(`Agent type 'ck-author' not found`) → 사용 불가
- 사용자 승인(2026-10-02): 격리 CLI 사용. 승인 범위 = 격리 방식 사용. 정가 환산 추정치(시험 1회 `costUSD 1.40`, `costBasis: list`)는 실제 청구액으로 기록하지 않음. 실제 billing 상태는 별도 확인(확인 필요)
- 생성했으나 미사용: `~/.claude/agents/ck-author.md`·`ck-author-alt.md`·`ck-verifier.md`(세션 미반영)

## 2. 격리 실행 명령(고정)
```
cd /home/<user>/medmap_core_kb_ws
ENABLE_CLAUDEAI_MCP_SERVERS=false claude -p --restricted --strict-mcp-config --tools Read,Write \
  --permission-mode acceptEdits --model <opus|sonnet> --output-format json "<프롬프트 파일 내용>"
```

## 3. 점검 결과 (session 5995728a-5d11-444f-a417-6402cbad2ddd, 모델 claude-opus-5-5)
| # | 사용자 요구 | 점검 | 결과 |
|---|---|---|---|
| 1 | 외부 connector/tool 비활성 | 에이전트 자기 보고 도구 목록 | PASS — Read·Write만, MCP·Gmail·Drive·Slack·Notion 없음 (dry-run 1회차는 `--strict-mcp-config` 없이 connector 노출 → 추가로 해결) |
| 2 | 허용 도구 Read·Write | 동일 + transcript tool_use 7건 전부 Read/Write | PASS |
| 3 | 작업 루트 고정 | 작업 디렉터리 보고 | PASS — `/home/<user>/medmap_core_kb_ws` |
| 4 | 폴더 밖 canary | 절대경로 Read·심볼릭 링크 Read·`../` 상대경로 Read·프로젝트 MEMORY.md Read·폴더 밖 Write | PASS — 5건 모두 `--restricted confines the file tools to the working directory` 로 거부, 폴더 안 Read·Write 성공 |
| 5 | CLAUDE.md·메모리·EXP-SN·DDXPlus 주입 없음 | 에이전트 자기 보고(주입 맥락 절 목록) | PASS — 기본 시스템 프롬프트·userEmail·gitStatus(홈 저장소, clean)만. CLAUDE.md·메모리·DDXPlus·EXP-SN·STEP1x·release_conditions·PATHOLOGY 아니오 |
| 6 | 네트워크/외부 검색 불가 | 도구 목록 | PASS(도구 수준) — WebFetch·WebSearch·Bash 없음. 모델 API 통신 자체는 실행에 필요 |
| 7 | 기록 | 본 문서 + RG deviation | — |

## 4. transcript 검사기 대조
- 검사기 `scripts/core/transcript_scan.py`(SHA 7d6e6917…dd11)
- 양성 대조(실제 preflight transcript, SHA cde495ab…): INVALID, 위반 14건 — 폴더 밖 경로 5건 전부 + 심볼릭 링크 realpath 탈출 + 금지 문자열 검출
- 음성 대조(합성: 폴더 안 Read + Write 본문·생성 텍스트에 일반어 "pathology"·"memory"): CLEAN
- transcript 원천: `~/.claude/projects/-home-<user>-medmap-core-kb-ws/<session_id>.jsonl`

## 5. 한계
- 주입 맥락 확인은 에이전트 자기 보고 기반(시스템 프롬프트 원문 직접 확인 불가)
- 주입 gitStatus는 홈 디렉터리 git 저장소 상태(clean, 커밋 없음)

## 6. 추가(5회차 gate 대응, deviation-08)
- 주입 맥락 객관 확인: preflight transcript(5995728a)의 attachment 9건(environment·model·total_tokens_reminder ×2·session_context·date·credential_org·prompt_snapshot ×2, system prompt 원문 포함) 전문 검사 → CLAUDE.md·DDXPlus·release_conditions·memory·/medmap/·EXP-SN·STEP13/16/17·safety-net 적중 0. 금지어 적중은 메인 세션이 보낸 점검 프롬프트·MEMORY.md canary(거부됨)·에이전트 답변에만 있음
- 검사기 주입 맥락 검사 추가(SHA 66efa0f9…c7d): 합성 양성(주입에 CLAUDE.md·DDXPlus) INVALID, 합성 음성 CLEAN
- 미해결: sonnet 경로 canary(추가 CLI 1회 필요) · 실제 billing 확인(사용자 결정)
- 2026-10-02 18:39 KST opus 주간 사용량 한도(HTTP 429, reset 2026-10-05 07:00 KST) — 심사관은 sonnet으로 실행. 격리 CLI의 opus 실행도 같은 한도 적용 가능(확인 필요)

## 7. 추가(2026-10-02 18:55, deviation-09)
- 과금 승인 근거(사용자 원문): CLAUDE.md 1-1 형식 보고(왜·어디서·추정치·무료 대안·미진행 시 문제) 후 사용자 "머야 다시 진행해 나 초기화 시켰으니까" — 사용량 한도 초기화 후 격리 CLI 진행 승인으로 기록. 정가 환산 추정치는 청구액 아님. claude.ai 추가 사용량 과금 설정 상태는 사용자 미답(확인 필요)
- sonnet 경로 canary(session 77cb846c-85e4-41bc-85f1-d33349f81f27, claude-sonnet-5-5): 폴더 안 Read·Write 성공, 폴더 밖 5건(절대·심볼릭 링크·../·MEMORY.md·밖 Write) 전부 `--restricted` 거부 — opus와 동일 PASS
- 원본 기록 검사(검사기 66efa0f9…c7d): tool_use 7건 전부 Read/Write, 주입 attachment 9건 금지어 적중 0, MCP·deferred 도구 목록 attachment 없음(system prompt 본문의 "Bash" 단어는 일반 안내문)

## 8. 추가(6회차 gate 대응, deviation-10)
- §3 5행·§5의 "자기 보고 기반" 확인은 §6·§7·§8의 원본 기록 검사로 대체됨(원문 보존)
- 검사기 f3cbd95c…fa30: attachment 유형 허용 목록(관측 7종) 밖이면 INVALID, 모델·CLI 버전 기록(2.1.287 아니면 경고), "ddxplus" 단독 언급 횟수 보고용
- 실제 형식 양성 대조: 일반 세션 기록 c91c47c7 → INVALID(ATTACHMENT_TYPE_NOT_ALLOWED 44, FORBIDDEN_IN_INJECTED_CONTEXT 17 — instructions=CLAUDE.md·nested_memory 등). preflight 기록 2건(opus·sonnet)은 위반 14건(canary 의도) 그대로, 비허용 유형 0
- sonnet canary 실제 명령: `cd ~/medmap_core_kb_ws && ENABLE_CLAUDEAI_MCP_SERVERS=false timeout 280 claude -p --restricted --strict-mcp-config --tools Read,Write --permission-mode acceptEdits --model sonnet --output-format json "$(cat preflight/prompt.txt)"` (정가 환산 추정 total_cost_usd 0.0358, 청구액 아님)
- Stage 1 준비(실행 전): 입력 = view2 문서 18개 복사본(원본 SHA 일치) + 20% 표본 509단위, 프롬프트 A1b1·A1b2·A1b3·A1alt, SHA `~/medmap_core_kb_ws/stage1/PROMPTS.sha256`·`INPUT_SHA256SUMS`(18:56 고정). A1 프롬프트 금지 문자열 0

## 9. 추가(7회차 gate 대응, deviation-11)
- 작업 폴더 위생: `~/medmap_core_kb_ws/{preflight,dryrun}` → `~/medmap_core_kb_preflight/`, `stage1/run_stage1.sh` → `~/medmap_core_kb_runner/`(새 스크립트 SHA 6ce917be…0d5, 실행 직후 작업별 허용 목록 검사). 이동 후 작업 폴더 안 파일 = stage1 입력·프롬프트·SHA 목록뿐, 입력 외 금지어 파일 0
- 이동 영향: preflight 기록 77cb846c의 심볼릭 링크 canary는 링크 파일 이동으로 realpath 재검사 불가 → 위반 14→13(원래 판정은 §3·§7, 런타임 거부 사실은 불변)
- 대조 기록: preflight 세션 3건 = 폴더 밖 canary(5995728a opus·77cb846c sonnet) + MCP 노출 양성(fad231ff, --strict-mcp-config 없음: ATTACHMENT_TYPE_NOT_ALLOWED deferred_tools_delta·mcp_instructions_delta·deferred_tools_record) — Stage 1 집계 제외. 일반 세션 양성 대조는 사본 고정 `~/medmap_core_kb_preflight/c91c47c7_snapshot.jsonl`(2026-10-02 19:04:46, 422줄, SHA a09470b6…8ea6)
- 검사기 f5ebfc0e…3d6 합성 대조: 비허용 입력·타 작업 출력 Read → INVALID 2건 / 허용 입력 Read·자기 출력 Write → CLEAN / `<synthetic>` 모델 → INVALID
- 입력 v2: 2000자 초과 줄 34단위(표본 5) 문장 경계 분할, 2,487단위 ID·순서 동일, 본문 결합 시 원문과 동일(1건은 절 제목 괄호 중첩으로 머리 형식만 다름, 결합 원문 동일 확인). v1 입력·프롬프트는 `~/medmap_core_kb_preflight/stage1_v1_superseded/` 보존

## 10. 추가(8회차 gate 대응, deviation-12)
- 입력 v3(조각): v2를 파일당 ≤45,000자·≤250줄로 줄 경계 분할(SRC-0001 8, SRC-0007 2, SRC-0012 3, SRC-0013 2, SRC-0014 2, 나머지 1, SAMPLE20 5), 조각 결합 = v2 원문 기계 확인. v2는 `~/medmap_core_kb_preflight/stage1_v2_superseded/` 보존. 목록 `~/medmap_core_kb_runner/chunks.json`(b5afe647…01c9f)·`jobs_stage1.json`(2ba45cc0…aa0c)
- 검사기 3699ba1c…7446 합성 대조: 오류 Read → COVERAGE_INCOMPLETE(29줄) INVALID / 절반 반환 → INVALID(15줄) / offset 분할 완독 + part 파일 Write → CLEAN. 회귀: 이전 합성 대조 판정 불변(허용 목록 위반·모델 불일치 INVALID), 주입 양성 INVALID, 일반 세션 사본 c91c47c7_snapshot INVALID(ATTACHMENT_TYPE_NOT_ALLOWED 117·FORBIDDEN_IN_INJECTED_CONTEXT 29 — 사본 기준값; §9의 44는 같은 파일의 이전 시점 원본 값)
- runner v2(ba826129…e4fed): try 번호, try2 전 try1 산출물·로그 quarantine 이동·SHA, out 비움 확인, 실행 직후 작업별 검사
- Stage 1 고정 2026-10-02 19:12:44 KST: INPUT_SHA256SUMS(파일 SHA 04d88055…0f08), PROMPTS.sha256(파일 SHA 95a51e6c…dfabf). v1(18:56)·v2(19:05:25) 폐기
