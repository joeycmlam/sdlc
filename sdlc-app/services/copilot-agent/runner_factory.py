"""
Runner factory — picks the right execution backend for a given model.

The GitHub Copilot SDK only knows GitHub Models, so requests targeting other
providers (DeepSeek today, anything else tomorrow) cannot go through
AgentRunner. They go through the LangGraph-based ``run_graph`` instead, which
uses ``llm_factory.build_llm`` to talk to any OpenAI-compatible endpoint.

Call sites use ``make_runner(config, ...)`` and then ``.run(...)`` — the same
shape AgentRunner already exposes, so the worker and api_server don't need to
care which backend they got.
"""

from __future__ import annotations

from typing import Callable, Optional

from agent_copilot import AgentConfig, AgentRunner, CheckpointHandler
from healer import Healer
from llm_factory import PROVIDERS


# Provider whose native runner is AgentRunner (GitHub Copilot SDK). Anything
# else goes through the LangGraph path.
_NATIVE_PROVIDER = "github"


def _uses_graph_runner(model: str) -> bool:
    if "/" not in model:
        return False
    prefix = model.split("/", 1)[0]
    return prefix in PROVIDERS and prefix != _NATIVE_PROVIDER


class _GraphRunnerAdapter:
    """Exposes AgentRunner's ``.run(...)`` shape on top of graph_runner.run_graph.

    All callbacks — chunks, tool starts, tool args, tool results, bash
    results, turn ticks — are forwarded so the UI sees the same event
    stream regardless of which backend handled the session.
    """

    def __init__(
        self,
        config: AgentConfig,
        checkpoint_handler: Optional[CheckpointHandler] = None,
        healer: Optional[Healer] = None,
    ) -> None:
        self._config = config
        self._checkpoint_handler = checkpoint_handler
        self._healer = healer

    async def run(
        self,
        initial_prompt: str,
        extra_context: str = "",
        on_chunk: Optional[Callable[[str], None]] = None,
        on_tool: Optional[Callable[..., None]] = None,
        on_bash_result: Optional[Callable[[str, str], None]] = None,
        on_turn: Optional[Callable[[int, int], None]] = None,
        on_tool_args: Optional[Callable[..., None]] = None,
        on_tool_result: Optional[Callable[..., None]] = None,
    ) -> str:
        from graph_runner import run_graph

        return await run_graph(
            self._config,
            initial_prompt,
            extra_context=extra_context,
            checkpoint_handler=self._checkpoint_handler,
            healer=self._healer,
            on_chunk=on_chunk,
            on_tool=on_tool,
            on_bash_result=on_bash_result,
            on_turn=on_turn,
            on_tool_args=on_tool_args,
            on_tool_result=on_tool_result,
        )


def make_runner(
    config: AgentConfig,
    *,
    checkpoint_handler: Optional[CheckpointHandler] = None,
    healer: Optional[Healer] = None,
):
    """Return an AgentRunner or graph-runner adapter based on ``config.model``."""
    if _uses_graph_runner(config.model):
        return _GraphRunnerAdapter(
            config,
            checkpoint_handler=checkpoint_handler,
            healer=healer,
        )
    return AgentRunner(
        config,
        checkpoint_handler=checkpoint_handler,
        healer=healer,
    )
