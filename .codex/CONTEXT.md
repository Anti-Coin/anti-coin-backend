# CONTEXT.md
Authoritative for: project goals, constraints, and tradeoff intent.

## Why This Project Exists
1) Build AIOps capability through real operations experience.
2) Build a portfolio with production-like discipline.
3) Grow into a real service, not a demo-only script.

## AI Usage Philosophy
- Prefer small, iterative changes over large one-shot generation.
- Challenge assumptions before implementation.
- Treat failure-path design as first-class work.

## Philosophy vs Domain Policy
- Philosophy: stable engineering stance and collaboration values.
- Domain policy: market-data specific rules that may evolve.

## Runtime Reality
- Target environment: Oracle Free Tier ARM.
- Resources are limited; operational simplicity is part of cost.

## Non-Negotiable Priority
1) Stability/reliability
2) Cost/resource efficiency
3) Performance/optimization

## Current Architecture Direction
- Worker-centric pipeline
- Static JSON user plane + status/ops API plane
- InfluxDB as Source of Truth
- UTC for internal time

## Context Budget Policy
1) Read active docs first (`CONTEXT_MIN`, `DECISIONS`, `PLAN`, `TASKS`).
2) Open archive docs only when current decision/task cannot be justified from active docs.
3) When archive is used, reference only the needed file/section.

## Scope Guard
Do not jump roadmap phases without explicit request.
