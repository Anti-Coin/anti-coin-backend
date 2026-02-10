import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_json(
    path: str | Path, payload: Any, indent: int | None = None
) -> None:
    """
    JSON을 저장하다가 죽어도 파일이 깨지지 않게 만듦(안전 장치)
    json.dump() 대신 사용
    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        dir=str(file_path.parent), prefix=f".{file_path.name}.", text=True
    )
    try:
        with os.fdopen(fd, "w") as temp_file:
            json.dump(payload, temp_file, indent=indent)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, file_path)
        os.chmod(file_path, 0o644)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
