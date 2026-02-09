# REPO_MAP.md
Authoritative for: repository structure and ownership boundaries.

## As-Is (Current Implemented Structure)
### Core app paths
- `api/main.py`: API and freshness/status endpoints.
- `scripts/pipeline_worker.py`: long-running ingest + prediction + static export worker.
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
- `tests/`: load-test script(s).

## Current Data Flow
`ccxt/binance -> worker -> InfluxDB + static JSON -> nginx/static + fastapi -> streamlit`

## To-Be (Planned, Not Implemented Yet)
Planned modular structure may include:
- `workers/`, `ingest/`, `model/`, `export/`, `gatekeeper/`, `utils/`, `config/`

This section is directional only.
Do not assume these paths exist unless explicitly created in the current task.

## Boundary Rules
- Keep ingest/model/export/serving concerns separated.
- Treat served static artifacts as validated outputs, not ad-hoc scratch files.
- Any boundary-crossing change requires risk + verification updates.
