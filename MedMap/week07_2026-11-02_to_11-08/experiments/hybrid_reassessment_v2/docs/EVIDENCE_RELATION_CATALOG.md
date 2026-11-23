# 근거 관계 카탈로그 (`knowledge/evidence_relations.json`, pe-pilot-1)

세션이 공개 원문에서 문구를 확인했다. **의료 전문가 검토 없음.** 출처: [2019 ESC 지침](https://academic.oup.com/eurheartj/article/41/4/543/5556136)(DOI 10.1093/eurheartj/ehz405), [Gallo 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC7873787)(CC BY-NC, 지침 요약 논문).

| ID | 소견 | 관계 | 맥락별 방향 | 근거 위치 |
|---|---|---|---|---|
| PE-CTPA-POSITIVE | 판독이 PE 명시 | SUPPORTS | 분절 이상 + 중간·높은 확률 = SUPPORT, 아분절·낮은 확률 = UNCERTAIN, 수준·확률 없음 = INSUFFICIENT | ESC Fig.5 각주 d, Gallo |
| PE-CTPA-NEGATIVE | 정상 CTPA | WEAKENS | 낮음·중간 = WEAKEN, 높음 = UNCERTAIN, 없음 = INSUFFICIENT | Gallo(I, A), ESC §4.5 |
| PE-DDIMER-NORMAL | 정상 D-dimer | WEAKENS | 낮음·중간 = WEAKEN, 높음 = NOT_APPLICABLE | ESC §4.4, Gallo |
| PE-DDIMER-ELEVATED | 상승 D-dimer | EVALUATES | NO_CLEAR_EFFECT(지지 아님) | ESC §4.4 |
| PE-PERFUSION-NORMAL | 정상 관류 스캔 | WEAKENS | WEAKEN | ESC §4.6 |
| PE-PROXIMAL-DVT | 초음파 근위부 DVT | SUPPORTS | PE 의심 시 SUPPORT(치료 근거 수준 문구) | ESC §4.10 |
| PE-FILLING-DEFECT | CT 충만 결손만 기술 | UNCERTAIN_RELATIONSHIP | UNCERTAIN | ESC §4.7(고전적 혈관조영 문구, 범위 다름) |
| PE-HISTORY-VTE | 과거 PE·DVT | ASSOCIATED_WITH | INSUFFICIENT | ESC §3.2, §4.2 |

## 근거가 없어 넣지 않은 것
- 증상·활력징후(호흡곤란, 빈맥, 객혈 등)의 PE 방향: 그래프 연관만 표시.
- 심낭염·심근염·결핵의 방향 관계. 이 가설에는 ABSTAIN.
- 약화가 다른 진단을 지지한다는 관계.
- 민감도·확률 수치.

## 근거 한계
- CTPA 충만 결손의 진단 기준은 2차 자료에서만 봤고 주 출처 원문을 확인하지 못해 UNCERTAIN 으로 둠.
- ESC 권고표는 이미지라 표 문구 대신 본문·각주·요약 논문을 사용.
- 임상 확률(pretest)이 필수 맥락이며 문장에서 자동 추출하지 않는다.
- NICE NG158 은 접근 실패(403)로 쓰지 않음.
