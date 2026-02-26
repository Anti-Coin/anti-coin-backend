# Model Metadata Schema

- Last Updated: 2026-02-26
- Scope: D-002 (모델 메타데이터/버전 스키마 정의)

## 1. Artifact Path
1. Canonical: `models/model_{SYMBOL}_{TIMEFRAME}.meta.json`
2. Legacy(primary timeframe only): `models/model_{SYMBOL}.meta.json`

## 2. Schema (v1)
1. `schema_version` (int): metadata schema version (`1`)
2. `run_id` (string): 학습 실행 식별자(MLflow run id)
3. `symbol` (string): 예: `BTC/USDT`
4. `timeframe` (string): 예: `1h`, `1d`
5. `trained_at` (string, UTC ISO8601): 예: `2026-02-26T13:00:00Z`
6. `row_count` (int): 학습에 사용된 candle row 수
7. `data_range` (object):
   - `start` (string | null, UTC ISO8601)
   - `end` (string | null, UTC ISO8601)
8. `model_version` (string | null): `sha256(serialized_model)[:12]`
9. `snapshot_path` (string): 학습 스냅샷 parquet 경로
10. `status` (string): `ok` | `skipped_insufficient_data`

## 3. Example
```json
{
  "schema_version": 1,
  "run_id": "4e20fa8db91c4d85a6d9a69f7dc1b301",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "trained_at": "2026-02-26T13:00:00Z",
  "row_count": 500,
  "data_range": {
    "start": "2026-02-05T00:00:00Z",
    "end": "2026-02-26T11:00:00Z"
  },
  "model_version": "6fd49e7ab5bd",
  "snapshot_path": "/app/static_data/snapshots/train_data_BTC_USDT_1h.parquet",
  "status": "ok"
}
```

## 4. Contract Notes
1. `schema_version` 변경은 `DECISIONS.md`에 신규 결정으로 기록한다.
2. 예측 경로는 현재 metadata sidecar를 로드하지 않으며, 운영/감사/추적 용도로 저장한다.
3. `status=skipped_insufficient_data`일 때는 모델 파일을 갱신하지 않는다.
