"""검사 수치·단위·검사법·검사실 기준값과 시계열.
원칙: 기록에 있는 값만 담는다. 단위 변환 없음(검증된 변환 규칙 없음). 기준값을 만들지 않는다.
'high-sensitivity'는 검사법(assay_type)이지 결과 해석('high')이 아니다. 기준 초과 ≠ 진단 기준 충족."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from hybrid4.graphs import T1, DataClass, EvidenceItem, EvidenceKind, Polarity, Provenance

UNK = "UNKNOWN"
UNITS = {"ng/l": "ng/L", "ng/ml": "ng/mL", "pg/ml": "pg/mL", "µg/l": "µg/L", "μg/l": "µg/L", "ug/l": "µg/L", "mcg/l": "µg/L", "mg/l": "mg/L", "mg/dl": "mg/dL"}
R_UNIT = r"(ng/l|ng/ml|pg/ml|µg/l|μg/l|ug/l|mcg/l|mg/l|mg/dl)"
R_NUM = re.compile(r"(<|>|≤|≥)?\s*(\d+(?:\.\d+)?)\s*" + R_UNIT + r"(?![a-z])", re.I)
R_TROP = re.compile(r"(?P<hs>high[- ]sensitivity\s+(?:cardiac\s+)?|hs-?)?(?:(?:cardiac\s+)?troponin(?:\s+(?P<it>[IT])\b)?|c?Tn(?P<it2>[IT])\b)", re.I)
R_CRP = re.compile(r"\bC[- ]reactive protein\b|\bCRP\b", re.I)
R_POC = re.compile(r"point[- ]of[- ]care", re.I)
R_REF = re.compile(r"(?P<label>99th[- ]percentile(?:\s+(?:upper reference limit|URL))?(?:\s*\(URL\))?|upper reference limit(?:\s*\(URL\))?|\bURL\b|upper limit of normal|\bULN\b|reference(?: range| limit| value)?|normal(?: range)?|\bNV\b|n\.v\.)"
                   r"\s*(?:\(URL\))?\s*(?:for\s+(?P<pop>women|females?|men|males?)\s*)?(?:[:=,]|of|is|was)?\s*(?P<cmp><|≤)?\s*(?P<val>\d+(?:\.\d+)?)\s*(?P<unit>" + R_UNIT[1:-1] + r")?", re.I)
R_OFFSET = re.compile(r"(?:at|after)\s+(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hours?)\b|(\d+(?:\.\d+)?)\s*(?:h|hours?)\s+later", re.I)
R_BASE = re.compile(r"\b(?:baseline|initial|admission|on arrival|at presentation)\b", re.I)
R_QUAL = re.compile(r"\b(elevated|raised|increased|high|normal|within normal limits|negative|positive|undetectable)\b", re.I)


@dataclass
class Observation:
    obs_id: str
    patient_id: str
    episode_id: str
    analyte: str                       # TROPONIN_I / TROPONIN_T / TROPONIN_UNSPECIFIED / CRP
    raw_value: str
    numeric_value: float | None
    comparator: str                    # '=', '<', '>'
    unit: str
    observation_time: float | None
    available_time: float | None
    source_record_id: str
    assay_name: str = UNK
    assay_type: str = UNK              # HIGH_SENSITIVITY / POINT_OF_CARE / UNKNOWN
    reference_lower: float | None = None
    reference_upper: float | None = None
    reference_unit: str = UNK
    reference_percentile: str = UNK
    reference_population: str = UNK    # FEMALE / MALE / ALL_STATED / UNKNOWN
    result_qualifier: str = UNK
    source_type: str = "RECORD"
    extraction_status: str = "EXTRACTED"
    time_basis: str = UNK
    supersedes: str | None = None
    concept_id: str = ""
    test_name: str = ""
    notes: list = field(default_factory=list)

    def to_item(self) -> EvidenceItem:
        return EvidenceItem(self.obs_id, self.patient_id, EvidenceKind.OTHER, self.raw_value, Provenance("observation", self.source_record_id, DataClass.SYNTHETIC),
                            observed_at=self.observation_time, available_at=self.available_time, polarity=Polarity.UNKNOWN, supersedes=self.supersedes)

    def as_row(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def _unit(u):
    return UNITS.get(u.lower(), u) if u else UNK


def _pop(p):
    if not p:
        return UNK
    return "FEMALE" if p.lower().startswith(("wom", "fem")) else "MALE"


def extract(text: str, patient_id: str, episode_id: str, record_id: str, observed_at, available_at) -> list:
    """문장 단위 추출. 값은 같은 문장의 가장 가까운 앞쪽 분석물 언급에 붙인다. 분석물이 없으면 버린다(추측 안 함)."""
    obs = []
    for si, sent in enumerate(re.split(r"(?<=[.;])\s+", text)):
        refs = [(m.start(), m.end(), m) for m in R_REF.finditer(sent)]
        ans = [(m.start(), m.end(), "TROPONIN_" + ((m.group("it") or m.group("it2") or "UNSPECIFIED").upper()), m) for m in R_TROP.finditer(sent)] + \
              [(m.start(), m.end(), "CRP", m) for m in R_CRP.finditer(sent)]
        ans.sort()
        for vi, v in enumerate(R_NUM.finditer(sent)):
            if any(a <= v.start() < b for a, b, _ in refs):
                continue                                                         # 기준값 숫자는 결과가 아님
            prev = [a for a in ans if a[1] <= v.start()]
            if not prev:
                continue
            a0, a1, analyte, am = prev[-1]
            if analyte.startswith("TROPONIN") and not am.group("it") and not am.group("it2"):
                # 'troponin ... T' 같은 뒤쪽 표기 없음 → I/T 미상
                pass
            seg = sent[a1:v.start()]
            ctx = sent[max(0, a0 - 60):v.end() + 40]
            hs = bool(am.groupdict().get("hs")) if analyte.startswith("TROPONIN") else False
            assay_type = "HIGH_SENSITIVITY" if hs else "POINT_OF_CARE" if R_POC.search(ctx) else UNK
            masked = list(sent)                                                    # 기준값 구간·'high-sensitivity' 표기는 결과 해석 단어로 읽지 않음
            for x0, x1 in [(r0, r1) for r0, r1, _ in refs] + [(m.start(), m.end()) for m in R_TROP.finditer(sent)]:
                masked[x0:x1] = " " * (x1 - x0)
            stop = min([w.start() for w in R_NUM.finditer(sent) if w.start() > v.end() and not any(r0 <= w.start() < r1 for r0, r1, _ in refs)] + [len(sent), v.end() + 45])
            ms = "".join(masked)
            prev_vals = [w.end() for w in R_NUM.finditer(sent) if a1 <= w.end() <= v.start() and not any(r0 <= w.start() < r1 for r0, r1, _ in refs)]
            q = R_QUAL.search(ms[v.end():stop]) or (R_QUAL.search(ms[max(0, a0 - 20):v.start()]) if not prev_vals else None)   # 값 뒤 우선, 앞은 분석물의 첫 값일 때만
            near_ref = [r for r in refs if r[2].start() >= v.end() and r[2].start() - v.end() <= 60] or [r for r in refs if a0 <= r[0] < v.start()]
            ref = near_ref[0][2] if near_ref else None
            nxt = [w.start() for w in R_NUM.finditer(sent) if w.start() > v.end()]
            after = sent[v.end():min(nxt[0] if nxt else len(sent), v.end() + 30)]               # 값 바로 뒤 시간 표현('35 ng/L at 3 hours')
            before = sent[max(a1, max([w.end() for w in R_NUM.finditer(sent) if w.end() <= v.start()] or [a1])):v.start()]
            off = R_OFFSET.search(after) or R_OFFSET.search(before)
            base = R_BASE.search(after) or R_BASE.search(before)
            first_of_analyte = not obs or obs[-1].analyte != analyte or obs[-1].source_record_id != record_id or obs[-1].obs_id.split(":")[2] != str(si)
            off_h = float(off.group(1) or off.group(2)) if off else (0.0 if base or first_of_analyte else None)
            t_obs = (observed_at + off_h) if (observed_at is not None and off_h is not None) else (observed_at if off_h == 0.0 else None)
            o = Observation(obs_id=f"OBS:{record_id}:{si}:{vi}", patient_id=patient_id, episode_id=episode_id, analyte=analyte, raw_value=v.group(0).strip(),
                            numeric_value=float(v.group(2)), comparator={"<": "<", "≤": "<", ">": ">", "≥": ">"}.get(v.group(1) or "", "="), unit=_unit(v.group(3)),
                            observation_time=t_obs, available_time=available_at, source_record_id=record_id, assay_type=assay_type,
                            result_qualifier=q.group(1).lower() if q else UNK, time_basis="RECORD_TIME_PLUS_STATED_OFFSET" if off else ("RECORD_TIME" if t_obs is not None else UNK),
                            concept_id="LAB:" + analyte, test_name=sent[a0:a1])
            if off_h is None:
                o.notes.append("측정 시각 미상: 같은 문장의 두 번째 이후 값인데 시간 표현 없음")
            if ref:
                o.reference_upper = float(ref.group("val"))
                o.reference_unit = _unit(ref.group("unit")) if ref.group("unit") else o.unit + "(단위 생략, 같은 단위로 기재됐다고 보지 않음)"
                o.reference_percentile = "99th" if "99" in ref.group("label") else UNK
                o.reference_population = _pop(ref.group("pop")) if ref.group("pop") else "NOT_STATED"
            obs.append(o)
    return obs


# ---------------- 시계열 ----------------
def comparable(a: Observation, b: Observation) -> tuple:
    if a.analyte != b.analyte:
        return False, "ANALYTE_DIFFERENT"
    if "UNSPECIFIED" in a.analyte:
        return None, "TROPONIN_I_OR_T_UNKNOWN"
    if a.unit != b.unit:
        return False, "UNIT_MISMATCH(변환 규칙 없음)"
    if UNK in (a.assay_type, b.assay_type):
        return None, "ASSAY_TYPE_UNKNOWN"
    if a.assay_type != b.assay_type:
        return False, "ASSAY_TYPE_DIFFERENT"
    if a.assay_name != UNK and b.assay_name != UNK and a.assay_name != b.assay_name:
        return False, "ASSAY_NAME_DIFFERENT"
    return True, "SAME_ANALYTE_UNIT_ASSAY_TYPE" + ("" if a.assay_name != UNK and b.assay_name != UNK else "(assay_name 미기재)")


def visible(obs: list, as_of: float) -> list:
    ids = {i.evidence_id for i in T1.visible_evidence([o.to_item() for o in obs], as_of)}
    return [o for o in obs if o.obs_id in ids]


def above_reference(o: Observation, patient_sex: str = UNK) -> dict:
    if o.reference_upper is None:
        return {"status": UNK, "reason": "기준값 없음(만들지 않음)"}
    if o.reference_unit != o.unit:
        return {"status": UNK, "reason": f"기준 단위 불일치·불명({o.reference_unit} vs {o.unit})"}
    if o.comparator == "<" and o.numeric_value <= o.reference_upper:
        st = "NOT_ABOVE"
    elif o.comparator == "<":
        st = UNK
    else:
        st = "ABOVE" if o.numeric_value > o.reference_upper else "NOT_ABOVE"
    sex_ok = "MATCHES_PATIENT_SEX" if o.reference_population in ("FEMALE", "MALE") and o.reference_population == patient_sex else \
             "SEX_SPECIFIC_NOT_CONFIRMED"
    return {"status": st, "reference_upper": o.reference_upper, "percentile": o.reference_percentile, "population": o.reference_population, "sex_specific_reference": sex_ok,
            "reason": "검사실 기준값과 비교한 수학적 결과일 뿐 진단 기준 판정 아님"}


def build_series(obs: list, as_of: float, patient_sex: str = UNK) -> list:
    """분석물별 시간순 정렬. 연속 쌍마다 비교 가능 여부 → 가능할 때만 변화량. 임상적 유의성 판정 없음."""
    out = []
    v = visible(obs, as_of)
    for analyte in sorted({o.analyte for o in v}):
        xs = sorted([o for o in v if o.analyte == analyte], key=lambda o: (o.observation_time is None, o.observation_time or 0, o.obs_id))
        pairs = []
        for a, b in zip(xs, xs[1:]):
            ok, why = comparable(a, b)
            p = {"from": a.obs_id, "to": b.obs_id, "comparable": ok, "comparability_reason": why, "interval": None, "abs_delta": None, "rel_delta": None, "delta_status": ""}
            if a.observation_time is not None and b.observation_time is not None:
                p["interval"] = round(b.observation_time - a.observation_time, 4)
            if ok is not True:
                p["delta_status"] = "WITHHELD_" + why
            elif "=" not in (a.comparator,) or b.comparator != "=":
                p["delta_status"] = "WITHHELD_CENSORED_VALUE(<, >)"
            elif p["interval"] is None:
                p["delta_status"] = "WITHHELD_TIME_UNKNOWN"
            else:
                p["abs_delta"] = round(b.numeric_value - a.numeric_value, 6)
                p["rel_delta"] = round(p["abs_delta"] / a.numeric_value, 6) if a.numeric_value > 0 else None
                p["delta_status"] = "COMPUTED_MATH_ONLY(임상적 유의 변화 판정 아님)"
            pairs.append(p)
        out.append({"analyte": analyte, "points": [{"obs_id": o.obs_id, "time": o.observation_time, "value": o.numeric_value, "comparator": o.comparator, "unit": o.unit,
                                                    "assay_type": o.assay_type, "reference_check": above_reference(o, patient_sex), "source_record_id": o.source_record_id,
                                                    "superseded": False} for o in xs], "pairs": pairs,
                    "superseded_hidden": sorted(x.obs_id for x in obs if x.analyte == analyte and x not in v and any(y.supersedes == x.obs_id for y in v))})
    return out
