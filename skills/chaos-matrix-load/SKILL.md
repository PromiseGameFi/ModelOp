---
name: chaos-matrix-load
description: Build and run multi-tenant load and chaos experiments for LLM inference platforms, including skewed traffic mixes, burst events, and post-mortem report generation. Use when creating load generators, designing tenant profiles, validating shedding behavior, or analyzing breaking points from benchmark runs.
---

# Chaos Matrix Load

Run load testing in controlled phases:

1. Establish baseline profile with no burst events.
2. Introduce tenant skew (long prompts vs short chat prompts).
3. Introduce burst ramp and sustained plateau.
4. Capture admitted vs shed request rates and latency decomposition.
5. Publish post-mortem with bottleneck diagnosis and corrective actions.

## Scenario Rules

- Keep at least two tenants with materially different prompt distributions.
- Include one burst profile that exceeds configured safe throughput.
- Store run metadata with timestamp, git SHA, and config hash.
- Fail the run if metrics collection is unavailable.

## References

- Read [tenant-profiles.md](references/tenant-profiles.md) when adding or changing traffic mixes.
- Read [postmortem-template.md](references/postmortem-template.md) to format results consistently.
- Use `scripts/chaos_runner.py` as the base CLI for load scenarios.

## Definition of Done

- Load runner can reproduce deterministic scenario names and configs.
- Post-mortem includes explicit breaking point and stabilization evidence.
- Recommendations map directly to observed TTFT/TPOT/KV pressure trends.
