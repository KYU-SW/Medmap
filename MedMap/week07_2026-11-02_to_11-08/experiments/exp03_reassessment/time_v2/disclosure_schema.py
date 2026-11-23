"""EXP-03-TIME v2 공개 집계 칸 관계의 선언(스키마·프로토콜 기반) — PROTOCOL_TIME_v2.md §9-3.

원칙: 관계는 칸의 정의(PROTOCOL §3–§6)에서 나온 것만 적는다. 합성·실제 자료에서 우연히 성립한 수치 관계는 규칙으로 쓰지 않는다.
합성 자료의 역할은 (1) 여기 선언이 틀리지 않았는지 시험, (2) 선언이 빠뜨린 관계를 찾아 그 칸을 공개 범위에서 빼는 것뿐이다(build_relations_v3).
독립성: 파이프라인·보호 코드(public_v2·disclosure_v2·run·records_v2)와 묶음 G 를 import 하지 않는다.
"""
from __future__ import annotations

ST, S1, S2 = "STRICT_AVAILABLE_TIME", "S1_TRIAGE_AT_INTIME_APPROX", "S2_STRICT_A_ONLY"
POLS = (ST, S1, S2)
TS = ("T0", "T1", "T2")
SRCS = ("lab", "rad", "triage", "ecg")
FLAGS = ("OK", "POST_ED", "UNKNOWN_AVAILABILITY", "TIME_CONFLICT", "NOT_IDENTIFIABLE", "EXCLUDED_BY_POLICY", "APPROX_INTIME")
GRADES = ("A_DOCUMENTED_AVAILABILITY", "B_CONSERVATIVE_PROXY", "C_UNKNOWN_OR_CONFLICT")
GC = GRADES[2]
STATES = ("NO_HYPOTHESIS", "CONFLICT", "SUPPORTED", "INSUFFICIENT", "UNKNOWN", "PENDING")
CATS = ("NO_HYPOTHESIS", "CONFLICT_R2", "SUPPORTED_R1", "SUPPORTED_R7", "INSUFFICIENT_R3", "INSUFFICIENT_NO_DECISIVE", "UNKNOWN_R4R5", "PENDING")
SUMMARY_OF = {"NO_HYPOTHESIS": "NO_HYPOTHESIS", "CONFLICT_R2": "CONFLICT", "SUPPORTED_R1": "SUPPORTED", "SUPPORTED_R7": "SUPPORTED",
              "INSUFFICIENT_R3": "INSUFFICIENT", "INSUFFICIENT_NO_DECISIVE": "INSUFFICIENT", "UNKNOWN_R4R5": "UNKNOWN", "PENDING": "PENDING"}
DECISIVE = ("CONFLICT_R2", "SUPPORTED_R1")
LOST, GAINED = "decisive_lost(STRICT 결정 → 비결정)", "decisive_gained(STRICT 비결정 → 결정)"
TYPES = ("CTA", "OTHER", "UNKNOWN_TYPE")
PE_CLASSES = ("ACUTE_POS", "CHRONIC_OR_PERSISTENT", "UNCERTAIN", "NEGATIVE", "NO_MENTION")
DECISIVE_PE = ("ACUTE_POS", "CHRONIC_OR_PERSISTENT", "UNCERTAIN", "NEGATIVE")
# 이미 공개된 EXP-02 값과 같은 정의의 칸(공격자가 이번 공개본과 무관하게 앎)
EXTERNAL_CELLS = ("stays/cohort_stays", "stays/cohort_patients", "records/lab/input_rows", "records/radiology/input_rows", "records/ecg/input_rows")


class _B:
    def __init__(self):
        self.eq, self.le, self.gen, self.zero = [], [], [], {}

    def sum_is(self, total: str, parts, why: str):
        """total = Σ parts."""
        d = {total: 1.0}
        for p in parts:
            d[p] = d.get(p, 0.0) - 1.0
        self.eq.append({"cells": list(d), "coef": list(d.values()), "why": why})

    def same(self, cells, why: str):
        cells = list(cells)
        for a, b in zip(cells, cells[1:]):
            self.eq.append({"cells": [a, b], "coef": [1.0, -1.0], "why": why})

    def leq(self, a: str, b: str, why: str):
        self.le.append([a, b, why])

    def general(self, terms: dict, why: str):
        """Σ coef·cell ≤ 0."""
        self.gen.append({"cells": list(terms), "coef": [float(v) for v in terms.values()], "why": why})

    def zero_by_definition(self, cell: str, why: str):
        self.zero[cell] = why


