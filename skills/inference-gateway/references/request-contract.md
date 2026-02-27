# Gateway Request Contract

## Input Schema

- `tenant_id`: string, required, low-cardinality identifier.
- `adapter_id`: string, optional; defaults to tenant fallback adapter.
- `prompt`: string, required.
- `max_new_tokens`: int, required, `1..4096`.
- `request_id`: string, optional; generated if missing.

## Admission Output

- `accepted`: bool.
- `reason`: enum `accepted|rate_limit|kv_pressure|queue_full|invalid`.
- `estimated_prompt_tokens`: int.
- `estimated_total_tokens`: int.

## Queue Handoff Payload

- Preserve immutable fields: `request_id`, `tenant_id`, `adapter_id`.
- Include timing markers for `received_at` and `enqueued_at`.
- Include cost estimate fields for scheduler budgeting.
