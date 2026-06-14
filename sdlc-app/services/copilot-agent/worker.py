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

import frontmatter as fm
from arq.connections import RedisSettings
from redis import asyncio as aioredis

from agent_copilot import AgentConfig, AgentRunner, _TOOL_TAG_MAP
from checkpoint_gate import CheckpointGate
from event_bus import EventBus
from healer import Healer
from session_store import RedisSessionStore

_here = Path(__file__).parent
# When installed as a wheel (e.g. inside Docker), __file__ resolves to
# site-packages rather than the runtime working directory.  Re-anchor _here
# to the parent of AGENTS_DIR so that agent/skill/team lookups work correctly.
_agents_dir_env = os.getenv("AGENTS_DIR")
if _agents_dir_env:
    _here = Path(_agents_dir_env).parent

AGENTS_DIR = Path(os.getenv("AGENTS_DIR", str(_here / "agents")))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Hard timeout applied *inside* run_session_job so TimeoutError is caught by
# our exception handler and the session is transitioned to failed instead of
# being left in "running" forever.  Keep this strictly below job_timeout so
# arq's outer wait_for never fires first.
_SESSION_RUN_TIMEOUT = int(os.getenv("SESSION_RUN_TIMEOUT_SECONDS", "570"))  # 9m 30s

# Arq's own hard cap per job.  Must be > _SESSION_RUN_TIMEOUT so our inner
# TimeoutError always fires first.  Configurable so operators can raise both
# limits together (e.g. SESSION_JOB_TIMEOUT_SECONDS=1800 for long sessions).
_SESSION_JOB_TIMEOUT = int(os.getenv("SESSION_JOB_TIMEOUT_SECONDS", "600"))  # 10 min


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


async def startup(ctx: dict) -> None:
    ctx["session_store"] = RedisSessionStore.from_url(REDIS_URL)
    ctx["event_bus"] = EventBus.from_url(REDIS_URL)
    # Separate Redis connection for pub/sub — the session store / event bus
    # connections are kept on stream ops; pub/sub needs its own client.
    ctx["redis_pubsub"] = aioredis.from_url(REDIS_URL, decode_responses=True)


async def shutdown(ctx: dict) -> None:
    await ctx["session_store"].close()
    await ctx["event_bus"].close()
    pubsub_client = ctx.get("redis_pubsub")
    if pubsub_client is not None:
        try:
            await pubsub_client.aclose()
        except AttributeError:
            await pubsub_client.close()


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

    def _on_bash_result(command: str, result_preview: str) -> None:
        try:
            publish_queue.put_nowait({
                "type": "bash_result",
                "command": command,
                "result": result_preview,
            })
        except asyncio.QueueFull:
            pass

    def _on_turn(turn_n: int, max_turns: int) -> None:
        try:
            publish_queue.put_nowait({"type": "turn", "n": turn_n, "max_turns": max_turns})
        except asyncio.QueueFull:
            pass

    def _on_heal(event: dict) -> None:
        # Route heal telemetry through the same ordered queue as agent events
        # so the session timeline shows retries inline with tool calls.
        try:
            publish_queue.put_nowait(event)
        except asyncio.QueueFull:
            pass

    try:
        agent_path = _resolve_agent_path(session.agent_file)
        system_prompt = agent_path.read_text(encoding="utf-8").strip()

        # Derive allowed_tools from the agent's frontmatter `tools` list.
        # None → no restriction (all tools); [] → no active tools (read-only agent).
        try:
            post = fm.loads(system_prompt)
            tag_list: list[str] | None = post.metadata.get("tools")
            if tag_list is None:
                allowed_tools = None  # no frontmatter → all tools
            else:
                allowed_tools: list[str] = []
                for tag in tag_list:
                    allowed_tools.extend(_TOOL_TAG_MAP.get(tag, []))
        except Exception:
            allowed_tools = None

        config = AgentConfig(
            system_prompt=system_prompt,
            model=session.model,
            streaming=True,
            max_turns=min(session.max_turns, 50),
            base_dir=_here,
            allowed_tools=allowed_tools,
        )
        gate = CheckpointGate(
            session_id=session_id,
            execution_mode=session.execution_mode,
            approval_policy=session.approval_policy,
            store=store,
            bus=bus,
            redis=ctx["redis_pubsub"],
        )
        healer = Healer(publish=_on_heal)
        runner = AgentRunner(config, checkpoint_handler=gate.check, healer=healer)

        ctx_parts = [session.extra_context] if session.extra_context else []
        if session.jira_url:
            ctx_parts.append(f"Jira ticket: {session.jira_url}")
        if session.confluence_pages:
            ctx_parts.append(
                "Confluence pages:\n" + "\n".join(f"- {p}" for p in session.confluence_pages)
            )
        extra_context = "\n\n".join(ctx_parts)

        result = await asyncio.wait_for(
            runner.run(
                session.instruction,
                extra_context=extra_context,
                on_chunk=_on_chunk,
                on_tool=_on_tool,
                on_bash_result=_on_bash_result,
                on_turn=_on_turn,
            ),
            timeout=session.timeout_seconds or _SESSION_RUN_TIMEOUT,
        )

        await store.set_result(session_id, result)
        try:
            await store.transition(session_id, "completed")
        except (ValueError, KeyError):
            pass  # session was deleted or already terminal
        publish_queue.put_nowait(
            {"type": "done", "content": result, "session_id": session_id}
        )

    except TimeoutError:
        session_timeout = session.timeout_seconds or _SESSION_RUN_TIMEOUT
        error_msg = f"Session timed out after {session_timeout}s."
        try:
            await store.set_error(session_id, error_msg)
            await store.transition(session_id, "failed")
        except (ValueError, KeyError):
            pass
        publish_queue.put_nowait({"type": "error", "message": error_msg, "code": 408})

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
    job_timeout = _SESSION_JOB_TIMEOUT
    max_jobs = 10           # concurrent jobs per worker
    keep_result = 3600      # keep job result for 1h (Arq's own bookkeeping)


def cli_main() -> None:
    """Entry point: `agent-worker` → arq.worker.run_worker(WorkerSettings)."""
    from arq.worker import run_worker

    run_worker(WorkerSettings)
