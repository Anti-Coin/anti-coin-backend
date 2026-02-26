# Model Contract (Prophet Baseline)

- Last Updated: 2026-02-26
- Scope: D-001 (`fit/predict/save/load` contract lock)
- Non-goal: 추상 인터페이스(`BaseModel`) 도입

## 1. Purpose
1. 현재 운영 경로(Prophet 기반)에서 모델 I/O 계약을 문서와 테스트로 고정한다.
2. 모델 교체는 후속 태스크에서 수행하고, 이번 단계는 계약 불변식만 잠근다.

## 2. Fit Contract
1. Entry point: `scripts/train_model.py::_prepare_prophet_train_df`
2. Input schema:
   - `timestamp` (timezone-aware 또는 naive datetime)
   - `close` (numeric)
3. Normalization:
   - `timestamp -> ds`
   - UTC 기준으로 정규화 후 timezone-naive(`datetime64[ns]`)로 변환
   - `close -> y`
4. Output schema:
   - columns: `ds`, `y`
   - `ds`: timezone-naive datetime

## 3. Save Contract
1. Entry point: `scripts/train_model.py::train_and_save`
2. Serialization:
   - `prophet.serialize.model_to_json(model)` 사용
3. Artifact paths:
   - canonical: `models/model_{SYMBOL}_{TIMEFRAME}.json`
   - legacy(primary timeframe only): `models/model_{SYMBOL}.json`
4. Metadata:
   - `run_id`, `data_range`, `row_count`, `model_version`
   - `model_version = sha256(serialized_model)[:12]`

## 4. Load Contract
1. Entry point: `workers/predict.py::run_prediction_and_save`
2. Candidate order:
   - 1순위: timeframe-specific canonical
   - 2순위: legacy primary model
3. Deserialization:
   - `prophet.serialize.model_from_json(...)` 사용
4. Failure code:
   - 파일 미존재 시 `("failed", "model_missing")`

## 5. Predict Contract
1. Entry point: `workers/predict.py::run_prediction_and_save`
2. Input:
   - loaded model
   - `future.ds`는 timeframe 경계 기준으로 생성하며 timezone-naive
3. Static output (`prediction_{symbol}_{timeframe}.json`):
   - top-level: `symbol`, `timeframe`, `updated_at`, `forecast`
   - `forecast[*]`: `timestamp`, `price`, `lower_bound`, `upper_bound`
   - `timestamp` format: UTC `YYYY-MM-DDTHH:MM:SSZ`
4. Influx output:
   - measurement: `prediction`
   - tags: `symbol`, `timeframe`
5. Return contract:
   - success: `("ok", None)`
   - policy skip: `("skipped", None)` or `("skipped", "insufficient_data")`
   - failure: `("failed", <reason>)`

## 6. Regression Coverage (D-001)
1. `tests/test_model_contract.py`
2. 검증 항목:
   - fit 입력 정규화(`ds` timezone-naive)
   - load 우선순위(canonical > legacy)
   - predict 산출물 schema(JSON + Influx) 고정
