# Coin Predict Decision Register (Active)

- Last Updated: 2026-02-20
- Scope: archive 연동형 의사결정 레지스터 (요약/상세 분리)
- Full Phase A History: `docs/archive/phase_a/DECISIONS_PHASE_A_FULL_2026-02-12.md`
- Full Phase B History: `docs/archive/phase_b/DECISIONS_PHASE_B_FULL_2026-02-19.md`

## 1. Archived Decisions (Summary)
| ID | Topic | Current Rule | Revisit Trigger |
|---|---|---|---|
| D-2026-02-10-01 | Ingest Strategy | Hybrid 수집(단기/장기 분리) 유지 | timeframe 정책 변경 시 |
| D-2026-02-10-02 | Freshness Policy | soft stale 경고 노출 허용, hard_stale/corrupt 차단 | 도메인 변경 시 |
| D-2026-02-10-03 | Admin Boundary | `admin/app.py`는 개발자 점검 도구로 한정 | 운영 경로 통합 요구 시 |
| D-2026-02-10-07 | Monitoring | 별도 monitor 프로세스로 상태전이 알림 운용 | 알림 채널/규칙 변경 시 |
| D-2026-02-10-09 | Data Authority | Source of Truth는 InfluxDB, JSON은 파생 산출물 | 저장소 구조 변경 시 |
| D-2026-02-10-10 | Prediction Time Axis | 예측 시작 시점은 timeframe 경계(UTC) 고정 | timeframe 확장 시 |
| D-2026-02-12-12 | Frontend Separation | 제품 FE는 Vue/React 계열, Streamlit은 운영 점검용 | 제품 FE 전략 변경 시 |
| D-2026-02-12-13 | Runtime Guard | Phase B 전 `INGEST_TIMEFRAMES=1h` 고정 | Phase B 진입 시 |
| D-2026-02-12-14 | Serving Plane (legacy) | SSG primary + fallback endpoint 유지(현재는 `D-2026-02-19-42`로 대체) | fallback 재도입 필요 시 |
| D-2026-02-12-18 | Prediction Failure Policy | prediction 저장 유지, 실패 시 last-good + degraded | 실패 정책 변경 시 |
| D-2026-02-12-19 | Signal Semantics | `soft stale`(경고)와 `degraded`(실패 신호) 분리 | 상태 모델 변경 시 |
| D-2026-02-12-20 | Phase Gate | Phase C 구현은 Phase A 신뢰성 베이스라인 후 진행 | 게이트 기준 변경 시 |
| D-2026-02-12-21 | Status Consistency | API/monitor는 공통 evaluator를 사용 | 다중 timeframe 판정 확장 시 |
| D-2026-02-12-22 | Query Verification | `stop: 2d`는 운영 스모크체크로 검증 | 쿼리 정책 변경 시 |
| D-2026-02-12-23 | Status Exposure | degraded는 `/status` 필드로 노출 | 운영 API 경계 변경 시 |
| D-2026-02-12-24 | Re-alert Policy | soft/hard unhealthy 상태 3사이클 재알림 | 노이즈 과다/누락 시 |
| D-2026-02-12-25 | Maintainability | 복잡 분기에는 의도 주석 + 상태전이 로그 우선 | 코드 리뷰 비용 증가 시 |
| D-2026-02-12-26 | Rebaseline Gate | Phase B 착수 전 B/C/D 재기준화 게이트 적용 | kickoff 기준 변경 시 |
| D-2026-02-12-27 | Rebaseline Priority | Option A(안정성 우선) 기준선 채택 | 비용 압력 임계 관측 시 |
| D-2026-02-12-28 | Phase B Kickoff | `B-002 -> B-003` 검증/롤백 경계 고정 | rollback 반복 시 |
| D-2026-02-13-29 | B Policy Baseline | `1m` 비대칭 정책 + 저장소 가드 | `1m` 제품 요구 변경 시 |
| D-2026-02-13-30 | Serving Policy | Hard Gate + Accuracy Signal 2층 구조 | FE 계약/지표 산식 변경 시 |
| D-2026-02-13-31 | B-001 Open Questions Lock | retention/eval/reconciliation 수치 잠금 | 경보 노이즈/디스크 추세 이탈 시 |
| D-2026-02-17-36 | Symbol Onboarding | full-first + hidden_backfilling gate | 온보딩 비용/디스크 임계 초과 시 |
| D-2026-02-19-42 | Endpoint Sunset | `/history`/`/predict`는 `410 Gone` tombstone | 숨은 호출 의존성 재발 시 |
| D-2026-02-19-43 | B-005 Completion | 오너 확인 기반으로 `B-005 done` 잠금 | `/history`/`/predict` 의존 재발 시 |
| D-2026-02-19-44 | B-008 Closure | FE 미구축 + sunset으로 `scope close` | FE 구축 재개 시 |
| D-2026-02-19-45 | Phase B Archiving | B 원문은 archive, 활성 문서는 요약 유지 | 차기 Phase 종료 시 |

