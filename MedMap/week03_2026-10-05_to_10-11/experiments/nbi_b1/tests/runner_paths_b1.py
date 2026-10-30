#!/usr/bin/env python3
"""NBI-B1 러너·실행기 실패 경로 시험 — 임시 사본 + HOME 교체, 고정 파일 변조로 실데이터 단계 전에 멈춤. 실데이터 미사용.

실행: python3 docs/research/nbi/b1/tests/runner_paths_b1.py
확인: 러너 인자 7, 출력 존재 4, 변조 5(제한 폴더 미생성) / 실행기 인자 7, 자원 미충족 8(marker 미생성),
      다른 cwd 에서 & 로 시작해도 로그·marker·ram_guard 로그가 b1/logs 절대경로에 생성(0), 두 번째 시작 4.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

B1 = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B0 = os.path.abspath(os.path.join(B1, "..", "b0"))
REAL_SCRIPTS = os.path.join(os.path.expanduser("~"), "scripts")


def sh(cmd, env, cwd="/tmp"):
    r = subprocess.run(["bash", "-c", cmd], env=env, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout


def main():
    res = []
    with tempfile.TemporaryDirectory() as d:
        b1, b0 = os.path.join(d, "nbi", "b1"), os.path.join(d, "nbi", "b0")
        shutil.copytree(B1, b1, ignore=shutil.ignore_patterns("logs", "out", "__pycache__"))
        shutil.copytree(B0, b0, ignore=shutil.ignore_patterns("logs", "__pycache__", "docs"))
        home = os.path.join(d, "home")
        os.makedirs(home)
        env = dict(os.environ, HOME=home)
        run, launch = os.path.join(b1, "run_b1.sh"), os.path.join(b1, "launch_b1.sh")
        res.append(("runner_args_7", sh(f"bash {run} x", env)[0] == 7))
        os.makedirs(os.path.join(b1, "out", "b1"))
        res.append(("runner_output_exists_4", sh(f"bash {run}", env)[0] == 4))
        shutil.rmtree(os.path.join(b1, "out"))
        with open(os.path.join(b1, "tests", "test_b1.py"), "a") as f:
            f.write("# tamper\n")
        res.append(("runner_tamper_5", sh(f"bash {run}", env)[0] == 5))
        res.append(("no_restricted_dir_after_5", os.listdir(home) == []))
        res.append(("launcher_args_7", sh(f"bash {launch} y", env)[0] == 7))
        fake = os.path.join(d, "fake_wait.sh")
        with open(fake, "w") as f:
            f.write('#!/bin/bash\necho "WAIT ram=95%"; exit 1\n')
        os.chmod(fake, 0o755)
        rc, _ = sh(f"bash {launch}", dict(env, B1_RESOURCE_CHECK=fake))
        res.append(("launcher_resources_8", rc == 8 and not os.path.exists(os.path.join(b1, "logs", "b1_launch.marker"))))
        ok_env = dict(env, B1_RESOURCE_CHECK=os.path.join(REAL_SCRIPTS, "wait_for_resources.sh"),
                      B1_RAM_GUARD=os.path.join(REAL_SCRIPTS, "ram_guard.sh"))
        rc, out = sh(f"cd /tmp && bash {launch} & wait $!", ok_env)
        res.append(("launcher_ok_0", rc == 0 and "B1_LAUNCH ok" in out))
        if rc != 0:
            print("launcher_output:", out.strip()[:300])
        marker = os.path.join(b1, "logs", "b1_launch.marker", "launch")
        txt = open(marker).read() if os.path.exists(marker) else ""
        res.append(("marker_records_override", "override=TEST_OVERRIDE_SET" in txt and "resource_check rc=0" in txt))
        for _ in range(90):  # ram_guard 가 대상 종료를 기록할 때까지(60 s 주기)
            g = os.path.join(b1, "logs", "ram_guard_b1.log")
            if os.path.exists(g) and "정상 종료" in open(g, encoding="utf-8").read():
                break
            time.sleep(1)
        res.append(("ram_guard_log_absolute", os.path.exists(os.path.join(b1, "logs", "ram_guard_b1.log"))))
        nl = os.path.join(b1, "logs", "nohup_b1.log")
        res.append(("runner_stopped_at_5", os.path.exists(nl) and "pinned_sha_mismatch" in open(nl).read()))
        res.append(("no_nested_logs", not os.path.exists(os.path.join("/tmp", "docs"))))
        res.append(("launcher_second_4", sh(f"bash {launch}", ok_env)[0] == 4))
    for n, ok in res:
        print(n, "PASS" if ok else "FAIL")
    bad = [n for n, ok in res if not ok]
    print("RUNNER_PATHS_SUMMARY pass=%d total=%d" % (len(res) - len(bad), len(res)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
