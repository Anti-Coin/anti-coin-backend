# Stale Escalation Runbook

- Last Updated: 2026-02-20
- Scope: monitor alert-only 운영에서 stale 장기 지속 사건 대응

## 1. Purpose
1. monitor가 제어를 수행하지 않고, 탐지/알림만 수행하는 경계를 유지한다.
2. 장주기 timeframe stale이 장시간 지속될 때 운영자 개입 시점을 표준화한다.
3. `hard_stale_repeat`와 `*_escalated`를 구분해 MTTR 판단을 단순화한다.

## 2. Alert Tiers
1. Transition Alert: 상태전이 발생 시 즉시 알림 (`hard_stale`, `missing`, `corrupt`, `recovery`)
2. Repeat Alert: 동일 상태 지속 시 주기 알림 (`MONITOR_RE_ALERT_CYCLES`)
3. Escalation Alert: 장기 지속 승격 알림 (`MONITOR_ESCALATION_CYCLES`)

## 3. Default Policy
1. `MONITOR_RE_ALERT_CYCLES=3`
2. `MONITOR_ESCALATION_CYCLES=60`
3. 승격 이벤트:
1. `hard_stale_escalated`
2. `missing_escalated`
3. `corrupt_escalated`
4. `soft_stale_escalated`

## 4. Failure Budget and Manual Intervention
1. Failure Budget (monitor 관점):
1. 같은 `symbol|timeframe` 키에서 escalation 이벤트가 1회 발생하면 "수동 개입 필요"로 간주한다.
2. Retry Upper Bound:
1. monitor는 제어/재시작/강제 재수집을 수행하지 않는다.
2. escalation 이후 자동 복구 기대치를 0으로 두고 운영자 점검으로 전환한다.
3. Manual Intervention Conditions:
1. `hard_stale_escalated` 또는 `missing_escalated` 1회 발생
2. `soft_stale_escalated`가 2회 이상 반복
3. `corrupt_escalated` 발생

## 5. Operator Checklist
1. `manifest.json`에서 해당 키의 `prediction.updated_at`, `status`, `serve_allowed`를 확인한다.
2. `prediction_health.json`에서 `last_success_at`, `last_failure_at`, `consecutive_failures`를 확인한다.
3. `ingest_watermarks.json`, `predict_watermarks.json`, `export_watermarks.json`의 전진 여부를 비교한다.
4. `runtime_metrics.json`에서 최근 cycle `result`, `detection_gate_*`, `ingest_since_source_counts`를 확인한다.
5. 필요 시 worker/monitor 로그를 확인하고 원인 분류를 기록한다.

## 6. Classification Guide
1. 정상 대기 가능성:
1. 장주기 TF 경계 전이며 watermarks가 최근 경계 기준으로 정합적일 때
2. 방치 가능성:
1. watermark/updated_at가 장시간 정체되고 동일 상태가 escalation 임계 이상 반복될 때
3. 데이터 무결성 위험:
1. `corrupt` 계열 이벤트 발생 또는 Influx-JSON mismatch가 반복 승격될 때

## 7. Verification Procedure (C-016)
1. 단위 테스트:
1. `PYENV_VERSION=coin pytest -q tests/test_status_monitor.py`
2. 회귀 테스트:
1. `PYENV_VERSION=coin pytest -q`
3. 운영 점검:
1. monitor 알림 메시지에서 `*_escalated` 이벤트 수신 확인
2. escalation 이벤트 메시지에 runbook 경로(`docs/RUNBOOK_STALE_ESCALATION.md`)가 포함되는지 확인
