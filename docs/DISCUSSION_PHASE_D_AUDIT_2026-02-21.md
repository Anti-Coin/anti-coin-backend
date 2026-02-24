# Phase D 사전 감사 및 전략 수정 기록

- Date: 2026-02-21
- Participants: Operator + AI
- Scope: Phase D 계획 비판적 리뷰, downsample 전략 재검토, Immediate Bundle 재정렬

## 1. 감사 배경

Phase D(Model Evolution) 착수 전, `pipeline_worker.py` 분해 과정에서 확보한 코드 이해를 바탕으로 Phase D 계획 전체를 비판적으로 재검토했다.$

핵심 질문: "이 계획대로 하면 안정적으로 진행 가능한가?"

## 2. 발견된 문제 (5건)

### 문제 1: D-012(학습 데이터 SoT)가 D-001(모델 인터페이스)보다 선행되어야 한다
- **발견 근거**: `train_model.py`가 거래소 API에서 직접 fetch (`exchange.fetch_ohlcv`), 운영 추론은 InfluxDB 사용. 학습/추론 데이터 소스 불일치.
- **리스크**: D-001 인터페이스가 "깨진 데이터 위의 추상화"가 됨.
- **결정**: D-012를 D-001보다 선행.

### 문제 2: D-010(min sample gate)은 P0 수준의 중요도
- **발견 근거**: `TIMEFRAME_POLICY_MATRIX.md`에 정의된 min sample 기준이 코드에 미구현.
- **후속 확인**: 1h가 `exchange earliest → 현재` full backfill 완료이므로, downsample된 1d/1w/1M도 상당한 데이터를 보유. 다만 `DOWNSAMPLE_SOURCE_LOOKBACK_DAYS=120` 제한으로 실제 120일분만 존재.
- **결정**: Direct fetch 전환 후 데이터 확보량이 극적으로 늘어나므로, gate 자체는 안전장치로 구현 필요.

### 문제 3: D-003(Shadow 추론 파이프라인)은 최소 단위가 아니다
- **발견 근거**: Shadow 모델 실행, Shadow 결과 저장, 격리 보장이 하나의 태스크에 포함.
- **결정**: 후속 실행 시 3개 서브태스크로 분해.

### 문제 4: 학습 코드 감사 태스크 누락
- **발견 근거**: `train_model.py`에 에러 처리 없음, atomic write 미사용, 메타데이터 없음, 데이터 검증 없음.
- **결정**: D-001 설계 전에 현재 학습 코드의 실패 모드를 먼저 정리.

### 문제 5: D-001 과설계 위험
- **발견 근거**: Prophet 모델 1개만 존재. 두 번째 모델 없이 추상 인터페이스를 만들면 YAGNI 위반.
- **결정**: D-001 scope을 "추상 인터페이스 정의"에서 "현재 Prophet 경로의 계약 명시화"로 축소.

## 3. 근본적 전략 재검토: Downsample → Direct Fetch

### 질문의 시작
> "1h에서 모든 데이터가 수집되었는데, 1d/1w/1M을 거래소에서 직접 수집하는 것과 무슨 차이가 있었는가?"

### 원래 결정 근거 (`D-2026-02-13-34`)
1. **내부 무결성 검증**: downsample 규칙이 코드에 고정되므로 `internal_deterministic_mismatch`를 0-tolerance로 감지 가능
2. **API 호출 절약**: 이미 수집된 1h를 재활용
3. **Free Tier 자원 절약**: 추가 API 호출 없이 파생 가능

### 재검토 결과
| 기준 | Downsample | Direct Fetch | 판정 |
|---|---|---|---|
| 데이터 권위 | 파생 (2차) | 원본 (1차) | **Direct 우위** |
| API 비용 | 없음 | 1d: 1회/일, 1w: 1회/주, 1M: 1회/월 | **무시 가능** |
| 코드 복잡도 | 함수 10개 | 기존 경로 재사용 | **Direct 우위** |
| 데이터 범위 | 120일 제한 | 거래소 전체 이력 | **Direct 우위** |
| lineage 추적 | ✅ 내부 규칙 고정 | ⚠️ 거래소 계산은 블랙박스 | Downsample 우위 |
| 운영 복잡도 | downsample + reconciliation 코드 필요 | 기존 ingest 경로 그대로 | **Direct 우위** |

### 최종 결정
- **Direct fetch로 전환한다.**
- lineage 추적 우위는 인정하나, 그것을 위해 10개 함수/120일 제한/파생 데이터를 감수하는 것은 비합리적.
- 원래 결정의 revisit trigger("파생 timeframe direct ingest 우회 필요 시")에 해당한다고 판단.

### 부수 결정
1. 기존 InfluxDB downsample 데이터: **삭제 후 거래소 원본으로 재수집**
2. `downsample_lineage.json`: **코드에서 완전 제거** (파일 삭제는 운영자 수동)
3. 1d/1w/1M full-first: **기존 watermark 메커니즘이 이미 처리** — 빈 볼륨이면 lookback부터, 기존 데이터 있으면 incremental

## 4. 수정된 Immediate Bundle

```
기존:  D-001 → D-002 → D-012

수정:  D-010 (min sample gate, 안전장치)
       → Direct Fetch 전환 (새 태스크, downsample 제거)
       → D-012 (학습 데이터 SoT 정렬)
       → D-001 (모델 계약 명시화, scope 축소)
       → D-002 (메타데이터/버전 스키마)
```

## 5. 제거되는 코드 (Direct Fetch 전환 시)

| 대상 | 위치 |
|---|---|
| `DOWNSAMPLE_TARGET_TIMEFRAMES` | `worker_config.py` |
| `DOWNSAMPLE_SOURCE_TIMEFRAME` | `worker_config.py` |
| `DOWNSAMPLE_SOURCE_LOOKBACK_DAYS` | `worker_config.py` |
| `DOWNSAMPLE_LINEAGE_FILE` | `worker_config.py` |
| `query_ohlcv_frame` | `workers/ingest.py` |
| `downsample_ohlcv_frame` | `workers/ingest.py` |
| `run_downsample_and_save` | `workers/ingest.py` + `pipeline_worker.py` |
| `upsert_downsample_lineage` | `pipeline_worker.py` |
| `_load_downsample_lineage` | `pipeline_worker.py` |
| `_save_downsample_lineage` | `pipeline_worker.py` |
