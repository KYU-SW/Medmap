# DDXPlus 증상 → HPO / UMLS / SNOMED 전수 Mapping Audit (STEP20)

- 작성: 2026-10-08 · 브랜치 `research/symptom-ontology-expansion` · 위치 `exp/step20_symptom_ontology_audit/`
- 범위: **terminology coverage · concept normalization 가능성 · disease retrieval 후보 공간 · KB 확장 가능성**만 본다. 진단 정확도·진단 가능 질환 수는 측정하지 않았다.
- 판정 출처: 110개 증상의 정답 매핑은 **Claude(LLM)가 원본 label·definition·parent를 보고 판정**했다(`curation/curated_mappings.tsv`). **임상의 검증은 받지 않았다.** 기존 후보는 이 판정과 계층 관계로 결정적 규칙 비교 + 사유를 남긴 수동 보정.

## 최종 판정

```
MAPPING            = CONDITIONAL        (usable union 93/110 = 84.5%; 기준 PASS ≥90%, CONDITIONAL 70–90%)
SYMPTOM_EXPANSION  = PARTIAL
RETRIEVAL_RANKING  = CONDITIONAL_GO
질문 2(49-class 재설계 없이 ontology 확장) = PARTIAL
```

## 핵심 수치

| 항목 | 값 |
|---|---|
| DDXPlus symptoms | 110 (증상 57 · 징후 10 · 복합 20 · 속성 12 · 수식어 10 · 노출 1) |
| HPO usable mapping | 86/110 |
| SNOMED usable mapping | 90/110 |
| UMLS usable mapping | 92/110 |
| union usable mapping (HPO∪UMLS∪SNOMED) | 93/110 |
| exact mapping (union) | 76 |
| partial (union, usable 아님) | 5 |
| no match (union) | 1 |
| not applicable (속성·노출, union) | 11 |
| core 증상만(속성·수식어·노출 제외, n=87) usable union | 85/87 |
| expansion HIGH / MEDIUM | 11 / 38 (합 49) |
| HPO phenotype-overlap disease count (exact HPO id, ≥1 / ≥3) | 5,982 / 1,760 |
| 같은 수치, true-path(조상 일치) ≥1 / ≥3 | 8,797 / 3,335 |
| DDXPlus 49질환이 HPO 주석(phenotype.hpoa)에 이름 그대로 있는 수 | 2 |
| DDXPlus 49질환 중 OptimusKG에서 HPO 증상 주석이 1개 이상인 수 | 8 |

> phenotype-overlap disease count는 **"이 증상 어휘로 후보에 올릴 수 있는 질환 공간"**이다. 진단 가능한 질환 수가 아니다.

## Coverage 표 (all 110, NOT_APPLICABLE 포함 분모)

| ontology | EXACT | BROADER | NARROWER | PARTIAL | WRONG | NO_MATCH | N/A | strict | usable | partial_incl |
|---|---|---|---|---|---|---|---|---|---|---|
| HPO | 55 | 26 | 5 | 7 | 0 | 5 | 12 | 55/110 (50.0%) | 86/110 (78.2%) | 93/110 (84.5%) |
| UMLS | 72 | 16 | 4 | 6 | 0 | 1 | 11 | 72/110 (65.5%) | 92/110 (83.6%) | 98/110 (89.1%) |
| SNOMED | 69 | 16 | 5 | 6 | 0 | 3 | 11 | 69/110 (62.7%) | 90/110 (81.8%) | 96/110 (87.3%) |
| HPO∪SNOMED | 75 | 14 | 3 | 6 | 0 | 1 | 11 | 75/110 (68.2%) | 92/110 (83.6%) | 98/110 (89.1%) |
| HPO∪UMLS | 76 | 14 | 3 | 5 | 0 | 1 | 11 | 76/110 (69.1%) | 93/110 (84.5%) | 98/110 (89.1%) |
| HPO∪UMLS∪SNOMED | 76 | 14 | 3 | 5 | 0 | 1 | 11 | 76/110 (69.1%) | 93/110 (84.5%) | 98/110 (89.1%) |

