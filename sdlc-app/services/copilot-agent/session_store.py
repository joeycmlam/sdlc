"""Session store backed by Redis (single-key JSON + EXPIRE TTL).

Sessions are persisted as JSON under `session:{id}` with a 24h TTL. Redis
evicts expired keys automatically — no background cleanup task is needed.

FSM transitions are validated in Python; in normal flow only the worker
mutates a session at a time. Concurrent writers race (last-write-wins);
this is acceptable for the current control-plane / worker-plane split.

Session states:
    pending → running → awaiting_approval → approved/rejected → completed/failed
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field
from redis import asyncio as aioredis

# ---------------------------------------------------------------------------
# Session model
# ---------------------------------------------------------------------------

SessionState = Literal[
    "pending",
    "running",
    "awaiting_approval",
    "approved",
    "rejected",
    "completed",
    "failed",
]

# Valid FSM transitions
_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    "pending": {"running", "failed"},
    "running": {"awaiting_approval", "completed", "failed"},
    "awaiting_approval": {"approved", "rejected", "failed"},
    "approved": {"running", "completed"},
    "rejected": {"completed"},
    "completed": set(),
    "failed": set(),
}


class Session(BaseModel):
    id: str
    state: SessionState = "pending"
    agent_file: str
    instruction: str
    model: str = "gpt-4o"
    max_turns: int = 20
    extra_context: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    result: str | None = None
    github_issue_url: str | None = None
    jira_url: str | None = None
    confluence_pages: list[str] = Field(default_factory=list)
    create_github_issue: bool = False
    github_owner: str | None = None
    github_repo: str | None = None
    custom_agent: str | None = None
    error: str | None = None

    def transition(self, new_state: SessionState) -> None:
        allowed = _TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {self.state!r} → {new_state!r}. "
                f"Allowed: {sorted(allowed)}"
            )
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Redis-backed store
# ---------------------------------------------------------------------------

_SESSION_TTL_SECONDS = 24 * 3600
_KEY_PREFIX = "session:"
_DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def _key(session_id: str) -> str:
    return f"{_KEY_PREFIX}{session_id}"


class RedisSessionStore:
    """Async Redis-backed session store. Drop-in replacement for the in-memory store."""

    def __init__(
        self,
        redis: aioredis.Redis,
        ttl_seconds: int = _SESSION_TTL_SECONDS,
    ) -> None:
        self._r = redis
        self._ttl = ttl_seconds

    @classmethod
    def from_url(
        cls,
        url: str | None = None,
        ttl_seconds: int = _SESSION_TTL_SECONDS,
    ) -> "RedisSessionStore":
        url = url or os.getenv("REDIS_URL", _DEFAULT_REDIS_URL)
        return cls(aioredis.from_url(url, decode_responses=True), ttl_seconds)

    async def close(self) -> None:
        await self._r.aclose()

    async def ping(self) -> bool:
        try:
            return bool(await self._r.ping())
        except Exception:
            return False

    # -- CRUD --------------------------------------------------------------

    async def create(
        self,
        agent_file: str,
        instruction: str,
        model: str = "gpt-4o",
        max_turns: int = 20,
        extra_context: str = "",
        jira_url: str | None = None,
        confluence_pages: list[str] | None = None,
        create_github_issue: bool = False,
        github_owner: str | None = None,
        github_repo: str | None = None,
        custom_agent: str | None = None,
    ) -> Session:
        session = Session(
            id=str(uuid.uuid4()),
            agent_file=agent_file,
            instruction=instruction,
            model=model,
            max_turns=max_turns,
            extra_context=extra_context,
            jira_url=jira_url,
            confluence_pages=confluence_pages or [],
            create_github_issue=create_github_issue,
            github_owner=github_owner,
            github_repo=github_repo,
            custom_agent=custom_agent,
        )
        await self._save(session)
        return session

    async def get(self, session_id: str) -> Session | None:
        raw = await self._r.get(_key(session_id))
        if raw is None:
            return None
        return Session.model_validate_json(raw)

    async def list(self, limit: int = 100) -> list[Session]:
        """Scan all live session keys and return up to `limit` sessions, newest first."""
        sessions: list[Session] = []
        seen = 0
        async for key in self._r.scan_iter(match=f"{_KEY_PREFIX}*", count=200):
            raw = await self._r.get(key)
            if raw is None:
                continue
            try:
                sessions.append(Session.model_validate_json(raw))
            except Exception:
                continue
            seen += 1
            if seen >= limit * 4:
                break
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]

    async def delete(self, session_id: str) -> bool:
        return bool(await self._r.delete(_key(session_id)))

    async def transition(self, session_id: str, new_state: SessionState) -> Session:
        session = await self._get_or_raise(session_id)
        session.transition(new_state)
        await self._save(session)
        return session

    async def set_result(self, session_id: str, result: str) -> Session:
        session = await self._get_or_raise(session_id)
        session.result = result
        session.updated_at = datetime.now(timezone.utc)
        await self._save(session)
        return session

    async def set_github_issue_url(self, session_id: str, url: str) -> Session:
        session = await self._get_or_raise(session_id)
        session.github_issue_url = url
        session.updated_at = datetime.now(timezone.utc)
        await self._save(session)
        return session

    async def set_error(self, session_id: str, error: str) -> Session:
        session = await self._get_or_raise(session_id)
        session.error = error
        session.updated_at = datetime.now(timezone.utc)
        await self._save(session)
        return session

    # -- Internals ---------------------------------------------------------

    async def _save(self, session: Session) -> None:
        await self._r.set(_key(session.id), session.model_dump_json(), ex=self._ttl)

    async def _get_or_raise(self, session_id: str) -> Session:
        session = await self.get(session_id)
        if session is None:
            raise KeyError(f"Session '{session_id}' not found.")
        return session
