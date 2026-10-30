"""격리 작성·감사 세션 transcript 기계 검사.

통과 조건(실행 전 고정):
- 각 result.json 의 session_id 에 대응하는 transcript 존재
- 모든 tool_use 이름 ∈ {Read, Write}
- 모든 file_path 가 ~/medmap_step23_authoring_ws/ 아래, Read 는 in/* 또는 out/gen_*.tsv 만, Write 는 out/* 만
- 작성 세션은 out/gen_*.tsv 를 읽지 않음(감사 세션만 읽음)
- attachment 에 nested_memory / instructions(CLAUDE.md·메모리 주입)가 없음
그 밖의 attachment 유형(플랫폼 reminder 등)은 기록만 하고 판정에 쓰지 않는다.
출력: outputs/authoring_isolation_check.json
"""
import glob
import json
from pathlib import Path

import s23_common as S

LOG = S.STEP / "logs/authoring"
TDIR = Path.home() / ".claude/projects" / ("-" + str(S.WS).strip("/").replace("/", "-").replace("_", "-"))


def main():
    res, ok_all = {}, True
    cand_dirs = [TDIR] + [Path(p) for p in glob.glob(str(Path.home() / ".claude/projects/*step23*"))]
    for rf in sorted(LOG.glob("*.result.json")):
        tag = rf.name.removesuffix(".result.json")
        r = json.loads(rf.read_text() or "{}")
        sid = r.get("session_id")
        tr = next((d / f"{sid}.jsonl" for d in cand_dirs if sid and (d / f"{sid}.jsonl").exists()), None)
        info = {"session_id": sid, "model_usage": list((r.get("modelUsage") or {}).keys()), "is_error": r.get("is_error"),
                "num_turns": r.get("num_turns"), "list_price_usd_estimate": r.get("total_cost_usd"),
                "transcript": str(tr) if tr else None, "tool_calls": [], "attachments": {}, "violations": []}
        if not tr:
            info["violations"].append("TRANSCRIPT_NOT_FOUND")
        else:
            for line in tr.read_text().splitlines():
                ev = json.loads(line)
                if ev.get("type") == "attachment":
                    t = (ev.get("attachment") or {}).get("type", "?")
                    info["attachments"][t] = info["attachments"].get(t, 0) + 1
                    if t in ("nested_memory", "instructions"):      # CLAUDE.md·메모리 주입 = 맥락 누수
                        info["violations"].append(f"CONTEXT_INJECTION:{t}")
                for c in ((ev.get("message") or {}).get("content") or []) if isinstance((ev.get("message") or {}).get("content"), list) else []:
                    if c.get("type") != "tool_use":
                        continue
                    name, fp = c.get("name"), (c.get("input") or {}).get("file_path", "")
                    info["tool_calls"].append([name, fp])
                    rel = fp.removeprefix(str(S.WS) + "/") if fp.startswith(str(S.WS) + "/") else None
                    if name not in ("Read", "Write"):
                        info["violations"].append(f"TOOL:{name}")
                    elif rel is None or ".." in fp:
                        info["violations"].append(f"PATH_OUTSIDE_WS:{fp}")
                    elif name == "Read" and not (rel.startswith("in/") or (rel.startswith("out/gen_") and tag.startswith("audit"))):
                        info["violations"].append(f"READ_NOT_ALLOWED:{rel}")
                    elif name == "Write" and not rel.startswith("out/"):
                        info["violations"].append(f"WRITE_NOT_ALLOWED:{rel}")
        info["PASS"] = not info["violations"]
        ok_all &= info["PASS"]
        res[tag] = info
    out = {"ISOLATION": "PASS" if ok_all and res else "FAIL", "sessions": res}
    S.dump_json(S.OUT / "authoring_isolation_check.json", out)
    print(out["ISOLATION"], {k: (v["PASS"], v["violations"][:3], v["attachments"], v["model_usage"]) for k, v in res.items()})


if __name__ == "__main__":
    main()
