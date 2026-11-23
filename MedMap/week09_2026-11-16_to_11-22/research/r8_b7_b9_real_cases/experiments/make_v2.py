"""[사후 정정 v2] 독립 검증(red-team/verifier) 지적 중 메인이 원문으로 재확인한 항목만 반영. v1(run2)은 보존.
사용: python -I -B make_v2.py  -> experiments/inputs/cases_input_v2.json, evaluation/REF_R_v2.json
정정 근거(메인 원문 확인):
 E1 SGLT2i 시작 eGFR 하한 20: VA CKD CPG L2923 'The lowest eGFR for initiation of SGLT2i was 20', VA DM 표 L4707 'eGFR <20–30 (see labeling)'.
 E2 NSAID 국소 포함 회피: VA CKD CPG p.126 L7375 'Avoid NSAID use, including OTC and prescription (oral/topical), if possible'.
 E3 SGLT2i 급성 사건 후 재개 서술: VA CKD CPG L2919 'reinitiation of SGLT2i treatment after an acute event has passed' -> EDKA 후 영구 금기는 VA 원문 근거 아님(사례 보고 저자 판단).
 E4 CASE_07: PMC10359101 Table 2 에 혈당강하제 없음, 'non-insulin dependent type 2 diabetes (hemoglobin A1c: 5.2%)'; 'blood pressure at goal with amlodipine and carvedilol' 문장 존재.
 E5 CASE_09 I2: 다른 SGLT2i 항목과 달리 sglt2_contra 누락(인코딩 불일치).
 E6 CASE_08 I4: AKI 회복 후 eGFR 원문 없음 -> P 변수.
 E7 CASE_13 I3: 저자 대안 3개, 환자 선호 없음 -> 선호 미확인.
 E8 CASE_04: 원문 선호 'Limit use of NSAIDs'(helpful) 누락 -> 추가(라벨 영향 없음).
"""
import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
v1 = json.load(open(os.path.join(ROOT, "experiments", "inputs", "cases_input_v1.json")))
ref1 = json.load(open(os.path.join(ROOT, "evaluation", "REF_R_v1.json")))
c = copy.deepcopy(v1)
r = copy.deepcopy(ref1)
C = c["cases"]
RC = r["cases"]
U = lambda cost, how, default: {"group": "P", "known": None, "domain": [True, False], "default": default, "cost": cost, "how": how}

# E1: SGLT2i 시작 항목에 egfr_ge20
sg = {"CASE_01": ("I1", True), "CASE_02": ("I4", None), "CASE_04": ("I4", None), "CASE_05": ("I3", True),
      "CASE_07": ("I2", True), "CASE_09": ("I2", True), "CASE_10": ("I4", True)}
for cid, (iid, kn) in sg.items():
    C[cid]["vars"]["egfr_ge20"] = {"group": "P", "known": kn} if kn is not None else U(1, "eGFR(SGLT2i 시작 하한 20)", True)
    C[cid]["items"][iid]["applies"] = "(" + C[cid]["items"][iid]["applies"] + ") and v['egfr_ge20']"
    C[cid]["items"][iid]["rules"] = C[cid]["items"][iid]["rules"] + ["VA_CKD_L2923"]
for cid in ("CASE_02", "CASE_04"):
    RC[cid]["required_confirm"].append("egfr_ge20"); RC[cid]["acceptable_confirm"].append("egfr_ge20")

# E2 + E8: CASE_04 국소 NSAID
del C["CASE_04"]["vars"]["k_topical_nsaid_covered"]
C["CASE_04"]["items"]["I2"]["contra"] = "v['ckd']"
C["CASE_04"]["items"]["I2"]["rules"] = ["OA11", "VA_CKD_P126_L7375"]
C["CASE_04"]["vars"]["q_limit_nsaid"] = {"group": "Q", "known": "accept", "src": "S1 Table No.12 'Limit use of NSAIDs'(helpful)"}
RC["CASE_04"]["items"]["I2"] = ["NOT_APPLY", []]

