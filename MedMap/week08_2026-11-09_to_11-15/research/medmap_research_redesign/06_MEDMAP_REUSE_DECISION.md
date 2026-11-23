# 06. 기존 MedMap 기능 유지·재사용 판단 (2026-11-10)

설계 판단만 기록. 코드 삭제·변경 없음.

| 기능 | 위치 | 분류 | 사유 |
|---|---|---|---|
| 검사 결과 공개 시각 관리·미래정보 차단(P-AVAIL) | exp03 `reassess.py`, exp02 `mimic_adapter.py` | KEEP | 세 설계 모두의 입력 계층. 2026년 문헌 기준 필수 관행 |
| 판독 정정 이력·정정 귀속 | v5-2A.2 `hybrid522` | KEEP | 문헌 공백(정정 영향 정량화)에 직접 대응 |
| 검사 정정 가상 비교 | v5-2A.2 counterfactual | KEEP | 설계 3의 섭동 연산자 S로 그대로 사용 |
| 검사 기록 중복 처리(근거 그룹화) | v5-2A.1 | KEEP | 설계 1·3의 중복군 정의 |
| 원본 출처 추적·판단 변화 원인 추적 | v3~v5 | REUSE_AS_COMPONENT | 기여 증거 제시(설명)에 사용. 논문 기여 아님 |
| MIMIC 어댑터·코호트 추출·봉인 출력 규칙 | exp02 | KEEP | 데이터 계층 전체 재사용 |
| 판독문 PE 분류기 v3b | exp02 `pe_rules_v3.py` | REUSE_AS_COMPONENT | 영상 범주 특징 1종. 알려진 오류 2건 존재 |
| 결함 주입·뮤테이션 검사 틀 | exp03, v5 tests | KEEP | 재생 엔진 정합성 보증 |
| 진단 에피소드 관리 | v4~v5 | REUSE_AS_COMPONENT | 내원 단위 분리에만 사용 |
| 의사 진단과 자동 추출 후보 구분 | v5 | REUSE_AS_COMPONENT | ED 진단 = 조건 변수로 역할 단순화 |
| 4값 논리·AND/OR/NOT/K-of-N 조건 평가 | v4 Reasoner | RESEARCH_BASELINE | PE 한정 규칙 기준선. 일반 방법과 비교용 |
| 진단별 조건 충족 평가(PE 카탈로그) | v4~v5-2B | RESEARCH_BASELINE | 동일 |
| 의료 지식그래프(질환 그래프 A) | exp01b, v4 | DEFER | 자체 결과 Graph=Flat. 정확도 기여 미입증 |
| 환자 증거그래프(B) | v4 | DEFER | 평면 사건 표로 충분. 추적 표현용으로만 보존 |
| 여러 질병 근거 비교(v5-2A) | v5-2A | DEFER | 활성 규칙 0, 정답 없음 |
| 연구용 규칙 비교(Shadow) 엔진 | v5-2B-Research | DEFER | 전문의 답변 전제. 답변 확보 시 재개 |
| ACS·심낭염 규칙 확장 | v5-0~v5-1 | REPLACE_CANDIDATE | 자료 유도 조건부 분포(DxShift)로 대체 검토 |
| 외부 지식 검증기(HPO·HSDN·UMLS 경로) | step9~13B | REMOVE_PROPOSAL | STEP13B AUROC 0.478, 도달 가능 한도 23% |
| 외부 프로필 질문 선택기 | step15~16A | REMOVE_PROPOSAL | STEP16A NO_GO 확정 |
| 내부 정보이득 다음 질문 엔진 | step16b, 제품 스택 | KEEP(제품 축) | 연구 방향과 별개. 제품 문진 기능으로 유지 |
| STT·문진 매퍼·웹 UI | stt, intake_mapper, medmap-web | KEEP(제품 축) | 이번 연구 재설계 범위 밖 |

## 요약

- 유지 핵심: 재생 엔진의 **증거 위생 3기능**(가용 시각, 정정, 중복) + MIMIC 데이터 계층 + 검사 틀.
- 기준선 전환: 규칙·4값 추론은 PE 한정 비교 대상.
- 보류: 그래프 2종, 다질환 규칙, Shadow 엔진.
- 대체 검토: 질병별 규칙 확장 → 자료 유도 조건부 분포.
- 새로 필요한 것: ICD→CCSR 범주화, 변경 라벨 구축, 조건부 분포 추정·수축, 기준선 모델, 퇴원요약 추출기, 사전등록 문서.
- 처음부터 다시 만들 필요 없는 것: 시간 재생, 정정 처리, 봉인 입출력, 테스트 틀.
