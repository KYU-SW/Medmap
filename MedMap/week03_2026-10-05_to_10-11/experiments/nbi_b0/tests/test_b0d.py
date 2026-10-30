"""NBI-B0d 합성 fixture 시험 — 실제 MIMIC 미사용(가짜 ID·가짜 시각·가짜 보고서 문장). B0a 시험의 Gen 재사용.

exam_name 은 사전 고정 목록(b0d/exam_map.json 의 accepted)과 방해 이름만 쓴다(정찰 어휘의 이름 문자열, 건수·환자 정보 없음).
실행: python3 -m unittest docs/research/nbi/b0/tests/test_b0d.py
"""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import b0a_availability as A  # noqa: E402
import b0d_availability as D  # noqa: E402
from test_b0a import Gen, gz, sha  # noqa: E402

SCHEMA = os.path.join(HERE, "..", "expected_schema_b0d.json")
EXAM_MAP = os.path.join(HERE, "..", "b0d", "exam_map.json")
RAD_H = ["note_id", "subject_id", "hadm_id", "note_type", "note_seq", "charttime", "storetime", "text"]
DET_H = ["note_id", "subject_id", "field_name", "field_value", "field_ordinal"]
CTA, CT = "CTA CHEST W&W/O C&RECONS, NON-CORONARY", "CT CHEST W/CONTRAST"
DISTRACT = ["CTA CORONARY ARTERIES W/3D W/FUNCTION", "CHEST (PA & LAT)", "CHEST (PORTABLE AP)",
            "CT ABD & PELVIS WITH CONTRAST", "CT LOW DOSE LUNG SCREENING", "F/U DIAGNOSTIC CT CHEST W/O CONTRAST LCS",
            "CT LUNG/MEDIASTINAL BX", "MRA CHEST W&W/O CONTRAST", "CTA HEAD W&W/O C & RECONS", "CT TRACHEA W/O CONTRAST"]
CTX = "2150-01-01 10:40:00"
STX = "2150-01-01 11:30:00"
SECRET = "INDICATION: r/o PE. IMPRESSION: Acute pulmonary embolism. 999 secret"
CT_ = "IMAGING_CTA_CHEST"


def classes(gen):
    m = {}
    for subj, sid, seq, code, ver, _ in gen.dx:
        if seq == 1:
            m[sid] = (subj, next(c for c in A.CODES if c in A.classify(ver, A.norm_code(code))))
    return m


def admit(gen, cls, n):
    cl = classes(gen)
    sids = [s for s, (_, c) in sorted(cl.items()) if c == cls][:n]
    gen.ed = [(r[0], "8" + str(r[2]) if r[2] in sids else r[1]) + tuple(r[2:]) for r in gen.ed]
    return gen


class Rad:
    def __init__(self, gen, vocab=None):
        self.gen, self.rad, self.det, self.k = gen, [], [], 0
        self.cls = classes(gen)
        names = vocab if vocab is not None else sorted(D.EXAMS["IMAGING_CTA_CHEST"] | D.EXAMS["IMAGING_CHEST_CT"])
        for n in names + DISTRACT:  # 코호트 밖 subject 의 어휘 행(모든 고정 이름이 detail 에 존재)
            self.note(99999999, [n], CTX, STX)

    def note(self, subj, exams, ct, st, note_type="RR", text=SECRET):
        self.k += 1
        nid = f"{subj}-{note_type}-{self.k}"
        self.rad.append((nid, subj, "77777777", note_type, self.k, ct, st, text))
        for j, e in enumerate(exams):
            self.det.append((nid, subj, "exam_name", e, j + 1))
            self.det.append((nid, subj, "cpt_code", "71275", j + 1))
            self.det.append((nid, subj, "exam_code", "XCODE", j + 1))
        return nid

    def add(self, cls, n, exams=(CTA,), ct=CTX, st=STX, start=0, note_type="RR", text=SECRET):
        sids = [s for s, (_, c) in sorted(self.cls.items()) if c == cls][start:start + n]
        for s in sids:
            self.note(self.cls[s][0], list(exams), ct, st, note_type, text)
        return self

    def write(self, d):
        ed, ecg = self.gen.write(d)
        rp, dp = os.path.join(d, "rad.csv.gz"), os.path.join(d, "det.csv.gz")
        open(rp, "wb").write(gz(RAD_H, self.rad))
        open(dp, "wb").write(gz(DET_H, self.det))
        ref = os.path.join(d, "ref_public.json")
        dd = A.compute(ed, ecg)
        json.dump(A.build(dd)[0] if dd["verdict"] == "OK" else {"pairs": {}}, open(ref, "w"))
        return ed, ecg, rp, dp, ref


