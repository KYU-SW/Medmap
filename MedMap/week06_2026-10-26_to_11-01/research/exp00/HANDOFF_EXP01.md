# EXP-00 → EXP-01 인수인계

## 지금 상태 (2026-10-26)
- EXP-00 판정 CONDITIONAL. EXP-01 은 데이터·재사용 코드 준비 완료, **구현 0 · 실행 0**.
- worktree `~/medmap-worktrees/main-ai`, 브랜치 `research/main-ai-exp00`, 미커밋.
- 이 worktree 에는 `data/`·`*.pkl` 이 없다(gitignore) → 원본은 `~/medmap/data`, 모델은 `~/medmap/exp/step16b_next_information_validation/` 에서 읽기 전용으로 참조.
  모델 SHA256 앞 16자: model_k3 `c3d67142104a41f8` · model_k5 `1cc295e0dc4bd9e8` · model_k10 `e59a9b62c2f3a457` · ig_table `34069a83148cdeea`.

## 다음 할 일(순서)
1. 사용자 결정: 이 worktree 에 Research Guardian 활성화 + EXP-01 rg-plan 작성 승인.
2. `codex_prompt_exp01.md` 로 구현 + SELECT 1,000 사례 스모크.
3. rg-gate RUN 후 SELECT 전체 → 기준 확정 → FINAL 1회 → rg-verify.

## 꼭 지킬 것
- 공식 validate·test 미사용, `release_conditions.json` 모델 입력 금지(순환), DIFFERENTIAL 입력 금지.
- 질환 삭제형 가지치기 금지, UNCERTAIN/NOT_TESTED/NOT_RECORDED ≠ NEGATIVE.
- Baseline A·B 와의 차이는 단일 원인으로 해석 금지(점수기·선택기 동시 변경). 인과 비교는 C→PA→PB→PC.
- 합성 성능 ≠ 임상 성능. 그래프가 복잡하다는 이유로 우수 판정 금지.

## 열린 결정(사용자)
| # | 결정 | 기본안 |
|---|---|---|
| D1 | RG 활성화 | 활성화 권장 |
| D2 | MIMIC hosp `diagnoses_icd`·`d_icd_diagnoses` 다운로드(EXP-02 전제) | EXP-01 끝난 뒤 |
| D3 | MIMIC-IV-Ext-DiReCT 신청(EXP-03) | 보류 |
| D4 | RL 라이브러리 설치(EXP-05) | 보류 |
| D5 | 커밋 여부 | 사용자 지시 시 |
