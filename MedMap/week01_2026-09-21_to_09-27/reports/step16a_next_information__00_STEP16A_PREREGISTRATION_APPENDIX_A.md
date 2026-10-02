# STEP16A 사전등록 부록 A (본문 SHA 보존을 위해 분리, 2026-09-22 VALIDATION 개봉 전)

## 부록 A (2026-09-22, VALIDATION 개봉 전 기록) — 재현성 결함 수정
- `make_view`의 split 키가 `abs(hash(split))%65536`로 되어 있어 Python 해시 무작위화(PYTHONHASHSEED)로 프로세스마다 달랐다(실측 17719 vs 30500). VALIDATION 개봉 전 `SPLIT_ID={"train":1,"validate":2}` 고정 상수로 교체. 규칙(RNG key=(split,seed,patient_index))은 불변.
- 영향: 이미 저장된 `model_k3/5/10.pkl`·`ig_table_train.npz`는 그대로 사용(TRAIN 뷰 자체는 동일 프로세스 내 결정적이었음). 단 TRAIN 뷰를 바이트 단위로 재생성하는 것은 불가 → 재현 시 저장된 모델 sha(e6799dc8/7f1c997c/5bd4e2b6)로 검증.
- 사전등록 본문·rules.json은 수정하지 않음(이 부록만 추가). 부록 추가 후 MD SHA는 변경되므로 RUN1 게이트는 `00_preregistration_sha256.json`의 JSON SHA(e260afd5…)와 본 부록 포함 MD의 새 SHA를 함께 기록한다.
