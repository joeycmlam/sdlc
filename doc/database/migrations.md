---
Auto-generated: true
Generated on: 2026-05-10 09:41:26 UTC
Generator: doc-architect agent v1.0
Repository: joeycmlam/sdlc
Branch: copilot/prepare-system-documentation
Commit: afd9a49
---

# Migrations

There is no SQL migration system in the repository today.

## Current state

- Session and event schemas are defined in Python (`session_store.py`, `event_bus.py`).
- Redis key names, TTLs, and event shapes are the effective schema contract.
- Backward compatibility must be managed in application code when session fields or event payloads change.

## Recommended schema change process

1. Update the relevant Pydantic model or event producer/consumer.
2. Preserve compatibility for any live sessions that may still exist in Redis for up to 24 hours.
3. Update the documentation in [`schema.md`](schema.md) and [`er-diagram.md`](er-diagram.md).
4. If a breaking key format change is required, clear or version the affected Redis keys during deployment.

## Historical migrations

No formal migration history is tracked yet. This file establishes the baseline for future documented schema changes.
