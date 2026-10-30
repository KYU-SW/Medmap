# MedMap 메인 AI 연구 영역 (exp/main_ai)

브랜치 `research/main-ai-exp00` (master `977877f` 분기). 제품 코드·기존 exp/step* 와 분리.
지시안의 `experiments/main_ai/` 대신 프로젝트 관례 `exp/` 아래에 둔다.

| 폴더 | 내용 | 상태 |
|---|---|---|
| `common/` | 공통 그래프 스키마(`evidence_graph.py`) | 초안, 단위 테스트 11 |
| `exp00_readiness/` | 데이터 감사·설계·규칙·양식·인수인계 | 완료(2026-10-26) |
| `exp01_symptom_graph/` | 증상 트리 vs 관계 그래프 | 비어 있음 — 다음 단계 |
| `exp02_patient_evidence/` | 환자↔질환 그래프 근거 연결 | 비어 있음 |
| `exp03_text_graph/` | 원문 vs 그래프 vs 결합 | 비어 있음 |
| `exp04_bayesian_voi/` | 베이즈 + 정보가치 | 비어 있음 |
| `exp05_adaptive_search_rl/` | 선택적 RAG + RL | 비어 있음 |
| `exp06_integration/` | 통합 + 제거 실험 | 비어 있음 |

EXP-00 읽는 순서: `exp00_readiness/EXP00_READINESS_REPORT.md` → `HANDOFF_EXP01.md` → `exp01_predesign.md` → `protocol.md`.

재실행:
```bash
cd ~/medmap-worktrees/main-ai/exp/main_ai/exp00_readiness
~/ai_env/bin/python scripts/check_data_access.py --out outputs/data_access_report.json
~/ai_env/bin/python scripts/render_data_assets.py --report outputs/data_access_report.json --out outputs/data_assets_generated.md
cd ~/medmap-worktrees/main-ai && ~/ai_env/bin/python -m unittest discover -s exp/main_ai/exp00_readiness/tests -v
```
