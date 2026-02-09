# CONTEXT.md
Authoritative for: project goals, constraints, and tradeoff intent.

## Why This Project Exists
1) Build AIOps capability through real operations experience.
2) Build a portfolio with production-like discipline.
3) Grow into a real service, not a demo-only script.

## AI Usage Philosophy
- Do not let AI produce large one-shot code blocks by default.
- Prefer small, iterative changes so the owner keeps project understanding.
- Decide after deep discussion on non-trivial topics.
- Always think about edge cases and failure paths before implementation.

## Delivery Philosophy
- Prefer practical MVP delivery over perfectionism.
- Treat failures as learning input, then iterate with small safe changes.
- Ask "Can we actually operate this in current environment?" before adopting tools.
- If a tool is elegant but not operable on current infra, pick the simpler operable option first.

## Runtime Reality
- Target environment: Oracle Free Tier ARM.
- Resources are limited and long-running behavior matters.
- Ops overhead is part of cost; simple and observable beats complex.

## Non-Negotiable Priority
1) Stability/reliability
2) Cost/resource efficiency
3) Performance/optimization

## Current Architecture Direction
- Worker-centric pipeline
- Static JSON artifacts for serving
- Gatekeeper-style freshness checks
- UTC for internal time

## Tooling Stance
- Heavy orchestration is conditional, not default (`R8`).
- Any big-tool proposal must include cost, alternatives, and rollback.

## Scope Guard
Do not jump roadmap phases without explicit request.
