# Grafana Layout Guidance

## Dashboard Sections

1. Admission overview:
   - admitted vs shed requests per second.
2. Latency decomposition:
   - TTFT percentile panel.
   - TPOT percentile panel.
3. Capacity pressure:
   - KV-cache utilization ratio.
   - queue depth and active sequences.
4. Tenant split:
   - top tenants by volume and rejection rate.

## Panel Rules

- Keep y-axis units explicit.
- Overlay only related metrics.
- Use same tenant filters across panels.
