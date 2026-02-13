# Coin Predict Living Plan (Hybrid)

- Last Updated: 2026-02-13
- Owner: Backend/Platform
- Status: Active
- Full Phase A History: `docs/archive/phase_a/PLAN_LIVING_HYBRID_PHASE_A_FULL_2026-02-12.md`

## 1. Plan Intent
1. 이 문서는 "현재 실행 기준"만 유지한다.
2. 과거 진행 로그와 상세 회고는 Archive에서 관리한다.
3. 계획 변경은 실패가 아니라 리스크 제어 활동으로 취급한다.

## 2. Current State
1. Phase A(Reliability Baseline): Completed (2026-02-12)
2. Phase B(Timeframe Expansion): Ready
3. Phase C(Scale and Ops): Ready
4. Phase D(Model Evolution): Backlog

## 3. Fixed Invariants
1. 우선순위: Stability > Cost > Performance.
2. Source of Truth: InfluxDB.
3. 사용자 데이터 플레인: SSG(static JSON).
4. `soft stale`는 경고 허용, `hard_stale/corrupt`는 차단.
5. `soft stale`와 `degraded`는 분리 신호로 운용.
6. Phase B 전 운영 timeframe은 `1h` 고정.

## 4. Phase Roadmap
| Phase | Status | Objective | Exit Condition |
|---|---|---|---|
| A | completed | 수집/복구/상태판정 신뢰성 확보 | A-001~A-019 완료 + Exit Criteria 충족 |
| B | ready | 다중 timeframe 전환 + 1m 비대칭 서빙 + 저장소 제약 내 운영 정합성 확보 | B-001~B-004, B-006 완료 + `1m` 예측 비서빙/ hybrid(`latest closed 180`) 경계 확정 + `1m` rolling(`14d default / 30d cap`) 적용 + Hard Gate+Accuracy 정책 확정 + API/monitor 상태 계약 유지 + `B-005` sunset 조건 충족 여부 확정 |
| C | ready | 장애 전파 범위 축소와 운영 관측성 강화 | `C-002` 관측 증거 확보 + `R-004` kickoff 확정 + (`C-005` 또는 대안) 구현으로 장애 격리 효과 검증 |
| D | backlog | 모델 진화의 "운영 안전성" 확보(자동화 자체가 목적 아님) | D-001~D-005 핵심 게이트(인터페이스/메타데이터/shadow 비교/승격 차단) 확립 + 롤백 경로 검증 |

## 4.1 Phase D Model Coverage Baseline (Locked)
1. 기본 커버리지는 `timeframe-shared champion`으로 시작한다(전 심볼 공통).
2. `symbol+timeframe` dedicated는 "기본값"이 아니라 "승격 결과"로만 도입한다.
3. dedicated 승격 조건:
   - 최소 샘플/평가 구간 게이트 통과
   - shared 대비 성능 개선 증거 확보
   - 학습/추론 비용이 운영 예산 범위 내
4. serving fallback 체인:
   - dedicated -> shared -> `insufficient_data` 차단
5. dedicated 실패를 shared로 조용히 대체하지 않는다. 실패 상태/사유를 노출해 운영 정직성을 유지한다.
6. 관련 정책 상세는 `D-2026-02-13-32`, 구현 단위는 `D-011`에서 관리한다.

## 5. Rebaseline Focus (Pre-Phase B)
1. Phase A 이전에 작성된 B/C/D 태스크는 구현 중 드러난 리스크를 충분히 반영하지 못했을 가능성을 전제로 한다.
2. Phase A 실행 결과(태스크 증가, 우선순위 변경)를 기준으로 B/C/D 전체를 다시 점검한다.
3. 이번 Rebaseline의 목표는 "완벽한 예측"이 아니라 "현재 시점에서 최대한 완결된 실행 기준선"을 만드는 것이다.
4. Rebaseline은 아래 4가지 질문에 답해야 완료로 본다.
   - 각 Phase 목적/Exit 조건이 지금도 타당한가?
   - 각 Task는 지금 아는 리스크를 반영해 충분히 세분화되었는가?
   - 우선순위는 실제 리스크/의존성/운영비 기준으로 재정렬되었는가?
   - Phase B kickoff에 필요한 최소 묶음(실행+검증+롤백)이 확정되었는가?