def _rec(s: str, k: str) -> str:
    return f"records/{s}/{k}"


def _used(p, t, s) -> str:
    return f"usage/{p}/{t}/used/{s}"


def _flag(p, s, f) -> str:
    return f"flags_by_policy/{p}/{s}:{f}"


def _grade(p, s, g) -> str:
    return f"grades_by_policy/{p}/{s}:{g}"


def _state(p, t, s) -> str:
    return f"states/{p}/{t}/{s}/stays"


def _cat(p, t, c) -> str:
    return f"categories/{p}/{t}/{c}/stays"


def _xt(px, t, a, b) -> str:
    return f"paired_crosstab_vs_STRICT/{px}/{t}/STRICT={a}|{px}={b}/stays"


def _stays_block(b: _B):
    s = "stays/"
    b.sum_is(s + "cohort_stays", [s + "time_defined", s + "time_undefined"], "§2 시각 정의·미정의 분할")
    b.same([s + "time_defined", s + "evaluated_stays"], "§2 시각 정의 체류만 평가")
    b.sum_is(s + "cohort_patients", [s + "evaluated_patients", s + "patients_without_evaluable_stay"], "코호트 환자 = 평가 환자 + 평가 체류 없는 환자")
    b.leq(s + "t1_equals_t2", s + "time_defined", "§2 T1=T2 체류 ⊂ 시각 정의 체류")
    b.leq(s + "evaluated_patients", s + "evaluated_stays", "체류마다 환자 1명")
    b.leq(s + "patients_without_evaluable_stay", s + "time_undefined", "그런 환자마다 시각 불명 체류 1개 이상")
    b.leq(s + "cohort_patients", s + "cohort_stays", "체류마다 환자 1명")


def _rows_block(b: _B, s: str):
    """§3 행 대조."""
    r = lambda k: _rec(s, k)
    b.sum_is(r("input_rows"), [r("missing_key_rows"), r("unique_keys"), r("dup_extra_rows")], "§3 행 대조")
    b.sum_is(r("unique_keys"), [r("kept_unique"), r("dup_key_groups_time_conflict")], "§3 시각 충돌 키 전체 제외")
    b.general({r("dup_key_groups_identical"): 1, r("dup_key_groups_time_conflict"): 1, r("dup_extra_rows"): -1}, "§3 중복 키마다 잉여 행 1개 이상")


