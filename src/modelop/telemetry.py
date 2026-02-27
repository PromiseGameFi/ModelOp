from __future__ import annotations

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
except ModuleNotFoundError:
    CONTENT_TYPE_LATEST = "text/plain; charset=utf-8"

    class _NoopMetric:
        def labels(self, **kwargs):
            return self

        def inc(self, amount: float = 1.0) -> None:
            return None

        def set(self, value: float) -> None:
            return None

        def observe(self, value: float) -> None:
            return None

    def Counter(*args, **kwargs):  # type: ignore[override]
        return _NoopMetric()

    def Gauge(*args, **kwargs):  # type: ignore[override]
        return _NoopMetric()

    def Histogram(*args, **kwargs):  # type: ignore[override]
        return _NoopMetric()

    def generate_latest() -> bytes:
        return b"# prometheus_client not installed; using noop telemetry\n"

REQUESTS_TOTAL = Counter(
    "gateway_requests_total",
    "Ingress request outcomes.",
    ["tenant_id", "result", "reason"],
)
TOKENS_GENERATED_TOTAL = Counter(
    "tokens_generated_total",
    "Generated output tokens by tenant.",
    ["tenant_id"],
)
PROMPT_TRUNCATIONS_TOTAL = Counter(
    "prompt_truncations_total",
    "Prompt truncation count by tenant.",
    ["tenant_id"],
)
REQUEST_ID_COLLISIONS_TOTAL = Counter(
    "request_id_collisions_total",
    "Concurrent request-id collision rejections.",
    ["tenant_id"],
)
SCHEDULER_TICKS_TOTAL = Counter("scheduler_ticks_total", "Continuous batching ticks.")

KV_CACHE_UTILIZATION_RATIO = Gauge(
    "kv_cache_utilization_ratio",
    "Active KV cache utilization (0..1).",
)
QUEUE_DEPTH = Gauge("queue_depth", "Inference queue depth.")
ACTIVE_SEQUENCES = Gauge("active_sequences", "Active decode sequences.")

TTFT_SECONDS = Histogram(
    "request_ttft_seconds",
    "Time to first token.",
    ["tenant_id"],
)
TPOT_SECONDS = Histogram(
    "request_tpot_seconds",
    "Time per output token after first token.",
    ["tenant_id"],
)
QUEUE_WAIT_SECONDS = Histogram(
    "queue_wait_seconds",
    "Time from enqueue to first decode step.",
    ["tenant_id"],
)


class Telemetry:
    def record_request_outcome(self, tenant_id: str, result: str, reason: str) -> None:
        REQUESTS_TOTAL.labels(
            tenant_id=tenant_id,
            result=result,
            reason=reason,
        ).inc()

    def observe_tpot(self, tenant_id: str, value: float) -> None:
        TPOT_SECONDS.labels(tenant_id=tenant_id).observe(max(0.0, value))

    def observe_ttft(self, tenant_id: str, value: float) -> None:
        TTFT_SECONDS.labels(tenant_id=tenant_id).observe(max(0.0, value))

    def observe_queue_wait(self, tenant_id: str, value: float) -> None:
        QUEUE_WAIT_SECONDS.labels(tenant_id=tenant_id).observe(max(0.0, value))

    def add_generated_tokens(self, tenant_id: str, count: int) -> None:
        TOKENS_GENERATED_TOTAL.labels(tenant_id=tenant_id).inc(max(0, count))

    def record_prompt_truncation(self, tenant_id: str) -> None:
        PROMPT_TRUNCATIONS_TOTAL.labels(tenant_id=tenant_id).inc()

    def record_request_id_collision(self, tenant_id: str) -> None:
        REQUEST_ID_COLLISIONS_TOTAL.labels(tenant_id=tenant_id).inc()

    def tick_scheduler(self, queue_depth: int, active_sequences: int) -> None:
        SCHEDULER_TICKS_TOTAL.inc()
        QUEUE_DEPTH.set(max(0, queue_depth))
        ACTIVE_SEQUENCES.set(max(0, active_sequences))

    def set_kv_utilization(self, utilization_ratio: float) -> None:
        KV_CACHE_UTILIZATION_RATIO.set(min(1.0, max(0.0, utilization_ratio)))

    @staticmethod
    def scrape() -> tuple[bytes, str]:
        return generate_latest(), CONTENT_TYPE_LATEST
