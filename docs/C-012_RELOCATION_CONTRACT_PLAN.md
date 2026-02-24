# C-012 Relocation Contract Plan

- Last Updated: 2026-02-20
- Task: `C-012` (디렉토리/파일 재배치 계획 수립, 런타임 계약 보존 전제)
- Status: Draft locked for execution handoff

## 1. Objective and Scope
1. 목적: 재배치 시 운영 장애를 막기 위해 `compose/Docker/import` 계약을 먼저 고정한다.
2. 범위: 이번 문서는 "계획 + 검증/롤백 절차"만 다룬다. 코드/경로 이동은 수행하지 않는다.
3. 비목표:
1. 실제 디렉토리 이동
2. 새 아키텍처 강제 도입
3. 런타임 동작 변경

## 2. Runtime Contract Map (Compose)
| Service | Runtime Entry | Must Exist In Image | Host Mount Contract | Break Condition |
|---|---|---|---|---|
| `worker-ingest` | `python -u -m scripts.worker_ingest` | `/app/scripts/worker_ingest.py`, `/app/scripts/pipeline_worker.py`, `/app/workers/*`, `/app/utils/*` | `./models:/app/models`, `./static_data:/app/static_data` | `scripts.worker_ingest` 경로 변경 시 compose command/worker Docker COPY 동시 갱신 누락 |
| `worker-publish` | `python -u -m scripts.worker_publish` | `/app/scripts/worker_publish.py`, `/app/scripts/pipeline_worker.py`, `/app/workers/*`, `/app/utils/*` | `./models:/app/models`, `./static_data:/app/static_data` | publish wrapper import 경로 또는 env 주입 순서 변경 |
| `monitor` | `python -u -m scripts.status_monitor` | `/app/scripts/status_monitor.py`, `/app/utils/prediction_status.py`, `/app/utils/config.py` | `./static_data:/app/static_data` | `scripts.status_monitor`/`utils` 경로 변경 후 Docker COPY 누락 |
| `fastapi` | `gunicorn api.main:app ...` | `/app/api/main.py`, `/app/utils/*` | `./static_data:/app/static_data` | `api.main` 모듈 경로 변경 시 gunicorn target 미수정 |
| `streamlit` | `streamlit run admin/app.py` | `/app/admin/app.py`, `/app/admin/manifest_view.py`, `/app/utils/*` | (none) | `admin/app.py` 경로 또는 `admin.manifest_view` import 경로 변경 누락 |
| `nginx` | static serving | `/etc/nginx/conf.d/default.conf`, `/usr/share/nginx/html/static/*` | `./static_data:/usr/share/nginx/html/static:ro` | 정적 산출물 경로 변경 후 nginx volume/conf 불일치 |

## 3. Build Contract Map (Docker + CI)
| Build Target | Build Context | Copy Contract | Entrypoint/CMD Contract | Break Condition |
|---|---|---|---|---|
| `docker/Dockerfile.worker` | `.` | `COPY scripts/`, `COPY utils/`, `COPY workers/`, `COPY docker/entrypoint_worker.sh` | `ENTRYPOINT /usr/local/bin/entrypoint_worker.sh`, default `CMD python -u -m scripts.pipeline_worker` | 소스 경로 이동 후 COPY/ENTRYPOINT/CMD 불일치 |
| `docker/Dockerfile.fastapi` | `.` | `COPY . /app` | `gunicorn api.main:app` | `api`/`utils` 모듈 경로 변경 시 실행 타깃 불일치 |
| `docker/Dockerfile.streamlit` | `.` | `COPY utils/ /app/utils`, `COPY admin/ /app/admin` | `streamlit run admin/app.py` | `admin` 또는 `utils` 재배치 후 COPY 누락 |

Supplement:
1. `.github/workflows/deploy.yml`에서 세 Docker image 모두 `context: .` 고정.
2. `docker-compose.yml`은 서버에서 image pull 후 command override로 role 분리 실행.

