"""STEP25 외부 라벨 → MedMap 77 canonical 매핑 판정 + 평가 단위 추출 + 누수 감사.

매핑 등급 규칙(실행 전 고정): 외부 '라벨'이 MedMap concept 하나를 가리킬 때만 EXACT/ACCEPTABLE.
범주 라벨(예: Symptom 전체)은 PARTIAL, 질병·신체·치료 라벨은 NO_MATCH(질병을 증상으로 바꾸지 않음), 스키마 미확인은 UNCERTAIN.
→ EXACT/ACCEPTABLE 이 없으면 GOLD_CANDIDATE 0.

평가 단위(정답 없음):
- BERT_NER_KO: 고유 ST span(외부 annotator 가 '증상'이라고 표시한 표현, concept 미지정) → UNLABELED
- KBMC: 고유 Disease span(질병·증상 혼재) → UNLABELED
- KO_MEDICAL_CHAT: 첫 client 발화(생성문, 복수 증상 가능) → UNLABELED
- SILVER: 공백 제거 표현이 STEP23 학습 표현과 완전일치(규칙으로 concept 부여 가능) — 동시에 학습 누수이므로 정확도 계산 금지
누수: STEP23 학습 1,119 · STEP21 gold 274(dev+test) 와 exact / normalized(공백 제거) / near(difflib ≥ 0.80)
출력: data/canonical_label_mapping.csv · data/eligible_external_examples.csv · outputs/leakage_audit.csv
"""
import collections
import difflib

import s25_common as S

MAPPING = [
    ("KBMC", "Disease", "", "NO_MATCH", "질병 범주(증상 표현도 섞여 태깅됨) — 질병 라벨을 증상 concept 으로 바꾸지 않음"),
    ("KBMC", "Body", "", "NO_MATCH", "신체 부위 = MedMap 에서는 concept 이 아니라 site 속성"),
    ("KBMC", "Treatment", "", "NO_MATCH", "치료"),
    ("BERT_NER_KO", "ST", "(77 중 미지정)", "PARTIAL", "'증상' 범주 라벨 — 어느 concept 인지 원본에 없음"),
    ("BERT_NER_KO", "DS", "", "NO_MATCH", "질병"),
    ("BERT_NER_KO", "BD", "", "NO_MATCH", "신체 부위(site 속성)"),
    ("KO_MEDICAL_CHAT", "(라벨 없음)", "", "NO_MATCH", "라벨 없음"),
    ("AIHUB_98", "증상/징후(카테고리)", "(77 중 미지정)", "PARTIAL", "카테고리 단위, 개별 증상 concept 아님 · 승인 전 원문 미확인"),
    ("AIHUB_208", "'증상별' 수집 단위", "", "UNCERTAIN", "안심존 데이터 — JSON 스키마·라벨 미확인"),
]


class Near:
    """difflib ratio ≥ t 근접 탐색(quick_ratio 상한으로 가지치기)."""

    def __init__(self, pool):
        self.pool = [p for p in pool if p]

    def best(self, x):
        b, bx = 0.0, ""
        for p in self.pool:
            sm = difflib.SequenceMatcher(None, x, p, autojunk=False)
            if sm.real_quick_ratio() <= b or sm.quick_ratio() <= b:
                continue
            r = sm.ratio()
            if r > b:
                b, bx = r, p
        return b, bx


