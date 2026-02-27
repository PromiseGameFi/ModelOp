import unittest

from modelop.config import GatewayConfig, TenantPolicy
from modelop.rate_limit import TokenRateLimiter


class TokenRateLimiterTests(unittest.TestCase):
    def test_token_bucket_refill_and_refund(self) -> None:
        config = GatewayConfig(
            tenant_policies={
                "tenant-x": TenantPolicy(
                    rate_tokens_per_sec=100.0,
                    burst_tokens=200.0,
                    default_adapter_id="adapter-x",
                )
            }
        )
        limiter = TokenRateLimiter(config=config)

        self.assertTrue(limiter.try_consume("tenant-x", amount=200, now=0.0))
        self.assertFalse(limiter.try_consume("tenant-x", amount=1, now=0.0))

        self.assertTrue(limiter.try_consume("tenant-x", amount=50, now=0.5))
        self.assertFalse(limiter.try_consume("tenant-x", amount=1, now=0.5))

        limiter.refund("tenant-x", amount=25)
        self.assertTrue(limiter.try_consume("tenant-x", amount=25, now=0.5))
