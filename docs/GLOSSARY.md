# Coin Predict Glossary

- Last Updated: 2026-02-10

## Core Terms
1. `fresh`: soft threshold 이내 최신 상태
2. `stale`: soft threshold 초과, hard threshold 이내 (경고 노출)
3. `hard_stale`: hard threshold 초과 (차단)
4. `corrupt`: 파일 파손/형식 오류로 신뢰 불가 상태 (차단)
5. `Hybrid Ingest`: 1m rolling + 1d/1w/1M 직접 수집 전략
6. `Backfill`: 과거 누락 구간을 채우는 수집 작업
7. `Gap Detector`: 시계열의 빈 구간을 탐지하는 로직
8. `Gap Refill`: 탐지된 빈 구간을 다시 수집하는 작업
9. `SSG`: Worker가 미리 JSON을 생성하고 정적으로 서빙하는 방식
10. `Champion Model`: 현재 실제 서빙 모델
11. `Shadow Model`: 사용자 영향 없이 병렬 평가되는 후보 모델
12. `Living Plan`: 운영 결과에 따라 갱신되는 계획 문서 체계