def _records_block(b: _B):
    for s in ("lab", "radiology", "ecg"):
        _rows_block(b, s)
    for s in ("lab", "radiology"):
        b.sum_is(_rec(s, "kept_unique"), [_rec(s, k) for k in ("attributed", "ambiguous", "unattributed")], "§4 귀속 3분할")
    r = lambda k: _rec("radiology", k)
    b.sum_is(r("kept_unique"), [r(f"type:{t}") for t in TYPES], "§5 영상 유형 3분할")
    for t in TYPES:
        b.sum_is(r(f"type:{t}"), [r(f"attributed:{t}"), r(f"ambiguous:{t}"), r(f"unattributed:{t}")], "§4·§5 유형별 귀속")
    for a in ("attributed", "ambiguous", "unattributed"):
        b.sum_is(r(a), [r(f"{a}:{t}") for t in TYPES], "§4·§5 귀속별 유형")
    b.sum_is(r("attributed:CTA"), [r(f"class:{c}") for c in PE_CLASSES], "§5 v3b 는 귀속 CTA 문서마다 1개 분류")
    b.sum_is(r("attributed:CTA"), [r("cta_input"), r("addendum_linked_no_decisive_not_input"), r("addendum_stored_before_parent_excluded"),
                                   r("addendum_charted_before_parent_excluded"), r("addendum_order_undeterminable_excluded")], "§5·§5-1 미투입 분리")
    b.sum_is(r("addendum_linked_replacing"), [r(f"replace_pair:{a}->{c}") for a in PE_CLASSES for c in DECISIVE_PE], "§5 대체 쌍 분해")
    b.sum_is(r("addendum_linked_no_decisive_not_input"),
             [r(f"nomention_addendum_parent_class:{a}") for a in PE_CLASSES + ("PARENT_NOT_INPUT",)], "§5 NO_MENTION 원 판독 분류")
    # 자식 하나가 부모 둘 이상이면 양방향 쌍을 2개 이상 차지 — 계수 2 는 하한이지 등식이 아님
    b.general({r("child_multiple_parents"): 2, r("child_not_AR"): 1, r("parent_not_in_extract"): 1, r("link_subject_mismatch"): 1,
               r("verified_links"): 1, r("link_pairs_both_fields"): -1}, "§5 양방향 쌍 분해(부모 2개 이상 자식은 쌍 2개 이상)")
    for k in ("addendum_linked_replacing", "addendum_linked_no_decisive_not_input", "addendum_stored_before_parent_excluded",
              "addendum_charted_before_parent_excluded", "addendum_order_undeterminable_excluded", "addendum_type_from_parent",
              "linked_addendum_stay_ne_parent_stay", "linked_addendum_parent_ambiguous_or_unattributed"):
        b.leq(r(k), r("verified_links"), "§5 연결 addendum 부분집합")
    e = lambda k: _rec("ecg", k)
    b.sum_is(e("kept_unique"), [e("no_stay_key"), e("stay_key_not_in_cohort"), e("on_time_undefined_stay"), e("matched")], "§4 ECG 키 분류")
    t = lambda k: _rec("triage", k)
    b.same([t("rows"), "stays/cohort_stays"], "§3 triage = 체류당 1행")
    b.same([t("rows_on_time_undefined_stay"), "stays/time_undefined"], "§3 triage = 체류당 1행")
    b.leq(t("rows_with_derived_evidence"), t("rows"), "파생 증거 있는 행 ⊂ 행")
    b.leq(t("rows_with_derived_evidence"), t("derived_evidence"), "행마다 증거 1개 이상")


def _unit_block(b: _B):
    """§6 기록·체류·환자 단위 분리: 같은 기록을 체류마다 다시 세지 않음. 환자 ≤ 체류 ≤ 기록."""
    base = {"lab": _rec("lab", "attributed"), "radiology": _rec("radiology", "cta_input"), "ecg": _rec("ecg", "matched"), "triage": "denominator/triage"}
    for s, n in base.items():
        st_, pt = _rec(s, "stays_with_records"), _rec(s, "patients_with_records")
        b.leq(st_, n, "기록 있는 체류마다 기록 1개 이상")
        b.leq(st_, "stays/evaluated_stays", "§6 부분집합")
        b.leq(pt, st_, "체류마다 환자 1명")
        b.leq(pt, "stays/evaluated_patients", "§6 부분집합")
    b.same([_rec("triage", "stays_with_records"), "denominator/triage"], "§3 triage = 체류당 1행")


def _denominator_block(b: _B):
    d = lambda s: f"denominator/{s}"
    b.same([d("lab"), _rec("lab", "attributed")], "§6 lab 분모")
    b.same([d("rad"), _rec("radiology", "cta_input")], "§6 rad 분모")
    b.same([d("ecg"), _rec("ecg", "matched")], "§6 ecg 분모")
    b.sum_is(d("pooled"), [d(s) for s in SRCS], "§6 합산 분모")
    b.leq(d("triage"), _rec("triage", "rows_with_derived_evidence"), "§6 triage 분모 ⊂ 파생 증거 행")
    b.general({_rec("triage", "rows_with_derived_evidence"): 1, d("triage"): -1, _rec("triage", "rows_on_time_undefined_stay"): -1},
              "§6 평가 안 된 파생 증거 행은 시각 불명 체류뿐")


