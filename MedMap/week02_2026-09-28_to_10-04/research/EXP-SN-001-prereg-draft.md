# EXP-SN-001 사전등록 초안 rev2 — 사전 정의된 흉통 감별 부분집합에서의 Diagnostic Safety Net 최소 검증

- rev0(2026-10-02 01:27) → RG gate **BLOCK** → rev1 `35cd445`(방법론 수정) → **rev2 2026-10-02(문헌 조사 반영, 이 문서)**
- 상태: **RG 재심사 전**. 사용자 확인 후에만 재심사한다.
- 금지(사용자 다음 승인 전): 질환 사실 작성 · DDXPlus 질환→소견 매핑 · K 계산 · FIT/TUNE/EVAL 실행 · 평가 행 열람 · 임계 산출 · 결과 확인 · Doctor 경고 UI · 49질환 확장 · 임상 성능 주장
- 근거 문서: `EXP-SN-001-literature-review.md`(출처 G1–G4·S1–S10, 라이선스) · `EXP-SN-001-knowledge-protocol.md`(rev2) · `2026-10-02-step13b-failure-analysis.md`

## 0. 연구 목적과 주장 한계
- 질문: 의사의 현재 진단(WD)이 환자 소견을 충분히 설명하지 못하는 경우를, 독립적이고 출처에 근거한 질환 지식이 **모델 확신도 기준선보다 추가로** 재검토 대상으로 구별하는가. 그리고 맞는 진단에는 불필요한 경고를 최소화하는가.
- 1순위로 평가하는 것은 "대안 진단을 보여주는 능력"이 아니라 **"경고해야 할 때와 조용히 있어야 할 때를 구별하는 능력"**이다. 대안 1–3개 제시와 다음 정보 추천은 보조로 둔다.
- 범위 표현: **"predefined chest-pain differential subset"**(사전 정의된 흉통 감별 부분집합). "흉통 전체 안전망"이라고 표현하지 않는다.
- 문헌 조사에서 나온 사전 기대(정직한 공개): 진료지침들은 병력만으로 ACS를 배제할 수 없고 검사가 필요하다고 말한다(G1 §1.4.2·§2.3, G2 1.2.2.5, G3 보충 p6). 확인된 후보쌍 가운데 **병력만으로 완전히 구별되는 쌍은 없다**(literature §3). 따라서 `NOT_REACHABLE`이나 높은 abstention 비율은 그럴 수 있는 정상적인 결과이고, 실패를 숨길 이유가 아니다.

## 1. 공개 사항 (사후 편향 위험)
- 후보군과 rev0의 7개 쌍은 STEP13B TEST·VALIDATION 오답 분석과 STEP16B holdout 혼동을 **본 뒤** 떠올린 것이다. rev2는 rev0 쌍을 버리고, **진료지침 근거로만** 다시 고른다(§3.3). 다만 질환군 후보의 출발점이 혼동 분석이었다는 사실은 그대로 공개한다.
- STEP17A DEV는 과거 학습(STEP16B·17A)과 TRAIN 통계(STEP14)에 쓰였다. 평가 결과에 노출된 적은 없다.
- 문헌 조사는 AI 에이전트가 지침 원문을 읽는 방식으로 했다. 일부는 정식판이 아닌 사본이었다(literature §0).

## 2. 데이터와 split (rev1 그대로)
- 사용 데이터: STEP17A DEV(656,593)만. VALIDATION·TEST·STEP16B_HOLDOUT·STEP17A_HOLDOUT 접근 0.
- `key_sn = sha256("safetynet01|"+key16)`, `int(key_sn[:8],16) % 10`: 0–5 → DEV_FIT, 6–7 → DEV_TUNE, 8–9 → DEV_EVAL(잠금, 1회)
- split 직후, 점수 계산 전에 기록할 것: 행수·SHA, 질환별 n(라벨만), FIT↔EVAL 동일 프로필 비율
- `DIFFERENTIAL_DIAGNOSIS` 열과 `release_conditions.json`의 증상 정의는 어디에도 쓰지 않는다.

