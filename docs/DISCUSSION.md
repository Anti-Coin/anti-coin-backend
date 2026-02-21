# Coin Predict Discussion Log

- Last Updated: 2026-02-20
- Purpose: 구현 전 쟁점/가설/옵션을 기록하고, 완료된 phase 토론은 archive로 분리해 active 문서 밀도를 유지한다.
- Full Phase C Discussion History: `docs/archive/phase_c/DISCUSSION_PHASE_C_FULL_2026-02-20.md`

## 1. Operating Rule
1. Discussion은 구현 지시가 아니라 "쟁점 정리 + 관찰 사실 + 옵션 비교"를 기록한다.
2. 구현 결론은 `docs/TASKS_MINIMUM_UNITS.md`에 별도 Task로 승격한 뒤 진행한다.
3. 완료된 phase의 상세 토론은 active 문서에서 제거하고 archive 원문을 단일 출처로 사용한다.

## 2. Entry Template
1. Date
2. Topic
3. Observed Facts
4. Hypotheses
5. Options
6. Recommendation
7. Follow-up Candidates

## 3. Entry 2026-02-20 - Phase C Discussion Archive Boundary
1. Topic: Phase C 토론 로그 경량화
2. Observed Facts:
1. `C-001`~`C-016` 완료 후 active Discussion에 Phase C 상세 로그가 과밀하게 남아 있었다.
2. active 문서의 목적은 "현재 실행 의사결정"이며, 과거 상세 토론은 참조 빈도가 낮다.
3. Decision:
1. Phase C 토론 원문은 `docs/archive/phase_c/DISCUSSION_PHASE_C_FULL_2026-02-20.md`로 고정한다.
2. active `docs/DISCUSSION.md`는 운영 규칙/템플릿/현재 follow-up 중심으로 유지한다.
3. Revisit Trigger:
1. Phase C 범위를 재개하거나 과거 토론 원문 근거가 필요한 경우.

## 4. Active Follow-up Candidates (Phase D)
1. `D-012`: 학습 데이터 SoT 정렬(Influx 기반 closed-candle snapshot)
2. `D-013`: 재학습 트리거 정책(시간+이벤트) 정의
3. `D-014`: 학습 실행 no-overlap/락 가드
4. `D-015`: 학습 실행 관측성/알림 baseline
