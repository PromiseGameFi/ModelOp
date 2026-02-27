from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from modelop.capacity import KVCapacityEstimator, KVPressureTracker
from modelop.config import GatewayConfig
from modelop.context_window import ContextOptimizationResult, ContextWindowOptimizer
from modelop.identity import InflightRequestRegistry
from modelop.rate_limit import TokenRateLimiter
from modelop.schemas import GenerateRequest, GenerateResponse, HealthResponse
from modelop.scheduler import ContinuousBatchingScheduler, InferenceJob
from modelop.telemetry import Telemetry


@dataclass
class Services:
    config: GatewayConfig
    telemetry: Telemetry
    context_optimizer: ContextWindowOptimizer
    request_registry: InflightRequestRegistry
    rate_limiter: TokenRateLimiter
    kv_estimator: KVCapacityEstimator
    kv_tracker: KVPressureTracker
    scheduler: ContinuousBatchingScheduler


def _build_services(config: GatewayConfig) -> Services:
    telemetry = Telemetry()
    kv_tracker = KVPressureTracker(kv_budget_bytes=config.kv_budget_bytes)
    services = Services(
        config=config,
        telemetry=telemetry,
        context_optimizer=ContextWindowOptimizer(
            head_ratio=config.prompt_truncation_head_ratio,
            truncation_marker=config.prompt_truncation_marker,
        ),
        request_registry=InflightRequestRegistry(),
        rate_limiter=TokenRateLimiter(config=config),
        kv_estimator=KVCapacityEstimator(bytes_per_token=config.kv_bytes_per_token),
        kv_tracker=kv_tracker,
        scheduler=ContinuousBatchingScheduler(
            max_active_sequences=config.scheduler_max_active_sequences,
            queue_capacity=config.scheduler_queue_capacity,
            decode_step_seconds=config.scheduler_decode_step_seconds,
            idle_sleep_seconds=config.scheduler_idle_sleep_seconds,
            kv_tracker=kv_tracker,
            telemetry=telemetry,
        ),
    )
    telemetry.set_kv_utilization(0.0)
    return services


