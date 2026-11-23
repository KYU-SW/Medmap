"""v5-2B-Research 보고서·검증 생성. 수치·표는 outputs/<RUN_ID>/*.json 에서 계산(손으로 쓰지 않음).
테스트(신규 + v5-2A.2·v5-2A.1·v5-2A·v5-1·v4·v3·v2 회귀), 기존 파일 체크섬, git 상태 → outputs/<RUN_ID>/validation.json + docs/*.md."""
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

H = Path(__file__).resolve().parent
EXP = H.parent
ROOT = EXP.parent
sys.path.insert(0, str(EXP / "hybrid_reassessment_v5_2a"))
from make_v5_2a_report import run_tests  # noqa: E402

RUN_ID = "run_20261109_03"
OUT = H / "outputs" / RUN_ID
SUITES = {"v5_2b_research": H, "v5_2a2": EXP / "hybrid_reassessment_v5_2a2", "v5_2a1": EXP / "hybrid_reassessment_v5_2a1", "v5_2a": EXP / "hybrid_reassessment_v5_2a",
          "v5_1": EXP / "hybrid_reassessment_v5_1", "v4": EXP / "hybrid_reassessment_v4", "v3": EXP / "hybrid_reassessment_v3", "v2": EXP / "hybrid_reassessment_v2"}


def load(n):
    return json.loads((OUT / n).read_text())


def preservation():
    base = {}
    for line in (H / "outputs/baseline_sha256.txt").read_text().splitlines():
        h, f = line.split(None, 1)
        base[f.strip()] = h
    now = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    before = (H / "outputs/baseline_git_status.txt").read_text().splitlines()
    return {"files_checked": len(base), "changed": [f for f, h in base.items() if (ROOT / f).exists() and hashlib.sha256((ROOT / f).read_bytes()).hexdigest() != h],
            "missing": [f for f in base if not (ROOT / f).exists()], "git_added": sorted(set(now) - set(before)), "git_disappeared": sorted(set(before) - set(now))}


def tbl(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]


