"""
Worker configuration constants.

Why this module exists:
- pipeline_worker.py의 상수/설정값을 분리해 오케스트레이션 코드의 인지 부하를 줄인다.
- 상수 변경 시 영향 범위를 이 파일로 한정한다.

Note:
- pipeline_worker.py에서 이 모듈의 값을 import해 모듈 속성으로 재노출하므로,
  테스트 monkeypatch 경로(`scripts.pipeline_worker.*`)는 그대로 유효하다.
"""

import os
from pathlib import Path

from utils.config import INGEST_TIMEFRAMES, PRIMARY_TIMEFRAME, TARGET_SYMBOLS

# ── InfluxDB ──
INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET")

# ── Alerting ──
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# ── Paths ──
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
STATIC_DIR = BASE_DIR / "static_data"
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# ── Target / Timeframe ──
TARGET_COINS = TARGET_SYMBOLS
TIMEFRAMES = INGEST_TIMEFRAMES if INGEST_TIMEFRAMES else [PRIMARY_TIMEFRAME]
LOOKBACK_DAYS = 30  # 과거 30일치 데이터 유지
# PRIMARY_TIMEFRAME은 utils.config에서 가져오되, 여기서도 재노출한다.
# 이유: pipeline_worker 모듈 속성으로 테스트가 monkeypatch하기 때문이다.
PRIMARY_TIMEFRAME = PRIMARY_TIMEFRAME

# ── State file paths ──
INGEST_STATE_FILE = STATIC_DIR / "ingest_state.json"
PREDICTION_HEALTH_FILE = STATIC_DIR / "prediction_health.json"
MANIFEST_FILE = STATIC_DIR / "manifest.json"
DOWNSAMPLE_LINEAGE_FILE = STATIC_DIR / "downsample_lineage.json"
RUNTIME_METRICS_FILE = STATIC_DIR / "runtime_metrics.json"
SYMBOL_ACTIVATION_FILE = STATIC_DIR / "symbol_activation.json"
INGEST_WATERMARK_FILE = STATIC_DIR / "ingest_watermarks.json"
PREDICT_WATERMARK_FILE = STATIC_DIR / "predict_watermarks.json"
EXPORT_WATERMARK_FILE = STATIC_DIR / "export_watermarks.json"

# ── Prediction policy ──
PREDICTION_DISABLED_TIMEFRAMES = {
    value.strip()
    for value in os.getenv("PREDICTION_DISABLED_TIMEFRAMES", "1m").split(",")
    if value.strip()
}
SERVE_ALLOWED_STATUSES = {"fresh", "stale"}

# ── Retention / Disk guard ──
RETENTION_1M_DEFAULT_DAYS = 14
RETENTION_1M_MAX_DAYS = 30
DISK_WATERMARK_WARN_PERCENT = 70
DISK_WATERMARK_CRITICAL_PERCENT = 85
DISK_WATERMARK_BLOCK_PERCENT = 90
DISK_USAGE_PATH = Path(os.getenv("DISK_USAGE_PATH", "/"))
RETENTION_ENFORCE_INTERVAL_SECONDS = 60 * 60

# ── Downsample ──
DOWNSAMPLE_TARGET_TIMEFRAMES = {"1d", "1w", "1M"}
DOWNSAMPLE_SOURCE_TIMEFRAME = "1h"
DOWNSAMPLE_SOURCE_LOOKBACK_DAYS = 120

# ── Backfill ──
FULL_BACKFILL_TOLERANCE_HOURS = 1

# ── Cycle / Runtime metrics ──
CYCLE_TARGET_SECONDS = int(os.getenv("WORKER_CYCLE_SECONDS", "60"))
RUNTIME_METRICS_WINDOW_SIZE = int(os.getenv("RUNTIME_METRICS_WINDOW_SIZE", "240"))

# ── Coverage guard ──
LOOKBACK_MIN_ROWS_RATIO = float(os.getenv("LOOKBACK_MIN_ROWS_RATIO", "0.8"))

# ── Scheduler ──
WORKER_SCHEDULER_MODE = os.getenv("WORKER_SCHEDULER_MODE", "boundary").strip().lower()
VALID_WORKER_SCHEDULER_MODES = {"poll_loop", "boundary"}

# ── Worker role / mode ──
WORKER_EXECUTION_ROLE = os.getenv("WORKER_EXECUTION_ROLE", "all").strip().lower()
VALID_WORKER_EXECUTION_ROLES = {"all", "ingest", "predict_export"}
WORKER_PUBLISH_MODE = (
    os.getenv("WORKER_PUBLISH_MODE", "predict_and_export").strip().lower()
)
VALID_WORKER_PUBLISH_MODES = {
    "predict_and_export",
    "predict_only",
    "export_only",
}