core 증상 subset(속성·수식어·노출 23개 제외):

| ontology | usable | strict |
|---|---|---|
| HPO | 79/87 (90.8%) | 53/87 (60.9%) |
| UMLS | 84/87 (96.5%) | 68/87 (78.2%) |
| SNOMED | 83/87 (95.4%) | 65/87 (74.7%) |
| HPO∪SNOMED | 84/87 (96.5%) | 71/87 (81.6%) |
| HPO∪UMLS | 85/87 (97.7%) | 72/87 (82.8%) |
| HPO∪UMLS∪SNOMED | 85/87 (97.7%) | 72/87 (82.8%) |

## 기존 mapping 후보 감사 (step8)

- `evidence_hpo_candidates.csv`·`evidence_umls_candidates.csv`: 문자열 TF-IDF 자동 후보. **review_status·final 칸이 110/110 비어 있어** 사람이 확정한 매핑은 없었다. HPO는 정확 매칭이 아니라 질문문 정규화 문자열 유사도라, `E_52 이중 시야 → Overlapping toe`처럼 단어 조각 일치로 오매핑이 많다. UMLS 후보는 56/110 증상에 후보가 아예 없다.
- `evidence_concept_map.csv`(이전 세션의 의미 구조 기반 map)는 훨씬 낫지만, 질환 개념을 증상 자리에 둔 경우(Cardiac arrhythmia·GERD·Pertussis)와 의미가 반대인 경우(E_180 Ophthalmoplegia — 실제 질문은 눈이 저절로 돌아가는 oculogyric 증상)가 있다.

| existing source | EXACT | usable | WRONG | no candidate |
|---|---|---|---|---|
| HPO step8 TF-IDF top1 | 21 | 37/110 | 35 | 0 |
| HPO step8 TF-IDF best of top3 (oracle pick) | 24 | 53/110 | 27 | 0 |
| HPO step8 concept_map (best component) | 36 | 55/110 | 6 | 21 |
| UMLS step8 TF-IDF cui1 | 14 | 20/110 | 15 | 56 |
| UMLS step8 concept_map (best component) | 44 | 61/110 | 9 | 0 |
| SNOMED step8 concept_map (best component) | 43 | 62/110 | 4 | 4 |

("best component"는 증상마다 가장 유리한 후보를 고른 상한값)

## 1. 잘 매핑되는 대표 사례

| evidence_id | canonical_concept | hpo_ids | sct_ids | umls |
|---|---|---|---|---|
| E_91 | Fever | HP:0001945 | 386661006 | C0015967 |
| E_53 | Pain | HP:0012531 | 22253000 | C0030193 |
| E_159 | Loss of consciousness | HP:0007185 | 419045004 | C0041657 |
| E_154 | Pallor | HP:0000980 | 398979000 | C0241137 |
| E_155 | Palpitations | HP:0001962 | 80313002 | C0030252 |
| E_210 | Hematemesis | HP:0002248 | 8765009 | C0018926 |
| E_140 | Melena | HP:0002249 | 2901004 | C0025222 |
| E_51 | Diarrhea | HP:0002014 | 62315008 | C0011991 |
| E_89 | Fatigue OR non-restorative sleep | HP:0012378;HP:5200292 | 84229001;248260009 | C0015672;C0424571 |
| E_114 | Irritability OR mood instability | HP:0000737;HP:0000712 | 55929007;18963009 | C0022107;C0085633 |
| E_82 | Presyncope (lightheaded, about to faint) | HP:0031972 | 427461000;386705008 | C0700200;C0220870 |
| E_148 | Nausea | HP:0002018 | 422587007 | C0027497 |

## 2. 잘 안 되는 대표 사례