## 3. 범위·사례·abstention

### 3.1 두 층 범위 (C1·C6, PROPOSED)
- **선정 규칙**(결과를 보지 않고 적용): 질환 d를 closed set에 넣는 조건은 (i) DDXPlus 49질환에 있고, (ii) G1 Table 4·9 또는 §4, 혹은 G3 Table S5에 급성 흉통 원인이나 ACS 흉내 질환으로 나오며, (iii) 후보쌍(§3.3) 하나 이상에 속하는 것이다.
- **A. Closed validation set(제안)**: 불안정형 협심증, NSTEMI/STEMI 의심, 안정형 협심증, PE, 심낭염, GERD, 자연 기흉, 공황 발작
  - 출처상 위치: G1 Table 9·§4 / G1 §2.3.1 / S1 / S2·G1 Table 3 / G1 §4.3.1·S4b / G1 Table 9 / G1 §4.3.2
- **심근염**: G1 §4가 전격성 심근염을 "potentially life-threatening"으로 들고, S2 §5.11이 ACS의 주요 감별로 든다. DDXPlus에도 있다. closed set에 넣을지는 **CONFIRM_NEEDED**(사용자 결정)이다. 넣지 않으면 B층으로 간다.
- **B. OUT_OF_SCOPE_HIGH_RISK(OOS)**: 출처가 생명 위협이라고 한 흉통 원인 가운데 closed set 밖의 것
  - (B1) **모델 라벨 공간에 없음**: 급성 대동맥 증후군·대동맥 박리(G1·S8), 겸상적혈구 흉부 위기(G1 §4). 모델이 후보로 낼 수 없고 KB도 다룰 수 없다.
  - (B2) **모델 공간에 있으나 closed set 밖**: 식도 파열(Boerhaave, G1 §2.1·S9), (심근염을 넣지 않을 경우) 심근염. 급성 폐부종과 급성 심부전은 G3 Table S5에서 mimic이지만 "life-threatening" 표기 근거는 S10 열람 제한으로 **확인 필요**다.
  - 긴장성 기흉: G1에서 "immediately life-threatening"이다. DDXPlus의 "Spontaneous pneumothorax"는 긴장성 여부를 구별하지 않으므로, 이 한계를 표기한다.
- B층은 실험 지식으로 비교하지 않는다. 다만 평가기와 앞으로의 제품은 "현재 지식 범위 밖"이라는 것을 반드시 인지해야 한다(§3.5).

### 3.2 사례 구성 (rev1 그대로)
- Primary 모집단: DEV_EVAL 환자 중 정답이 closed set에 있고 §3.3의 확정 쌍에 짝이 있는 환자. 환자당 correct 1건 + wrong 1건이고, 두 사례는 같은 view를 쓴다.
- wrong WD는 **사전 고정 쌍의 짝만** 쓴다. 짝이 여럿이면 `sha256("sn01wd|"+key16)` mod 짝 수로 고른다(코드 오름차순).
- 모델 top2/3에서 고른 wrong WD는 primary에서 금지하고, exploratory 층으로만 둔다.
- 정보 수준: primary = k3 start view(seed 42). 보조 = initial / +1 IG / +3 IG / full.

### 3.3 쌍 선정 절차 (C2)
1. 후보쌍은 literature §3 표만 쓴다(출처가 감별을 명시한 쌍). 모델 혼동과 STEP13B 결과는 쓰지 않는다.
2. 쌍마다 기록할 필드: `pair_id, disease_A, disease_B, source, clinical_reason_for_pair, history_discriminable(yes/partial/no/UNKNOWN), biomarker_or_test_dependent, research_scope_status, review_status=unreviewed`
3. **Primary 쌍 조건**: 양쪽 질환이 closed set에 있고, `history_discriminable ∈ {partial}`이다(yes는 현재 0개). `no`는 primary에서 제외하고 **test-dependent 층**으로 보고한다. UNKNOWN은 제외한다.
4. 제안 primary 쌍: P1(ACS–GERD), P2(ACS–PE), P3(ACS–심낭염), P6(안정형–불안정형/ACS)
   - P4(ACS–기흉)와 P8(심낭염–PE)은 history_discriminable이 UNKNOWN이라 출처가 확인될 때까지 제외한다.
   - P5(ACS–공황)는 no/partial이고, 출처가 공황을 "diagnosis of exclusion"이라고 하므로 test-dependent 층에 둔다(**CONFIRM_NEEDED**).
