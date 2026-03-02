# Coin Predict Decision Register (Active)

- Last Updated: 2026-02-26
- Scope: 활성 결정 요약 + archive 원문 링크
- Full Phase A History: `docs/archive/phase_a/DECISIONS_PHASE_A_FULL_2026-02-12.md`
- Full Phase B History: `docs/archive/phase_b/DECISIONS_PHASE_B_FULL_2026-02-19.md`
- Full Phase C History: `docs/archive/phase_c/DECISIONS_PHASE_C_FULL_2026-02-20.md`

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

## 2. Current Baseline Decisions (Summary)
| ID | Topic | Current Rule | Revisit Trigger |
|---|---|---|---|
| D-2026-02-13-32 | Phase D Coverage Strategy | 기본은 `timeframe-shared champion` 단일화. `symbol+timeframe dedicated` 승격은 당분간 보류(Free Tier 인프라 OOM 방지 및 운영 제약 우선 고려) | shared 품질 저하 반복 및 인프라(RAM) 증설 또는 최적화 완료 시 |
| D-2026-02-13-33 | Cycle Cadence | `UTC boundary + detection gate` 하이브리드 고정 | `overrun_rate` 상승 또는 `missed_boundary` 재발 |
| D-2026-02-13-34 | Reconciliation + Derived Guard | 내부 mismatch 즉시 critical, 외부 mismatch는 3회 연속 critical. `1d/1w/1M` direct ingest 금지 규칙은 `D-2026-02-21-51`에서 direct fetch 허용으로 대체됨(legacy decision trace). | 외부 warning 과다, 데이터 계약/대사 정책 재정의 필요 시 |
| D-2026-02-13-35 | `1h` Underfill Guard Position | `underfill -> rebootstrap` guard는 임시 containment, RCA 전 제거 금지 | guard 재트리거 빈도 증가, 관찰 창 종료 |
| D-2026-02-17-37 | `C-008` RCA Result | legacy fallback을 no-timeframe row로 제한해 cross-timeframe 오염 차단 | guard 재트리거가 운영 허용치 초과 |
| D-2026-02-17-38 | Worker Split + Publish Gate | 당시 baseline은 `worker-ingest`/`worker-publish` 2-service + ingest watermark gate였다. 현재 실행 방향은 `D-2026-02-24-56` 직렬 전환으로 대체됨(legacy decision trace). | 직렬 전환 실패, 또는 자원 경합/장애 격리 요구로 split 재도입 필요 시 |
| D-2026-02-19-39 | Freshness Thresholds | `1w/1M` threshold 고정, `4h`는 legacy compatibility 유지 | `1w/1M` 경보 과소/과다, `4h` 비사용 근거 확정 |
| D-2026-02-19-40 | Monitor Consistency Scope | monitor consistency는 `symbol+timeframe`, legacy fallback은 `PRIMARY_TIMEFRAME`만 허용 | query 비용 임계 초과, 오탐/누락 재발 |
| D-2026-02-19-41 | SLA-lite Baseline | availability/alert-miss/MTTR-stale 공식 + 일간 rollup/주간 review 고정 | monitor 이벤트 영속화 도입, 사고 빈도 증가 |
| D-2026-02-20-46 | Long-Stale Escalation | `*_escalated` 이벤트 + `MONITOR_ESCALATION_CYCLES` 기준, monitor는 alert-only 유지 | escalation 알림 과다/과소, poll cadence 변경 |
| D-2026-02-20-47 | Standalone Training Boundary | 학습은 `worker-train` one-shot 경계로 분리, 자동 재학습/승격은 D 후속 태스크로 분리 | 수동 학습 빈도 급증, 학습-운영 자원 경합 재발 |
| D-2026-02-20-48 | Phase C Archive Boundary | Phase C 상세는 archive 단일 출처, active 문서는 요약 유지, 우선순위는 Phase D로 고정 | Phase C 재개 필요 운영 이슈 발생 |
| D-2026-02-21-49 | pipeline_worker Decomposition | config/guards/scheduling을 별도 모듈로 분리, 상태 관리/ctx 래퍼는 D-001 후 후속 수행 | 분해 후 테스트 실패 발생, 또는 D-001 설계 시 상태 레이어 필요 확정 |
| D-2026-02-21-50 | Phase D Plan Audit | 당시 기준 Immediate Bundle(`D-010→Direct Fetch→D-012→D-001→D-002`)을 고정했다. 현재 실행 묶음은 `D-2026-02-24-56/57`에 따라 직렬 전환 체인(`D-027→D-028→D-029→D-030→D-031`)으로 재잠금됐고, `D-022~D-026`은 hold 상태다(legacy trace). | 실행 중 선후관계 오류 발견, 또는 D-001 설계 시 추상 인터페이스 필요성 재확인 |
| D-2026-02-21-51 | 1d/1w/1M Direct Fetch 전환 | downsample 경로 폐기, 모든 TF를 거래소 direct fetch로 통일, downsample_lineage 코드 제거 | direct fetch 데이터 계약 위반(누락/지연/갭) 반복 확인, 또는 거래소 API 장기 TF 제공 중단 |
| D-2026-02-23-52 | 1d/1w/1M Full-Fill 복구 방침 | 1차 대응으로 운영 조치(InfluxDB 1d/1w/1M 정리 + `ingest_state.json` cursor 제거)를 선택했다. 이후 `D-020` 완료로 자동 재감지 가드가 반영되어 본 결정은 legacy trace로 유지한다(`D-2026-02-24-64`). | full-fill 판단 정책/허용 오차(`FULL_BACKFILL_TOLERANCE_HOURS`) 변경 필요 시 |
| D-2026-02-23-53 | 방어 로직 구조 판정 | 방어 메커니즘 자체는 정당(silent failure 금지 철학의 필수 파생). 문제는 구조 분산이며 D-016/D-017에서 상태 관리 분리 + ctx 래퍼 해소로 개선. 방어 수 축소는 하지 않음 | D-016/D-017 실행 시점, 또는 방어 분기 추가로 `pipeline_worker.py` 3000줄 초과 시 |
| D-2026-02-24-54 | Publish Simplification Direction | split+projector 경로 기준선으로 기록한다. 현재 active 경로는 `D-2026-02-24-56/57`(직렬 전환)이며 본 결정은 hold reference로 유지한다. | 직렬 전환 실패 또는 split 경로 재개 필요 시 |
| D-2026-02-24-55 | State Reduction Boundary | watermark 3종 축소 경계는 split+projector 경로의 감축 규칙으로 유지한다. 현재는 `D-2026-02-24-57`에 따라 hold reference 상태다. | 직렬 경로가 폐기되거나 onboarding/degraded 정책이 변경될 때 |
| D-2026-02-24-56 | Serial Pipeline Direction | 우선순위(`오노출 0 > 운영 단순성 > 복구 지연`)와 운영 관측(대부분 cycle 10초대, 간헐 30초대, target 60초)을 근거로 기본 전환 방향을 직렬 pipeline(ingest->publish in-cycle causal chain)으로 잠근다. | 7일 관측에서 `overrun_rate` 악화, `p95_cycle_seconds > 45`, 또는 장애 격리 요구 재상승 시 |
| D-2026-02-24-57 | Projector Bundle Status | `D-022~D-026` projector 기반 분해/축소 번들은 `hold`로 전환한다. 관련 문서는 rollback/reference 자산으로 유지한다. | 직렬 전환 실패 또는 split+projector 경로 재개 필요 시 |
| D-2026-02-24-58 | Serial Transition Guardrails | `D-029` 실행 전 가드레일을 고정한다. `fail-closed`(오노출 의심 시 해당 심볼/TF publish 차단), cycle 예산(`target=60s`, 전환 보류/롤백 트리거는 `p95_cycle_seconds > 45`), 안정성 임계(`overrun_rate` 7일 기준선 대비 +3%p 초과 시 롤백 검토), 복구 임계(artifact reconcile 2 cycle 초과 실패 시 롤백)로 운영 경계를 잠근다. | cadence 변경, 런타임 프로파일 급변, 또는 장애 격리 요구 재상승 시 |
| D-2026-02-24-59 | Runtime Headroom Measurement Contract | `D-028` 계측 계약을 scheduler-aware로 고정한다. 소스는 `static_data/runtime_metrics.json`(ingest role), 지표 매핑은 `p95_cycle_seconds := summary.p95_elapsed_seconds`, `overrun_rate := summary.overrun_rate`로 통일한다. precondition은 경로별로 분리한다: (A) `poll_loop`면 `WORKER_CYCLE_SECONDS=60`, `RUNTIME_METRICS_WINDOW_SIZE >= 10080`, `summary.samples >= 9000`; (B) `boundary + 1h 포함`이면 `RUNTIME_METRICS_WINDOW_SIZE >= 240`, `summary.samples >= 240`(hourly due 기준 7일 이상 관측 근사). baseline(`overrun_rate_7d_baseline`, `p95_cycle_seconds_7d_baseline`)은 `docs/PLAN_LIVING_HYBRID.md` 5.3에 기록하고, `D-029`는 기록 후에만 진행한다. | scheduler 모드/ingest timeframe 정책 변경, 또는 metrics 파일 포맷 변경 시 |
| D-2026-02-24-60 | Serial Execution Flag Contract (legacy trace) | `D-029` 당시 직렬 전환 리스크를 줄이기 위해 `PIPELINE_SERIAL_EXECUTION_ENABLED` + `legacy-split` rollback 경계를 임시 채택했다. `D-034` 완료로 해당 계약은 retire됐고, 실행 기준은 `D-2026-02-24-63`으로 대체됐다. | 직렬 단일 경로를 재차 단계적 플래그 전환으로 되돌릴 필요가 생길 때 |
| D-2026-02-24-61 | Serial Publish Reconcile Simplification | serial 경로(ingest stage in-cycle publish)에서는 publish 판단을 "ingest watermark 존재 여부" 단일 기준으로 단순화한다. ingest-vs-publish watermark 비교 gate와 publish skip 시 self-heal 분기는 serial 경로에서 비활성화한다. split 전용 분기 삭제는 `D-035`에서 완료한다. | serial 경로에서 artifact 누락 장기화/중복 publish 관측, 또는 reconcile 기준 변경 필요 시 |
| D-2026-02-24-62 | Deletion Gate Lock + Rollback Boundary Shift | `D-032` 기준으로 삭제 진입 게이트를 잠근다. runtime 근거는 `D-028` 기록(`samples=240`, `overrun_rate=0.0`, `p95_cycle_seconds=12.57`)이며 삭제 시작점(`D-033+`)부터 rollback 기본 경계는 split 즉시 복귀가 아니라 배포 롤백(직전 정상 이미지/커밋 재배포)으로 전환한다. | `D-033+` 진행 중 성능/복구 악화 관측, 또는 split 경로 재도입 요구가 재상승할 때 |
| D-2026-02-24-63 | Serial Path Hard Lock | `D-034` 기준으로 `PIPELINE_SERIAL_EXECUTION_ENABLED`와 compose `legacy-split` profile(`worker-publish`)을 제거해 직렬 경로를 유일 실행 계약으로 고정한다. rollback 경로는 split 즉시 복귀가 아닌 배포 롤백(직전 정상 이미지/커밋 재배포)만 사용한다. | 직렬 경로에서 overrun/복구 지연이 임계치를 넘거나, 장애 격리 요구로 split topology 재도입이 필요할 때 |
| D-2026-02-24-64 | D-020 Closure + Full-Fill Re-detection Guard | `D-020`은 운영 복구로 종료하되 재발 방지는 코드 계약으로 잠근다. full-fill TF(`1h/1d/1w/1M`)에서 `db_first > exchange_earliest + tolerance`면 `force_rebootstrap`을 활성화해 exchange earliest부터 재수집하며, boundary detection gate skip 상태여도 backward coverage gap이 감지되면 ingest를 진행한다. | false positive 재부트스트랩 증가, 또는 장주기 TF underfill 재발 시 |
| D-2026-02-26-65 | D-012 Training Execution Policy Lock | `D-012` 실행 기준을 잠근다. 모델 추적은 MLflow `SQLite backend`로 시작하고(file backend 미채택), 학습 결과 반영은 `symbol+timeframe partial-success`를 허용한다. snapshot 산출물은 `latest 1개`만 유지하고, 재현성은 run metadata(`run_id`, `data_range`, `row_count`, `model_version`) 기록으로 보완한다. | Model Registry stage 운영/다중 운영자 감사 요구로 중앙 서버가 필요해질 때, 또는 다중 snapshot 포렌식 요구가 생길 때 |
| D-2026-02-26-66 | Training Snapshot Strategy (On-demand 유지 + Pre-materialize Hold) | 현재 학습 데이터 추출은 `train_model.py` 실행 시점 on-demand extractor를 기본으로 유지한다. 누적 pre-materialize extractor는 `D-038 hold`로 분리하고, 전환은 학습 시간/SLA 압력이 반복될 때만 검토한다. | on-demand 경로에서 학습 시간 SLA 반복 초과, Influx query 비용/실패율 증가, 또는 동일 추출 재사용 요구가 누적될 때 |

## 3. Decision Operation Policy
1. 활성 문서는 요약만 유지한다(상세 서술 금지).
2. 상세 원문은 `docs/archive/*`에 append-only로 보존한다.
3. 신규 결정 추가 시:
   - active에는 요약 행을 추가한다.
   - 상세 본문은 해당 phase archive 문서에 추가한다.
4. phase 종료 시 `DECISIONS/PLAN/TASKS` 원문을 archive로 스냅샷하고 active는 요약 상태로 되돌린다.
