import os


def main() -> None:
    os.environ["WORKER_EXECUTION_ROLE"] = "predict_export"
    os.environ["WORKER_PUBLISH_MODE"] = "predict_only"
    from scripts.pipeline_worker import run_worker

    run_worker()


if __name__ == "__main__":
    main()
