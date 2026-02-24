"""
Pipeline runtime state stores.

Why this module exists:
- run_worker에서 symbol activation 파일 I/O 세부 구현을 분리해
  오케스트레이터 순수성을 높인다.
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
    format_utc_datetime,
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

        Expected payload shape:
        {
          "version": 1,
          "updated_at": "...Z",
          "entries": {
            "BTC/USDT": {"state": "backfilling", "visibility": "hidden_backfilling", ...}
          }
        }
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

        Note:
        - dict 입력도 허용하지만 저장 전에 DTO로 정규화한다.
        - unknown/invalid 필드는 DTO 변환 시 제거되어 파일 계약을 안정화한다.
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
