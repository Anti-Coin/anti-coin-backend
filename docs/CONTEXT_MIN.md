# Coin Predict Context (Minimum)

- Last Updated: 2026-02-21
- Purpose: 새 세션에서 최소 토큰으로 현재 상태를 정렬하기 위한 요약

## 1. Snapshot
1. Phase A(Reliability Baseline)는 2026-02-12에 완료했다.
2. Phase B(Timeframe Expansion)는 2026-02-19에 완료했다.
3. Phase C(Scale and Ops)는 2026-02-20에 완료했고, 상세는 archive로 이동했다.
4. 현재 활성 실행 구간은 Phase D(Model Evolution)다.
5. 운영 현실은 Oracle Free Tier ARM + 단일 운영자다.

## 2. Archived Summaries
1. Phase B 상세 원문: `docs/archive/phase_b/*`
2. Phase C 상세 원문: `docs/archive/phase_c/*`
3. 활성 문서는 요약/현재 실행 기준만 유지한다.

## 3. Phase D Active Baseline
1. 기본 모델 커버리지는 `timeframe-shared champion`으로 시작한다(`D-2026-02-13-32`).
2. dedicated 도입은 승격 조건(최소 샘플/성능 개선/비용 허용) 충족 시에만 허용한다.
3. fallback 체인은 `dedicated -> shared -> insufficient_data`로 고정한다.
4. 실패 은닉 금지: dedicated 실패를 shared로 조용히 대체하지 않고 상태/사유를 노출한다.

## 4. Current Priority Tasks
1. `D-001`: 모델 인터페이스 계약(`fit/predict/save/load`) 고정
2. `D-002`: 모델 메타데이터/버전 스키마 정의
3. `D-012`: 학습 데이터 SoT 정렬(Influx 기반 closed-candle snapshot)
4. `D-013`: 재학습 트리거 정책 정의(시간+이벤트)

## 5. Recent Completion (2026-02-20)
1. `C-013`: `pipeline_worker` timeboxed micro-refactor(동작 불변)
2. `C-014`: derived TF publish starvation 완화
3. `C-015`: non-primary prediction fallback 오염 차단
4. `C-016`: monitor escalation(`*_escalated`) + runbook 고정
5. `C-004`: 학습 one-shot 경계(`worker-train`) 및 runbook 고정
6. `D-018`: `1d/1w/1M` direct fetch 전환 + downsample/lineage 코드 비참조화
7. 기준선 회귀: `PYENV_VERSION=coin pytest -q` 통과(`140 passed`)

## 6. Non-Negotiables
1. 우선순위: Stability > Cost > Performance.
2. No silent failure, Idempotency first, UTC internally.
3. Soft stale은 경고와 함께 노출 가능, hard_stale/corrupt는 차단.

## 7. Serving Boundary
1. Source of Truth는 InfluxDB다.
2. 사용자 데이터 플레인은 SSG(static JSON)다.
3. `/status`는 운영 신호 및 프론트 경고 노출에 사용 가능하다.
4. `/history`, `/predict`는 sunset tombstone(`410`)이며 정상 운영 경로가 아니다.

## 8. Current Risk Focus
1. `TD-012`: 자동 재학습/승격 게이트 미구현
2. `TD-010`: 모델 인터페이스 미구현
3. `TD-022`: prediction freshness 의미론(입력 stale 은닉 가능성) 정렬 필요
4. `TD-009`: dev push 즉시 배포 구조 리스크

## 9. Deep References
1. 현재 운영 결정: `docs/DECISIONS.md`
2. 현재 로드맵/다음 단계: `docs/PLAN_LIVING_HYBRID.md`
3. 활성 태스크 보드: `docs/TASKS_MINIMUM_UNITS.md`
4. 과거 원문 이력: `docs/archive/README.md`
