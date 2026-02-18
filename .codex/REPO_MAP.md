# REPO_MAP.md
Authoritative for: repository structure and ownership boundaries.

## As-Is (Current Implemented Structure)
### Core app paths
- `api/main.py`: API and freshness/status endpoints.
- `scripts/pipeline_worker.py`: orchestrator + shared worker runtime glue.
- `workers/ingest.py`: ingest/downsample domain logic.
- `workers/predict.py`: prediction/health domain logic.
- `workers/export.py`: static export/manifest domain logic.
- `scripts/worker_ingest.py`, `scripts/worker_publish.py`, `scripts/worker_predict.py`, `scripts/worker_export.py`: role-specific worker entrypoints.
- `admin/app.py`: Streamlit dashboard for monitoring and visualization.

### Infra and runtime
- `docker-compose.yml`: service topology and runtime wiring.
- `docker/`: Dockerfiles and per-service requirements.
- `nginx/default.conf`: static artifact serving config.
- `prometheus/prometheus.yml`: monitoring scrape config.
- `.github/workflows/deploy.yml`: build/push/deploy pipeline.

### Data/artifact paths
- `models/`: serialized model artifacts.
- `static_data/` (runtime mount): generated history/prediction JSON artifacts.
- `tests/`: unit and load-test scripts.
- `docs/`: living plan, task board, decisions, debt register, handoff.

## Current Data Flow
`ccxt/binance -> worker-ingest -> InfluxDB -> worker-publish -> static JSON -> nginx/static + fastapi -> streamlit`

## To-Be (Planned, Not Implemented Yet)
Planned modular structure may include:
- `workers/`, `ingest/`, `model/`, `export/`, `gatekeeper/`, `utils/`, `config/`

This section is directional only.
Do not assume these paths exist unless explicitly created in the current task.

## Boundary Rules
- Keep ingest/model/export/serving concerns separated.
- Treat served static artifacts as validated outputs, not ad-hoc scratch files.
- Any boundary-crossing change requires risk + verification updates.