def main():
    tests = {k: run_tests(d) for k, d in SUITES.items()}
    pv = preservation()
    sc, lc, tp, gf, md, rd = (load(n) for n in ("shadow_cases.json", "legacy_shadow_comparison.json", "temporal_dependency_comparison.json", "graph_flat_comparison.json",
                                                 "multidisease_research.json", "rule_discrepancy_analysis.json"))
    s = rd["summary"]
    rel = json.loads((H / "knowledge/shadow_pe_relations.json").read_text())
    val = {"run_id": RUN_ID, "tests": tests, "preservation": pv, "registry": rd["registry"], "summary": s, "active_direction_relations_engine": 0,
           "shadow_engine_active": False, "clinical_performance": "NOT_EVALUATED"}
    (OUT / "validation.json").write_text(json.dumps(val, ensure_ascii=False, indent=1), encoding="utf-8")
    comps = lc["comparisons"]
    diff_rows = [(cid, r["legacy_relation"] or "-", r["legacy_token"], r["shadow_relation"] or "-", r["shadow_token"], r["category"], "; ".join(r["drivers"])[:90])
                 for cid, rows in comps.items() for r in rows if r["category"] != "SAME_DECISION"]
    D = H / "docs"
    D.mkdir(exist_ok=True)
    # ---------- 01 baseline ----------
    (D / "01_RESEARCH_BASELINE.md").write_text("\n".join([
        "# 01 연구 기준선(PHASE 1, 읽기 전용 확인 결과)", "",
        *tbl(["대상", "실제 계약(로컬 코드 확인)", "분류", "이번 사용"], [
            ("v4 PE 카탈로그", "hybrid4.graphs.normalized_relations(): relation dict + logic.Structured(gates·required·alternatives·fallbacks·unconditional)", "REUSABLE", "Shadow 카탈로그를 같은 형식으로 별도 생성"),
            ("v4 방향 판단", "hybrid4.logic.decide(Structured, facts) — HOLD/BLOCK_ONLY_IF_TRUE 게이트, 경로 OR", "REUSABLE", "그대로 호출"),
            ("v4 임상 조건", "hybrid4.reason.evaluate_one(ev, norm, h, agg, …) — 임상 단계(phase_fact)·D-dimer 문장 조건", "REUSABLE", "세계(확률 값)별로 호출"),
            ("v4 관계 조회·입력", "Reasoner(relations, mode).find_relations / episode_inputs(graph=DiseaseKG 순회, flat=FlatRuleTable·행 필터)", "REUSABLE", "Shadow 카탈로그로 인스턴스 생성"),
            ("v4 맥락 집계", "graphs.aggregate_facts — 에피소드 전체 값 합침(시각·도구 무시)", "NEEDS_EXTENSION", "확률 관측(값·도구·시각) 보존 + 해석 세계"),
            ("v5-1 K-of-N·분류", "hybrid5.logic.eval_kofn, classification.criterion_facts_* / pericarditis_classification", "REUSABLE", "심낭염 정책 A/B/C, STRICT 임상 양상"),
            ("v5-2A 비교", "PatientGraph52.compare / collect, evidence_linker.catalog", "REUSABLE", "MI·심낭염 연구 분류, 다질환 비교"),
            ("v5-2A.1 그룹화", "grouping.build_groups, conflict.mark_conflicts, lineage", "REUSABLE", "Shadow 원시 판단 그룹화"),
            ("v5-2A.2 시간·정정", "PatientGraph522(input_log), counterfactual.replay/fixed_context, event_history.resolve_events", "REUSABLE", "정정 가상 비교·사건 해석"),
            ("v5-2B-P0 자료", "relation_review.json(인용 25건), condition_matrix.csv(33행), 반례 28", "REUSABLE", "Shadow 출처·사전 등록 기대값"),
            ("ESC 2019 Table 4 행 구조", "평탄화된 표 — 'And' 연결어는 있으나 행 배정이 발췌마다 다름(2026-11-09 재확인)", "SOURCE_UNVERIFIED", "활력징후 조합 판정 안 함"),
            ("입원·임신·항응고·YEARS·2단계", "v3 미추출", "RESEARCH_ONLY", "연구용 정규식(같은 기록 원문)"),
            ("혈역학 미기록·확률 재평가·등급→방향", "원문 처리 문구 없음", "CLINICAL_REVIEW_REQUIRED", "정책 변수로 분리"),
        ]), ""]), encoding="utf-8")
    # ---------- PE rule audit ----------
    rows = [(r["relation_id"], r["finding"], r["shadow_status"], r["legacy_counterpart"] or "-", r["conditions"].get("directional_outcome") or "방향 없음",
             ", ".join(x["summary"] for x in r["sources"])) for r in rel["relations"]]
    (D / "V5_2B_PE_RULE_AUDIT.md").write_text("\n".join([
        "# PE 규칙 감사 — Legacy v4 8관계 vs PE_SHADOW_RESEARCH", "", f"실행 {RUN_ID}. Shadow 는 engine_active=false, RESEARCH_ONLY·NOT_CLINICALLY_VALIDATED.", "",
        "## Shadow 카탈로그", "", *tbl(["Shadow 관계", "결과 상태", "Shadow 상태", "Legacy 대응", "방향", "출처(P0 인용 ID)"], rows), "",
        "## 정책 매개변수", "", f"- 혈역학: {rel['policies']['haemo']} (기본 {rel['policies']['default']['haemo']})",
        f"- 검사 전 확률: {rel['policies']['pretest']} (기본 {rel['policies']['default']['pretest']})",
        "- SHADOW_OUTCOME_INVARIANT: 기록된 확률 값 각각으로 평가해 결과가 모두 같으면 채택, 다르면 보류(같은 시각 충돌 / 시간 재평가 정책 미확인 구분). 도구가 같다고 가정하지 않음 — 결론 불변성만 확인.",
        "- LATEST_BEFORE_TEST 는 원문 근거 없는 민감도 분석용.", "",
        "## Legacy 와 다른 판단(전체)", "", *tbl(["사례", "Legacy 관계", "Legacy", "Shadow 관계", "Shadow", "분류", "조건"], diff_rows), "",
        "## 위험 반례", "", *tbl(["ID", "내용", "기대", "근거", "Shadow", "Legacy", "Legacy 불일치"],
                                 [(r["case_id"], r["title"], "/".join(r["expected_behavior"]), r["expected_behavior_basis"], "/".join(map(str, r["actual_behavior"])),
                                   "/".join(map(str, r["actual_legacy"])), r["legacy_discrepancy"]) for r in rd["new_counterexamples"]]), "",
        "P0 반례 대응: " + json.dumps(s["p0_counterexamples"], ensure_ascii=False), ""]), encoding="utf-8")
    # ---------- clinician review ----------
    def case_line(cid):
        c = sc["cases"][cid]
        txt = " / ".join(f"{r['record_id']}({r['available_at']}): {r['text']}" for r in c["records"])
        lg = "; ".join(f"{j['relation_id']}={j['direction']}({j['stage']})" for j in c["legacy"]) or "판단 없음"
        sh = "; ".join(f"{j['relation_id']}={j['direction']}({j['stage']})" for j in c["shadow"]) or "판단 없음"
        return [f"- 합성 상황 `{cid}`: {txt}", f"- Legacy v4: {lg}", f"- Shadow: {sh}"]
    Q = [("1. 혈역학 안정성 미기록", "F01", "ESC 2019 Figure 5 제목(불안정 없는 환자), Table 4(행 구조는 평탄화 텍스트에서 확정 불가)",
          "미기록을 안정으로 간주하면 실제 불안정 환자에 Figure 5 판단 적용 / 보류하면 대부분 판단 불가", "(a) 보류 (b) 활력징후 확인 시만 (c) 적용+경고 (d) 응급 의심 평가 맥락이면 안정 간주",
          "미기록 처리 문구, Table 4 행별 조건"),
     ("2. CTPA 음성 + 검사 전 확률 재평가", "E01", "§4.5 불일치 시 추가 검사, Figure 5 각주 e", "재평가 전 낮음으로 배제하거나 재평가 후 높음을 무시할 위험",
      "(a) 검사 직전 최신 평가 (b) 가장 높은 평가 (c) 보류 (d) 도구 우선순위", "재평가 규칙"),
     ("3. 서로 다른 도구의 낮음·중간", "D01", "§4.2(경험적 판단·예측 규칙 병용), 진단 절 '낮음·중간 CTPA 음성 배제'", "도구 간 동등성 가정 위험 / 결론이 같은데 보류하는 과잉 보류",
      "(a) 결론 불변이면 채택(Shadow) (b) 항상 보류(Legacy) (c) 특정 도구 우선", "도구 간 비교 기준"),
     ("4. 2단계 'PE unlikely' 와 D-dimer", "U05", "Figure 5 각주 b(중등도 민감 → 낮은 확률 또는 PE-unlikely)", "2단계를 3단계로 섞는 위험",
      "(a) 각주 b 경로만 허용(Shadow) (b) 고민감 검사에도 허용 (c) 불허", "고민감 + PE-unlikely 조합, CTPA 경로에서의 의미(U06 보류)"),
     ("5. YEARS 적용", "J01", "각주 c(항목 0 + <1000, 항목 ≥1 + <500 µg/L)", "3단계 확률 요구(Legacy 는 판단 없음) / 단위(FEU·DDU) 오해석",
      "(a) YEARS 독립 경로(Shadow) (b) 3단계도 요구 (c) 불허", "단위 규정, YEARS 항목 판정 기준, 임신 적응판"),
     ("6. 입원·임신 D-dimer", "U07", "각주 b 'limited use', §9.2.1", "입원·임신에서 정상 D-dimer 로 배제", "(a) 보류(Shadow) (b) 경고만 (c) 제외", "'limited use' 의 의미"),
     ("7. 근위부 DVT", "U02", "§4.10 '추가 검사 없이 항응고 치료에 충분'", "치료 결정을 진단 확인으로 변환(Legacy SUPPORT)", "(a) 비방향 VTE 치료 근거(Shadow) (b) 약한 SUPPORT (c) 현행",
      "PE 진단 의미를 직접 다룬 문구"),
     ("8. MI 배제 경로·허혈 근거", None, "UDMI5 §14.1.3·§14.1.5·Box 3·Box 6·§12", "단일 매우 낮은 값(분류 경로)을 'MI 기준 미충족'으로 바꾸는 위험, 흉통만으로 허혈 증상 판정",
      "(a) 분류 경로와 기준 미충족 분리(현 연구) (b) 단일 배제를 MI WEAKEN 으로", "연속 측정 적정 시점·검사법 조건, 허혈 증상 조작적 정의"),
     ("9. 심낭염 영상 계수·임상 양상", None, "ESC 2025 Table 4, §4.4.1", "영상 2항목으로 Definite / 비특이 흉통을 임상 양상으로", "정책 A/B/C, BROAD/STRICT",
      "영상 행 계수 규칙, 임상 양상 정의")]
    L = ["# 전문의 검토 패킷(v5-2B-Research)", "", "모든 항목 CLINICIAN_REVIEW_PENDING. 답변을 만들지 않는다. Legacy·Shadow 판단은 실제 실행 결과(" + RUN_ID + ").", ""]
    for title, cid, guide, risk, opts, unk in Q:
        L += [f"## {title}"] + (case_line(cid) if cid else []) + [f"- 관련 지침: {guide}", f"- 오해석 위험: {risk}", f"- 선택지: {opts}", f"- 아직 확인 못 한 사실: {unk}", ""]
    mi = md["acs_mi"]
    L += ["### 8번 관련 실행 결과(MI 연구 분류)", *tbl(["사례", "급성 손상", "Box 3", "배제 경로", "기준 미충족", "위험 분류"],
                                              [(c, v["result"][0]["research_classification"]["acute_myocardial_injury"], v["result"][0]["research_classification"]["primary_mi_box3"][:45],
                                                v["result"][0]["research_classification"]["mi_rule_out_pathway"][:45], v["result"][0]["research_classification"]["mi_criteria_not_met"][:30],
                                                v["result"][0]["research_classification"]["risk_stratification"][:28]) for c, v in mi.items()]), "",
          "### 9번 관련 실행 결과(심낭염 정책)", *tbl(["사례", "임상 양상 정책", "A(5항목)", "B(영상 1)", "C(다르면 보류)"],
                                               [(c, p.split("(")[0], x["POLICY_A_FIVE_ITEMS"], x["POLICY_B_IMAGING_MERGED"], x["POLICY_C_HOLD_IF_DEPENDS"][:25])
                                                for c, v in md["pericarditis"].items() for p, x in v["result"][0]["policies"].items()]), ""]
    (D / "V5_2B_CLINICIAN_REVIEW.md").write_text("\n".join(L), encoding="utf-8")
    # ---------- main report ----------
    t = tests
    R = ["# MedMap v5-2B-Research 보고서 — PE Shadow 비교 엔진 · 합성 조건 반례 · 다질환 연구 분류", "",
         f"실행 {RUN_ID}(이전 실행 run_20261109_01·02 보존). 수치는 outputs/{RUN_ID}/*.json 에서 계산. Shadow 결과는 RESEARCH_ONLY·NOT_CLINICALLY_VALIDATED·ENGINE_ACTIVE_FALSE. 임상 성능 NOT_EVALUATED.", "",
         "## 1. 구현", "", "- `hybrid5b/shadow_catalog.py`(격리 카탈로그·정책), `clinical_context.py`(확률 관측·2단계·혈역학 명시 문구·입원·임신·항응고·YEARS), `shadow_reasoner.py`(v4 Reasoner·evaluate_one·decide 재사용 + 확률 해석 세계), `legacy_adapter.py`, `experiment_matrix.py`, `comparison.py`, `temporal.py`(v5-2A.1 그룹화·v5-2A.2 재생 연결), `multidisease.py`, `graph_flat.py`.",
         "- 기존 코드 무수정. v4 카탈로그는 실행 전후 동일(테스트).", "",
         "## 2. 핵심 수치", "",
         f"- PE 합성 사례 {s['pe_cases']}개(그룹 A~O·U·Z) + 시간·중복·정정 6개 + MI {len(md['acs_mi'])} + 심낭염 {len(md['pericarditis'])} + 다질환 {len(md['multi_disease'])}",
         f"- 판단 수: Legacy {s['pe_judgments']['legacy']}, Shadow {s['pe_judgments']['shadow']}",
         f"- 사전 고정 기대값: PE {s['pe_expectation_checks']['pass']}/{s['pe_expectation_checks']['total']} (근거별 {s['pe_expectation_checks']['by_basis']}), 비교 분류 기대 {s['comparison_expectation_checks']['pass']}/{s['comparison_expectation_checks']['total']}, MI {s['mi_checks']['pass']}/{s['mi_checks']['total']}, 심낭염 {s['pc_checks']['pass']}/{s['pc_checks']['total']}",
         f"- P0 진리표 33행 대조: {s['p0_matrix']}", f"- P0 반례: {s['p0_counterexamples']}",
         f"- Legacy vs Shadow 분류: {s['comparison_categories']}", f"- 후보 표시: {s['candidate_flags']}", f"- 차이 조건: {s['drivers']}",
         f"- Shadow 전문의 검토 필요 판단: {s['shadow_review_required']}",
         f"- Graph vs Flat: {s['graph_flat']}", f"- 시간·중복·정정 검사: {s['temporal_checks']}",
         f"- 신규 반례 18: {s['new_counterexamples']}", f"- 레지스트리: {rd['registry']}", "",
         "## 3. 해석(규칙 적합성 — 임상 정확도 아님)", "",
         "- **Legacy 과잉 보류 후보(LEGACY_MORE_CONSERVATIVE):** 결론 불변 확률 충돌(C03·D01·D02·E02), 'high-sensitivity assay' 문구 미매핑(H02), YEARS(J01·J03), 2단계 PE-unlikely(U05).",
         "- **Legacy 성급 판단 후보:** 혈역학 미기록(F01·F02·F03), 입원·임신 D-dimer(U07·U08), 근위부 DVT SUPPORT(U02, 의미 검토), 관류 정상 WEAKEN(U01, 출처·해석 미확정).",
         "- **Shadow 의 보류 증가:** 혈역학 미기록 보류는 정책 C 의 결과이며 정책 A 에서는 사라짐(정책 민감도 표) — 원문이 미기록 처리를 말하지 않으므로 어느 쪽도 정답으로 두지 않음.",
         "- **원문 부족으로 보류:** 관류 정상 방향, 충만 결손, 낮은 확률 양성 CTPA(Table 6 미확인), 2단계 + CTPA, 혈압·승압제·저관류 조합(Table 4 행 구조 미확정).",
         "- **ACS·MI:** 급성 손상과 MI 를 분리. ECG 경로는 '새로운' 변화가 기록될 때만 Box 3 구성요소 충족으로 표시(MI 확정 아님). 단일 매우 낮은 값은 분류 경로(§14.1.3)로, 연속값 모두 기준 이하는 '기준 미충족 후보(시점 적정성 미검증)'로 따로 둠 — 두 절은 목적이 달라 모순으로 분류하지 않음.",
         "- **심낭염:** 영상 2항목 사례(PC03)에서 정책 A=DEFINITE, B=POSSIBLE → C 보류. 비특이 흉통(PC02)은 STRICT 에서 등급 미생성. CMR 미시행 음성(PC04)은 Unlikely 로 가지 않음. 등급 → 방향 변환 없음.", "",
         "## 4. 테스트·보존", "", *tbl(["묶음", "실행", "결과"], [(k, v["ran"], "OK" if v["ok"] else "FAIL") for k, v in t.items()]), "",
         f"- 기존 v1~v5-2B-P0 파일 {pv['files_checked']}개 체크섬: 변경 {len(pv['changed'])} · 누락 {len(pv['missing'])}",
         f"- git: 추가 {pv['git_added']} · 사라짐 {pv['git_disappeared']}", "",
         "## 5. 발견·수정한 기술 결함(신규 코드 범위)", "",
         "- 카탈로그: D-dimer 의 확률 게이트를 HOLD 로 두어 2단계 경로가 막힘 → BLOCK_ONLY_IF_TRUE 로 수정(경로 자체가 확률을 요구하므로 중복 보류 제거). [RULE_SEMANTIC_ERROR]",
         "- 실행 연결: 반례 참조 키(MI08)와 사례 키(MI08_new_ecg_change) 불일치 → 접두어 매칭. [CODE_BUG]",
         "- 시간 검사 8번: as_of 3.0(판독 공개 4.0 전)에 SUPPORT 를 기대한 검사 작성 오류 → 공개 전 판단 없음 + 5.0 SUPPORT + 8.0 WEAKEN 으로 강화(run_01 은 실패 상태로 보존). [EXPECTATION_UNSUPPORTED]",
         "- 뮤테이션 7종 중 'ECG 새로움 무시' 미검출 → 사례 MI13 추가 후 검출(사후 추가 명시). 나머지 6종은 처음부터 검출.",
         "- P0 진리표 9행에 대응 사례가 없어 Z01~Z09 추가(기대값 = P0 사전 등록 후보 판단) → 33/33 일치.", "",
         "## 6. 남은 기술 문제", "",
         "- 활력징후 기반 혈역학 판정(Table 4 행 구조 확정 필요), 확률 평가 시각은 기록 공개 시각만 사용, YEARS 항목·단위 추출은 연구용 정규식(실제 기록 표현 범위 미검증).",
         "- MI·심낭염 연구 분류는 v5-2A 그래프 경로만 사용(Graph/Flat 동일성은 v5-2A 에서 32/32 확인된 하위 계층에 의존).",
         "- 문맥 의존 Legacy 판단의 원인 귀속은 v5-2A.2 사건 이력에 연결 가능하나 Shadow 이력에는 아직 사건별 귀속 표를 만들지 않음.", "",
         "## 7. 의학적 미검증 · 확인 수준", "",
         "- 원문: UDMI5 로컬 전문(직접), ESC 2019·2025 는 OUP 발췌(요약 모델 경유), Table 4 행 구조·Table 6·권고표 미확인, 미국 지침 2종 미비교.",
         "- 문헌 기대값도 임상 정답이 아님. 전문의 검토 전 — 모든 연구용 방향 라벨은 비활성.", ""]
    (D / "V5_2B_RESEARCH_REPORT.md").write_text("\n".join(R), encoding="utf-8")
    N = ["# 다음 결정(v5-2B-Research 이후)", "",
         "## 바로 다음 1순위", "- 전문의 패킷 1~3번(혈역학 미기록, 확률 재평가, 도구 다른 확률) 답변 확보 → Shadow 정책 기본값 확정.", "",
         "## 승인 가능한 연구 기능(제안, 미실행)",
         "- Shadow 정책 기본값을 전문의 답변으로 고정한 'Research 카탈로그 v1'(여전히 engine_active=false).",
         "- 활력징후 추출기(혈압·승압제·저관류·심정지) — Table 4 원문 표 이미지 확인 후.",
         "- 확률 평가 시각 추출(기록 공개 시각과 분리).", "",
         "## 미검증 관계(활성화 금지 유지)",
         "- SH-CTPA-POS/NEG, SH-DD-NORMAL, SH-DD-YEARS(연구용 방향 라벨), 관류 정상(방향 보류), 근위부 DVT(비방향), MI Box 3 ECG 경로, 심낭염 등급.", "",
         "## 필요한 데이터",
         "- 판단 시점별 의사 작업 진단, 혈역학·확률 평가 시각, 검사 사건 ID·정정 이력, 최종 진단 판정(위원회). 제한 자료 접근은 별도 승인·IRB 확인 필요.", "",
         "## 후속 검증 계획",
         "- 전문의 답변 → 정책 고정 → 같은 합성 사례 재실행(새 RUN_ID) → 차이 재분류 → 소규모 비식별 실제 기록에서 규칙 적합성만 확인(성능 주장 없이).", ""]
    (D / "V5_2B_NEXT_DECISION.md").write_text("\n".join(N), encoding="utf-8")
    print(json.dumps({k: (v["ran"], v["ok"]) for k, v in tests.items()}), "changed", len(pv["changed"]), "missing", len(pv["missing"]), "git+", pv["git_added"], "git-", pv["git_disappeared"])


if __name__ == "__main__":
    main()
