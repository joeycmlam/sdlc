"""Self-healing layer for tool invocations — PR-1: transient-only.

Wraps an async operation in an exponential-backoff retry loop with a
deterministic classifier. No LLM, no sub-agents — those land in PR-2.

Wiring:
    AgentRunner is given an optional Healer at construction. BashTool and
    the HTTP-backed tool handlers call `run_with_retry` around the
    network/subprocess boundary so callers see a single "did it succeed"
    answer. Every retry decision is emitted as a `tool_heal` event so the
    session timeline shows the recovery attempt.

Design notes:
  - Classification is *deterministic* (exception type + status code).
    Cost stays bounded.
  - `create_github_issue` is non-idempotent — only ConnectError (pre-flight)
    is treated as retriable for that path. Idempotent GETs may retry on
    any transient.
  - Telemetry failures never bubble. Healing must not introduce new error
    paths.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import httpx


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HealBudget:
    max_attempts_per_tool: int = 3
    backoff_base_ms: int = 500
    backoff_max_ms: int = 8_000
    backoff_jitter_ms: int = 250

    @classmethod
    def from_env(cls) -> "HealBudget":
        return cls(
            max_attempts_per_tool=int(os.getenv("HEAL_MAX_ATTEMPTS_PER_TOOL", "3")),
            backoff_base_ms=int(os.getenv("HEAL_BACKOFF_BASE_MS", "500")),
            backoff_max_ms=int(os.getenv("HEAL_BACKOFF_MAX_MS", "8000")),
            backoff_jitter_ms=int(os.getenv("HEAL_BACKOFF_JITTER_MS", "250")),
        )


# ---------------------------------------------------------------------------
# Classifiers
# ---------------------------------------------------------------------------


_TRANSIENT_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})

_TRANSIENT_EXC: tuple[type[BaseException], ...] = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
    asyncio.TimeoutError,
    ConnectionError,
)


def is_transient_exception(exc: BaseException | None) -> bool:
    return exc is not None and isinstance(exc, _TRANSIENT_EXC)


def is_transient_status(status: int | None) -> bool:
    return status is not None and status in _TRANSIENT_STATUS


def is_preflight_exception(exc: BaseException | None) -> bool:
    """True iff we can be sure the request never reached the server.

    Safe-to-retry signal for *non-idempotent* tools (e.g. create_github_issue).
    """
    return exc is not None and isinstance(exc, (httpx.ConnectError, ConnectionError))


# ---------------------------------------------------------------------------
# Redaction (for telemetry)
# ---------------------------------------------------------------------------


# Authorization headers carry a scheme + token (`Bearer abc.def.ghi`), so
# consume the rest of the line. Other keywords stop at the first whitespace —
# they're typically `key=value` pairs.
_SECRET_RE_AUTH = re.compile(r"(?i)authorization\s*[:=]\s*[^\r\n]+")
_SECRET_RE_KV = re.compile(
    r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*\S+"
)


def redact(text: str, limit: int = 200) -> str:
    text = _SECRET_RE_AUTH.sub("Authorization=[REDACTED]", text)
    text = _SECRET_RE_KV.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    return text[:limit]


# ---------------------------------------------------------------------------
# Healer
# ---------------------------------------------------------------------------


Publisher = Callable[[dict], Any]  # may return None or Awaitable[None]


@dataclass
class Attempt:
    tool: str
    args: dict
    attempt_n: int
    error: BaseException | None = None
    status_code: int | None = None
    duration_ms: int = 0


class Healer:
    """Deterministic transient-failure healer.

    PR-1 responsibilities:
      - own the retry budget
      - compute exponential backoff with jitter
      - emit `tool_heal` events through an optional publisher

    Out of scope for PR-1: semantic remediation via sub-agents, structural
    failure escalation through the checkpoint gate. Those land in PR-2 / PR-3.
    """

    def __init__(
        self,
        budget: HealBudget | None = None,
        publish: Publisher | None = None,
    ) -> None:
        self._budget = budget or HealBudget.from_env()
        self._publish = publish

    @property
    def budget(self) -> HealBudget:
        return self._budget

    def delay_seconds(self, attempt_n: int) -> float:
        """Exponential backoff with jitter. attempt_n is 1-indexed."""
        b = self._budget
        raw_ms = min(b.backoff_base_ms * (2 ** (attempt_n - 1)), b.backoff_max_ms)
        jitter = random.uniform(0, b.backoff_jitter_ms)
        return (raw_ms + jitter) / 1000.0

    async def emit(self, payload: dict) -> None:
        if self._publish is None:
            return
        try:
            result = self._publish({"type": "tool_heal", **payload})
            if inspect.isawaitable(result):
                await result
        except Exception:
            # Telemetry must never break the agent.
            pass


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------


Retriable = Callable[[BaseException | None, int | None], bool]


async def run_with_retry(
    *,
    healer: Healer,
    tool: str,
    args: dict,
    op: Callable[[], Awaitable[Any]],
    is_retriable: Retriable,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> tuple[Any | None, BaseException | None, int | None]:
    """Run `op` with retry-on-transient.

    Returns a triple (result, last_exception, last_status_code).
    On success: (result, None, None).
    On exhaustion or non-retriable failure: (None, exc, status).

    HTTP failures raised as `httpx.HTTPStatusError` have their status code
    surfaced for both telemetry and the caller's error rendering.
    """
    budget = healer.budget
    last_exc: BaseException | None = None
    last_status: int | None = None

    for n in range(1, budget.max_attempts_per_tool + 1):
        t0 = time.monotonic()
        try:
            result = await op()
        except (KeyboardInterrupt, asyncio.CancelledError):
            raise
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            last_status = exc.response.status_code if exc.response is not None else None
        except BaseException as exc:
            last_exc = exc
            last_status = None
        else:
            if n > 1:
                await healer.emit({
                    "tool": tool,
                    "outcome": "recovered",
                    "attempt_n": n,
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                })
            return result, None, None

        duration_ms = int((time.monotonic() - t0) * 1000)
        retry = (
            is_retriable(last_exc, last_status)
            and n < budget.max_attempts_per_tool
        )

        await healer.emit({
            "tool": tool,
            "args": _safe_args(args),
            "outcome": "retry" if retry else "exhausted",
            "attempt_n": n,
            "status_code": last_status,
            "error_class": type(last_exc).__name__ if last_exc else None,
            "error_excerpt": redact(str(last_exc) or ""),
            "duration_ms": duration_ms,
        })

        if not retry:
            return None, last_exc, last_status

        await sleep(healer.delay_seconds(n))

    return None, last_exc, last_status


def _safe_args(args: dict) -> dict:
    """Trim and redact tool args before publishing them on the event bus."""
    safe: dict[str, Any] = {}
    for k, v in args.items():
        if isinstance(v, str):
            safe[k] = redact(v)
        else:
            safe[k] = v
    return safe
