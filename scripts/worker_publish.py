"""
Publish-role worker entrypoint.

Why this tiny wrapper exists:
- 동일 이미지/코드에서 환경변수만으로 실행 역할을 고정해 운영 단순성을 유지한다.
- docker compose에서 명령만 바꿔 ingest/publish 프로세스를 분리할 수 있다.
- import 전에 env를 주입해야 pipeline_worker의 module-level 설정이 올바르게 계산된다.
"""

import os


def main() -> None:
    """
    publish role 환경을 고정한 뒤 공용 run_worker를 실행한다.

    Called from:
    - docker compose service `worker-publish` command entrypoint
    """
    # publish worker는 ingest를 실행하지 않고, watermark를 기준으로
    # predict/export만 수행한다.
    os.environ["WORKER_EXECUTION_ROLE"] = "predict_export"
    os.environ["WORKER_PUBLISH_MODE"] = "predict_and_export"
    from scripts.pipeline_worker import run_worker

    run_worker()


if __name__ == "__main__":
    main()
