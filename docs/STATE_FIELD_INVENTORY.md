# State Field Inventory Audit

- Last Updated: 2026-03-04
- Scope: `manifest`(`manifest.json` -> `manifest.v2`), `runtime_metrics.json`, `prediction_health.json`, `symbol_activation.json`, `ingest_watermarks.json`
- Goal: 조용한 fallback/중복 상태를 줄이고 `Fail-Closed + SoT 명확화`를 위한 제거 후보를 식별한다.

## 1. Audit Rules
1. 각 필드는 `SoT`, `Derived`, `Diagnostic`, `Legacy-Compat` 중 하나로 분류한다.
2. `SoT`가 아닌 필드는 기본적으로 제거 또는 파생 전환 후보로 본다.
3. 제거 시 즉시 깨질 소비자(admin/ops/FE/test)를 먼저 식별한다.
4. 오노출 방지 비트(`serve_allowed`)는 단순화 대상이 아니라 보호 대상이다.

## 2. Cross-File Duplication Map
| Signal | Current Source | Duplicated Into | Audit Verdict |
|---|---|---|---|
| `degraded`, `last_success_at`, `last_failure_at`, `consecutive_failures` | `prediction_health.json` | `manifest` entry | `manifest.v2.public`은 최소 요약만 유지, 상세는 `manifest.v2.ops`로 이동 |
| `visibility`, `state`, `is_full_backfilled`, `coverage_*` | `symbol_activation.json` | `manifest` entry | FE 경로에서는 제거 가능, ops 경로에만 유지 |
| freshness status/age | prediction file + thresholds | `manifest` entry | 유지(serve gate 판단 근거) |
| watermark latest | `ingest_watermarks.json` | (직접 중복 없음) | 유지(최소 상태 파일) |

## 3. File-Level Inventory

### 3.1 `manifest` (`manifest.json` current, `manifest.v2` target)
| Field | Class | Consumers | Audit Verdict | Notes |
|---|---|---|---|---|
| `version`, `generated_at` | Diagnostic | admin/ops | Keep | 파일 계약 버전/생성시각 |
| `entries[].key` | SoT(identity) | admin/ops | Keep | `symbol|timeframe` 조인 키 |
| `entries[].symbol`, `entries[].timeframe` | SoT(identity) | admin/ops/FE | Keep | FE 필터/표시 기본 키 |
| `entries[].history.updated_at` | Diagnostic | admin/ops | Keep(ops) | 사용자 경로 필수는 아님 |
| `entries[].history.source_file` | Diagnostic | debug only | Drop candidate | 디버깅 전용. public payload 비권장 |
| `entries[].prediction.status` | SoT(gate input) | admin/ops/FE | Keep | serve 결정 핵심 입력 |
| `entries[].prediction.updated_at` | SoT(gate input) | admin/ops/FE | Keep | freshness 계산 근거 |
| `entries[].prediction.age_minutes` | Derived | admin | Derive-on-read candidate | 계산 가능, 저장 필수 아님 |
| `entries[].prediction.threshold_minutes` | Derived/config echo | admin | Keep(ops) | 운영 해석 편의 |
| `entries[].prediction.source_detail` | Diagnostic | admin/ops | Keep(ops) | 원인 분석용 |
| `entries[].degraded` | SoT(view) | admin/ops/FE | Keep | freshness와 분리된 실패 신호 |
| `entries[].last_prediction_success_at` | Derived from health | admin/ops | Move to `manifest.v2.ops` | FE 필수 아님 |
| `entries[].last_prediction_failure_at` | Derived from health | admin/ops | Move to `manifest.v2.ops` | FE 필수 아님 |
| `entries[].prediction_failure_count` | Derived from health | admin/ops | Move to `manifest.v2.ops` | FE 필수 아님 |
| `entries[].visibility` | SoT(onboarding) | admin/FE | Keep(ops), optional(public) | serve gate와 역할 중복 가능 |
| `entries[].symbol_state` | Derived-ish(`state`) | admin/ops | Derive candidate | `visibility/is_full_backfilled`와 중복 가능 |
| `entries[].is_full_backfilled` | SoT(onboarding) | admin/ops | Keep(ops), optional(public) | onboarding 판정 핵심 |
| `entries[].coverage_start_at/end_at/exchange_earliest_at` | Diagnostic | admin/ops | Move to `manifest.v2.ops` | FE 필수 아님 |
| `entries[].serve_allowed` | SoT(final gate) | FE/admin | Keep(critical) | 오노출 0 최종 비트 |
| `summary.*` | Derived aggregate | admin/ops | Keep | 뷰/알림 요약에 유용 |

### 3.2 `runtime_metrics.json`
| Field | Class | Consumers | Audit Verdict | Notes |
|---|---|---|---|---|
| `version`, `updated_at` | Diagnostic | ops | Keep | |
| `target_cycle_seconds`, `window_size` | Config echo | ops | Keep | 계측 해석 필수 |
| `boundary_tracking.*` | Diagnostic | ops | Keep | scheduler 모드 증거 |
| `summary.samples/success/failure/overrun/p95` | SoT(ops KPI) | ops/docs | Keep | D-028/D-059 근거 |
| `summary.ingest_since_source_counts` | Diagnostic | ops | Keep | 재부트스트랩 추적 |
| `summary.detection_gate_*` | Diagnostic | ops | Keep | gate 동작 추적 |
| `recent_cycles[]` 전체 | Diagnostic history | ops only | Reduce candidate | 장기 운영 시 용량 증가. window 상한 강제 필요 |
| `recent_cycles[].error` | Diagnostic | ops | Keep | 실패 RCA 핵심 |

