"""SUBAGENT C - 무작위 60건 수동 대조 판정(작성자: SUBAGENT C, 단일 비전문가 판독) + error_cases.csv + 유형/원인 집계.
판정은 '이의 후보'이며 정답 수정이 아님. 전문가 검토 전에는 [연구 가설] 수준.
"""
from __future__ import annotations

import collections
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path("/home/<user>/medmap-guidelinecoordination-repro-20261118")
OUT = ROOT / "C-error-analysis"
GOLD_REF = "upstream/GuidelineCoordination/rules_gold.json"

# 18 후보 유형 (과대/과소 분리)
T = {
    "T01": "필수 조건 누락", "T02": "과대 적용", "T03": "과소 적용", "T04": "AND/OR 오류", "T05": "부정 오류",
    "T06": "예외 누락", "T07": "용어 연결 오류", "T08": "시간 조건 누락", "T09": "비교 연산자 오류", "T10": "단위 오류",
    "T11": "환자 조건 혼합", "T12": "권고/근거 혼동", "T13": "지침에 없는 조건 추가", "T14": "충돌 유형 오분류",
    "T15": "중복 vs 충돌 혼동", "T16": "근거 부족을 충돌로", "T17": "논리 표현 불완전", "T18": "의학 지식 부족",
}
# 표본 판정: order -> (verdict, types, cause_primary, cause_secondary, wrong_part)
# verdict: ISSUE(실질), MINOR(경미/형식), AMBIGUOUS(원문 모호), OK
S = {
    1: ("ISSUE", "T07;T03", "D", "F", "GDMT 를 ACEI/ARNI/ARB/BB/MRA 로만 연결, SGLT2i 누락 가능(2024 중국 심부전 지침 GDMT 범위 확인 필요)"),
    2: ("OK", "", "", "", ""), 3: ("OK", "", "", "", ""),
    4: ("ISSUE", "T13;T03", "C", "F", "원문에 없는 pred.on_gliclazide 추가(현재 복용자로 축소); '不建议使用或禁用'→avoid 는 원문 이중표현"),
    5: ("ISSUE", "T07;T02;T08", "B", "C", "'二甲双胍或其与SGLT2i的FDC' 를 subjects 집합 [sglt2, metformin] 로 분해→SGLT2i 단독에도 적용; '检查前和检查时' 시점 누락"),
    6: ("OK", "", "", "", ""),
    7: ("ISSUE", "T07;T02;T01", "B", "C", "'SGLT2i或SGLT2i/二甲双胍FDC' 를 [sglt2, metformin] 로 분해→metformin 단독 recommend 로 해석 가능; 'eGFR使用限制' 교차참조 누락"),
    8: ("OK", "", "", "", ""),
    9: ("MINOR", "T06", "B", "", "'除非有禁忌证或不能耐受' 예외 미표현(암묵적 예외)"),
    10: ("MINOR", "", "C", "", "requirements 에 pred.dose_reduction_half(술어 ID) 혼입 — 형식 불일치, 논리 영향 없음"),
    11: ("OK", "", "", "", ""),
    12: ("ISSUE", "T01;T02", "C", "A", "'以改善血糖控制'(혈당 목적) 한정 누락→신장/심장 보호 목적 사용까지 avoid 로 확장"),
    13: ("OK", "", "", "", ""), 14: ("OK", "", "", "", ""), 15: ("OK", "", "", "", ""),
    16: ("ISSUE", "T13;T03", "C", "F", "#4 와 동일 패턴: pred.on_gliquidone 추가"),
    17: ("OK", "", "", "", ""),
    18: ("MINOR", "T13", "F", "C", "'对于…患者使用二甲双胍普通片' 를 pred.on_metformin 으로 표현(같은 출처 #12 는 on_ 미사용 — 표현 불일치)"),
    19: ("OK", "", "", "", ""), 20: ("OK", "", "", "", ""), 21: ("OK", "", "", "", ""), 22: ("OK", "", "", "", ""),
    23: ("OK", "", "", "", ""), 24: ("OK", "", "", "", ""),
    25: ("ISSUE", "T07;T08", "C", "", "같은 quote 의 #5 는 [sglt2, metformin], 본 규칙은 [metformin] 만 — 동일 원문 subjects 불일치, 시점 누락"),
    26: ("MINOR", "T13", "F", "C", "#18 과 동일(on_metformin_er)"),
    27: ("ISSUE", "T17", "B", "", "모니터링 권고를 caution 으로 근사 — action 어휘에 monitor 없음"),
    28: ("OK", "", "", "", ""), 29: ("OK", "", "", "", ""), 30: ("OK", "", "", "", ""),
    31: ("ISSUE", "T01;T02", "C", "A", "'心肾风险仍需进一步管理' 조건 누락→모든 SGLT2i 사용자에게 finerenone recommend"),
    32: ("AMBIGUOUS", "T01", "UNKNOWN", "F", "非奈利酮 共识의 대상 집단(CKD+T2D 등) 맥락이 condition 에 없음 — 절 제목 확인 필요"),
    33: ("AMBIGUOUS", "", "F", "", "'不建议使用或禁用' → avoid (contraindicate 도 가능)"),
    34: ("MINOR", "T07", "C", "", "subject ID med.class.sglt2i(10건) vs 다수 med.class.sglt2(154건) 변형 — analyzer 정확일치라 상호 미연결"),
    35: ("OK", "", "", "", ""), 36: ("OK", "", "", "", ""), 37: ("OK", "", "", "", ""),
    38: ("ISSUE", "T12;T13;T03", "B", "C", "'使用SGLT2i前建议评估低血糖风险' 를 SGLT2i recommend 로 변환(권고 대상 혼동); '特别是' 를 필수 AND 조건으로"),
    39: ("ISSUE", "T17;T01", "B", "", "'2种甚至3种…联合' 병용 의미 소실(5개 약 각각 recommend); '采用一种降糖药治疗' 맥락 누락"),
    40: ("ISSUE", "T17;T02", "B", "", "'SGLT2i联合二甲双胍' 병용 회피를 subjects 집합으로→metformin 단독 회피로도 해석"),
    41: ("MINOR", "T17", "B", "C", "'逐步减量或停用' 중 停用 누락, '优先考虑' 강도 소실"),
    42: ("OK", "", "", "", ""),
    43: ("ISSUE", "T08;T02", "B", "C", "'不建议开始使用'(개시만 금지) → avoid, 개시/지속 구분 소실"),
    44: ("OK", "", "", "", ""), 45: ("OK", "", "", "", ""),
    46: ("MINOR", "T17", "B", "", "'可尝试' 강도, '或种类'(약 가짓수 감소) 소실"),
    47: ("OK", "", "", "", ""), 48: ("OK", "", "", "", ""), 49: ("OK", "", "", "", ""), 50: ("OK", "", "", "", ""),
    51: ("OK", "", "", "", ""), 52: ("OK", "", "", "", ""), 53: ("OK", "", "", "", ""), 54: ("OK", "", "", "", ""),
    55: ("OK", "", "", "", ""), 56: ("OK", "", "", "", ""), 57: ("OK", "", "", "", ""),
    58: ("MINOR", "T07", "C", "", "id 는 vildagliptin, subject 는 med.kaogelieting(병음 ID, 표준코드 아님) — 메타데이터 불일치"),
    59: ("OK", "", "", "", ""),
    60: ("ISSUE", "T01;T02", "C", "A", "id 에 t2dm_ckd 가 있으나 condition 은 intolerant_to_acei_arb 단독→CKD 맥락 누락(논문 Contextual Loss 와 동일 형태)"),
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(c - h, 4), round(c + h, 4)


def main() -> None:
    raw = pd.read_csv(OUT / "gold_audit_sample60_raw.csv", keep_default_na=False)
    assert len(raw) == 60 and set(S) == set(range(1, 61))
    raw["verdict"] = raw.sample_order.map(lambda i: S[i][0])
    raw["error_types"] = raw.sample_order.map(lambda i: ";".join(f"{t}:{T[t]}" for t in filter(None, S[i][1].split(";"))))
    raw["cause_primary"] = raw.sample_order.map(lambda i: S[i][2])
    raw["cause_secondary"] = raw.sample_order.map(lambda i: S[i][3])
    raw["wrong_part"] = raw.sample_order.map(lambda i: S[i][4])
    raw["annotator"] = "SUBAGENT_C(single, non-expert)"
    raw.to_csv(OUT / "gold_audit_sample60_annotated.csv", index=False, encoding="utf-8-sig")

    vc = raw.verdict.value_counts().to_dict()
    k_issue = vc.get("ISSUE", 0)
    k_any = k_issue + vc.get("MINOR", 0) + vc.get("AMBIGUOUS", 0)
    stats = {"verdicts": vc, "ISSUE_rate": round(k_issue / 60, 4), "ISSUE_wilson95": wilson(k_issue, 60),
             "ISSUE+MINOR+AMBIG_rate": round(k_any / 60, 4), "any_wilson95": wilson(k_any, 60)}

    # ---------- error_cases ----------
    cases = []

    def add(**kw):
        base = dict(case_id="", source_kind="", ref_file="", ref_id="", ref_field="", gold_value="", system_output="없음(예측 파일 미공개)",
                    wrong_part="", error_types="", stage="", evidence_location="", reproducible="", fixable_existing_tech="",
                    expert_review_needed="", cause_primary="", cause_secondary="", multi_label="", tag="")
        base.update(kw)
        base["multi_label"] = "Y" if (";" in base["error_types"] or base["cause_secondary"]) else "N"
        cases.append(base)

    paper = "arXiv:2604.17340v1 HTML, Results > Evaluation of Formalization Accuracy (절 번호 없음)"
    add(case_id="P01", source_kind="PAPER_REPORTED", ref_file=paper, ref_field="Contextual Loss (56.7%, 63 cases)",
        gold_value="(논문 예) 'Treatment for T2DM' 절의 권고 → pred.has_t2dm 포함", system_output="(논문 예) pred.has_t2dm 누락",
        wrong_part="절 제목의 암묵적 진단 맥락 누락 → 규칙 과대 적용", error_types="T01:필수 조건 누락;T02:과대 적용", stage="술어 생성/규칙 조립",
        evidence_location=paper, reproducible="N(개별 사례 미공개)", fixable_existing_tech="부분(절 제목·문서 구조를 입력에 포함)",
        expert_review_needed="N", cause_primary="C", cause_secondary="A", tag="[원문으로 확인한 사실]")
    add(case_id="P02", source_kind="PAPER_REPORTED", ref_file=paper, ref_field="Entity Grounding Failure (19.6%, 23 cases)",
        gold_value="정확한 gliflozin/RxNorm 코드", system_output="(논문 서술) gliflozin 간 혼동, 상품명→RxNorm 연결 실패",
        wrong_part="약물 개체 환각·오분류", error_types="T07:용어 연결 오류", stage="개체 연결(Entity Agent)", evidence_location=paper,
        reproducible="N", fixable_existing_tech="가능(사전 기반 정규화, RxNorm API)", expert_review_needed="N", cause_primary="A", cause_secondary="C",
        tag="[원문으로 확인한 사실]")
    add(case_id="P03", source_kind="PAPER_REPORTED", ref_file=paper, ref_field="Predicate Distortion (12.6%, 14 cases)",
        gold_value="원문 조건", system_output="(논문 서술) 없는 조건 환각, 중요 제외조건 누락, 수치 연산자 반전",
        wrong_part="술어 왜곡", error_types="T13:지침에 없는 조건 추가;T06:예외 누락;T09:비교 연산자 오류", stage="술어 생성(Predicate Agent)",
        evidence_location=paper, reproducible="N", fixable_existing_tech="부분(수치 정규식 검증, 원문 대조 규칙)", expert_review_needed="N",
        cause_primary="A", cause_secondary="C", tag="[원문으로 확인한 사실]")
    add(case_id="P04", source_kind="PAPER_REPORTED", ref_file=paper, ref_field="Action Alignment Error (8.1%, 9 cases)",
        gold_value="should be considered → Consider", system_output="(논문 예) Recommend; Avoid↔Contraindicate 혼동",
        wrong_part="권고 강도·방향 오정렬", error_types="T12:권고/근거 혼동", stage="규칙 조립(Rule Agent)", evidence_location=paper,
        reproducible="N", fixable_existing_tech="가능(양상 동사 사전 매핑)", expert_review_needed="부분", cause_primary="A", cause_secondary="F",
        tag="[원문으로 확인한 사실]")
    add(case_id="P05", source_kind="PAPER_REPORTED", ref_file=paper, ref_field="오류 분모·합계",
        gold_value="111 errors / 565 rules", system_output="범주 합 63+23+14+9=109; 비율 합 97.0%; 23/111=20.7%(표기 19.6%); 111/565=19.65%(표기 19.9%); 80.1%→오류 112.4건",
        wrong_part="보고 수치 내부 불일치", error_types="", stage="보고/평가", evidence_location=paper, reproducible="Y(산술 재계산)",
        fixable_existing_tech="가능(저자 정정)", expert_review_needed="N", cause_primary="G", tag="[실제 실행해 확인한 결과]")

    # 구조적·체계적 관찰(정답 파일 + 코드)
    add(case_id="G01", source_kind="GOLD_OBSERVED", ref_file=GOLD_REF,
        ref_id="rule.ckd_egfr_lt_15_or_dialysis_continue_sglt2 / rule.ckd_egfr_lt_15_or_dialysis_stop_sglt2", ref_field="condition, action.permission",
        gold_value="두 규칙 condition 동일: pred.has_ckd AND (pred.egfr_lt_15 OR pred.on_dialysis) AND pred.on_sglt2i; permission continue vs stop",
        wrong_part="한 문장('应停用SGLT2i，但若已使用SGLT2i可继续维持使用至透析或肾移植')의 예외 구조를 같은 집단의 continue/stop 두 규칙으로 표현 → 인위적 Intrinsic Conflict. 논문 Table 2 Intrinsic 예시와 동일하며 논문은 '지침 버전·근거 해석 차이'로 설명",
        error_types="T06:예외 누락;T08:시간 조건 누락;T14:충돌 유형 오분류", stage="규칙 조립 → 관계 추론 → 결과 해석",
        evidence_location="gold_audit_lexical_intrinsic_conflicts.csv; 논문 Table 2", reproducible="Y", fixable_existing_tech="가능(stop 규칙에 NOT pred.on_sglt2i 또는 개시/지속 구분)",
        expert_review_needed="Y(원문 의미 확정)", cause_primary="F", cause_secondary="C", tag="[실제 실행해 확인한 결과]")
    add(case_id="G02", source_kind="GOLD_OBSERVED", ref_file=GOLD_REF, ref_id="rule.dapagliflozin_egfr_lt_25_avoid_initiation", ref_field="condition, action.permission",
        gold_value="label '不推荐起始达格列净治疗', condition 'pred.egfr_lt_25 AND pred.on_dapagliflozin', permission continue",
        wrong_part="id/label 은 '개시 금지'인데 내용은 continue 규칙 복제 → '개시 금지' 규칙이 정답에 없음, 거짓 Complete Redundancy 3중(동일 condition·subject·permission 3건)",
        error_types="T12:권고/근거 혼동;T15:중복 vs 충돌 혼동;T08:시간 조건 누락", stage="정답 구축(수동 교정)", evidence_location="gold_audit_duplicates.csv; gold_audit_rule_checks.csv",
        reproducible="Y", fixable_existing_tech="가능", expert_review_needed="N", cause_primary="E", cause_secondary="C", tag="[실제 실행해 확인한 결과]")
    add(case_id="G03", source_kind="GOLD_OBSERVED", ref_file=GOLD_REF, ref_id="rule.diabetes_annual_cvd_risk_assessment_require", ref_field="action.subjects, provenance.source",
        gold_value="subjects ['nan'], source ''", wrong_part="결측값이 문자열 'nan' 으로 직렬화, 출처 비어 있음(빈 source 3건)",
        error_types="", stage="정답 직렬화", evidence_location="gold_audit_rule_checks.csv", reproducible="Y", fixable_existing_tech="가능",
        expert_review_needed="N", cause_primary="E", tag="[실제 실행해 확인한 결과]")
    add(case_id="G04", source_kind="GOLD_OBSERVED", ref_file=GOLD_REF, ref_id="(다수) med.class.sglt2 154건 vs med.class.sglt2i 10건 외 6쌍", ref_field="action.subjects",
        gold_value="같은 약물 계열에 서로 다른 ID", wrong_part="pipeline/analyzer.py L417-L432 는 subjects 를 정확 문자열 교집합으로 비교 → ID 변형·계열(class) vs 개별약 간 관계는 INDEPENDENT 처리. 정확일치 겹침 쌍 16,598 vs 계열 확장 시 41,427(2.50배), 상충 action 쌍 6,875 vs 17,627",
        error_types="T07:용어 연결 오류;T03:과소 적용", stage="개체 연결 + 관계 추론(평가 코드)", evidence_location="gold_audit_med_id_variants.csv; gold_audit_extra_summary.json; pipeline/analyzer.py",
        reproducible="Y", fixable_existing_tech="가능(ATC/RxNorm 계층 확장)", expert_review_needed="N", cause_primary="G", cause_secondary="C", tag="[실제 실행해 확인한 결과]")
    add(case_id="G05", source_kind="GOLD_OBSERVED", ref_file=GOLD_REF, ref_id="(다수) 394개 술어 중 237개(60.2%) 1회 사용", ref_field="condition",
        gold_value="같은 개념 다른 이름: has_ckd/has_renal_insufficiency/has_renal_impairment/renal_impairment/ckd_adult; ckd_stage_3a vs has_ckd_stage_3a; has_severe_liver_impairment/severe_liver_impairment/has_servere_liver_impairment(오타) 등",
        wrong_part="술어 의미는 미공개 predicates.json(formal_definition)에 의존 → 이름 변형이 Z3 에서 같은 변수로 합쳐지는지 확인 불가. 합쳐지지 않으면 관계 누락",
        error_types="T07:용어 연결 오류", stage="술어 생성(Predicate Agent)·정답", evidence_location="gold_audit_similar_predicates.csv; gold_audit_synonym_groups.csv",
        reproducible="Y(이름 수준)", fixable_existing_tech="가능(술어 정규화 사전)", expert_review_needed="부분", cause_primary="C", cause_secondary="B", tag="[실제 실행해 확인한 결과] + [아직 검증하지 못한 사항](의미 동치)")
    add(case_id="G06", source_kind="GOLD_OBSERVED", ref_file=GOLD_REF, ref_id="(신기능 관련 16건; 제한 permission+on_<같은 약> 전체 24건) 예: rule.ckd_4_5_gliclazide_avoid, rule.t2dm_egfr_lt_25_hf_ckd_no_dialysis_avoid_dapagliflozin", ref_field="condition",
        gold_value="신기능 단계 제한 규칙에 pred.on_<같은 약> 추가; 같은 출처의 acarbose/miglitol/voglibose 규칙은 미추가",
        wrong_part="원문에 '현재 복용' 표현 없는데 대상 축소(신기능 관련 16건 중 원문에 正在/已使用/期间 류 단어 0건; 전체 24건 중 1건[rule.monitor_aki_risk]만 있음, 24건엔 약물상호작용 규칙처럼 정당한 on_ 사용 포함). 표현 불일치",
        error_types="T13:지침에 없는 조건 추가;T03:과소 적용", stage="술어 생성·정답", evidence_location="gold_audit_rule_checks.csv(check=on_subject_in_condition_with_restrictive_perm)",
        reproducible="Y", fixable_existing_tech="가능", expert_review_needed="부분", cause_primary="C", cause_secondary="F", tag="[실제 실행해 확인한 결과]")
    add(case_id="G07", source_kind="GOLD_OBSERVED", ref_file=GOLD_REF, ref_id="(34건) gold_audit_glycemic_purpose.csv", ref_field="condition",
        gold_value="원문 '…进行血糖控制/以改善血糖控制' 64건 중 34건이 condition 에 혈당 관련 술어 없음(그중 SGLT2 계열 제한 permission 9건)",
        wrong_part="목적 한정어 누락 → 신장·심장 보호 목적 SGLT2i 권고와 거짓 Local/Implication Conflict 생성 가능",
        error_types="T01:필수 조건 누락;T02:과대 적용", stage="술어 생성·정답", evidence_location="gold_audit_glycemic_purpose.csv", reproducible="Y",
        fixable_existing_tech="가능(pred.treatment_for_glycemic_control 은 이미 7건에서 사용 중)", expert_review_needed="Y", cause_primary="C", cause_secondary="A",
        tag="[실제 실행해 확인한 결과] + [연구 가설](충돌 수 영향)")
    add(case_id="G08", source_kind="GOLD_OBSERVED", ref_file=GOLD_REF, ref_id="(9쌍) gold_audit_duplicates.csv dup_type=same_condition_subjects_DIFFERENT_permission", ref_field="action.permission",
        gold_value="예: rule.t1dm_avoid_sglt2i(avoid) vs rule.t1dm_contraindicate_sglt2(contraindicate), 같은 출처; rule.egfr_lt_30_metformin_contraindicate vs rule.ckd_egfr_lt_30_avoid_metformin",
        wrong_part="같은 집단·약물에 avoid/contraindicate 공존 — analyzer 는 둘 다 PROHIBIT 로 같은 범주. 원문 '不建议使用或禁用' 처럼 이중표현이 원인인 경우 존재",
        error_types="T12:권고/근거 혼동;T15:중복 vs 충돌 혼동", stage="규칙 조립·정답", evidence_location="gold_audit_duplicates.csv", reproducible="Y",
        fixable_existing_tech="부분", expert_review_needed="Y", cause_primary="F", cause_secondary="E", tag="[실제 실행해 확인한 결과]")
    add(case_id="G09", source_kind="GOLD_OBSERVED", ref_file="upstream/GuidelineCoordination/pipeline/z3env.py L34-L52; standard_library.py; analyzer.py L1675",
        ref_id="-", ref_field="Duration/Assess 연산자, predicates.json",
        gold_value="z3env: Duration·Assess 는 UNSUPPORTED_OPERATORS, Stage·Risk 는 상호배타 처리; predicates.json/terms.json/meds.json 저장소에 없음",
        wrong_part="시간 조건과 임상평가 조건은 Z3 비교 불가 → 시간 관련 충돌·포함관계 판정 불가. 정답 규칙의 술어 정의 부재로 Z3 재실행 불가",
        error_types="T08:시간 조건 누락;T17:논리 표현 불완전", stage="관계 추론(평가 코드)", evidence_location="pipeline/z3env.py", reproducible="Y(코드 열람)",
        fixable_existing_tech="부분", expert_review_needed="N", cause_primary="B", cause_secondary="G", tag="[원문으로 확인한 사실]")
    add(case_id="G10", source_kind="GOLD_OBSERVED", ref_file=GOLD_REF, ref_id="(14 문자열) provenance.source", ref_field="provenance.source",
        gold_value="출처 문자열 14종: '…二甲双胍治疗2型糖尿病专家共识（2023版）'(35) 과 '…（2023）'(29) 이 별도, 빈 문자열 3건; 논문은 12개 지침. 규칙 수 563 vs 논문 감사 565",
        wrong_part="출처 표기 불일치·결측, 규칙 수 2건 차이(원인 확인 필요)", error_types="", stage="정답 구축", evidence_location="gold_audit_sources_in_gold.csv",
        reproducible="Y", fixable_existing_tech="가능", expert_review_needed="N", cause_primary="E", tag="[실제 실행해 확인한 결과]")
    add(case_id="G11", source_kind="GOLD_OBSERVED", ref_file=GOLD_REF, ref_id="(정답 전체) recommendation_grade/evidence_level", ref_field="provenance",
        gold_value="grade 'None' 437/563(77.6%), evidence 'None' 426/563(75.7%); 표기 혼재 IIa/II a, IIb/II b/Ⅱb, 1/2 vs I/II, '强推荐','推荐'",
        wrong_part="근거 수준 정보 부족·비표준 → 권고 강도 기반 충돌 우선순위 판단에 쓰기 어려움", error_types="T12:권고/근거 혼동", stage="정답 구축",
        evidence_location="gold_audit_grade_by_permission.csv", reproducible="Y", fixable_existing_tech="가능", expert_review_needed="N", cause_primary="E", cause_secondary="F",
        tag="[실제 실행해 확인한 결과]")

    add(case_id="G12", source_kind="GOLD_OBSERVED", ref_file=GOLD_REF, ref_id="rule.linagliptin_child_pugh_a_allow, rule.linagliptin_ckd4_caution, rule.linagliptin_ckd5_contraindicate, rule.linagliptin_ckd3a_3b_reduce_dose, rule.vildagliptin_renal_insufficiency_all_stages", ref_field="id vs action.subjects",
        gold_value="id 는 linagliptin/vildagliptin, subjects 는 med.ruigeliptin(瑞格列汀)/med.kaogelieting(考格列汀)", wrong_part="id(약물명)와 subject 불일치 5건; subject 는 원문과 일치하나 병음 기반 비표준 ID(RxNorm 연결 불가 가능)",
        error_types="T07:용어 연결 오류", stage="개체 연결·정답 메타데이터", evidence_location="rules_gold.json 해당 id", reproducible="Y", fixable_existing_tech="가능",
        expert_review_needed="N", cause_primary="E", cause_secondary="C", tag="[실제 실행해 확인한 결과]")
    add(case_id="G13", source_kind="GOLD_OBSERVED", ref_file=GOLD_REF, ref_id="rule.semaglutide_liver_allow, rule.linagliptin_child_pugh_a_allow, rule.hfref_safe_continue_sglt2i, rule.su_met_combination_young_good_beta_cell", ref_field="provenance.recommendation_grade vs action.permission",
        gold_value="recommendation_grade 'III' 인데 permission allow/continue/recommend (III 전체 16건 중 4건)", wrong_part="ESC 식 Class III(권고하지 않음/해로움)이면 방향 모순; 해당 지침의 III 정의는 확인 필요. su_met 규칙은 'SU或GLN' 중 GLN, '初诊HbA1c较高' 조건도 누락",
        error_types="T12:권고/근거 혼동;T01:필수 조건 누락", stage="정답 구축", evidence_location="gold_audit_grade_by_permission.csv", reproducible="Y",
        fixable_existing_tech="가능", expert_review_needed="Y", cause_primary="E", cause_secondary="UNKNOWN", tag="[실제 실행해 확인한 결과] + [아직 검증하지 못한 사항](III 정의)")

    # 표본 사례
    raw_iss = raw[raw.verdict != "OK"]
    for _, r in raw_iss.iterrows():
        add(case_id=f"S{int(r.sample_order):02d}", source_kind="GOLD_SAMPLE60", ref_file=GOLD_REF, ref_id=r.id, ref_field="condition/action vs provenance.quote",
            gold_value=f"C: {r.condition} | S: {r.subjects} | P: {r.permission}", wrong_part=r.wrong_part, error_types=r.error_types,
            stage="정답(수동 교정 후 추정) 형식화", evidence_location=f"gold_audit_sample60_annotated.csv order={int(r.sample_order)}; quote: {r.quote}",
            reproducible="Y(원문 대조)", fixable_existing_tech="가능" if r.verdict in ("ISSUE", "MINOR") else "원문 해석 필요",
            expert_review_needed="Y" if r.verdict in ("ISSUE", "AMBIGUOUS") else "N", cause_primary=r.cause_primary or "UNKNOWN",
            cause_secondary=r.cause_secondary, tag=f"[연구 가설](단일 비전문가 판독, {r.verdict})")
    cdf = pd.DataFrame(cases)
    cdf.to_csv(OUT / "error_cases.csv", index=False, encoding="utf-8-sig")

    # ---------- 집계: 표본 60건 기준 ----------
    tcount = collections.Counter()
    for et in raw.error_types:
        for t in filter(None, et.split(";")):
            tcount[t] += 1
    type_rows = [{"type": f"{k}:{v}", "n_rules_sample60": tcount.get(f"{k}:{v}", 0),
                  "pct_of_60": round(100 * tcount.get(f"{k}:{v}", 0) / 60, 1),
                  "pct_of_nonOK": round(100 * tcount.get(f"{k}:{v}", 0) / max(1, (raw.verdict != 'OK').sum()), 1)} for k, v in T.items()]
    pd.DataFrame(type_rows).to_csv(OUT / "error_type_counts_sample60.csv", index=False, encoding="utf-8-sig")
    ccount = raw[raw.verdict != "OK"].cause_primary.replace("", "UNKNOWN").value_counts().to_dict()
    stats.update({"type_counts": dict(tcount), "cause_primary_counts_nonOK": ccount,
                  "n_multi_type_nonOK": int(sum(1 for et in raw[raw.verdict != 'OK'].error_types if et.count(";") >= 1)),
                  "n_cases": len(cdf), "cases_by_kind": cdf.source_kind.value_counts().to_dict()})
    (OUT / "sample60_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
