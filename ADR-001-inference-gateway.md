# ADR-001: Multi-Tenant Inference Gateway MVP

- Status: accepted
- Date: 2026-02-27

## Context

The system must serve mixed multi-tenant workloads where request cost varies by token volume, not request count. Under overload, failure mode must be controlled shedding instead of OOM or cascading latency.

## Decision

Build a gateway + scheduler simulation with:

1. Tenant token buckets using estimated total tokens.
2. KV-pressure admission gate using projected allocation ratio.
3. Continuous batching scheduler with per-tick slot refill.
4. Prometheus metrics for TTFT, TPOT, queue wait, queue depth, active sequences, KV utilization, and rejection reasons.

## KV Memory Model

Use a conservative admission estimate:

`kv_bytes ~= estimated_total_tokens * kv_bytes_per_token`

Where `kv_bytes_per_token` is calibrated experimentally. The gateway reserves projected bytes on admission and releases on completion/abort.

Projected pressure:

`pressure = (active_kv_bytes + request_kv_bytes) / kv_budget_bytes`

Reject request with HTTP 429 when `pressure >= shed_threshold`.

## Consequences

Positive:

- Stable behavior under burst traffic.
- Clear separation of ingress control-plane and decode scheduler.
- Observable bottleneck signatures.

Tradeoffs:

- Token estimate is approximate.
- Mock decode loop represents scheduling mechanics but not GPU kernels.
- Static per-tenant policy defaults need runtime config for production.