5. 자연 기흉은 closed set에 있지만 현재 primary 쌍이 없다(P4가 UNKNOWN). 그래서 primary 모집단에 들어가지 않으며, 쌍의 출처가 확인되면 추가한다. 공황은 test-dependent 층에만 들어간다.
6. 여기서 "ACS"는 DDXPlus의 불안정형 협심증과 NSTEMI/STEMI 의심을 뜻한다(G2·G3의 ACS 정의). 짝 방향은 양방향이다.
7. 쌍 목록은 지식 작성 전(K1)에 SHA로 동결한다. 동결 뒤에는 바꾸지 않는다.

### 3.4 중증도 정책 (C3)
- 새 HIGH/LOW 등급을 만들지 않는다. **severity_source** = G1 §4(e387–388)
- **severity_definition**: G1의 원문 범주 "life-threatening (emergency)" 대 "nonemergency"
- **classification_rule**: 질환이 G1 §4 또는 §2.1·§2.2의 life-threatening 목록에 있으면 `LT`, G1이 nonemergency로 분류하면 `NE`, 어느 쪽으로도 확인되지 않으면 `UNCLASSIFIED`. 출처 문장 위치를 함께 기록한다.
  - ACS는 G1에 따라 LT다. 안정형 협심증·GERD·공황의 분류 문장 위치는 K3에서 확인하고, 확인되지 않으면 UNCLASSIFIED로 둔다.
- 방향 층: **LT 누락**(정답 LT, WD가 LT 아님) / 과분류 / 동급. G4는 LT 누락 층에서 판정한다.
- G1의 ACS 저·중·고위험 3단계는 심전도·트로포닌·CDP 기반이라 병력만의 실험에서는 쓰지 않는다.

### 3.5 Abstention 의미 (C5·C6, 새로 추가)
- 평가기 출력: `consistent`(조용히 있음) / `re-review`(재검토) / `abstain_out_of_scope` / `abstain_test_dependent`
  - `abstain_out_of_scope`: 모델 Alt(49질환 상위 5) 안에 B2 층 OOS 질환이 있는 경우. 이때 "현재 지식 범위로 안전 판정 불가"를 낸다. B1 층(모델 공간 밖)은 사례별로 감지할 수 없으므로, **모든 사례에 고정 범위 고지**(예: 대동맥 박리는 이 검사 범위 밖)를 붙이는 것으로 처리한다.
  - `abstain_test_dependent`: WD와 K가 가장 강하게 지목한 대안의 쌍이 test-dependent 층(history_discriminable = no)인 경우. 의미는 "병력만으로 구별 불가, 검사 필요"이다. 정당한 출력이며 실패가 아니다.
- **채점 규칙(사전 고정)**:
  - primary에서 abstain은 경고하지 않은 것으로 센다(보수적이다. wrong 사례에서는 탐지 손실로, correct 사례에서는 오경보가 아닌 것으로 처리). B1에는 abstention이 없으므로 이 규칙은 S에 불리하게 작용하고, 성능을 부풀리지 않는다.
  - 보조: abstain을 경고로 센 결과, abstention 비율(correct·wrong 각각), abstention 유형별 분포
- 앞으로 제품 표현 후보(지금 구현하지 않음): "이 진단이 틀렸다"가 아니라 "현재 정보만으로 해당 고위험 원인을 충분히 배제할 수 없음"

