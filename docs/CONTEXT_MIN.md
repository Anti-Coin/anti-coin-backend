# Coin Predict Context (Minimum)

- Last Updated: 2026-03-05
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
1. 현재 런타임 모델 아티팩트 단위는 `symbol+timeframe canonical`이다(`D-2026-03-03-71`).
2. 학습/추론 모두 canonical 모델/metadata 경로(`model_{symbol}_{timeframe}*.json`)를 사용한다.
3. shared/dedicated coverage resolver는 `D-011` hold로 남아 있다.
4. 모델 부재/샘플 부족(`model_missing`/`insufficient_data`)은 상태/사유를 숨기지 않고 노출한다.

## 4. Current Priority Tasks
1. `D-013`: 재학습 트리거 정책 정의(1차 시간 기반, 이벤트는 도입 조건만 고정)
2. `D-046`: Status-Monitor 판정 경로 단일화(모니터 기준)
3. `D-040`: Legacy Kill Stage 1(모델 fallback 제거)
4. `D-041`: Legacy Kill Stage 2(static dual-write 제거)
5. `D-042`: Legacy Kill Stage 3(legacy query fallback 제거, ingest+monitor)
6. `D-043`: Manifest 계약 분리(`manifest.v2` 단일 파일 내 `public/ops`)
7. `D-047`: Scheduler mode boundary 단일화(`poll_loop` 제거)

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
4. `TD-035`: 이벤트 기반 재학습 임계치 휴리스틱(미보정) 리스크

## 9. Deep References
1. 현재 운영 결정: `docs/DECISIONS.md`
2. 현재 로드맵/다음 단계: `docs/PLAN_LIVING_HYBRID.md`
3. 활성 태스크 보드: `docs/TASKS_MINIMUM_UNITS.md`
4. 과거 원문 이력: `docs/archive/README.md`
