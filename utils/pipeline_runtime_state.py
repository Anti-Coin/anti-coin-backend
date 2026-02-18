"""
Pipeline runtime state stores.

Why this module exists:
- run_worker에서 파일 I/O 세부 구현을 분리해 오케스트레이터 순수성을 높인다.
- symbol activation / watermark를 DTO 기반으로 읽고 쓰도록 통일한다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from utils.file_io import atomic_write_json
from utils.pipeline_contracts import (
    SymbolActivationEntryPayload,
    SymbolActivationFilePayload,
    SymbolActivationSnapshot,
    WatermarkCursor,
    WatermarkFilePayload,
    format_utc_datetime,
    parse_utc_datetime,
)


class SymbolActivationStore:
    """
    symbol_activation.json 파일 접근 계층.
    """

    def __init__(self, path: Path, logger):
        self._path = Path(path)
        self._logger = logger

    def load(self) -> dict[str, SymbolActivationSnapshot]:
        """
        파일에서 activation entries를 읽어 DTO dict로 반환한다.
        """
        if not self._path.exists():
            return {}

        try:
            with open(self._path, "r") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self._logger.error(f"Failed to load symbol activation file: {e}")
            return {}

        entries = payload.get("entries")
        if not isinstance(entries, dict):
            self._logger.error(
                "Invalid symbol activation format: entries is not a dict."
            )
            return {}

        resolved_now = datetime.now(timezone.utc)
        normalized: dict[str, SymbolActivationSnapshot] = {}
        for symbol, raw_entry in entries.items():
            if not isinstance(symbol, str) or not symbol:
                continue
            normalized[symbol] = SymbolActivationSnapshot.from_payload(
                symbol=symbol,
                payload=raw_entry if isinstance(raw_entry, dict) else {},
                fallback_now=resolved_now,
            )
        return normalized

    def save(
        self,
        entries: Mapping[str, SymbolActivationSnapshot | dict],
        *,
        now: datetime | None = None,
    ) -> None:
        """
        DTO dict를 symbol_activation.json 포맷으로 저장한다.
        """
        resolved_now = now or datetime.now(timezone.utc)
        payload_entries: dict[str, SymbolActivationEntryPayload] = {}

        for symbol, entry in entries.items():
            if not isinstance(symbol, str) or not symbol:
                continue
            if isinstance(entry, SymbolActivationSnapshot):
                snapshot = entry
            else:
                snapshot = SymbolActivationSnapshot.from_payload(
                    symbol=symbol,
                    payload=entry if isinstance(entry, dict) else {},
                    fallback_now=resolved_now,
                )
            payload_entries[symbol] = snapshot.to_payload()

        payload: SymbolActivationFilePayload = {
            "version": 1,
            "updated_at": format_utc_datetime(resolved_now) or "",
            "entries": payload_entries,
        }
        atomic_write_json(self._path, payload, indent=2)


class WatermarkStore:
    """
    ingest/predict/export watermark 파일 접근 계층.
    """

    def __init__(self, path: Path, logger):
        self._path = Path(path)
        self._logger = logger

    def load(self) -> dict[str, WatermarkCursor]:
        """
        파일에서 watermark entries를 읽어 DTO dict로 반환한다.
        """
        if not self._path.exists():
            return {}

        try:
            with open(self._path, "r") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self._logger.error(
                f"Failed to load watermark file {self._path.name}: {e}"
            )
            return {}

        entries = payload.get("entries")
        if not isinstance(entries, dict):
            self._logger.error(
                f"Invalid watermark format in {self._path.name}: entries is not a dict."
            )
            return {}

        normalized: dict[str, WatermarkCursor] = {}
        for key, value in entries.items():
            cursor = None
            if isinstance(value, str):
                cursor = WatermarkCursor.from_key_value(key=key, value=value)
            if cursor is not None:
                normalized[key] = cursor
        return normalized

    def save(
        self,
        entries: Mapping[str, WatermarkCursor | str],
        *,
        now: datetime | None = None,
    ) -> None:
        """
        DTO dict를 watermark 파일 포맷으로 저장한다.
        """
        resolved_now = now or datetime.now(timezone.utc)
        payload_entries: dict[str, str] = {}

        for key, value in entries.items():
            if isinstance(value, WatermarkCursor):
                cursor_key, cursor_value = value.to_entry()
                payload_entries[cursor_key] = cursor_value
                continue

            if isinstance(value, str):
                parsed = parse_utc_datetime(value)
                if parsed is None:
                    continue
                payload_entries[key] = format_utc_datetime(parsed) or ""

        payload: WatermarkFilePayload = {
            "version": 1,
            "updated_at": format_utc_datetime(resolved_now) or "",
            "entries": payload_entries,
        }
        atomic_write_json(self._path, payload, indent=2)