## 4. 점수 정의 (rev1 그대로, 결과 보기 전 고정)
- **누수 방지**: 평가기는 정답이 closed set에 있다는 정보를 받지 않는다. Alt = 모델 49질환 사후확률 상위 5개에서 WD를 뺀 것이다. 재정규화하지 않는다.
- **기준선**: B0 = 1[모델 top1 ≠ WD]. B1 = 1 − P_model(WD), 49질환 기준
- **K**:
  - s(f,d) 정수표: 있음(+2/+1/−2/−1/+1) / 명시적 없음(−1/0/+1/0/−2) / 미관측 0. 열 순서는 strong / weak / conflicting / uncommon / important_negative
  - D(a,WD) = Σ_f[s(f,a) − s(f,WD)]
  - K = max(0, max_{a∈Alt∩KB} D(a,WD))
  - 지식이 비면 K = 0(포함, open-world)
- **결합**: S = 0.5·F_B1(B1) + 0.5·F_K(K). F는 DEV_TUNE 전체 사례 ECDF(midrank)로 동결한다. 사례마다 독립적으로 계산하고, 환자 안의 두 사례를 서로 비교하지 않는다.
- **PRE-SPECIFIED ARBITRARY FUSION**(정직한 표기):
  - 0.5/0.5는 근거로 도출한 가중치가 아니라 **튜닝하지 않으려고 고른 등가중**이다. 결과를 보기 전에 고정했으므로 confirmatory 비교에 쓸 수 있다.
  - 가중 0.25/0.75와 0.75/0.25는 exploratory 민감도로만 본다.
  - 대안안(재심사 때 검토 요청): primary를 "K를 추가했을 때의 증분"으로 정의하고, 결합 방식을 바꾸지 않은 채 sens_S − sens_B1로 유지한다.
- **임계**: 점수 ≥ t이면 경고. t = DEV_TUNE correct 사례의 경고율이 0.10 이하가 되는 최소값. 무작위 동점 분할 없음.

## 5. 임계 퇴화 기준 (rev1 그대로)
K의 서로 다른 값 ≥ 3, S의 서로 다른 값 ≥ 20, t < max, DEV_TUNE 실현 FPR ∈ [0.07, 0.10], 임계 동점 correct 사례 ≤ 3%. 하나라도 미달이면 EVAL을 열지 않고 중단한다. EVAL 실현 FPR ≤ 0.12.

## 6. 판정 G0–G4
| ID | 내용 | 시점 |
|---|---|---|
| G0 | reachable 비율 ≥ 0.40 그리고 퇴화 기준 충족. **reachable** = KB에 WD가 있고, KB에 있는 대안 a∈Alt가 1개 이상이며, view에서 관측된 소견 f 중 s(f,a) ≠ s(f,WD)인 f가 1개 이상인 사례. 분모 = DEV_TUNE primary wrong 사례 전체(abstain 포함), 분자 = reachable이면서 abstain이 아닌 사례 | DEV_TUNE |
| G1 | sens_S − sens_B1의 환자 단위 쌍대 bootstrap 95% CI 하한 > **δ = 0.02** | DEV_EVAL |
| G2 | 실현 FPR ≤ 0.12(S와 B1 각각) | DEV_EVAL |
| G3 | AUROC(S) − AUROC(B1)의 CI 하한 > −0.01 | DEV_EVAL |
| G4 | **LT 누락 층**에서 sens_S − sens_B1의 CI 하한 > −Δ_safe(§7) | DEV_EVAL |

- 성능(G1–G4)은 unreachable·abstain 사례를 포함한 **primary 전체**로 계산한다(제거 금지). reachable-only 결과는 진단용으로만 보고하고 판정에 쓰지 않는다.
- **최소 표본**(split 직후 라벨만으로 확인, 미달이면 평가 전 중단·보고): primary 전체 wrong 사례 1,000 이상. LT 누락 층은 n_min(§7) 이상이어야 하며, 미달이면 G4 판정 불가이므로 GO를 내지 않는다. 쌍 방향별·질환별·나이·성별·난이도 하위군은 n이 30 이상일 때만 수치를 보고하고, 미만이면 "결론 금지"로 표기한다.
- 통계: bootstrap 10,000회, seed 20261002, 재표집 단위 = 환자(두 사례를 함께), 임계·ECDF 고정. 판정은 G0–G4 동시 충족이다. 그 밖의 결과는 모두 보정 없는 기술 통계다.

