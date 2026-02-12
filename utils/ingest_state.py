import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from utils.file_io import atomic_write_json
from utils.freshness import parse_utc_timestamp
from utils.logger import get_logger

logger = get_logger(__name__)


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_utc(dt: datetime) -> str:
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
        self._path = Path(path)
        self._entries = self._load_entries()

    @staticmethod
    def _key(symbol: str, timeframe: str) -> str:
        return f"{symbol}|{timeframe}"

    def _load_entries(self) -> dict[str, dict]:
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
        payload = {
            "version": 1,
            "updated_at": _format_utc(datetime.now(timezone.utc)),
            "entries": self._entries,
        }
        atomic_write_json(self._path, payload, indent=2)

    def get(self, symbol: str, timeframe: str) -> IngestStateEntry | None:
        raw = self._entries.get(self._key(symbol, timeframe))
        if not isinstance(raw, dict):
            return None

        last_closed = parse_utc_timestamp(raw.get("last_closed_ts"))
        updated_at = parse_utc_timestamp(raw.get("updated_at")) or datetime.now(
            timezone.utc
        )
        status = raw.get("status") if isinstance(raw.get("status"), str) else "unknown"
        return IngestStateEntry(
            symbol=raw.get("symbol", symbol),
            timeframe=raw.get("timeframe", timeframe),
            last_closed_ts=last_closed,
            status=status,
            updated_at=updated_at,
        )

    def get_last_closed(self, symbol: str, timeframe: str) -> datetime | None:
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
        key = self._key(symbol, timeframe)
        existing = self._entries.get(key, {})

        resolved_last_closed = (
            _format_utc(last_closed_ts)
            if last_closed_ts is not None
            else existing.get("last_closed_ts")
        )
        self._entries[key] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "last_closed_ts": resolved_last_closed,
            "status": status,
            "updated_at": _format_utc(datetime.now(timezone.utc)),
        }
        self._persist()
