# STEP28.8 → STEP29 인수인계(연구용)

- 검색기 진입점: `scripts/policies.py` `PolicyEngine().run_all(text)["P5"]`(구문 단위, 출력 필드는 STEP28.7 `docs/step29_interface.md` 와 같고 `held_*`·`ko_evidence` 추가).
- 단일 경로(P5만): `scripts/benchmark_runtime.py` 의 `p5()` 참고. CPU·오프라인·LLM 없음.
- 검사기: `scripts/evaluator.py` v3(SHA 는 `outputs/evaluator_validation.json`). 다음 버전은 '토할 것 같다 → vomiting' 탐지를 **평가 전에** 추가하고 정답 세트로 다시 검증.
- 덜 노출 보조 Gold: STEP21 pilot_gold 중 REGRESSION168 밖 106(이번에 처음 정책 평가에 사용 → 이제 노출됨). 새 독립 평가 자료는 없음.
- 알려진 결함·진입 조건: `docs/step29_readiness.md`.
- 금지 유지: LLM·다운로드 사전 승인, MDRKOR, 제품·PatientState·49질환 모델 변경, 사후 판정 변경, 격리 FAIL 양성 사용, commit/push 는 지시 시.
