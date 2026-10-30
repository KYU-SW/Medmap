"""DDXPlus 환자 기록 → PatientRecord(graph_engine). 223 근거 매핑표 포함.

매핑 근거: STEP20 수작업 매핑(curated_mappings.tsv, 증상 110개, 읽기 전용) + 이번 회차 정의 1건(흉통 = E_53 양성 + E_55 흉부 부위 값).
매핑 상태
  EXACT              — 같은 개념(HPO EXACT, 또는 'A AND B' 복합의 각 개념)            → 추론에 사용
  EXACT_BROADER      — DDXPlus 개념 ⊂ HPO 개념(ACCEPTABLE_BROADER): 양성이면 HPO 개념 양성 → 추론에 사용
  EXACT_COMPOSITE    — 여러 DDXPlus 질문 조합 = 하나의 HPO 개념(흉통, 이번 회차 정의)      → 추론에 사용(검토 권장 표기)
  REVIEW             — 좁은/부분/OR 복합/병력↔노출 후보: 검토가 필요한 후보                 → 추론에 사용 안 함
  NO_CONCEPT         — 연결할 실제 의료 개념 없음(속성·수치·NO_MATCH)                    → 추론에 사용 안 함
  NOT_ASSESSED       — 병력(antecedent) 중 이번 회차에 조사하지 않음                        → 추론에 사용 안 함
DDXPlus 의미 규칙: EVIDENCES 에 있는 것 = 양성. **없는 것은 음성으로 바꾸지 않는다(미기록)**. 시뮬레이터의 '물었고 아니오'
규약을 복제하지 않는다. DIFFERENTIAL_DIAGNOSIS(생성기 출력)·release_conditions(생성기 정답표)는 읽지 않는다.
"""
from __future__ import annotations

import csv
import functools
import json
from pathlib import Path

from graph_engine import EvidenceRecord, PatientRecord, Status

EVID_JSON = Path("/home/<user>/medmap/data/ddxplus/en/release_evidences.json")
STEP20_TSV = Path("/home/<user>/medmap-worktrees/symptom-ontology/exp/step20_symptom_ontology_audit/curation/curated_mappings.tsv")
CHEST_PAIN_HP = "HP:0100749"
CHEST_SITES = ("V_29", "V_55", "V_56", "V_101", "V_170", "V_171")   # lower/side(R,L)/upper/posterior chest wall(R,L)
# 37회차 복합 매핑(정의 기반, 정답 라벨 미참조)
PLEURITIC_HP = "HP:0033771"          # Pleuritic chest pain: "sharp, stabbing, or burning pain in the chest when inhaling and exhaling"
PLEURITIC_QUALITY = ("V_179", "V_181", "V_192")   # E_54: a knife stroke / burning / sharp — 정의의 성질과 같은 값만(추정 없음)
LIMB_SWELLING_HP = "HP:6000840"      # Localized soft-tissue swelling on extremity: "enlargement restricted to a specific part of a limb"
LIMB_WORDS = ("thigh", "calf", "tibia", "ankle", "foot", "sole", "heel", "toe", "knee", "popliteal", "ischio jambier",
              "forearm", "biceps", "triceps", "elbow", "wrist", "hand", "palm", "finger", "thumb")
COMPOSITE_CODES = ("E_55", "E_220", "E_151", "E_152", "E_54", "E_33")
POSITIONAL_NODE = "CONCEPT:chest_pain_relieved_sitting_forward"   # 38회차, knowledge_discriminators 개념 노드
HIV_NODE = "CONCEPT:hiv_infection"       # 다른 질문과 함께만 해석
# 병력 ↔ DisMech 위험 노출: 개념 범위가 달라 전부 REVIEW(추론 미사용). 이유를 함께 남긴다.
RISK_REVIEW = {
    "E_196": ("RF:ECTO:2000054", "최근 1개월 내 '모든' 수술 vs DisMech 'Major surgery'(대수술) — 범위 다름"),
    "E_110": ("RF:Pulmonary_Embolism:1", "3일 이상 거동 불가(4주 내) vs 'Prolonged immobilisation' — 기간 정의 미확인"),
    "E_100": ("RF:ECTO:9000010", "현재 호르몬 복용(종류 불명) vs 'Oestrogen exposure' — 범위 다름"),
    "E_8": ("RF:Pericarditis:1", "투석 중 vs 'End-stage renal disease and uraemia' — 투석 ≠ 요독증"),
    "E_113": ("RF:Pericarditis:1", "만성 신부전 vs 'End-stage renal disease and uraemia' — 병기 범위 다름"),
    "E_109": ("HP:0002625", "DVT 과거력 vs 현재 소견 'Deep venous thrombosis' — 시점 다름"),
}


