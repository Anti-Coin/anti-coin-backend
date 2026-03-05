"""
Model artifact path resolver.

Why this module exists:
- 모델 경로 규칙(canonical/legacy)을 한 곳에서 유지해
  train/predict 경계의 계약 드리프트를 줄인다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelArtifactPaths:
    canonical: Path
    legacy: Path | None = None


def to_safe_symbol(symbol: str) -> str:
    return symbol.replace("/", "_")


def resolve_canonical_model_path(
    models_dir: Path,
    symbol: str,
    timeframe: str,
) -> Path:
    safe_symbol = to_safe_symbol(symbol)
    return models_dir / f"model_{safe_symbol}_{timeframe}.json"


def resolve_canonical_model_metadata_path(
    models_dir: Path,
    symbol: str,
    timeframe: str,
) -> Path:
    safe_symbol = to_safe_symbol(symbol)
    return models_dir / f"model_{safe_symbol}_{timeframe}.meta.json"


def resolve_model_paths(
    models_dir: Path,
    symbol: str,
    timeframe: str,
    *,
    primary_timeframe: str,
) -> ModelArtifactPaths:
    canonical = resolve_canonical_model_path(models_dir, symbol, timeframe)
    legacy: Path | None = None
    if timeframe == primary_timeframe:
        safe_symbol = to_safe_symbol(symbol)
        legacy = models_dir / f"model_{safe_symbol}.json"
    return ModelArtifactPaths(canonical=canonical, legacy=legacy)


def resolve_model_metadata_paths(
    models_dir: Path,
    symbol: str,
    timeframe: str,
    *,
    primary_timeframe: str,
) -> ModelArtifactPaths:
    safe_symbol = to_safe_symbol(symbol)
    canonical = models_dir / f"model_{safe_symbol}_{timeframe}.meta.json"
    legacy: Path | None = None
    if timeframe == primary_timeframe:
        legacy = models_dir / f"model_{safe_symbol}.meta.json"
    return ModelArtifactPaths(canonical=canonical, legacy=legacy)