## 6.1 보조 지표·자기참조 금지·ablation (rev1 유지)
- "미설명 소견 재현율"과 "충돌 소견 정밀도"는 기준이 K 자신이다. 그래서 **"K 내부 일관성(exploratory)"**으로 부르고 판정에서 뺀다. 독립 gold(출처에 근거한 별도 주석 또는 임상의 판독)가 생기기 전에는 정밀도라고 부르지 않는다.
- 대안 1–3 포함률(재검토 경고 사례만)은 무작위 기준선과 B1 순위 기준선을 함께 보고한다.
- K 대 B0: K의 임계를 B0의 DEV_TUNE 실현 FPR에 맞춰 기술 비교만 한다(판정 없음).
- Ablation(exploratory): K_data(역할 = DEV_FIT 경험 P(e|d)) · 모델 유래 hard negative 층 · test-dependent 층(P5 등) · open-set 층 · 정보 수준 · 결합 가중 0.25/0.75와 0.75/0.25 · DDXPlus severity 민감도
- Q6(다음 정보): WD와 대안으로 재정규화한 IG 대 현재 IG에서, 1문항 뒤 사후확률이 어떻게 움직이는지 본다. exploratory이며 제품 코드는 바꾸지 않는다.

## 7. C8 Δ_safe (제안 — 결과 전 고정, 최종 승인 CONFIRM_NEEDED)
- 근거 계산(데이터 없이 공식만 사용): 쌍대 민감도 차이의 95% CI 반폭은 약 1.96·√(d/n)이다(d = 쌍대 불일치율).
  - d = 0.10일 때: n = 300 → ±0.036, n = 1,000 → ±0.020, n = 2,000 → ±0.014
  - 참 차이가 0일 때 비열등을 80% 확률로 보이는 데 필요한 n ≈ 7.84·d/Δ²:
    - Δ = 0.01 → d 0.05/0.10/0.20에서 3,920 / 7,840 / 15,680
    - Δ = 0.02 → 980 / 1,960 / 3,920
    - Δ = 0.03 → 436 / 872 / 1,743
- 검토:
  - Δ = 0은 "개선"을 요구하는 것과 같아서 비열등 기준으로는 부적절하다.
  - Δ = 0.01은 고위험 층에 수천~1만여 명이 필요해 실현 가능성이 낮다.
- **제안**: Δ_safe = 0.02와 **표본 규칙**을 함께 둔다. DEV_TUNE의 LT 누락 층에서 관측한 d̂로 n_min = ⌈7.84·d̂/0.0004⌉을 계산해 평가 전에 고정한다. DEV_EVAL의 LT 누락 층 n이 n_min보다 작으면 G4는 "판정 불가"이고 GO를 내지 않는다.
- 대안: Δ_safe = 0.03(필요 n이 작음). 고위험 누락의 임상적 중요도를 생각하면 0.02를 우선 추천한다.

## 8. C9 유병률 가정 (제안)
- **Primary endpoint에는 유병률 가정이 없다.** sens@고정 FPR, AUROC, 쌍대 증분은 정답·오답 비율과 무관하게 정의된다. 쌍대 1:1 설계는 지표 계산 구조일 뿐 유병률 주장이 아니다.
- PPV·환자 100명당 경고 수(경고 부담)는 **시나리오 A/B/C**(wrong-WD 비율 π = 0.05 / 0.10 / 0.20, 가상값)로 민감도 분석만 하고 판정에 쓰지 않는다. 외부 유병률 출처가 필요하면 그때 따로 조사한다.

## 9. C7 초기 소견과 관측 가능성 (질문 사전 기준, 질환 연결 없음)
G1 §2.1의 6개 항목 + 위험인자(G1 권고 1, G2 1.3.2.1)를 DDXPlus 중립 질문 사전과 대조했다(질환→소견 구조는 보지 않음).