5. `R-001`~`R-004`는 완료됐으나, 신규 리스크(`D-2026-02-13-29`) 반영으로 `B-001` 정책 잠금 후 `B-002 -> B-003` 착수로 기준선을 보정한다.

## 6. Rebaseline Protocol (Execution)
1. 목적 재검증(`R-001`, 완료): B/C/D의 Objective/Exit Condition을 다시 정의한다.
2. 태스크 재세분화(`R-002`, 완료): 각 태스크에 `why/failure mode/verification/rollback`을 추가한다.
3. 우선순위 재정렬(`R-003`, 완료): Option A/B를 비교하고 안정성 우선 기준으로 Option A를 채택한다.
4. 착수 게이트 확정(`R-004`, 완료): kickoff 구현 묶음을 `B-002 -> B-003`으로 고정하고, 검증/롤백 경계를 확정한다.

## 7. Next Cycle (Recommended)
1. `B-001`: timeframe tier 정책 매트릭스 잠금(1m 비대칭 + `latest closed 180` + `14d/30d` + Hard Gate+Accuracy)
2. `B-003`: timeframe-aware export 전환(`1m` prediction 비생성 포함)
3. `B-004`: manifest 생성(심볼/타임프레임 최신 상태 요약)
4. `B-006`: 저장소 예산 가드 + retention/downsample 실행
5. `C-002`: 실행시간/실패율 메트릭 수집(Phase C 착수 근거)
6. `D-011` 설계 착수: model coverage matrix + fallback resolver 구현 기준 세분화

## 8. Portfolio Capability Matrix (Current vs Next)
| Capability | Current Evidence | Next Strengthening |
|---|---|---|
| 사용자 플레인 안정 서빙(SSG) | 정적 JSON + nginx 분리, freshness 상태 노출 | availability 지표화(`R-005`) |
| 상태 정직성(fresh/stale/hard/corrupt) | `/status` 및 monitor 공통 evaluator 운용 | 경고 노출 정책의 FE 계약 명문화(`B-005`) |
| 장애 신호 분리(`soft stale` vs `degraded`) | prediction health 및 상태전이 알림 적용 | alert miss 측정 체계(`R-005`) |
| 수집 복구/무결성 | gap detect/refill, ingest cursor 상태 저장 | 장주기 중단 복구 시나리오 운영 검증(`C-002`) |
| 배포 전 품질 게이트 | CI `pytest` 선행 후 배포 | 운영 승인 게이트 분리(후속 태스크화 필요) |

## 9. Current Risk Register (Top)
1. `TD-018`: API-SSG 운영 계약 최종 확정 전까지 경계 혼선 가능
2. `TD-019`: 단일 worker 결합으로 장애 전파 가능
3. `TD-020`: 고정 poll loop로 비용/정합성 리스크
4. `TD-024`: 단계별 부분 실패 알림 세분화 미완료
5. `1m` 예측 경로를 그대로 확장할 경우 candle 경계 내 완료 실패(오버런) 리스크
6. Free Tier 50GB 제약에서 다중 심볼 `1m` 장기 보관 시 디스크 고갈 리스크
7. `1M` 등 장기 TF에서 샘플 부족 상태로 모델 판단/서빙이 왜곡될 리스크

## 10. Change Rules
1. 정책 변경은 `docs/DECISIONS.md`를 먼저 갱신한다.
2. 실행 우선순위 변경은 `docs/TASKS_MINIMUM_UNITS.md`와 동기화한다.
3. 새 기술 부채는 `docs/TECH_DEBT_REGISTER.md`에 기록한다.
4. Archive append는 Phase 종료 시점 또는 명시 요청이 있을 때만 수행한다.