def _flags_block(b: _B):
    """정책별 flag·등급: v1 정의(시간 등급은 원천·시각으로 결정, 정책은 사용 허용만 바꿈)."""
    for p in POLS:
        for s in ("lab", "rad", "ecg"):
            den = f"denominator/{s}"
            b.sum_is(den, [_flag(p, s, f) for f in FLAGS], "§6 flag 분할 = 분모")
            b.sum_is(den, [_grade(p, s, g) for g in GRADES], "§6 등급 분할 = 분모")
        b.sum_is(f"C_candidates_vs_used/{p}/C_input_by_source/triage", [_flag(p, "triage", f) for f in FLAGS], "triage 입력 = 파생 증거 단위")
        b.sum_is(f"C_candidates_vs_used/{p}/C_input_by_source/triage", [_grade(p, "triage", g) for g in GRADES], "triage 입력 = 파생 증거 단위")
        for s in SRCS:
            if s != "triage":
                b.same([f"C_candidates_vs_used/{p}/C_input_by_source/{s}", _grade(p, s, GC)], "§6 C 입력 = 등급 C")
        for t in TS:
            b.same([f"usage/{p}/{t}/APPROX_used(evidence)", f"usage/{p}/{t}/triage_derived_evidence_used", f"C_candidates_vs_used/{p}/C_used/{t}"],
                   "§6 정책상 사용되는 등급 C = S1 triage 근사뿐")
    for p in POLS:
        b.general({f"records/triage/rows_with_derived_evidence": 1, _grade(p, "triage", GC): -1, "records/triage/rows_on_time_undefined_stay": -1},
                  "파생 증거 행마다 증거 1개 이상")
        b.leq(_grade(p, "triage", GC), _rec("triage", "derived_evidence"), "평가 체류 파생 증거 ⊂ 전체 파생 증거")
    # 등급은 기록 시각 속성이라 정책과 무관(정책은 사용 허용만 바꿈, v1 §1–§3)
    for s in SRCS:
        for g in GRADES:
            b.same([_grade(p, s, g) for p in POLS], "v1 §1 등급 = 기록 속성(정책 무관)")
        b.same([f"C_candidates_vs_used/{p}/C_input_by_source/{s}" for p in POLS], "v1 §1 등급 C 입력 = 정책 무관")
        for f in ("UNKNOWN_AVAILABILITY", "TIME_CONFLICT", "NOT_IDENTIFIABLE"):
            if s != "triage":
                b.same([_flag(p, s, f) for p in POLS], "v1 §2 시각 불명·충돌·식별 불가 = 기록 속성")
    for f in FLAGS:
        b.same([_flag(p, "lab", f) for p in POLS], "v1 §3 lab 은 세 정책 동일 처리")
        b.same([_flag(p, "ecg", f) for p in POLS], "v1 §3 ecg 는 세 정책 동일 처리")
        b.same([_flag(ST, "rad", f), _flag(S1, "rad", f)], "v1 §3 rad 는 STRICT·S1 동일 처리")
        b.same([_flag(ST, "triage", f), _flag(S2, "triage", f)], "v1 §3 triage 는 STRICT·S2 동일 처리")
    b.sum_is(_flag(S2, "rad", "EXCLUDED_BY_POLICY"), [_flag(ST, "rad", "OK"), _flag(ST, "rad", "POST_ED")], "v1 §3 S2 는 시각 있는 rad 를 정책 제외")
    b.same([_flag(S1, "triage", "APPROX_INTIME"), _flag(ST, "triage", "UNKNOWN_AVAILABILITY")], "v1 §3 S1 은 시각 없는 triage 를 intime 근사")
    for p in POLS:
        for s in SRCS:
            b.sum_is(_grade(p, s, GC), [_flag(p, s, f) for f in ("UNKNOWN_AVAILABILITY", "TIME_CONFLICT", "NOT_IDENTIFIABLE", "APPROX_INTIME")],
                     "v1 §1–§2 등급 C = 시각 불명·충돌·식별 불가·근사")
    for t in TS:
        b.same([f"usage/{S1}/{t}/triage_derived_evidence_used", _grade(S1, "triage", GC)], "§1 S1 은 평가 체류 파생 증거 전부 사용")
    # flag 병합(공개 2순위): 정의상 합
    for p in POLS:
        for s in SRCS:
            b.sum_is(f"flags_merged/{p}/{s}:USABLE_BY_TIME(OK+APPROX_INTIME)", [_flag(p, s, "OK"), _flag(p, s, "APPROX_INTIME")], "병합 범주 정의")
            b.same([f"flags_merged/{p}/{s}:AFTER_ED(POST_ED)", _flag(p, s, "POST_ED")], "병합 범주 정의")
            b.sum_is(f"flags_merged/{p}/{s}:NOT_USED(UNKNOWN+CONFLICT+NOT_IDENTIFIABLE+EXCLUDED)",
                     [_flag(p, s, f) for f in ("UNKNOWN_AVAILABILITY", "TIME_CONFLICT", "NOT_IDENTIFIABLE", "EXCLUDED_BY_POLICY")], "병합 범주 정의")


