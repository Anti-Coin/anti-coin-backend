# Coin Predict Decision Register (Active)

- Last Updated: 2026-02-12
- Scope: archive 연동형 의사결정 레지스터 (요약/상세 분리)
- Full History: `docs/archive/phase_a/DECISIONS_PHASE_A_FULL_2026-02-12.md`

## 1. Archived Decisions (Summary)
| ID | Topic | Current Rule | Revisit Trigger |
|---|---|---|---|
| D-2026-02-10-01 | Ingest Strategy | Hybrid 수집(단기/장기 분리) 유지 | Timeframe 정책 변경 시 |
| D-2026-02-10-02 | Freshness Policy | soft stale 경고 노출 허용, hard_stale/corrupt 차단 | 도메인 변경 시 |
| D-2026-02-10-03 | Admin Boundary | `admin/app.py`는 개발자 점검 도구로 한정 | 운영 경로 통합 요구 시 |
| D-2026-02-10-07 | Monitoring | 별도 monitor 프로세스로 상태전이 알림 운용 | 알림 채널/규칙 변경 시 |
| D-2026-02-10-09 | Data Authority | Source of Truth는 InfluxDB, JSON은 파생 산출물 | 저장소 구조 변경 시 |
| D-2026-02-10-10 | Prediction Time Axis | 예측 시작 시점은 timeframe 경계(UTC) 고정 | timeframe 확장 시 |
| D-2026-02-12-12 | Frontend Separation | 제품 FE는 Vue/React 계열, Streamlit은 운영 점검용 | 제품 FE 전략 변경 시 |
| D-2026-02-12-13 | Runtime Guard | Phase B 전 `INGEST_TIMEFRAMES=1h` 고정 | Phase B 진입 시 |
| D-2026-02-12-14 | Serving Plane | 사용자 기본 경로는 SSG, `/history`/`/predict`는 fallback | `B-005` 수행 시 |
| D-2026-02-12-18 | Prediction Failure Policy | prediction은 저장 유지, 실패 시 last-good + degraded 노출 | 실패 정책 변경 시 |
| D-2026-02-12-19 | Signal Semantics | `soft stale`(경고)와 `degraded`(실패 신호) 분리 | 상태 모델 변경 시 |
| D-2026-02-12-20 | Phase Gate | Phase C 구현은 Phase A 신뢰성 베이스라인 후 진행 | 게이트 기준 변경 시 |
| D-2026-02-12-21 | Status Consistency | API/monitor는 공통 evaluator를 사용 | 다중 timeframe 판정 확장 시 |
| D-2026-02-12-22 | Query Verification | `stop: 2d`는 운영 스모크체크로 검증 | 쿼리 정책 변경 시 |
| D-2026-02-12-23 | Status Exposure | degraded는 `/status` 필드로 노출 | 운영 API 경계 변경 시 |
| D-2026-02-12-24 | Re-alert Policy | soft/hard unhealthy 상태 3사이클 재알림 | 노이즈 과다/누락 시 |
| D-2026-02-12-25 | Maintainability | 복잡 분기에는 의도 주석 + 상태전이 로그 우선 | 코드 리뷰 비용 증가 시 |

## 2. Non-Archived Decisions (Detailed)
### D-2026-02-12-26
- Date: 2026-02-12
- Status: Accepted
- Topic: Rebaseline Gate
- Context:
  - Phase A 이전에 작성된 B/C/D 태스크는 구현 중 발견된 리스크를 충분히 반영하지 못했을 가능성이 있다.
  - Phase A 실행 과정에서 실제 태스크 수와 우선순위가 초기 가정과 달라졌고, 이 상태로 Phase B에 진입하면 계획-실행 불일치가 반복될 수 있다.
- Decision:
  - Phase B 구현 착수 전, B/C/D 전체를 대상으로 Rebaseline 게이트를 적용한다.
  - Rebaseline 범위는 `목적/Exit 조건`, `태스크 세분화`, `교차 의존성`, `우선순위 재정렬`을 포함한다.
  - `R-001`~`R-004` 완료 전에는 B/C 구현 태스크를 설계/검증 준비 단계로 제한한다.
