# 메인 AI 실험 공통 규칙(EXP-01 ~ 06)

## 1. 데이터 분할

### DDXPlus
| 이름 | 정의 | 용도 | 사용 이력 |
|---|---|---|---|
| TRAIN16 | train 파일 중 STEP16B 규칙 `int(sha256(row_index\|AGE\|SEX\|PATHOLOGY\|EVIDENCES)[:8],16) % 10 >= 2` | 학습·우도표 | STEP16B 학습에 사용 |
| SELECT | STEP16B holdout 중 `int(sha256("EXP01\|"+row_index)[:8],16) % 2 == 0` | 개발·모델 선택(반복 허용) | holdout 전체가 STEP16B 평가에 1회 사용됨(새 모델 선택에는 미사용) |
| FINAL | 위 holdout 의 나머지 절반 | 실험당 최종 1회 | 동일 |
| 공식 validate | `release_validate_patients` | **사용 안 함** | STEP14·15·16A 반복 사용 **[사실: PROVENANCE.md]** |
| 공식 test | `release_test_patients` | **사용 안 함**(사용자 규칙 2026-09-21: 존재 확인만) | STEP13B 1회 개봉 **[사실: handoff §2]** |

- DDXPlus 행은 합성 환자 1명 = 1행, 환자 ID 없음 → 행 단위 분할. 단 동일 프로필 중복이 분할을 넘는 비율을 매 실험 보고.
- FINAL 은 실험별 1회. 결과를 본 뒤 설정을 바꾸면 EXPLORATORY 로 별도 기록, 공식 판정 변경 금지.
- Baseline A(STEP16B 모델)는 TRAIN16 으로 학습됐으므로 TRAIN16 에서 평가하지 않는다.

### MIMIC
- **환자(subject_id) 단위 분할**. 같은 환자의 모든 stay·입원·검사·판독은 같은 분할.
- 시간 기준 분할을 병행 보고(anchor_year_group 기준; 날짜 이동(date shift) 때문에 절대 날짜 비교 금지 **[문헌: MIMIC-IV 문서]**).
- 판단 시점 t 의 입력 = `storetime ≤ t` (lab·판독), ED 는 `intime ≤ t ≤ outtime` 범위 기록만.
- `~/<restricted>/` 봉인 산출물은 열지 않는다(사용자 규칙).

## 2. 누출 방지 체크리스트(실험 manifest 에 그대로 복사해 체크)

- [ ] 평가 분할 행이 학습·우도표·사전(어휘) 구축에 쓰이지 않았다(행 인덱스 SHA 대조)
- [ ] DDXPlus `release_conditions.json` 을 모델 입력·질환 그래프로 쓰지 않았다(쓴 팔은 ORACLE 로 표시)
- [ ] `DIFFERENTIAL_DIAGNOSIS`·PATHOLOGY 를 질문 선택·점수 입력에 쓰지 않았다
- [ ] severity 는 평가 메타·비용 행렬로만 사용했고, 그 사실을 보고서에 적었다
- [ ] MIMIC: 판단 시점 이후 storetime 기록 0건(자동 검사기 + 변이 테스트)
- [ ] MIMIC: 진단명 문자열이 입력 텍스트에 남지 않았다(마스킹 검사)
- [ ] MIMIC: 검사 시행 여부를 특징으로 썼다면 선택 편향 분석을 함께 보고했다
- [ ] 미시행 검사의 가상 결과를 정답으로 쓰지 않았다
- [ ] 합성(DDXPlus) 성능을 임상 성능으로 표현하지 않았다
- [ ] FINAL 사용 횟수 = 1(로그로 확인)
- [ ] 검사기는 정답 세트(알려진 위반 주입)로 오판 0 확인 후 SHA 고정했다

## 3. 공통 지표

EXP-01 `exp01_predesign.md` §5 를 기준 정의로 사용. 공통 필수 보고 항목:
후보 재현율@5·@8, Top-1/3/5, 중요 후보 누락률(DDXPlus severity ≤ 2 = 17질환), 질문 수, 탐색 노드 수, 사례당 ms(p50·p95), 잘못된 분기 종료율, (확률 모델만) ECE·Brier.
통계: 분석 단위 = 사례(DDXPlus) / 환자(MIMIC), paired bootstrap 95% CI, 사전 지정 비교에 Holm 보정, 소표본 하위군(n < 100)은 결론 보류.

## 4. 재현성

- 실험마다 `config.yaml`(templates/experiment_config.yaml) + 입력 파일 SHA256 + 코드 SHA256 + git HEAD 기록.
- seed 고정, 여러 seed 면 평균±std(최고값 단독 보고 금지).
- 출력은 실험 폴더 `outputs/<run_id>/` 에 새로 만들고 덮어쓰지 않는다. 실패 run 도 삭제하지 않는다.
- 2분 이상 실행은 `wait_for_resources.sh --check` → `nohup` + `ram_guard.sh 90`(RAM 15 GB, 90% 상한).
- Python = `~/ai_env/bin/python`(3.12). 테스트 = unittest(pytest 미설치·설치 금지).
- WSL `/` 는 물리적으로 C: 드라이브 → `df /` 의 여유(714 GB)가 아니라 C: 여유(172 GB, 2026-10-26)가 실제 상한.
- 실행한 세션이 스스로 VERIFIED 를 선언하지 않는다 → `rg-verify`(독립 verifier).

## 5. 결과 기록

`templates/result_record.md` 를 실험 폴더에 복사해 채운다. 사실·문헌·가설·미검증 제안을 구분해 쓴다.
