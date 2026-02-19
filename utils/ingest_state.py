"""
Ingest cursor state store.

Why this exists:
- InfluxDB last timestamp만으로는 재시작/부분 실패 시점의 의도를 충분히 보존하기 어렵다.
- symbol+timeframe 단위 커서를 별도 파일로 유지해 재실행을 idempotent하게 만든다.
- 읽기 실패 시 fail-open 대신 빈 상태로 시작해 워커가 멈추지 않도록 한다.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from utils.file_io import atomic_write_json
from utils.freshness import parse_utc_timestamp
from utils.logger import get_logger

logger = get_logger(__name__)


def _to_utc(dt: datetime) -> datetime:
    """
    datetime을 UTC aware 객체로 정규화한다.

    Called from:
    - `_format_utc`
    """
    # 내부 표준 시간을 UTC로 고정해 timezone 혼선을 제거한다.
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_utc(dt: datetime) -> str:
    """
    datetime을 프로젝트 표준 문자열(`YYYY-MM-DDTHH:MM:SSZ`)로 직렬화한다.

    Called from:
    - `_persist`
    - `upsert`
    """
    return _to_utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class IngestStateEntry:
    symbol: str
    timeframe: str
    last_closed_ts: datetime | None
    status: str
    updated_at: datetime


class IngestStateStore:
    def __init__(self, path: str | Path):
        """
        ingest cursor 저장소를 초기화한다.

        Called from:
        - `scripts.pipeline_worker.run_worker` 시작 시 1회
        """
        self._path = Path(path)
        self._entries = self._load_entries()

    @staticmethod
    def _key(symbol: str, timeframe: str) -> str:
        """
        symbol/timeframe 고유 키를 생성한다.

        Why:
        - 단일 JSON 파일에서 다중 cursor를 충돌 없이 관리하기 위함.
        """
        return f"{symbol}|{timeframe}"

    def _load_entries(self) -> dict[str, dict]:
        """
        상태 파일을 메모리로 로드한다.

        Called from:
        - `__init__`
        """
        if not self._path.exists():
            return {}

        try:
            with open(self._path, "r") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load ingest state file: {e}")
            return {}

        entries = payload.get("entries")
        if not isinstance(entries, dict):
            logger.error("Invalid ingest state format: entries is not a dict.")
            return {}
        return entries

    def _persist(self) -> None:
        """
        현재 메모리 상태를 파일에 기록한다.

        Called from:
        - `upsert`
        """
        # atomic write를 강제해 프로세스 중단/동시 읽기 상황에서도
        # 반쯤 써진 JSON(손상 파일) 노출을 줄인다.
        payload = {
            "version": 1,
            "updated_at": _format_utc(datetime.now(timezone.utc)),
            "entries": self._entries,
        }
        atomic_write_json(self._path, payload, indent=2)

    def get(self, symbol: str, timeframe: str) -> IngestStateEntry | None:
        """
        특정 symbol/timeframe의 상태 엔트리를 조회한다.

        Called from:
        - `get_last_closed`
        """
        raw = self._entries.get(self._key(symbol, timeframe))
        if not isinstance(raw, dict):
            return None

        last_closed = parse_utc_timestamp(raw.get("last_closed_ts"))
        updated_at = parse_utc_timestamp(raw.get("updated_at")) or datetime.now(
            timezone.utc
        )
        status = (
            raw.get("status")
            if isinstance(raw.get("status"), str)
            else "unknown"
        )
        return IngestStateEntry(
            symbol=raw.get("symbol", symbol),
            timeframe=raw.get("timeframe", timeframe),
            last_closed_ts=last_closed,
            status=status,
            updated_at=updated_at,
        )

    def get_last_closed(self, symbol: str, timeframe: str) -> datetime | None:
        """
        마지막 저장된 closed candle 시각만 반환한다.

        Called from:
        - `scripts.pipeline_worker.run_worker` ingest 기준점 계산
        """
        entry = self.get(symbol, timeframe)
        if entry is None:
            return None
        return entry.last_closed_ts

    def upsert(
        self,
        symbol: str,
        timeframe: str,
        *,
        last_closed_ts: datetime | None,
        status: str,
    ) -> None:
        """
        symbol/timeframe 상태를 갱신하고 즉시 persist한다.

        Called from:
        - `scripts.pipeline_worker.run_worker` ingest 결과 처리(`saved/failed/blocked`)
        """
        key = self._key(symbol, timeframe)
        existing = self._entries.get(key, {})

        resolved_last_closed = (
            _format_utc(last_closed_ts)
            if last_closed_ts is not None
            else existing.get("last_closed_ts")
        )
        # 새 closed timestamp가 없을 때 기존 값을 유지하는 이유:
        # - "이번 cycle에 저장 없음"이 "커서를 null로 리셋"을 뜻하지는 않는다.
        # - 커서를 지우면 다음 cycle에서 불필요한 재부트스트랩을 유발할 수 있다.
        self._entries[key] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "last_closed_ts": resolved_last_closed,
            "status": status,
            "updated_at": _format_utc(datetime.now(timezone.utc)),
        }
        self._persist()