| evidence_id | canonical_concept | hpo_class | hpo_reason | sct_class | umls_class |
|---|---|---|---|---|---|
| E_33 | Pain relieved by leaning forward | NO_MATCH | only generic 'Ameliorated by' HP:0025254 | NO_MATCH | NO_MATCH |
| E_75 | Choking sensation / feeling of suffocation | NO_MATCH | HPO only has Choking episodes HP:0030842 (feeding behaviour) - different meaning | EXACT | EXACT |
| E_169 | Itchy nose OR itchy throat | NO_MATCH | HPO Pruritus is a skin phenotype; no nasal/pharyngeal itch term | PARTIAL | ACCEPTABLE_BROADER |
| E_166 | Post-tussive vomiting | NO_MATCH | no HPO term | EXACT | EXACT |
| E_76 | Dizziness OR lightheadedness (mild) | PARTIAL | HPO Vertigo carries 'dizziness' as synonym; lightheadedness is not vertigo | EXACT | EXACT |
| E_150 | Able to pass stool/gas (inverse of obstipation) | PARTIAL | polarity inverted: YES = able; concept = inability (Obstipation) | PARTIAL | PARTIAL |
| E_202 | Whooping cough (symptom) | EXACT | Whooping cough is an HPO cough phenotype | PARTIAL | =SCT |
| E_218 | Symptom aggravated by exertion, relieved by rest | PARTIAL | Triggered by exertion; relief by rest lost | NO_MATCH | =HPO |
| E_13 | Crescendo pattern: worse over 2 weeks with less effort | PARTIAL | Progressive; exertional threshold lost | PARTIAL | =SCT |
| E_180 | Involuntary eye deviation (oculogyric) | ACCEPTABLE_NARROWER | Oculogyric crisis; lay wording ambiguous | ACCEPTABLE_NARROWER | ACCEPTABLE_NARROWER |
| E_168 | Involuntary tongue protrusion (dystonic) | PARTIAL | Protruding tongue is a morphology term; evidence is involuntary movement | PARTIAL | PARTIAL |
| E_128 | Brief suffocation with inability to breathe/speak | PARTIAL | Laryngospasm is a mechanism-level label for the episode | ACCEPTABLE_BROADER | =SCT |

## 3. 현재 110개 증상 구조의 근본적인 한계

- **110개 중 23개는 증상이 아니다**: 속성 12(부위·양상·강도·발생속도·위치 명확도·색·크기·부종·통증 강도), 수식어 10(악화·완화·야간·식후·악화 경향), 노출 1(E_42). 이 23개는 어떤 ontology의 "증상 개념"으로도 정확히 대응하지 않는다(커버리지 분모에 남겨 둠).
- **흔한 주소(主訴)가 독립 증상이 아니다**: 흉통·두통·복통은 `E_53 통증 + E_55 부위 값(165개)` 조합이다. ontology의 Chest pain·Headache·Abdominal pain 개념은 evidence가 아니라 **값 수준**에서만 연결된다.
- **복합 질문 20개**: 한 질문에 2–3개 개념(예: E_175 피로·권태·근육통). 답이 "예"여도 어느 개념인지 모른다.
- **같은 개념의 변형이 별도 feature**: 호흡곤란 E_66·E_64·E_67·E_217, 기침 E_201·E_203·E_77·E_166, 피로 E_89·E_88·E_175. ontology 관점에서는 하나의 개념 + slot.
- **극성 반전**: E_150 "대변·방귀가 나오나요?"(예 = 정상) — 개념(Obstipation)과 반대 방향.
- **HPO는 증상 표현에 약하다**: HPO는 유전·희귀질환 표현형 중심이라 lightheadedness, choking sensation, 코·목 가려움, post-tussive vomiting, 통증 완화 자세 같은 일상 증상 개념이 없거나 진단 수준 라벨(Laryngospasm, Arrhythmia, GERD)로만 있다.

