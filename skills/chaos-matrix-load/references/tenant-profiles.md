# Tenant Profiles

## Tenant A: Long-Context Analytics

- Prompt tokens: 1200-4000
- Max new tokens: 200-800
- Request rate: low-medium
- Behavior: heavy KV pressure

## Tenant B: Chat UX

- Prompt tokens: 20-300
- Max new tokens: 32-256
- Request rate: high
- Behavior: queue pressure, latency sensitive

## Tenant C: Batch Summaries (Optional)

- Prompt tokens: 500-1200
- Max new tokens: 100-400
- Request rate: bursty
- Behavior: mixed pressure profile
