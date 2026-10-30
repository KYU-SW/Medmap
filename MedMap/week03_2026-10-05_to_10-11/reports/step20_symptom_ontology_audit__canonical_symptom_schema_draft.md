# MedMap Canonical Symptom Schema — 초안 (STEP20, 2026-10-08)

> 상태: **초안 문서**. production `PatientState`·API·모델은 바꾸지 않는다. STEP20 감사 결과(`outputs/`)를 근거로 한 설계 제안이다.
> 근거 파일: `outputs/concept_normalization_layers.csv`, `outputs/symptom_expansion_opportunities.csv`, `outputs/ddxplus_*_mapping_audit.csv`.

## 1. 왜 필요한가 (감사에서 확인된 구조 문제)

- DDXPlus 110 증상 중 **12개는 증상이 아니라 다른 증상의 속성**(부위·양상·강도·발생속도·색·크기)이고, **10개는 수식어**(악화·완화 요인, 시간 양상), **1개는 노출**(알레르기 물질 접촉)이다.
- **20개는 한 질문에 두 개념 이상**을 묶은 복합 질문이다(예: E_89 "피곤하거나 잠을 자도 개운하지 않음").
- 흉통·두통·복통은 독립 증상이 아니라 `E_53 통증 + E_55 부위 값` 조합이다.
- 같은 개념이 표현만 바꿔 여러 feature로 존재한다(예: 호흡곤란 E_66 · 조금만 움직여도 숨참 E_64 · 자다가 숨막힘 E_67 · 누우면 심해짐 E_217).
- 극성(polarity)이 뒤집힌 질문이 있다(E_150 "대변·방귀가 나오나요?" — 예 = 정상).

→ "증상 1개 = binary feature 1개" 구조로는 새 표현·새 개념을 붙일 때마다 feature가 늘어난다. **표현 → 정규화 개념 → canonical 증상 + 속성 slot** 구조로 분리한다.

## 2. 3층 구조

```
layer 1  surface expression   "숨이 차요" "숨이 가빠요" "숨쉬기 힘들어요" "호흡이 벅차요" / "shortness of breath"
             │  (entity linking — 이번 단계에서 구현하지 않음)
layer 2  normalized concept   HPO:0002094 · SCTID:267036007 · UMLS:C0013404
             │  (ontology 계층으로 묶기)
layer 3  canonical symptom    dyspnea  + slots {exertional_vs_rest, position, onset, severity, temporal_pattern, ...}
```

- 4개의 한국어 표현은 **증상 4개가 아니라** layer 1의 표현 4개다. layer 3에는 `dyspnea` 하나만 생긴다.
- "조금만 움직여도 숨참"은 새 증상이 아니라 `dyspnea` + `exertional_vs_rest = exertional` + `severity = minimal effort`.
- 정규화 ID는 3개 ontology를 함께 저장한다. 감사에서 HPO는 증상 표현이 약하고(가벼운 어지러움·숨막힘·코/목 가려움 등), SNOMED·UMLS는 증상 수준 개념이 더 많았다.

## 3. 레코드 형식 (초안)

```json
{
  "concept_id": "dyspnea",
  "canonical_name": "Dyspnea",
  "hpo_id": "HP:0002094",
  "snomed_id": "267036007",
  "umls_cui": "C0013404",
  "status": "present",
  "site": [],
  "laterality": null,
  "onset": null,
  "duration": null,
  "severity": null,
  "quality": [],
  "frequency": null,
  "trend": null,
  "temporal_pattern": null,
  "position": null,
  "aggravating_factors": [],
  "relieving_factors": [],
  "associated_features": [],
  "context": null,
  "source": {"kind": "patient_text|question_answer|doctor_entry", "text": null, "question_id": null},
  "confidence": null,
  "assertion": {"negated": false, "historical": false, "family": false, "hypothetical": false}
}
```

| 필드 | 값 | 비고 |
|---|---|---|
| `status` | `present` · `absent` · `unknown` | 현재 PatientState의 POSITIVE/NEGATIVE/UNKNOWN과 1:1 대응 가능 |
| `site` | 부위 concept 목록(SNOMED body structure 등) | DDXPlus E_55·E_133·E_152 값이 여기로 들어간다 |
| `onset` | `sudden` · `gradual` · 0–10 척도 원값 | E_59 |
| `severity` | 0–10 · mild/moderate/severe · 기능 등급 | E_56 · E_134 · E_136, E_88(활동 제한), E_64(최소 노력) |
| `quality` | 양상 값 목록 | E_54 값(찌르는·타는 듯 등) |
| `trend` | `worsening` · `stable` · `improving` | E_13(2주 사이 악화) |
| `temporal_pattern` | `nocturnal` · `postprandial` · `episodic` … | E_219, E_215 |
| `position` | `worse_lying` · `relieved_leaning_forward` … | E_217, E_33 |
| `aggravating_factors` / `relieving_factors` | `exertion` · `movement` · `deep_inspiration` · `valsalva` · `rest` … | E_218, E_216, E_220, E_221 |
| `associated_features` | 다른 canonical 증상 ID | 예: heartburn ↔ regurgitation(쓴맛) |
| `assertion` | 부정·과거력·가족력·가정 | 증상/병력/위험요인이 섞이지 않게 분리(감사 14절) |

## 4. 규칙

1. **새 binary feature를 만들기 전에** 기존 canonical 증상 + slot 값으로 표현되는지 먼저 본다.
   SNOMED 하위 개념(예: "Productive cough - yellow sputum")은 대부분 속성 조합이므로 **slot 값 어휘**로 쓰고 별도 feature로 쪼개지 않는다.
2. **복합 질문**(OR)은 구성 개념마다 따로 저장한다. 하나만 확인됐으면 그 개념만 `present`.
3. **속성 질문**(부위·강도 등)은 독립 concept을 만들지 않고 부모 증상의 slot에 넣는다.
4. **수식어 질문**(악화·완화·시간)은 어느 증상에 붙는지 명시한다(`E_218 "증상"`처럼 대상이 불명확하면 `unknown_target`).
5. **극성**: 질문 문장이 아니라 개념 기준으로 저장한다(E_150 "예" → `obstipation: absent`).
6. **노출·병력·위험요인**은 증상 레코드가 아니라 별도 레코드(`exposure`, `history`, `risk_factor`)로 둔다. DDXPlus antecedent 113개가 여기에 해당한다.
7. 정규화 ID가 없는 증상(이번 감사의 NO_MATCH)은 `concept_id`만 MedMap 내부 ID로 만들고 ontology ID는 비워 둔다 — 억지 매핑 금지.

## 5. 현재 모델과의 관계 (변경하지 않음)

- 현재 49질환 classifier는 DDXPlus 223 binary/categorical feature를 그대로 입력으로 쓴다. 이 스키마는 **그 위의 표현층**이다.
- 이행 시 필요한 것: canonical 레코드 → DDXPlus feature 벡터로 되돌리는 **결정적 projection**(예: `dyspnea{exertional}` → E_66=1, E_64=1).
  이 projection은 이번 단계에서 만들지 않는다.
- 새 증상 개념은 projection 대상 feature가 없으면 현재 classifier에 입력되지 않는다. 이 한계는 감사 보고서 17절 질문 2에서 다룬다.

## 6. 이번 단계에서 하지 않은 것

- 한국어 표현 대규모 생성, entity linker·SapBERT 설치, PatientState 수정, projection 구현, 새 증상 학습.
