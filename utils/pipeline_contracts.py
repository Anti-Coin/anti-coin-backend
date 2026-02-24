"""
Pipeline runtime contracts (DTO + Enum).

Why this module exists:
- `scripts.pipeline_worker` 내부에 흩어진 문자열/딕셔너리 상태를
  명시적인 타입으로 고정해 런타임 오타와 분기 누락을 줄인다.
- 상태 전이와 워터마크 갱신 정책을 Enum으로 모델링해
  fail-closed 기본 동작을 강제한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TypedDict

UTC_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_utc_datetime(text: str | None) -> datetime | None:
    """
    UTC 문자열을 aware datetime으로 파싱한다.
    """
    if not isinstance(text, str) or not text:
        return None
    try:
        return datetime.strptime(text, UTC_DATETIME_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def format_utc_datetime(value: datetime | None) -> str | None:
    """
    datetime을 프로젝트 표준 UTC 문자열로 직렬화한다.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        normalized = value.replace(tzinfo=timezone.utc)
    else:
        normalized = value.astimezone(timezone.utc)
    return normalized.strftime(UTC_DATETIME_FORMAT)


class SymbolActivationState(str, Enum):
    """
    심볼 activation 상태.
    """

    REGISTERED = "registered"
    BACKFILLING = "backfilling"
    READY_FOR_SERVING = "ready_for_serving"


class SymbolVisibility(str, Enum):
    """
    심볼 노출 상태.
    """

    VISIBLE = "visible"
    HIDDEN_BACKFILLING = "hidden_backfilling"


class StorageGuardLevel(str, Enum):
    """
    디스크 저장소 가드 수준.
    """

    NORMAL = "normal"
    WARN = "warn"
    CRITICAL = "critical"
    BLOCK = "block"


class DetectionGateReason(str, Enum):
    """
    boundary+detection gate 판단 사유.
    """

    DETECTION_UNAVAILABLE_FALLBACK_RUN = "detection_unavailable_fallback_run"
    NO_NEW_CLOSED_CANDLE = "no_new_closed_candle"
    NEW_CLOSED_CANDLE = "new_closed_candle"


class PublishGateReason(str, Enum):
    """
    ingest watermark 기반 publish gate 판단 사유.
    """

    NO_INGEST_WATERMARK = "no_ingest_watermark"
    UP_TO_DATE_INGEST_WATERMARK = "up_to_date_ingest_watermark"
    INGEST_WATERMARK_ADVANCED = "ingest_watermark_advanced"


class IngestExecutionResult(str, Enum):
    """
    ingest 단계 결과 코드.
    """

    SAVED = "saved"
    NO_DATA = "no_data"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class PredictionExecutionResult(str, Enum):
    """
    prediction 단계 결과 코드.
    """

    OK = "ok"
    SKIPPED = "skipped"
    FAILED = "failed"


class IngestSinceSource(str, Enum):
    """
    ingest since 기준점 출처 코드.
    """

    DB_LAST = "db_last"
    BOOTSTRAP_LOOKBACK = "bootstrap_lookback"
    BOOTSTRAP_EXCHANGE_EARLIEST = "bootstrap_exchange_earliest"
    FULL_BACKFILL_EXCHANGE_EARLIEST = "full_backfill_exchange_earliest"
    STATE_DRIFT_REBOOTSTRAP = "state_drift_rebootstrap"
    STATE_DRIFT_REBOOTSTRAP_EXCHANGE_EARLIEST = (
        "state_drift_rebootstrap_exchange_earliest"
    )
    BLOCKED_STORAGE_GUARD = "blocked_storage_guard"
    UNDERFILLED_REBOOTSTRAP = "underfilled_rebootstrap"
    UNDERFILLED_REBOOTSTRAP_EXCHANGE_EARLIEST = (
        "underfilled_rebootstrap_exchange_earliest"
    )


class SymbolActivationEntryPayload(TypedDict):
    """
    symbol_activation.json entries 내부 단일 row payload.
    """

    symbol: str
    state: str
    visibility: str
    is_full_backfilled: bool
    coverage_start_at: str | None
    coverage_end_at: str | None
    exchange_earliest_at: str | None
    ready_at: str | None
    updated_at: str


