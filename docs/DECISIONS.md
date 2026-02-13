# Coin Predict Decision Register (Active)

- Last Updated: 2026-02-13
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

### D-2026-02-13-29
- Date: 2026-02-13
- Status: Accepted
- Topic: Phase B Timeframe Asymmetry + Storage Guard Baseline
- Context:
  - Rebaseline 이후 재검토에서 Phase B 기준선에 `1m` 특수성(짧은 캔들 주기 대비 예측 실행시간)과 저장소 제약(Oracle Free Tier 50GB) 정책이 충분히 명시되지 않았음이 확인됐다.
  - 이 상태로 `B-002`/`B-003`을 먼저 진행하면, 구현은 빨라도 서빙/보존/예측 경계가 다시 뒤집혀 재작업 가능성이 높다.
- Decision:
  - `1m`은 Phase B 기준에서 prediction 비서빙을 기본값으로 한다(향후 명시 승인 시에만 확장).
  - `1m` 사용자 노출은 hybrid(SSG + API latest window)로 설계하며, API 범위는 `최신 closed 180캔들(약 3시간)` 고정으로 시작한다(임의 range 조회 미허용).
  - `1m` 보존은 rolling 정책을 필수로 하며, `기본 14일`과 `상한 30일`을 고정하고 `B-006`에서 실행한다.
  - `1d/1w/1M`은 `1h` 기준 downsample 경로를 기본 후보로 하며, source/검증식을 `B-001`에서 고정한다.
  - 장기 timeframe은 최소 샘플 미달 시 prediction을 차단하고 `insufficient_data` 신호를 노출한다(`D-010`).
  - 실행 순서는 `B-001 -> B-002 -> B-003`로 보정하며, `B-001` 잠금 전 `B-002`/`B-003` 착수는 보류한다.
- Consequence:
  - 단기 구현 속도는 늦어지지만, 잘못된 전제 위 구현으로 인한 재작업/운영사고 리스크를 줄인다.
  - `R-004`는 폐기되지 않으며, 신규 선행조건(`B-001`)이 추가된 형태로 해석된다.
- Revisit Trigger:
  - `1m` prediction 필요성이 제품 요구로 명시되거나, 실제 디스크/실행시간 관측이 가정과 크게 다를 때

### D-2026-02-13-30
- Date: 2026-02-13
- Status: Accepted
- Topic: Serving Policy - Hard Gate + Accuracy Signal
- Context:
  - 사용자 요청에 따라 서빙 정책은 "차단 기준(안전)"과 "품질 신호(설명)"를 분리할 필요가 있다.
  - 정확도 신호만으로 차단을 결정하면 regime 변화/표본 부족 구간에서 오판 가능성이 크다.
- Decision:
  - 서빙 정책은 `Hard Gate + Accuracy Signal` 2층 구조로 운용한다.
  - Hard Gate 조건(`serve 금지`): `corrupt`, `hard_stale`, `insufficient_data`, `incomplete_bucket`.
  - Accuracy Signal(`serve 가능 + 경고/표시`): `mae`, `smape`, `directional_accuracy`, `sample_count`, `evaluation_window`.
  - 정확도는 Hard Gate를 우회하지 못한다(정확도가 높아도 hard 상태면 차단).
- Consequence:
  - 데이터 무결성/신뢰성 기준을 유지하면서, 사용자에게 예측 품질 정보를 투명하게 제공할 수 있다.
  - 지표 계산/표시 비용이 추가되며, 표준 스키마가 필요하다.
- Revisit Trigger:
  - FE 계약 변경, 지표 산식 변경, 또는 정확도 지표 노이즈가 과도할 때

### D-2026-02-13-31
- Date: 2026-02-13
- Status: Accepted
- Topic: B-001 Open Questions Lock (Retention / Evaluation Window / Reconciliation)
- Context:
  - `docs/TIMEFRAME_POLICY_MATRIX.md`의 Open Questions 3개가 미고정 상태로 남아 있어, `B-002/B-003` 착수 시 정책 드리프트 가능성이 있었다.
  - 사용자 확인 결과 심볼 확장은 점진적이며, 오래된/유명 심볼 중심으로 운영할 계획이다.
- Decision:
  - `1h` retention은 `365d` 기본, `730d` 상한으로 고정한다.
  - evaluation window와 최소 샘플은 timeframe별로 분리 고정한다:
    - `1h`: `rolling_30d`, min sample `240`
    - `1d`: `rolling_180d`, min sample `120`
    - `1w`: `rolling_104w`, min sample `52`
    - `1M`: `rolling_36M`, min sample `24`
  - reconciliation은 동일 거래소/동일 심볼 기준으로 수행한다.
  - 내부 downsample deterministic 검증은 `0 tolerance`로 적용한다.
  - 운영 주기는 `daily quick(24h)`, `weekly deep(90d)`로 고정한다.
  - `incomplete_bucket/missing bucket`은 즉시 `critical`, 동일 bucket mismatch 3회 연속 시 `critical`로 상향한다.
