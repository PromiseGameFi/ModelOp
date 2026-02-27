import unittest

from fastapi.testclient import TestClient

from modelop.config import GatewayConfig, TenantPolicy
from modelop.gateway import create_app


class GatewayAdmissionTests(unittest.TestCase):
    def test_rejects_oversized_request_with_400(self) -> None:
        app = create_app(
            GatewayConfig(
                max_request_tokens=20,
                tenant_policies={
                    "tenant-a": TenantPolicy(
                        rate_tokens_per_sec=10_000.0,
                        burst_tokens=10_000.0,
                        default_adapter_id="adapter-a",
                    )
                },
            )
        )
        payload = {
            "tenant_id": "tenant-a",
            "prompt": "x" * 80,  # ceil(80/4)=20 prompt tokens
            "max_new_tokens": 5,  # total 25 > max_request_tokens (20)
        }

        with TestClient(app) as client:
            response = client.post("/v1/generate", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("exceeds max_request_tokens=20", response.json()["detail"])

    def test_rejects_rate_limited_request_with_429(self) -> None:
        app = create_app(
            GatewayConfig(
                kv_budget_bytes=1_000_000_000,
                tenant_policies={
                    "tenant-r": TenantPolicy(
                        rate_tokens_per_sec=0.0,
                        burst_tokens=8.0,
                        default_adapter_id="adapter-r",
                    )
                },
            )
        )
        payload = {
            "tenant_id": "tenant-r",
            "prompt": "hello world",  # ceil(11/4)=3 prompt tokens
            "max_new_tokens": 2,  # total 5 tokens
        }

        with TestClient(app) as client:
            first = client.post("/v1/generate", json=payload)
            second = client.post("/v1/generate", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["detail"], "rate limit exceeded")

    def test_rejects_kv_pressure_with_429(self) -> None:
        app = create_app(
            GatewayConfig(
                kv_budget_bytes=10_000,
                kv_bytes_per_token=1_000,
                shed_threshold=0.50,
                tenant_policies={
                    "tenant-k": TenantPolicy(
                        rate_tokens_per_sec=10_000.0,
                        burst_tokens=10_000.0,
                        default_adapter_id="adapter-k",
                    )
                },
            )
        )
        payload = {
            "tenant_id": "tenant-k",
            "prompt": "x" * 44,  # ceil(44/4)=11 prompt tokens
            "max_new_tokens": 1,  # total 12 -> 12000 bytes, pressure 1.2 >= 0.5
        }

        with TestClient(app) as client:
            response = client.post("/v1/generate", json=payload)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(
            response.json()["detail"],
            "request shed due to KV-cache pressure threshold",
        )
