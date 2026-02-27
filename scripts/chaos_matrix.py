#!/usr/bin/env python3
"""Multi-tenant chaos/load runner for the gateway MVP."""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class TenantProfile:
    tenant_id: str
    min_prompt_tokens: int
    max_prompt_tokens: int
    min_new_tokens: int
    max_new_tokens: int
    weight: int


@dataclass
class LoadStats:
    sent: int = 0
    succeeded: int = 0
    rejected_429: int = 0
    failed: int = 0
    latencies: list[float] = None
    ttft_values: list[float] = None
    tpot_values: list[float] = None

    def __post_init__(self) -> None:
        self.latencies = []
        self.ttft_values = []
        self.tpot_values = []

    def merge(self, other: "LoadStats") -> None:
        self.sent += other.sent
        self.succeeded += other.succeeded
        self.rejected_429 += other.rejected_429
        self.failed += other.failed
        self.latencies.extend(other.latencies)
        self.ttft_values.extend(other.ttft_values)
        self.tpot_values.extend(other.tpot_values)


SCENARIOS: dict[str, list[TenantProfile]] = {
    "baseline": [
        TenantProfile("tenant-a", 80, 240, 24, 64, 1),
        TenantProfile("tenant-b", 40, 160, 24, 64, 1),
    ],
    "skewed-burst": [
        TenantProfile("tenant-a", 1200, 2800, 256, 512, 1),
        TenantProfile("tenant-b", 40, 220, 32, 128, 4),
    ],
}


def weighted_choice(rng: random.Random, profiles: list[TenantProfile]) -> TenantProfile:
    total = sum(profile.weight for profile in profiles)
    pick = rng.randint(1, total)
    cursor = 0
    for profile in profiles:
        cursor += profile.weight
        if pick <= cursor:
            return profile
    return profiles[-1]


def make_prompt(token_count: int) -> str:
    return " ".join(["token"] * token_count)


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * quantile)))
    return ordered[index]


async def worker(
    worker_id: int,
    base_url: str,
    scenario: str,
    duration_seconds: int,
    target_rps: float,
) -> LoadStats:
    rng = random.Random(worker_id * 7919 + int(time.time()))
    profiles = SCENARIOS[scenario]
    stats = LoadStats()
    started = time.monotonic()

    async with httpx.AsyncClient(timeout=60.0) as client:
        while time.monotonic() - started < duration_seconds:
            profile = weighted_choice(rng, profiles)
            prompt_tokens = rng.randint(profile.min_prompt_tokens, profile.max_prompt_tokens)
            max_new_tokens = rng.randint(profile.min_new_tokens, profile.max_new_tokens)
            payload = {
                "tenant_id": profile.tenant_id,
                "prompt": make_prompt(prompt_tokens),
                "max_new_tokens": max_new_tokens,
            }

            stats.sent += 1
            req_started = time.monotonic()
            try:
                response = await client.post(f"{base_url}/v1/generate", json=payload)
                latency = time.monotonic() - req_started
                stats.latencies.append(latency)
                if response.status_code == 200:
                    body = response.json()
                    stats.succeeded += 1
                    stats.ttft_values.append(float(body.get("ttft_seconds", 0.0)))
                    stats.tpot_values.append(float(body.get("avg_tpot_seconds", 0.0)))
                elif response.status_code == 429:
                    stats.rejected_429 += 1
                else:
                    stats.failed += 1
            except Exception:
                stats.failed += 1

            if target_rps > 0:
                sleep_time = rng.expovariate(target_rps)
                await asyncio.sleep(min(1.0, sleep_time))

    return stats


async def run_load(
    base_url: str,
    scenario: str,
    workers: int,
    duration_seconds: int,
    target_rps: float,
) -> LoadStats:
    tasks = [
        asyncio.create_task(
            worker(
                worker_id=i,
                base_url=base_url,
                scenario=scenario,
                duration_seconds=duration_seconds,
                target_rps=target_rps,
            )
        )
        for i in range(workers)
    ]
    results = await asyncio.gather(*tasks)

    merged = LoadStats()
    for result in results:
        merged.merge(result)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multi-tenant chaos load against gateway.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="skewed-burst")
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--duration-seconds", type=int, default=60)
    parser.add_argument(
        "--target-rps",
        type=float,
        default=2.0,
        help="Approximate request rate per worker",
    )
    args = parser.parse_args()

    stats = asyncio.run(
        run_load(
            base_url=args.base_url,
            scenario=args.scenario,
            workers=args.workers,
            duration_seconds=args.duration_seconds,
            target_rps=args.target_rps,
        )
    )

    report = {
        "scenario": args.scenario,
        "workers": args.workers,
        "duration_seconds": args.duration_seconds,
        "sent": stats.sent,
        "succeeded": stats.succeeded,
        "rejected_429": stats.rejected_429,
        "failed": stats.failed,
        "success_rate": (stats.succeeded / stats.sent) if stats.sent else 0.0,
        "rejection_rate": (stats.rejected_429 / stats.sent) if stats.sent else 0.0,
        "latency_p50_ms": percentile(stats.latencies, 0.50) * 1000,
        "latency_p95_ms": percentile(stats.latencies, 0.95) * 1000,
        "ttft_p95_ms": percentile(stats.ttft_values, 0.95) * 1000,
        "tpot_avg_ms": statistics.mean(stats.tpot_values) * 1000 if stats.tpot_values else 0.0,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