def create_app(config: GatewayConfig | None = None) -> FastAPI:
    app_config = config or GatewayConfig()

    async def allocate_request_id(services: Services, request: GenerateRequest) -> str:
        if request.request_id is not None:
            claimed = await services.request_registry.claim(request.request_id)
            if claimed:
                return request.request_id
            services.telemetry.record_request_id_collision(request.tenant_id)
            services.telemetry.record_request_outcome(
                tenant_id=request.tenant_id,
                result="rejected",
                reason="request_id_collision",
            )
            raise HTTPException(
                status_code=409,
                detail="request_id already in flight; use a unique request_id",
            )

        # Generated IDs are retried defensively in the unlikely event of collision.
        for _ in range(5):
            candidate = str(uuid.uuid4())
            if await services.request_registry.claim(candidate):
                return candidate
        raise HTTPException(status_code=503, detail="could not allocate unique request_id")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        services = _build_services(config=app_config)
        app.state.services = services
        await services.scheduler.start()
        yield
        await services.scheduler.stop()

    app = FastAPI(title="ModelOp Gateway", version="0.1.0", lifespan=lifespan)

    @app.post("/v1/generate", response_model=GenerateResponse)
    async def generate(request: GenerateRequest) -> GenerateResponse:
        services: Services = app.state.services
        now = time.monotonic()
        request_id = await allocate_request_id(services=services, request=request)
        policy = services.config.policy_for(request.tenant_id)
        adapter_id = request.adapter_id or policy.default_adapter_id

        try:
            prompt_budget_tokens = services.config.max_request_tokens - request.max_new_tokens
            if prompt_budget_tokens <= 0:
                services.telemetry.record_request_outcome(
                    tenant_id=request.tenant_id,
                    result="rejected",
                    reason="invalid",
                )
                raise HTTPException(
                    status_code=400,
                    detail="max_new_tokens leaves no room for prompt tokens",
                )

            context_result: ContextOptimizationResult = services.context_optimizer.optimize(
                prompt=request.prompt,
                max_prompt_tokens=prompt_budget_tokens,
            )

            if context_result.prompt_truncated and not services.config.enable_prompt_truncation:
                services.telemetry.record_request_outcome(
                    tenant_id=request.tenant_id,
                    result="rejected",
                    reason="invalid",
                )
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"request token budget {context_result.original_prompt_tokens + request.max_new_tokens} "
                        f"exceeds max_request_tokens={services.config.max_request_tokens}"
                    ),
                )

            if context_result.prompt_truncated:
                services.telemetry.record_prompt_truncation(request.tenant_id)

            prompt_tokens = context_result.effective_prompt_tokens
            estimated_total_tokens = prompt_tokens + request.max_new_tokens

            if estimated_total_tokens > services.config.max_request_tokens:
                services.telemetry.record_request_outcome(
                    tenant_id=request.tenant_id,
                    result="rejected",
                    reason="invalid",
                )
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"request token budget {estimated_total_tokens} exceeds "
                        f"max_request_tokens={services.config.max_request_tokens}"
                    ),
                )

            if not services.rate_limiter.try_consume(
                tenant_id=request.tenant_id,
                amount=estimated_total_tokens,
                now=now,
            ):
                services.telemetry.record_request_outcome(
                    tenant_id=request.tenant_id,
                    result="rejected",
                    reason="rate_limit",
                )
                raise HTTPException(status_code=429, detail="rate limit exceeded")

            estimated_kv_bytes = services.kv_estimator.estimate_request_bytes(
                estimated_total_tokens=estimated_total_tokens
            )
            if not services.kv_tracker.try_reserve(
                request_id=request_id,
                bytes_needed=estimated_kv_bytes,
                shed_threshold=services.config.shed_threshold,
            ):
                services.rate_limiter.refund(
                    tenant_id=request.tenant_id, amount=estimated_total_tokens
                )
                services.telemetry.record_request_outcome(
                    tenant_id=request.tenant_id,
                    result="rejected",
                    reason="kv_pressure",
                )
                raise HTTPException(
                    status_code=429,
                    detail="request shed due to KV-cache pressure threshold",
                )
            services.telemetry.set_kv_utilization(services.kv_tracker.utilization_ratio)

            future: asyncio.Future = asyncio.get_running_loop().create_future()
            job = InferenceJob(
                request_id=request_id,
                tenant_id=request.tenant_id,
                adapter_id=adapter_id,
                prompt=context_result.prompt,
                prompt_tokens=prompt_tokens,
                max_new_tokens=request.max_new_tokens,
                estimated_total_tokens=estimated_total_tokens,
                admitted_at=now,
                enqueued_at=time.monotonic(),
                future=future,
            )
            accepted = await services.scheduler.enqueue(job)
            if not accepted:
                services.kv_tracker.release(request_id=request_id)
                services.rate_limiter.refund(
                    tenant_id=request.tenant_id, amount=estimated_total_tokens
                )
                services.telemetry.set_kv_utilization(services.kv_tracker.utilization_ratio)
                services.telemetry.record_request_outcome(
                    tenant_id=request.tenant_id,
                    result="rejected",
                    reason="queue_full",
                )
                raise HTTPException(status_code=429, detail="scheduler queue is full")

            services.telemetry.record_request_outcome(
                tenant_id=request.tenant_id,
                result="accepted",
                reason="accepted",
            )

            try:
                result = await asyncio.wait_for(
                    future,
                    timeout=services.config.generation_timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                services.telemetry.record_request_outcome(
                    tenant_id=request.tenant_id,
                    result="rejected",
                    reason="timeout",
                )
                raise HTTPException(status_code=504, detail="generation timeout") from exc

            return GenerateResponse(
                request_id=result.request_id,
                tenant_id=result.tenant_id,
                adapter_id=result.adapter_id,
                output=result.output,
                prompt_tokens=prompt_tokens,
                original_prompt_tokens=context_result.original_prompt_tokens,
                effective_prompt_tokens=prompt_tokens,
                prompt_truncated=context_result.prompt_truncated,
                completion_tokens=result.completion_tokens,
                total_tokens=prompt_tokens + result.completion_tokens,
                queue_time_seconds=result.queue_time_seconds,
                ttft_seconds=result.ttft_seconds,
                avg_tpot_seconds=result.avg_tpot_seconds,
                total_time_seconds=result.total_time_seconds,
            )
        finally:
            await services.request_registry.release(request_id)

    @app.get("/metrics")
    async def metrics() -> Response:
        body, content_type = Telemetry.scrape()
        return Response(content=body, media_type=content_type)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        services: Services = app.state.services
        return HealthResponse(
            status="ok",
            queue_depth=services.scheduler.queue_depth,
            active_sequences=services.scheduler.active_count,
            kv_cache_utilization_ratio=services.kv_tracker.utilization_ratio,
        )

    return app
