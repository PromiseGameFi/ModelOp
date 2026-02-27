# ModelOp MVP

Multi-tenant inference gateway prototype with:

- token-aware admission control
- KV-pressure load shedding
- adapter-aware routing metadata
- continuous batching scheduler simulation
- Prometheus telemetry for TTFT/TPOT/queue pressure

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn modelop.main:app --host 0.0.0.0 --port 8000
```

## Endpoints

- `POST /v1/generate`
- `GET /metrics`
- `GET /health`

## Load test

```bash
python scripts/chaos_matrix.py --base-url http://127.0.0.1:8000 --scenario skewed-burst
```

## Artifacts

- ADR: `ADR-001-inference-gateway.md`
- Grafana dashboard JSON: `dashboards/grafana-inference-gateway.json`
- Load test post-mortem template: `LOAD_TEST_POSTMORTEM.md`
