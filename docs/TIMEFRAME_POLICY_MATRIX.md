# Coin Predict Timeframe Policy Matrix (B-001)

- Last Updated: 2026-02-13
- Status: Draft v3 (Semantics Clarified)
- Owners: Backend/Platform
- Source Decisions: `D-2026-02-13-29`, `D-2026-02-13-30`, `D-2026-02-13-31`, `D-2026-02-13-34`

## 1. Purpose
1. Phase B에서 timeframe별 수집/보존/서빙/예측 경계를 명확히 고정한다.
2. `1m` 비대칭 정책, 저장소 예산(Free Tier 50GB), Hard Gate + Accuracy Signal을 실행 가능한 기준으로 통일한다.
3. 구현(`B-002`, `B-003`, `B-006`) 전에 정책 드리프트를 차단한다.

## 2. Invariants
1. 우선순위: Stability > Cost > Performance.
2. Source of Truth: InfluxDB.
3. 내부 시간: UTC 고정.
4. Hard Gate 상태는 정확도 지표로 우회할 수 없다.
5. `1m` prediction은 기본 비서빙이다.

## 3. Timeframe Tier Matrix
| Timeframe | Data Source | Retention | Serving Policy | Prediction Policy | Notes |
|---|---|---|---|---|---|
| `1m` | Exchange closed candles | `14d` default, `30d` cap | SSG + Hybrid API(latest window only) | Disabled(default) | 고빈도 특성상 지연/비용 리스크 우선 차단 |
| `1h` | Exchange closed candles (canonical base) | `365d` default, `730d` cap | SSG primary | Enabled | `1d/1w/1M` downsample의 기준 소스 |
| `1d` | Derived from `1h` downsample | Derived retention | SSG primary | Enabled(샘플 gate 통과 시) | direct exchange ingest 금지(파생 전용) |
| `1w` | Derived from `1h` downsample | Derived retention | SSG primary | Enabled(샘플 gate 통과 시) | direct exchange ingest 금지(파생 전용) |
| `1M` | Derived from `1h` downsample | Derived retention | SSG primary | Enabled(샘플 gate 통과 시) | direct exchange ingest 금지(파생 전용) |

## 3.1 Ingest Routing Guard
1. Exchange fetch는 base timeframe(`1m`, `1h`)에만 허용한다.
2. `1d/1w/1M`은 `1h` downsample materialization으로만 생성한다(직접 수집 금지).
3. 현재 worker의 공용 fetch 함수는 base timeframe 재사용 경로이며, 파생 timeframe 경로는 정책상 호출하지 않는다.
4. 파생 timeframe direct ingest 정리/하드 가드는 `C-005` 구현 범위에서 확정한다.

## 4. 1m Hybrid API Boundary
1. `1m` Hybrid API는 `latest closed 180 candles`만 제공한다(약 3시간).
2. 임의 range 조회(`from/to`)는 허용하지 않는다.
3. 목적은 "최근 관측 보강"이며, 과거 데이터 대량 조회는 SSG/배치 경로로 분리한다.
4. 응답은 closed candle만 포함한다(incomplete candle 제외).

## 5. Retention and Budget Guard
1. `1m` raw retention 기본값은 `14d`, 운영 상한은 `30d`.
2. 용량 압박 시 정책:
1. 먼저 `14d` 유지 여부를 보장한다.
2. `14d` 유지가 불가능해지면 경보를 우선 발행한다.
3. 강제 축소가 필요하면 운영 의사결정 로그를 남긴다.
3. `B-006`에서 disk watermark를 적용한다.
1. `warn`: 70%
2. `critical`: 85%
3. `block new expensive backfill`: 90%

