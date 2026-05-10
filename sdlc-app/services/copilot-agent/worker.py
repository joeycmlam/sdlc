"""Arq worker — executes AgentRunner jobs and streams events to Redis.

Run with either:
    arq worker.WorkerSettings
    agent-worker                    (installed console script)

Workers consume jobs enqueued by api_server (`/sessions/{id}/run`),
load the session from RedisSessionStore, run the AgentRunner, publish
chunk/tool/done/error events to the EventBus, and persist the final
result + state.

Multiple worker processes can be launched in parallel for horizontal
scale; each Arq worker handles up to `max_jobs` concurrent sessions.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from arq.connections import RedisSettings

from agent_copilot import AgentConfig, AgentRunner
from event_bus import EventBus
from session_store import RedisSessionStore

_here = Path(__file__).parent
AGENTS_DIR = _here / "agents"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


async def startup(ctx: dict) -> None:
    ctx["session_store"] = RedisSessionStore.from_url(REDIS_URL)
    ctx["event_bus"] = EventBus.from_url(REDIS_URL)


async def shutdown(ctx: dict) -> None:
    await ctx["session_store"].close()
    await ctx["event_bus"].close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_agent_path(agent_file: str) -> Path:
    """Validate agent_file lives under AGENTS_DIR — guard against path traversal."""
    resolved = (_here / agent_file).resolve()
    if not resolved.is_relative_to(_here.resolve()):
        raise ValueError(f"Invalid agent_file path: {agent_file!r}")
    if not resolved.exists():
        raise FileNotFoundError(f"Agent file not found: {agent_file!r}")
    return resolved


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------


async def run_session_job(ctx: dict, session_id: str) -> None:
    """Execute one session end-to-end."""
    store: RedisSessionStore = ctx["session_store"]
    bus: EventBus = ctx["event_bus"]

    session = await store.get(session_id)
    if session is None:
        # Deleted before we picked it up — nothing to do.
        return

    # A bounded queue + dedicated drain task preserves event order without
    # the GC hazard of unawaited create_task calls inside sync callbacks.
    publish_queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=1024)

    async def _drain() -> None:
        while True:
            event = await publish_queue.get()
            if event is None:
                return
            try:
                await bus.publish(session_id, event)
            except Exception as exc:
                # Don't let publish failures kill the run; log and continue.
                print(f"[worker] publish failed for {session_id}: {exc}", flush=True)

    drain_task = asyncio.create_task(_drain())

    def _on_chunk(chunk: str) -> None:
        if chunk:
            try:
                publish_queue.put_nowait({"type": "chunk", "content": chunk})
            except asyncio.QueueFull:
                pass  # drop on backpressure rather than block the runner

    def _on_tool(name: str) -> None:
        if name:
            try:
                publish_queue.put_nowait({"type": "tool", "name": name})
            except asyncio.QueueFull:
                pass

    try:
        agent_path = _resolve_agent_path(session.agent_file)
        system_prompt = agent_path.read_text(encoding="utf-8").strip()
        config = AgentConfig(
            system_prompt=system_prompt,
            model=session.model,
            streaming=True,
            max_turns=min(session.max_turns, 50),
            base_dir=_here,
        )
        runner = AgentRunner(config)

        ctx_parts = [session.extra_context] if session.extra_context else []
        if session.jira_url:
            ctx_parts.append(f"Jira ticket: {session.jira_url}")
        if session.confluence_pages:
            ctx_parts.append(
                "Confluence pages:\n" + "\n".join(f"- {p}" for p in session.confluence_pages)
            )
        extra_context = "\n\n".join(ctx_parts)

        result = await runner.run(
            session.instruction,
            extra_context=extra_context,
            on_chunk=_on_chunk,
            on_tool=_on_tool,
        )

        await store.set_result(session_id, result)
        try:
            await store.transition(session_id, "completed")
        except (ValueError, KeyError):
            pass  # session was deleted or already terminal
        publish_queue.put_nowait(
            {"type": "done", "content": result, "session_id": session_id}
        )

    except Exception as exc:
        error_msg = str(exc)
        try:
            await store.set_error(session_id, error_msg)
            await store.transition(session_id, "failed")
        except (ValueError, KeyError):
            pass
        publish_queue.put_nowait({"type": "error", "message": error_msg, "code": 500})

    finally:
        publish_queue.put_nowait(None)
        await drain_task
        try:
            await bus.end(session_id)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Arq settings
# ---------------------------------------------------------------------------


class WorkerSettings:
    functions = [run_session_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    job_timeout = 600       # 10 min per session
    max_jobs = 10           # concurrent jobs per worker
    keep_result = 3600      # keep job result for 1h (Arq's own bookkeeping)


def cli_main() -> None:
    """Entry point: `agent-worker` → arq.worker.run_worker(WorkerSettings)."""
    from arq.worker import run_worker

    run_worker(WorkerSettings)