def load_evidences() -> dict:
    return json.loads(EVID_JSON.read_text(encoding="utf-8"))


# 35회차 재판정(사람 판단, 사유 필수). STEP20 판정을 덮는다. 상태가 EXACT 계열이 아니면 추론에 쓰지 않는다.
OVERRIDES = {
    "E_164": ("EXACT_BROADER", ["HP:0001962"], "불규칙한 박동 '느낌' ⊂ 두근거림(Palpitations). 부정맥(HP:0011675)은 진단 개념이라 연결 안 함. "
              "STEP20 이 E_155(빠름·불규칙·쿵쾅)를 Palpitations EXACT 로 둔 것과 일관"),
    "E_173": ("REVIEW", [], "속쓰림(작열감 상행) ≠ 위식도역류(HP:0002020 = 역류 현상). HPO 에 속쓰림 용어 없음"),
    "E_96": ("REVIEW", [], "최근 체중 증가(변화) ≠ Increased body weight(상태)"),
    "E_211": ("REVIEW", [], "여러 번 구토 OR 구역 노력(헛구역질 HP:6001526 별도 개념) — 혼합 질문"),
    "E_93": ("REVIEW", [], "감각 저하 OR 감각 소실 OR 저림 — 감각저하(HP:0033748)와 이상감각(HP:0003401) 혼합"),
    "E_157": ("REVIEW", [], "감각 저하 OR 감각 소실 OR 저림 — 혼합 질문"),
    "E_215": ("REVIEW", [], "수식어(식후 악화)만 — 어떤 증상인지 없음"),
    "E_216": ("REVIEW", [], "수식어(움직이면 악화)만 — 소견 단독 개념 아님"),
    "E_219": ("REVIEW", [], "수식어(야간 악화)만 — 소견 단독 개념 아님"),
    "E_51": ("REVIEW", [], "설사 OR 배변 횟수 증가 — 횟수 증가만으로는 설사(HPO 정의: 묽은 변) 아님"),
    "E_63": ("REVIEW", [], "발음 곤란 OR 말하기 곤란 — 실어증 등 포함 가능, 구음장애보다 넓음"),
    "E_65": ("REVIEW", [], "삼킴 곤란 OR 삼킬 때 불편(연하통 포함) — 혼합"),
    "E_156": ("REVIEW", [], "현재 또는 과거(회복된) 안면 마비 — 시점 혼합"),
}
# 병력(antecedent) 중 4질환 위험인자·병력과 직접 관련된 항목만 조사(35회차). 나머지는 NOT_ASSESSED 유지.
ANTECEDENT_REVIEW = {
    "E_167": ("NO_KB_RELATION", "임신 — DisMech 폐색전증 설명 문장(유발 인자 나열)에만 언급, 근거 붙은 구조화 관계 없음"),
    "E_34": ("NO_KB_RELATION", "활동성 암 — DisMech 폐색전증·심낭염 설명 문장에만 언급, 구조화 관계 없음"),
    "E_37": ("NO_KB_RELATION", "전이암 — 위와 같음"),
    "E_0": ("NO_KB_RELATION", "최근 바이러스 감염 — 심근염 아형(viral myocarditis)·심낭염 원인 서술, 위험인자 관계 없음"),
    "E_2": ("NO_KB_RELATION", "HIV — 심낭염 결핵형 서술에만 언급, 결핵 항목에 위험인자 관계 없음"),
    "E_227": ("NO_KB_RELATION", "면역억제 — 4질환 구조화 위험인자 없음"),
    "E_44": ("NO_KB_RELATION", "코르티코스테로이드 — 심낭염 재발 기전 서술, 위험인자 관계 없음"),
    "E_3": ("NO_KB_RELATION", "심낭염 과거력 — 재발형 서술만, 구조화 관계 없음"),
}
NUMERIC_SCALE = "NUMERIC_SCALE"


