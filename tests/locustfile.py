from __future__ import annotations

import json
import os
import random

from locust import HttpUser, between, tag, task


def _parse_csv(raw: str | None, default: list[str]) -> list[str]:
    if not raw:
        return default.copy()
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or default.copy()


def _parse_code_set(raw: str | None, default: set[int]) -> set[int]:
    if not raw:
        return set(default)
    codes: set[int] = set()
    for chunk in raw.split(","):
        try:
            codes.add(int(chunk.strip()))
        except ValueError:
            continue
    return codes or set(default)


LOAD_SYMBOLS = _parse_csv(
    os.getenv("LOAD_TEST_SYMBOLS"),
    _parse_csv(os.getenv("TARGET_SYMBOLS"), ["BTC/USDT"]),
)
LOAD_TIMEFRAMES = _parse_csv(
    os.getenv("LOAD_TEST_TIMEFRAMES"),
    _parse_csv(os.getenv("INGEST_TIMEFRAMES"), ["1h"]),
)
PRIMARY_LOAD_TIMEFRAME = LOAD_TIMEFRAMES[0]
STATUS_ACCEPT_CODES = _parse_code_set(
    os.getenv("LOAD_TEST_STATUS_ACCEPT_CODES"), {200, 503}
)
STATIC_ACCEPT_CODES = _parse_code_set(
    os.getenv("LOAD_TEST_STATIC_ACCEPT_CODES"), {200}
)


def _safe_symbol(symbol: str) -> str:
    return symbol.replace("/", "_")


def _status_path(symbol: str, timeframe: str) -> str:
    return f"/status/{symbol}?timeframe={timeframe}"


def _history_path(symbol: str, timeframe: str) -> str:
    return f"/static/history_{_safe_symbol(symbol)}_{timeframe}.json"


def _prediction_path(symbol: str, timeframe: str) -> str:
    return f"/static/prediction_{_safe_symbol(symbol)}_{timeframe}.json"


class _BaseLoadUser(HttpUser):
    abstract = True

    def _pick_symbol_timeframe(self) -> tuple[str, str]:
        return random.choice(LOAD_SYMBOLS), random.choice(LOAD_TIMEFRAMES)

    def _json_or_fail(self, response, allowed_codes: set[int]):
        if response.status_code == 0:
            response.failure(f"Network fail: {response.error}")
            return None
        if response.status_code not in allowed_codes:
            response.failure(
                f"Unexpected status={response.status_code} body={response.text[:180]}"
            )
            return None
        try:
            return response.json()
        except json.JSONDecodeError:
            response.failure("JSON decode error")
            return None

    def _request_status(self, symbol: str, timeframe: str) -> None:
        with self.client.get(
            _status_path(symbol, timeframe),
            name="/status/[symbol]?timeframe=[tf]",
            catch_response=True,
        ) as response:
            payload = self._json_or_fail(response, STATUS_ACCEPT_CODES)
            if payload is None:
                return

            if response.status_code == 200 and "status" not in payload:
                response.failure("status payload missing 'status'")
                return
            if response.status_code == 503 and "detail" not in payload:
                response.failure("status 503 payload missing 'detail'")
                return
            response.success()

    def _request_static_json(
        self,
        path: str,
        *,
        name: str,
        required_keys: tuple[str, ...] = (),
    ) -> None:
        with self.client.get(path, name=name, catch_response=True) as response:
            payload = self._json_or_fail(response, STATIC_ACCEPT_CODES)
            if payload is None:
                return
            if not isinstance(payload, dict):
                response.failure("Expected JSON object payload")
                return
            for key in required_keys:
                if key not in payload:
                    response.failure(f"payload missing key='{key}'")
                    return
            response.success()


class BaselineLoadUser(_BaseLoadUser):
    wait_time = between(1, 3)

    @tag("baseline")
    @task(4)
    def status_baseline(self):
        symbol, timeframe = self._pick_symbol_timeframe()
        self._request_status(symbol, timeframe)

    @tag("baseline")
    @task(3)
    def manifest_baseline(self):
        self._request_static_json(
            "/static/manifest.json",
            name="/static/manifest.json",
            required_keys=("entries", "summary"),
        )

    @tag("baseline")
    @task(2)
    def history_baseline(self):
        symbol = random.choice(LOAD_SYMBOLS)
        self._request_static_json(
            _history_path(symbol, PRIMARY_LOAD_TIMEFRAME),
            name="/static/history_[symbol]_[tf].json",
            required_keys=("symbol", "timeframe", "data"),
        )

    @tag("baseline")
    @task(1)
    def prediction_baseline(self):
        symbol = random.choice(LOAD_SYMBOLS)
        self._request_static_json(
            _prediction_path(symbol, PRIMARY_LOAD_TIMEFRAME),
            name="/static/prediction_[symbol]_[tf].json",
            required_keys=("symbol", "timeframe", "forecast"),
        )


class StressLoadUser(_BaseLoadUser):
    wait_time = between(0.1, 0.5)

    @tag("stress")
    @task(5)
    def status_stress(self):
        symbol, timeframe = self._pick_symbol_timeframe()
        self._request_status(symbol, timeframe)

    @tag("stress")
    @task(4)
    def manifest_stress(self):
        self._request_static_json(
            "/static/manifest.json",
            name="/static/manifest.json",
            required_keys=("entries", "summary"),
        )

    @tag("stress")
    @task(3)
    def history_stress(self):
        symbol = random.choice(LOAD_SYMBOLS)
        self._request_static_json(
            _history_path(symbol, PRIMARY_LOAD_TIMEFRAME),
            name="/static/history_[symbol]_[tf].json",
            required_keys=("symbol", "timeframe", "data"),
        )