def built(rad):
    with tempfile.TemporaryDirectory() as d:
        ed, ecg, rp, dp, _ = rad.write(d)
        exams, note_c = D.exam_scan(dp)
        assert exams == D.EXAMS, exams
        return D.build_b0d(D.compute_b0d(ed, ecg, rp, note_c))


def lab(pub, t, p="ACS~PE", g="labels"):
    return pub["pairs"][p][g][t]


def margs(d, ed, ecg, rp, dp, ref, schema=SCHEMA, ref_c=None):
    a = ["--ed-zip", ed, "--ecg-zip", ecg, "--radiology", rp, "--radiology-detail", dp, "--schema", schema,
         "--b0a-public", ref, "--b0c-public", ref_c or ref]
    out = []
    for i in range(0, len(a), 2):
        out += [a[i], a[i + 1], a[i] + "-sha", sha(a[i + 1])]
    return out + ["--out", os.path.join(d, "out"), "--sealed", os.path.join(d, "sealed"),
                  "--private-log", os.path.join(d, "priv", "p.log")]


def run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = D.main(argv)
    return rc, buf.getvalue()


class TestExamMap(unittest.TestCase):
    def test_rule_reproduces_frozen_and_rejects_distractors(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, _, dp, _ = Rad(Gen()).write(d)
            self.assertEqual(D.exam_scan(dp)[0], D.EXAMS)
        for n in DISTRACT:
            self.assertEqual(D.concept_of(n), [], n)
        self.assertEqual(D.concept_of("CTA CHEST"), ["IMAGING_CTA_CHEST"])
        self.assertEqual(D.concept_of("CT CHEST W/O CONTRAST"), ["IMAGING_CHEST_CT"])

    def test_missing_or_new_name_breaks_map(self):
        names = sorted(D.EXAMS["IMAGING_CTA_CHEST"] | D.EXAMS["IMAGING_CHEST_CT"])
        for vocab in (names[1:], names + ["CT CHEST NEW SYNTHETIC PROTOCOL"]):
            with tempfile.TemporaryDirectory() as d:
                _, _, _, dp, _ = Rad(Gen(), vocab=vocab).write(d)
                self.assertNotEqual(D.exam_scan(dp)[0], D.EXAMS)

    def test_exam_map_file_matches_code(self):
        m = json.load(open(EXAM_MAP, encoding="utf-8"))
        self.assertEqual({c: frozenset(v) for c, v in m["accepted"].items()}, D.EXAMS)
        self.assertEqual(m["rules"], {c: rx.pattern for c, rx in D.RULES.items()})

    def test_concepts_disjoint(self):
        self.assertFalse(D.EXAMS["IMAGING_CTA_CHEST"] & D.EXAMS["IMAGING_CHEST_CT"])

    def test_no_text_or_forbidden_columns_read(self):
        self.assertEqual(D.RAD_ALLOW, ["note_id", "subject_id", "note_type", "charttime", "storetime"])
        self.assertEqual(D.DET_ALLOW, ["note_id", "field_name", "field_value"])
        src = open(os.path.join(HERE, "..", "b0d_availability.py"), encoding="utf-8").read()
        self.assertNotRegex(src, r"\[\"text\"\]|\[\"hadm_id\"\]|\"cpt_code\"|\"exam_code\"|field_ordinal\"\]")

    def test_report_text_does_not_change_output(self):
        a = built(Rad(Gen()).add("ACS", 35).add("PE", 35))
        b = built(Rad(Gen()).add("ACS", 35, text="normal").add("PE", 35, text="no embolism"))
        self.assertEqual(a, b)


class TestLayers(unittest.TestCase):
    def test_study_and_report_in_stay_available(self):
        pub, s = built(Rad(Gen()).add("ACS", 35).add("PE", 35))
        for l in D.LAYERS:
            self.assertEqual(lab(pub, f"{CT_}_{l}"), "RECORDED_IN_STAY_AVAILABLE")
            self.assertEqual(lab(pub, f"IMAGING_CHEST_CT_{l}"), "NOT_AVAILABLE_IN_DATA")
        self.assertEqual(s["pairs"]["ACS~PE"]["avail"][f"{CT_}_STUDY"]["a"], 35)

    def test_study_in_stay_report_after_ed(self):
        pub, s = built(Rad(Gen()).add("ACS", 35, st="2150-01-01 16:30:00").add("PE", 35, st="2150-01-01 16:30:00"))
        self.assertEqual(lab(pub, f"{CT_}_STUDY"), "RECORDED_IN_STAY_AVAILABLE")
        self.assertEqual(lab(pub, f"{CT_}_REPORT"), "NOT_AVAILABLE_IN_DATA")
        self.assertEqual(s["pairs"]["ACS~PE"]["avail"][f"{CT_}_REPORT"]["report_after_ed_stays"], 70)

    def test_report_time_missing_uncertain(self):
        pub, s = built(Rad(Gen()).add("ACS", 35, st="").add("PE", 35, st=""))
        self.assertEqual(lab(pub, f"{CT_}_STUDY"), "RECORDED_IN_STAY_AVAILABLE")
        self.assertEqual(lab(pub, f"{CT_}_REPORT"), "TEMPORALLY_UNCERTAIN")
        self.assertEqual(lab(pub, f"{CT_}_REPORT", g="timing"), "TEMPORALLY_UNCERTAIN")
        self.assertEqual(s["pairs"]["ACS~PE"]["avail"][f"{CT_}_REPORT"]["stays_all_time_missing"], 70)

    def test_study_time_missing_uncertain_report_counts(self):
        pub, _ = built(Rad(Gen()).add("ACS", 35, ct="").add("PE", 35, ct=""))
        self.assertEqual(lab(pub, f"{CT_}_STUDY"), "TEMPORALLY_UNCERTAIN")
        self.assertEqual(lab(pub, f"{CT_}_REPORT"), "RECORDED_IN_STAY_AVAILABLE")

    def test_uncertain_stay_unit_and_min(self):
        r = Rad(Gen()).add("ACS", 35).add("PE", 35)
        for _ in range(70):  # 한 stay 에 판독 시각 결측 사건 70건 → stay 단위면 1 stay
            r.add("ACS", 1, st="", start=36)
        pub, s = built(r)
        self.assertEqual(lab(pub, f"{CT_}_REPORT"), "RECORDED_IN_STAY_AVAILABLE")
        self.assertEqual(s["pairs"]["ACS~PE"]["avail"][f"{CT_}_REPORT"]["stays_all_time_missing"], 1)
        pub, _ = built(Rad(Gen()).add("ACS", 29, st="").add("PE", 1))  # 29/30 결측이지만 < Q_MIN
        self.assertEqual(lab(pub, f"{CT_}_REPORT"), "RECORDED_IN_STAY_PARTIAL")

    def test_uncertain_boundary_exactly_half(self):
        pub, s = built(Rad(Gen(n_acs=60, n_pe=40, n_peri=0)).add("ACS", 30, st="").add("ACS", 30, start=30))
        a = s["pairs"]["ACS~PE"]["avail"][f"{CT_}_REPORT"]
        self.assertEqual((a["stays_all_time_missing"], a["stays_seen_in_stay"]), (30, 60))
        self.assertEqual(lab(pub, f"{CT_}_REPORT"), "TEMPORALLY_UNCERTAIN")
        pub, _ = built(Rad(Gen(n_acs=60, n_pe=60, n_peri=0)).add("ACS", 30, st="").add("ACS", 30, start=30)
                       .add("PE", 30))  # 30/90
        self.assertNotEqual(lab(pub, f"{CT_}_REPORT"), "TEMPORALLY_UNCERTAIN")

    def test_study_before_arrival(self):
        pub, s = built(Rad(Gen()).add("ACS", 35, ct="2150-01-01 09:30:00", st="2150-01-01 10:30:00")
                       .add("PE", 35, ct="2150-01-01 09:30:00", st="2150-01-01 10:30:00"))
        self.assertEqual(lab(pub, f"{CT_}_STUDY"), "NOT_AVAILABLE_IN_DATA")
        self.assertEqual(lab(pub, f"{CT_}_REPORT"), "NOT_AVAILABLE_IN_DATA")
        a = s["pairs"]["ACS~PE"]["avail"]
        self.assertEqual((a[f"{CT_}_REPORT"]["pre_t0_study_stays"], a[f"{CT_}_STUDY"]["pre_t0_24h_stays"]), (70, 70))

    def test_study_after_ed(self):
        pub, s = built(Rad(Gen()).add("ACS", 35, ct="2150-01-01 17:00:00", st="2150-01-01 18:00:00")
                       .add("PE", 35, ct="2150-01-01 17:00:00", st="2150-01-01 18:00:00"))
        self.assertEqual(lab(pub, f"{CT_}_STUDY"), "NOT_AVAILABLE_IN_DATA")
        self.assertEqual(lab(pub, f"{CT_}_REPORT"), "NOT_AVAILABLE_IN_DATA")
        self.assertEqual(s["pairs"]["ACS~PE"]["avail"][f"{CT_}_STUDY"]["post_ed_24h_stays"], 70)

    def test_outtime_inclusive(self):
        pub, _ = built(Rad(Gen()).add("ACS", 35, ct="2150-01-01 15:00:00", st="2150-01-01 16:00:00")
                       .add("PE", 35, ct="2150-01-01 15:00:00", st="2150-01-01 16:00:00"))
        self.assertEqual(lab(pub, f"{CT_}_REPORT"), "RECORDED_IN_STAY_AVAILABLE")

    def test_report_later_than_study_timing_and_lag(self):
        pub, s = built(Rad(Gen()).add("ACS", 35, ct="2150-01-01 10:30:00", st="2150-01-01 12:30:00")
                       .add("PE", 35, ct="2150-01-01 10:30:00", st="2150-01-01 12:30:00"))
        self.assertEqual(lab(pub, f"{CT_}_STUDY", g="timing"), "EARLY_ROUTINE_POSSIBLE")
        self.assertEqual(lab(pub, f"{CT_}_REPORT", g="timing"), "LATER_IN_STAY")
        self.assertEqual(s["pairs"]["ACS~PE"]["avail"][f"{CT_}_REPORT"]["report_lag_h_event_quantiles"]["p50"], 2.0)

    def test_insufficient_n_timing(self):
        pub, _ = built(Rad(Gen()).add("ACS", 10).add("PE", 10))
        self.assertEqual(lab(pub, f"{CT_}_STUDY", g="timing"), "INSUFFICIENT_N")
        self.assertEqual(lab(pub, f"{CT_}_STUDY"), "RECORDED_IN_STAY_PARTIAL")

    def test_duplicate_events_counted_once_earliest(self):
        r = Rad(Gen()).add("ACS", 35, ct="2150-01-01 13:00:00", st="2150-01-01 14:00:00").add("PE", 35)
        r.add("ACS", 35, ct="2150-01-01 10:20:00", st="2150-01-01 10:50:00")
        pub, s = built(r)
        a = s["pairs"]["ACS~PE"]["avail"][f"{CT_}_STUDY"]
        self.assertEqual(a["a"], 35)
        self.assertEqual(a["windows"]["W1"]["a"], 35)  # 가장 이른 사건(10:20)이 첫 시각

    def test_addendum_ignored_and_multi_exam_note(self):
        r = Rad(Gen()).add("ACS", 35, note_type="AR").add("PE", 35, note_type="AR")
        pub, s = built(r)
        self.assertEqual(lab(pub, f"{CT_}_STUDY"), "NOT_AVAILABLE_IN_DATA")
        self.assertGreaterEqual(s["ar_notes_skipped"], 70)
        pub, _ = built(Rad(Gen()).add("ACS", 35, exams=(CTA, CT)).add("PE", 35, exams=(CTA, CT)))
        for c in D.CONCEPTS:
            self.assertEqual(lab(pub, f"{c}_STUDY"), "RECORDED_IN_STAY_AVAILABLE")

    def test_distractor_exam_not_counted(self):
        pub, _ = built(Rad(Gen()).add("ACS", 35, exams=("CTA CORONARY ARTERIES W/3D W/FUNCTION",))
                       .add("PE", 35, exams=("CHEST (PA & LAT)",)))
        self.assertTrue(all(v == "NOT_AVAILABLE_IN_DATA" for v in pub["pairs"]["ACS~PE"]["labels"].values()))

    def test_overlapping_later_stay_takes_event(self):
        gen = Gen(n_acs=35, n_pe=35, n_peri=0)
        for sid, (subj, c) in list(classes(gen).items()):
            gen.sid += 1
            gen.ed.append((subj, "", gen.sid, "2150-01-01 12:00:00", "2150-01-01 13:00:00", "F", "X", "WALK IN", "HOME"))
        late = built(Rad(gen).add("ACS", 35, ct="2150-01-01 12:10:00", st="2150-01-01 12:30:00")
                     .add("PE", 35, ct="2150-01-01 12:10:00", st="2150-01-01 12:30:00"))[0]
        self.assertEqual(lab(late, f"{CT_}_STUDY"), "NOT_AVAILABLE_IN_DATA")

    def test_not_evaluable_pair(self):
        pub, _ = built(Rad(Gen(n_pe=0)).add("ACS", 35))
        self.assertEqual(pub["pairs"]["ACS~PE"]["pair_status"], "NOT_EVALUABLE")
        self.assertTrue(all(v == "NOT_EVALUABLE" for v in pub["pairs"]["ACS~PE"]["labels"].values()))


class TestPublicMinimal(unittest.TestCase):
    def test_schema_and_vocab(self):
        pub, _ = built(Rad(Gen()).add("ACS", 35).add("PE", 35))
        keys = json.load(open(SCHEMA, encoding="utf-8"))["keys"]
        self.assertEqual(sorted(k for k, _ in A.flatten(pub)), sorted(keys))
        self.assertEqual(len(keys), 28)
        self.assertEqual(D.guard(pub), [])
        for k, v in A.flatten(pub):
            self.assertIsInstance(v, str, k)
            self.assertIsNone(re.fullmatch(r"[\d.]+", v), k)

    def test_small_pool_withheld(self):
        pub, _ = built(Rad(Gen()).add("ACS", 35).add("PE", 35))  # n_pool 80
        self.assertEqual(lab(pub, f"{CT_}_STUDY", g="pooled_share_bin"), "WITHHELD")
        pub, _ = built(Rad(Gen(n_acs=150, n_pe=150, n_peri=0)).add("ACS", 150).add("PE", 150))
        self.assertEqual(lab(pub, f"{CT_}_STUDY", g="pooled_share_bin"), "90_100")

    def test_attack_small_cell_invisible(self):
        outs = set()
        for k in range(1, 11):
            pub, _ = built(Rad(Gen(n_acs=150, n_pe=150, n_peri=0)).add("ACS", 150).add("PE", k))
            outs.add(json.dumps(pub, sort_keys=True))
        self.assertEqual(len(outs), 1)

    def test_strata_and_lag_sealed_only(self):
        gen = admit(Gen(n_acs=150, n_pe=150, n_peri=0), "ACS", 150)
        pub, s = built(Rad(gen).add("ACS", 150).add("PE", 40))
        flat = " ".join(k for k, _ in A.flatten(pub))
        for w in ("admitted", "lag", "window", "W1", "pre_t0", "after_ed"):
            self.assertNotIn(w, flat)
        self.assertEqual(s["pairs"]["ACS~PE"]["avail"][f"{CT_}_STUDY"]["stratum_admitted_recorded"], 150)

    def test_deterministic(self):
        r = Rad(Gen()).add("ACS", 35).add("PE", 35, st="")
        self.assertEqual(built(r), built(r))


class TestMain(unittest.TestCase):
    def test_complete_and_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            ed, ecg, rp, dp, ref = Rad(Gen()).add("ACS", 35).add("PE", 35).write(d)
            rc, out = run(margs(d, ed, ecg, rp, dp, ref))
            self.assertEqual((rc, out), (0, "B0D_VERDICT COMPLETE\n"))
            pub = json.load(open(os.path.join(d, "out", "b0d_public.json")))
            self.assertEqual(pub["meta"]["sealed_file_sha256"], sha(os.path.join(d, "sealed", "b0d_sealed.json")))
            self.assertTrue(os.path.exists(os.path.join(d, "out", "B0D_SHA256SUMS")))
            self.assertEqual(oct(os.stat(os.path.join(d, "sealed")).st_mode & 0o777), "0o700")
            raw = open(os.path.join(d, "out", "b0d_public.json")).read()
            for leak in ("secret", "embolism", "99999999", "2150-", "7777"):
                self.assertNotIn(leak, raw)
            self.assertNotRegex(out.replace("B0D", ""), r"\d")

    def test_aborts(self):
        for reason in ("sha_mismatch", "exam_map_mismatch", "cohort_mismatch", "cohort_mismatch_b0c",
                       "schema_mismatch"):
            with tempfile.TemporaryDirectory() as d:
                r = Rad(Gen(), vocab=["CTA CHEST"] if reason == "exam_map_mismatch" else None)
                ed, ecg, rp, dp, ref = r.add("ACS", 35).add("PE", 35).write(d)
                ref_c, schema = None, SCHEMA
                if reason.startswith("cohort_mismatch"):
                    x = json.load(open(ref))
                    x["pairs"]["ACS~PE"]["cohort_pooled_bucket"] = "GE_5000"
                    bad = os.path.join(d, "bad.json")
                    json.dump(x, open(bad, "w"))
                    if reason == "cohort_mismatch":
                        ref = bad
                    else:
                        ref_c = bad
                if reason == "schema_mismatch":
                    schema = os.path.join(d, "schema.json")
                    k = json.load(open(SCHEMA))
                    k["keys"] = k["keys"][:-1]
                    json.dump(k, open(schema, "w"))
                a = margs(d, ed, ecg, rp, dp, ref, schema=schema, ref_c=ref_c)
                if reason == "sha_mismatch":
                    a[a.index("--radiology-sha") + 1] = "0" * 64
                rc, out = run(a)
                self.assertEqual(rc, 2, reason)
                self.assertIn("reason=" + reason.replace("_b0c", ""), out)
                self.assertFalse(os.path.exists(os.path.join(d, "out")), reason)
                self.assertFalse(os.path.exists(os.path.join(d, "sealed")), reason)

    def test_guard_blocks_numeric_leaf(self):
        orig = D.build_b0d

        def leaky(d):
            pub, sealed = orig(d)
            pub["pairs"]["ACS~PE"]["pooled_share_bin"][f"{CT_}_STUDY"] = "37"
            return pub, sealed
        with tempfile.TemporaryDirectory() as d:
            ed, ecg, rp, dp, ref = Rad(Gen()).add("ACS", 35).add("PE", 35).write(d)
            D.build_b0d = leaky
            try:
                rc, out = run(margs(d, ed, ecg, rp, dp, ref))
            finally:
                D.build_b0d = orig
            self.assertEqual(rc, 2)
            self.assertIn("reason=output_guard", out)
            self.assertFalse(os.path.exists(os.path.join(d, "sealed")))

    def test_output_exists_one_run_guard(self):
        with tempfile.TemporaryDirectory() as d:
            ed, ecg, rp, dp, ref = Rad(Gen()).add("ACS", 35).add("PE", 35).write(d)
            self.assertEqual(run(margs(d, ed, ecg, rp, dp, ref))[0], 0)
            rc, out = run(margs(d, ed, ecg, rp, dp, ref))  # 같은 경로 두 번째 실행
            self.assertEqual(rc, 2)
            self.assertIn("output_exists", out)

    def test_stop_title_no_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            ed, ecg, rp, dp, ref = Rad(Gen(title_override="Something unrelated")).write(d)
            rc, _ = run(margs(d, ed, ecg, rp, dp, ref))
            self.assertEqual(rc, 3)
            self.assertFalse(os.path.exists(os.path.join(d, "sealed")))
            self.assertFalse(os.path.exists(os.path.join(d, "out")))


if __name__ == "__main__":
    unittest.main()
