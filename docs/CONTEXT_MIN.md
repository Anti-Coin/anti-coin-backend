# Coin Predict Context (Minimum)

- Last Updated: 2026-02-19
- Purpose: 새 세션에서 최소 토큰으로 현재 상태를 정렬하기 위한 요약

## 1. Snapshot
1. Phase A(Reliability Baseline)는 2026-02-12에 완료했다.
2. Phase B(Timeframe Expansion)는 2026-02-19에 완료했다.
3. 현재 활성 실행 구간은 Phase C(ops/maintainability)이며, Phase D는 backlog다.
4. 운영 현실은 Oracle Free Tier ARM + 단일 운영자다.

## 2. Phase B Summary (Archived)
1. `B-005` 완료: `/history`/`/predict` sunset(`410`) + 오너 확인 기반 fallback 비의존 운영 확인.
2. `B-007` 완료: admin manifest-first 대시보드 확장.
3. `B-008` 완료(`sunset scope close`): FE 미구축 상태에서 종료, FE 재개 시 재오픈.
4. 상세 원문: `docs/archive/phase_b/*`

## 3. Phase C Detailed Baseline
1. 실행 기준: `boundary + detection gate` cadence 유지(`D-2026-02-13-33`).
2. worker 경계: `worker-ingest`/`worker-publish` 2-service + ingest watermark 기반 publish gate 유지(`D-2026-02-17-38`).
3. 대사 기준: monitor Influx-JSON consistency는 `symbol+timeframe` 고정, `PRIMARY_TIMEFRAME`에만 legacy fallback 허용(`D-2026-02-19-40`).
4. 현재 핵심 태스크:
   - `C-001`: 심볼 확장 자동화 경계 확정
   - `C-003`: 정적/상태 경로 부하 테스트 시나리오 정비
   - `C-012`: 디렉토리/파일 재배치 계획 수립(런타임 계약 보존 전제)
5. `C-010` 완료 근거(2026-02-19):
   - ingest_state 즉시 커밋 vs ingest watermark 지연 커밋 경계를 코드 helper로 명시화.
   - characterization test(커밋 경계/blocked_storage_guard/실패 시 watermark 비전진) 추가.
   - 기준선 회귀: `PYENV_VERSION=coin pytest -q` 통과(`118 passed`) + 운영 smoke 확인.

## 4. Phase D Detailed Strategy
1. 기본 모델 커버리지는 `timeframe-shared champion`으로 시작한다(`D-2026-02-13-32`).
2. dedicated 도입은 승격 조건(최소 샘플/성능 개선/비용 허용) 충족 시에만 허용한다.
3. fallback 체인은 `dedicated -> shared -> insufficient_data`로 고정한다.
4. 실패 은닉 금지: dedicated 실패를 shared로 조용히 대체하지 않고 상태/사유를 노출한다.
5. Phase D 핵심 착수 축:
   - `D-001`/`D-002`: 인터페이스/메타데이터 표준
   - `D-003`/`D-004`/`D-005`: shadow 비교/승격 게이트
   - `D-010`/`D-011`: 장기 TF 샘플 gate + coverage/fallback resolver

## 5. Non-Negotiables
1. 우선순위: Stability > Cost > Performance.
2. No silent failure, Idempotency first, UTC internally.
3. Soft stale은 경고와 함께 노출 가능, hard_stale/corrupt는 차단.

## 6. Serving Boundary
1. Source of Truth는 InfluxDB다.
2. 사용자 데이터 플레인은 SSG(static JSON)다.
3. `/status`는 운영 신호 및 프론트 경고 노출에 사용 가능하다.
4. `/history`, `/predict`는 sunset tombstone(`410`)이며 정상 운영 경로가 아니다.

## 7. Current Risk Focus
1. `TD-020`: 스케줄링/실행 비용 및 정합성 리스크
2. `TD-024`: 단계별 부분 실패 알림 세분화 미완료
3. `TD-027`: `1m` hybrid 경계 재활성화 시 정책/구현 재정렬 필요
4. `TD-009`: dev push 즉시 배포 구조로 인한 운영 실수 영향 확대 리스크

## 8. Deep References
1. 현재 운영 결정: `docs/DECISIONS.md`
2. 현재 로드맵/다음 단계: `docs/PLAN_LIVING_HYBRID.md`
3. 활성 태스크 보드: `docs/TASKS_MINIMUM_UNITS.md`
4. 과거 원문 이력: `docs/archive/README.md`