# E3: CASE_08 SGLT2i 재개 / GLP-1 RA
C["CASE_08"]["vars"]["k_sglt2_after_edka_safe"] = {"group": "K", "known": None, "domain": [True, False], "default": True,
    "how": "EDKA 후 SGLT2i 재개 안전성(VA 는 급성 사건 후 재개 서술, 사례 저자는 영구 중단 판단)"}
C["CASE_08"]["items"]["I2"]["contra"] = "not v['k_sglt2_after_edka_safe']"
C["CASE_08"]["items"]["I3"]["applies"] = "v['t2dm'] and v['ckd'] and not v['k_sglt2_after_edka_safe']"
RC["CASE_08"]["items"]["I2"] = ["HOLD", ["K"]]
RC["CASE_08"]["items"]["I3"] = ["HOLD", ["K"]]
# E6: CASE_08 metformin 재개 eGFR
C["CASE_08"]["vars"]["egfr_post_ok"] = U(1, "AKI 회복 후 eGFR(metformin 사용 기준)", True)
C["CASE_08"]["items"]["I4"]["applies"] = "v['egfr_post_ok'] and v['k_metformin_after_mala_safe']"
RC["CASE_08"]["items"]["I4"] = ["HOLD", ["K", "P"]]
RC["CASE_08"]["required_confirm"].append("egfr_post_ok"); RC["CASE_08"]["acceptable_confirm"].append("egfr_post_ok")

# E4: CASE_07
C["CASE_07"]["vars"]["on_glucose_lowering"] = {"group": "P", "known": False, "src": "PMC10359101 Table 2 혈당강하제 없음"}
C["CASE_07"]["vars"]["sbp_ge130"] = U(1, "혈압(급성기 169/60 vs 원문 'blood pressure at goal')", False)
RC["CASE_07"]["items"]["I1"] = ["NOT_APPLY", []]
RC["CASE_07"]["required_confirm"].append("sbp_ge130"); RC["CASE_07"]["acceptable_confirm"].append("sbp_ge130")

# E5: CASE_09 I2
C["CASE_09"]["vars"]["sglt2_contra"] = U(1, "약물 목록·SGLT2i 금기(원문 약물 목록 없음, AKI 동반)", False)
C["CASE_09"]["items"]["I2"]["contra"] = "v['sglt2_contra']"
RC["CASE_09"]["items"]["I2"] = ["HOLD", ["P", "Q"]]
RC["CASE_09"]["required_confirm"].append("sglt2_contra")

# E7: CASE_13 I3
C["CASE_13"]["vars"]["q_regimen_choice"] = {"group": "Q", "known": None, "domain": ["accept", "reject"], "default": "accept", "cost": 1,
    "how": "clopidogrel 전환+PPI 중단(대안 1) 수용 여부 — 저자 대안 3개"}
C["CASE_13"]["items"]["I3"]["prefs"] = [["q_regimen_choice", "accept"]]
RC["CASE_13"]["items"]["I3"] = ["HOLD", ["Q"]]
RC["CASE_13"]["required_confirm"].append("q_regimen_choice"); RC["CASE_13"]["acceptable_confirm"].append("q_regimen_choice")

c["_note"] = v1["_note"] + " | v2 = 독립 검증 후 사후 정정(E1~E8, make_v2.py 머리말)."
r["label"] = ref1["label"] + " | v2 = run2 결과와 독립 검증을 본 뒤의 사후 정정(E1~E8). 사후 정정이므로 v1 과 함께만 보고."
json.dump(c, open(os.path.join(ROOT, "experiments", "inputs", "cases_input_v2.json"), "w"), ensure_ascii=False, indent=1)
json.dump(r, open(os.path.join(ROOT, "evaluation", "REF_R_v2.json"), "w"), ensure_ascii=False, indent=1)
print("v2 written")
