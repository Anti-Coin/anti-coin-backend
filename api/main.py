from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
from contextlib import asynccontextmanager
import pandas as pd
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from utils.logger import get_logger
from utils.config import (
    FRESHNESS_THRESHOLDS,
    FRESHNESS_HARD_THRESHOLDS,
)
from utils.prediction_status import evaluate_prediction_status
from utils.prediction_health_store import build_prediction_health_status
from utils.status_consistency import (
    apply_influx_json_consistency,
    get_latest_ohlcv_timestamp,
)

logger = get_logger(__name__)

# 환경 변수
INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET")

# 정적 파일 경로 (Docker compose에서 /app/static_data로 마운트 됨)
BASE_DIR = Path("/app")
STATIC_DIR = BASE_DIR / "static_data"
PREDICTION_HEALTH_FILE = STATIC_DIR / "prediction_health.json"

client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    logger.info("Connecting to InfluxDB...")
    client = InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG,
        timeout=10000,  # 타임아웃 설정
        retries=3,  # 연결 끊김 대비 재시도
    )
    yield

    logger.info("Closing InfluxDB connection...")
    client.close()


app = FastAPI(title="Coin Predict API", version="1.0.0", lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP에선 편의상 모두 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 모델 저장소
loaded_models = {}


def _load_prediction_health(symbol: str, timeframe: str) -> dict:
    """
    worker가 기록한 prediction health 상태를 읽어 `/status` 응답에 합친다.

    원칙:
    - 파일/포맷 오류는 조용히 무시하지 않고 degraded=True로 승격한다.
    - 엔트리가 없으면 기본값(degraded=False)으로 처리한다.
    """
    return build_prediction_health_status(
        PREDICTION_HEALTH_FILE,
        symbol,
        timeframe,
        logger=logger,
    )


def _resolve_influx_query_api():
    """Return query_api if Influx client is ready; otherwise None."""
    if client is None:
        return None

    try:
        return client.query_api()
    except Exception as e:
        logger.error(f"Failed to resolve Influx query API: {e}")
        return None


# InfluxDB 쿼리 헬퍼 함수
def query_influx(symbol: str, measurement: str, days: int = 30):
    query_api = client.query_api()

    # 최근 N일 데이터 조회 + Pivot으로 테이블 형태 변환
    # range stop: 2d -> 미래 데이터도 조회하기 위해 미래 시간까지 범위를 엶.
    query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -{days}d, stop: 2d)
      |> filter(fn: (r) => r["_measurement"] == "{measurement}")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: false)
    """

    try:
        df = query_api.query_data_frame(query)
    except Exception as e:
        logger.error(f"DB Query Error: {e}")
        return None

    if isinstance(df, list) or df.empty:
        return None

    # InfluxDB 리턴값 정리 ('_time' -> 'timestamp')
    df.rename(columns={"_time": "timestamp"}, inplace=True)

    return df


@app.get("/history/{symbol:path}")
def get_history(symbol: str):
    """
    Sunset tombstone endpoint.

    Why:
    - 사용자 데이터 플레인은 static JSON(SSG) + `/status`로 고정되었다.
    - legacy fallback 호출을 조용히 성공시키지 않고, 명시적으로 종료를 알린다.
    """
    safe_symbol = symbol.replace("/", "_")
    raise HTTPException(
        status_code=410,
        detail=(
            "Endpoint sunset: /history is no longer served. "
            f"Use /static/history_{safe_symbol}_<timeframe>.json and "
            f"/status/{symbol}."
        ),
    )


@app.get("/predict/{symbol:path}")
def predict_price(symbol: str):
    """
    Sunset tombstone endpoint.

    Why:
    - 사용자 데이터 플레인은 static JSON(SSG) + `/status`로 고정되었다.
    - legacy fallback 호출을 조용히 성공시키지 않고, 명시적으로 종료를 알린다.
    """
    safe_symbol = symbol.replace("/", "_")
    raise HTTPException(
        status_code=410,
        detail=(
            "Endpoint sunset: /predict is no longer served. "
            f"Use /static/prediction_{safe_symbol}_<timeframe>.json and "
            f"/status/{symbol}."
        ),
    )


@app.get("/status/{symbol:path}")
def check_status(symbol: str, timeframe: str = "1h"):
    """
    정적 파일의 신선도(Freshness) 검사
    - 파일이 없거나, 너무 오래되었으면 503에러 반환
    """
    try:
        base_snapshot = evaluate_prediction_status(
            symbol=symbol,
            timeframe=timeframe,
            now=datetime.now(timezone.utc),
            static_dir=STATIC_DIR,
            soft_thresholds=FRESHNESS_THRESHOLDS,
            hard_thresholds=FRESHNESS_HARD_THRESHOLDS,
        )
        latest_ohlcv_ts = get_latest_ohlcv_timestamp(
            _resolve_influx_query_api(),
            symbol,
            timeframe,
            INFLUXDB_BUCKET,
        )
        snapshot = apply_influx_json_consistency(base_snapshot, latest_ohlcv_ts)
        if snapshot.status != base_snapshot.status:
            logger.warning(
                "[Status API] Consistency override: "
                f"{symbol} {timeframe} {base_snapshot.status}->{snapshot.status} "
                f"detail={snapshot.detail}"
            )

        if snapshot.status == "missing":
            raise HTTPException(status_code=503, detail="Not initialized yet.")

        if snapshot.status == "corrupt":
            if snapshot.error_code == "json_decode_error":
                raise HTTPException(
                    status_code=503, detail="Data corruption detected"
                )
            raise HTTPException(status_code=503, detail="Invalid data format")

        if snapshot.status == "hard_stale":
            raise HTTPException(
                status_code=503,
                detail="Data is stale beyond hard limit. "
                f"Last updated: {snapshot.updated_at}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status Check Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    response = {
        "status": snapshot.status,
        "updated_at": snapshot.updated_at,
        "age_minutes": snapshot.age_minutes,
        "threshold_minutes": {
            "soft": snapshot.soft_limit_minutes,
            "hard": snapshot.hard_limit_minutes,
        },
    }
    # freshness 상태와 독립적으로 prediction 파이프라인 상태(degraded)를 별도 노출한다.
    health = _load_prediction_health(symbol, timeframe)
    response["degraded"] = health["degraded"]
    response["last_prediction_success_at"] = health["last_success_at"]
    response["last_prediction_failure_at"] = health["last_failure_at"]
    response["prediction_failure_count"] = health["consecutive_failures"]
    if health["degraded"]:
        response["degraded_reason"] = (
            health["last_error"] or "prediction_pipeline_degraded"
        )
    if snapshot.status == "stale":
        response["warning"] = "Data is stale but within soft-stale tolerance."
    return response


@app.get("/")
def health_check():
    return {"status": "ok", "models_loaded": list(loaded_models.keys())}
