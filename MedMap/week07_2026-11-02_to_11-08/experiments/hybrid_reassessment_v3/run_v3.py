"""v3 End-to-End 실행: CASE 1~10(새로 작성한 합성 기록), 그래프 ablation, 노출 문장에서 P2·v3 개념 연결 비교.
결과 outputs/v3_e2e.json, outputs/v3_ablation.json, outputs/v3_linking_compare.json. 임상 정확도 아님."""
import json
import sys
from collections import Counter
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from hybrid3 import concepts as CP, reasoner as R  # noqa: E402
from hybrid3.kg import EvidenceGraph  # noqa: E402
from hybrid3.reasoner import Case, Doc, Hypothesis  # noqa: E402
from hybrid.schema import DxStatus  # noqa: E402

PE = "DX:Pulmonary embolism"
SUSP = "Pulmonary embolism is suspected in the emergency department. Clinical probability was assessed as intermediate using the Wells score. The patient is hemodynamically stable."
SUSP_LOW = "Pulmonary embolism is suspected. Clinical probability was assessed as low (Wells). The patient is hemodynamically stable."
POS = "IMPRESSION: Acute pulmonary embolism in the right lower lobe segmental arteries."
NEG = "IMPRESSION: No evidence of pulmonary embolism."


def cur(eid="E1"):
    return Hypothesis("h1", "Pulmonary embolism", PE, 0.0, episode_id=eid)


def build(engine):
    C = {}

    def case(name, hyps, docs, as_of, tests=()):
        c = Case(name, engine)
        for h in hyps:
            c.add_hypothesis(h)
        for d in docs:
            c.add_document(d)
        for t in tests:
            c.add_test_event(*t)
        C[name] = (c, as_of)
    case("CASE01_suspected_positive_ctpa", [cur()], [Doc("n1", SUSP, "NOTE", 0.5, 1.0), Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0)], [5.0])
    case("CASE02a_suspected_negative_ctpa", [cur()], [Doc("n1", SUSP, "NOTE", 0.5, 1.0), Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0)], [5.0])
    case("CASE02b_low_probability_ddimer_conditions_stated", [cur()], [Doc("n1", SUSP_LOW, "NOTE", 0.5, 1.0), Doc("l1", "D-dimer measured by ELISA was normal, below the age-adjusted cut-off.", "LAB", 1.5, 2.0)], [3.0])
    case("CASE02c_ddimer_conditions_missing", [cur()], [Doc("n1", SUSP_LOW, "NOTE", 0.5, 1.0), Doc("l1", "D-dimer was normal.", "LAB", 1.5, 2.0)], [3.0])
    case("CASE03_past_pe_followup", [Hypothesis("h0", "Pulmonary embolism", PE, 1.0, DxStatus.CONFIRMED_DIAGNOSIS, "E0", "PAST_EPISODE", 1.0)],
         [Doc("n0", "Pulmonary embolism was diagnosed one month ago and she is currently receiving apixaban.", "NOTE", 30.0, 30.0),
          Doc("r9", "Follow-up CTPA after three months of anticoagulation showed no pulmonary embolism.", "CTPA_REPORT", 90.0, 91.0),
          Doc("p9", "Perfusion scan was normal at follow-up after treatment for pulmonary embolism.", "NOTE", 92.0, 93.0)], [95.0])
    case("CASE04_order_only", [cur()], [Doc("n1", SUSP, "NOTE", 0.5, 1.0), Doc("o1", "CTPA was ordered to rule out pulmonary embolism.", "NOTE", 1.0, 1.0)], [1.5], [("ctpa", "ORDER", 1.0)])
    case("CASE05_late_result_and_correction", [cur()], [Doc("n1", SUSP, "NOTE", 0.5, 1.0), Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), Doc("r2", NEG, "CTPA_REPORT", 2.0, 7.0, supersedes="r1")],
         [3.0, 4.0, 6.9, 7.0], [("ctpa", "ORDER", 1.0), ("ctpa", "COLLECT", 2.0), ("ctpa", "RESULT", 4.0), ("ctpa", "CORRECT", 7.0)])
    case("CASE06_mixed_polarity", [cur()], [Doc("n1", SUSP, "NOTE", 0.5, 1.0), Doc("r1", "No deep vein thrombosis was seen on ultrasound, but CTPA showed segmental pulmonary embolism.", "NOTE", 2.0, 4.0)], [5.0])
    case("CASE07_synonyms_and_subtype", [cur()], [Doc("n1", SUSP, "NOTE", 0.5, 1.0),
         Doc("r1", "Computed tomographic pulmonary angiogram revealed subsegmental pulmonary embolism (SSPE). The SSPE was isolated.", "CTPA_REPORT", 2.0, 4.0)], [5.0])
    case("CASE08_unsupported", [cur(), Hypothesis("h2", "Aortic dissection", "DX:Aortic dissection", 0.0, episode_id="E9")],
         [Doc("n1", SUSP, "NOTE", 0.5, 1.0), Doc("e1", "Echocardiography showed a pericardial effusion and the aorta was dilated.", "NOTE", 2.0, 3.0)], [4.0])
    case("CASE09_context_in_record", [cur()], [Doc("n1", "Chest pain. Concern for PE; low clinical probability by Geneva. Hemodynamically stable.", "NOTE", 0.5, 1.0),
         Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0)], [5.0])
    case("CASE10_no_context_in_record", [cur()], [Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), Doc("l1", "D-dimer was normal.", "LAB", 1.5, 2.0)], [5.0])
    case("CASE11_recurrence_separate", [Hypothesis("h0", "Pulmonary embolism", PE, 1.0, DxStatus.CONFIRMED_DIAGNOSIS, "E0", "PAST_EPISODE", 1.0),
                                        Hypothesis("h3", "Pulmonary embolism", PE, 200.0, episode_id="E2", kind="RECURRENCE", target_time=200.0)],
         [Doc("n0", "Pulmonary embolism was diagnosed in 2024 and anticoagulation was completed.", "NOTE", 5.0, 5.0),
          Doc("n2", "New dyspnea; recurrent pulmonary embolism is suspected.", "NOTE", 200.0, 200.0), Doc("r2", NEG, "CTPA_REPORT", 201.0, 202.0)], [203.0])
    case("CASE12_haemodynamic_instability", [cur()], [Doc("n1", "Pulmonary embolism is suspected; high clinical probability. The patient is in obstructive shock.", "NOTE", 0.5, 1.0),
         Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0)], [5.0])
    return C


