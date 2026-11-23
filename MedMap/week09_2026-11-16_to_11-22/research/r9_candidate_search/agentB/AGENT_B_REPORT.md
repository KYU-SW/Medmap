# AGENT_B_REPORT — 직접 경쟁 연구·시스템 조사

- 작성: 2026-11-21, Agent B
- 범위: PA~PF 6개 영역. 유료 API, 저자 연락, git 사용 없음. 웹 검색과 공개 페이지만 사용했다.
- 산출물
  - `agentB/PRIOR_ART_MATRIX.csv` (41행, 18열, UTF-8 BOM)
  - `agentB/PRIOR_ART_REVIEW.md` (영역별 이미 해결된 것, 남은 것, 조합 해결 가능 여부)
  - `agentB/AGENT_B_REPORT.md` (이 문서)

## 결론
| 영역 | 선점 | 가장 강한 기존 시스템 | 조합 해결 | MedMap 차별 여지 |
|---|---|---|---|---|
| PA | 높음 | Singh e-trigger(JCO 2015 RCT), Northwestern NLP 폐쇄 루프(NEJM Catalyst 2022) | 가능 | 인지 시점 감사. 독립 정답 확보 어려움 |
| PB | 중~높음 | GuidelineForge(NeurIPS 2026 워크숍) | 대부분 가능 | 손실 분류와 MIMIC 공개 재현. R4·R8 정답 부재 반복 위험 |
| PC | 중간 | EHRCon(NeurIPS 2024 D&B), TBU(NeurIPS 2026 워크숍) | 조건부 가능 | **가장 큼.** 시간 경과로 오래된 정보가 된 경우를 구조화 시계열로 판정하는 수학 정답 |
| PD | 높음 | Liu·Wright VUMC XAI(JAMIA 2024) | 가능(데이터 없음) | 거의 없음. 경고 로그 미보유 |
| PE | 높음 | SPADE + Safer Dx e-trigger(JAMA IM 2024) | 가능 | 작음. 불확실성 보존은 2026 벤치마크와 겹침 |
| PF | 높음(품질 평가) / 중간(사건 기반 누락 감사) | Williams JAMA IM 2025, Hartman JAMA Netw Open 2024 | 조건부 가능 | 퇴원 요약 대기 검사 누락의 자동·대규모 감사(Walz 2011 수작업의 확장) |

## 우선순위 제안
1. **PC**를 가장 먼저 검토한다. 기존 연구는 단일 시점 불일치(EHRCon)와 노트 간 모순(TBU)이다. 시점별 사실 여부(언제부터 틀렸나) 판정은 검색 범위에서 찾지 못했다.
2. **PF**는 정답을 자동 생성할 수 있어 차선이다. 다만 신규성은 규모와 자동화 수준에 그친다.

## 주의·한계
- 본문을 직접 읽은 논문은 0건이다. 전부 초록, 공식 페이지, 검색 요약 수준이다.
- 2026년 워크숍·프리프린트(PB1·PB3·PB4, PC8·PC9, PE4)는 정답 작성자가 미기재이거나 확인이 필요하다.
- 서지 정보를 다시 확인해야 하는 항목
  - PB6 GLIF3, PD6 McCoy 2012: 기억 기반으로 적었다.
  - PB7 CPGPrompt, PC9 EHR-Inspector, PE4: 저자 확인 필요.
  - PF7 Walz: 게재지 확인 필요.
  - TIMER: 게재처 확인 필요.
- 확인하지 못한 항목
  - "Dalal 판독 후속 권고 추적 NLP" 논문은 찾지 못했다. 대신 Dalal 2014 TPAD RCT를 수록했다.
  - Kaiser 경고 최적화 사례는 특정 논문을 찾지 못했다(확인 필요).
  - Xie & Du 2604.17340의 정체는 지침 간 충돌 SAT 검증 논문이다(AAAI-26 Bridge). 지침→규칙 의미 손실을 직접 다룬 논문은 아니다.
- 검색 범위가 제한적이라 "기존 연구 없음"이라고 단정하지 않는다. 남은 여지는 모두 "검색 범위에서 찾지 못함" 수준이다.
