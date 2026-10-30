# 3주차 (2026-10-05 ~ 10-11) — MIMIC 가용성 검증 · 증상 개념 연결 · 화면 디자인

## 요약
- **MIMIC-IV 가용성·신호 검증(NBI-B0~B1S)**: 흉통 감별에 필요한 정보가 실제 응급실 기록에 언제·얼마나 있는지 봤습니다. Troponin 1종에서 ACS–폐색전증 분리 신호(ΔAUROC +0.08)를 찾았지만, 상당 부분이 심근경색 진단 기준과 얽힌 효과였습니다(B1S).
- **증상 개념 연결(STEP20~29.1)**: DDXPlus 증상을 HPO·SNOMED·UMLS 개념에 연결하고, 한국어 환자 표현을 개념으로 바꾸는 단계를 차례로 시험했습니다. 대부분 부분 개선 또는 회귀였고, 실패 원인(검사기 결함, 문장 부호 없는 입력, 가족 증상 등)을 기록했습니다.
- **화면 디자인**: 웹 재디자인 정적 시안, 실제 의사 화면 디자인 적용(브랜치, 4주차에 병합).

## 날짜별
| 날짜 | 한 일 | 결과 |
|---|---|---|
| 10-04~05 | NBI-B0a(활력·리듬·ECG 가용성) · B0c(검사 수치) · B0d(영상 판독) 1회씩 실행 | 세 실험 모두 COMPLETE, 독립 검증 VERIFIED. ACS–폐색전증: Troponin AVAILABLE(70~80 % 구간), D-dimer AVAILABLE(0~10 %), 흉부 CTA AVAILABLE(10~20 %) |
| 10-06 | **NBI-B1**(EXP-SN-NBI-003): 측정된 환자 subset에서 Troponin·D-dimer 추가 시 분리도 | Troponin 51003: 기준 모델 0.78 → 0.86, **ΔAUROC +0.08 (95 % CI 0.06–0.11)**. D-dimer는 단위 문제·표본 부족으로 평가 불가 |
| 10-06 | **NBI-B1S**(EXP-SN-NBI-004): 라벨 의존 민감도 | MI형 ACS +0.10 vs 불안정 협심증형 +0.02 → **SIGNAL_MOSTLY_REFERENCE_DEPENDENT**. 측정 여부 자체가 질환과 연관(AUROC 0.64) |
| 10-07~08 | 성과전시회 판넬 · 웹 재디자인 정적 시안(의사·인계·포스터) | 시안만(앱 미적용) |
| 10-08 | 의사 화면 디자인 실제 적용(브랜치) · **STEP20** 증상→HPO/SNOMED/UMLS 전수 매핑 감사 · **STEP21** 한국어 표현 개념 연결 | 프런트 테스트 293/293 · STEP20 **CONDITIONAL**(사용 가능 93/110) · STEP21 **NO_GO** |
| 10-08~10 | **STEP22** 선형 정규화기 · **STEP23** 표현 확장 · **STEP24/24-v2** KoELECTRA 하이브리드 · **STEP25** 외부 한국어 의료 데이터 · **STEP26** 범위 밖(OOD) 처리 | STEP22 NO_GO(Top-1 35.8 %) → STEP23 Top-1 88.1 %(표현 276→1,119) · STEP24 학습 붕괴 후 확장 grid(프로토콜 이탈 기록) · STEP25 공개 3종 확보, 개념 정답 0 · STEP26 거부 정책 유용(약한 대리 지표) |
| 10-10~11 | **STEP27** 안전 라우팅 · **STEP28** 개방형 어휘 확장 · **STEP28.5** 한·영 병렬 검색 · **STEP28.6** 격리 LLM 보조 연결 | STEP27 PARTIAL_IMPROVEMENT · STEP28 PARTIAL_FEASIBILITY · STEP28.5 BLOCKED · STEP28.6 LINKING_FEASIBLE(SILVER 등급) |
| 10-11 | **STEP28.7** 매핑 품질 · **STEP28.8** 한국어 검색 수리 · **STEP29** 임상 NLU · **STEP29.1** 문맥 NLU 수리 | 28.7 REGRESSION(검사기 결함) · 28.8 PARTIAL_IMPROVEMENT · 29 REGRESSION · 29.1 REGRESSION(단독 가드가 정답 24건 차단) |

## 폴더
- `research/nbi/` — B0c·B0d·B1·B1S 사전등록
- `experiments/nbi_b0`, `nbi_b1`, `nbi_b1s` — 실행 스크립트·테스트. **MIMIC-IV 원자료·파생 출력·사전 매핑 파일은 PhysioNet 사용 조건 때문에 넣지 않았습니다.** 결과는 위 표의 구간·집계값만 공개합니다.
- `reports/` — STEP20~29.1 보고서(`실험폴더__보고서명`). 핵심: `step20_symptom_ontology_audit__symptom_mapping_audit_report.md`, `step23_korean_expression_expansion__korean_expression_expansion_report.md`, `step28_8_korean_retrieval_repair__step28_8_report.md`
- `experiments/stepNN_*` — 각 단계 스크립트·테스트·실행 스크립트. 데이터·모델·색인·출력은 제외(UMLS·SNOMED 파생물, 격리 LLM이 만든 SILVER 대응표 포함)
- `qa_screenshots/` — 의사 화면 디자인 적용(`doctorui_*`), 웹 재디자인 시안(`webv3_mock_*`)

## 아직 검증되지 않은 것
- NBI 결과는 MIMIC-IV 후향 자료에서 측정된 환자만 본 조건부 분리도입니다. 임상 성능이 아니며, 측정 선택 편향이 확인됐습니다.
- 한국어 표현 연결은 합성 문장과 자체 작성 표현으로만 평가했습니다. 실제 환자 발화 검증은 없습니다.