## 6. Downsample Contract (1h -> 1d/1w/1M)
1. 시간 경계는 UTC bucket boundary를 사용한다.
2. 캔들 집계 규칙:
1. `open`: bucket 내 첫 `1h`의 `open`
2. `high`: bucket 내 `high`의 `max`
3. `low`: bucket 내 `low`의 `min`
4. `close`: bucket 내 마지막 `1h`의 `close`
5. `volume`: bucket 내 `volume` 합
3. Completeness rule:
1. bucket 내 필요한 `1h` 캔들이 모두 존재해야 `complete`.
2. 누락 시 해당 bucket은 `incomplete_bucket`으로 표시하고 서빙 차단(Hard Gate)한다.
4. 외부 대사 정책:
1. 내부 변환은 deterministic 규칙으로 재현 가능해야 한다.
2. 거래소 공개 데이터와 정기 대사(reconciliation)를 수행한다.
3. 허용 오차는 "변환 오차"가 아니라 "소스 차이/집계 타이밍 차이"로만 취급한다.

## 7. Serving Policy: Hard Gate + Accuracy Signal
### 7.1 Hard Gate (`serve 금지`)
1. `corrupt`
2. `hard_stale`
3. `insufficient_data`
4. `incomplete_bucket`

### 7.2 Accuracy Signal (`serve 가능 + 품질 표시`)
1. `mae`
2. `smape`
3. `directional_accuracy`
4. `sample_count`
5. `evaluation_window`

### 7.3 Evaluation Window and Min Sample (Per Timeframe)
| Timeframe | Evaluation Window | Min Sample |
|---|---|---|
| `1h` | `rolling_30d` | `240` |
| `1d` | `rolling_180d` | `120` |
| `1w` | `rolling_104w` | `52` |
| `1M` | `rolling_36M` | `24` |

### 7.4 Interpretation
1. Hard Gate 발생 시 정확도 지표가 좋아도 `serve 금지`.
2. Hard Gate 미발생 시 정확도 지표를 사용자/운영자에게 투명하게 표시한다.

## 8. Output Contract (for FE/Consumer)
최소 필드 표준(예시 스키마):

```json
{
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "status": "healthy|soft_stale|hard_stale|corrupt|insufficient_data|incomplete_bucket",
  "serve_allowed": true,
  "updated_at": "2026-02-13T12:00:00Z",
  "quality": {
    "mae": 123.4,
    "smape": 2.1,
    "directional_accuracy": 0.57,
    "sample_count": 240,
    "evaluation_window": "rolling_30d"
  }
}
```

## 9. Verification Checklist (B-001 Gate)
1. 정책 스키마 테스트:
1. `1m` retention이 `14d <= x <= 30d` 범위 제약을 만족한다.
2. `1m` hybrid limit이 `180`으로 고정되어 임의 range가 거부된다.
2. downsample 검증:
1. OHLCV 집계 규칙이 deterministic하게 재현된다.
2. 누락 bucket은 `incomplete_bucket`으로 차단된다.
3. 서빙 정책 검증:
1. Hard Gate 상태에서 `serve_allowed=false`.
2. Hard Gate 미발생 상태에서 quality 필드가 포함된다.
4. 평가 구간 검증:
1. timeframe별 `evaluation_window`와 `min sample` 규칙이 매핑대로 적용된다.
2. `min sample` 미달 시 `insufficient_data`로 차단된다.

## 10. Rollback Rules
1. 정책 충돌/과도한 장애 발생 시 즉시 `1h` 단일 운영 모드로 회귀.
2. `1m` hybrid API는 feature flag로 비활성화 가능해야 한다.
3. retention/downsample job은 독립적으로 중지 가능해야 한다.

## 11. Reconciliation Policy (Locked)
1. Reconciliation은 동일 거래소/동일 심볼 기준으로 수행한다.
2. 내부 downsample 무결성 검증(필수):
1. deterministic OHLCV 규칙 검증은 `0 tolerance`다.
2. `internal_deterministic_mismatch` 발생 시 즉시 `critical`.
3. 외부 대사(동일 소스) 운영 주기:
1. `daily quick`: 최근 24h bucket 비교.
2. `weekly deep`: 최근 90d bucket 비교.
4. 경보 규칙:
1. `incomplete_bucket` 또는 missing bucket 발생 시 즉시 `critical`.
2. 단발 `external_reconciliation_mismatch`는 `warning`으로 기록하고 추적한다.
3. 동일 bucket `external_reconciliation_mismatch`가 연속 3회 반복되면 `critical`.
