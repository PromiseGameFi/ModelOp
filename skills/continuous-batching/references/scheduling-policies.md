# Scheduling Policies

## FIFO

- Lowest implementation complexity.
- Good for predictable single-tenant latency.
- Risk: tenant starvation under long-running prompts.

## Weighted Fair Queueing (Tenant Weight)

- Maintain per-tenant queue.
- Select next tenant by weighted deficit counters.
- Better fairness under skewed traffic.

## Recommended Default

- Use FIFO for initial MVP.
- Keep policy abstraction so weighted fairness can be enabled later.