## 4. ontology를 붙였을 때 실제로 좋아지는 것

- **표준 ID 정규화**: core 증상 87개 중 85개가 최소 한 ontology에서 usable 매핑을 갖는다. 다른 데이터·KB와 같은 ID로 연결할 수 있다.
- **표현층 분리 근거**: UMLS 소비자 어휘(CHV·MedlinePlus) 표현이 81/110 증상에 있고, 증상 1개당 영어 표현 중앙값 18개 → "표현 여러 개 = 개념 1개" 구조를 데이터로 뒷받침(`concept_normalization_layers.csv`).
- **세분화 어휘**: SNOMED·HPO 하위 개념(예: 기침 하위 SNOMED 39개, 통증 하위 HPO 109개)을 slot 값 어휘로 쓸 수 있다. 단, 대부분 부위·시간·양상의 사전 조합이라 **별도 feature로 쪼개지 말고 slot 값으로 쓰는 것**을 권고(`snomed_split_recommendation`).
- **확장 차원**: expansion HIGH 11개 · MEDIUM 38개 — 발생·기간·강도·양상·악화/완화·동반증상 slot을 붙일 여지가 있다.

## 5. ontology를 붙여도 해결되지 않는 것

- **한국어 표현 → 개념 연결(entity linking)**: 이번에 사용한 HPO·SNOMED(INT)·UMLS(영어 parquet)에는 한국어 표현이 없다. "숨이 가빠요"를 C0013404로 보내는 단계는 별도 구현·검증이 필요하다.
- **속성·수식어의 구조화**: ontology는 개념 ID를 줄 뿐, "어느 증상이 어떤 자세에서 악화되는지" 같은 관계는 MedMap 스키마(`docs/canonical_symptom_schema_draft.md`)가 담아야 한다.
- **현재 classifier 입력**: 49질환 모델은 DDXPlus 223 feature만 받는다. 새 개념은 기존 feature로 되돌릴(projection) 수 있는 하위 개념이 아니면 모델에 들어가지 않는다.
- **흔한 질환의 증상 지식**: HPO 질환 주석은 희귀·유전질환 위주다. DDXPlus 49질환 중 이름 그대로 있는 것은 2개, OptimusKG에서 HPO 증상 주석이 있는 것은 8개뿐이다.
- **확률·빈도**: phenotype.hpoa의 빈도 칸은 희귀질환 문헌 기반이고, aspect P 주석의 19.4%가 비어 있다. 일차 진료 증상의 사전확률은 여기서 나오지 않는다.

## 6. 질환 확장 가능성

phenotype.hpoa (`#description: "HPO annotations for rare diseases [8478: OMIM; 47: DECIPHER; 4357…`):

- 질환 12,866개(aspect P, NOT 제외) — OMIM 8,464 · ORPHA 4,355 · DECIPHER 47; 주석 268,179개, 서로 다른 HPO term 11,560개
- 질환당 phenotype 수: 중앙값 15 (10% 3 · 90% 45 · 최대 230)
- phenotype당 질환 수: 중앙값 4 (90% 45 · 최대 2583)

usable HPO 매핑만 썼을 때 phenotype-overlap disease count:

| min overlap (DDX evidence) | exact HPO id | true-path (ancestor match) | OptimusKG true-path |
|---|---|---|---|
| ≥1 | 5982 | 8797 | 4545 |
| ≥2 | 3060 | 5443 | 2592 |
| ≥3 | 1760 | 3335 | 1433 |
| ≥5 | 757 | 1497 | 425 |

- exact HPO id = 질환 주석 term이 매핑 term과 같을 때만, true-path = 질환 주석 term의 조상에 매핑 term이 있으면 일치(예: "Productive cough" 주석 → Cough 일치).
- true-path 수치는 `HP:0000951 Abnormality of the skin`·`HP:0012531 Pain` 같은 넓은 term 때문에 부풀려진다. **보수적으로는 exact id 수치를 본다.**
- 이 공간은 대부분 **희귀·유전질환**이다. 일차 진료의 흔한 질환 후보 공간이 아니다.

