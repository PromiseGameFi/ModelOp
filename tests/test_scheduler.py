from __future__ import annotations

import asyncio
import time
import unittest

from modelop.capacity import KVPressureTracker
from modelop.scheduler import ContinuousBatchingScheduler, InferenceJob
from modelop.telemetry import Telemetry


class ContinuousBatchingSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_scheduler_refills_slot_immediately(self) -> None:
        kv_tracker = KVPressureTracker(kv_budget_bytes=1_000_000)
        telemetry = Telemetry()
        scheduler = ContinuousBatchingScheduler(
            max_active_sequences=2,
            queue_capacity=10,
            decode_step_seconds=0.01,
            idle_sleep_seconds=0.001,
            kv_tracker=kv_tracker,
            telemetry=telemetry,
        )

        await scheduler.start()
        try:
            admitted_at = time.monotonic()
            jobs: list[InferenceJob] = []
            for request_id, max_new_tokens in [
                ("req-1", 5),
                ("req-2", 1),
                ("req-3", 1),
            ]:
                kv_tracker.try_reserve(
                    request_id=request_id,
                    bytes_needed=100,
                    shed_threshold=0.99,
                )
                future: asyncio.Future = asyncio.get_running_loop().create_future()
                jobs.append(
                    InferenceJob(
                        request_id=request_id,
                        tenant_id="tenant-a",
                        adapter_id="adapter-x",
                        prompt="hello",
                        prompt_tokens=2,
                        max_new_tokens=max_new_tokens,
                        estimated_total_tokens=2 + max_new_tokens,
                        admitted_at=admitted_at,
                        enqueued_at=time.monotonic(),
                        future=future,
                    )
                )

            for job in jobs:
                accepted = await scheduler.enqueue(job)
                self.assertTrue(accepted)

            results = await asyncio.wait_for(
                asyncio.gather(*(job.future for job in jobs)),
                timeout=5.0,
            )
        finally:
            await scheduler.stop()

        req_1 = next(result for result in results if result.request_id == "req-1")
        req_3 = next(result for result in results if result.request_id == "req-3")

        # req-3 should not wait for req-1 to fully complete because req-2 frees a slot.
        self.assertLess(req_3.queue_time_seconds, 0.05)
        self.assertLess(req_3.total_time_seconds, req_1.total_time_seconds)
        self.assertEqual(kv_tracker.active_bytes, 0)
