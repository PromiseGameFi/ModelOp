# ModelOp MVP

Multi-tenant inference gateway prototype with:

- token-aware admission control
- context-window-aware prompt compaction (head/tail truncation)
- KV-pressure load shedding
- adapter-aware routing metadata
- continuous batching scheduler simulation
- concurrent in-flight request ID uniqueness enforcement
- Prometheus telemetry for TTFT/TPOT/queue pressure

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn modelop.main:app --host 0.0.0.0 --port 8000
```

If your environment is offline and cannot install new packages, run directly with:

```bash
PYTHONPATH=src uvicorn modelop.main:app --host 0.0.0.0 --port 8000
```

The app now falls back to noop telemetry export when `prometheus_client` is unavailable.

## Tests

Primary:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Optional (if `pytest` is installed):

```bash
PYTHONPATH=src pytest -q
```

## Endpoints

- `POST /v1/generate`
- `GET /metrics`
- `GET /health`

## What This Demonstrates

Patterns used by large AI serving systems:

- Token/content window optimization:
  Requests reserve output tokens first, then compact over-budget prompts to fit the model window while preserving early and recent context.
- Concurrent traffic management:
  Tenant token buckets, queueing, and continuous batching keep throughput stable under simultaneous requests.
- Request uniqueness under concurrency:
  In-flight `request_id` registry rejects duplicate IDs (`409`) if the same ID is already running.

### Example request

```json
{
  "tenant_id": "tenant-a",
  "request_id": "req-12345",
  "prompt": "long prompt ...",
  "max_new_tokens": 256
}
```

Response includes:

- `prompt_truncated`
- `original_prompt_tokens`
- `effective_prompt_tokens`

## Load test

```bash
python scripts/chaos_matrix.py --base-url http://127.0.0.1:8000 --scenario skewed-burst
```

## Artifacts

- ADR: `ADR-001-inference-gateway.md`
- Grafana dashboard JSON: `dashboards/grafana-inference-gateway.json`
- Load test post-mortem template: `LOAD_TEST_POSTMORTEM.md`
