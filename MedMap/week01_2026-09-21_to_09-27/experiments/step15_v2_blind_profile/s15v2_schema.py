"""STEP15 v2 schema + strict validators. Facts are Python objects, never hand-typed TSV."""
from dataclasses import dataclass, field, asdict, fields
import re, pathlib

RAW = pathlib.Path("data/disease_profiles_v2/raw")

DISEASES = ["Acute rhinosinusitis","Chronic rhinosinusitis","Acute laryngitis","Viral pharyngitis",
 "Stable angina","Unstable angina","Acute HIV infection","Scombroid poisoning",
 "Acute COPD exacerbation","PSVT"]
CATEGORIES = {"symptom","sign","negative_finding","temporal","trigger_relief","risk_factor","exposure",
 "history","family_history","medication","demographic","lab_finding","diagnostic_criteria",
 "differentiating_feature","red_flag","associated_symptom","etiology","location"}
RELATIONS = {"has_symptom","has_sign","lacks_finding","has_duration","has_onset","has_location",
 "triggered_by","relieved_by","aggravated_by","has_risk_factor","has_exposure","has_history",
 "has_family_history","medication_related","affects_demographic","has_lab_finding",
 "diagnostic_criterion","differentiated_by","red_flag","has_progression","has_frequency","has_etiology",
 "has_severity","has_quality"}
ROLES = {"core_symptom","supporting","diagnostic_criterion","differentiating","risk","red_flag","lab","exclusion","contextual"}
TIERS = {"tier1","tier2","tier3"}
ANAT = ["chest","breastbone","sternum","throat","larynx","voice box","vocal","nose","nasal","sinus","face","facial",
 "cheek","forehead","eye","ear","pharynx","tonsil","neck","jaw","arm","shoulder","back","lymph","mouth","oral",
 "skin","trunk","upper body","lung","airway","abdomen","stomach","heart","atria","upper chambers","middle meatus",
 "paranasal","head","teeth","tooth","dental","lips","fingernail","ankle","leg","glottic","supraglottic"]
TIME_UNIT = re.compile(r"(second|minute|min\b|hour|day|week|month|year|overnight)", re.I)
TIME_HINT = re.compile(r"(\d|few|several|minute|hour|day|week|month|year|<|≤|≥|>|long|short|persist|brief|transient)", re.I)
ONSET_HINT = re.compile(r"(sudden|abrupt|gradual|slowly|acute|within|after|immediately|recent|new|begins|starts|onset|minutes|hours|days|weeks|follow)", re.I)
FAMILY_HINT = re.compile(r"(family|relative|parent|sibling|hereditary)", re.I)
FLOATY = re.compile(r"^\s*0?\.\d+\s*$")

@dataclass
class Fact:
    fact_id: str = ""
    disease: str = ""
    fact_category: str = ""
    base_concept: str = ""
    relation: str = ""
    value_raw: str = ""
    value_normalized: str = ""
    unit: str = ""
    location: str = ""
    severity: str = ""
    onset: str = ""
    duration: str = ""
    frequency: str = ""
    frequency_raw: str = ""
    progression: str = ""
    trigger: str = ""
    aggravating_factor: str = ""
    relieving_factor: str = ""
    history_context: str = ""
    family_context: str = ""
    exposure_context: str = ""
    medication_context: str = ""
    positive_or_negative: str = "positive"
    diagnostic_role: str = "supporting"
    source_id: str = ""
    source_strength: str = ""
    source_quote_short: str = ""
    review_needed: bool = False
    review_reason: str = ""
    conflict_group_id: str = ""
    conflict_note: str = ""
    source_limitation: bool = False
    notes: str = ""

def norm(s):
    s = s.replace("’","'").replace("‘","'").replace("“",'"').replace("”",'"')
    s = s.replace("–","-").replace("—","-").replace("−","-").replace("\xa0"," ").replace("­","")
    s = s.replace("ﬁ","fi").replace("ﬂ","fl")
    return re.sub(r"\s+"," ",s).strip().lower()

_TEXT_CACHE = {}
def source_text(sid):
    if sid not in _TEXT_CACHE:
        _TEXT_CACHE[sid] = norm((RAW/f"{sid}.txt").read_text(errors="replace"))
    return _TEXT_CACHE[sid]

def validate(f: Fact, registry: dict):
    e = []
    if f.disease not in DISEASES: e.append(f"disease {f.disease}")
    if f.fact_category not in CATEGORIES: e.append(f"category {f.fact_category}")
    if f.relation not in RELATIONS: e.append(f"relation {f.relation}")
    if f.diagnostic_role not in ROLES: e.append(f"role {f.diagnostic_role}")
    if f.positive_or_negative not in {"positive","negative"}: e.append("pos/neg")
    if not f.base_concept: e.append("base_concept empty")
    if not f.value_raw: e.append("value_raw empty")
    if f.source_id not in registry: e.append(f"unknown source {f.source_id}")
    else:
        src = registry[f.source_id]
        if src["status"] != "OK": e.append(f"source {f.source_id} not OK")
        if f.source_strength != src["source_tier"]: e.append(f"tier mismatch {f.source_strength}!={src['source_tier']}")
    if not f.source_quote_short: e.append("quote empty")
    else:
        if len(f.source_quote_short.split()) > 15: e.append("quote >15 words")
        if f.source_id in registry and norm(f.source_quote_short) not in source_text(f.source_id):
            e.append(f"QUOTE NOT IN SOURCE: {f.source_quote_short!r}")
    # column placement rules
    if f.family_context and not FAMILY_HINT.search(f.family_context): e.append("family_context not family")
    if f.fact_category == "family_history" and not f.family_context: e.append("family_history without family_context")
    if f.family_context and f.fact_category != "family_history": e.append("family_context in non-family fact")
    if f.duration and not (TIME_UNIT.search(f.duration) and TIME_HINT.search(f.duration)): e.append(f"duration not time: {f.duration}")
    if f.onset and not ONSET_HINT.search(f.onset): e.append(f"onset not onset-like: {f.onset}")
    if f.trigger and (TIME_UNIT.search(f.trigger) or re.search(r"\d",f.trigger)): e.append(f"trigger contains time/number: {f.trigger}")
    if f.location and not any(a in f.location.lower() for a in ANAT): e.append(f"location not anatomical: {f.location}")
    if f.history_context and FAMILY_HINT.search(f.history_context): e.append("family term inside history_context")
    for col in ("frequency","frequency_raw"):
        if FLOATY.match(getattr(f,col) or ""): e.append(f"{col} looks like invented probability")
    if f.frequency and not f.frequency_raw: e.append("frequency without frequency_raw (source literal required)")
    if f.value_normalized and re.search(r"\d", f.value_normalized) and not re.search(r"\d", f.value_raw):
        e.append("numeric value_normalized without numeric value_raw (quantification forbidden)")
    if f.relation == "has_duration" and not f.duration: e.append("has_duration without duration")
    if f.relation == "triggered_by" and not f.trigger: e.append("triggered_by without trigger")
    if f.relation == "relieved_by" and not f.relieving_factor: e.append("relieved_by without relieving_factor")
    if f.relation == "has_location" and not f.location: e.append("has_location without location")
    if f.relation == "has_exposure" and not f.exposure_context: e.append("has_exposure without exposure_context")
    if f.relation == "medication_related" and not f.medication_context: e.append("medication without medication_context")
    if f.relation == "lacks_finding" and f.positive_or_negative != "negative": e.append("lacks_finding must be negative")
    return e

COLUMNS = [x.name for x in fields(Fact)]