## 보조 KB 대조 (통합하지 않음)

- HSDN 증상 어휘(MeSH 322개)에 있는 증상: 35/110 · MEDLINE 공출현 증상 어휘: 36/110
- HPO에서 NO_MATCH/PARTIAL인데 HSDN·MEDLINE 어휘에는 있는 증상: E_76
- OptimusKG: HPO 증상 edge가 있는 질환 6,648개. DDXPlus 49질환 중 이름(일부 별칭)으로 노드를 찾은 수 28, 그중 HPO 증상 주석이 1개 이상인 수 8 (`auxiliary_kb_ddx49_in_optimuskg.csv`)
- DisMech: 이번에 재측정하지 않음(4.9 GB YAML). 기존 README 기록은 49질환 중 17개 연결.

## 대표 증상 상세

| representative_symptom | ddxplus_representation | hpo_mapping | snomed_mapping | umls_mapping | expansion_level |
|---|---|---|---|---|---|
| chest pain | E_53 + E_55∈{V_101 upper chest, V_29 lower chest, V_55/V_56 side of chest, V_170/V_171 posterior chest wall, V_159/V_160 breast}; E_14 at rest; E_220 pleuritic | HP:0100749 Chest pain | 29857009 Chest pain | C0008031 Chest Pain | HIGH (E_53 pain dims already factorized) |
| dyspnea | E_66 (+E_64 exertional, E_67 PND, E_217 orthopnea-type) | HP:0002094 [EXACT] | 267036007 [EXACT] | C0013404 [EXACT] | HIGH |
| fever | E_91 | HP:0001945 [EXACT] | 386661006 [EXACT] | C0015967 [EXACT] | HIGH |
| cough | E_201 (+E_77 sputum, E_203 paroxysmal, E_45 hemoptysis, E_166 post-tussive vomiting) | HP:0012735 [EXACT] | 49727002 [EXACT] | C0010200 [EXACT] | HIGH |
| headache | E_53 + E_55∈{V_89 forehead, V_62 top of head, V_25 back of head, V_124 occiput, V_166/V_167 temple} | HP:0002315 Headache | 25064002 Headache | C0018681 Headache | HIGH (E_53 pain dims already factorized) |
| abdominal pain | E_53 + E_55∈{V_197 epigastric, V_103/V_104 hypochondrium, V_87/V_88 iliac fossa, V_84/V_85 flank, V_187 belly, V_153 pubis} | HP:0002027 Abdominal pain | 21522001 Abdominal pain | C0000737 Abdominal Pain | HIGH (E_53 pain dims already factorized) |
| nausea | E_148 | HP:0002018 [EXACT] | 422587007 [EXACT] | C0027497 [EXACT] | MEDIUM |
| vomiting | E_211 (+E_210 hematemesis) | HP:0002013 [ACCEPTABLE_BROADER] | 422400008 [ACCEPTABLE_BROADER] | C0042963 [ACCEPTABLE_BROADER] | HIGH |
| dizziness | E_76 (mild dizziness/lightheaded), E_82 (presyncope) | HP:0002321 [PARTIAL] | 404640003;386705008 [EXACT] | C0012833;C0220870 [EXACT] | HIGH |
| palpitations | E_155 (+E_164 irregular) | HP:0001962 [EXACT] | 80313002 [EXACT] | C0030252 [EXACT] | HIGH |
| fatigue | E_89 (+E_88 severe, E_175 malaise) | HP:0012378;HP:5200292 [EXACT] | 84229001;248260009 [EXACT] | C0015672;C0424571 [EXACT] | HIGH |
| syncope | no syncope evidence; E_159 loss of consciousness, E_82 presyncope | HP:0007185 [EXACT] | 419045004 [EXACT] | C0041657 [EXACT] | MEDIUM |
| edema | E_151 swelling + E_152 site | HP:0000969 [ACCEPTABLE_NARROWER] | 65124004 [EXACT] | C0038999 [EXACT] | HIGH |
| diarrhea | E_51 | HP:0002014 [EXACT] | 62315008 [EXACT] | C0011991 [EXACT] | HIGH |
| weakness | E_84 bilateral limbs (+E_176 limb/face, E_90 fatigable, E_83 face/eye) | HP:0003690 [ACCEPTABLE_BROADER] | 713514005;15634971000119107 [ACCEPTABLE_BROADER] | C2219734;C4751283 [EXACT] | MEDIUM |

