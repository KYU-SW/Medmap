"""STEP21 문서 생성: docs/korean_entity_linking_report.md, docs/pilot_dataset_protocol.md.
수치는 모두 outputs/metrics.json · data/leakage_report.json · CSV 에서 읽는다(손으로 적지 않음). 서술은 Claude 작성.
"""
import json
from collections import Counter

import el_common as c

DOCS = c.STEP / "docs"
B = ["BASELINE_EXACT", "BASELINE_FUZZY", "BASELINE_COMBINED_EXACT_THEN_FUZZY", "BASELINE_MEDMAP_INTAKE_MAPPER_v1_2"]
SHORT = {"BASELINE_EXACT": "EXACT", "BASELINE_FUZZY": "FUZZY", "BASELINE_COMBINED_EXACT_THEN_FUZZY": "COMBINED",
         "BASELINE_MEDMAP_INTAKE_MAPPER_v1_2": "MAPPER(제품)"}


def pct(x):
    return "n/a" if x is None else f"{x:.1%}"


def table(rows, cols):
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(r.get(k, "")).replace("|", "/") for k in cols) + " |" for r in rows]
    return "\n".join(out)


def main():
    m = json.load(open(c.OUT / "metrics.json"))
    lk = json.load(open(c.DATA / "leakage_report.json"))
    gold = c.load_gold()
    errs = c.read_csv(c.OUT / "error_analysis.csv")
    comb = {r["utterance_id"]: r for r in c.read_csv(c.OUT / "combined_predictions.csv")}
    mp = {r["utterance_id"]: r for r in c.read_csv(c.OUT / "mapper_predictions.csv")}
    d = m["decisions"]
    best = d["best_baseline"]
    T = {b: m["baselines"][b]["test"] for b in B}
    bt = T[best]
    th = m["thresholds_fuzzy_family"]

    head = [{"지표 (test split)": k} for k in []]
    rows = []
    for b in B:
        t = T[b]
        rows.append({"baseline": SHORT[b], "gate": m["baselines"][b]["gate_on_test"]["verdict"],
                     "A+B Top-1": pct(t["tier_AB"]["top1_accuracy"]), "A+B R@3": pct(t["tier_AB"]["recall_at_3"]),
                     "A+B R@5": pct(t["tier_AB"]["recall_at_5"]), "A+B 새 표현 Top-1": pct(t["tier_AB_novel"]["top1_accuracy"]),
                     "A+B 사전 표현 Top-1": pct(t["tier_AB_seen"]["top1_accuracy"]),
                     "multi F1": pct(t["all"]["concept_micro_f1"]), "status F1": pct(t["all"]["status_aware_micro_f1"]),
                     "auto P": pct(t["all"]["policy"]["auto_accept_precision"]), "auto": pct(t["all"]["policy"]["auto_accept_rate"]),
                     "ask": pct(t["all"]["policy"]["ask_confirmation_rate"]), "abstain": pct(t["all"]["policy"]["abstention_rate"]),
                     "unknown P/R": f"{pct(t['all']['unknown_rejection']['precision'])} / {pct(t['all']['unknown_rejection']['recall'])}"})
    tier_rows = []
    for b in B:
        t = T[b]
        tier_rows.append({"baseline": SHORT[b], **{k: f"{pct(t[k]['top1_accuracy'])} (n={t[k]['n_should_link']})"
                                                   for k in ("all", "tier_A", "tier_AB", "tier_C", "tier_AB_mapper_covered_concepts", "tier_AB_mapper_uncovered_concepts")},
                          "Tier D 거절(recall)": pct(t["tier_D"]["unknown_rejection"]["recall"])})
    st_rows = []
    for b in B:
        a = m["baselines"][b]["all"]["all"]
        st_rows.append({"baseline": SHORT[b],
                        "부정 개념 검출": pct(a["negation"]["concept_detection_rate"]), "부정 status 정확(검출 중)": pct(a["negation"]["status_accuracy_given_detected"]),
                        "부정 end-to-end": pct(a["negation"]["end_to_end_correct_rate"]),
                        "과거 개념 검출": pct(a["temporal_historical"]["concept_detection_rate"]), "과거 end-to-end": pct(a["temporal_historical"]["end_to_end_correct_rate"]),
                        "타인 증상 누출": pct(a["other_person"]["leak_rate"]), "n(부정/과거/타인)": f"{a['negation']['n_mentions']}/{a['temporal_historical']['n_mentions']}/{a['other_person']['n_mentions']}"})
    cat_rows = []
    cats = sorted({k for b in B for k in m["error_category_counts_test"][b]})
    for k in cats:
        cat_rows.append({"category": k, **{SHORT[b]: m["error_category_counts_test"][b].get(k, 0) for b in B}})
    # 잘 되는/실패 사례(test)
    good = [g for g in gold if g["split"] == "test" and g["lexical_exposure"] == "novel" and g["tier"] in "AB"
            and comb[g["utterance_id"]]["ranked_top5"].split(";")[0] in c.patient_concepts(g)
            and comb[g["utterance_id"]]["policy"] != "ABSTAIN"][:10]
    good_rows = [{"문장": g["text_ko"], "정답": g["primary_concept"], "COMBINED top3": ";".join(comb[g["utterance_id"]]["ranked_top5"].split(";")[:3]),
                  "정책": comb[g["utterance_id"]]["policy"], "MAPPER": mp[g["utterance_id"]]["top1"] or "(없음)"} for g in good]
    mgood = [g for g in gold if g["split"] == "test" and g["lexical_exposure"] == "novel" and mp[g["utterance_id"]]["top1"] in c.patient_concepts(g)][:8]
    mgood_rows = [{"문장": g["text_ko"], "정답": g["primary_concept"], "MAPPER": mp[g["utterance_id"]]["top1"]} for g in mgood]
    fail = [e for e in errs if e["baseline"] == best and e["split"] == "test"]
    pick, seen_cat = [], set()
    for e in fail:
        k = e["categories"].split(";")[0]
        if k not in seen_cat:
            seen_cat.add(k)
            pick.append(e)
    fail_rows = [{"문장": e["text_ko"], "정답": e["gold"], f"{SHORT[best]} top3": e["pred_top3"], "정책": e["policy"], "분류": e["categories"]} for e in pick]
    mfail = [e for e in errs if e["baseline"] == "BASELINE_MEDMAP_INTAKE_MAPPER_v1_2" and e["split"] == "test" and e["policy"] == "AUTO_ACCEPT"][:8]
    mfail_rows = [{"문장": e["text_ko"], "정답": e["gold"], "MAPPER 예측": e["pred_set"], "분류": e["categories"]} for e in mfail]
    sch = m["schema_check"]
    ex_attr = next(g for g in gold if g["text_ko"].startswith("어제 밤부터 왼쪽 가슴"))

    rep = f"""# 한국어 환자 표현 → Canonical Symptom Entity Linking Pilot (STEP21)

- 작성 2026-10-08 · 브랜치 `research/symptom-ontology-expansion` · `exp/step21_korean_symptom_entity_linking/`
- **데이터는 전부 합성**: 평가 문장 {lk['gold_utterances']}개는 Claude가 작성한 합성 표현이다(실제 환자 발화 아님). 정답 라벨도 Claude 판정(임상의 검수 없음).
- label space: STEP20 core symptom 87개(속성·수식어·노출 제외). pilot 은 그중 20개 concept. 부위·양상·시점은 별도 class 가 아니라 attribute.
- 수치는 **test split**(dev 에서 threshold 를 고른 뒤 고정 적용). 엔지니어링 gate 이며 임상 성능 기준이 아니다.

## 최종 판정

```
KOREAN_ENTITY_LINKING = {d['KOREAN_ENTITY_LINKING']}      (가장 나은 baseline: {SHORT[best]})
DICTIONARY_BASELINE   = {d['DICTIONARY_BASELINE']}
FUZZY_BASELINE        = {d['FUZZY_BASELINE']}
LEARNED_LINKER_NEEDED = {d['LEARNED_LINKER_NEEDED']}
NLU_NEEDED            = {d['NLU_NEEDED']}
Baseline 3 (local embedding) = NOT_EVALUATED
```

## 핵심 수치 ({SHORT[best]}, test)

| 항목 | 값 |
|---|---|
| canonical symptoms tested | {lk['n_pilot_concepts']} |
| utterances | {lk['gold_utterances']} (dev {lk['split']['dev']} / test {lk['split']['test']}) |
| Tier A+B Top-1 | {pct(bt['tier_AB']['top1_accuracy'])} |
| Recall@3 (Tier A+B) | {pct(bt['tier_AB']['recall_at_3'])} |
| Multi-label micro F1 (concept) | {pct(bt['all']['concept_micro_f1'])} |
| Negation accuracy (end-to-end, 전체 split) | {pct(m['baselines'][best]['all']['all']['negation']['end_to_end_correct_rate'])} |
| Unknown rejection precision / recall | {pct(bt['all']['unknown_rejection']['precision'])} / {pct(bt['all']['unknown_rejection']['recall'])} |
| Auto-accept precision | {pct(bt['all']['policy']['auto_accept_precision'])} (자동 수락 {bt['all']['policy']['n_auto']}건) |
| Ask-confirmation rate | {pct(bt['all']['policy']['ask_confirmation_rate'])} |
| Abstention rate | {pct(bt['all']['policy']['abstention_rate'])} |

FUZZY·COMBINED threshold(dev 에서만 선택): T_high={th['T_high']} · T_low={th['T_low']} · T_multi={th['T_multi']}. **T_high=1.01은 dev 에서 auto precision 95%를 넘는 점수 구간이 없어 자동 수락을 끈 상태**라는 뜻이다.

## baseline 비교 (test)

{table(rows, list(rows[0].keys()))}

Tier 별 Top-1 (test, 괄호는 정답 있는 문장 수):

{table(tier_rows, list(tier_rows[0].keys()))}

- MAPPER(제품 Natural Intake v1.2) 는 alias 가 있는 pilot concept 이 {len(m['mapper_alias_covered_pilot_concepts'])}/20 ({', '.join(m['mapper_alias_covered_pilot_concepts'])}) 뿐이다. 나머지 concept 은 구조적으로 0%.

## 부정 · 시점 · 다른 사람 (전체 split, mention 단위)

{table(st_rows, list(st_rows[0].keys()))}

EXACT·FUZZY·COMBINED 는 status 를 항상 present 로 내므로 부정·과거 status 정확도가 0 이다(규칙을 덧붙여 올리지 않았다). MAPPER 는 부정 scope 규칙이 있어 검출한 부정은 맞히지만 검출 자체가 낮고, 과거 시점은 처리하지 않는다.

## 1. 잘 되는 한국어 표현 사례 (test, 사전에 없는 새 표현, COMBINED 가 1순위로 맞히고 확인 질문으로 넘긴 것)

{table(good_rows, list(good_rows[0].keys())) if good_rows else '(없음)'}

MAPPER 가 새 표현을 맞힌 예:

{table(mgood_rows, list(mgood_rows[0].keys())) if mgood_rows else '(없음)'}

## 2. 실패 사례 (test, {SHORT[best]} — 분류별 첫 예)

{table(fail_rows, list(fail_rows[0].keys())) if fail_rows else '(없음)'}

MAPPER 가 **잘못 자동 수락**한 예:

{table(mfail_rows, list(mfail_rows[0].keys())) if mfail_rows else '(없음)'}

- "토했어요 → nausea": 제품 매퍼에는 구토(E_211) alias 가 없고, DDXPlus E_148 질문("메스껍거나 토할 것 같은가요")에 '토'가 걸려 오심으로 들어간다. 구토 보고가 오심으로 자동 저장되는 구조적 오류다.
- "목이 따가워요 → pain": DDXPlus 에서는 인후통(E_97)과 통증+부위(E_53+인두)가 둘 다 가능한 표현이라, 정답 정의에 따라 오답이 아닐 수도 있다(라벨 공간 자체의 중복).

## 실패 분류 (test, 문장 1개에 여러 분류 가능)

{table(cat_rows, ['category'] + [SHORT[b] for b in B])}

## 3. 현재 dictionary 의 한계

- 사전({lk['dictionary_expressions']}개 표현, {lk['dictionary_concepts']}개 concept)은 **화면 라벨과 질문문**뿐이다. 환자가 실제로 쓰는 활용형("어지러워요", "숨이 벅차요", "토했어요")이 없다.
- test A+B 중 사전 표현이 그대로 들어 있는 문장은 Top-1 {pct(T['BASELINE_EXACT']['tier_AB_seen']['top1_accuracy'])} 이지만, 새 표현은 {pct(T['BASELINE_EXACT']['tier_AB_novel']['top1_accuracy'])} 이다 — 사전 방식은 **암기만 되고 일반화가 안 된다**.
- 라벨에서 잘라낸 짧은 조각이 다른 증상으로 오탐을 만든다: "누런 가래가 나오는 기침" → '누런'(누런 콧물 E_182), "얼굴이 부석부석해요" → '얼굴'(얼굴 근육 경련·근력 약화). 다른 사람 문장("남편이 기침을…", "할머니가 숨이 차신대요")과 가정 문장("열이 나면 어떻게 해야 하나요")도 그대로 자동 수락된다(`exact_predictions.csv`).

## 4. fuzzy matching 의 한계

- 문자 유사도는 의미가 아니라 글자 겹침을 본다: "가슴이 아파요" → 1순위 '목이 아픈가요?'(인후통)·2순위 '가슴 두근거림', "땅이 흔들리는 느낌이에요" → 1순위 '삼킬 때 걸리는 느낌'(`fuzzy_predictions.csv`).
- 정답이 상위 3개 안에 들어오는 비율(A+B R@3 {pct(T['BASELINE_FUZZY']['tier_AB']['recall_at_3'])})도 확인 UX 에 쓰기엔 낮다.
- dev 에서 자동 수락해도 될 만큼 정확한 점수 구간이 없었다(T_high 미설정) → fuzzy 는 "확인 질문 후보 생성"으로만 쓸 수 있고 자동 매핑에는 못 쓴다.

## 5. 학습형 entity linker 가 필요한가 — {d['LEARNED_LINKER_NEEDED']}

- 규칙: 어떤 baseline 도 test A+B **새 표현** Top-1 ≥ 90%를 넘지 못하면 YES. 실제 최고치 {pct(max(T[b]['tier_AB_novel']['top1_accuracy'] or 0 for b in B))}.
- 다만 이 pilot 만으로 "학습형 모델이 해결한다"는 증거는 없다. 사전을 환자 표현으로 보강했을 때(alias 확장)와 학습형 linker 를 **같은 test 로 비교**해야 결정할 수 있다.
- 로컬 모델: xlm-roberta-base 뿐(문장 유사도 학습 없음) → Baseline 3 NOT_EVALUATED. SapBERT·sentence-transformers 는 지시대로 설치하지 않았다.

## 6. NLU 가 별도로 필요한가 — {d['NLU_NEEDED']}

- 개념 찾기와 별개로 **부정·과거·다른 사람·복수 증상**이 따로 무너진다. 사전·fuzzy 는 구조상 status 를 낼 수 없고, 제품 매퍼도 과거 시점과 검출률이 낮다.
- 다른 사람 증상 누출: EXACT {pct(m['baselines']['BASELINE_EXACT']['all']['all']['other_person']['leak_rate'])}, COMBINED {pct(m['baselines']['BASELINE_COMBINED_EXACT_THEN_FUZZY']['all']['all']['other_person']['leak_rate'])}. 환자 PatientState 에 가족의 증상이 들어가는 위험.
- 필요한 문장 이해 단위(향후 dialogue/NLU 요구사항): mention 별 status(present/absent/historical/uncertain), subject(환자/타인), 복수 mention 분리, attribute 연결.

## 7. MedMap 환자 UX 적용

- **지금 단계에서 자동 매핑을 넓히면 안 된다.** 자동 수락 precision 이 95%에 못 미친다(EXACT {pct(T['BASELINE_EXACT']['all']['policy']['auto_accept_precision'])}, MAPPER {pct(T['BASELINE_MEDMAP_INTAKE_MAPPER_v1_2']['all']['policy']['auto_accept_precision'])}).
- 가능한 형태: 자유 문장 → 상위 3개 후보를 **환자에게 한 번 확인**("숨이 차신 건가요?"). COMBINED 의 ASK 구간에서 정답이 상위 3개에 든 비율 {pct(T['BASELINE_COMBINED_EXACT_THEN_FUZZY']['all']['policy']['ask_top3_contains_primary'])} — 확인 UX 를 쓰더라도 후보 품질이 먼저 올라가야 한다.
- 부정·과거·타인 문장은 확인 질문에서 status 를 따로 묻는 설계가 필요하다(“지금도 그런가요?”, “본인 증상인가요?”).

## 21절 — canonical schema 연결

- 예: “{ex_attr['text_ko']}” → concept `{ex_attr['primary_concept']}`, attributes `{json.dumps(ex_attr['attributes'], ensure_ascii=False)}`
- gold attribute 값 {sch['attribute_values']}개 중 {sch['fit_draft_schema']}개가 초안 스키마 필드(site·onset·quality·severity·aggravating_factors·temporal_pattern·position·context 등)에 들어간다.
- 들어가지 않는 키: {', '.join(sch['need_concept_specific_fields'])} → 증상별 전용 attribute(가래 색·객혈 양·토사물 내용·함요부종 등)가 필요하다. 초안 스키마에 `concept_specific: {{}}` 칸을 추가하는 수정을 제안(이번엔 문서만, production 무변경).
- 이번 baseline 은 attribute 추출을 하지 않았다(개념 연결만 평가).

## 8. 다음 실험

가장 먼저 하나: **같은 test 로 "환자 표현 alias 보강 사전" vs "학습형 multilingual linker(SapBERT-XLMR 등)"를 비교**한다.
alias 보강은 dev 표현만 보고 만들고 test 는 그대로 봉인해야 한다. 학습형 linker 는 모델 다운로드 승인이 필요하다(이번엔 하지 않음).
NLU(부정·시점·화자)는 개념 연결과 별도 트랙으로 둔다.

## 한계

- 평가 문장·정답 모두 Claude 작성 합성 데이터라 실제 환자 말투·오타·방언 분포를 대표하지 않는다. 숫자는 baseline 간 **상대 비교**로만 쓴다.
- test {lk['split']['test']}문장(A+B {T['BASELINE_EXACT']['tier_AB']['n_should_link']}문장)으로 작아서 1문장이 약 1%p 를 움직인다.
- 제품 매퍼는 다른 blind set 으로 이미 평가된 모듈이며, 이번 test 와 질문 범위(binary evidence 41개)가 달라 절대 성능 비교가 아니다.

## 재현

```bash
bash exp/step21_korean_symptom_entity_linking/run_all.sh     # 1분 이내, 2회 실행 SHA256 동일 확인(logs/sha1.txt, sha2.txt)
~/ai_env/bin/python exp/step21_korean_symptom_entity_linking/scripts/build_report.py
```
"""
    DOCS.mkdir(exist_ok=True)
    (DOCS / "korean_entity_linking_report.md").write_text(rep, encoding="utf-8")

    tier_cnt = Counter(g["tier"] for g in gold)
    type_cnt = Counter(g["utt_type"] for g in gold)
    concept_cnt = Counter(g["group"] for g in gold)
    proto = f"""# Pilot dataset protocol (STEP21)

## label space
- STEP20 `curation/curated_mappings.tsv` 에서 role ∈ {{SYMPTOM, SIGN, COMPOSITE}} 인 87개 evidence = canonical symptom 공간. 그 외 23개(속성·수식어·노출)는 class 로 쓰지 않는다.
- pilot 20 concept 과 DDXPlus evidence 연결: {json.dumps(c.PILOT, ensure_ascii=False)}
- 선정 기준: (1) DDXPlus 학습 데이터에서 자주 나오는 초기 증상(initial_evidence_ko frequent_ids 포함) (2) 응급·감별 가치(객혈·토혈·의식 소실·흉통) (3) 한국어 표현 다양성이 큰 것.
- 사용자 후보와의 차이:
  - 흉통·두통·복통 → 별도 concept 아님. `pain` + site attribute (DDXPlus E_53 + E_55 구조, STEP20 결론).
  - 실신 → inventory 에 syncope 없음 → `loc`(E_159 의식 소실)로 대체.
  - 전신 쇠약 → generalized weakness concept 없음 → `limb_weakness`(E_84·E_176)로 대체; "온몸에 힘이 없어요"는 Tier D(피로/쇠약 애매)로 둠.
  - 의식 변화 → `confusion`(E_39).
  - 변비 → inventory 에 없음(E_150 은 극성 반전된 PARTIAL) → 제외, 대신 `sore_throat`(E_97)·`heartburn`(E_173)·`decreased_appetite`(E_32·E_161) 추가.
  - 어지럼 → `dizziness`(E_76). 실신 전 느낌(E_82 presyncope)은 pilot 밖 concept 으로 남김.

## 표현 출처 (provenance)
- DICTIONARY(train 쪽): 기존 MedMap 자원만 — terminology_ko.json(evidence_short label 과 구성 부분, evidence_questions), initial_evidence_ko.json(label·detail), question_labels_ko.json. {lk['dictionary_expressions']}개 표현.
- TEST(gold): `data/pilot_source_utterances.tsv`, **source_type = synthetic_paraphrase**(Claude 작성, 2026-10-08). existing_medmap 0, existing_patient_companion 0 (친구 저장소는 로컬에 없음 — 2026-10-04 사용자 결정으로 미반입).
- 제품 매퍼의 기존 평가 문장(exp/intake_mapper_v1*/)은 매퍼 튜닝·평가에 쓰였으므로 test 에 넣지 않았다.

## 문장 유형 (사용자 A–J + S)
{table([{"type": k, "n": v} for k, v in sorted(type_cnt.items())], ["type", "n"])}

A 짧은 일상 · B 자연 문장 · C 비정형/의성어 · D 증상+속성 · E 복수 증상 · F 부정 · G 과거/현재 · H 다른 사람 · I 애매 · J 매핑 불가 · S 철자 변형

## 품질 등급
{table([{"tier": k, "n": v} for k, v in sorted(tier_cnt.items())], ["tier", "n"])}

TIER_A 정답 명확 · TIER_B 정답 있으나 구어·애매 표현 · TIER_C 복수/부정/시점/타인/불확실 · TIER_D 한 concept 에 연결하면 안 됨(정답 = 없음)

concept 그룹별 문장 수: {dict(sorted(concept_cnt.items()))}

## gold 형식 (`data/pilot_gold.csv`)
- `gold_mentions`: [{{concept, status ∈ present/absent/historical/uncertain, subject ∈ patient/other}}]. 환자 정답 = subject=patient 인 concept.
- `primary_concept` / `secondary_concepts` / `other_person_concepts` / `attributes`(concept 별 slot) / `should_link` / `ambiguity_flag` / `reason`.
- "쥐어짜는 느낌" 같은 양상은 class 가 아니라 `attributes.pain.quality`.

## 누수 방지
- 사전과 정규화 완전일치 또는 difflib ≥ {lk['thresholds']['near_dictionary_difflib']} → 평가에서 제거: {lk['removed_for_leakage']}건 {lk['removed_examples']}
- gold 내부 near-duplicate(≥ {lk['thresholds']['near_gold_difflib']})가 dev/test 에 갈린 경우 test 로 이동: {lk['moved_to_test_for_internal_near_duplicates']}
- 정답 concept 의 사전 stem 이 문장에 그대로 있으면 `lexical_exposure=seen`(암기), 아니면 `novel`(일반화): seen {lk['lexical_exposure']['seen']} · novel {lk['lexical_exposure']['novel']} · 정답 없음 {lk['lexical_exposure']['n/a']}. 결과는 둘을 분리해 보고한다.
- split: concept 그룹 안 원본 순서 index % 3 == 0 → dev, 나머지 test. threshold 는 dev 에서만 고른다.

## 정규화(과도한 규칙 금지)
공백·문장부호 제거, 사전 쪽 의문형 어미(-나요/-가요/-요 등) 제거, 명사형 어미(-ㅁ/-음) 제거 변형을 **추가**(원형도 유지 — '기침'의 ㅁ 받침 보호).
"""
    (DOCS / "pilot_dataset_protocol.md").write_text(proto, encoding="utf-8")
    print("docs written")


if __name__ == "__main__":
    main()
