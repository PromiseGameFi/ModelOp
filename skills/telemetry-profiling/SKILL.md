---
name: telemetry-profiling
description: Define and implement LLM-serving observability, including TTFT, TPOT, queue time, KV-cache utilization, and rejection reason telemetry. Use when instrumenting gateway/scheduler code paths, creating Prometheus metrics, or generating Grafana dashboards and load-test analysis artifacts.
---

# Telemetry Profiling

Instrument every request lifecycle stage:

1. Measure queue wait from enqueue to first decode step.
2. Measure TTFT from admission to first output token.
3. Measure TPOT from token 2..N generation deltas.
4. Track KV-cache utilization and active sequence counts per tick.
5. Record rejection reason counters (`rate_limit`, `kv_pressure`, `queue_full`).

## Metric Rules

- Keep metric names stable and lowercase snake case.
- Keep labels low cardinality (`tenant_id`, `adapter_id`, `result`).
- Avoid per-request labels in Prometheus metrics.
- Export summary and histogram forms for latency where needed.

## References

- Read [metric-contract.md](references/metric-contract.md) before adding or renaming metrics.
- Read [grafana-layout.md](references/grafana-layout.md) before editing dashboard JSON.

## Definition of Done

- Metrics endpoint is scrape-ready.
- Dashboard separates TTFT and TPOT trends by tenant.
- Load-test report references metric evidence for bottleneck claims.
