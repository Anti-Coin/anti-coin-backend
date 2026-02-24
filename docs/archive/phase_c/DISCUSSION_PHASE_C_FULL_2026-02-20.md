# Coin Predict Discussion Log

- Last Updated: 2026-02-20
- Purpose: 아키텍처/운영 의사결정 전 토론 포인트를 구조적으로 기록하고, 추정이 아닌 근거 기반으로 후속 Task를 분리하기 위한 로그.

## 1. Operating Rule
1. Discussion은 구현 지시가 아니라 "쟁점 정리 + 근거 + 옵션 비교"를 기록한다.
2. 구현이 필요한 결론은 `TASKS_MINIMUM_UNITS`에 별도 Task로 승격한 뒤 진행한다.
3. 항목마다 "관찰 사실"과 "추정"을 분리한다.

## 2. Entry Template
1. Date
2. Topic
3. Observed Facts
4. Hypotheses
5. Options
6. Recommendation
7. Follow-up Candidates

## 3. Entry 2026-02-20 - Stale Alert and Pipeline Coupling
1. Topic: `1d` stale 반복, `1h` 정상, monitor는 탐지만 수행(제어 미수행)

2. Observed Facts:
1. monitor stale 판정은 prediction JSON의 `updated_at` 기반이며, 필요 시 Influx-JSON 갭으로 `hard_stale` 승격한다.
2. publish 실행 트리거는 ingest watermark advance다.
3. ingest 단계에서 detection gate가 skip이면 publish 단계도 현재 cycle에서 건너뛴다.
4. `ingest_state`는 즉시 파일 커밋, `*watermarks`는 cycle 종료 시 파일 커밋이다.
5. `1h`는 경계가 자주 와서 회복 기회가 많고, `1d/1w/1M`은 기회가 적다.

3. Hypotheses:
1. derived timeframe에서 `already_materialized`로 ingest skip이 발생할 때 ingest watermark 동기화가 안 되면, publish가 장시간 실행되지 않아 prediction stale이 누적될 수 있다.
2. worker 재시작/중단 시점에 watermark 파일 반영 타이밍이 어긋나면, 장주기 timeframe의 stale 체류 시간이 길어질 수 있다.

4. Additional Findings:
1. `utils/prediction_status.py`는 non-primary timeframe에도 legacy prediction 파일 fallback 후보를 포함한다. canonical 파일이 없을 때 cross-timeframe 판정 오염 가능성이 있다.
2. monitor는 alert-only 역할이라, 장애 자동복구를 직접 트리거하지 않는다. 이는 단순성은 높지만 복구 지연 리스크가 남는다.

5. Options:
1. Option A (단순 보강): detection gate skip(`already_materialized`) 시점에 ingest watermark를 DB latest로 동기화해 publish starvation을 줄인다.
2. Option B (경계 분리 강화): publish 트리거를 ingest watermark 단일 기준에서 "DB latest + publish cursor" 보조 기준으로 확장한다.
3. Option C (역할 분리 심화): ingest/export/predict를 완전 독립 파이프라인으로 분리하고 이벤트/큐 기반 동기화로 전환한다.

6. Recommendation:
1. 단기: Option A로 starvation 리스크를 줄이고 재현 로그를 확보한다.
2. 중기: legacy fallback을 `PRIMARY_TIMEFRAME`로 제한해 상태 판정 오염을 차단한다.
3. 장기: Option C는 운영 비용/복잡도가 커서 Phase C 말미 또는 Phase D 초입에 재평가한다.

7. Follow-up Candidates:
1. publish starvation 완화: derived TF ingest skip 경로에서 watermark 동기화 규칙 검토.
2. prediction status fallback 경계: non-primary legacy fallback 제한 여부 검토.
3. monitor-control 연계: monitor는 감시 전용 유지, 제어는 별도 runbook/ops task로 분리할지 결정.