def _usage_block(b: _B):
    for p in POLS:
        for t in TS:
            b.sum_is(_used(p, t, "pooled"), [_used(p, t, s) for s in SRCS], "§6 합산 사용")
            b.same([f"usage/{p}/{t}/PROXY_used(evidence)", _used(p, t, "rad")], "§6 rad 사용 = PROXY(대리 시각)")
            b.leq(f"usage/{p}/{t}/stays_with_any_used/stays", "stays/evaluated_stays", "§6 부분집합")
            b.leq(f"usage/{p}/{t}/stays_with_any_used/stays", _used(p, t, "pooled"), "증거 있는 체류마다 사용 기록 1개 이상")
            b.leq(f"usage/{p}/{t}/stays_cta_performed_not_yet_available", "stays/evaluated_stays", "§6 부분집합")
            b.leq(f"usage/{p}/{t}/stays_with_unlinked_AR_effective/stays", "stays/evaluated_stays", "§5 부분집합")
            b.leq(_used(p, t, "triage"), f"usage/{p}/{t}/stays_with_any_used/stays", "triage 사용 행 = 그 체류")
            for s in SRCS:
                b.leq(_used(p, t, s), f"denominator/{s}", "§6 포함률 ≤ 1")
            b.leq(_used(p, t, "triage"), f"usage/{p}/{t}/triage_derived_evidence_used", "행마다 증거 1개 이상")
            b.leq(f"usage/{p}/{t}/stays_with_unlinked_AR_effective/stays", f"usage/{p}/{t}/stays_with_any_used/stays", "§5 유효 증거 있는 체류 ⊂ 증거 있는 체류")
            b.leq(f"usage/{p}/{t}/stays_with_unlinked_AR_effective/stays", _used(p, t, "rad"), "§5 미연결 AR 은 rad 사용 기록")
            for st_ in ("CONFLICT", "SUPPORTED", "UNKNOWN"):
                b.leq(_state(p, t, st_), f"usage/{p}/{t}/stays_with_any_used/stays", "reassess 상태는 사용 증거에서 나옴")
            for st_ in ("CONFLICT", "UNKNOWN"):
                b.leq(_state(p, t, st_), _used(p, t, "rad"), "reassess.py:134 R2·R4·R5 는 영상 규칙")
            b.leq(f"states/{p}/{t}/alerts/AL2_SUPPORT_RETRACTED/stays", _used(p, t, "rad"), "AL2 는 대체 영상에서 나옴")
            b.leq(f"states/{p}/{t}/alerts/AL2_SUPPORT_RETRACTED/stays", f"usage/{p}/{t}/stays_with_any_used/stays", "AL2 는 사용 증거가 있는 체류에서만")
        for t0, t1 in zip(TS, TS[1:]):
            for s in SRCS + ("pooled",):
                b.leq(_used(p, t0, s), _used(p, t1, s), "§2 시점이 늦을수록 이용 가능 기록 증가")
            b.leq(f"usage/{p}/{t0}/stays_with_any_used/stays", f"usage/{p}/{t1}/stays_with_any_used/stays", "§2 단조")
    for t in TS:
        b.same([_used(p, t, "lab") for p in POLS], "§1 lab 등급 A — 세 정책 모두 사용")
        b.same([_used(ST, t, "rad"), _used(S1, t, "rad")], "§1 rad 등급 B — STRICT·S1 사용")
        b.leq(f"usage/{S2}/{t}/stays_with_any_used/stays", f"usage/{ST}/{t}/stays_with_any_used/stays", "§1 S2 사용 ⊂ STRICT 사용")
        b.leq(f"usage/{ST}/{t}/stays_with_any_used/stays", f"usage/{S1}/{t}/stays_with_any_used/stays", "§1 STRICT 사용 ⊂ S1 사용")
        b.same([f"usage/{ST}/{t}/stays_with_unlinked_AR_effective/stays", f"usage/{S1}/{t}/stays_with_unlinked_AR_effective/stays"], "§5 rad 사용 같음")
        b.same([f"usage/{ST}/{t}/observed_le_T_lt_available(records)", f"usage/{S1}/{t}/observed_le_T_lt_available(records)"], "§6 lab·rad 같음")
        b.same([f"usage/{ST}/{t}/stays_cta_performed_not_yet_available", f"usage/{S1}/{t}/stays_cta_performed_not_yet_available"], "§6 rad 같음")
        for p in POLS:                                                  # 정의상 0
            b.zero_by_definition(_used(p, t, "ecg"), "§1 ECG 는 사용 안 함")
        b.zero_by_definition(_used(ST, t, "triage"), "§1 STRICT triage 미사용")
        b.zero_by_definition(_used(S2, t, "triage"), "§1 S2 triage 미사용")
        b.zero_by_definition(_used(S2, t, "rad"), "§1 S2 rad 미사용")
        b.zero_by_definition(f"usage/{S2}/{t}/stays_with_unlinked_AR_effective/stays", "§1 S2 rad 미사용")
        b.zero_by_definition(f"usage/{S2}/{t}/stays_cta_performed_not_yet_available", "§1 S2 rad 미사용")
    for t in TS[1:]:
        b.same([_used(S1, TS[0], "triage"), _used(S1, t, "triage")], "§1 S1 triage = intime 근사(T 불변)")
    for p in POLS:
        for r in ("rejected_no_source", "correction_target_not_in_timeline"):
            pass  # 정의상 관계 없음(자료 품질 건수)


