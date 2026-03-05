"""
Serve policy evaluators.

Why this module exists:
- manifest writer/export 경로에 흩어진 serve gate 계산식을 단일 함수로 고정해
  정책 변경 시 수정 지점을 줄인다.
"""

from __future__ import annotations


def evaluate_serve_allowed(
    *,
    visibility: str,
    prediction_status: str,
    allowed_statuses: set[str],
) -> bool:
    """
    사용자 플레인 노출 가능 여부를 계산한다.

    Current contract:
    - visibility가 `visible`이고,
    - prediction_status가 허용 목록(기본 `fresh/stale`)에 포함될 때만 True.
    """
    return visibility == "visible" and prediction_status in allowed_statuses

