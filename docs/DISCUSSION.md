# Coin Predict Discussion Log

- Last Updated: 2026-02-24
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

## 8. Entry 2026-02-24 — 상태파일 중심 파이프라인 재구성 및 Projector 단순화
1. Topic: 상태파일/방어분기 축소를 위한 근본 원인 기반 재구성
2. Observed Facts:
   1. `ingest_state.json`의 cursor/status는 ingest 단계에서 즉시 파일 커밋된다.
   2. `ingest/predict/export watermarks`는 cycle 종료 시점에 파일 커밋된다.
   3. publish-only worker는 매 cycle 시작 시 `symbol_activation`과 `ingest_watermarks`를 파일에서 재로딩한다.
   4. `manifest.json`은 publish(export stage) 이후 생성되며 admin 대시보드의 1차 소스다.
   5. `prediction_health.json`은 predict 성공/실패 전이를 저장하며 `/status` degraded 신호의 근거다.
   6. `runtime_metrics.json`은 ingest role에서만 기록되는 운영 관측 파일이다.
3. Core Finding:
   1. 복잡성의 핵심은 "파일 개수"보다 "동일 사실의 다중 표현"이다.
   2. 예시: ingest 진행 사실이 `ingest_state`와 `ingest_watermark`로 이원화되어 있다.
4. Decision:
   1. `poll_loop=60`만으로 self-heal을 즉시 제거할 수 없다(현행 watermark gate 구조상 artifact 누락을 일반 경로에서 흡수하지 못함).
   2. self-heal 제거는 projector 전환 이후 branch collapse로 수행한다.
   3. 상태 소유권 원칙을 `one fact = one owner = one persisted representation`으로 고정한다.
5. Follow-up (Task 승격):
   1. `D-022`: publish 비대칭 스케줄러 전환(ingest=boundary, publish=poll_loop 60s)
   2. `D-023`: projector decision 함수 도입(그림자 모드)
   3. `D-024`: publish 실행 경로 projector 전환 + self-heal 분기 흡수
   4. `D-025`: watermark 상태파일/게이트 함수 제거
   5. `D-026`: cross-worker 순서 레이스 회귀 테스트 고정
6. Reference:
   1. `docs/PROJECTOR_REDUCTION_MAP.md`
7. Revisit Trigger:
   1. projector shadow 결과와 기존 gate 판단의 불일치가 임계치를 넘을 때
   2. 전환 후 `overrun_rate`가 기준선 대비 악화될 때

## 9. Entry 2026-02-24 — 직렬 pipeline 재평가(운영 headroom 기준)
1. Topic: split vs serial 재비교와 실행 경로 재잠금
2. Observed Facts:
   1. 코드 기준으로 실행 역할은 단일값이 아니다. `WORKER_EXECUTION_ROLE`은 `all/ingest/predict_export`, `WORKER_PUBLISH_MODE`는 `predict_and_export/predict_only/export_only`를 사용한다.
   2. 엔트리포인트(`worker_ingest`, `worker_publish`, `worker_predict`, `worker_export`)는 동일 `run_worker`를 role/mode 조합으로 다르게 고정해 호출한다.
   3. 최근 운영 관측은 cycle 대부분 10초대, 간헐 30초대이며 target cycle은 60초다.
   4. 현재 통증 지점은 연산 과부하보다 cross-worker 순서 레이스와 상태 동기화 복잡도에서 반복 관측된다.
3. Re-evaluation:
   1. 현 시점 headroom에서는 split의 장점(장애 격리/오버런 완화)보다 serial의 장점(인과 순서 고정/상태 단순화)이 우세하다.
   2. 단, 장애 격리 요구가 다시 커지면 split 경로 재도입이 합리적이다.
4. Decision:
   1. 기본 실행 경로는 직렬 pipeline 전환으로 잠근다(`D-2026-02-24-56`).
   2. projector bundle(`D-022~D-026`)은 hold로 전환하고 reference 자산으로 유지한다(`D-2026-02-24-57`).
   3. 전환은 즉시 대체가 아니라 최소 단위 태스크(`D-027~D-031`)로 단계 진행한다.
5. Follow-up (Task 승격):
   1. `D-027`: 직렬 pipeline 설계/가드레일 잠금
   2. `D-028`: runtime headroom 7일 계측 잠금
   3. `D-029`: 직렬 실행 경로 전환(feature flag)
   4. `D-030`: 직렬 경로 상태/분기 축소
   5. `D-031`: 롤백 리허설 + 순서 레이스 회귀 테스트
6. Revisit Trigger:
   1. 7일 관측에서 `overrun_rate` 악화 또는 `p95_cycle_seconds > 45`
   2. 장애 격리 요구(운영/배포 경계)가 재상승할 때