def _states_block(b: _B):
    for p in POLS:
        for t in TS:
            b.sum_is("stays/evaluated_stays", [_state(p, t, s) for s in STATES], "§6 체류마다 상태 1개")
            b.sum_is("stays/evaluated_stays", [_cat(p, t, c) for c in CATS], "§6 체류마다 범주 1개")
            for s in STATES:
                b.sum_is(_state(p, t, s), [_cat(p, t, c) for c in CATS if SUMMARY_OF[c] == s], "§6 상태 = 범주 합")
            for r in ("AL1_NEW_CONFLICT", "AL2_SUPPORT_RETRACTED"):
                b.leq(f"states/{p}/{t}/alerts/{r}/stays", "stays/evaluated_stays", "§6 부분집합")
            b.zero_by_definition(_state(p, t, "PENDING"), "§6 MIMIC 에 의뢰 시각 없음 — PENDING 미생성")
            b.zero_by_definition(_cat(p, t, "PENDING"), "§6 PENDING 미생성")
            b.zero_by_definition(_state(p, t, "NO_HYPOTHESIS"), "§6 모든 체류에 SIMULATED_WD 가설")
            b.zero_by_definition(_cat(p, t, "NO_HYPOTHESIS"), "§6 모든 체류에 가설")
        c = lambda n: f"states/{p}/changes/{n}/stays"
        b.leq(c("summary_T0_vs_T2"), c("summary_any_checkpoint"), "§6 T0≠T2 ⊂ 어느 시점 변화")
        b.leq(c("alerts_T0_vs_T2"), c("alerts_any_checkpoint"), "§6 T0≠T2 ⊂ 어느 시점 변화")
        b.leq(c("summary_any_checkpoint"), "stays/evaluated_stays", "§6 부분집합")
        b.leq(c("alerts_any_checkpoint"), "stays/evaluated_stays", "§6 부분집합")


