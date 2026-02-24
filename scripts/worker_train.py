"""
Train-role worker entrypoint.

Why this wrapper exists:
- 운영 환경에서 `worker` 이미지 재사용을 유지한다.
- 학습 실행을 ingest/publish 루프와 명시적으로 분리한다.
- one-shot 학습 명령을 compose service로 고정한다.
"""

from scripts.train_model import main


if __name__ == "__main__":
    raise SystemExit(main())