KEEP = ("document", "surface", "concept", "subtype", "assertion", "finding", "direction", "relation_id", "abstain_reason", "missing_context", "conditions_used", "graph_path", "gaps")


def run_cases(engine):
    out = {}
    for name, (c, ts) in build(engine).items():
        out[name] = []
        for t in ts:
            s = c.state(t)
            out[name].append({"as_of": t, "visible_documents": s["visible_documents"], "tests": s["tests"], "context": s["context"], "hypotheses": s["hypotheses"],
                              "results": [{k: r[k] for k in KEEP} | {"hypothesis_episode": r["episode_id"], "explanation": R.explain(r)} for r in s["results"]
                                          if r["link_status"] == "LINKED" or r["gaps"]]})
    return out


def directions(res):
    return {f"{n}@{st['as_of']}|{r['hypothesis_episode']}|{r['document']}|{r['surface']}": r["direction"] for n, sts in res.items() for st in sts for r in st["results"]}


full = run_cases(R.Engine(EvidenceGraph()))
(H / "outputs/v3_e2e.json").write_text(json.dumps(full, ensure_ascii=False, indent=1), encoding="utf-8")
base = directions(full)
ab = {"full_graph": {"stats": EvidenceGraph().stats()}}
rel_ids = [r["id"] for r in EvidenceGraph().catalog["relations"]]
for label, g in (("no_verified_relations", EvidenceGraph(disabled_relations=rel_ids)), ("without_PE-CTPA-POSITIVE", EvidenceGraph(disabled_relations=["PE-CTPA-POSITIVE"])),
                 ("without_PE-CTPA-NEGATIVE", EvidenceGraph(disabled_relations=["PE-CTPA-NEGATIVE"])), ("without_base_graph", EvidenceGraph(use_base=False))):
    d = directions(run_cases(R.Engine(g)))
    ch = {k: (base[k], d.get(k)) for k in base if base[k] != d.get(k)}
    ab[label] = {"stats": g.stats(), "changed": ch, "n_changed": len(ch), "directional_before": sum(v in R.DIRECTIONAL for v in base.values()),
                 "directional_after": sum(v in R.DIRECTIONAL for v in d.values())}