## 2. Non-Archived Decisions (Detailed)
### D-2026-02-13-32
- Date: 2026-02-13
- Status: Accepted
- Topic: Phase D Model Coverage Strategy (Tiered Coverage + Fallback Chain)
- Context:
  - Symbol/Timeframe별 전용 모델 일괄 도입은 Free Tier 자원/운영 복잡도 기준에서 초기 실패 확률이 높다.
  - 목표는 "모든 모델 자동화"가 아니라 운영 가능한 AIOps 역량 증명이다.
- Decision:
  - Phase D 기본 커버리지는 `timeframe-shared champion`으로 시작한다.
  - `symbol+timeframe` dedicated는 승격 조건(최소 샘플/성능 개선/비용 허용)을 만족할 때만 도입한다.
  - fallback 체인은 `dedicated -> shared -> insufficient_data`로 고정한다.
  - dedicated 실패를 조용히 shared로 은닉하지 않고 상태/사유를 노출한다.
- Consequence:
  - 단기 모델 다양성은 줄지만 운영 안정성과 설명 가능성이 높아진다.
- Revisit Trigger:
  - shared 모델 품질 저하 반복 또는 심볼/트래픽 급증 시

### D-2026-02-13-33
- Date: 2026-02-13
- Status: Accepted
- Topic: Multi-Timeframe Cycle Cadence - Boundary + Detection Gate Hybrid
- Context:
  - 고정 poll loop는 다중 timeframe에서 overrun/불필요 실행을 유발한다.
- Decision:
  - 실행 주기는 UTC boundary 기준으로 고정한다.
  - 실행 직전 detection gate를 적용해 신규 closed candle이 없으면 skip한다.
  - 구현 순서는 `C-006 -> C-007`로 고정한다.
  - 장애 시 기존 poll loop로 즉시 rollback 가능해야 한다.
- Consequence:
  - 경계 정합성과 비용 효율을 동시에 개선한다.
- Revisit Trigger:
  - `overrun_rate` 상승 또는 `missed_boundary` 재발 시

### D-2026-02-13-34
- Date: 2026-02-13
- Status: Accepted
- Topic: Reconciliation Mismatch Semantics + Derived Timeframe Ingest Guard
- Context:
  - 내부/외부 mismatch 규칙이 혼재되어 critical 기준이 불명확했다.
- Decision:
  - `internal_deterministic_mismatch`: 1회 발생도 즉시 critical.
  - `external_reconciliation_mismatch`: 단발 warning, 동일 bucket 3회 연속 시 critical.
  - `1d/1w/1M` direct ingest는 금지, `1h` downsample materialization 경로로 고정한다.
- Consequence:
  - 무결성 오류와 외부 대사 차이를 구분해 운영 판단을 명확히 한다.
- Revisit Trigger:
  - 외부 warning 과다 또는 direct ingest 우회 필요 긴급 사건 발생 시

### D-2026-02-13-35
- Date: 2026-02-13
- Status: Accepted
- Topic: `1h` Underfill Guard is Temporary Containment (Not Final Fix)
- Context:
  - underfill 증상 완화를 위해 guard를 넣었지만 RCA는 미완료였다.
- Decision:
  - `underfill -> rebootstrap` guard는 임시 방편(containment)으로 분류한다.
  - RCA 완료 전 guard 제거를 금지한다.
  - RCA 완료 기준(재현/인과 증거, 원인 분류, 영구 수정 또는 유지 근거 문서화)을 요구한다.
- Consequence:
  - 단기 복구성은 높아지지만 재백필 비용 관찰이 필요하다.
- Revisit Trigger:
  - guard 재트리거 빈도 증가 또는 관찰 창 종료 시

