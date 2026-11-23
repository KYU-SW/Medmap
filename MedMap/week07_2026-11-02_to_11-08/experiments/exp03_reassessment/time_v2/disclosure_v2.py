"""EXP-03-TIME v2 공개 집계 보호(PROTOCOL_TIME_v2.md §9) — INTERNAL 과 PUBLIC 분리, 보수적 공개.

순서
1) heuristic: public_v2.suppress(1–9 '<10' + 항등식 묶음 보완) — 기존 단계 유지
2) 정책: 환자 수는 평가 체류 전체 1칸만 공개(집합 관계는 선형 검증 범위 밖), 나머지 환자 칸 PUBLIC_WITHHELD
3) 독립 검증기(disclosure_verifier, 보호 코드·묶음 G 미사용)로 역산 검사 → FAILED·NOT_VERIFIABLE 칸이 속한(또는 그 관계 성분의
   가장 세부) 표를 통째로 PUBLIC_WITHHELD → 처음부터 재검사, VERIFIED 될 때까지 반복(표 수만큼이 상한)
4) 관계 파일이 없거나 끝까지 검증 안 되면 모든 자료 표 PUBLIC_WITHHELD(공개 0)
공개 범위(개정 2026-11-03): T1 전체 요약 · T2 병합 범주만 공개 후보. T3 세부(flag·등급·C 입력·범주·8×8 교차표·세부 기록 집계)는 검증 결과와 무관하게
외부 공개 제외 — 환자 보호를 확인할 수 없는 세부는 내지 않음. 공개 숫자 최대화는 목표가 아님. 같은 실패 성분이면 병합(T2) → 요약(T1) 순으로 비공개.
이번 자료에서 거짓인 선언 관계·상수의 칸(untrusted)이 든 표는 첫 검증 전에 비공개.
내부 정확값(X)은 바꾸지 않는다(사본에만 표시).
"""
from __future__ import annotations

import disclosure_verifier as DV
import public_v2 as PB

WITHHELD = DV.WITHHELD_TOKEN
MERGED_FLAGS = {"USABLE_BY_TIME(OK+APPROX_INTIME)": ("OK", "APPROX_INTIME"),
                "AFTER_ED(POST_ED)": ("POST_ED",),
                "NOT_USED(UNKNOWN+CONFLICT+NOT_IDENTIFIABLE+EXCLUDED)": ("UNKNOWN_AVAILABILITY", "TIME_CONFLICT", "NOT_IDENTIFIABLE",
                                                                          "EXCLUDED_BY_POLICY")}
RECORD_CORE = {"input_rows", "missing_key_rows", "unique_keys", "dup_extra_rows", "kept_unique", "attributed", "ambiguous",
               "unattributed", "matched", "rows", "rows_with_derived_evidence", "cta_input"}   # 영상 유형 칸은 공개 시간 감사(CTA 행 수)와 겹쳐 제외
PATIENT_WHITELIST = {("stays", "evaluated_patients"), ("stays", "cohort_patients")}
PATIENT_INTERNAL_ONLY = {("stays", "patients_without_evaluable_stay")}
PUBLISH_TIERS = (1, 2)
POLICY_WITHHELD_REASON = "PATIENT_COUNTS_INTERNAL_ONLY(집합 관계 검증 범위 밖)"
GENERIC_REASON = "PUBLIC_WITHHELD — 공개 안전성 검증 실패 또는 검증 불가(세부 사유·값은 내부 기록에만)"


def table_of(path: tuple) -> tuple[str, int]:
    """칸 → (표 id, 등급 1·2·3)."""
    r = path[0]
    if r == "stays":
        return ("stays_patients", 1) if "patients" in str(path[1]) else ("stays", 1)   # 환자 칸은 체류 표와 따로 비공개 가능
    if r == "records":
        return (f"records_{path[1]}_core", 1) if path[2] in RECORD_CORE else (f"records_{path[1]}_detail", 3)
    if r == "denominator":
        return "denominator", 1
    if r in ("flags_by_policy", "grades_by_policy", "C_candidates_vs_used"):
        return f"{r}_{path[1]}", 3
    if r == "flags_merged":
        return f"flags_merged_{path[1]}", 2
    if r == "usage":
        return (f"usage_{path[1]}_{path[2]}", 1) if path[2] in ("T0", "T1", "T2") else (f"usage_misc_{path[1]}", 1)
    if r == "states":
        if path[2] == "changes":
            return f"changes_{path[1]}", 1
        if len(path) > 3 and path[3] == "alerts":
            return f"alerts_{path[1]}_{path[2]}", 1
        return f"states_{path[1]}_{path[2]}", 1
    if r == "categories":
        return f"categories_{path[1]}_{path[2]}", 3
    if r == "paired_crosstab_vs_STRICT":
        return (f"crosstab_{path[1]}_{path[2]}", 3) if str(path[3]).startswith("STRICT=") else (f"paired_summary_{path[1]}_{path[2]}", 1)
    return f"other_{r}", 3


def _flat(pub: dict) -> dict:
    return {"/".join(map(str, k)): v for k, v in pub.items()}


