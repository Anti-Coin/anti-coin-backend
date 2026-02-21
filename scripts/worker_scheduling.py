"""
Boundary scheduling logic.

Why this module exists:
- pipeline_worker.py에서 timeframe boundary 스케줄링 계산을 분리해
  오케스트레이션 코드의 인지 부하를 줄인다.
- 이 함수들은 순수 계산 함수로 외부 의존이 없다.
"""

from __future__ import annotations

from datetime import datetime

from utils.time_alignment import (
    last_closed_candle_open,
    next_timeframe_boundary,
)


def initialize_boundary_schedule(
    now: datetime, timeframes: list[str]
) -> dict[str, datetime]:
    """
    각 timeframe의 현재 경계(open timestamp)를 초기 스케줄로 설정한다.

    Called from:
    - run_worker() 시작 시(경계 스케줄러 모드)
    """
    # 재시작 직후 "다음 경계만 대기"하면 장주기 TF(1d/1w/1M)가
    # 다음 경계까지 오래 정체될 수 있다.
    # 따라서 시작 시점에는 "현재 경계"를 기준점으로 잡아
    # 놓친 경계를 첫 cycle에서 한 번 따라잡도록 한다.
    return {
        timeframe: next_timeframe_boundary(
            last_closed_candle_open(now, timeframe), timeframe
        )
        for timeframe in timeframes
    }


def resolve_boundary_due_timeframes(
    *,
    now: datetime,
    timeframes: list[str],
    next_boundary_by_timeframe: dict[str, datetime],
) -> tuple[list[str], int, datetime | None]:
    """
    현재 시각 기준으로 실행 due timeframe과 missed boundary 수를 계산한다.

    Called from:
    - run_worker() cycle 시작부
    """
    due_timeframes: list[str] = []
    missed_boundary_count = 0

    for timeframe in timeframes:
        next_boundary = next_boundary_by_timeframe.get(timeframe)
        if next_boundary is None:
            next_boundary = next_timeframe_boundary(now, timeframe)
            next_boundary_by_timeframe[timeframe] = next_boundary

        # 봉 마감 미완료 된 데이터
        if now < next_boundary:
            continue

        due_timeframes.append(timeframe)
        boundary_advance_steps = 0
        while next_boundary <= now:
            # 워커 중단/지연 후 복귀 시 경계를 여러 개 건너뛸 수 있다.
            # while로 다음 경계까지 따라잡고, 몇 개를 놓쳤는지 계측해
            # 운영자가 missed boundary를 관찰할 수 있게 한다.
            next_boundary = next_timeframe_boundary(next_boundary, timeframe)
            boundary_advance_steps += 1

        # 원본 변경
        next_boundary_by_timeframe[timeframe] = next_boundary
        missed_boundary_count += max(0, boundary_advance_steps - 1)

    next_boundary_at = (
        min(next_boundary_by_timeframe.values()) if next_boundary_by_timeframe else None
    )
    return due_timeframes, missed_boundary_count, next_boundary_at
