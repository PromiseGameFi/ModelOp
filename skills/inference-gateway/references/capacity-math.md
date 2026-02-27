# Capacity Math Notes

## Rough KV Cache Estimate

Use a conservative estimate for admission checks:

`kv_bytes ~= seq_tokens * num_layers * hidden_size * 2 (k+v) * bytes_per_elem`

Apply headroom factor:

`effective_kv_bytes = kv_bytes * 1.15`

## Shedding Policy

- Compute `pressure = active_kv_bytes / kv_budget_bytes`.
- Shed new requests when `pressure >= shed_threshold` (default `0.90`).
- Start warning telemetry when `pressure >= 0.80`.

## Token Budget Gate

- Reject if `estimated_prompt_tokens + max_new_tokens > max_request_tokens`.
- Reject if tenant token bucket has insufficient tokens.