def _crosstab_block(b: _B):
    for px in (S1, S2):
        for t in TS:
            for a in CATS:
                b.sum_is(_cat(ST, t, a), [_xt(px, t, a, x) for x in CATS], "§6 교차표 행 = STRICT 범주")
            for x in CATS:
                b.sum_is(_cat(px, t, x), [_xt(px, t, a, x) for a in CATS], "§6 교차표 열 = 비교 정책 범주")
            base = f"paired_crosstab_vs_STRICT/{px}/{t}"
            b.sum_is(f"{base}/differs/summary/stays", [_xt(px, t, a, x) for a in CATS for x in CATS if SUMMARY_OF[a] != SUMMARY_OF[x]], "§6 요약 상태 상이")
            b.sum_is(f"{base}/{LOST}/stays", [_xt(px, t, a, x) for a in DECISIVE for x in CATS if x not in DECISIVE], "§6 결정 상실")
            b.sum_is(f"{base}/{GAINED}/stays", [_xt(px, t, a, x) for a in CATS if a not in DECISIVE for x in DECISIVE], "§6 결정 획득")
            b.leq(f"{base}/differs/alerts/stays", "stays/evaluated_stays", "§6 부분집합")


def _definition_links(b: _B):
    """정책 정의·reassess 규칙에서 곧바로 나오는 칸 사이 등식(자료 관찰이 아니라 코드 정의가 근거)."""
    for p in POLS:
        for t in TS:
            b.same([_state(p, t, "CONFLICT"), f"states/{p}/{t}/alerts/AL1_NEW_CONFLICT/stays"], "reassess.py:191·200 R2 ⇔ 상태 CONFLICT ⇔ AL1")
    for t in TS:
        for c in ("CONFLICT_R2", "SUPPORTED_R1", "INSUFFICIENT_R3", "UNKNOWN_R4R5"):
            b.same([_cat(ST, t, c), _cat(S1, t, c)], "reassess.py:134 결정 규칙은 영상만 — S1 은 triage 만 추가")
        b.same([_state(ST, t, "UNKNOWN"), _state(S1, t, "UNKNOWN")], "결정 규칙은 영상만")
        b.same([f"states/{ST}/{t}/alerts/AL2_SUPPORT_RETRACTED/stays", f"states/{S1}/{t}/alerts/AL2_SUPPORT_RETRACTED/stays"], "알림 규칙은 영상만")
    for c in ("alerts_T0_vs_T2", "alerts_any_checkpoint"):
        b.same([f"states/{ST}/changes/{c}/stays", f"states/{S1}/changes/{c}/stays"], "알림 규칙은 영상만")
    for t in TS:
        b.same([_used(S1, t, "triage"), "denominator/triage"], "§1 S1 은 intime 근사로 파생 증거 있는 행 전부 사용")
    for p in (ST, S1):
        b.same([_flag(p, "rad", "OK"), _used(p, "T2", "rad")], "§2 T2 = outtime: OK = 퇴실 전 이용 가능 = T2 사용")
    for p in POLS:
        b.same([_flag(p, "lab", "OK"), _used(p, "T2", "lab")], "§2 T2 = outtime: OK = 퇴실 전 이용 가능 = T2 사용")
    b.same([f"usage/{S2}/T2/observed_le_T_lt_available(records)", _flag(S2, "lab", "POST_ED")], "§6 T2 에서 시행·미이용 lab = 퇴실 후 이용")


def build_schema() -> dict:
    b = _B()
    _stays_block(b)
    _records_block(b)
    _denominator_block(b)
    _unit_block(b)
    _flags_block(b)
    _usage_block(b)
    _states_block(b)
    _crosstab_block(b)
    _definition_links(b)
    cells = set(b.zero)
    for e in b.eq + b.gen:
        cells.update(e["cells"])
    for x in b.le:
        cells.update(x[:2])
    return {"equalities": b.eq, "inequalities": [x[:2] for x in b.le], "inequality_reasons": [x[2] for x in b.le], "inequalities_general": b.gen,
            "constant": {c: 0 for c in b.zero}, "constant_reasons": b.zero, "external_cells": list(EXTERNAL_CELLS), "schema_cells": sorted(cells)}