8. Taskization Snapshot (2026-02-20):
1. `C-014`(P1): derived TF `already_materialized` skip 시 publish starvation 완화.
2. `C-015`(P1): prediction status fallback을 `PRIMARY_TIMEFRAME` 전용으로 제한.
3. `C-016`(P2): stale 장기 지속 시 재시도/승격(runbook+alert) 정책 명문화.
4. Progress Update (2026-02-20): `C-014` 구현/회귀 완료.
   - `_run_ingest_timeframe_step`에서 `already_materialized` skip + `last_time` 존재 시 ingest watermark를 DB latest로 동기화하고 publish 단계를 허용한다.
   - 검증: `tests/test_pipeline_worker.py`에 skip 경로 회귀 테스트 2건 추가 후 `PYENV_VERSION=coin pytest -q` 통과(`123 passed`).
5. Progress Update (2026-02-20): `C-015` 구현/회귀 완료.
   - `utils/prediction_status.py`에서 legacy prediction fallback을 `PRIMARY_TIMEFRAME` 전용으로 제한했다.
   - 검증: `tests/test_api_status.py`, `tests/test_status_monitor.py`에 non-primary fallback 차단 회귀를 추가했고 `PYENV_VERSION=coin pytest -q` 통과(`125 passed`).

## 4. Entry 2026-02-20 - `pipeline_worker.py` Low-level Maintainability Audit
1. Topic: 코드라인 수가 큰 것이 본질적 문제인지, 또는 저수준 가독성/유지보수 관점에서 실제로 분해가 필요한지

2. Observed Facts:
1. `scripts/pipeline_worker.py`는 2,804 LOC다.
2. 함수/클래스 단위는 총 85개이며, 길이 50라인 이상 8개, 100라인 이상 4개다.
3. 장문 함수는 `run_worker`(280), `_run_ingest_timeframe_step`(206), `_run_publish_timeframe_step`(149), `append_runtime_cycle_metrics`(146)에 집중된다.
4. `C-010`으로 ingest_state 즉시 커밋 vs watermark cycle-end 커밋 경계는 helper로 분리되어 있다.
5. `tests/test_pipeline_worker.py`에 커밋 경계/게이트 분기/watermark 비전진 관련 characterization test가 존재한다.

3. Hypotheses:
1. 현재 코드는 완전한 "스파게티"라기보다, 오케스트레이션 파일에 책임이 과밀된 상태다.
2. 문제의 본질은 단순 LOC보다 "한 파일에서 scheduler/ingest/publish/runtime metrics/파일 커밋 정책을 동시에 변경해야 하는 인지부하"다.
3. 디렉토리 재배치까지 한 번에 수행하면 docker/compose/import 계약 리스크가 커질 수 있다.

4. Options:
1. Option A (유지): 코드 이동 없이 주석/문서만 강화한다.
2. Option B (권장): 동작 불변을 전제로 `pipeline_worker.py` 내부 경계를 추가 추출해 오케스트레이션 중심으로 축소한다.
3. Option C (대규모): 디렉토리 재배치와 파일 분할을 동시에 수행한다.

5. Recommendation:
1. 단기에는 Option B가 가장 안전하다.
2. 규칙은 "행동 변경 금지 + characterization test 선행/동시"로 고정한다.
3. C-012(재배치 계획)와 C-013(저수준 분해)을 분리해, 경로 리스크와 로직 리스크를 동시에 키우지 않는다.

6. Follow-up Candidates:
1. `C-013`: `run_worker`를 오케스트레이션 중심으로 유지하고, stage helper 추출을 추가 수행.
2. `TD-031`: 책임 과밀 부채를 debt register에 명시하고 해소 기준을 테스트와 함께 관리.
3. 함수 길이/분기 밀도 지표를 문서 기준선으로 고정해 회귀를 계량적으로 추적.

## 5. Entry 2026-02-20 - Refactor Necessity vs Overengineering
1. Topic: 현 시점 리팩토링 필요성 재검토(오버엔지니어링 방지)

2. Observed Facts:
1. `C-014`, `C-015`로 stale 관련 즉시 위험은 1차 완화됐다.
2. 현재 활성 목표는 운영 안정성 증빙(Phase C)이며, 전면 구조개편의 즉시 ROI가 낮다.
3. `pipeline_worker.py`는 인지부하가 크지만, 대규모 분해는 회귀 면적을 빠르게 키운다.