### D-2026-02-17-37
- Date: 2026-02-17
- Status: Accepted
- Topic: `C-008` RCA - `1h` underfill 원인 고정 및 guard 수명 결정
- Context:
  - legacy fallback이 타 timeframe row를 오인해 `1h` since 계산을 오염시킬 수 있었다.
- Decision:
  - legacy fallback은 `timeframe` 태그가 없는 row(`not exists r["timeframe"]`)로 제한한다.
  - cross-timeframe 오염 경로를 차단한다.
  - guard는 즉시 제거하지 않고 2차 안전장치로 유지한다.
- Consequence:
  - `1h` 커버리지 계산 오염 가능성을 낮추고 underfill 재발 확률을 줄인다.
- Revisit Trigger:
  - guard 재트리거 추세가 운영 허용치 초과 시

### D-2026-02-17-38
- Date: 2026-02-17
- Status: Accepted
- Topic: `C-005B` Worker File Split + 2-Service Deployment + Ingest-Watermark Publish Gate
- Context:
  - 단일 엔트리 구조는 역할 경계가 불명확해 장애 격리성과 가독성이 낮았다.
- Decision:
  - 엔트리포인트를 ingest/predict/export/publish 파일로 분리한다.
  - 운영 기본은 compose 2-service(`worker-ingest`, `worker-publish`)로 고정한다.
  - publish 트리거는 ingest watermark advance 기반으로 고정한다.
- Consequence:
  - 운영 비용 급증 없이 책임 경계와 장애 전파 통제를 개선한다.
- Revisit Trigger:
  - publish backlog/자원 병목/워터마크 경합이 반복될 때

### D-2026-02-19-39
- Date: 2026-02-19
- Status: Accepted
- Topic: Multi-Timeframe Freshness Threshold Baseline (`1w`/`1M`) + `4h` Legacy Compatibility
- Context:
  - 기본 threshold가 `1h/4h/1d` 중심으로 남아 장주기 TF 기준이 불명확했다.
- Decision:
  - 기본 threshold를 다음으로 고정한다.
    - `1w`: soft `11520m`(8d), hard `23040m`(16d)
    - `1M`: soft `50400m`(35d), hard `100800m`(70d)
  - `4h`는 legacy compatibility로 유지하고 제거는 후속 결정으로 분리한다.
- Consequence:
  - 장주기 TF freshness 판정 일관성이 향상된다.
- Revisit Trigger:
  - `1w/1M` 경보 과소/과다 또는 `4h` 비사용 근거 확정 시

### D-2026-02-19-40
- Date: 2026-02-19
- Status: Accepted
- Topic: Monitor Influx-JSON Consistency Must Be Timeframe-Aware
- Context:
  - 심볼 단위 조회를 timeframe 판정에 재사용해 오탐/누락 가능성이 있었다.
- Decision:
  - monitor Influx latest 조회 기준을 `symbol+timeframe`으로 고정한다.
  - `PRIMARY_TIMEFRAME`에만 legacy(no timeframe tag) row fallback을 허용한다.
  - consistency override 정책은 기존 경계(기본 JSON 판정 + hard limit 초과 승격)를 유지한다.
- Consequence:
  - multi-timeframe 운영의 대사 신뢰도가 높아진다.
- Revisit Trigger:
  - query 비용 임계 초과 또는 오탐/누락 재발 시

### D-2026-02-19-41
- Date: 2026-02-19
- Status: Accepted
- Topic: `R-005` SLA-lite Baseline Lock (`User Plane Availability`)
- Context:
  - 지표는 있었지만 공식/데이터소스/주기가 문서 간 완전히 잠기지 않았다.
- Decision:
  - Availability: `successful_probes / total_probes` (대상: static + `/status`)
  - Alert Miss Rate: `missed_alert_transitions / total_unhealthy_transitions`
  - MTTR-Stale: `avg(recovery_detected_at - hard_stale_detected_at)`
  - Cadence: `daily rollup + weekly review`
- Consequence:
  - 포트폴리오 관점의 운영 지표 경계가 명확해진다.
- Revisit Trigger:
  - monitor 이벤트 영속화 도입 또는 트래픽/사고 빈도 증가 시

### D-2026-02-20-46
- Date: 2026-02-20
- Status: Accepted
- Topic: Monitor Long-Stale Escalation Tier (`C-016`)
- Context:
  - 기존 monitor는 상태전이 + 주기 재알림은 제공했지만, 장기 지속 사건을 명시적으로 승격하지 못했다.
  - 장주기 timeframe에서는 "정상 대기"와 "장기 방치"를 구분하는 운영 기준이 필요했다.
