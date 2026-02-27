import unittest
import threading
import time

from fastapi.testclient import TestClient

from modelop.config import GatewayConfig, TenantPolicy
from modelop.gateway import create_app


class GatewayAdmissionTests(unittest.TestCase):
    def test_rejects_oversized_request_with_400(self) -> None:
        app = create_app(
            GatewayConfig(
                max_request_tokens=20,
                enable_prompt_truncation=False,
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

    def test_truncates_prompt_to_fit_context_window(self) -> None:
        app = create_app(
            GatewayConfig(
                max_request_tokens=20,
                enable_prompt_truncation=True,
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
            "max_new_tokens": 5,  # prompt budget is 15, requires truncation
        }

        with TestClient(app) as client:
            response = client.post("/v1/generate", json=payload)

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["prompt_truncated"])
        self.assertGreater(body["original_prompt_tokens"], body["effective_prompt_tokens"])
        self.assertLessEqual(body["effective_prompt_tokens"] + payload["max_new_tokens"], 20)

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

    def test_rejects_duplicate_request_id_with_409(self) -> None:
        app = create_app(
            GatewayConfig(
                scheduler_decode_step_seconds=0.02,
                tenant_policies={
                    "tenant-u": TenantPolicy(
                        rate_tokens_per_sec=10_000.0,
                        burst_tokens=10_000.0,
                        default_adapter_id="adapter-u",
                    )
                },
            )
        )
        payload = {
            "tenant_id": "tenant-u",
            "request_id": "dup-request-1",
            "prompt": "hello world " * 20,
            "max_new_tokens": 40,
        }

        first_status: list[int] = []

        with TestClient(app) as client:
            def run_first() -> None:
                first_status.append(client.post("/v1/generate", json=payload).status_code)

            first_thread = threading.Thread(target=run_first)
            first_thread.start()
            time.sleep(0.05)

            second = client.post("/v1/generate", json=payload)
            first_thread.join()

        self.assertEqual(first_status[0], 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn("already in flight", second.json()["detail"])