def build_mapping() -> dict:
    """E 코드 → {status, hp_ids, used, negative_ok, reason, question, is_antecedent, data_type}.
    used = 양성 답을 HPO 양성으로 쓴다. negative_ok = 명시적 음성 답을 HPO 음성으로 쓴다(같은 개념 EXACT 단일만).
    상위 개념 연결(EXACT_BROADER)은 양성 방향만: 좁은 증상이 없다는 답이 넓은 개념 전체를 부정하지 않는다."""
    ev = load_evidences()
    cur = {}
    with open(STEP20_TSV, encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            cur[r["evidence_id"]] = r
    out = {}
    for code, v in ev.items():
        base = {"question": v["question_en"], "is_antecedent": v["is_antecedent"], "data_type": v["data_type"],
                "negative_ok": False, "value_rule": ""}
        if v["data_type"] == "C" and v["possible-values"] and all(isinstance(x, int) for x in v["possible-values"]):
            base["value_rule"] = NUMERIC_SCALE              # 0 = 없음 → 양성 아님
        elif v["data_type"] == "C" and {m.get("en") for m in v.get("value_meaning", {}).values()} >= {"N", "Y"}:
            base["value_rule"] = "YN"                       # V_12 = Y 만 양성, N 은 명시적 아니오
        if v["is_antecedent"]:
            if code in RISK_REVIEW:
                out[code] = {**base, "status": "REVIEW", "hp_ids": [], "used": False,
                             "reason": f"후보 {RISK_REVIEW[code][0]}: {RISK_REVIEW[code][1]}"}
            elif code in ANTECEDENT_REVIEW:
                out[code] = {**base, "status": ANTECEDENT_REVIEW[code][0], "hp_ids": [], "used": False,
                             "reason": ANTECEDENT_REVIEW[code][1]}
            else:
                out[code] = {**base, "status": "NOT_ASSESSED", "hp_ids": [], "used": False,
                             "reason": "병력 문항 — 미조사(4질환 직접 관련 항목만 조사함)"}
            continue
        r = cur.get(code)
        if r is None:
            out[code] = {**base, "status": "NOT_ASSESSED", "hp_ids": [], "used": False, "reason": "STEP20 매핑 없음"}
            continue
        hps = [h for h in r["hpo_ids"].split(";") if h]
        cls, role, canon = r["hpo_class"], r["role"], r["canonical_concept"]
        if code in OVERRIDES:
            st, hps, reason = OVERRIDES[code]
            reason = "35회차 재판정: " + reason
        elif cls in ("NO_MATCH", "NOT_APPLICABLE") or not hps:
            st, reason = "NO_CONCEPT", f"STEP20 {cls} ({role}): {r['hpo_reason']}"
        elif role == "COMPOSITE" and " OR " in canon and cls != "ACCEPTABLE_BROADER":
            st, reason = "REVIEW", f"OR 복합 질문 — 단일 HPO 개념({hps})이 모든 경우를 포함하는지 미확인 ({canon})"
        elif len(hps) > 1 and " AND " not in canon:
            st, reason = "REVIEW", f"여러 개념 중 하나만 있어도 '예'인 질문 — 어느 개념인지 모름 ({canon})"
        elif role == "MODIFIER" and cls != "EXACT":
            st, reason = "REVIEW", f"수식어 질문({canon}) — STEP20 {cls}"
        elif cls == "EXACT":
            st, reason = "EXACT", f"STEP20 EXACT: {r['hpo_reason']}"
        elif cls == "ACCEPTABLE_BROADER" and len(hps) == 1:
            st, reason = "EXACT_BROADER", f"STEP20 ACCEPTABLE_BROADER(HPO 가 더 넓음 → 양성만 함의): {r['hpo_reason']}"
        else:
            st, reason = "REVIEW", f"STEP20 {cls}: {r['hpo_reason']}"
        used = st in ("EXACT", "EXACT_BROADER")
        out[code] = {**base, "status": st, "hp_ids": hps if used else [], "candidate_hp_ids": hps, "used": used,
                     "negative_ok": st == "EXACT" and len(hps) == 1, "reason": reason}
    out["E_55"] = {**out["E_55"], "status": "EXACT_COMPOSITE", "hp_ids": [CHEST_PAIN_HP], "used": True,
                   "reason": f"E_53 양성 + E_55 ∈ {list(CHEST_SITES)} → 흉통(HP:0100749). 유방·견갑골·흉추·늑하부 제외. 통증 성질(E_54)은 쓰지 않음. 검토 권장"}
    out["E_220"] = {**out["E_220"], "status": "EXACT_COMPOSITE", "hp_ids": [PLEURITIC_HP], "used": True, "negative_ok": True,
                    "reason": "37회차: E_220 양성 + 흉통 복합(E_53+E_55 흉부) + E_54 ∈ {knife stroke, burning, sharp} → 흉막성 흉통(HPO 정의의 "
                              "흡기 시 악화·흉부·성질 모두 명시 값). 성질 값이 없으면 연결 안 함. 음성(흡기 악화 없음) → 흉막성 흉통 음성(필수 성분 부재)"}
    limb = limb_sites()
    out["E_151"] = {**out["E_151"], "status": "EXACT_COMPOSITE", "hp_ids": [LIMB_SWELLING_HP], "used": True, "negative_ok": True,
                    "reason": f"37회차: E_151 양성 + E_152 사지 부위({len(limb)}값) → 사지 국소 연부조직 부종(HP:6000840). Edema(체액 저류)·DVT 로 연결 안 함"
                              "(HPO Edema 의 'Soft tissue swelling' 은 BROAD 동의어). 사지 외 부위는 연결 안 함. 음성(부종 없음) → HP:6000840 음성"}
    out["E_152"] = {**out["E_152"], "status": "EXACT_COMPOSITE", "hp_ids": [LIMB_SWELLING_HP], "used": True,
                    "reason": "E_151 의 부위 값(성분)"}
    out["E_54"] = {**out["E_54"], "status": "NO_CONCEPT", "hp_ids": [], "used": False,
                   "reason": "37회차: 통증 성질 단독은 HPO 수식어(Sharp HP:0025281 등 clinical modifier) — 소견 아님. 흉막성 흉통 복합의 성분으로만 사용"}
    out["E_33"] = {**out["E_33"], "reason": out["E_33"]["reason"] + " · 37회차 hp.obo 이름 검색('leaning/sitting forward', 자세) 해당 용어 없음 — NO_CONCEPT 유지"}
    out["E_33"] = {**out["E_33"], "status": "EXACT_COMPOSITE", "hp_ids": [POSITIONAL_NODE], "used": True,
                   "reason": "38회차: E_33(앞으로 숙이면 통증 완화) + 흉통 복합(E_53+E_55 흉부) → 개념 노드 '앞으로 숙이면 완화되는 흉통'"
                             "(DisMech 심낭염 흉통 설명 'relieved by sitting forward'; HPO 용어 없음, lean≈sitting forward 자세 동일로 판정)"}
    out["E_2"] = {**out["E_2"], "status": "EXACT", "hp_ids": [HIV_NODE], "used": True, "negative_ok": True,
                  "reason": "38회차: HIV 감염 여부(환자 보고) = 개념 노드 HIV 감염. CHEST 2018 결핵 선별 조건(PLWHIV)에 사용"}
    out["E_57"] = {**out["E_57"], "value_rule": "SITE_OR_NOWHERE",
                   "reason": out["E_57"]["reason"] + " · 값 V_123('nowhere') = 방사 없음(명시적 음성), 그 외 부위 = 방사통 양성"}
    return out


@functools.lru_cache(maxsize=1)
def limb_sites() -> tuple:
    vm = load_evidences()["E_152"]["value_meaning"]
    return tuple(sorted(k for k, v in vm.items() if any(w in v.get("en", "") for w in LIMB_WORDS)))


def mapping_summary(m: dict) -> dict:
    def cnt(pred):
        return sum(1 for v in m.values() if pred(v))
    return {"total": len(m),
            "symptoms": cnt(lambda v: not v["is_antecedent"]), "antecedents": cnt(lambda v: v["is_antecedent"]),
            **{st: cnt(lambda v, st=st: v["status"] == st)
               for st in ("EXACT", "EXACT_BROADER", "EXACT_COMPOSITE", "REVIEW", "NO_CONCEPT", "NO_KB_RELATION",
                          "NOT_ASSESSED")},
            "used_in_inference": cnt(lambda v: v["used"]), "negative_answer_usable": cnt(lambda v: v["negative_ok"])}


def parse_tokens(evidences_str: str) -> dict:
    """"['E_48', 'E_55_@_V_29', ...]" → {E 코드: [값...]} (이진은 빈 목록)."""
    toks = json.loads(evidences_str.replace("'", '"'))
    out: dict = {}
    for t in toks:
        code, _, val = t.partition("_@_")
        out.setdefault(code, [])
        if val:
            out[code].append(val)
    return out


def answer_records(pid: str, code: str, status: Status, vals: list, m: dict, t: float, raw: str | None = None) -> list:
    """DDXPlus 질문 하나의 답 → EvidenceRecord 목록.
    - 양성: 사용 매핑이면 HP 양성(값 규칙 적용), 아니면 'DDX:E_xx'(그래프 밖).
    - 명시적 음성: negative_ok(같은 개념 EXACT 단일)일 때만 HP 음성. 상위 개념 연결·복합·검토 필요는 그래프 밖 음성으로만 보존.
    - 불확실·미검사: 같은 개념 EXACT 단일만 HP 에 같은 상태, 그 외 그래프 밖.
    - 값 규칙: NUMERIC_SCALE 0 = 없음(양성 아님) · YN 'N' = 명시적 아니오 · E_57 'nowhere' = 방사통 명시적 음성."""
    mm = m.get(code, {})
    src = f"{pid}-{code}"
    raw = raw or (code if not vals else ";".join(f"{code}_@_{v}" for v in vals))
    prov = f"DDXPlus {code}: {mm.get('question', '')} [{mm.get('status', '?')}]"

    def rec(node, st, suffix, value=raw, note=""):
        return EvidenceRecord(node, st, src, t, t, "patient_report", value=value, provenance=prov + note,
                              evidence_id=f"{src}-{suffix}")

    out = []
    rule = mm.get("value_rule", "")
    if status == Status.POSITIVE and rule == NUMERIC_SCALE and vals and all(str(v) == "0" for v in vals):
        return [rec(f"DDX:{code}", Status.NEGATIVE, "x", note=" (척도 0 = 없음)")]
    if status == Status.POSITIVE and rule == "YN" and vals and set(vals) <= {"V_10"}:
        status = Status.NEGATIVE                                  # 'N' 선택 = 명시적 아니오
    if code == "E_57" and status == Status.POSITIVE:
        sites = [v for v in vals if v != "V_123"]
        if "V_123" in vals and not sites:
            return [rec(mm["hp_ids"][0], Status.NEGATIVE, "0", note=" (방사 부위 'nowhere' = 방사 없음)")]
        vals = sites
    if code == "E_55" or (status == Status.POSITIVE and code in COMPOSITE_CODES):
        return [rec(f"DDX:{code}", status, "x", note=" (복합 성분 — case_records 에서 해석)")] if code != "E_55" else out
    if status == Status.POSITIVE and mm.get("used"):
        return [rec(hp, Status.POSITIVE, str(i)) for i, hp in enumerate(mm["hp_ids"])]
    if status != Status.POSITIVE and mm.get("negative_ok"):
        return [rec(mm["hp_ids"][0], status, "0")]
    return [rec(f"DDX:{code}", status, "x")]


def case_records(pid: str, case: dict, m: dict, codes, t: float) -> list:
    """codes 에 속한 DDXPlus 기록 근거(EVIDENCES = 양성 답) → EvidenceRecord. 기록에 없는 질문은 만들지 않는다(미기록)."""
    toks = parse_tokens(case["EVIDENCES"])
    recs = []
    for code in codes:
        if code not in toks:
            continue
        vals = toks[code]
        if code == "E_55":
            src = f"{pid}-{code}"
            raw = ";".join(f"{code}_@_{v}" for v in vals)
            prov = f"DDXPlus {code}: {m.get(code, {}).get('question', '')} [{m.get(code, {}).get('status', '?')}]"
            chest = [v for v in vals if v in CHEST_SITES]
            if chest and "E_53" in toks:
                recs.append(EvidenceRecord(CHEST_PAIN_HP, Status.POSITIVE, src, t, t, "patient_report", value=raw,
                                           provenance=prov + " + E_53", evidence_id=f"{src}-chest"))
            other = [v for v in vals if v not in CHEST_SITES]
            if other:
                recs.append(EvidenceRecord(f"DDX:{code}", Status.POSITIVE, src, t, t, "patient_report",
                                           value=";".join(other), provenance=prov + " (흉부 외 부위: 연결 개념 없음)",
                                           evidence_id=f"{src}-other"))
            continue
        if code == "E_220":
            chest = "E_53" in toks and any(v in CHEST_SITES for v in toks.get("E_55", []))
            if chest and set(toks.get("E_54", [])) & set(PLEURITIC_QUALITY):
                recs.append(EvidenceRecord(PLEURITIC_HP, Status.POSITIVE, f"{pid}-E_220", t, t, "patient_report",
                                           value="E_220+E_55흉부+E_54" + ",".join(sorted(set(toks["E_54"]) & set(PLEURITIC_QUALITY))),
                                           provenance=f"DDXPlus E_220: {m['E_220']['question']} + 흉부 부위 + 성질 [EXACT_COMPOSITE]",
                                           evidence_id=f"{pid}-E_220-pl"))
                continue
            recs += answer_records(pid, code, Status.POSITIVE, vals, m, t)   # 조건 미충족 → 그래프 밖
            continue
        if code == "E_151":
            sites = [v for v in toks.get("E_152", []) if v in limb_sites()]
            if sites:
                recs.append(EvidenceRecord(LIMB_SWELLING_HP, Status.POSITIVE, f"{pid}-E_151", t, t, "patient_report",
                                           value="E_151+E_152:" + ",".join(sites),
                                           provenance=f"DDXPlus E_151: {m['E_151']['question']} + 사지 부위 [EXACT_COMPOSITE]",
                                           evidence_id=f"{pid}-E_151-limb"))
                continue
            recs += answer_records(pid, code, Status.POSITIVE, vals, m, t)
            continue
        if code == "E_152":
            continue                                                  # E_151 과 함께 처리
        if code == "E_33":
            chest = "E_53" in toks and any(v in CHEST_SITES for v in toks.get("E_55", []))
            if chest:
                recs.append(EvidenceRecord(POSITIONAL_NODE, Status.POSITIVE, f"{pid}-E_33", t, t, "patient_report",
                                           value="E_33+E_55흉부", evidence_id=f"{pid}-E_33-pos",
                                           provenance=f"DDXPlus E_33: {m['E_33']['question']} + 흉부 부위 [EXACT_COMPOSITE]"))
                continue
            recs += answer_records(pid, code, Status.POSITIVE, vals, m, t)
            continue
        recs += answer_records(pid, code, Status.POSITIVE, vals, m, t)
    return recs


def split_phases(case: dict, m: dict) -> tuple[list, list]:
    """1단계 = 첫 증상 + 병력(접수 시 정보), 2단계 = 나머지 증상 답변(추가 질문). E_55 는 E_53 과 같은 단계."""
    toks = parse_tokens(case["EVIDENCES"])
    first = {case["INITIAL_EVIDENCE"]} | {c for c in toks if m.get(c, {}).get("is_antecedent")}
    if "E_53" in first:
        first.add("E_55")
    p1 = [c for c in toks if c in first]
    p2 = [c for c in toks if c not in first]
    return p1, p2


def patient_from_case(pid: str, case: dict, m: dict, working_dx: str | None) -> tuple[PatientRecord, list, list]:
    pr = PatientRecord(pid, age=int(case["AGE"]), sex=case["SEX"], working_dx=working_dx)
    p1, p2 = split_phases(case, m)
    for r in case_records(pid, case, m, p1, 1.0):
        pr.add(r)
    return pr, p1, case_records(pid, case, m, p2, 2.0)
