from __future__ import annotations

import time
from dataclasses import dataclass

from modelop.config import GatewayConfig, TenantPolicy


@dataclass
class TokenBucket:
    rate_tokens_per_sec: float
    burst_tokens: float
    tokens: float
    last_refill_ts: float

    @classmethod
    def from_policy(cls, policy: TenantPolicy, now: float) -> "TokenBucket":
        return cls(
            rate_tokens_per_sec=policy.rate_tokens_per_sec,
            burst_tokens=policy.burst_tokens,
            tokens=policy.burst_tokens,
            last_refill_ts=now,
        )

    def _refill(self, now: float) -> None:
        elapsed = max(0.0, now - self.last_refill_ts)
        self.tokens = min(self.burst_tokens, self.tokens + elapsed * self.rate_tokens_per_sec)
        self.last_refill_ts = now

    def try_consume(self, amount: float, now: float) -> bool:
        if amount <= 0:
            return True
        self._refill(now)
        if self.tokens < amount:
            return False
        self.tokens -= amount
        return True

    def refund(self, amount: float) -> None:
        if amount <= 0:
            return
        self.tokens = min(self.burst_tokens, self.tokens + amount)


class TokenRateLimiter:
    def __init__(self, config: GatewayConfig) -> None:
        self._config = config
        self._buckets: dict[str, TokenBucket] = {}

    def _bucket_for(self, tenant_id: str, now: float) -> TokenBucket:
        bucket = self._buckets.get(tenant_id)
        if bucket is None:
            policy = self._config.policy_for(tenant_id)
            bucket = TokenBucket.from_policy(policy, now=now)
            self._buckets[tenant_id] = bucket
        return bucket

    def try_consume(self, tenant_id: str, amount: int, now: float | None = None) -> bool:
        ts = now if now is not None else time.monotonic()
        return self._bucket_for(tenant_id, now=ts).try_consume(amount=amount, now=ts)

    def refund(self, tenant_id: str, amount: int) -> None:
        bucket = self._buckets.get(tenant_id)
        if bucket is None:
            return
        bucket.refund(amount=amount)