추천 canonical 표현은 `outputs/representative_symptoms.csv`의 `recommended_canonical_representation`, 스키마는 `docs/canonical_symptom_schema_draft.md`.

## 17절 판정 근거

- **질문 1 — 110개 제한에서 벗어날 기술적 기반: PARTIAL.** 영어 개념 정규화 기반은 있다(core 85/87 usable, 소비자 표현 81/110). 그러나 한국어 표현 연결, 속성 slot 구조, 흔한 질환의 증상 KB가 없다.
- **질문 2 — 49-class 모델 재설계 없이 ontology 기반 확장: PARTIAL.** 기존 evidence의 **하위 개념**(예: 객담 색, 야간 기침)은 상위 개념으로 되돌려(projection) 현재 모델에 넣을 수 있다. 그러나 기존 223 feature에 대응이 없는 **새 증상 개념**은 학습 데이터(DDXPlus 합성)에 없어서 현재 classifier가 쓸 수 없다.
- **질문 3 — Retrieval + Ranking 구조로 넘어갈 가치: CONDITIONAL_GO.** 개념 정규화와 질환-증상 KB(희귀질환 12,866개)는 있다. 하지만 DDXPlus 49질환 같은 흔한 질환의 증상 주석이 거의 없고(8/49), 빈도 정보와 평가 정답이 없다. **흔한 질환 증상 KB를 확보하고 평가 설계를 먼저 고정한다는 조건**에서만 baseline 실험 가치가 있다.

## 7. 다음 실험 제안 (자동 진행하지 않음)

가장 먼저 할 것 하나: **"한국어 환자 표현 → canonical 증상 개념" 연결의 소규모 평가셋 만들기.** 기존 natural intake 문장과 `terminology_ko.json` 표현에서 core 증상 87개를 대상으로 표현–개념 쌍을 고정한 뒤, 사전 기반 baseline부터 측정한다(외부 모델 설치 전).
Disease Retrieval baseline은 흔한 질환 증상 KB 확보 여부를 먼저 결정해야 하므로 그 다음이다.

## 품질 검증 (21절)

| 항목 | 결과 | 근거 |
|---|---|---|
| symptom 110개 전수 | PASS | load_symptoms() 110/113/223 assert, curation 110행 assert |
| duplicate 없음 | PASS | evidence_id unique assert (inventory·curation) |
| missing ID 없음 | PASS | curation 집합 == DDXPlus 증상 집합 assert; curated HPO/SNOMED/CUI 전부 원본에 존재 |
| ontology version 기록 | PASS | HPO hp/releases/2026-09-01, UMLS 2026AA, SNOMED INT 2026-09-01 (manifest.json) |
| obsolete HPO | PASS | 기존·curated 후보 중 obsolete 0건, alt_id 0건 (발견 시 replaced_by/consider 기록 로직 포함) |
| inactive SNOMED | PASS | curated 전부 active; 기존 후보 중 INT 배포판에 없는 US extension ID 3건 → WRONG 처리·사유 기록 |
| UMLS semantic type | PASS(경고 포함) | curated CUI 중 Sign or Symptom/Finding 아닌 것 24건 = CHECK 표기(UMLS 가 증상에도 Disease or Syndrome 을 붙임). 질환 자체 CUI(Pertussis·Myasthenias·Cardiac Arrhythmia 등)는 WRONG |
| source provenance | PASS | 모든 행에 candidate_source(curated/step8_tfidf/step8_concept_map/…) |
| 자동 vs 수동 판정 구분 | PASS | judgement_source = curated / auto_rule / manual_override, review_status 명시 |
| 재현 가능성 | PASS | run_all.sh 2회 실행 결과 CSV·JSON SHA256 동일(logs/sha_run1.txt vs sha_run2.txt) |
| deterministic | PASS | 난수 없음, 정렬 순회 |
| 임상 검증 | 미검증 | curated 판정은 Claude(LLM) 검토이며 임상의 검토 아님 — 수치는 이 판정에 의존 |

