# Metric Contract

## Counters

- `gateway_requests_total{tenant_id,result,reason}`
- `scheduler_ticks_total`
- `tokens_generated_total{tenant_id}`

## Gauges

- `kv_cache_utilization_ratio`
- `queue_depth`
- `active_sequences`

## Histograms

- `request_ttft_seconds{tenant_id}`
- `request_tpot_seconds{tenant_id}`
- `queue_wait_seconds{tenant_id}`

## Label Constraints

- Allowed labels: `tenant_id`, `adapter_id`, `result`, `reason`.
- Do not include request IDs or prompt hashes.
