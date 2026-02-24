# Coin Predict Discussion Log

- Last Updated: 2026-02-23
- Purpose: 구현 전 쟁점/가설/옵션을 기록하고, 완료된 phase 토론은 archive로 분리해 active 문서 밀도를 유지한다.
- Full Phase C Discussion History: `docs/archive/phase_c/DISCUSSION_PHASE_C_FULL_2026-02-20.md`

## 1. Operating Rule
1. Discussion은 구현 지시가 아니라 "쟁점 정리 + 관찰 사실 + 옵션 비교"를 기록한다.
2. 구현 결론은 `docs/TASKS_MINIMUM_UNITS.md`에 별도 Task로 승격한 뒤 진행한다.
3. 완료된 phase의 상세 토론은 active 문서에서 제거하고 archive 원문을 단일 출처로 사용한다.

## 2. Entry Template
1. Date
2. Topic
3. Observed Facts
4. Hypotheses
5. Options
6. Recommendation
7. Follow-up Candidates

## 3. Entry 2026-02-20 - Phase C Discussion Archive Boundary
1. Topic: Phase C 토론 로그 경량화
2. Observed Facts:
1. `C-001`~`C-016` 완료 후 active Discussion에 Phase C 상세 로그가 과밀하게 남아 있었다.
2. active 문서의 목적은 "현재 실행 의사결정"이며, 과거 상세 토론은 참조 빈도가 낮다.
3. Decision:
1. Phase C 토론 원문은 `docs/archive/phase_c/DISCUSSION_PHASE_C_FULL_2026-02-20.md`로 고정한다.
2. active `docs/DISCUSSION.md`는 운영 규칙/템플릿/현재 follow-up 중심으로 유지한다.
3. Revisit Trigger:
1. Phase C 범위를 재개하거나 과거 토론 원문 근거가 필요한 경우.

## 4. Active Follow-up Candidates (Phase D)
1. `D-012`: 학습 데이터 SoT 정렬(Influx 기반 closed-candle snapshot)
2. `D-013`: 재학습 트리거 정책(시간+이벤트) 정의
3. `D-014`: 학습 실행 no-overlap/락 가드
4. `D-015`: 학습 실행 관측성/알림 baseline

## 5. Entry 2026-02-23 — 방어 로직 구조 평가
1. Topic: `pipeline_worker.py` 방어/복구 로직의 밀도와 구조
2. Observed Facts:
   1. `resolve_ingest_since`에 7개 분기(경로 결정 전략)가 존재한다.
   2. `_ctx()` 래퍼 ~30개가 `workers/*` 마이그레이션 잔존물로 남아 있다.
   3. symbol activation 상태 처리가 4개 함수에 분산되어 있다.
   4. detection gate, publish gate, storage guard, min sample gate 등 방어 메커니즘은 각각 정당한 역할을 갖는다.
3. Conclusion:
   1. 방어 로직 자체를 줄이는 것은 오답이다. "silent failure 금지" 철학에서 파생된 필수 기능이다.
   2. 느낌의 실체는 "구조 없이 한 파일에 흩어진 배치"에서 오는 인지 부하다.
   3. 개선 방향은 D-016/D-017에서 자연스럽게 다룰 수 있다.
4. Revisit Trigger: D-001 완료 후 리팩터링 시점.

## 6. Entry 2026-02-23 — 1d/1w/1M full-fill 미작동 및 prediction self-heal 연쇄 장애 진단
1. Topic: 장주기 TF 데이터 부족 → prediction 차단 연쇄
2. Observed Facts:
   1. 1d/1w/1M은 lookback(30일) 데이터만 존재하고 exchange earliest까지 full-fill되지 않았다.
   2. `resolve_ingest_since`는 `last_time`이 존재하면 `db_last` 분기로 빠지므로, 기존 lookback 데이터가 있는 한 full-fill 경로에 진입할 수 없다.
   3. 1w/1M min sample(52/24) 미충족 → prediction이 `insufficient_data`로 항상 skip된다.
   4. prediction self-heal은 정상 트리거되지만, `run_prediction_and_save` 내부에서 min sample gate에 의해 차단된다.
   5. 서버 확인: `prediction_health.last_success_at` 존재, 모든 watermark 존재, min sample만 미충족.
3. Root Cause: D-018(direct fetch 전환) 이전에 downsample/lookback으로 들어간 데이터가 `db_last` 분기를 고착시킨 것.
4. Resolution: Bug 1(full-fill) 해결이 prediction 복구까지 연쇄 해결함. → `D-020` 태스크 참조.
5. Revisit Trigger: full-fill 복구 후 1w/1M prediction 파일 정상 생성 확인.

## 7. Entry 2026-02-23 — 환경 변수/상수 밀도 관찰
1. Topic: env var ~26개, Python 상수 ~55개의 관리 비용
2. Observed Facts:
   1. env var 26개는 Docker 배포 환경에서 정당한 수준이다.
   2. Python 상수 ~55개가 `utils/config.py`와 `worker_config.py`에 구조 없이 나열되어 있다.
   3. `worker_config.py`에서 `utils.config` 값을 재노출하는 패턴이 의존성 혼란을 유발한다.
3. Conclusion: D-001 이후 D-016/D-017 리팩터링 시 역할별 그룹화로 자연스럽게 개선 가능.
4. Revisit Trigger: D-016 착수 시.
