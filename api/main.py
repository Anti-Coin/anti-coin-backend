from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
from contextlib import asynccontextmanager
import pandas as pd
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from utils.logger import get_logger
from utils.config import FRESHNESS_THRESHOLDS, FRESHNESS_HARD_THRESHOLDS
from utils.prediction_status import evaluate_prediction_status

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


def _prediction_health_key(symbol: str, timeframe: str) -> str:
    """prediction health 파일에서 심볼/타임프레임 키를 구성."""
    return f"{symbol}|{timeframe}"


def _load_prediction_health(symbol: str, timeframe: str) -> dict:
    """
    worker가 기록한 prediction health 상태를 읽어 `/status` 응답에 합친다.

    원칙:
    - 파일/포맷 오류는 조용히 무시하지 않고 degraded=True로 승격한다.
    - 엔트리가 없으면 기본값(degraded=False)으로 처리한다.
    """
    default = {
        "degraded": False,
        "last_success_at": None,
        "last_failure_at": None,
        "last_error": None,
        "consecutive_failures": 0,
    }
    # health 파일이 없으면 아직 초기화 전으로 보고 기본값을 반환한다.
    if not PREDICTION_HEALTH_FILE.exists():
        return default

    try:
        with open(PREDICTION_HEALTH_FILE, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        # 읽기/파싱 실패는 운영 신호 상 "건강 상태를 신뢰할 수 없음"으로 취급한다.
        logger.error(f"Prediction health read failed: {e}")
        fallback = default.copy()
        fallback["degraded"] = True
        fallback["last_error"] = "prediction_health_read_error"
        return fallback

    entries = payload.get("entries")
    if not isinstance(entries, dict):
        # 스키마 파손도 읽기 실패와 동일하게 degraded로 노출한다.
        logger.error("Prediction health format invalid: entries is not a dict.")
        fallback = default.copy()
        fallback["degraded"] = True
        fallback["last_error"] = "prediction_health_format_error"
        return fallback

    entry = entries.get(_prediction_health_key(symbol, timeframe))
    if not isinstance(entry, dict):
        # 해당 심볼 엔트리가 아직 생성되지 않은 정상 케이스.
        return default

    raw_failures = entry.get("consecutive_failures", 0)
    try:
        failures = int(raw_failures)
    except (TypeError, ValueError):
        failures = 0

    return {
        "degraded": bool(entry.get("degraded", False)),
        "last_success_at": entry.get("last_success_at"),
        "last_failure_at": entry.get("last_failure_at"),
        "last_error": entry.get("last_error"),
        "consecutive_failures": failures,
    }


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
        snapshot = evaluate_prediction_status(
            symbol=symbol,
            timeframe=timeframe,
            now=datetime.now(timezone.utc),
            static_dir=STATIC_DIR,
            soft_thresholds=FRESHNESS_THRESHOLDS,
            hard_thresholds=FRESHNESS_HARD_THRESHOLDS,
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
