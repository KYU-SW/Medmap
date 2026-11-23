"""K7 example check: can plain SQL over (valid time, availability time, transaction time) + approval events
answer the 'as-of decision time' questions?  Standard library only (sqlite3).  Synthetic toy data, no real patient data.

Axes (names follow Combi/Montanari/Pozzi's four-dimensional clinical model, T4SQL):
  vt_from/vt_to   valid time: when the state held for the patient (may be indeterminate: vt_from_lo..vt_from_hi)
  ev_time         event time: when the generating event (utterance / lab release) happened
  at_from/at_to   availability time: when the information system (incl. clinician/MedMap) knew & believed it
  tx_from/tx_to   transaction time: when this row was current in the database (append-only)
"""
import sqlite3

INF = "9999-12-31"
db = sqlite3.connect(":memory:")
db.executescript(
    """
CREATE TABLE fact(
  id TEXT, subject TEXT, attr TEXT, value TEXT, source TEXT,
  vt_from_lo TEXT, vt_from_hi TEXT, vt_to TEXT, ev_time TEXT,
  at_from TEXT, at_to TEXT, tx_from TEXT, tx_to TEXT);
CREATE TABLE approval(            -- clinician confirmation of an extracted fact = a separate event with its own times
  fact_id TEXT, state TEXT, at_from TEXT, tx_from TEXT, tx_to TEXT);
"""
)
F = "INSERT INTO fact VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
A = "INSERT INTO approval VALUES (?,?,?,?,?)"

# ---- Example 2 (test result) ------------------------------------------------------------------
# 11/11 lab: pathology pending (system fact, approved at once)
db.execute(F, ("f1", "P", "병리검사", "pending", "lab_system", "11-11", "11-11", INF, "11-11", "11-11", INF, "11-11", INF))
db.execute(A, ("f1", "accepted", "11-11", "11-11", INF))
# 11/15 clinician says the result is back; result release date unknown -> indeterminate vt start in [11-11, 11-15]
db.execute(F, ("f2", "P", "병리검사", "resulted", "clinician_statement(extracted)", "11-11", "11-15", INF, "11-15", "11-15", INF, "11-15", INF))
# 11/16 clinician confirms the extraction
db.execute(A, ("f2", "accepted", "11-16", "11-16", INF))
# AT revision: on 11-18 we learn (audit) the clinician had actually been told on 11-14.  Old row closed in TT, new row added.
db.execute("UPDATE fact SET tx_to='11-18' WHERE id='f2'")
db.execute(F, ("f2", "P", "병리검사", "resulted", "clinician_statement(extracted)", "11-11", "11-15", INF, "11-14", "11-14", INF, "11-18", INF))


def as_was(t_at, t_tx="11-30",  # "now" = current DB state
           reviewed_only=True, approval_axis="at"):
    """Decision reconstruction: what the information system knew at availability time t_at, as recorded in DB state t_tx.
    approval_axis='at'  : approval must itself be available by t_at (correct)
    approval_axis='now' : use today's approval state regardless of when it happened (the leak)"""
    appr_cond = {
        "at": "EXISTS(SELECT 1 FROM approval a WHERE a.fact_id=f.id AND a.state IN ('accepted','edited') "
              "AND a.at_from<=:t AND a.tx_from<=:tx AND :tx<a.tx_to)",
        "now": "EXISTS(SELECT 1 FROM approval a WHERE a.fact_id=f.id AND a.state IN ('accepted','edited') AND a.tx_to=:inf)",
    }[approval_axis]
    q = f"""SELECT attr, value, at_from FROM fact f
            WHERE at_from<=:t AND :t<at_to AND tx_from<=:tx AND :tx<tx_to {('AND ' + appr_cond) if reviewed_only else ''}
            ORDER BY at_from"""
    out = {}
    for attr, value, _ in db.execute(q, {"t": t_at, "tx": t_tx, "inf": INF}):
        out[attr] = value  # latest available wins
    return out


def retrospective(t_valid):
    """Retrospective re-interpretation: using everything known NOW, what was the state at valid time t_valid?
    With indeterminate start, answer in possible/definite form (Dyreson & Snodgrass 1998 style)."""
    res = {}
    for attr, value, lo, hi in db.execute(
        "SELECT attr,value,vt_from_lo,vt_from_hi FROM fact WHERE tx_to=:inf AND at_to=:inf ORDER BY at_from", {"inf": INF}
    ):
        if hi <= t_valid:
            res[attr] = f"definitely {value}"
        elif lo <= t_valid:
            res[attr] = f"possibly {value} (else earlier state)"
    return res


print("== Example 2 ==")
for t in ["11-12", "11-14", "11-15", "11-16"]:
    print(f"as-was AT={t}  reviewed(approval@AT) :", as_was(t),
          "| reviewed(approval@now) :", as_was(t, approval_axis="now"),
          "| unreviewed allowed :", as_was(t, reviewed_only=False))
print("as-was AT=11-14 seen from DB state TT=11-17 (before AT revision):", as_was("11-14", "11-17", reviewed_only=False))
print("as-was AT=11-14 seen from DB state TT=11-19 (after AT revision) :", as_was("11-14", "11-19", reviewed_only=False))
print("retrospective valid-time 11-12 (current knowledge):", retrospective("11-12"))

# ---- Example 1 (symptom state + relative-time anchoring) ---------------------------------------
print("\n== Example 1 ==")
# spoken 11-10 ('사흘 전부터 숨이 찼고 지금은 좀 나아졌지만 완전히 괜찮지는 않아요'), entered into DB on 11-12
spoken, entered = "11-10", "11-12"


def minus_days(mmdd, d):
    m, dd = map(int, mmdd.split("-"))
    return f"{m:02d}-{dd - d:02d}"


for anchor_name, anchor in [("utterance time (correct)", spoken), ("transaction time (wrong anchor)", entered)]:
    print(f"onset from '사흘 전' anchored to {anchor_name}: {minus_days(anchor, 3)}")
db.execute(F, ("s1", "P", "호흡곤란", "present(improving, not resolved)", "patient_utterance",
               minus_days(spoken, 3), minus_days(spoken, 3), INF, spoken, spoken, INF, entered, INF))
db.execute(A, ("s1", "accepted", spoken, entered, INF))
summary_claim = ("호흡곤란", "absent")
state = as_was("11-10", reviewed_only=False)
print("as-was 11-10 state:", state.get("호흡곤란"), "| summary claims:", summary_claim[1],
      "| consistent:", state.get("호흡곤란", "").startswith(summary_claim[1]))
# Note: deciding that 'present(improving, not resolved)' contradicts 'absent' is a value-vocabulary rule, not a time-DB operation.
