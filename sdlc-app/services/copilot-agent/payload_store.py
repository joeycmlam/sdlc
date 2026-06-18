"""Ephemeral payload store backed by Redis.

Agents stage large content here (BRDs, BDD scenarios, long Jira comments)
so it can be fed into other tools via stdin pipe (`payload-cat <name> |
next-tool`) without encoding the bytes into a shell command string —
that's what tripped BashTool's 4 KB command cap and burned the BA agent's
turn budget chunking workarounds.

Keys live under `agent:payload:<name>` with a short TTL (10 min default)
so abandoned payloads self-evict. The store is binary-safe — callers
pass and receive `bytes`.
"""

from __future__ import annotations

import os

from redis import asyncio as aioredis

_KEY_PREFIX = "agent:payload:"
_DEFAULT_TTL_SECONDS = 600  # 10 min
_DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def _payload_key(name: str) -> str:
    return f"{_KEY_PREFIX}{name}"


class PayloadStore:
    """Async Redis-backed scratch store for agent-staged payloads."""

    def __init__(self, redis: aioredis.Redis, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self._r = redis
        self._ttl = ttl_seconds

    @classmethod
    def from_url(
        cls,
        url: str | None = None,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> "PayloadStore":
        url = url or os.getenv("REDIS_URL", _DEFAULT_REDIS_URL)
        # decode_responses=False keeps the store binary-safe; agents send
        # UTF-8 markdown today, but we don't want to bake in that assumption.
        return cls(aioredis.from_url(url, decode_responses=False), ttl_seconds)

    async def close(self) -> None:
        await self._r.aclose()

    async def stage(
        self,
        name: str,
        content: bytes,
        append: bool = False,
    ) -> str:
        """Store `content` under the logical name. Returns the short name.

        On append, content is concatenated to the existing value. TTL is
        refreshed on every call so streamed appends don't expire mid-write.
        """
        key = _payload_key(name)
        if append:
            await self._r.append(key, content)
        else:
            await self._r.set(key, content)
        await self._r.expire(key, self._ttl)
        return name

    async def fetch(self, name: str) -> bytes | None:
        """Return the stored bytes, or None if the key doesn't exist."""
        return await self._r.get(_payload_key(name))

    async def delete(self, name: str) -> bool:
        """Remove the staged payload. Returns True if a key was deleted."""
        deleted = await self._r.delete(_payload_key(name))
        return bool(deleted)
