# Coin Predict Timeframe Policy Matrix (B-001)

- Last Updated: 2026-02-21
- Status: Active (D-018 direct fetch 반영)
- Owners: Backend/Platform
- Source Decisions: `D-2026-02-13-29`, `D-2026-02-13-30`, `D-2026-02-13-31`, `D-2026-02-17-36`, `D-2026-02-21-51`

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
| `1h` | Exchange closed candles (activation canonical) | full-first(`exchange earliest -> now`) | SSG primary | Enabled | symbol activation 기준 TF(`SYMBOL_ACTIVATION_SOURCE_TIMEFRAME`) |
| `1d` | Exchange closed candles (direct fetch) | Timeframe-native retention | SSG primary | Enabled(샘플 gate 통과 시) | downsample 미사용 |
| `1w` | Exchange closed candles (direct fetch) | Timeframe-native retention | SSG primary | Enabled(샘플 gate 통과 시) | downsample 미사용 |
| `1M` | Exchange closed candles (direct fetch) | Timeframe-native retention | SSG primary | Enabled(샘플 gate 통과 시) | downsample 미사용 |

## 3.1 Ingest Routing Guard
1. Exchange fetch는 모든 운영 timeframe(`1m`,`1h`,`1d`,`1w`,`1M`)에 허용한다.
2. `1d/1w/1M`은 direct fetch로 수집하며 downsample materialization을 사용하지 않는다.
3. worker 공용 ingest 진입점(`run_ingest_step`)은 timeframe 분기 없이 `fetch_and_save`를 호출한다.
4. 장주기 TF의 publish starvation 완화는 detection gate skip(`no_new_closed_candle`) 시 ingest watermark sync로 처리한다.

## 3.2 Symbol Activation Gate (`1h` Full-First)
1. 적용 범위: 현재 및 미래의 모든 심볼.
2. `full` 기준: 상장일 메타가 아닌 `exchange API가 제공하는 earliest closed 1h candle`부터 현재까지.
3. 상태 전이: `registered -> backfilling -> ready_for_serving`.
4. `backfilling` 상태 심볼은 FE 사용자 플레인에서 완전 비노출한다(심볼 목록 포함).
5. 운영자 경로(admin/ops)에서는 `backfilling` 상태와 진행 메타를 노출할 수 있다.
6. 저장소 `block(>=90%)`에서는 신규 심볼 full backfill을 시작/재개하지 않는다(가드 우회 금지).

## 4. 1m Hybrid API Boundary
1. `1m` Hybrid API는 `latest closed 180 candles`만 제공한다(약 3시간).
2. 임의 range 조회(`from/to`)는 허용하지 않는다.
3. 목적은 "최근 관측 보강"이며, 과거 데이터 대량 조회는 SSG/배치 경로로 분리한다.
4. 응답은 closed candle만 포함한다(incomplete candle 제외).

## 5. Retention and Budget Guard
1. `1m` raw retention 기본값은 `14d`, 운영 상한은 `30d`.
2. `1h`는 onboarding 시 full-first 수집을 수행하고, 기본 운영에서는 주기적 day-cap purge를 적용하지 않는다.
3. 용량 압박 시 정책:
1. 먼저 `14d` 유지 여부를 보장한다.
2. `14d` 유지가 불가능해지면 경보를 우선 발행한다.
3. 강제 축소가 필요하면 운영 의사결정 로그를 남긴다.
4. `B-006`에서 disk watermark를 적용한다.
1. `warn`: 70%
2. `critical`: 85%
3. `block new expensive backfill`: 90%

## 6. Long TF Direct Fetch Contract (`1d/1w/1M`)
1. `1d/1w/1M`은 거래소 closed candle을 직접 수집한다.
2. detection gate는 거래소 latest closed candle 기준으로 실행/스킵을 판단한다.
3. skip 사유가 `no_new_closed_candle`이고 long TF + `last_time` 존재 시 ingest watermark를 `last_time`으로 동기화해 publish starvation을 완화한다.
4. 데이터 품질은 downsample deterministic 검증 대신 거래소 데이터 계약(누락/지연/갭) 기반으로 감시한다.

## 7. Serving Policy: Hard Gate + Accuracy Signal
### 7.1 Hard Gate (`serve 금지`)
1. `corrupt`
2. `hard_stale`
3. `insufficient_data`

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
  "visibility": "visible|hidden_backfilling",
  "is_full_backfilled": true,
  "coverage_start_at": "2018-01-01T00:00:00Z",
  "coverage_end_at": "2026-02-17T12:00:00Z",
  "status": "healthy|soft_stale|hard_stale|corrupt|insufficient_data",
  "serve_allowed": true,
  "updated_at": "2026-02-17T12:00:00Z",
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
2. direct fetch 검증:
1. `1d/1w/1M` ingest가 거래소 fetch 경로로 실행된다.
2. detection gate skip(`no_new_closed_candle`) 시 long TF watermark sync가 수행된다.
3. 서빙 정책 검증:
1. Hard Gate 상태에서 `serve_allowed=false`.
2. Hard Gate 미발생 상태에서 quality 필드가 포함된다.
4. 평가 구간 검증:
1. timeframe별 `evaluation_window`와 `min sample` 규칙이 매핑대로 적용된다.
2. `min sample` 미달 시 `insufficient_data`로 차단된다.
5. onboarding/노출 게이트 검증:
1. 신규 심볼은 full backfill 완료 전 `visibility=hidden_backfilling`이며 FE 목록에서 제외된다.
2. full backfill 완료 후에만 `ready_for_serving`으로 전이된다(`is_full_backfilled=true` + coverage 메타 존재).
3. 디스크 `block` 구간에서는 신규 심볼 full backfill 시작/재개가 차단된다.

## 10. Rollback Rules
1. 정책 충돌/과도한 장애 발생 시 즉시 `1h` 단일 운영 모드로 회귀.
2. `1m` hybrid API는 feature flag로 비활성화 가능해야 한다.
3. retention/long-tf ingest job은 독립적으로 중지 가능해야 한다.

## 11. Reconciliation Policy (Locked)
1. Reconciliation은 동일 거래소/동일 심볼 기준으로 수행한다.
2. 외부 대사(동일 소스) 운영 주기:
1. `daily quick`: 최근 24h bucket 비교.
2. `weekly deep`: 최근 90d bucket 비교.
3. 경보 규칙:
1. missing bucket 발생 시 즉시 `critical`.
2. 단발 `external_reconciliation_mismatch`는 `warning`으로 기록하고 추적한다.
3. 동일 bucket `external_reconciliation_mismatch`가 연속 3회 반복되면 `critical`.