class SymbolActivationFilePayload(TypedDict):
    """
    symbol_activation.json 전체 payload.
    """

    version: int
    updated_at: str
    entries: dict[str, SymbolActivationEntryPayload]


class WatermarkFilePayload(TypedDict):
    """
    *watermarks.json 전체 payload.
    """

    version: int
    updated_at: str
    entries: dict[str, str]


def _parse_symbol_activation_visibility(
    raw_visibility: str | None,
    *,
    is_full_backfilled: bool,
) -> SymbolVisibility:
    if isinstance(raw_visibility, str):
        try:
            return SymbolVisibility(raw_visibility)
        except ValueError:
            pass
    if is_full_backfilled:
        return SymbolVisibility.VISIBLE
    return SymbolVisibility.HIDDEN_BACKFILLING


def _parse_symbol_activation_state(
    raw_state: str | None,
    *,
    visibility: SymbolVisibility,
    is_full_backfilled: bool,
    has_coverage_start: bool,
) -> SymbolActivationState:
    if isinstance(raw_state, str):
        try:
            return SymbolActivationState(raw_state)
        except ValueError:
            pass

    if is_full_backfilled or visibility == SymbolVisibility.VISIBLE:
        return SymbolActivationState.READY_FOR_SERVING
    if has_coverage_start:
        return SymbolActivationState.BACKFILLING
    return SymbolActivationState.REGISTERED


@dataclass(frozen=True)
class SymbolActivationSnapshot:
    """
    심볼 activation 스냅샷 DTO.
    """

    symbol: str
    state: SymbolActivationState
    visibility: SymbolVisibility
    is_full_backfilled: bool
    coverage_start_at: datetime | None
    coverage_end_at: datetime | None
    exchange_earliest_at: datetime | None
    ready_at: datetime | None
    updated_at: datetime

    @property
    def is_hidden_for_serving(self) -> bool:
        return self.visibility == SymbolVisibility.HIDDEN_BACKFILLING

    @classmethod
    def from_payload(
        cls,
        *,
        symbol: str,
        payload: dict | None,
        fallback_now: datetime | None = None,
    ) -> "SymbolActivationSnapshot":
        """
        json row payload를 DTO로 역직렬화한다.
        """
        resolved_now = fallback_now or datetime.now(timezone.utc)
        raw = payload if isinstance(payload, dict) else {}

        is_full_backfilled = bool(raw.get("is_full_backfilled", False))
        coverage_start_at = parse_utc_datetime(raw.get("coverage_start_at"))
        visibility = _parse_symbol_activation_visibility(
            raw.get("visibility"),
            is_full_backfilled=is_full_backfilled,
        )
        state = _parse_symbol_activation_state(
            raw.get("state"),
            visibility=visibility,
            is_full_backfilled=is_full_backfilled,
            has_coverage_start=coverage_start_at is not None,
        )
        updated_at = parse_utc_datetime(raw.get("updated_at")) or resolved_now
        ready_at = parse_utc_datetime(raw.get("ready_at"))

        return cls(
            symbol=str(raw.get("symbol") or symbol),
            state=state,
            visibility=visibility,
            is_full_backfilled=is_full_backfilled,
            coverage_start_at=coverage_start_at,
            coverage_end_at=parse_utc_datetime(raw.get("coverage_end_at")),
            exchange_earliest_at=parse_utc_datetime(raw.get("exchange_earliest_at")),
            ready_at=ready_at,
            updated_at=updated_at,
        )

    def to_payload(self) -> SymbolActivationEntryPayload:
        """
        DTO를 symbol_activation.json row payload로 직렬화한다.
        """
        updated_at_text = format_utc_datetime(self.updated_at)
        return {
            "symbol": self.symbol,
            "state": self.state.value,
            "visibility": self.visibility.value,
            "is_full_backfilled": self.is_full_backfilled,
            "coverage_start_at": format_utc_datetime(self.coverage_start_at),
            "coverage_end_at": format_utc_datetime(self.coverage_end_at),
            "exchange_earliest_at": format_utc_datetime(self.exchange_earliest_at),
            "ready_at": format_utc_datetime(self.ready_at),
            "updated_at": updated_at_text or "",
        }