- Consequence:
  - 초기 계획 과신을 줄이고, 현재 사실 기반의 실행 기준선으로 다음 사이클을 시작할 수 있다.
  - 선행 정렬 비용이 증가하지만, 중간에 대규모 우선순위 역전이 반복될 리스크를 줄인다.
- Revisit Trigger:
  - Rebaseline 프로토콜 또는 Phase kickoff 기준 변경 시

### D-2026-02-12-27
- Date: 2026-02-12
- Status: Accepted
- Topic: Rebaseline Priority Baseline (`R-003`)
- Context:
  - `R-001`, `R-002` 완료 후 실제 구현 순서(Phase B 선행 vs Phase C 선행)에 대한 선택이 필요했다.
  - 우선순위 원칙은 `Stability > Cost > Performance`이며, 사용자는 `B-005`를 P2로 유지하길 원했다.
- Decision:
  - `R-003` 결과로 Option A(phase-ordered stability)를 기준선으로 채택한다.
  - 실행 순서는 `R-004 -> B-002 -> B-003 -> B-004 -> C-002 -> C-005 -> C-006 -> R-005 -> B-005(P2)`를 기본으로 한다.
  - Option B(cost-first)는 `C-002` 관측 결과에서 비용 압력이 즉시 임계 수준으로 확인될 때만 fallback으로 사용한다.
- Consequence:
  - B 경계를 먼저 고정해 C/D 재작업 리스크를 줄인다.
  - 단기 비용 최적화 체감은 늦어질 수 있으나, 운영 경계 안정성을 우선 확보한다.
- Revisit Trigger:
  - `C-002` 결과에서 cycle overrun/비용 압력이 심각하게 확인되거나, B 작업이 장기 지연될 때

### D-2026-02-12-28
- Date: 2026-02-12
- Status: Accepted
- Topic: Phase B Kickoff Contract (`R-004`)
- Context:
  - `R-003`로 우선순위 기준선(Option A)은 정해졌지만, 실제 구현 착수 단위(1~2개)와 검증/롤백 경계가 미고정 상태였다.
  - Rebaseline의 완료 조건은 "Phase B kickoff 최소 묶음(실행+검증+롤백) 확정"이며, 이를 고정하지 않으면 재기준화 효과가 약해진다.
- Decision:
  - kickoff 구현 묶음은 `B-002`와 `B-003` 두 태스크로 고정한다.
  - 실행 순서는 `B-002` 선행, `B-003` 후행으로 고정한다.
  - `B-002`는 파일명 규칙 테스트와 legacy fallback 유지를 검증 경계로 두고, 실패 시 legacy 우선 read로 회귀한다.
  - `B-003`는 다중 timeframe export 충돌 부재와 산출물 필드/시각 일관성을 검증 경계로 두고, 실패 시 `1h` 단일 export로 회귀한다.
- Consequence:
  - Phase B 착수 범위가 과확장되지 않고, 실패 시 복귀 경로가 명시된 상태로 진행할 수 있다.
  - `C-005`, `C-006` 착수는 `B-003` 검증 증거 확보 이후로 지연되어 단기 비용 최적화 체감은 늦어질 수 있다.
- Revisit Trigger:
  - `B-002` 또는 `B-003`에서 rollback이 2회 이상 반복되거나, 예상보다 큰 API/monitor 계약 충돌이 확인될 때

## 3. Decision Operation Policy
1. Archive로 이동된 결정은 `Section 1`에 요약 형태로만 유지한다.
2. 아직 archive로 이동하지 않은 결정은 `Section 2`에 상세 형태로 유지한다.
3. 새 결정은 먼저 `Section 2`에 상세 기록한다.
4. Archive append는 Phase 종료 시점 또는 명시 요청이 있을 때만 수행한다.
5. Archive 이동 후에는 `Section 1` 요약을 유지하고, 상세 본문은 archive 파일을 단일 출처로 사용한다.
