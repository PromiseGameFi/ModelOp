from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TenantPolicy:
    rate_tokens_per_sec: float
    burst_tokens: float
    default_adapter_id: str


DEFAULT_TENANT_POLICIES: dict[str, TenantPolicy] = {
    "tenant-a": TenantPolicy(
        rate_tokens_per_sec=4000.0,
        burst_tokens=8000.0,
        default_adapter_id="adapter-analytics-v1",
    ),
    "tenant-b": TenantPolicy(
        rate_tokens_per_sec=2500.0,
        burst_tokens=5000.0,
        default_adapter_id="adapter-chat-v1",
    ),
}


@dataclass
class GatewayConfig:
    max_request_tokens: int = 8192
    generation_timeout_seconds: float = 120.0

    shed_threshold: float = 0.90
    kv_budget_bytes: int = 8 * 1024 * 1024 * 1024
    kv_bytes_per_token: int = 16_384

    scheduler_max_active_sequences: int = 16
    scheduler_queue_capacity: int = 1024
    scheduler_decode_step_seconds: float = 0.02
    scheduler_idle_sleep_seconds: float = 0.005

    tenant_policies: dict[str, TenantPolicy] = field(
        default_factory=lambda: DEFAULT_TENANT_POLICIES.copy()
    )
    default_tenant_policy: TenantPolicy = TenantPolicy(
        rate_tokens_per_sec=1500.0,
        burst_tokens=3000.0,
        default_adapter_id="adapter-default",
    )

    def policy_for(self, tenant_id: str) -> TenantPolicy:
        return self.tenant_policies.get(tenant_id, self.default_tenant_policy)

