"""SttScheduler: 스트림별 최신 partial 만, final 우선, 추론은 한 번에 하나.

실행: ~/ai_env/bin/python -m unittest tests.test_stt_scheduler
"""
import asyncio
import sys
import threading
import time
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from medmap.stt_scheduler import SttInferenceError, SttScheduler


class FakeModel:
    def __init__(self, delay=0.05):
        self.calls, self.delay, self.active, self.max_active = [], delay, 0, 0
        self.lock = threading.Lock()

    def __call__(self, audio):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(self.delay)
        with self.lock:
            self.active -= 1
        self.calls.append(len(audio))
        if len(audio) == 99:
            raise RuntimeError("boom")
        return f"len{len(audio)}"


class SchedulerTest(unittest.TestCase):
    def test_latest_partial_wins(self):
        model = FakeModel(0.1)

        async def go():
            sch = SttScheduler(model)
            first = asyncio.create_task(sch.submit_partial("s", np.zeros(10)))
            await asyncio.sleep(0.02)                          # first 가 실행 중
            stale = asyncio.create_task(sch.submit_partial("s", np.zeros(20)))
            await asyncio.sleep(0)
            latest = asyncio.create_task(sch.submit_partial("s", np.zeros(30)))
            return await first, await stale, await latest

        a, b, c = asyncio.run(go())
        self.assertEqual(a[0], "len10")
        self.assertIsNone(b)
        self.assertEqual(c[0], "len30")
        self.assertEqual(model.calls, [10, 30])

    def test_final_before_waiting_partial_and_serial(self):
        model = FakeModel(0.05)

        async def go():
            sch = SttScheduler(model)
            busy = asyncio.create_task(sch.submit_partial("a", np.zeros(1)))
            await asyncio.sleep(0.01)
            p = asyncio.create_task(sch.submit_partial("b", np.zeros(2)))
            await asyncio.sleep(0)
            f = asyncio.create_task(sch.submit_final("c", np.zeros(3)))
            await asyncio.gather(busy, p, f)

        asyncio.run(go())
        self.assertEqual(model.calls, [1, 3, 2])
        self.assertEqual(model.max_active, 1)

    def test_other_streams_partials_are_not_dropped(self):
        model = FakeModel(0.02)

        async def go():
            sch = SttScheduler(model)
            return await asyncio.gather(sch.submit_partial("a", np.zeros(4)), sch.submit_partial("b", np.zeros(5)))

        a, b = asyncio.run(go())
        self.assertEqual((a[0], b[0]), ("len4", "len5"))

    def test_timings_overload_and_errors(self):
        async def go():
            sch = SttScheduler(FakeModel(0.02), overload_ms=1.0)
            await asyncio.gather(*(sch.submit_final(str(i), np.zeros(1)) for i in range(3)))
            overloaded = sch.overloaded
            text, ms = await SttScheduler(FakeModel(0.0)).submit_final("x", np.zeros(5))
            with self.assertRaises(SttInferenceError) as ctx:     # assertRaises 는 traceback frame 을 정리한다 — 워커가 살아남아야 함
                await sch.submit_final("y", np.zeros(99))
            self.assertEqual(ctx.exception.kind, "RuntimeError")
            after = await sch.submit_final("z", np.zeros(6))          # 오류 뒤에도 워커가 살아 있다
            return overloaded, ms, after

        overloaded, ms, after = asyncio.run(go())
        self.assertTrue(overloaded)
        self.assertEqual(set(ms), {"queue", "decode"})
        self.assertEqual(after[0], "len6")


    def test_overload_flag_expires(self):
        sch = SttScheduler(FakeModel(0.0), overload_ms=1.0, overload_window_s=0.05)
        sch.last_queue_ms, sch.last_queue_at = 5000.0, time.perf_counter()
        self.assertTrue(sch.overloaded)
        time.sleep(0.06)
        self.assertFalse(sch.overloaded)                     # 새 측정이 없어도 시간이 지나면 풀린다


if __name__ == "__main__":
    unittest.main()