## 4. Import Contract Map (Python Module Path)
| Entry Module | Critical Import Contract | Relocation Constraint |
|---|---|---|
| `scripts.worker_ingest` | `os.environ` 세팅 후 `from scripts.pipeline_worker import run_worker` | wrapper 경로를 바꾸면 compose command와 함께 갱신해야 함 |
| `scripts.worker_publish` | `WORKER_EXECUTION_ROLE`, `WORKER_PUBLISH_MODE` 주입 후 `run_worker` import | import 이전 env 주입 순서 보존 필요 |
| `scripts.status_monitor` | `from utils.prediction_status import evaluate_prediction_status` | `utils` 재배치 시 monitor 경로 동시 수정 필요 |
| `api.main` | `from utils.prediction_status import evaluate_prediction_status` | `utils` 이동 시 API status 경로 영향 |
| `admin.app` | `from admin.manifest_view import ...` | streamlit CMD 경로 + admin import 경로 동시 유지 필요 |
| `scripts.pipeline_worker` | `from workers import ingest/export/predict`, `from utils.*` | `workers`/`utils` 이동은 고위험 변경으로 분리 시행 필요 |

Notes:
1. 현재 `scripts`, `workers`, `utils`, `api`, `admin`은 상위 패키지 경로 계약을 직접 사용한다.
2. `python -m scripts.<entrypoint>` 실행 모델을 깨면 compose command가 전부 영향받는다.

## 5. Staged Relocation Strategy (No Big-Bang)
### Stage 0: Baseline Freeze (Required)
1. 기준선 테스트 고정: `PYENV_VERSION=coin pytest -q`
2. compose 계약 스냅샷: `docker compose config`
3. 핵심 엔트리포인트 존재 검증: `scripts/worker_ingest.py`, `scripts/worker_publish.py`, `scripts/status_monitor.py`, `api/main.py`, `admin/app.py`

### Stage 1: Low-Risk Preparation
1. "실행 엔트리포인트 파일 이동 금지" 규칙 유지.
2. 변경 허용 범위는 비엔트리 헬퍼부터 시작한다.
3. 이동이 필요한 경우 기존 경로에 compatibility shim을 먼저 둔다.

### Stage 2: Medium-Risk Moves (One Unit Per Task)
1. 단위 원칙: 한 태스크에서 한 묶음만 이동한다.
2. 한 묶음 변경 시 수정 허용 파일:
1. 실제 이동 대상 파일
2. 해당 파일을 import하는 최소 호출점
3. 관련 테스트
3. worker 도메인(`workers/*`) 이동은 `scripts/pipeline_worker.py`와 동시 대규모 변경 금지.

### Stage 3: High-Risk Moves (Last)
1. 엔트리포인트(`scripts/worker_*`, `scripts/status_monitor.py`, `api/main.py`, `admin/app.py`) 이동은 마지막에 수행.
2. 이 단계에서만 Dockerfile `COPY`, runtime command, CI build contract를 함께 수정한다.
3. Stage 3는 `C-013` 안정화 이후 착수한다.

## 6. Verification Gate per Stage
1. Static check:
1. `python -m compileall api utils scripts workers admin tests`
2. Test gate:
1. `PYENV_VERSION=coin pytest -q`
3. Contract gate:
1. `docker compose config`
2. (필요 시) `docker build -f docker/Dockerfile.worker .`
3. (필요 시) `docker build -f docker/Dockerfile.fastapi .`
4. (필요 시) `docker build -f docker/Dockerfile.streamlit .`
4. Runtime smoke (배포 환경):
1. `GET /status/BTC/USDT?timeframe=1h`
2. `GET /static/manifest.json`
3. monitor 컨테이너 로그에 import/runtime error 없음 확인

## 7. Rollback Runbook (Path Change Incident)
### R1. Pre-deploy rollback
1. 재배치 변경 파일만 즉시 원복한다.
2. `PYENV_VERSION=coin pytest -q`로 회귀 확인.
3. `docker compose config`가 정상 파싱되는지 재확인한다.

### R2. Post-deploy rollback
1. 서버에서 최신 compose 파일 기준 이전 정상 이미지 태그를 재배포한다.
2. `docker compose --env-file .env.prod up -d`로 재기동한다.
3. `/status` + static manifest + monitor 알림을 1 cycle 관찰한다.

### R3. Failsafe
1. 원인 격리 전 추가 재배치 작업은 중단한다.
2. 실패 원인은 `docs/DISCUSSION.md`에 관찰 사실/가설로 분리 기록한다.

## 8. C-012 Exit Checklist
1. compose runtime 계약 맵 문서화 완료
2. Docker/CI build 계약 맵 문서화 완료
3. import 계약 맵 문서화 완료
4. 단계별 검증 게이트 정의 완료
5. 단계별 롤백 절차 정의 완료

Conclusion:
1. `C-012`의 done condition(계약 맵 + 단계별 롤백/검증 확정)을 문서로 충족한다.
2. 실제 코드 재배치는 `C-013` 이후 작은 단위 태스크로 분할 수행한다.
