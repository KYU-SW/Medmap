"""STEP28.7 §6 — STEP28.6 격리 검사 FAIL(A_c03 · A_c04 · B_c04) 원인 분석. LLM 호출·재작성 없음.

STEP28.6 판정(outputs/authoring_isolation_check.json)은 바꾸지 않는다. 이 스크립트는 transcript 를 다시 읽어 사실만 기록한다:
 1 사용 도구·대상 파일·시각(tool_use / tool_result, 오류 여부)
 2 실제 읽은 파일·바뀐 파일(첫 Write ↔ 마지막 Write 내용 비교 → 바뀐 행 id)
 3 허용 밖 맥락(다른 작성자 파일·작업 폴더 밖·CLAUDE.md/메모리 주입 attachment)
 4 다른 작성자 결과 노출 가능성: 세션 시각에 out/ 에 이미 있던 다른 작성자 파일(파일 mtime 기준 — 존재 ≠ 읽음)
 5 결과 영향: 자기 출력 재읽기 후 재작성으로 바뀐 행 = '자기 검토 영향 있음'(교차 오염 아님) · 안 바뀐 행도 재작성 세션 산출물이므로 FAIL 유지
provenance(행·작성자 단위, 사전 고정): 해당 작성 세션 PASS → ISOLATION_PASS · FAIL → ISOLATION_FAIL · 세션 기록 없음 → ISOLATION_UNVERIFIED.
'교차 오염 근거 없음' 을 이유로 PASS 로 바꾸지 않는다.
출력: outputs/isolation_analysis.json · data/row_isolation.csv(id × 작성자)
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import s287_common as S

TDIR = Path.home() / ".claude/projects" / ("-" + str(S.WS).strip("/").replace("/", "-").replace("_", "-"))


def parse_tsv(text: str) -> dict[str, list[str]]:
    rd = csv.reader(io.StringIO(text), delimiter="\t")
    next(rd, None)
    return {r[0].strip(): [x.strip() for x in r] for r in rd if r}


def main():
    chk = S.load_json(S.S286_DIR / "outputs/authoring_isolation_check.json")
    man = S.read_csv(S.S286_DIR / "data/expression_manifest.csv")
    chunk = S.chunk_of([m["id"] for m in man])
    sess = S.isolation_by_session()
    out_files = {p.name: p.stat().st_mtime for p in (S.WS / "out").glob("*.tsv")}
    res = {}
    for tag, info in chk["sessions"].items():
        if info["PASS"]:
            continue
        tr = TDIR / f"{info['session_id']}.jsonl"
        ev_list, writes, errors, atts = [], [], [], {}
        t_first = None
        for line in tr.read_text().splitlines():
            ev = json.loads(line)
            ts = ev.get("timestamp")
            if ev.get("type") == "attachment":
                t = (ev.get("attachment") or {}).get("type", "?")
                atts[t] = atts.get(t, 0) + 1
            content = (ev.get("message") or {}).get("content")
            for c in content if isinstance(content, list) else []:
                if c.get("type") == "tool_use":
                    inp = c.get("input") or {}
                    t_first = t_first or ts
                    ev_list.append({"ts": ts, "tool": c["name"], "file": inp.get("file_path", "").removeprefix(str(S.WS) + "/"),
                                    "offset": inp.get("offset"), "limit": inp.get("limit")})
                    if c["name"] == "Write":
                        writes.append(inp.get("content", ""))
                elif c.get("type") == "tool_result" and "error" in str(c.get("content", "")).lower():
                    errors.append({"ts": ts, "result": str(c.get("content"))[:160]})
        first, last = parse_tsv(writes[0]), parse_tsv(writes[-1])
        changed = sorted(i for i in set(first) | set(last) if first.get(i) != last.get(i))
        diffs = [{"id": i, "first_write": "\t".join(first.get(i, [])[2:8]), "final_write": "\t".join(last.get(i, [])[2:8])} for i in changed]
        who = tag.split("_")[1]
        other = sorted(n for n, m in out_files.items() if not n.startswith(f"author_{who}_") and n.startswith("author_"))
        from datetime import datetime
        t0 = datetime.fromisoformat(t_first.replace("Z", "+00:00")).timestamp() if t_first else 0
        existed = [n for n in other if out_files[n] < t0]   # 현재 mtime 기준(이후 재작성된 파일은 과소 추정 가능 — 기록만)
        res[tag] = {"session_id": info["session_id"], "step28_6_violations": info["violations"], "tool_events": ev_list, "tool_errors": errors,
                    "attachments": atts, "reads_outside_allowed": [e["file"] for e in ev_list if e["tool"] == "Read" and not e["file"].startswith("in/")],
                    "read_other_author_file": any(e["tool"] == "Read" and e["file"].startswith("out/") and not e["file"].startswith(f"out/author_{who}_") for e in ev_list),
                    "path_outside_ws": any(e["file"].startswith("/") for e in ev_list),
                    "edit_attempted": any(e["tool"] == "Edit" for e in ev_list),
                    "edit_succeeded": not any("No such tool available: Edit" in x["result"] for x in errors) and any(e["tool"] == "Edit" for e in ev_list),
                    "n_writes": len(writes), "rows_first_write": len(first), "rows_final_write": len(last), "rows_changed_by_self_revision": changed,
                    "row_diffs": diffs, "other_author_files_existing_before_session(mtime)": existed,
                    "context_injection": [k for k in atts if k in ("nested_memory", "instructions")],
                    "assessment": {
                        "cause": "작성 후 자기 출력 파일 일부(offset/limit 1–3행)를 다시 읽고 전체를 재작성(자기 검토). 지시문은 '다른 파일·폴더는 읽지 않는다' 였고 "
                                 "검사 규칙은 작성 세션 Read 를 지시문·배정 조각으로만 허용 → 규칙상 위반",
                        "other_author_exposure": "다른 작성자 파일 Read 0 · 작업 폴더 밖 접근 0 · 메모리/CLAUDE.md 주입 0. 단 파일 시스템에는 존재했을 수 있음(읽음 증거 없음)",
                        "influence_on_output": f"재작성으로 {len(changed)} 행 변경(자기 검토 영향). 교차 오염 근거 없음 ≠ 격리 PASS",
                        "provenance": "ISOLATION_FAIL 유지(이 조각의 해당 작성자 행 전부)"}}
    rows = []
    for m in man:
        for w in ("A", "B"):
            st = S.row_isolation(w, chunk[m["id"]], sess)
            chg = any(m["id"] in r["rows_changed_by_self_revision"] for t, r in res.items() if t == f"author_{w}_{chunk[m['id']]}")
            rows.append({"id": m["id"], "korean": m["korean"], "sources": m["sources"], "author": w, "chunk": chunk[m["id"]], "isolation_status": st,
                         "changed_by_self_revision": chg})
    S.wcsv(S.DATA / "row_isolation.csv", rows)
    summ = {"STEP28_6_ISOLATION": chk["ISOLATION"], "failed_sessions": sorted(res), "sessions": res,
            "rows_by_status": {st: sum(1 for r in rows if r["isolation_status"] == st) for st in ("ISOLATION_PASS", "ISOLATION_FAIL", "ISOLATION_UNVERIFIED")},
            "ids_with_any_author_fail": len({r["id"] for r in rows if r["isolation_status"] == "ISOLATION_FAIL"}),
            "fail_ids_by_source": {s: len({r["id"] for r in rows if r["isolation_status"] == "ISOLATION_FAIL" and s in r["sources"]})
                                   for s in ("SILVER442", "WEAKNON903", "SMOKE")},
            "rewrite_cost_if_needed": {"targets": sorted(res), "rows": sum(r["rows_final_write"] for r in res.values()),
                                       "estimate_usd_list_price": "STEP28.6 동일 조각 실측(llm_usage.csv) 합계 기준 — 아래 llm_cost_same_chunks",
                                       "llm_cost_same_chunks": {r["tag"]: r["list_price_usd"] for r in S.read_csv(S.S286_DIR / "outputs/llm_usage.csv")
                                                                if r["tag"] in res},
                                       "executed": False, "note": "이번 단계 LLM 호출 금지 — 재작성은 별도 과금 승인 대상"}}
    S.dump_json(S.OUT / "isolation_analysis.json", summ)
    print(S.dumps({k: summ[k] for k in ("failed_sessions", "rows_by_status", "ids_with_any_author_fail", "fail_ids_by_source")}))
    for t, r in res.items():
        print(t, "changed", len(r["rows_changed_by_self_revision"]), r["rows_changed_by_self_revision"][:10], "edit_ok", r["edit_succeeded"], "other_existed", r["other_author_files_existing_before_session(mtime)"])
    print(S.dumps(summ["rewrite_cost_if_needed"]["llm_cost_same_chunks"]))


if __name__ == "__main__":
    main()
