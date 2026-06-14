"""Unit tests for the PR-1 transient-only healer.

Covers the contract that AgentRunner + BashTool depend on:
  - success on first try emits nothing, returns the result
  - recovers after a transient, emits recovered + retry events
  - exhaustion returns (None, exc, status) and emits an `exhausted` event
  - non-retriable failures short-circuit (no sleep, no retry)
  - sleep is called with monotonically increasing delays up to backoff_max

Pure asyncio + pytest. No Copilot SDK, no Redis, no network.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from healer import (
    HealBudget,
    Healer,
    is_preflight_exception,
    is_transient_exception,
    is_transient_status,
    redact,
    run_with_retry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Capturing:
    """Drop-in publisher that records every event for assertions."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def __call__(self, event: dict) -> None:
        self.events.append(event)


def _budget(**overrides: Any) -> HealBudget:
    base = dict(
        max_attempts_per_tool=3,
        backoff_base_ms=1,
        backoff_max_ms=4,
        backoff_jitter_ms=0,
    )
    base.update(overrides)
    return HealBudget(**base)


async def _no_sleep(_: float) -> None:
    return None


# ---------------------------------------------------------------------------
# Classifier tests
# ---------------------------------------------------------------------------


def test_is_transient_status() -> None:
    assert is_transient_status(429)
    assert is_transient_status(503)
    assert not is_transient_status(404)
    assert not is_transient_status(None)


def test_is_transient_exception() -> None:
    assert is_transient_exception(asyncio.TimeoutError())
    assert is_transient_exception(httpx.ConnectError("boom"))
    assert not is_transient_exception(ValueError("nope"))
    assert not is_transient_exception(None)


def test_is_preflight_exception() -> None:
    assert is_preflight_exception(httpx.ConnectError("no route"))
    # ReadTimeout is transient but NOT pre-flight — the server may have received
    # the write before timing out, so non-idempotent tools must not retry it.
    assert not is_preflight_exception(httpx.ReadTimeout("slow"))


def test_redact_strips_secrets_and_truncates() -> None:
    raw = "Authorization: Bearer abc.def.ghi token=xyz" + ("a" * 500)
    out = redact(raw, limit=80)
    assert "abc.def.ghi" not in out
    assert "xyz" not in out
    assert len(out) <= 80


# ---------------------------------------------------------------------------
# run_with_retry tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_on_first_attempt_emits_nothing() -> None:
    pub = _Capturing()
    healer = Healer(budget=_budget(), publish=pub)

    async def ok() -> str:
        return "fine"

    result, exc, status = await run_with_retry(
        healer=healer,
        tool="t",
        args={},
        op=ok,
        is_retriable=lambda _e, _s: True,
        sleep=_no_sleep,
    )
    assert result == "fine"
    assert exc is None and status is None
    assert pub.events == []  # silent on the happy path


@pytest.mark.asyncio
async def test_recovers_after_one_transient() -> None:
    pub = _Capturing()
    healer = Healer(budget=_budget(), publish=pub)
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom")
        return "ok"

    result, exc, _ = await run_with_retry(
        healer=healer,
        tool="t",
        args={"k": "v"},
        op=flaky,
        is_retriable=lambda e, _s: is_transient_exception(e),
        sleep=_no_sleep,
    )
    assert result == "ok"
    assert exc is None
    outcomes = [e["outcome"] for e in pub.events]
    assert outcomes == ["retry", "recovered"]


@pytest.mark.asyncio
async def test_exhausts_and_returns_last_error() -> None:
    pub = _Capturing()
    healer = Healer(budget=_budget(max_attempts_per_tool=3), publish=pub)

    async def always_503() -> str:
        req = httpx.Request("GET", "http://x")
        resp = httpx.Response(503, request=req, text="busy")
        raise httpx.HTTPStatusError("503", request=req, response=resp)

    result, exc, status = await run_with_retry(
        healer=healer,
        tool="t",
        args={},
        op=always_503,
        is_retriable=lambda _e, s: is_transient_status(s),
        sleep=_no_sleep,
    )
    assert result is None
    assert status == 503
    assert isinstance(exc, httpx.HTTPStatusError)
    outcomes = [e["outcome"] for e in pub.events]
    assert outcomes == ["retry", "retry", "exhausted"]


@pytest.mark.asyncio
async def test_non_retriable_short_circuits() -> None:
    pub = _Capturing()
    healer = Healer(budget=_budget(), publish=pub)
    calls = {"n": 0}

    async def hard_fail() -> str:
        calls["n"] += 1
        raise ValueError("structural")

    result, exc, _ = await run_with_retry(
        healer=healer,
        tool="t",
        args={},
        op=hard_fail,
        is_retriable=lambda _e, _s: False,
        sleep=_no_sleep,
    )
    assert result is None
    assert isinstance(exc, ValueError)
    assert calls["n"] == 1  # exactly one attempt, no retries
    assert [e["outcome"] for e in pub.events] == ["exhausted"]


@pytest.mark.asyncio
async def test_backoff_grows_exponentially_and_caps() -> None:
    """Pure-math check: confirm delays follow base * 2**(n-1), capped."""
    healer = Healer(budget=_budget(backoff_base_ms=100, backoff_max_ms=300))
    delays = [healer.delay_seconds(n) for n in (1, 2, 3, 4)]
    # jitter is 0 in the test budget, so values are deterministic.
    assert delays == [0.1, 0.2, 0.3, 0.3]


@pytest.mark.asyncio
async def test_publisher_failure_does_not_break_run() -> None:
    def boom(_event: dict) -> None:
        raise RuntimeError("event bus down")

    healer = Healer(budget=_budget(), publish=boom)

    async def flaky() -> str:
        return "ok"

    # If the publisher raised, this would fail. It must not.
    result, exc, _ = await run_with_retry(
        healer=healer,
        tool="t",
        args={},
        op=flaky,
        is_retriable=lambda _e, _s: True,
        sleep=_no_sleep,
    )
    assert result == "ok" and exc is None


@pytest.mark.asyncio
async def test_cancelled_error_propagates() -> None:
    """asyncio.CancelledError must never be swallowed by the retry loop."""
    pub = _Capturing()
    healer = Healer(budget=_budget(), publish=pub)

    async def cancelled() -> str:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await run_with_retry(
            healer=healer,
            tool="t",
            args={},
            op=cancelled,
            is_retriable=lambda _e, _s: True,
            sleep=_no_sleep,
        )
    assert pub.events == []  # no telemetry emitted for the cancel
