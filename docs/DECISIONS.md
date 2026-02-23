# Coin Predict Decision Register (Active)

- Last Updated: 2026-02-23
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
| D-2026-02-13-34 | Reconciliation + Derived Guard | 내부 mismatch 즉시 critical, 외부 mismatch는 3회 연속 critical, `1d/1w/1M` direct ingest 금지 | 외부 warning 과다, direct ingest 우회 긴급 이슈 |
| D-2026-02-13-35 | `1h` Underfill Guard Position | `underfill -> rebootstrap` guard는 임시 containment, RCA 전 제거 금지 | guard 재트리거 빈도 증가, 관찰 창 종료 |
| D-2026-02-17-37 | `C-008` RCA Result | legacy fallback을 no-timeframe row로 제한해 cross-timeframe 오염 차단 | guard 재트리거가 운영 허용치 초과 |
| D-2026-02-17-38 | Worker Split + Publish Gate | `worker-ingest`/`worker-publish` 2-service + ingest watermark gate 고정 | publish backlog/자원 병목/워터마크 경합 반복 |
| D-2026-02-19-39 | Freshness Thresholds | `1w/1M` threshold 고정, `4h`는 legacy compatibility 유지 | `1w/1M` 경보 과소/과다, `4h` 비사용 근거 확정 |
| D-2026-02-19-40 | Monitor Consistency Scope | monitor consistency는 `symbol+timeframe`, legacy fallback은 `PRIMARY_TIMEFRAME`만 허용 | query 비용 임계 초과, 오탐/누락 재발 |
| D-2026-02-19-41 | SLA-lite Baseline | availability/alert-miss/MTTR-stale 공식 + 일간 rollup/주간 review 고정 | monitor 이벤트 영속화 도입, 사고 빈도 증가 |
| D-2026-02-20-46 | Long-Stale Escalation | `*_escalated` 이벤트 + `MONITOR_ESCALATION_CYCLES` 기준, monitor는 alert-only 유지 | escalation 알림 과다/과소, poll cadence 변경 |
| D-2026-02-20-47 | Standalone Training Boundary | 학습은 `worker-train` one-shot 경계로 분리, 자동 재학습/승격은 D 후속 태스크로 분리 | 수동 학습 빈도 급증, 학습-운영 자원 경합 재발 |
| D-2026-02-20-48 | Phase C Archive Boundary | Phase C 상세는 archive 단일 출처, active 문서는 요약 유지, 우선순위는 Phase D로 고정 | Phase C 재개 필요 운영 이슈 발생 |
| D-2026-02-21-49 | pipeline_worker Decomposition | config/guards/scheduling을 별도 모듈로 분리, 상태 관리/ctx 래퍼는 D-001 후 후속 수행 | 분해 후 테스트 실패 발생, 또는 D-001 설계 시 상태 레이어 필요 확정 |
| D-2026-02-21-50 | Phase D Plan Audit | Immediate Bundle을 `D-010→Direct Fetch→D-012→D-001→D-002`로 재정렬, D-001 scope을 "계약 명시화"로 축소, D-003은 3개 서브태스크로 분해 예정 | 실행 중 선후관계 오류 발견, 또는 D-001 설계 시 추상 인터페이스 필요성 재확인 |
| D-2026-02-21-51 | 1d/1w/1M Direct Fetch 전환 | downsample 경로 폐기, 모든 TF를 거래소 direct fetch로 통일, downsample_lineage 코드 제거 | direct fetch 데이터 계약 위반(누락/지연/갭) 반복 확인, 또는 거래소 API 장기 TF 제공 중단 |
| D-2026-02-23-52 | 1d/1w/1M Full-Fill 복구 방침 | InfluxDB 1d/1w/1M 데이터 삭제 + `ingest_state.json` cursor 제거로 `bootstrap_exchange_earliest` 재진입 유도. 코드 수정(자동 재감지) 대신 운영 조치 선택(단순한 해법 우선 원칙) | 동일 증상 재발(신규 TF 추가 시), 또는 운영 조치 빈도 증가 시 자동 감지 코드 도입 재검토 |
| D-2026-02-23-53 | 방어 로직 구조 판정 | 방어 메커니즘 자체는 정당(silent failure 금지 철학의 필수 파생). 문제는 구조 분산이며 D-016/D-017에서 상태 관리 분리 + ctx 래퍼 해소로 개선. 방어 수 축소는 하지 않음 | D-016/D-017 실행 시점, 또는 방어 분기 추가로 `pipeline_worker.py` 3000줄 초과 시 |

## 3. Decision Operation Policy
1. 활성 문서는 요약만 유지한다(상세 서술 금지).
2. 상세 원문은 `docs/archive/*`에 append-only로 보존한다.
3. 신규 결정 추가 시:
   - active에는 요약 행을 추가한다.
   - 상세 본문은 해당 phase archive 문서에 추가한다.
4. phase 종료 시 `DECISIONS/PLAN/TASKS` 원문을 archive로 스냅샷하고 active는 요약 상태로 되돌린다.
