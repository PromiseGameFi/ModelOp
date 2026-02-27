from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    prompt: str = Field(min_length=1)
    max_new_tokens: int = Field(default=128, ge=1, le=4096)
    adapter_id: str | None = Field(default=None, max_length=128)
    request_id: str | None = Field(default=None, max_length=128)


class GenerateResponse(BaseModel):
    request_id: str
    tenant_id: str
    adapter_id: str
    output: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    queue_time_seconds: float
    ttft_seconds: float
    avg_tpot_seconds: float
    total_time_seconds: float


class HealthResponse(BaseModel):
    status: str
    queue_depth: int
    active_sequences: int
    kv_cache_utilization_ratio: float