## 10. Entry 2026-02-24 — D-030 serial 경로 분기 축소 적용
1. Topic: serial publish 경로의 watermark/self-heal 분기 축소
2. Observed Facts:
   1. split 경로의 복잡성 핵심은 publish gate 비교(ingest vs predict/export watermark) + gate skip 시 self-heal 분기 누적이다.
   2. serial 경로에서는 ingest와 publish가 동일 cycle 인과 체인으로 실행되어 cross-worker 순서 레이스가 없다.
3. Decision:
   1. serial 경로에서는 publish 판단을 `ingest watermark 존재` 단일 기준으로 단순화한다.
   2. serial 경로에서 gate skip 기반 self-heal 분기는 비활성화한다.
   3. split 경로의 기존 gate/self-heal 동작은 rollback 자산으로 유지한다.
4. Evidence:
   1. 회귀: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py` 통과
5. Revisit Trigger:
   1. serial 경로에서 artifact 누락 장기화 또는 중복 publish가 관측될 때

## 11. Entry 2026-02-24 — 삭제 우선 단순화 태스크 재구성
1. Topic: "추가보다 삭제" 원칙으로 직렬 경로 잔존 복잡도 제거
2. Observed Facts:
   1. 운영 기본 경로는 직렬(ingest in-cycle publish)이지만, 코드에는 `WORKER_EXECUTION_ROLE`/`WORKER_PUBLISH_MODE` 매트릭스 분기가 잔존한다.
   2. compose 기본 기동은 `worker-ingest` 단일 경로이며 `worker-publish`는 `legacy-split` profile에만 남아 있다.
   3. `_run_publish_timeframe_step`는 serial 경로 외에 split 전용 gate/self-heal 분기를 계속 보유해 함수 인지 부하가 높다.
   4. 상태파일은 `ingest/predict/export watermarks` 3종을 유지하지만, serial 실행에서는 사실상 ingest 인과 체인이 publish 판단의 기준이다.
   5. `pipeline_worker -> workers/*` 위임이 완료됐어도 `_ctx()` + pass-through wrapper 다수가 테스트 호환성 때문에 잔존한다.
3. Core Finding:
   1. 현재 복잡성의 큰 축은 "안전 가드 자체"가 아니라 "rollback 호환 분기와 중복 표현 유지 비용"이다.
   2. 따라서 단순화는 신규 추상화 추가가 아니라, 검증 가능한 순서로 분기/파일을 삭제하는 방식이 맞다.
4. Decision:
   1. 삭제는 한 번에 하지 않고 `D-032 -> D-033 -> D-034 -> D-035 -> D-036 -> D-037` 순서로 진행한다.
   2. `D-031`(롤백 리허설) 완료 전에는 split 제거를 시작하지 않는다.
   3. 불변식은 유지한다: 오노출 0, fail-closed, runtime 비열화.
5. Follow-up (Task 승격):
   1. `D-032`: 삭제 전환 게이트 잠금(직렬 단일 경로 고정)
   2. `D-033`: role/mode 실행 매트릭스 삭제
   3. `D-034`: 직렬 플래그/legacy profile 삭제
   4. `D-035`: split 전용 publish gate/self-heal 코드 삭제
   5. `D-036`: split 전용 watermark 상태파일/저장 계층 삭제
   6. `D-037`: 미사용 워커 엔트리포인트 제거
6. Revisit Trigger:
   1. 삭제 단계에서 `overrun_rate` 악화 또는 artifact 복구 지연이 관측될 때
   2. 장애 격리 요구로 publish 전용 프로세스 재도입 필요성이 상승할 때

## 12. Entry 2026-02-24 — D-034 직렬 경로 하드락 적용
1. Topic: serial 경로를 feature flag/profile 없이 유일 실행 계약으로 고정
2. Observed Facts:
   1. `D-029`의 `PIPELINE_SERIAL_EXECUTION_ENABLED`는 전환 안전장치로는 유효했지만, 삭제 단계에서는 분기 복잡도만 남긴다.
   2. compose의 `legacy-split` profile(`worker-publish`)은 실운영 기본 경로가 아니며, 유지 시 재활성화 실수 여지를 남긴다.
3. Decision:
   1. `scripts/worker_config.py`에서 serial flag를 제거한다.
   2. `scripts/pipeline_worker.py`는 serial 여부를 런타임 토글이 아닌 ingest stage 고정 경로로 해석한다.
   3. `docker-compose.yml`에서 `legacy-split` profile/`worker-publish` 서비스를 제거한다.
4. Evidence:
   1. 회귀: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py` (`64 passed`)
5. Revisit Trigger:
   1. 직렬 경로에서 overrun/복구 지연이 임계치를 넘거나, 장애 격리 요구가 재상승할 때
