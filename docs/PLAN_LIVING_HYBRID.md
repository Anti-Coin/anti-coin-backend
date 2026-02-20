# Coin Predict Living Plan (Hybrid)

- Last Updated: 2026-02-20
- Owner: Backend/Platform
- Status: Active
- Full Phase A History: `docs/archive/phase_a/PLAN_LIVING_HYBRID_PHASE_A_FULL_2026-02-12.md`
- Full Phase B History: `docs/archive/phase_b/PLAN_LIVING_HYBRID_PHASE_B_FULL_2026-02-19.md`

## 1. Plan Intent
1. 이 문서는 "현재 실행 기준"만 유지한다.
2. 과거 상세 이력/원문은 Archive를 단일 출처로 사용한다.
3. 계획 변경은 실패가 아니라 리스크 제어 활동으로 취급한다.

## 2. Current State
1. Phase A(Reliability Baseline): Completed (2026-02-12)
2. Phase B(Timeframe Expansion): Completed (2026-02-19)
3. Phase C(Scale and Ops): Active
4. Phase D(Model Evolution): Backlog

## 3. Fixed Invariants
1. 우선순위: Stability > Cost > Performance.
2. Source of Truth: InfluxDB.
3. 사용자 데이터 플레인: SSG(static JSON).
4. `soft stale`는 경고 허용, `hard_stale/corrupt`는 차단.
5. `soft stale`와 `degraded`는 분리 신호로 운용한다.
6. 운영 timeframe 기본값은 `1h`이며, `ENABLE_MULTI_TIMEFRAMES=true`에서만 다중 timeframe을 허용한다.

## 4. Phase Roadmap
| Phase | Status | Objective | Exit Condition |
|---|---|---|---|
| A | completed | 수집/복구/상태판정 신뢰성 확보 | A-001~A-019 완료 + Exit Criteria 충족 |
| B | completed | 다중 timeframe 전환 + 1m 비대칭 서빙 + 저장소 제약 내 운영 정합성 확보 | B-001~B-008 종료 (`B-005` sunset 완료, `B-008` sunset scope close) |
| C | active | 장애 전파 범위 축소와 운영 관측성 강화 | `C-010` 포함 핵심 운영 태스크 완료 + 동작 불변 회귀 근거 확보 |
| D | backlog | 모델 진화의 "운영 안전성" 확보(자동화 자체가 목적 아님) | D-001~D-005 핵심 게이트(인터페이스/메타데이터/shadow 비교/승격 차단) 확립 + 롤백 경로 검증 |

## 4.1 Phase C Operations Baseline (Locked)
1. worker 역할 분리는 `worker-ingest`/`worker-publish` 2-service를 기본으로 유지한다.
2. cadence는 `UTC boundary + detection gate`를 기본 실행 규칙으로 유지한다.
3. publish 실행은 ingest watermark advance를 기준으로 판단한다.
4. monitor 대사 기준은 `symbol+timeframe` 고정이며, `PRIMARY_TIMEFRAME`에만 legacy fallback을 허용한다.
5. orchestrator 변경(`C-010`)은 동작 변경 없는 책임 경계 명확화를 원칙으로 한다.
6. 장애 시 fallback은 poll loop 회귀보다 먼저 원인 격리/관측 증거 수집을 우선한다.

## 4.2 Phase D Model Coverage Baseline (Locked)
1. 기본 커버리지는 `timeframe-shared champion`으로 시작한다(전 심볼 공통).
2. `symbol+timeframe dedicated`는 기본값이 아니라 승격 결과로만 도입한다.
3. dedicated 승격 조건:
   - 최소 샘플/평가 구간 게이트 통과
   - shared 대비 성능 개선 증거 확보
   - 학습/추론 비용이 운영 예산 범위 내
4. serving fallback 체인:
   - dedicated -> shared -> `insufficient_data` 차단
5. dedicated 실패를 shared로 조용히 대체하지 않는다. 실패 상태/사유를 노출해 운영 정직성을 유지한다.
6. 관련 정책 상세는 `D-2026-02-13-32`, 구현 단위는 `D-011`에서 관리한다.

## 4.3 Runtime Cadence Baseline (Locked)
1. 다중 timeframe 실행 주기는 `UTC candle boundary`를 기준으로 한다.
2. 실행 직전 `new closed candle detection gate`를 적용해 신규 데이터가 없으면 cycle을 skip한다.
3. 구현 순서는 `C-006(boundary scheduler) -> C-007(detection gate)`를 유지한다.
4. 계측은 `C-002`를 선행 조건으로 유지한다(실행시간/overrun/missed boundary).
5. 장애 시 rollback은 고정 poll 루프로 즉시 회귀 가능해야 한다.

## 5. Phase B Completion Summary
1. endpoint sunset(`B-005`)은 `410` tombstone + 오너 확인 기반 운영 검증으로 완료 처리했다.
2. admin 대시보드 확장(`B-007`)은 manifest-first 운영 뷰 기준으로 완료했다.
3. FE visibility gate(`B-008`)는 FE 미구축 + sunset 맥락에서 `scope close`로 종료했다.
4. Phase B 상세 이력은 `docs/archive/phase_b/*`를 단일 출처로 사용한다.

## 6. Next Cycle (Recommended)
1. `C-013` 수행: `pipeline_worker.py` timeboxed micro-refactor(함수 1~2개, 동작 불변)
2. `C-004` 수행: 모델 학습 잡 분리 초안 정렬(운영 경로와 자원 경합 최소화)
3. `D-001` 수행: 모델 인터페이스 계약(`fit/predict/save/load`) 고정

## 7. Portfolio Capability Matrix (Current vs Next)
| Capability | Current Evidence | Next Strengthening |
|---|---|---|
| 사용자 플레인 안정 서빙(SSG) | 정적 JSON + `/status` + fallback sunset(`410`) | availability probe 자동화/리포팅 정교화 |
| 상태 정직성(fresh/stale/hard/corrupt) | API/monitor 공통 evaluator + timeframe-aware consistency | alert miss 집계 자동화 |
| 장애 신호 분리(`soft stale` vs `degraded`) | prediction health + 상태전이 알림 | 단계별 실패 시그널 세분화 |
| 수집 복구/무결성 | gap detect/refill + ingest_state/watermark 경계 | 장주기 재시작/복구 리허설 표준화 |
| 실행 비용 통제 | boundary+detection gate + runtime metrics | 장주기 TF 비용 편차 분석 자동화 |

## 8. Current Risk Register (Top)
1. `TD-020`: 스케줄링/실행 비용 및 정합성 리스크
2. `TD-024`: 단계별 부분 실패 알림 세분화 미완료
3. `TD-027`: `1m` hybrid 경계 재활성화 시 정책/구현 재정렬 필요
4. `TD-009`: dev push 즉시 배포 구조로 인한 운영 실수 영향 확대 리스크

## 9. Change Rules
1. 정책 변경은 `docs/DECISIONS.md`를 먼저 갱신한다.
2. 실행 우선순위 변경은 `docs/TASKS_MINIMUM_UNITS.md`와 동기화한다.
3. 새 기술 부채는 `docs/TECH_DEBT_REGISTER.md`에 기록한다.
4. Archive append는 Phase 종료 시점 또는 명시 요청 시 수행한다.
