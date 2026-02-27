from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from modelop.capacity import KVPressureTracker
from modelop.telemetry import Telemetry


@dataclass(slots=True)
class GenerationResult:
    request_id: str
    tenant_id: str
    adapter_id: str
    output: str
    completion_tokens: int
    queue_time_seconds: float
    ttft_seconds: float
    avg_tpot_seconds: float
    total_time_seconds: float


@dataclass(slots=True)
class InferenceJob:
    request_id: str
    tenant_id: str
    adapter_id: str
    prompt: str
    prompt_tokens: int
    max_new_tokens: int
    estimated_total_tokens: int
    admitted_at: float
    enqueued_at: float
    future: asyncio.Future[GenerationResult]


@dataclass
class ActiveSequence:
    job: InferenceJob
    started_at: float | None = None
    first_token_at: float | None = None
    last_token_at: float | None = None
    output_chunks: list[str] = field(default_factory=list)
    generated_tokens: int = 0
    tpot_deltas: list[float] = field(default_factory=list)
    done: bool = False


class ContinuousBatchingScheduler:
    def __init__(
        self,
        max_active_sequences: int,
        queue_capacity: int,
        decode_step_seconds: float,
        idle_sleep_seconds: float,
        kv_tracker: KVPressureTracker,
        telemetry: Telemetry,
    ) -> None:
        self._max_active_sequences = max_active_sequences
        self._decode_step_seconds = decode_step_seconds
        self._idle_sleep_seconds = idle_sleep_seconds
        self._queue: asyncio.Queue[InferenceJob] = asyncio.Queue(maxsize=queue_capacity)
        self._active_sequences: list[ActiveSequence] = []

        self._kv_tracker = kv_tracker
        self._telemetry = telemetry

        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    @property
    def active_count(self) -> int:
        return len(self._active_sequences)

    @property
    def queue_capacity(self) -> int:
        return self._queue.maxsize

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="continuous-batching-scheduler")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
            self._task = None

        while not self._queue.empty():
            try:
                job = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            self._kv_tracker.release(job.request_id)
            if not job.future.done():
                job.future.set_exception(RuntimeError("scheduler stopped before execution"))
            self._queue.task_done()

        for active in self._active_sequences:
            self._kv_tracker.release(active.job.request_id)
            if not active.job.future.done():
                active.job.future.set_exception(RuntimeError("scheduler stopped during execution"))
        self._active_sequences.clear()

        self._telemetry.tick_scheduler(queue_depth=self.queue_depth, active_sequences=self.active_count)
        self._telemetry.set_kv_utilization(self._kv_tracker.utilization_ratio)

    async def enqueue(self, job: InferenceJob) -> bool:
        if self._queue.full():
            return False
        await self._queue.put(job)
        self._telemetry.tick_scheduler(
            queue_depth=self.queue_depth, active_sequences=self.active_count
        )
        return True

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            await self._refill_slots()

            if not self._active_sequences:
                self._telemetry.tick_scheduler(
                    queue_depth=self.queue_depth, active_sequences=self.active_count
                )
                await asyncio.sleep(self._idle_sleep_seconds)
                continue

            await asyncio.sleep(self._decode_step_seconds)
            now = time.monotonic()

            for sequence in list(self._active_sequences):
                self._decode_single_step(sequence=sequence, now=now)

            self._finalize_completed(now=now)
            await self._refill_slots()
            self._telemetry.tick_scheduler(
                queue_depth=self.queue_depth, active_sequences=self.active_count
            )
            self._telemetry.set_kv_utilization(self._kv_tracker.utilization_ratio)

    async def _refill_slots(self) -> None:
        while len(self._active_sequences) < self._max_active_sequences:
            try:
                job = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            self._queue.task_done()
            self._active_sequences.append(ActiveSequence(job=job))

    def _decode_single_step(self, sequence: ActiveSequence, now: float) -> None:
        if sequence.done:
            return

        if sequence.started_at is None:
            sequence.started_at = now
            self._telemetry.observe_queue_wait(
                tenant_id=sequence.job.tenant_id,
                value=sequence.started_at - sequence.job.enqueued_at,
            )

        if sequence.generated_tokens == 0:
            sequence.first_token_at = now
            self._telemetry.observe_ttft(
                tenant_id=sequence.job.tenant_id,
                value=sequence.first_token_at - sequence.job.admitted_at,
            )
        elif sequence.last_token_at is not None:
            delta = now - sequence.last_token_at
            sequence.tpot_deltas.append(delta)
            self._telemetry.observe_tpot(tenant_id=sequence.job.tenant_id, value=delta)

        next_index = sequence.generated_tokens + 1
        sequence.output_chunks.append(f"tok{next_index}")
        sequence.generated_tokens = next_index
        sequence.last_token_at = now

        if sequence.generated_tokens >= sequence.job.max_new_tokens:
            sequence.done = True

    def _finalize_completed(self, now: float) -> None:
        if not self._active_sequences:
            return

        remaining: list[ActiveSequence] = []
        for sequence in self._active_sequences:
            if not sequence.done:
                remaining.append(sequence)
                continue

            self._kv_tracker.release(sequence.job.request_id)
            self._telemetry.set_kv_utilization(self._kv_tracker.utilization_ratio)
            self._telemetry.add_generated_tokens(
                tenant_id=sequence.job.tenant_id,
                count=sequence.generated_tokens,
            )

            if sequence.first_token_at is None:
                ttft = 0.0
            else:
                ttft = max(0.0, sequence.first_token_at - sequence.job.admitted_at)

            avg_tpot = (
                sum(sequence.tpot_deltas) / len(sequence.tpot_deltas)
                if sequence.tpot_deltas
                else 0.0
            )

            result = GenerationResult(
                request_id=sequence.job.request_id,
                tenant_id=sequence.job.tenant_id,
                adapter_id=sequence.job.adapter_id,
                output=" ".join(sequence.output_chunks),
                completion_tokens=sequence.generated_tokens,
                queue_time_seconds=max(0.0, (sequence.started_at or now) - sequence.job.enqueued_at),
                ttft_seconds=ttft,
                avg_tpot_seconds=avg_tpot,
                total_time_seconds=max(0.0, now - sequence.job.admitted_at),
            )

            if not sequence.job.future.cancelled() and not sequence.job.future.done():
                sequence.job.future.set_result(result)

        self._active_sequences = remaining
