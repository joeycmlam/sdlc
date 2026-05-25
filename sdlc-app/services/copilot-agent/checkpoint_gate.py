"""Cross-process pause/resume gate for human_touch sessions.

The worker runs an AgentRunner in one process; the user approves checkpoints
through the API server in another. They coordinate via two Redis primitives:

1. EventBus  — the API stream the UI subscribes to. A 'checkpoint' event tells
                the operator what tool the agent wants to run.
2. Pub/sub   — a dedicated channel ``approval:{session_id}`` the API publishes
                an {action, comment} message to when /approve is called. The
                worker subscribes to this channel while blocked.

The gate is a callable: the AgentRunner invokes it before every tool call.
When the tool isn't gated (autonomous mode, or tool not in policy) the gate
returns Decision.APPROVED instantly with no Redis I/O.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from redis import asyncio as aioredis

from event_bus import EventBus
from session_store import RedisSessionStore


_APPROVAL_CHANNEL_PREFIX = "approval:"
_SUBSCRIBE_TIMEOUT_SECONDS = 60 * 60  # 1h — matches Arq job_timeout headroom


def approval_channel(session_id: str) -> str:
    return f"{_APPROVAL_CHANNEL_PREFIX}{session_id}"


class DecisionAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True)
class Decision:
    action: DecisionAction
    comment: str = ""

    @property
    def is_approved(self) -> bool:
        return self.action == DecisionAction.APPROVE


def matches_policy(tool_name: str, policy: list[str]) -> bool:
    """Return True when ``tool_name`` should be gated under ``policy``.

    Exact match against tool names (e.g. 'create_github_issue').
    Group tokens — special pseudo-names that match a family of operations the
    agent reaches via a generic shell — currently:
      - 'jira:write'        : bash_exec invoking jira_cli.py write subcommands
      - 'confluence:write'  : bash_exec invoking confluence_cli write subcommands
    """
    return tool_name in policy


class CheckpointGate:
    """Block tool execution until a human approves, when the policy requires it."""

    def __init__(
        self,
        session_id: str,
        execution_mode: Literal["autonomous", "human_touch"],
        approval_policy: list[str],
        store: RedisSessionStore,
        bus: EventBus,
        redis: aioredis.Redis,
    ) -> None:
        self._session_id = session_id
        self._mode = execution_mode
        self._policy = approval_policy
        self._store = store
        self._bus = bus
        self._redis = redis

    def _is_gated(self, tool_name: str) -> bool:
        if self._mode != "human_touch":
            return False
        return matches_policy(tool_name, self._policy)

    async def check(
        self,
        tool_name: str,
        args_preview: dict,
        summary: str = "",
    ) -> Decision:
        """Return immediately when not gated; otherwise pause until /approve."""
        if not self._is_gated(tool_name):
            return Decision(action=DecisionAction.APPROVE)

        checkpoint_id = str(uuid.uuid4())
        checkpoint = {
            "checkpoint_id": checkpoint_id,
            "tool": tool_name,
            "args_preview": args_preview,
            "summary": summary,
        }

        # Persist on the session so a late-joining UI can see what we're waiting on,
        # then publish to the event stream + flip FSM state.
        await self._store.set_pending_checkpoint(self._session_id, checkpoint)
        try:
            await self._store.transition(self._session_id, "awaiting_approval")
        except (ValueError, KeyError):
            # Session already terminal or missing — surface as rejection so the
            # runner stops cleanly instead of blocking forever.
            return Decision(
                action=DecisionAction.REJECT,
                comment="session is no longer running",
            )

        await self._bus.publish(
            self._session_id,
            {"type": "checkpoint", **checkpoint},
        )

        decision = await self._await_decision()

        await self._store.set_pending_checkpoint(self._session_id, None)
        try:
            await self._store.transition(self._session_id, "running")
        except (ValueError, KeyError):
            pass

        await self._bus.publish(
            self._session_id,
            {
                "type": "checkpoint_resolved",
                "checkpoint_id": checkpoint_id,
                "action": decision.action.value,
                "comment": decision.comment,
            },
        )

        return decision

    async def _await_decision(self) -> Decision:
        """Subscribe to the approval channel and wait for the operator."""
        pubsub = self._redis.pubsub()
        channel = approval_channel(self._session_id)
        await pubsub.subscribe(channel)
        try:
            # get_message with a long timeout, looped, so the asyncio task remains
            # cancellable by the worker if the job is killed.
            deadline = asyncio.get_event_loop().time() + _SUBSCRIBE_TIMEOUT_SECONDS
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    return Decision(
                        action=DecisionAction.REJECT,
                        comment="approval timeout",
                    )
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=min(remaining, 30.0),
                )
                if msg is None:
                    continue
                try:
                    payload = json.loads(msg["data"])
                except (TypeError, ValueError, KeyError):
                    continue
                action_raw = (payload.get("action") or "").lower()
                if action_raw not in ("approve", "reject"):
                    continue
                return Decision(
                    action=DecisionAction(action_raw),
                    comment=payload.get("comment", ""),
                )
        finally:
            try:
                await pubsub.unsubscribe(channel)
            except Exception:
                pass
            try:
                await pubsub.aclose()
            except AttributeError:
                await pubsub.close()


async def publish_decision(
    redis: aioredis.Redis,
    session_id: str,
    action: DecisionAction | str,
    comment: str = "",
) -> int:
    """Side-channel signal from the API to the worker. Returns subscriber count."""
    action_value = action.value if isinstance(action, DecisionAction) else action
    return await redis.publish(
        approval_channel(session_id),
        json.dumps({"action": action_value, "comment": comment}),
    )
