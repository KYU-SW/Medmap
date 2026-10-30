"""STEP27 판정 + 보고서 + STEP28 인계 + manifest. 숫자는 모두 outputs/ 파일에서 읽는다.

판정 기준(지시문 §12 Engineering Gate, BEST_POLICY vs POLICY_A, 보고 집합 EXT_EVAL·INT_REGRESSION_CORE·latency):
 G_A weak-symptom→NON ≤ 0.03 그리고 POLICY_A 대비 상대 감소 ≥ 50%('크게')
 G_B weak-non auto-accept ≤ A + 0.005              G_C regression auto coverage ≥ A(0.3761)
 G_D regression auto precision ≥ 0.95              G_E EXT disagreement auto-accept = 0
 G_F CPU p95 ≤ 50 ms                               G_U weak-non→UNKNOWN ≤ A + 0.05(UNKNOWN 남발 방지)
 G_N weak-non→NON ≥ A − 0.10 그리고 weak-non→UNCERTAIN ≤ A + 0.10(UNCERTAIN 팽창 방지)
 [공개] G_N 은 EVAL 수치를 본 뒤 추가한 보수 방향 조항이다(지시문 §11 'UNKNOWN 을 늘려 수치가 좋아지는 정책 불채택'의 UNCERTAIN 판).
        G_N 없이 계산한 판정도 함께 기록한다(verdict_without_G_N).
 REGRESSION = G_B·G_D·G_E 중 하나라도 실패(안전 악화) · ROUTING_IMPROVED = 전부 통과 ·
 PARTIAL_IMPROVEMENT = 안전 gate 통과 & G_A 의 상대 감소 ≥ 50% 이지만 다른 gate 실패 · NO_GAIN = 그 외.
"""
import json

import s27_common as S
from safe_symptom_router import POLICIES

ORDER = ["POLICY_A", "POLICY_B", "POLICY_C", "POLICY_D", "POLICY_E"]


def pct(x):
    return "—" if x in (None, "") else f"{float(x) * 100:.1f}%"


