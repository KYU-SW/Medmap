"""EXP-MAI-009 비교 실험: BASE(단순 처리) vs MEDMAP(근거 검증 엔진), 같은 합성 사건·같은 조회 시점. (1차 심사 반영본)

예상 정답은 생성기 템플릿(scenarios.generate 의 Gold)이 정의한다 — 같은 작성자가 만든 규칙 해석 일치 검사(독립 정답 아님).
모델 추론 없음(AI 입력 집합만 비교). 지표는 합산하지 않는다(한 기록이 A·D 등 여러 지표에 동시에 들어갈 수 있음).
조회 = (합성 환자, 조회 시점). 같은 환자의 조회는 같은 저장소에서 누적되므로 서로 독립이 아니다.
각 지표를 세 단위로 보고: occurrences(기록-조회 발생 건수), lineages(한 번이라도 해당된 고유 계보 수), patients(해당 환자 수).
 A 미래 정보 사용(recorded_at > t 또는 결과 available_at > t) · A2 시각 모름 결과 사용 · B 요청·대기·취소 기록 사용
 C 중복 사본을 원본과 함께 사용(계보 간 사본 단독 사용은 G·I·exact 로 잡힘) · D 정정으로 대체된 버전(정정 전 내용의 재전송 포함) 사용 · E 다른 환자 기록 사용
 F 과거 재생 불일치 조회 수(MEDMAP 은 recorded_at 으로 먼저 거르므로 설계상 0 이 보장되는 값 — 독립 확인 아님)
 G 정답상 보류·제외 계보의 사유 누락 · G2 사유 불일치 · H 반복·입력 순서 섞기(5개 순열) 불일치 조회 수
 I 거짓 보류(정답상 사용해야 하는데 사용하지 않음) · exact 정답 사용 집합 완전 일치 조회 수
주 seed 20261116 + 사전 지정 확인 seed 20261117·20261118·20261119(각 60명).
사용: python run_compare.py <RUN_ID> [--reserve]   (--reserve: 사전 지정 예비 seed 20261120~22, 첫 실행 실패 후 엔진 수정 시에만)
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
import time
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from medmap_demo.events import EventStore  # noqa: E402
from medmap_demo.naive import naive_inputs  # noqa: E402
from medmap_demo.replay import replay  # noqa: E402
from medmap_demo.scenarios import T0, _templates, generate  # noqa: E402

RESULTS = ("AVAILABLE", "CORRECTED", "INVALID")
SEEDS = {"primary": 20261116, "confirm": (20261117, 20261118, 20261119)}
N_PATIENTS, N_SHUFFLE = 60, 5
KEYS = ("A", "A2", "B", "C", "D", "E", "G", "G2", "I")
CODE_FILES = ["medmap_demo/events.py", "medmap_demo/replay.py", "medmap_demo/naive.py", "medmap_demo/scenarios.py", "medmap_demo/assess.py",
              "medmap_demo/model_adapter.py", "src/run_compare.py", "src/run_demo.py", "src/server.py",
              "web/index.html", "tests/test_engine.py", "../hybrid_reassessment_v5_2a1/hybrid521/lineage.py", "../hybrid_reassessment_v4/hybrid4/graphs.py"]


def code_hashes() -> dict:
    return {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in CODE_FILES}


def medmap_out(store, case, t):
    rp = replay(store, case, t)
    return sorted(i.used.event_id for i in rp.usable()), {i.lineage_id: list(i.reasons) for i in rp.items if i.state != "USABLE"}


def base_out(store, case, t, snapshot_only=False):
    return sorted(e.event_id for e, _ in naive_inputs(store, case, t, snapshot_only)), {}


def run(seed: int, n: int) -> dict:
    data = generate(seed, n)
    tpl_all = set(_templates())
    assert {g.template for _, _, gs, _ in data for g in gs} >= tpl_all, "템플릿 일부가 생성되지 않음"
    rng = random.Random(seed + 1)
    occ = {m: {k: 0 for k in KEYS + ("F", "H", "exact", "queries", "used_total")} for m in ("BASE", "MEDMAP")}
    lin = {m: {k: set() for k in KEYS} for m in occ}
    pat = {m: {k: set() for k in KEYS + ("F", "H")} for m in occ}
    per_tpl = {}
    for case, raws, golds, qs in data:
        store = EventStore().extend(raws)
        assert not [x for x in store.log if x["action"] == "REJECTED"], "생성기 기록 거부"
        shuffled = []
        for _ in range(N_SHUFFLE):
            sh = raws[:]
            rng.shuffle(sh)
            shuffled.append(EventStore().extend(sh))
        ev = store.events
        copy_of = {c: g.dup_group for g in golds for c in g.copy_ids}
        for q in qs:
            t = T0 + timedelta(minutes=q)
            gold_used, gold_reason, sup = set(), {}, set()
            for g in golds:
                stt, u, r = g.at(q)
                if stt == "PRESENT":
                    if u:
                        gold_used.add(u)
                    if r:
                        gold_reason[g.lineage_id] = (r, g.template)
                for ts, eid in g.superseded_ids:
                    if q >= ts:
                        sup.add(eid)
            outs = {"MEDMAP": medmap_out(store, case, t), "BASE": base_out(store, case, t)}
            snaps = {"MEDMAP": medmap_out(store.snapshot(t), case, t), "BASE": base_out(store, case, t, snapshot_only=True)}
            reps = {"MEDMAP": [medmap_out(store, case, t)] + [medmap_out(s, case, t) for s in shuffled],
                    "BASE": [base_out(store, case, t)] + [base_out(s, case, t) for s in shuffled]}
            for m, (used, reasons) in outs.items():
                X, L, P = occ[m], lin[m], pat[m]
                X["queries"] += 1
                X["used_total"] += len(used)
                us = set(used)
                used_lineages = {ev[x].lineage_id for x in used}

                def hit(k, lid):
                    X[k] += 1
                    L[k].add(lid)
                    P[k].add(case.patient_id)
                for eid in used:
                    e = ev[eid]
                    if e.recorded_at > t or (e.status in RESULTS and e.available_at is not None and e.available_at > t):
                        hit("A", e.lineage_id)
                    if e.status in RESULTS and e.available_at is None:
                        hit("A2", e.lineage_id)
                    if e.status in ("ORDERED", "PENDING", "CANCELLED"):
                        hit("B", e.lineage_id)
                    if eid in sup:
                        hit("D", e.lineage_id)
                    if e.patient_id != case.patient_id:
                        hit("E", e.lineage_id)
                    if eid in copy_of and copy_of[eid] in used_lineages:
                        hit("C", e.lineage_id)
                for u in gold_used - us:
                    hit("I", ev[u].lineage_id)
                if snaps[m] != (used, reasons):
                    X["F"] += 1
                    P["F"].add(case.patient_id)
                if any(r != (used, reasons) for r in reps[m]):
                    X["H"] += 1
                    P["H"].add(case.patient_id)
                X["exact"] += us == gold_used
                for lid, (r, tpl) in gold_reason.items():
                    got = reasons.get(lid)
                    if not got:
                        hit("G", lid)
                    elif got[0] != r:
                        hit("G2", lid)
                    k = per_tpl.setdefault(tpl, {"BASE": [set(), set()], "MEDMAP": [set(), set()]})
                    k[m][0].add(lid)
                    if got and got[0] == r:
                        k[m][1].add(lid)
    summary = {}
    for m in occ:
        summary[m] = {k: {"occurrences": occ[m][k], "lineages": len(lin[m][k]), "patients": len(pat[m][k])} for k in KEYS}
        for k in ("F", "H"):
            summary[m][k] = {"queries": occ[m][k], "patients": len(pat[m][k])}
        summary[m]["exact_used_match"] = f"{occ[m]['exact']}/{occ[m]['queries']}"
        summary[m]["used_total_occurrences"] = occ[m]["used_total"]
    return {"seed": seed, "n_patients": n, "n_queries": occ["MEDMAP"]["queries"], "n_records": sum(len(r) for _, r, _, _ in data),
            "templates": sorted(tpl_all), "metrics": summary,
            "reason_correct_lineages_by_template(정답 계보 중 사유 첫 코드 일치 — 계보 단위, 어느 조회에서든 일치하면 포함)":
                {k: {m: f"{len(v[m][1])}/{len(v[m][0])}" for m in v} for k, v in sorted(per_tpl.items())}}


def passed(r: dict) -> bool:
    M = r["metrics"]["MEDMAP"]
    zero = all(M[k]["occurrences"] == 0 for k in KEYS) and M["F"]["queries"] == 0 and M["H"]["queries"] == 0
    n = r["n_queries"]
    return n > 0 and zero and M["exact_used_match"] == f"{n}/{n}"


def main(run_id: str, seeds: dict | None = None):
    seeds = seeds or SEEDS
    out = ROOT / "outputs" / f"compare_{run_id}"
    if out.exists():
        raise SystemExit("이미 있는 실행 식별자 — 덮어쓰지 않음")
    out.mkdir(parents=True)
    t0 = time.time()
    res_seeds = {"primary": run(seeds["primary"], N_PATIENTS), "confirm": [run(s, N_PATIENTS) for s in seeds["confirm"]]}
    again = run(seeds["primary"], N_PATIENTS)
    body = {"experiment": "EXP-MAI-009", "design": "사전 정의 합성 사건 시험(규칙 해석 일치 검사). 임상 자료·임상 성능 아님",
            "base_definition": sys.modules["medmap_demo.naive"].__doc__.strip(), "seeds": seeds, "n_shuffle_permutations": N_SHUFFLE,
            "results": res_seeds, "in_process_rerun_identical": again == res_seeds["primary"],
            "pass_primary": passed(res_seeds["primary"]), "pass_confirm": [passed(r) for r in res_seeds["confirm"]],
            "not_covered_by_generator(단위 테스트에서만 검증)": ["CONFLICTING_VERSIONS", "LINEAGE_INVALID(순환·이전 버전 누락·계보 간 정정)", "PATIENT_ID_CONFLICT",
                                                          "EVIDENCE_INVALID", "NOT_LINKED_TO_HYPOTHESIS", "NEWER_VERSION_NOT_YET_AVAILABLE",
                                                          "NEWER_VERSION_TIME_UNKNOWN", "kind 는 LAB 단일"],
            "code_sha256": code_hashes()}
    canon = json.dumps(body, ensure_ascii=False, sort_keys=True)
    res = {"run_id": run_id, **body, "result_sha256(실행 시간 제외 본문)": hashlib.sha256(canon.encode()).hexdigest(), "elapsed_sec": round(time.time() - t0, 1)}
    (out / "compare.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    p = res_seeds["primary"]["metrics"]
    print(json.dumps({m: {k: (v["occurrences"] if "occurrences" in v else v) if isinstance(v, dict) else v for k, v in p[m].items()} for m in p}, ensure_ascii=False))
    print("pass primary", res["pass_primary"], "confirm", res["pass_confirm"], "rerun", res["in_process_rerun_identical"], "sha", res["result_sha256(실행 시간 제외 본문)"][:16])


RESERVE_SEEDS = {"primary": 20261120, "confirm": (20261121, 20261122)}   # 사전 지정 예비 seed(첫 실행 실패·엔진 수정 시에만 사용)

if __name__ == "__main__":
    main(sys.argv[1], RESERVE_SEEDS if "--reserve" in sys.argv[2:] else None)