3. Decision:
1. `C-016`을 `C-013`보다 우선한다.
2. `C-013`은 대규모 리팩토링이 아니라 timeboxed micro-refactor로 축소한다.
3. timebox(최대 1세션) 초과 시 즉시 중단하고 기능/운영 트랙으로 복귀한다.

4. Guardrails:
1. `C-013` 범위: 상위 인지부하 함수 1~2개 분리만 허용.
2. characterization + `pytest` + runtime smoke를 통과하지 못하면 병합하지 않는다.
3. 리팩토링 목표는 “구조 미학”이 아니라 “변경 통제성과 읽기 쉬움”으로 제한한다.

5. Progress Update (2026-02-20): `C-016` 구현/검증 완료.
1. monitor에 장기 지속 승격 이벤트(`*_escalated`)를 추가하고, `MONITOR_ESCALATION_CYCLES`(default 60) 기준을 도입했다.
2. escalation 이벤트는 repeat보다 우선해 운영자에게 장기 지속 상태를 명시한다.
3. 운영 개입 절차를 `docs/RUNBOOK_STALE_ESCALATION.md`로 고정했다.
4. 검증: `PYENV_VERSION=coin pytest -q tests/test_status_monitor.py` 통과(`21 passed`), 전체 `PYENV_VERSION=coin pytest -q` 통과(`127 passed`).

6. Progress Update (2026-02-20): `C-013` timeboxed micro-refactor 완료.
1. `_run_ingest_timeframe_step`에서 detection gate 처리와 underfill rebootstrap 판단을 helper 2개로 분리했다.
2. 분해 범위는 1세션 내 2 helper로 제한했고, 로직 순서/상태 갱신/로그 의미는 유지했다.
3. 검증: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py` 통과(`52 passed`), 전체 `PYENV_VERSION=coin pytest -q` 통과(`127 passed`).

7. Progress Update (2026-02-20): `C-004` 모델 학습 잡 분리 초안 완료.
1. `worker-train` one-shot service(`ops-train` profile)를 추가해 ingest/publish 루프와 학습 실행 경계를 분리했다.
2. `scripts/train_model.py`에 `--symbols/--timeframes/--lookback-limit` CLI를 도입하고, canonical 모델 저장 + primary legacy 동기화를 고정했다.
3. 검증: `tests/test_train_model.py` 추가 후 `PYENV_VERSION=coin pytest -q tests/test_train_model.py` 통과(`10 passed`), 전체 `PYENV_VERSION=coin pytest -q` 통과(`137 passed`).

## 6. Entry 2026-02-20 - Phase C Archiving and Model-Training Detail Expansion
1. Topic: Phase C 종료 후 활성 문서 경량화 + D 단계 학습 디테일 태스크 추가

2. Observed Facts:
1. `C-001`~`C-016`이 모두 done 상태이며, 활성 문서에 C 상세를 계속 유지하면 읽기 비용이 커진다.
2. `C-004`로 학습 실행 경계(one-shot)는 확보됐지만, 학습 데이터 SoT/트리거/락/관측성은 아직 미완료다.
3. Free Tier 제약상 MLflow/Prefect 도입은 당장 ROI가 낮다.

3. Decision:
1. Phase C 상세 원문은 `docs/archive/phase_c/*`로 보존하고, 활성 문서는 요약본으로 유지한다.
2. 다음 실행 축을 Phase D 활성 작업으로 고정한다.
3. 모델 학습 디테일은 별도 태스크(`D-012`~`D-015`)로 분리한다.

4. Follow-up Candidates:
1. `D-012`: 학습 데이터 SoT 정렬(Influx 기반 snapshot)
2. `D-013`: 재학습 트리거 정책(시간+이벤트) 정의
3. `D-014`: 학습 실행 no-overlap/락 가드
4. `D-015`: 학습 실행 관측성/알림 baseline