- Decision:
  - monitor에 장기 지속 승격 이벤트를 추가한다.
    - `hard_stale_escalated`, `missing_escalated`, `corrupt_escalated`, `soft_stale_escalated`
  - 승격 기준은 `MONITOR_ESCALATION_CYCLES`(default 60)로 고정하고, repeat보다 우선한다.
  - monitor 역할은 alert-only를 유지하고, 제어는 runbook 수동 개입으로 분리한다.
  - 수동 개입 기준/점검 절차는 `docs/RUNBOOK_STALE_ESCALATION.md`로 고정한다.
- Consequence:
  - 장기 지속 이벤트 인지가 쉬워지고 MTTR 판단 근거가 명확해진다.
  - 자동 제어를 넣지 않아 운영 단순성과 경계 분리를 유지한다.
- Revisit Trigger:
  - escalation 알림 과다/과소 또는 poll cadence 변경(`MONITOR_POLL_SECONDS`) 시

### D-2026-02-20-47
- Date: 2026-02-20
- Status: Accepted
- Topic: Standalone Training Job Boundary (`C-004`)
- Context:
  - 학습 로직이 운영 ingest/publish 루프 내부로 다시 편입되면 `pipeline_worker` 비대화와 자원 경합 리스크가 커진다.
  - 현 단계 목표는 자동 재학습보다 "독립 실행 경계 + 운영 통제 가능성"을 먼저 고정하는 것이다.
- Decision:
  - 학습은 `worker-train` one-shot service(`docker compose --profile ops-train run --rm worker-train`)로 분리한다.
  - `scripts/train_model.py`는 CLI(`--symbols`, `--timeframes`, `--lookback-limit`)를 제공해 대상/비용을 실행 시점에 제한 가능하도록 한다.
  - 모델 저장은 canonical(`model_{symbol}_{timeframe}.json`)을 기본으로 하고, `PRIMARY_TIMEFRAME`에 한해 legacy(`model_{symbol}.json`)를 동시 기록한다.
  - 자동 스케줄/자동 승격은 `D-006`,`D-007`,`D-005`로 분리해 본 태스크에서 도입하지 않는다.
- Consequence:
  - 학습 실행 경계가 명확해져 운영 루프와 책임이 분리된다.
  - 자동화 수준은 낮지만 오버엔지니어링 없이 D 단계 확장 포인트를 보존한다.
- Revisit Trigger:
  - 수동 학습 빈도 증가, 학습-운영 자원 경합 재발, 또는 자동 재학습 요구가 확정될 때

### D-2026-02-20-48
- Date: 2026-02-20
- Status: Accepted
- Topic: Phase C Completion + Archive Boundary
- Context:
  - Phase C 핵심 태스크(`C-001`~`C-016`)가 완료되어 활성 문서에 C 상세를 계속 유지할 실익이 줄었다.
  - 활성 문서 토큰 밀도를 낮추고, 다음 실행 집중축을 Phase D로 명확히 전환할 필요가 있었다.
- Decision:
  - Phase C를 `completed`로 잠그고, `TASKS/PLAN/DECISIONS` 원문을 `docs/archive/phase_c/*`로 보존한다.
  - 활성 문서는 Phase C 요약만 유지하고, 상세 근거는 archive 링크로 참조한다.
  - 현재 실행 우선순위는 Phase D(`D-001`, `D-002`, `D-012`, `D-013`)로 고정한다.
- Consequence:
  - 활성 문서의 읽기 비용이 줄고, 신규 세션에서 D 트랙 집중도가 높아진다.
  - Phase C 재작업이 필요할 때는 archive 원문 참조 후 새 Task ID로 재승격해야 한다.
- Revisit Trigger:
  - 운영 이슈로 Phase C 범위의 재개가 필요해질 때

## 3. Decision Operation Policy
1. archive로 이동된 결정은 요약 형태로만 활성 문서에 유지한다.
2. 새 결정은 활성 문서 `Section 2`에 상세 기록한다.
3. Phase 종료 또는 명시 요청 시 archive append를 수행한다.
4. archive 이동 후 활성 문서는 현재 규칙과 재검토 트리거 중심으로 유지한다.
