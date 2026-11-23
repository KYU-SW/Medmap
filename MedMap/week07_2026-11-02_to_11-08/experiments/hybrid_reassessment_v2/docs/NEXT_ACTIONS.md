# 다음 작업

## 가장 중요한 하나
새 CC BY 문장 표본으로 수정 후 파이프라인 1회 확인(2차). 2026-11-05 Europe PMC 503 으로 미완료.
절차: `eval/sample_public.py` 실행(코드 동결·표본 추출, 이전 문서 제외) → 파이프라인 실행 전 `eval/gold_public.json` 새로 고정(1차는 `_run1` 보관) → `eval/run_public.py` 1회 → 결과를 `outputs/public_linking_results_run2.json` 으로 보관 → 추가 조정 없이 `VALIDATION_REPORT.md` 갱신.
주의: `sample_public.py` 는 `eval/public_sentences.jsonl`·`FREEZE.json` 을 덮어씀. 1차 사본은 `_run1`.

## 그다음 후보
1. 임상 확률을 기록에서 읽거나 의사 입력으로 받는 방식 설계(대부분의 방향 판단이 여기에 의존)
2. 문서 단위 약어·문장 간 맥락 처리
3. ER-Reason 승인 확인 후 평가 계획 진행
4. 로컬 LLM 후보 비교(다운로드는 승인 후)

## LLM 이 필요해 보이는 구간
표현 변형, 문장 간 맥락, 문서 내 약어, 임상 확률 추출. 추가 시 인용 일치, 잘못된 방향, 학습 자료 오염을 검증해야 한다.

## 보류 유지
EXP-MAI-003, EXP-02 TEST, EXP-01 FINAL 재실행 안 함.