def main():
    S.write_csv(S.DATA / "canonical_label_mapping.csv",
                [{"dataset": d, "external_label": e, "canonical_id": c, "grade": g, "reason": r, "used_for_accuracy": g in ("EXACT", "ACCEPTABLE")}
                 for d, e, c, g, r in MAPPING])
    train = S.read_csv(S.S24.S23 / "data/expanded_train_expressions.csv")
    train_ns = {S.nospace(r["expression"]): r["canonical_id"] for r in train}
    train_norm = {S.norm(r["expression"]) for r in train}
    gold = S.S24.load_gold()
    gold_ns = {S.nospace(g["text_ko"]): g["split"] for g in gold}
    near_train, near_gold = Near(list(train_ns)), Near(list(gold_ns))

    units = []
    nk = S.load_bert_ner_ko()
    c = collections.Counter(S.nospace(x) for r in nk for t, x in r["spans"] if t == "ST")
    surf = {}
    for r in nk:
        for t, x in r["spans"]:
            if t == "ST":
                surf.setdefault(S.nospace(x), x)
    for k, n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])):
        units.append({"dataset": "BERT_NER_KO", "unit_type": "ST_span", "text": surf[k], "freq": n})
    kb = S.load_kbmc()
    c = collections.Counter(S.nospace(x) for r in kb for t, x in r["spans"] if t == "Disease")
    surf = {}
    for r in kb:
        for t, x in r["spans"]:
            if t == "Disease":
                surf.setdefault(S.nospace(x), x)
    for k, n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])):
        units.append({"dataset": "KBMC", "unit_type": "Disease_span", "text": surf[k], "freq": n})
    seen = set()
    for r in S.load_ko_medical_chat():
        if r["client_turns"] and S.nospace(r["client_turns"][0]) not in seen:
            seen.add(S.nospace(r["client_turns"][0]))
            units.append({"dataset": "KO_MEDICAL_CHAT", "unit_type": "first_client_turn", "text": r["client_turns"][0], "freq": 1, "src": r["id"]})

    for i, u in enumerate(units):
        x = S.nospace(u["text"])
        u["unit_id"] = f"X{i:05d}"
        u["train_exact_nospace"] = x in train_ns
        u["train_exact_norm"] = S.norm(u["text"]) in train_norm
        rt, _ = near_train.best(x) if u["dataset"] != "KO_MEDICAL_CHAT" else (0.0, "")
        rg, gx = near_gold.best(x)
        u["train_max_ratio"] = round(rt, 4) if u["dataset"] != "KO_MEDICAL_CHAT" else ""
        u["gold_exact"] = x in gold_ns
        u["gold_max_ratio"] = round(rg, 4)
        u["gold_nearest_split"] = gold_ns.get(gx, "")
        u["negation_cue_in_text"] = bool(S.NEG_CUE.search(u["text"]))
        u["tier"] = "SILVER" if u["train_exact_nospace"] else "UNLABELED"
        u["silver_rule_concept"] = train_ns.get(x, "")
        u["eligible_for_accuracy"] = False                      # GOLD_CANDIDATE 0 → 정확도 계산 대상 없음
        u["eligible_for_unlabeled_analysis"] = not u["train_exact_nospace"] and not u["gold_exact"]
    fields = ["unit_id", "dataset", "unit_type", "text", "freq", "tier", "silver_rule_concept", "train_exact_nospace", "train_exact_norm",
              "train_max_ratio", "gold_exact", "gold_max_ratio", "gold_nearest_split", "negation_cue_in_text", "eligible_for_accuracy",
              "eligible_for_unlabeled_analysis"]
    S.write_csv(S.DATA / "eligible_external_examples.csv", units, fields)

    rows = []
    for ds in ("BERT_NER_KO", "KBMC", "KO_MEDICAL_CHAT"):
        us = [u for u in units if u["dataset"] == ds]
        tr = [float(u["train_max_ratio"]) for u in us if u["train_max_ratio"] != ""]
        rows.append({"dataset": ds, "n_units": len(us), "train_exact": sum(u["train_exact_nospace"] for u in us),
                     "train_near_ge_0.80": sum(x >= 0.8 for x in tr) if tr else "", "train_near_ge_0.60": sum(x >= 0.6 for x in tr) if tr else "",
                     "gold_exact": sum(u["gold_exact"] for u in us), "gold_near_ge_0.80": sum(u["gold_max_ratio"] >= 0.8 for u in us),
                     "gold_near_test_ge_0.80": sum(u["gold_max_ratio"] >= 0.8 and u["gold_nearest_split"] == "test" for u in us),
                     "silver": sum(u["tier"] == "SILVER" for u in us), "gold_candidate": 0,
                     "eligible_for_unlabeled_analysis": sum(u["eligible_for_unlabeled_analysis"] for u in us),
                     "negation_cue": sum(u["negation_cue_in_text"] for u in us)})
    S.write_csv(S.OUT / "leakage_audit.csv", rows)
    for r in rows:
        print(r)
    print("silver concepts", collections.Counter(u["silver_rule_concept"] for u in units if u["tier"] == "SILVER").most_common(12))


if __name__ == "__main__":
    main()
