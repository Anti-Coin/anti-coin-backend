# Projector Reduction Map

- Last Updated: 2026-02-24
- Status: Hold Reference (`D-2026-02-24-57`)
- Purpose: 상태파일/방어 분기를 "원인 제거 기반"으로 축소하기 위한 기준선을 고정한다.
- Scope: split+projector 경로 재개 시 참고할 감축 기준선을 보존한다(현재 active 실행 경로는 직렬 전환).

## 1. 목적/범위
1. 상태파일 lifecycle(언제/어떻게 read-write 되는지)을 단일 문서에서 확인 가능하게 만든다.
2. "파일 개수 축소"가 아니라 "동일 사실의 다중 표현 제거"를 1차 목표로 둔다.
3. self-heal은 projector 전환 완료 전까지 유지한다(오노출 금지 불변식 우선).
4. 이번 문서는 설계/감축 기준만 고정하며, 코드 변경은 포함하지 않는다.

## 2. 상태파일 Lifecycle 요약 (현재)
| State File | Owner | Write Timing | Read Timing | Current Role |
|---|---|---|---|---|
| `ingest_state.json` | ingest worker | ingest 단계 cursor/status 갱신 즉시 commit | ingest 시작 시 load | ingest 진행 cursor의 1차 소스 |
| `ingest_watermarks.json` | pipeline runtime | cycle 종료 시점 commit | publish cycle 시작 시 load(특히 publish-only worker) | "ingest가 최신인지" gate 입력 |
| `predict_watermarks.json` | pipeline runtime | cycle 종료 시점 commit | prediction/publish gate 평가 시 load | predict 최신성 추적 |
| `export_watermarks.json` | pipeline runtime | cycle 종료 시점 commit | publish gate/skip 판단 시 load | export 최신성 추적 |
| `symbol_activation.json` | onboarding policy layer | activation 상태 전이 시 commit | publish cycle 시작 시 load | `hidden_backfilling`/노출 가능 여부 정책 |
| `prediction_health.json` | predict worker | predict 성공/실패 전이 시 commit | `/status`, monitor, publish 판단 보조 입력 시 load | degraded 신호와 최근 성공 시각 제공 |
| `manifest.json` | export worker | publish(export) 완료 후 commit | admin/serving에서 read | served artifact 인덱스 |
| `runtime_metrics.json` | ingest worker | ingest cycle 관측값 수집 시 commit | 운영 관측/대시보드 조회 시 read | runtime 운영 지표 스냅샷 |

## 3. 삭제 가능 상태파일 목록 (전제 포함)
### 3.1 1차 삭제 대상
1. `ingest_watermarks.json`
2. `predict_watermarks.json`
3. `export_watermarks.json`
- 전제: projector 판단이 shadow 검증(D-023)에서 기존 gate와 기능 동등 또는 더 안전함이 확인되어야 한다.

### 3.2 유지 대상
1. `symbol_activation.json` (onboarding 정책 owner 유지 필요)
2. `prediction_health.json` (degraded 신호 owner 유지 필요)
3. `manifest.json` (served artifact 인덱스 owner 유지 필요)

### 3.3 조건부 축소 대상
1. `ingest_state.json` (ingest cursor를 DB/단일 projector state로 흡수할 수 있을 때만)
2. `runtime_metrics.json` (운영 지표 수집 경로가 별도 TSDB/metrics backend로 완전 이관될 때만)

## 4. 삭제 가능 함수 목록 + 파일별 LOC 추정
- 기준: 코드 블록 단위 추정, 허용 오차 ±20%.

### 4.1 `scripts/pipeline_worker.py`
직접 삭제 후보(워터마크 전용):
1. `_load_watermark_entries` (14 LOC)
2. `_save_watermark_entries` (13 LOC)
3. `_parse_utc` (10 LOC)
4. `_resolve_watermark_datetime` (13 LOC)
5. `_upsert_watermark` (25 LOC)
6. `evaluate_publish_gate_from_ingest_watermark` (38 LOC)
7. `should_run_publish_from_ingest_watermark` (31 LOC)
- 직접 합계: **144 LOC**

부분 삭제 후보(projector 전환 후 축소):
1. `_run_publish_timeframe_step` 내부 gate/self-heal 분기
2. `_persist_cycle_runtime_state` 내부 watermark commit 블록
3. `run_worker` 초기 watermark load/init 블록
- 부분 합계 추정: **120~190 LOC**
- 파일 합계 추정: **264~334 LOC**

### 4.2 `utils/pipeline_runtime_state.py`
1. `WatermarkStore` 클래스 제거: **약 80 LOC**

### 4.3 `scripts/worker_config.py`
1. watermark 경로 상수 3개 제거: **3 LOC**

### 4.4 테스트 영향
1. `tests/test_pipeline_worker.py`의 watermark gate/self-heal 중심 테스트 교체: **약 350~500 LOC 변경 추정**

## 5. 단계별 삭제 게이트 체크리스트
1. Gate A (`D-022`): publish `poll_loop=60s` 전환 후 long TF publish lag p95 <= 1m, overrun 비열화 확인.
2. Gate B (`D-023`): shadow projector vs 기존 gate 판단 diff 로그/지표 확보(불일치율과 패턴 확인).
3. Gate C (`D-024`): artifact missing이 별도 self-heal 분기 없이 일반 reconcile 경로에서 복구됨을 검증.
4. Gate D (`D-025`): watermark 3종 + gate 함수 제거, 관련 회귀 테스트 정비.
5. Gate E (`D-026`): `publish-first / ingest-later / long TF` 자동화 회귀 테스트 고정.

## 6. 롤백 규칙 (기존 gate 복귀 플래그)
1. projector 전환은 feature flag 기반으로 단계적 전개한다.
2. 권장 플래그(문서 기준):
   - `PIPELINE_PROJECTOR_ENABLED` (`0`이면 기존 watermark gate 경로)
   - `PIPELINE_WATERMARK_GATE_ENABLED` (`1`이면 기존 gate 강제)
   - `PIPELINE_PUBLISH_SELF_HEAL_ENABLED` (`1`이면 self-heal 유지)
3. 롤백 트리거:
   - `overrun_rate` 악화
   - projector 판단 불일치 급증
   - artifact 복구 실패 반복
4. 롤백 절차:
   - projector 비활성화
   - watermark gate 재활성화
   - self-heal 유지
   - 1 cycle 내 복구 여부를 로그/지표로 확인