- Consequence:
  - Phase B 실행 기준이 수치 수준까지 고정되어 구현 중 정책 재역전 가능성을 줄인다.
  - 대사/품질 기준이 엄격해져 초기 경보량이 늘 수 있으나, 데이터 신뢰성 요구를 우선 충족한다.
- Revisit Trigger:
  - 실제 디스크 성장률이 예상과 크게 다르거나, 경보 노이즈가 운영 임계치를 넘을 때

### D-2026-02-13-32
- Date: 2026-02-13
- Status: Accepted
- Topic: Phase D Model Coverage Strategy (Tiered Coverage + Fallback Chain)
- Context:
  - Symbol/Timeframe별 전용 모델을 일괄 도입하면 Free Tier 자원과 운영 복잡도 기준에서 초기 실패 확률이 높다.
  - 제품 목표는 "모든 모델 자동화" 자체가 아니라, 운영 가능한 AIOps 역량과 근거를 축적하는 것이다.
  - 사용자 확인 기준상 심볼 확장은 점진적으로 진행되며, 초기에는 오래된/대표 심볼 중심 운영이 예상된다.
- Decision:
  - Phase D 기본 커버리지는 `timeframe-shared champion`으로 시작한다(전 심볼 공통 경로).
  - `symbol+timeframe` 전용 모델은 아래 조건을 모두 만족할 때만 승격한다.
    - 최소 샘플/평가 윈도우 게이트 통과
    - shared 대비 성능 개선(사전 정의한 지표 임계치) 입증
    - 학습/추론 비용이 운영 예산 범위 내
  - 서빙 fallback 체인은 아래 순서로 고정한다.
    - dedicated(`symbol+timeframe`) -> shared(`timeframe`) -> `insufficient_data` 차단
  - dedicated 모델 실패 시 hard 상태를 숨기지 않으며, 조용한 shared 대체로 실패를 은닉하지 않는다(상태/사유 노출).
  - 모델 메타데이터(`D-002`)에 `coverage_scope`, `fallback_parent`, `promoted_by_gate_at` 필드를 필수로 추가한다.
- Consequence:
  - 단기에는 모델 다양성보다 운영 안정성과 재현성을 우선 확보한다.
  - 전용 모델 확장은 느리지만, 승격/롤백 근거가 명확해져 포트폴리오 설명 가능성이 높아진다.
- Revisit Trigger:
  - 심볼 수/트래픽이 예상보다 빠르게 증가하거나, shared 모델의 장기 품질 저하가 반복될 때

### D-2026-02-13-33
- Date: 2026-02-13
- Status: Accepted
- Topic: Multi-Timeframe Cycle Cadence - Boundary + Detection Gate Hybrid
- Context:
  - 다중 timeframe(`1h/1d/1w/1M`)과 다중 symbol 조합에서는 고정 poll while-loop가 cycle overrun을 유발하기 쉽다.
  - 단순 boundary-only는 불필요 실행을 줄이지 못하고, detection-only는 경계 누락/중복 실행 리스크가 있다.
- Decision:
  - 실행 주기는 `timeframe boundary`를 기준으로 고정한다(UTC, closed-candle 기준).
  - 실행 직전 `data detection gate`를 적용한다.
    - 해당 `symbol+timeframe`의 최신 closed candle이 이전 실행과 동일하면 ingest/predict/export를 skip.
    - 신규 closed candle이 확인될 때만 cycle을 수행한다.
  - 단계적 구현 순서는 `C-006(boundary scheduler) -> C-007(detection gate)`로 고정한다.
  - 장애 시 rollback은 기존 고정 poll 루프로 즉시 회귀한다.
- Consequence:
  - 경계 정합성을 유지하면서 불필요 cycle을 줄여 overrun/비용 리스크를 동시에 완화한다.
  - gate 판정 오류가 있으면 누락/지연이 발생할 수 있으므로 계측(`C-002`)이 필수다.
- Revisit Trigger:
  - `overrun_rate`가 7일 기준 1%를 초과하거나, `missed_boundary`가 관측될 때
  - 거래소 지연/스키마 변경으로 gate 오탐이 반복될 때

## 3. Decision Operation Policy
1. Archive로 이동된 결정은 `Section 1`에 요약 형태로만 유지한다.
2. 아직 archive로 이동하지 않은 결정은 `Section 2`에 상세 형태로 유지한다.
3. 새 결정은 먼저 `Section 2`에 상세 기록한다.
4. Archive append는 Phase 종료 시점 또는 명시 요청이 있을 때만 수행한다.
5. Archive 이동 후에는 `Section 1` 요약을 유지하고, 상세 본문은 archive 파일을 단일 출처로 사용한다.
