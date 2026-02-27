---
name: inference-gateway
description: Build and evolve the multi-tenant inference ingress layer, including request normalization, tenant-aware adapter routing, token-aware admission control, and overload shedding decisions. Use when implementing or refactoring API handlers, rate-limit logic, capacity checks, queue handoff contracts, or gateway-level telemetry for LLM serving systems.
---

# Inference Gateway

Implement gateway logic in this order:

1. Validate and normalize request input.
2. Estimate prompt + generation token budget before admission.
3. Apply tenant token bucket and global concurrency checks.
4. Compute KV-cache pressure and shed early when threshold is exceeded.
5. Build scheduler job with immutable metadata (`tenant_id`, `adapter_id`, `request_id`, token budget).
6. Emit gateway metrics for accepted and rejected traffic.

## Operational Rules

- Prefer deterministic rejection at ingress over best-effort processing.
- Return `429 Too Many Requests` for rate-limit or pressure rejection.
- Return `503 Service Unavailable` for internal scheduler unavailable states.
- Preserve idempotent request identifiers for trace stitching.
- Keep adapter selection pure (no side effects in resolver).

## Contracts

- Read [request-contract.md](references/request-contract.md) before changing API schema.
- Read [capacity-math.md](references/capacity-math.md) before changing shedding thresholds.
- Use `scripts/token_estimator.py` to sanity-check rough token estimates for prompt text.

## Definition of Done

- Gateway rejects overload without crashing scheduler or worker loop.
- Tenant-specific limits are configurable and test-covered.
- Metrics include queue admission outcome and rejection reason.
