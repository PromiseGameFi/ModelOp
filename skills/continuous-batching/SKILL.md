---
name: continuous-batching
description: Design and implement a continuous batching scheduler for autoregressive inference, including queue policy, slot replacement, token-step iteration, and fairness across tenants. Use when building or modifying scheduler loops, batch state machines, queue discipline, or simulation logic for throughput and latency analysis.
---

# Continuous Batching

Implement scheduler changes with this invariant-first flow:

1. Define slot and queue invariants before editing code.
2. Keep token-step iteration monotonic (one decode step per active slot per tick).
3. Refill freed slots immediately from waiting queue according to policy.
4. Recompute pressure and fairness after every tick.
5. Emit batch-level telemetry for queue depth, active slots, and per-step work.

## Invariants

- Never exceed configured max active sequences.
- Never admit a request with estimated tokens above remaining budget.
- Never starve low-volume tenants indefinitely.
- Remove finished sequence state in the same tick that emits EOS.

## References

- Read [state-machine.md](references/state-machine.md) for lifecycle transitions.
- Read [scheduling-policies.md](references/scheduling-policies.md) for FIFO vs weighted fairness tradeoffs.
- Use `scripts/simulate_batch.py` for quick iteration simulations.

## Definition of Done

- Scheduler replaces finished requests without waiting for full-batch completion.
- Queue wait time and TTFT improve under mixed prompt lengths.
- Unit tests cover admission, replacement, and EOS cleanup edge cases.