@dataclass(frozen=True)
class WatermarkCursor:
    """
    symbol+timeframe별 closed candle watermark DTO.
    """

    symbol: str
    timeframe: str
    closed_at: datetime

    @property
    def key(self) -> str:
        return f"{self.symbol}|{self.timeframe}"

    @classmethod
    def from_key_value(
        cls,
        *,
        key: str,
        value: str,
    ) -> "WatermarkCursor" | None:
        """
        dict entry(`key -> closed_at`)를 DTO로 변환한다.
        """
        if not isinstance(key, str) or "|" not in key:
            return None
        symbol, timeframe = key.split("|", 1)
        if not symbol or not timeframe:
            return None
        closed_at = parse_utc_datetime(value)
        if closed_at is None:
            return None
        return cls(symbol=symbol, timeframe=timeframe, closed_at=closed_at)

    def to_entry(self) -> tuple[str, str]:
        """
        DTO를 dict entry(`key -> closed_at`)로 변환한다.
        """
        return self.key, format_utc_datetime(self.closed_at) or ""


@dataclass(frozen=True)
class DetectionGateDecision:
    """
    detection gate 판단 DTO.
    """

    should_run: bool
    reason: DetectionGateReason


@dataclass(frozen=True)
class PublishGateDecision:
    """
    publish gate 판단 DTO.
    """

    should_run: bool
    reason: PublishGateReason
    ingest_closed_at: datetime | None


@dataclass(frozen=True)
class IngestExecutionOutcome:
    """
    ingest 실행 결과 DTO.
    """

    latest_saved_at: datetime | None
    result: IngestExecutionResult


@dataclass(frozen=True)
class PredictionExecutionOutcome:
    """
    prediction 실행 결과 DTO.
    """

    result: PredictionExecutionResult
    error: str | None


def parse_ingest_execution_result(
    raw_result: str | None,
) -> IngestExecutionResult:
    """
    ingest 문자열 결과를 Enum으로 정규화한다.
    """
    if not isinstance(raw_result, str):
        return IngestExecutionResult.FAILED
    try:
        return IngestExecutionResult(raw_result)
    except ValueError:
        return IngestExecutionResult.FAILED


def parse_prediction_execution_result(
    raw_result: str | None,
) -> PredictionExecutionResult:
    """
    prediction 문자열 결과를 Enum으로 정규화한다.
    """
    if not isinstance(raw_result, str):
        return PredictionExecutionResult.FAILED
    try:
        return PredictionExecutionResult(raw_result)
    except ValueError:
        return PredictionExecutionResult.FAILED


def parse_ingest_since_source(
    raw_source: str | None,
) -> IngestSinceSource | None:
    """
    since source 문자열을 Enum으로 정규화한다.
    """
    if not isinstance(raw_source, str):
        return None
    try:
        return IngestSinceSource(raw_source)
    except ValueError:
        return None


def is_rebootstrap_source(source: IngestSinceSource | None) -> bool:
    """
    rebootstrap 계열 source인지 반환한다.
    """
    if source is None:
        return False
    return source in {
        IngestSinceSource.BOOTSTRAP_LOOKBACK,
        IngestSinceSource.BOOTSTRAP_EXCHANGE_EARLIEST,
        IngestSinceSource.FULL_BACKFILL_EXCHANGE_EARLIEST,
        IngestSinceSource.STATE_DRIFT_REBOOTSTRAP,
        IngestSinceSource.STATE_DRIFT_REBOOTSTRAP_EXCHANGE_EARLIEST,
        IngestSinceSource.UNDERFILLED_REBOOTSTRAP,
        IngestSinceSource.UNDERFILLED_REBOOTSTRAP_EXCHANGE_EARLIEST,
    }