def table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def main():
    sel = S.load_json(S.OUT / "routing_selection.json")
    best = sel["BEST_POLICY"]
    comp = {}
    for r in S.read_csv(S.OUT / "policy_comparison.csv"):
        comp[(r["policy"], r["set"], r["metric"])] = r["value"]

    def v(p, st, m, d=None):
        x = comp.get((p, st, m), "")
        return d if x == "" else float(x)

    lat = S.load_json(S.OUT / "latency.json")
    summ = S.load_json(S.OUT / "routing_error_summary.json")
    smoke = S.load_json(S.OUT / "illustrative_smoke.json")
    insp = S.load_json(S.OUT / "previous_inspection.json")
    p95 = lat["single_message_cpu"][f"STEP27_ROUTER_{best}"]["p95_ms"]
    p50 = lat["single_message_cpu"][f"STEP27_ROUTER_{best}"]["p50_ms"]

    E, R = "EXT_EVAL", "INT_REGRESSION_CORE"
    A, B = "POLICY_A", best
    fnA, fnB = v(A, E, "WEAK_SYMPTOM|NON_SYMPTOM_rate"), v(B, E, "WEAK_SYMPTOM|NON_SYMPTOM_rate")
    rel = (fnA - fnB) / fnA if fnA else 0.0
    g = {"G_A": fnB <= 0.03 and rel >= 0.5,
         "G_B": v(B, E, "WEAK_NON_SYMPTOM|KNOWN_SYMPTOM_rate") <= v(A, E, "WEAK_NON_SYMPTOM|KNOWN_SYMPTOM_rate") + 0.005,
         "G_C": v(B, R, "auto_coverage") >= v(A, R, "auto_coverage") - 1e-9,
         "G_D": v(B, R, "auto_precision") >= 0.95,
         "G_E": v(B, E, "disagreement_auto_count") == 0,
         "G_F": p95 <= 50,
         "G_U": v(B, E, "WEAK_NON_SYMPTOM|UNKNOWN_SYMPTOM_rate") <= v(A, E, "WEAK_NON_SYMPTOM|UNKNOWN_SYMPTOM_rate") + 0.05,
         "G_N": v(B, E, "WEAK_NON_SYMPTOM|NON_SYMPTOM_rate") >= v(A, E, "WEAK_NON_SYMPTOM|NON_SYMPTOM_rate") - 0.10
                and v(B, E, "WEAK_NON_SYMPTOM|UNCERTAIN_rate") <= v(A, E, "WEAK_NON_SYMPTOM|UNCERTAIN_rate") + 0.10}

    def verdict(keys):
        if not (g["G_B"] and g["G_D"] and g["G_E"]):
            return "REGRESSION"
        if all(g[k] for k in keys):
            return "ROUTING_IMPROVED"
        if rel >= 0.5:
            return "PARTIAL_IMPROVEMENT"
        return "NO_GAIN"
    res = verdict(list(g))
    res_wo = verdict([k for k in g if k != "G_N"])
    out = {"STEP27_RESULT": res, "verdict_without_G_N": res_wo, "BEST_POLICY": best, "params": sel["params"],
           "FALSE_NON_RATE": fnB, "FALSE_NON_RATE_POLICY_A": fnA, "FALSE_NON_REL_REDUCTION": S.rnd(rel),
           "WEAK_NEGATIVE_AUTO_ACCEPT_RATE": v(B, E, "WEAK_NON_SYMPTOM|KNOWN_SYMPTOM_rate"),
           "SUPPORTED_AUTO_COVERAGE": v(B, R, "auto_coverage"), "REGRESSION_AUTO_PRECISION": v(B, R, "auto_precision"),
           "UNKNOWN_RATE(EXT_EVAL)": v(B, E, "UNKNOWN_rate"), "UNCERTAIN_RATE(EXT_EVAL)": v(B, E, "UNCERTAIN_rate"),
           "CPU_P50_MS": p50, "CPU_P95_MS": p95, "PEAK_RSS_MIB": lat["peak_rss_mib"], "PRODUCTION_READY": "NO",
           "CANONICAL_ACCURACY_VALIDATED": "NO", "EXTERNAL_GOLD_AVAILABLE": "NO", "GPU_USED": "NO", "gates": g, "rules": __doc__}
    S.dump_json(S.OUT / "step27_verdict.json", out)

    # ---- 보고서 ----
    rows = []
    spec = [("Weak-symptom → NON (false NON)", E, "WEAK_SYMPTOM|NON_SYMPTOM_rate", pct),
            ("Weak-symptom → UNKNOWN", E, "WEAK_SYMPTOM|UNKNOWN_SYMPTOM_rate", pct),
            ("Weak-symptom → UNCERTAIN", E, "WEAK_SYMPTOM|UNCERTAIN_rate", pct),
            ("Weak-symptom → KNOWN 자동 수락", E, "WEAK_SYMPTOM|KNOWN_SYMPTOM_rate", pct),
            ("Weak-non → KNOWN 자동 수락", E, "WEAK_NON_SYMPTOM|KNOWN_SYMPTOM_rate", pct),
            ("Weak-non → NON", E, "WEAK_NON_SYMPTOM|NON_SYMPTOM_rate", pct),
            ("Weak-non → UNKNOWN", E, "WEAK_NON_SYMPTOM|UNKNOWN_SYMPTOM_rate", pct),
            ("Weak-non → UNCERTAIN", E, "WEAK_NON_SYMPTOM|UNCERTAIN_rate", pct),
            ("Weak-non 후보 표시율", E, "WEAK_NON_SYMPTOM|candidate_display_rate", pct),
            ("Weak-symptom 후보 표시율", E, "WEAK_SYMPTOM|candidate_display_rate", pct),
            ("후보 억제율(A 가 표시한 행 중)", E, "candidate_suppression_rate_vs_A", pct),
            ("모델 불일치 자동 수락 수", E, "disagreement_auto_count", lambda x: int(float(x))),
            ("EXT UNKNOWN 비율", E, "UNKNOWN_rate", pct), ("EXT UNCERTAIN 비율", E, "UNCERTAIN_rate", pct),
            ("Regression 자동 수락 precision", R, "auto_precision", pct), ("Regression 자동 수락 coverage", R, "auto_coverage", pct),
            ("Regression 비자동 중 gold 표시", R, "nonauto_gold_in_displayed", lambda x: int(float(x))),
            ("Regression 비자동 중 gold 없는 표시", R, "nonauto_displayed_without_gold", lambda x: int(float(x))),
            ("Regression COMPLEX_INPUT 비율", R, "COMPLEX_INPUT_rate", pct),
            ("KMC 복합문 COMPLEX_INPUT 비율", "KMC_COMPLEX_STRESS", "COMPLEX_INPUT_rate", pct),
            ("KMC 복합문 자동 수락", "KMC_COMPLEX_STRESS", "auto_rate", pct)]
    for name, st, m, f in spec:
        rows.append([name] + [f(comp.get((p, st, m), "")) if comp.get((p, st, m), "") != "" else "—" for p in ORDER])
    dev_rows = []
    for name, st, m, f in spec[:12]:
        st2 = "EXT_DEV" if st == E else st
        dev_rows.append([name] + [f(comp.get((p, st2, m), "")) if comp.get((p, st2, m), "") != "" else "—" for p in ORDER])
    for name, m in (("core dev 자동 precision", "auto_precision"), ("core dev 자동 coverage", "auto_coverage"), ("core dev 비자동 중 gold 표시", "nonauto_gold_in_displayed")):
        dev_rows.append([name] + [comp.get((p, "INT_DEV_CORE", m), "—") for p in ORDER])
    n_ws, n_wn = int(v(A, E, "WEAK_SYMPTOM|n")), int(v(A, E, "WEAK_NON_SYMPTOM|n"))
    sep = summ["unknown_vs_non_separation"]
    inap = summ["inappropriate_display_proxy(A shown rows)"]
    inap_new = summ["inappropriate_display_proxy(best newly shown rows)"]
    raw = summ["raw_preservation_check(best, all rows)"]
    rep = S.read_csv(S.OUT / "representative_cases.csv")
    import collections
    rep_tab = []
    for t in sorted({r["term"] for r in rep}):
        rs = [r for r in rep if r["term"] == t]
        ca = collections.Counter(r["POLICY_A_status"] for r in rs)
        cb = collections.Counter(r[f"{best}_status"] for r in rs)
        rep_tab.append([t, len(rs), "; ".join(f"{k} {n}" for k, n in ca.most_common()), "; ".join(f"{k} {n}" for k, n in cb.most_common())])
    sm = [[t, o["status"], o["decision"], ";".join(o["candidate_ids"]) or "—", ";".join(o["reason_codes"])] for t, o in smoke["results"].items()]
    gsel = sel["dev_gate"]
    gate_rows = [[p, "PASS" if gsel[p]["pass"] else "FAIL", ", ".join(k for k, ok in gsel[p]["checks"].items() if not ok) or "—"] for p in ORDER]
    sev_ = summ["silver"]
    s28 = summ["step28"]
    e_info = sel["E_info"]
    ff = lambda x: f"{x * 100:.1f}%"  # noqa: E731

    md = f"""# STEP27 — MedMap Safe Symptom Routing v2

- STEP27_RESULT = **{res}** (G_N 제외 시 {res_wo}) · BEST_POLICY = **{best}** · PRODUCTION_READY = **NO** · CANONICAL_ACCURACY_VALIDATED = NO · EXTERNAL_GOLD_AVAILABLE = NO · GPU_USED = NO
- 파라미터(DEV 선택): `{S.dumps(sel['params'])}`
- 지표 성격: EXT = 외부 NER 범주 weak-label proxy(MedMap concept 정답 아님). Regression = 합성 FIXED_REGRESSION_TEST 109(blind 아님). EXT_EVAL 은 STEP25·26 에서 이미 예측을 본 데이터 → frozen retrospective evaluation. 임상 안전성 검증 아님.
- 기존 결과 재현: B4 {insp['I3_b4_reproduction']['n_rows']}행 불일치 {insp['I3_b4_reproduction']['mismatch']} · STEP26 상태 불일치 {insp['I4_step26_status_reproduction']['mismatch']} · label map 일치 · Linear 점수 재계산 차 {insp['I5_linear_score_recompute_max_abs_diff(200 rows)']}. POLICY_A 보고 집합 상태 = STEP26 predictions.csv 와 100% 일치(assert).

## 1. 판정 요약

| 항목 | 값 |
|---|---|
| FALSE_NON_RATE (EVAL weak-symptom → NON, n={n_ws}) | {pct(fnB)} (POLICY_A {pct(fnA)}) |
| WEAK_NEGATIVE_AUTO_ACCEPT_RATE (n={n_wn}) | {pct(out['WEAK_NEGATIVE_AUTO_ACCEPT_RATE'])} |
| SUPPORTED_AUTO_COVERAGE (regression) | {pct(out['SUPPORTED_AUTO_COVERAGE'])} |
| REGRESSION_AUTO_PRECISION | {pct(out['REGRESSION_AUTO_PRECISION'])} |
| UNKNOWN_RATE (EXT_EVAL 전체) | {pct(out['UNKNOWN_RATE(EXT_EVAL)'])} |
| CPU p50 / p95 | {p50} ms / {p95} ms |
| 메모리(peak RSS) | {lat['peak_rss_mib']} MiB (모델 적재 후 {lat['rss_after_load_mib']} MiB) |

Gate: {' · '.join(f"{k} {'PASS' if ok else 'FAIL'}" for k, ok in g.items())}. 규칙은 `scripts/build_report.py` 문서열(G_N 은 EVAL 수치를 본 뒤 추가한 보수 조항 — 공개).

## 2. 정책 비교 — 보고 집합(EXT_EVAL · Regression · KMC, 선택에 미사용)

{table(rows, ['지표'] + ORDER)}

## 3. 정책 비교 — DEV(선택에 사용, EXT_DEV 비증상 점수는 out-of-fold)

{table(dev_rows, ['지표'] + ORDER)}

DEV gate(BEST 선택 규칙, `evaluate_routing.py` 문서열):

{table(gate_rows, ['policy', 'DEV gate', '실패 항목'])}

POLICY_E(B4 임계 변경, 탐색): fold 별 선택 CV core coverage {pct(e_info['cv_step27_objective']['core_coverage'])} · precision {pct(e_info['cv_step27_objective']['core_precision'])} · WN auto {pct(e_info['cv_step27_objective']['WN_auto'])} vs B4(DEV) coverage {pct(e_info['b4_on_dev(in-sample params)']['core_coverage'])} → 채택 = {e_info['adopted']}. 표의 POLICY_E 열은 보고용(BEST 후보 아님).

## 4. UNKNOWN ↔ NON 분리 (EXT_EVAL, weak label 대비)

{table([[p, sep[f'EXT_EVAL|{p}']['UNKNOWN_on_WS'], sep[f'EXT_EVAL|{p}']['UNKNOWN_on_WN'], pct(sep[f'EXT_EVAL|{p}']['UNKNOWN_weak_symptom_share']), sep[f'EXT_EVAL|{p}']['NON_on_WS'], sep[f'EXT_EVAL|{p}']['NON_on_WN'], pct(sep[f'EXT_EVAL|{p}']['NON_weak_non_share'])] for p in ORDER], ['policy', 'UNKNOWN·WS', 'UNKNOWN·WN', 'UNKNOWN 중 WS 비율', 'NON·WS', 'NON·WN', 'NON 중 WN 비율'])}

## 5. 후보 표시 (부적절 표시 proxy: weak-non 에 표시 · 최대 후보 유사도 < 0.2 · INT 에서 gold 미포함)

{table([[st, inap[st]['A_shown_rows'], inap[st]['A_flagged'], inap[st]['best_shown_rows'], inap[st]['best_flagged'], inap_new[st]['rows'], inap_new[st]['flagged']] for st in inap], ['set', 'A 표시 행', 'A 중 proxy 해당', 'A 표시 행 중 BEST 표시', 'BEST proxy 해당', 'BEST 가 새로 표시한 행(B 의 NON 완화 결과)', '그중 proxy 해당'])}

## 6. 원문 보존 검사(BEST, 전 {raw['rows']}행)

source_text 손실 {raw['source_text_lost']} · raw_expression 누락 {raw['raw_expression_missing']} · UNKNOWN 인데 canonical 있음 {raw['unknown_with_canonical']} · UNKNOWN 인데 후보 표시 {raw['unknown_with_displayed_candidates']} · NON 인데 canonical/후보 {raw['non_with_canonical_or_candidates']} · COMPLEX 자동 수락 {raw['complex_auto_accept']}. 상태 분포 {S.dumps(raw['status_counts'])}.

## 7. 대표 사례(탐색적 — 이 세션은 STEP26 §4 우선 사례를 본 뒤 어휘 단서를 작성, 지표·임계값에 미사용)

데이터 안(표현 포함 행, A → BEST 상태 분포):

{table(rep_tab, ['표현', '행', 'POLICY_A', best])}

데이터 밖 smoke:

{table(sm, ['입력', 'status', 'decision', '표시 후보', 'reason'])}

## 8. SILVER_CANDIDATE 442 (`data/external_silver_candidates.csv`, 사람 검증 아님)

n {sev_['n']} · 분할 {S.dumps(sev_['split_counts'])} · STEP27 상태 {S.dumps(sev_['status_counts'])}. STEP28 기계 분류 {S.dumps(s28)}(`outputs/step28_candidates.csv`).

## 9. 누수·노출

- 선택: EXT_DEV + INT_DEV_CORE 59 만. EXT_EVAL·Regression 109·KMC 는 1회 적용. EXT_DEV 비증상 점수는 STEP26 재료·fold 로 다시 만든 out-of-fold 값(STEP26 full 분류기는 EXT_DEV in-sample).
- 어휘 단서(NON_TYPE_CUE·SYMPTOM_CUE)는 일반 형태 규칙으로 작성, 개별 사례 표현(고혈압·결핵·코피) 미포함. 다만 STEP26 §4 우선 사례 16 표현을 본 상태에서 작성 → 해당 표현 결과는 탐색적. STEP26 HELD_OUT weak-symptom→NON 26건 목록은 보지 않았다.
- 판정 조항 G_N 은 EVAL 수치를 본 뒤 추가(보수 방향). 정책·임계값은 EVAL 을 본 뒤 바꾸지 않았다.
- Regression 109 는 STEP21–26 에서 여러 번 분석된 고정 집합 — blind 아님.

## 10. 핵심 질문 답

1. **false NON 개선**: EVAL weak-symptom→NON {pct(fnA)} → {pct(fnB)}(n={n_ws}). DEV(out-of-fold) {pct(v(A, 'EXT_DEV', 'WEAK_SYMPTOM|NON_SYMPTOM_rate'))} → {pct(v(B, 'EXT_DEV', 'WEAK_SYMPTOM|NON_SYMPTOM_rate'))}. 대가: weak-non→NON {pct(v(A, E, 'WEAK_NON_SYMPTOM|NON_SYMPTOM_rate'))} → {pct(v(B, E, 'WEAK_NON_SYMPTOM|NON_SYMPTOM_rate'))}, weak-non→UNCERTAIN {pct(v(A, E, 'WEAK_NON_SYMPTOM|UNCERTAIN_rate'))} → {pct(v(B, E, 'WEAK_NON_SYMPTOM|UNCERTAIN_rate'))}. 질환명(예: 고혈압·결핵 포함 행)도 NON 에서 UNCERTAIN 으로 이동(§7).
2. **UNKNOWN ↔ NON 구분**: 안정적이지 않다. NON 판정은 거의 weak-non 에만 남았지만(§4), 비증상 대부분을 NON 으로 보내지 못하고 UNCERTAIN 으로 미룬다. DEV 에서 weak-symptom→NON ≤ 3% 를 지키며 얻을 수 있는 최대 weak-non→NON 이 {pct(v(B, 'EXT_DEV', 'WEAK_NON_SYMPTOM|NON_SYMPTOM_rate'))} 였다 — 현재 문자 TF-IDF 비증상 점수의 분리력 한계. UNKNOWN 중 weak-non 비율은 §4 표.
3. **원문 보존**: 전 행 손실 0(§6). UNKNOWN 에 canonical·표시 후보 0, NON 에도 canonical 0. 실험용 구조이며 PatientState 미변경.
4. **부적절 후보 감소**: A 가 표시한 EVAL {inap['EXT_EVAL']['A_shown_rows']}행 중 proxy 해당 {inap['EXT_EVAL']['A_flagged']} → BEST {inap['EXT_EVAL']['best_flagged']}, 그러나 B 의 NON 완화로 새로 표시된 {inap_new['EXT_EVAL']['rows']}행 중 {inap_new['EXT_EVAL']['flagged']}행이 proxy 해당. weak-non 후보 표시율 {pct(v(A, E, 'WEAK_NON_SYMPTOM|candidate_display_rate'))} → {pct(v(B, E, 'WEAK_NON_SYMPTOM|candidate_display_rate'))}. '코피가 나요' smoke 는 hemoptysis 1개가 여전히 표시됨(§7) — 의미 연결 검증은 해결되지 않았다.
5. **지원 증상 자동 처리**: B4 그대로 → regression coverage {pct(v(B, R, 'auto_coverage'))}, precision {pct(v(B, R, 'auto_precision'))}(A 와 동일). regression 비자동 행의 gold 표시 {int(v(A, R, 'nonauto_gold_in_displayed'))} → {int(v(B, R, 'nonauto_gold_in_displayed'))}. 임계 변경(POLICY_E)은 DEV CV 에서 채택 조건 미달.
6. **재학습 없는 한계**: (a) 비증상 점수가 질환명과 증상 단편을 문자 수준으로만 구분 → NON 을 보수적으로 하면 질환명 인식이 무너짐 (b) 77 개 밖 증상(코피 등)은 KoE·Linear 가 가장 가까운 지원 concept 에 높은 확률을 주므로, 확률·문자 유사도만으로 '의미가 다르다'를 판단할 수 없음 (c) COMPLEX 판정이 정규식이라 regression 지원 증상 문장 {pct(v(B, R, 'COMPLEX_INPUT_rate'))} 를 COMPLEX 로 보냄 (d) 짧은 명사형 지원 증상 용어(외부의 두통·구토·발열·객혈 등)가 B4 를 통과하지 못해 UNKNOWN/UNCERTAIN 에 남음(`docs/step28_handoff.md` 주의) (e) 정확도 수치는 합성 regression·weak label 에만 근거.
7. **STEP28**: (1) 77 밖 concept 검색(HPO/SNOMED/UMLS)으로 UNKNOWN 표현에 '지원 안 됨'의 적극적 근거 제공 (2) 질환·약물·검사 사전(라이선스 확인된 용어집)으로 NON 의 적극적 근거 제공 (3) 후보 표시 전 concept 정의 수준 의미 검증 (4) 사람 라벨 Gold(누가·어떻게는 사용자 결정). `docs/step28_handoff.md`.
"""
    (S.DOCS / "safe_symptom_routing_report.md").write_text(md, encoding="utf-8")

    s28rows = S.read_csv(S.OUT / "step28_candidates.csv")
    ex = {c: [r["raw_expression"] for r in s28rows if r["machine_category"] == c][:15] for c in ("SYNONYM_GAP_CANDIDATE", "ONTOLOGY_SEARCH_CANDIDATE", "TYPE_UNCLEAR_REVIEW")}
    unk_all = [r for r in S.read_csv(S.OUT / "unknown_analysis.csv") if r["set"].startswith("EXT")]
    h = f"""# STEP28 인계 — 77 개 밖 증상의 안전한 표준화 준비

STEP28 은 자동 실행하지 않았다. 아래 목록은 기계 분류(의학적 판단·정답 아님)이며 사람 검토 전 후보다.

## 입력 파일
- `data/external_silver_candidates.csv` — BERT-NER-KO 증상(ST) span 442, 모델·B4·STEP27 출력(SILVER_CANDIDATE, human_verified=False)
- `outputs/step28_candidates.csv` — 442 중 KNOWN 아닌 고유 표현 {sum(s28.values())}: {S.dumps(s28)}
- `outputs/unknown_analysis.csv` — BEST 상태 UNKNOWN_SYMPTOM 전체(외부 {len(unk_all)}행), 내부 후보·후보 유사도 포함
- `outputs/routing_features.csv` · `routing_decisions.csv` — 정책 A–E 전체 출력

## 분류 기준(사전 고정, analyze_routing_errors.py 문서열)
- SYNONYM_GAP_CANDIDATE: 증상 근거 있음 + 내부 1순위 후보 cand_sim ≥ 0.3 + KoE 확률 ≥ 0.5 → 기존 concept 표현 보완 후보. 예: {', '.join(ex['SYNONYM_GAP_CANDIDATE']) or '—'}
- ONTOLOGY_SEARCH_CANDIDATE: 증상 근거 있음 + 위 조건 미달 → 77 밖 concept 가능성, HPO/SNOMED/UMLS 검색 대상. 예: {', '.join(ex['ONTOLOGY_SEARCH_CANDIDATE']) or '—'}
- TYPE_UNCLEAR_REVIEW: 증상 근거 없음(어휘 단서 없음·비증상 점수 ≥ 0.5) → 증상 여부부터 검토. 예: {', '.join(ex['TYPE_UNCLEAR_REVIEW']) or '—'}
- '새 concept 자체가 필요한 표현' 확정은 사람 검토 + ontology 검색 결과가 필요하다(이번 단계에서 판정하지 않음).
- **주의(생성 후 육안 확인)**: 이 기계 분류는 눈에 띄게 틀린 예가 있다 — 지원 concept 의 기본 용어(두통·구토·발열·복통)가 ONTOLOGY_SEARCH 로, 미지원 '코피가'가 SYNONYM_GAP 으로, 지원 '객혈'류가 TYPE_UNCLEAR 로 분류됐다. 짧은 명사형 지원 증상 용어가 B4 를 통과하지 못하는 것(학습 표현 유사도·KoE 확률 부족)이 원인 후보이며 확인 필요. STEP28 입력으로 쓰기 전에 분류 규칙 자체를 다시 설계해야 한다(이번 단계에서 고치지 않음).

## STEP28 설계 메모
- 기존 Linear/KoELECTRA 는 고정. 추가는 ontology 후보 검색(HPO/SNOMED/UMLS, 라이선스·로컬 보관 확인 — OFFLINE_ON_PREM_FIRST) + 후보 의미 검증 단계.
- 라우터 인터페이스(`docs/routing_schema.md`)의 UNKNOWN_SYMPTOM.raw_record 를 ontology 검색 입력으로 쓴다. 검색 결과가 있어도 사람 확인 전 canonical 로 자동 확정하지 않는다.
- STEP27 남은 문제: 질환명 NON 인식 손실, 코피류 후보 표시, COMPLEX 정규식 과잉 판정, Gold 부재.
- 금지 승계: 77 밖 증상을 77 에 끼워 맞추지 않음 · weak/SILVER 를 Gold 로 부르지 않음 · 사용자에게 대량 라벨링 요청 금지(방법은 선택지로만).
"""
    (S.DOCS / "step28_handoff.md").write_text(h, encoding="utf-8")

    files = sorted([p for p in (S.DATA.glob("*")) if p.is_file()] + [p for p in S.OUT.glob("*") if p.is_file() and p.name != "manifest.json"]
                   + [p for p in (S.STEP / "scripts").glob("*.py")] + [S.STEP / "run_all.sh"] + [p for p in S.DOCS.glob("*.md")])
    S.dump_json(S.OUT / "manifest.json", {"step": "STEP27_safe_symptom_routing", "verdict": {k: out[k] for k in ("STEP27_RESULT", "BEST_POLICY", "PRODUCTION_READY")},
                                          "inputs_sha256": insp["I1_input_sha256"],
                                          "files_sha256": {str(p.relative_to(S.STEP)): S.sha256(p) for p in files},
                                          "notes": "production·PatientState·기존 결과 미변경. 기존 모델 재학습 없음. GPU 미사용. 다운로드·유료 API 없음."})
    print(S.dumps({k: out[k] for k in out if k not in ("rules",)}))


if __name__ == "__main__":
    main()
