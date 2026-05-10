"""Event bus backed by Redis Streams for per-session SSE fan-out.

Each session gets its own stream key `events:{session_id}`. Producers
(the worker) call `publish()`; consumers (SSE handlers in api_server)
iterate via `subscribe()`. The worker emits a final `{"type": "__end__"}`
sentinel via `end()` so subscribers know when to close the stream.

Streams are bounded with MAXLEN ~10000 and given a 24h TTL so abandoned
streams self-evict — matching the session TTL in session_store.
"""

from __future__ import annotations

import json
import os
from typing import AsyncIterator

from redis import asyncio as aioredis

_EVENT_PREFIX = "events:"
_MAX_STREAM_LEN = 10_000
_STREAM_TTL_SECONDS = 24 * 3600
_END_SENTINEL = "__end__"
_DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def _stream_key(session_id: str) -> str:
    return f"{_EVENT_PREFIX}{session_id}"


class EventBus:
    """Publish / subscribe to per-session event streams."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    @classmethod
    def from_url(cls, url: str | None = None) -> "EventBus":
        url = url or os.getenv("REDIS_URL", _DEFAULT_REDIS_URL)
        return cls(aioredis.from_url(url, decode_responses=True))

    async def close(self) -> None:
        await self._r.aclose()

    async def publish(self, session_id: str, event: dict) -> None:
        """Append a structured event to the session's stream."""
        key = _stream_key(session_id)
        await self._r.xadd(
            key,
            {"data": json.dumps(event)},
            maxlen=_MAX_STREAM_LEN,
            approximate=True,
        )
        # Refresh TTL on every publish so active streams stay alive.
        await self._r.expire(key, _STREAM_TTL_SECONDS)

    async def end(self, session_id: str) -> None:
        """Emit the end-of-stream sentinel so subscribers can close cleanly."""
        await self.publish(session_id, {"type": _END_SENTINEL})

    async def subscribe(
        self,
        session_id: str,
        from_start: bool = True,
        block_ms: int = 30_000,
        max_idle_blocks: int = 10,
    ) -> AsyncIterator[dict]:
        """Async iterator over events for a session.

        from_start=True replays from the beginning — use this for SSE clients
        that may connect after the worker started. Set to False to tail only
        new events.

        Returns when:
          - the end-sentinel is received, or
          - max_idle_blocks consecutive XREAD timeouts elapse with no events
            (default: 10 × 30s = 5 min idle).

        The caller is also free to cancel the iterator at any time (e.g. when
        the SSE client disconnects).
        """
        key = _stream_key(session_id)
        last_id = "0" if from_start else "$"
        idle_blocks = 0
        while True:
            resp = await self._r.xread({key: last_id}, block=block_ms, count=100)
            if not resp:
                idle_blocks += 1
                if idle_blocks >= max_idle_blocks:
                    return
                continue
            idle_blocks = 0
            _, messages = resp[0]
            for msg_id, fields in messages:
                last_id = msg_id
                event = json.loads(fields["data"])
                if event.get("type") == _END_SENTINEL:
                    return
                yield event