### 3.3 `prediction_health.json`
| Field | Class | Consumers | Audit Verdict | Notes |
|---|---|---|---|---|
| `version`, `updated_at` | Diagnostic | api/ops | Keep | |
| `entries[key].symbol`, `timeframe` | Redundant(identity) | api/admin | Drop candidate | key에 이미 포함됨 |
| `entries[key].degraded` | SoT | api/manifest/monitor | Keep | |
| `entries[key].last_success_at` | SoT(history) | api/manifest/ops | Keep | |
| `entries[key].last_failure_at` | SoT(history) | api/manifest/ops | Keep | |
| `entries[key].consecutive_failures` | SoT(counter) | api/manifest/ops | Keep | |
| `entries[key].last_error` | SoT(reason) | api/ops | Keep | 승격/차단 사유 |
| `entries[key].updated_at` | Diagnostic | ops | Keep | |

### 3.4 `symbol_activation.json`
| Field | Class | Consumers | Audit Verdict | Notes |
|---|---|---|---|---|
| `version`, `updated_at` | Diagnostic | ingest/export/ops | Keep | |
| `entries[symbol].symbol` | Redundant(identity) | ingest/export | Drop candidate | map key와 중복 |
| `entries[symbol].state` | SoT(onboarding) | ingest/export/admin | Keep | canonical state 추천 |
| `entries[symbol].visibility` | Derived from state | ingest/export/admin | Derive candidate | 상태 enum에서 계산 가능 |
| `entries[symbol].is_full_backfilled` | Derived from state+coverage | ingest/export/admin | Derive candidate | 중복 가능성 높음 |
| `entries[symbol].coverage_start_at/end_at` | SoT(coverage) | ingest/admin | Keep | 운영 판단 근거 |
| `entries[symbol].exchange_earliest_at` | SoT(reference) | ingest/admin | Keep | full-fill 비교 기준 |
| `entries[symbol].ready_at` | SoT(event time) | admin/ops | Keep | 전이 시각 추적 |

### 3.5 `ingest_watermarks.json`
| Field | Class | Consumers | Audit Verdict | Notes |
|---|---|---|---|---|
| `version`, `updated_at` | Diagnostic | ingest/publish/ops | Keep | |
| `entries[key]=closed_at` | SoT(cursor) | pipeline core | Keep(critical) | 직렬 경로 인과 보장 핵심 |

## 4. Target Backlog (Execution Order)
1. P0: 모델/정적산출물 legacy fallback 제거(`model`, `prediction/history dual-write`).
2. P0: `prediction_health` redundant identity 필드(`symbol`, `timeframe`) 제거.
3. P1: `manifest.v2` 계약 분리(단일 파일 내 `public` 최소 필드 + `ops` 상세 필드).
4. P1: `symbol_activation` 정규화(`state` 단일 SoT, `visibility/is_full_backfilled` 파생화).
5. P2: `runtime_metrics.recent_cycles` 보존 정책 축소(용량 상한/회전 정책 강화).

## 5. Keep-By-Design (Do Not Remove)
1. `serve_allowed`: 오노출 0 보장을 위한 최종 게이트 비트.
2. `prediction_health` 전이 필드(`last_success_at`, `consecutive_failures`, `last_error`): 단순 freshness 파일로 대체 불가.
3. `ingest_watermarks.entries`: 파이프라인 인과성과 idempotency 핵심 상태.

## 6. Open Questions Before Destructive Cleanup
1. `manifest.v2.public` 필드 최소셋을 어디까지 고정할지(`degraded` 포함 여부).
2. `manifest.v2.ops` 보존 기간/용량 상한은 얼마로 둘 것인지.
3. `symbol_activation`에서 `state`를 단일 SoT로 고정할지, 아니면 `is_full_backfilled`를 단일 SoT로 둘지.

## 7. File Elimination Feasibility (2026-03-04)
1. `prediction_health.json`
1. 필드 축소 가능: `entries[key].symbol`, `entries[key].timeframe`는 제거 가능(키와 중복).
2. 파일 삭제는 현재 비권장: `/status` degraded 신호와 recovery 이력의 owner이므로 즉시 제거 시 상태 정직성 저하 위험.
2. `ingest_watermarks.json`
1. 필드 축소 여지 낮음: 핵심은 `entries[key]=closed_at` 단일 커서.
2. 파일 삭제는 조건부 가능: publish gate를 `ingest_state` 기반으로 재설계하고 long TF detection-skip 동기화 경로를 대체해야 함(현 구조에서는 인과/재시작 경계 리스크 큼).
3. `runtime_metrics.json`
1. 파일 삭제 비권장: D-028/운영 headroom 근거 파일.
2. 축소 후보: `recent_cycles` 보존 길이 축소.
4. `symbol_activation.json`
1. 파일 삭제 비권장: onboarding hide 정책 owner.
2. 축소 후보: `symbol`, `visibility`, `is_full_backfilled` 파생 전환.
