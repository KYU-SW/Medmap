"""STEP28.6 격리 작성·감사 세션 transcript 기계 검사(STEP23 검사기와 같은 규칙, 경로만 STEP28.6).

통과 조건(실행 전 고정):
- result.json 의 session_id 에 대응하는 transcript 존재 · 결과 모델이 지정 모델(author_A = opus, author_B = sonnet, audit = opus)
- 모든 tool_use ∈ {Read, Write} · 모든 file_path 가 ~/medmap_step28_6_ws/ 아래('..' 없음)
- 작성 세션 Read = in/author_instructions.md 와 배정 조각 in/expressions_cNN.tsv 만 · 감사 세션 Read = in/audit_* 만 · Write = out/* 만
- 작성 세션은 out/ 의 다른 작성자 파일을 읽지 않음
- attachment 에 nested_memory / instructions(CLAUDE.md·메모리 주입) 없음. 그 밖의 플랫폼 attachment 는 기록만.
- 실행 오류(is_error, 예: 주간 한도 메시지)는 run_error 로 따로 기록(격리 판정과 별개). [변경 기록 2026-10-11: 처음엔 위반에 섞어 셌음]
출력: outputs/authoring_isolation_check.json
"""
import json
from pathlib import Path

import s286_common as S

LOG = S.LOGS / "authoring"
TDIR = Path.home() / ".claude/projects" / ("-" + str(S.WS).strip("/").replace("/", "-").replace("_", "-"))


def main():
    res, ok_all = {}, True
    for rf in sorted(LOG.glob("*.result.json")):
        tag = rf.name.removesuffix(".result.json")
        r = json.loads(rf.read_text() or "{}")
        sid = r.get("session_id")
        tr = TDIR / f"{sid}.jsonl" if sid else None
        want = "opus" if tag.startswith(("author_A", "audit")) else "sonnet"
        models = list((r.get("modelUsage") or {}).keys())
        info = {"session_id": sid, "model_usage": models, "is_error": r.get("is_error"), "num_turns": r.get("num_turns"),
                "list_price_usd_estimate": r.get("total_cost_usd"), "transcript": str(tr) if tr and tr.exists() else None,
                "tool_calls": [], "attachments": {}, "violations": []}
        if not any(want in m for m in models):
            info["violations"].append(f"MODEL_MISMATCH:{models}")
        info["run_error"] = (r.get("result") or "")[:100] if r.get("is_error") else ""   # 실행 오류(예: 주간 한도)는 격리 위반과 분리해 기록
        if not (tr and tr.exists()):
            info["violations"].append("TRANSCRIPT_NOT_FOUND")
        else:
            chunk = tag.split("_")[-1] if tag.startswith("author") else None
            for line in tr.read_text().splitlines():
                ev = json.loads(line)
                if ev.get("type") == "attachment":
                    t = (ev.get("attachment") or {}).get("type", "?")
                    info["attachments"][t] = info["attachments"].get(t, 0) + 1
                    if t in ("nested_memory", "instructions"):
                        info["violations"].append(f"CONTEXT_INJECTION:{t}")
                content = (ev.get("message") or {}).get("content")
                for c in content if isinstance(content, list) else []:
                    if c.get("type") != "tool_use":
                        continue
                    name, fp = c.get("name"), (c.get("input") or {}).get("file_path", "")
                    info["tool_calls"].append([name, fp])
                    rel = fp.removeprefix(str(S.WS) + "/") if fp.startswith(str(S.WS) + "/") else None
                    if name not in ("Read", "Write"):
                        info["violations"].append(f"TOOL:{name}")
                    elif rel is None or ".." in fp:
                        info["violations"].append(f"PATH_OUTSIDE_WS:{fp}")
                    elif name == "Read":
                        ok = (rel in ("in/author_instructions.md", f"in/expressions_{chunk}.tsv")) if chunk else rel.startswith("in/audit_")
                        if not ok:
                            info["violations"].append(f"READ_NOT_ALLOWED:{rel}")
                    elif name == "Write" and not rel.startswith("out/"):
                        info["violations"].append(f"WRITE_NOT_ALLOWED:{rel}")
        info["PASS"] = not info["violations"]
        ok_all &= info["PASS"]
        res[tag] = info
    cost = sum(v["list_price_usd_estimate"] or 0 for v in res.values())
    out = {"ISOLATION": "PASS" if ok_all and res else "FAIL", "n_sessions": len(res), "list_price_usd_estimate_total(청구액 아님)": round(cost, 3),
           "sessions": res}
    S.dump_json(S.OUT / "authoring_isolation_check.json", out)
    print(out["ISOLATION"], round(cost, 3), {k: (v["PASS"], v["violations"][:3]) for k, v in res.items()})


if __name__ == "__main__":
    main()
