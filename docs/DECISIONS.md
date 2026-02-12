# Coin Predict Decision Register (Active)

- Last Updated: 2026-02-12
- Scope: 현재 유효한 결정만 유지 (원문 히스토리는 Archive 참조)
- Full History: `docs/archive/phase_a/DECISIONS_PHASE_A_FULL_2026-02-12.md`

## 1. Active Decisions
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

## 2. Archive Policy
1. 상세 Context/Consequence 원문은 Archive에서 관리한다.
2. Active 문서에는 현재 동작을 결정하는 규칙만 남긴다.
3. 새 결정 추가 시 Active에 먼저 반영하고, 상세 원문은 Archive에 append한다.