| G1 항목 | A. 현재 관측 가능(질문 예) | B. 의학적으로 중요하지만 관측 불가 | C. 검사·진찰 필요 |
|---|---|---|---|
| nature | 통증 양상 E_54(다중선택), 강도 E_56 | — | — |
| onset and duration | 발생 속도 E_59, 2주간 악화 E_13, 안정 시 흉통 E_14 | 한 번의 통증 지속시간(분, 예: G2의 >15분), 발생 후 경과시간(G2의 12/72시간), 빈도 | — |
| location and radiation | 부위 E_55, 방사 E_57, 국소성 E_58 | — | — |
| precipitating | 운동 E_218, 흡기 E_220, 식후 E_215, 움직임 E_216, 기침·힘줌 E_221, 누움 E_217 | 감정 스트레스 유발 | — |
| relieving | 휴식 E_218, 앞으로 숙임 E_33, 앉으면 완화 E_217 | (니트로글리세린 반응은 G1·G2가 진단 기준이 아니라고 명시) | — |
| associated symptoms | 호흡곤란 E_66, 발한 E_50, 오심 E_148, 어지럼 E_82, 두근거림 E_155, 객혈 E_45, 타는 느낌 E_173, 불안 E_16 | — | — |
| risk factors | 고혈압 E_104, 콜레스테롤 E_71, 당뇨 E_69, 흡연 E_79, 조기 심혈관 가족력 E_225, 심근경색·협심증 병력 E_105, DVT E_109, 부동 E_110, 최근 수술 E_196, 암 E_34, 기흉 병력 E_21, 심낭염 병력 E_3 | — | — |
| (출처의 검사·진찰) | — | — | 심전도, 트로포닌, D-dimer, CTPA, 흉부 X선, 심초음파, CMR, 활력징후·혈역학, 호흡음, 마찰음, 흉벽 압통 재현 |

- 정책: 지식에서는 `clinical_importance`와 `medmap_observable`을 분리한다. 관측할 수 없는 중요 소견을 지우지 않고 `medmap_observable = false`로 둔다. 실험 점수는 관측 가능한 것만 쓴다.
- **흉통 초기 소견 정의(open-set 층)**: 통증 존재 E_53 = 예이고, 부위 E_55가 흉부 계열인 경우. 어떤 값이 흉부 계열인지는 값 코드 사전으로 정하며 **CONFIRM_NEEDED**(K4 단계)다.

## 10. 남은 BLOCK
| ID | 내용 | 해제 조건 |
|---|---|---|
| **B-LIC** | 출처 중 소프트웨어·AI 사용을 허락한 곳이 없다(ESC·NICE·APA는 NO, AHA·BTS·ACG는 UNCLEAR). 사실 작성(C4)과 LLM 저자(C10)가 막힌다 | 사용자 결정: (a) ESC·NICE 등에 연구 허가 요청, (b) 재사용이 허용된 출처(CC BY 리뷰 등)로 한정해 다시 조사, (c) 사람 저자가 개인 연구 목적으로 작성 |
| **B-AUTH** | 저자 A·검증자 B·매핑 C의 실제 주체와 모델 ID가 정해지지 않음 | C10 결정 |
| B-VERIFY | 문헌 인용은 agent-extracted, unverified 상태(사본·요약 경유 포함) | K3 원문 대조 |
| B-N | 표본 수(전체 / LT 누락 층 / 쌍별)를 split 전이라 알 수 없음 | 승인 후 split(라벨만) |
| B-SCOPE | 심근염 포함 여부, P5(공황) 처리, 흉통 초기 소견 값 정의 | 사용자 확인 |

## 11. 주장 범위 (rev1 그대로)
성공하더라도 다음까지만 말한다: "predefined chest-pain differential subset·병력 정보만·시뮬레이션 WD·합성 환자에서, 검수 전 외부 지식 기반 재검토 신호가 고정 오경보율에서 모델 확률 기준선 대비 증분 탐지를 보였다(시뮬레이터 일치율 X%, 임상의 검수 없음, abstention 비율 Y%)." 오진 탐지·임상 성능·오진 감소 주장은 하지 않는다.