def protect(X: dict, G: list, PAT: list, relations: dict | None, max_rounds: int | None = None, withhold_all: bool = False):
    """반환 (공개 dict: 경로 → 값 또는 토큰, 공개 보고). X 는 바꾸지 않음. withhold_all=True: 자료 표 전부 비공개(공개 0, 4순위 일괄)."""
    pub = PB.suppress(X, G)
    for sp, pp in PAT:                                                  # 체류가 가려지면 환자도 가림(1단계)
        if PB.is_masked(pub[sp]) and not PB.is_masked(pub[pp]):
            pub[pp] = PB.COMPLEMENT
    policy_withheld = []
    for k in list(pub):                                                 # 2단계: 환자 수 정책
        if (k[-1] == "patients" and k not in PATIENT_WHITELIST) or k in PATIENT_INTERNAL_ONLY:
            pub[k] = WITHHELD
            policy_withheld.append(k)
    tables, tier = {}, {}
    for k in X:
        t, g = table_of(k)
        tables.setdefault(t, []).append(k)
        tier[t] = g
    withheld = []
    rounds, last = 0, None
    dropped = None
    if relations is not None and not withhold_all:                     # 선언 관계 대조 — 거짓 관계의 칸은 untrusted(표 비공개), 버리고 통과시키지 않음
        relations, dropped = DV.restrict_to_truth(relations, {"/".join(map(str, k)): int(v) for k, v in X.items()})
        cell_of = {"/".join(map(str, k)): k for k in X}
        pre = {t for t, g in tier.items() if g not in PUBLISH_TIERS}    # 세부 표 = 공개 범위 밖
        pre |= {table_of(cell_of[c])[0] for c in relations.get("_untrusted", ()) if c in cell_of}
        for t in pre:
            for k in tables[t]:
                pub[k] = WITHHELD
        withheld.extend(sorted(pre))
    if relations is None or withhold_all:
        for t, cells in tables.items():
            for k in cells:
                pub[k] = WITHHELD
        withheld = sorted(tables)
        last = {"status": DV.NOT_VERIFIABLE if relations is None else "WITHHOLD_ALL",
                "note": "관계 파일 없음 — 검증 불가, 전 자료 표 비공개" if relations is None else "요청에 따라 전 자료 표 비공개"}
    else:
        limit = max_rounds if max_rounds is not None else len(tables) + 1
        cell_table = {"/".join(map(str, k)): table_of(k)[0] for k in X}
        while rounds < limit:
            rounds += 1
            last = DV.verify_flat(_flat(pub), {}, relations)
            if last["status"] == DV.VERIFIED:                          # LP 통과 후 정수 재확인(반복 비용 때문에 통과 시점에만)
                last = DV.verify_flat(_flat(pub), {}, relations, integer_check=True)
            bad = last["failed"] + last["not_verifiable"]
            if last["status"] == DV.VERIFIED:
                break
            cand = {cell_table[c] for c in bad if c in cell_table} - set(withheld)
            if not cand:                                               # 이미 비공개인 칸이 다른 표의 공개값으로 역산됨
                open_tables = set(tables) - set(withheld)
                for c in last["failed"]:                               # 실패 칸마다 그 성분에서 가장 세부인 공개 표 하나(동률은 이름순 — 결정적)
                    pool = {cell_table[x] for x in last.get("linked_public", {}).get(c, []) if x in cell_table} & open_tables
                    if pool:
                        cand.add(max(pool, key=lambda t: (tier[t], len(tables[t]), t)))
                if not cand:
                    if not open_tables:
                        break
                    cand = {max(open_tables, key=lambda t: (tier[t], len(tables[t]), t))}
            for t in cand:
                for k in tables[t]:
                    pub[k] = WITHHELD
                withheld.append(t)
        if last is None or last["status"] != DV.VERIFIED:               # 끝까지 검증 안 되면 전부 비공개
            for t, cells in tables.items():
                for k in cells:
                    pub[k] = WITHHELD
            withheld = sorted(tables)
            last = DV.verify_flat(_flat(pub), {}, relations, integer_check=True)   # 전부 비공개 뒤 재판정 — 보고값이 실제 공개본 상태와 일치
    report = {"policy": "INTERNAL 정확 집계 보존 · PUBLIC 은 독립 검증 VERIFIED 분만 · 실패·검증 불가 표는 통째로 PUBLIC_WITHHELD",
              "verifier_status": last["status"] if last else None,
              "rounds": rounds, "withheld_tables": sorted(set(withheld)), "withheld_reason": GENERIC_REASON,
              "patient_counts_policy": POLICY_WITHHELD_REASON + " — 공개 환자 칸은 stays/evaluated_patients 1개",
              "published_tables": sorted(t for t in tables if t not in set(withheld)),
              "tiers": {"T1": "전체 요약", "T2": "병합 범주(flags_merged)", "T3": "세부 — 외부 공개 제외(내부 집계에만)"},
              "verifier_scope": (last or {}).get("scope"), "verifier_limits": DV.LIMITS,
              "relations_used": "스키마·프로토콜 선언 관계. 이번 자료에서 거짓인 관계의 칸은 비공개(건수는 내부 기록)",
              "status_meaning": {"VERIFIED": "정해진 검증 범위에서 위험 미검출", "FAILED": "복원 위험 검출",
                                 "NOT_VERIFIABLE": "검증 범위 밖 — 공개하지 않음"}}
    report["_internal_only"] = {"relations_dropped_false_on_data": dropped}   # run 이 공개 전에 떼어 내부 파일에만 기록
    report["_relations_used"] = relations
    return pub, report