(H / "outputs/v3_ablation.json").write_text(json.dumps(ab, ensure_ascii=False, indent=1), encoding="utf-8")

# P2 기본 경로(맥락 입력 없음)와 같은 문서를 비교: 맥락 추출의 효과
p2 = {}
for name, (c, ts) in build(R.Engine()).items():
    for d in c.docs.values():
        for h in c.hyps:
            for rec in CP.P2.extract(d.text, d.doc_type):
                o = CP.P2.assess_record(rec, h.assertion("c"), {})
                p2[f"{name}|{h.episode_id}|{d.doc_id}|{rec['surface']}"] = o["direction"]

# 노출 문장 개념 연결 비교(회귀·개발 자료, 독립 평가 아님)
V2 = H.parent / "hybrid_reassessment_v2"
PILOT = {"PE_DIAGNOSIS", "DDIMER", "DVT", "CTPA_STUDY", "PERFUSION_SCAN", "FILLING_DEFECT"}
cmp_ = {}
eng = R.Engine()
for setn, (sf, gf) in {"run1_exposed": ("eval/public_sentences_run1.jsonl", "eval/gold_public_run1.json"), "run2_exposed": ("eval/public_sentences.jsonl", "eval/gold_public.json")}.items():
    S = [json.loads(x) for x in (V2 / sf).read_text(encoding="utf-8").splitlines()]
    gold = json.loads((V2 / gf).read_text(encoding="utf-8"))["items"]
    res = {}
    for ver in ("P2", "V3"):
        m = Counter()
        dirs, gaps, ex = Counter(), Counter(), []
        for r in S:
            g = gold.get(str(r["id"]), {}).get("concepts", {})
            recs = CP.P2.extract(r["sentence"], "") if ver == "P2" else [x for x in CP.extract(r["sentence"], "") if x["role"] == "MENTION"]
            got = {}
            for x in recs:
                if x["link_status"] == "LINKED" and x["concept"] in PILOT:
                    got.setdefault(x["concept"], []).append(x["assertion"])
            for c, a in g.items():
                m["gold"] += 1
                if c in got:
                    m["found"] += 1
                    m["agree"] += a in got[c]
                elif ver == "V3":
                    ex.append({"id": r["id"], "missed": c})
            m["unsupported"] += sum(c not in g for c in got)
            m["ambiguous"] += sum(x["link_status"] == "AMBIGUOUS" for x in recs)
            if ver == "V3":
                case = Case(f"s{r['id']}", eng)
                case.add_hypothesis(cur())
                case.add_document(Doc("s", r["sentence"], "NOTE", 0.0, 0.0))
                for o in case.state(0.0)["results"]:
                    dirs[o["direction"]] += 1
                    for gp in o["gaps"]:
                        gaps[gp["class"]] += 1
        res[ver] = dict(m) | ({"directions": dict(dirs), "gap_classes": dict(gaps), "v3_missed": ex} if ver == "V3" else {})
    cmp_[setn] = {"n_sentences": len(S), **res}
(H / "outputs/v3_linking_compare.json").write_text(json.dumps({"label": "EXPOSED_DEVELOPMENT_SENTENCES_NOT_INDEPENDENT", "p2_default_directions_on_cases": dict(Counter(p2.values())), **cmp_}, ensure_ascii=False, indent=1), encoding="utf-8")

for n, sts in full.items():
    for st in sts:
        print(f"== {n} @ {st['as_of']} hyps={st['hypotheses']}")
        for r in st["results"]:
            if r["concept"] in PILOT or r["direction"] != "ABSTAIN":
                print(f"   {r['hypothesis_episode']} {r['document']} '{r['surface']}' {r['assertion']} → {r['direction']} {r['relation_id']} {r['abstain_reason']} miss={r['missing_context']} gaps={[g['item'] + ':' + g['class'] for g in r['gaps']]}")
print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "stats"} for k, v in ab.items() if k != "full_graph"}, ensure_ascii=False, indent=0)[:3000])
print(json.dumps(cmp_, ensure_ascii=False)[:1500])
print("P2 default on same case docs", dict(Counter(p2.values())))
