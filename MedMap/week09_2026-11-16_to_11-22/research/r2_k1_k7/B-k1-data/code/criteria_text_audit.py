"""Count criterion lines by type across fetched ClinicalTrials.gov records (untrusted text, parse only)."""
import csv, glob, json, os, re
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAT = {
 "numeric_threshold": r"(\d+(\.\d+)?\s*(%|mL/min|mg/g|mmol|ng/L|years|Gy|x ULN|ULN))|[≥≤]|\\[<>]|greater than|less than",
 "temporal_window": r"within \d+|\d+\s*(weeks|days|months|years)\s*(prior|before)|at least \d+ (weeks|months)|for at least|persistent|2 out of 3",
 "vague_term": r"(?i)adequate|significant|clinically relevant|uncontrolled|severe|clinically (active|appropriate)|known to be poorly",
 "investigator_judgement": r"(?i)investigator|judg|in the opinion|as selected by",
 "renal_mention": r"(?i)eGFR|creatinine|renal|kidney|dialysis|CrCl|glomerular",
}
rows = []
for f in sorted(glob.glob(os.path.join(BASE, "data/ctgov/*.json"))):
    d = json.load(open(f)); p = d["protocolSection"]
    txt = p["eligibilityModule"].get("eligibilityCriteria", "")
    lines = [l.strip(" *-\t") for l in re.split(r"\n|(?<=\s)-\s(?=[A-Z])", txt) if len(l.strip(" *-\t")) > 15 and not re.match(r"(?i)^(key )?(inclusion|exclusion) criteria", l.strip(" *-\t"))]
    r = {"nct": p["identificationModule"]["nctId"], "acronym": p["identificationModule"].get("acronym", ""), "n_lines": len(lines), "chars": len(txt)}
    for k, pat in PAT.items():
        r[k] = sum(bool(re.search(pat, l)) for l in lines)
    r["renal_lines_text"] = " | ".join(l[:90] for l in lines if re.search(PAT["renal_mention"], l))[:400]
    rows.append(r)
with open(os.path.join(BASE, "results_criteria_text_audit.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
tot = {k: sum(r[k] for r in rows) for k in ["n_lines"] + list(PAT)}
print("TOTAL", tot)
for r in rows: print(r["nct"], r["acronym"], r["n_lines"], r["numeric_threshold"], r["temporal_window"], r["vague_term"], r["investigator_judgement"], "renal:", r["renal_lines_text"][:200])