결과 파일(row 수·SHA256 앞 16자, 전체는 `outputs/manifest.json`):

| file | rows | sha256 |
|---|---|---|
| outputs/auxiliary_kb_ddx49_in_optimuskg.csv | 49 | 3aeca274ece5a836… |
| outputs/auxiliary_kb_sampling.csv | 110 | f5696c9a96bb9ed6… |
| outputs/concept_normalization_layers.csv | 110 | da3d1bc1aaeb0965… |
| outputs/ddxplus_hpo_mapping_audit.csv | 570 | 31909332cf226ccd… |
| outputs/ddxplus_snomed_mapping_audit.csv | 381 | 712701a05772f37a… |
| outputs/ddxplus_umls_mapping_audit.csv | 440 | 13c2f31393d23fa1… |
| outputs/disease_annotation_distribution.json |  | 18bcb2772b356588… |
| outputs/disease_overlap_summary.csv | 32 | 6b1bbbde36dc9797… |
| outputs/mapping_coverage_summary.json |  | cd14f42be4ae006b… |
| outputs/representative_symptoms.csv | 15 | 571099c76eccf5ef… |
| outputs/symptom_expansion_opportunities.csv | 110 | b3c621f3a6879270… |
| outputs/symptom_inventory.csv | 110 | a16cac1d9aeae4c4… |
| outputs/umls_lay_strings.csv | 126 | 01b4f58b880acc6e… |

## 한계

- 정답 판정(curated)은 Claude 1인(LLM) 판정이다. 임상의·독립 reviewer 재판정이 없어서 EXACT/ACCEPTABLE 경계는 판정자에 따라 바뀔 수 있다. coverage 수치는 이 판정에 의존한다.
- 기존 후보 판정은 curated 와의 계층 비교 규칙 + 수동 보정(스크립트의 OVERRIDES 목록)이다. 규칙상 WRONG 이어도 의미가 일부 겹치는 후보가 남아 있을 수 있다.
- SNOMED 는 International 배포판만 사용했다(US extension 개념은 없음). UMLS 는 영어 MRCONSO(SUPPRESS=N)만 사용했다.
- phenotype-overlap 은 희귀질환 주석(phenotype.hpoa) 기준이며, true-path 수치는 넓은 상위 term 때문에 커진다.

## 이 감사에서 주장하지 않는 것

- HPO를 붙이면 모든 질환을 진단할 수 있다 — 주장하지 않음
- SNOMED를 쓰면 희귀질환을 찾을 수 있다 — 주장하지 않음
- 49질환에서 수천 질환으로 진단 확장 가능하다 — 주장하지 않음(수천은 phenotype-overlap 후보 공간일 뿐)
- ontology coverage가 높으니 진단 정확도가 높다 — 주장하지 않음(정확도는 측정하지 않음)

## 재현

```bash
bash exp/step20_symptom_ontology_audit/run_all.sh          # 원본 data/ 읽기만, 약 10–20분, 캐시 .cache/
~/ai_env/bin/python exp/step20_symptom_ontology_audit/scripts/build_report.py
```
