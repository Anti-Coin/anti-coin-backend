from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
from contextlib import asynccontextmanager
import pandas as pd
import os
import time
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

# load_dotenv()

# 환경 변수
INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET")

# 정적 파일 경로 (Docker compose에서 /app/static_data로 마운트 됨)
BASE_DIR = Path("/app")
STATIC_DIR = BASE_DIR / "static_data"

# Timeframe별 허용 임계값 (Timeframe + 여유시간)
# 현재는 1h만 사용. 추후 확장을 위해 구조를 잡아둠.
THRESHOLDS = {
    "1h": timedelta(minutes=65),
    "4h": timedelta(minutes=250),
    "1d": timedelta(hours=25),
}

client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    print("Connecting to InfluxDB...")
    client = InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG,
        timeout=10000,  # 타임아웃 설정
        retries=3,  # 연결 끊김 대비 재시도
    )
    yield

    print("Closing InfluxDB connection...")
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
        print(f"DB Query Error: {e}")
        return None

    if isinstance(df, list) or df.empty:
        return None

    # InfluxDB 리턴값 정리 ('_time' -> 'timestamp')
    df.rename(columns={"_time": "timestamp"}, inplace=True)

    return df


@app.get("/history/{symbol:path}")
def get_history(symbol: str):
    """
    과거 30일치 차트 데이터 반환
    """
    start_time = time.time()
    df = query_influx(symbol, "ohlcv", days=30)

    if df is None:
        raise HTTPException(status_code=404, detail=f"No history data for {symbol}")

    # 필요한 컬럼만 추출
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    available_cols = [c for c in cols if c in df.columns]

    return {
        "symbol": symbol,
        "count": len(df),
        "execution_time": round(time.time() - start_time, 4),
        "data": df[available_cols].to_dict(orient="records"),
    }


@app.get("/predict/{symbol:path}")
def predict_price(symbol: str):
    """
    'prediction' 테이블에서 미리 계산된 데이터를 가져옴
    """
    start_time = time.time()

    # DB에서 예측 결과 조회 (최근 24시간 내 생성된 데이터 중 미래값)
    df = query_influx(symbol, "prediction", days=2)

    if df is None or df.empty:
        # DB에 아직 예측값이 없을 경우 (Worker가 안 돌았거나 모델이 없을 때)
        raise HTTPException(status_code=404, detail="No prediction data found.")

    now = datetime.now(timezone.utc)
    df = df[df["timestamp"] > now]

    if df is None or df.empty:
        raise HTTPException(status_code=503, detail="System outdated. Worker is down.")

    cols = ["timestamp", "yhat", "yhat_lower", "yhat_upper"]
    available_cols = [c for c in cols if c in df.columns]

    return {
        "symbol": symbol,
        "source": "InfluxDB (Pre-computed)",
        "execution_time": round(time.time() - start_time, 4),
        "forecast": df[available_cols].to_dict(orient="records"),
    }


@app.get("/status/{symbol:path}")
def check_status(symbol: str, timeframe: str = "1h"):
    """
    정적 파일의 신선도(Freshness) 검사
    - 파일이 없거나, 너무 오래되었으면 503에러 반환
    """
    safe_symbol = symbol.replace("/", "_")

    # 파일 명 결정 (TODO:추후 Timeframe 확장에 대비한 네이밍 규칙 필요)
    # 현재 MVP는 prediction_BTC_USDT.json 고정 사용 중
    filename = f"prediction_{safe_symbol}.json"
    file_path = STATIC_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=503, detail="Not initialized yet.")

    try:
        # 메타 데이터 읽기 (전체보다 헤더를 읽는 게 빠르지만, json이므로 우선 모두 로드)
        # 파일 크기가 작으므로 I/O 부담은 미미함.
        with open(file_path, "r") as f:
            data = json.load(f)

        updated_at_str = data.get("updated_at")
        if not updated_at_str:
            raise HTTPException(status_code=503, detail="Invalid data format")

        # 시간 차 계산
        updated_at = datetime.strptime(updated_at_str, "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        now = datetime.now(timezone.utc)

        # 임계값 조회 (기본 값 65분)
        limit = THRESHOLDS.get(timeframe, timedelta(minutes=65))

        if (now - updated_at) > limit:
            # 데이터가 상한 경우
            raise HTTPException(
                status_code=503, detail=f"Data is stale. Last updated: {updated_at_str}"
            )
    except json.JSONDecodeError:
        raise HTTPException(status_code=503, detail="Data corruption detected")
    except Exception as e:
        print(f"Status Check Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    # 신선함
    return {"status": "ok", "updated_at": updated_at_str}


@app.get("/")
def health_check():
    return {"status": "ok", "models_loaded": list(loaded_models.keys())}


@app.on_event("shutdown")
def shutdown_event():
    client.close()
