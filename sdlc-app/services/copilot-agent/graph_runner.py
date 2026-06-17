"""
LangGraph-based agent runner — Phase 2 of the LangGraph migration.

Replaces AgentRunner (Copilot SDK event loop) with a LangGraph ReAct agent graph.
All tool business logic is preserved; the orchestration layer changes from a
hand-rolled turn loop to create_react_agent.

Phases:
  Phase 2 (this file):  AgentRunner → LangGraph ReAct graph
  Phase 3:             Session FSM → LangGraph RedisSaver checkpointer
  Phase 4:             CheckpointGate → LangGraph interrupt()
  Phase 5:             invoke_agent tool → LangGraph subgraphs
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

import frontmatter as _fm
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from agent_copilot import (
    MAX_RECURSION_DEPTH,
    SUB_AGENT_MAX_TURNS,
    AgentConfig,
    BashTool,
    CheckpointHandler,
    _TOOL_TAG_MAP,
)
from healer import (
    Healer,
    is_preflight_exception,
    is_transient_exception,
    is_transient_status,
    run_with_retry,
)
from llm_factory import build_llm


# ---------------------------------------------------------------------------
# Pydantic schemas for tool arguments
# ---------------------------------------------------------------------------

class _BashInput(BaseModel):
    command: str

class _InvokeAgentInput(BaseModel):
    agent_file: str
    instruction: str
    context: str = ""

class _GithubIssueInput(BaseModel):
    owner: str
    repo: str
    title: str
    prompt: str
    agent: str = ""
    skills: list[str] = []

class _ConfluenceInput(BaseModel):
    url: str

class _FinishInput(BaseModel):
    summary: str = ""


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------

def build_lc_tools(
    config: AgentConfig,
    checkpoint_handler: CheckpointHandler | None = None,
    healer: Healer | None = None,
    on_bash_result: Callable[[str, str], None] | None = None,
) -> list[StructuredTool]:
    """Build LangChain StructuredTool instances from an AgentConfig.

    Reuses BashTool's validation, blocklist, and healer logic. Return types
    are plain strings (not Copilot SDK ToolResult) for LangGraph compatibility.
    """
    _healer = healer or Healer()
    _bash_impl = BashTool(checkpoint_handler=checkpoint_handler, healer=_healer)
    _bash_impl.on_bash_result = on_bash_result

    # ----- bash_exec --------------------------------------------------------

    async def bash_exec(command: str) -> str:
        """Execute a shell command and return its stdout/stderr."""
        class _Inv:
            arguments = {"command": command}
        result = await _bash_impl(_Inv())
        return getattr(result, "text_result_for_llm", str(result))

    # ----- invoke_agent (bridges to AgentRunner; Phase 5 will replace with subgraph) -----

    async def invoke_agent(agent_file: str, instruction: str, context: str = "") -> str:
        """Delegate a sub-task to a specialised sub-agent defined by an agent file.

        Runs the sub-agent in isolation with its own conversation history and
        turn budget. Returns the sub-agent's final text output as a string.
        """
        from runner_factory import make_runner

        if config.depth >= MAX_RECURSION_DEPTH:
            return "[Error: max sub-agent recursion depth reached]"

        agent_path = config.base_dir / agent_file
        if not agent_path.exists():
            return (
                f"[Error: Agent file '{agent_file}' not found at {agent_path}. "
                "Use the relative path including directory prefix, "
                "e.g. 'agents/jira-reader.md'.]"
            )

        sub_prompt = agent_path.read_text(encoding="utf-8").strip()
        try:
            _post = _fm.loads(sub_prompt)
            _tag_list: list[str] | None = _post.metadata.get("tools")
            sub_allowed = (
                None if _tag_list is None
                else [n for tag in _tag_list for n in _TOOL_TAG_MAP.get(tag, [])]
            )
        except Exception:
            sub_allowed = None

        sub_config = AgentConfig(
            system_prompt=sub_prompt,
            model=config.model,
            streaming=config.streaming,
            max_turns=SUB_AGENT_MAX_TURNS,
            depth=config.depth + 1,
            base_dir=config.base_dir,
            allowed_tools=sub_allowed,
        )
        result = await make_runner(
            sub_config, checkpoint_handler=checkpoint_handler, healer=_healer
        ).run(instruction, extra_context=context, on_bash_result=on_bash_result)
        return result or "(sub-agent returned no output)"

    # ----- create_github_issue ----------------------------------------------

    async def create_github_issue(
        owner: str,
        repo: str,
        title: str,
        prompt: str,
        agent: str = "",
        skills: list[str] = [],
    ) -> str:
        """Create a GitHub issue in the specified repository."""
        import httpx

        if not (owner and repo and title and prompt):
            return "[Error: create_github_issue requires owner, repo, title, prompt]"

        if checkpoint_handler is not None:
            decision = await checkpoint_handler(
                "create_github_issue",
                {
                    "owner": owner,
                    "repo": repo,
                    "title": title,
                    "body_preview": prompt[:280],
                    "agent": agent,
                    "skills": skills,
                },
                summary=f"Open issue in {owner}/{repo}: {title}",
            )
            if not decision.is_approved:
                reason = decision.comment or "operator rejected the action"
                return f"[Rejected by operator: {reason}]"

        api_base = os.getenv("AGENT_API_URL", "http://localhost:8000")
        payload: dict[str, Any] = {
            "owner": owner, "repo": repo, "title": title,
            "body": prompt, "assign_to_copilot": True,
        }
        if agent:
            payload["custom_agent"] = agent
        if skills:
            payload["skills"] = skills

        async def _do_create() -> dict:
            async with httpx.AsyncClient(timeout=30) as http:
                resp = await http.post(f"{api_base}/github/issues", json=payload)
                resp.raise_for_status()
                return resp.json()

        data, exc, status = await run_with_retry(
            healer=_healer, tool="create_github_issue",
            args={"owner": owner, "repo": repo, "title": title},
            op=_do_create,
            is_retriable=lambda e, _s: is_preflight_exception(e),
        )
        if exc is None:
            assigned = (
                "assigned to Copilot" if data.get("copilot_assigned")
                else "Copilot assignment skipped"
            )
            return f"Created issue #{data['number']} ({assigned}): {data['html_url']}"
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            return f"[Error creating issue: HTTP {status} — {exc.response.text}]"
        return f"[Error creating issue: {exc}]"

    # ----- read_confluence --------------------------------------------------

    async def read_confluence(url: str) -> str:
        """Fetch the Markdown-rendered content of a Confluence page by URL.

        Requires the atlassian-bridge service to be running on :8002.
        """
        import httpx

        if not url:
            return "[Error: read_confluence requires 'url']"

        _bridge = os.getenv("ATLASSIAN_BRIDGE_URL", "http://localhost:8002")

        async def _do_fetch() -> dict:
            async with httpx.AsyncClient(timeout=30) as http:
                resp = await http.post(f"{_bridge}/confluence/fetch", json={"url": url})
                resp.raise_for_status()
                return resp.json()

        data, exc, status = await run_with_retry(
            healer=_healer, tool="read_confluence", args={"url": url},
            op=_do_fetch,
            is_retriable=lambda e, s: is_transient_exception(e) or is_transient_status(s),
        )
        if exc is None:
            content = data.get("body_markdown") or data.get("content") or str(data)
            title = data.get("title", "")
            return f"# {title}\n\n{content}" if title else content
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            return f"[Error fetching Confluence page: HTTP {status} — {exc.response.text}]"
        return f"[Error fetching Confluence page: {exc}]"

    # ----- finish -----------------------------------------------------------

    def finish(summary: str = "") -> str:
        """Signal that the workflow is fully complete.

        Call this as the LAST action once all steps are done and all outputs
        have been delivered. Do NOT call mid-workflow.
        """
        msg = summary.strip() or ""
        if msg:
            print(f"\n\033[32m[Agent finished]\033[0m {msg}", flush=True)
        else:
            print("\n\033[32m[Agent finished]\033[0m", flush=True)
        return "[Workflow complete. Session will now end.]"

    # ----- assemble tool list -----------------------------------------------

    all_tools: list[StructuredTool] = [
        StructuredTool.from_function(
            name="bash_exec",
            description=BashTool.DESCRIPTION,
            coroutine=bash_exec,
            args_schema=_BashInput,
        ),
        StructuredTool.from_function(
            name="invoke_agent",
            description=(
                "Delegate a sub-task to a specialised sub-agent defined by an agent file. "
                "Runs the sub-agent in isolation with its own conversation history and "
                "turn budget. Returns the sub-agent's final text output as a string. "
                "Use this instead of reading agent files inline or switching persona."
            ),
            coroutine=invoke_agent,
            args_schema=_InvokeAgentInput,
        ),
        StructuredTool.from_function(
            name="create_github_issue",
            description=(
                "Create a GitHub issue in the specified repository and optionally assign "
                "it to a specialised Copilot agent. Returns the URL of the created issue."
            ),
            coroutine=create_github_issue,
            args_schema=_GithubIssueInput,
        ),
        StructuredTool.from_function(
            name="read_confluence",
            description=(
                "Fetch the Markdown-rendered content of a Confluence page by its URL. "
                "Requires the atlassian-bridge service to be running on :8002."
            ),
            coroutine=read_confluence,
            args_schema=_ConfluenceInput,
        ),
        StructuredTool.from_function(
            name="finish",
            description=(
                "Signal that the workflow is fully complete. "
                "Call this as the LAST action once all steps are done and all outputs "
                "have been delivered. Do NOT call finish mid-workflow."
            ),
            func=finish,
            args_schema=_FinishInput,
        ),
    ]

    allowed = config.allowed_tools
    if allowed is None:
        return all_tools
    # Always include `finish` so the agent can signal completion.
    return [t for t in all_tools if t.name == "finish" or t.name in allowed]


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_agent_graph(
    config: AgentConfig,
    checkpointer=None,
    checkpoint_handler: CheckpointHandler | None = None,
    healer: Healer | None = None,
    on_bash_result: Callable[[str, str], None] | None = None,
):
    """Compile a LangGraph ReAct agent graph for the given AgentConfig.

    Args:
        config:             Agent configuration (system_prompt, model, max_turns, …).
        checkpointer:       LangGraph checkpointer (e.g. RedisSaver). None = stateless.
        checkpoint_handler: Human-in-the-loop gate called before write tools (Phase 4).
        healer:             Healer instance for transient-failure retries.
        on_bash_result:     Callback(command, result_preview) streamed to EventBus.

    Returns:
        A compiled CompiledGraph. Invoke via::

            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=prompt)]},
                config={"configurable": {"thread_id": session_id},
                        "recursion_limit": config.max_turns * 2 + 2},
            )
    """
    tools = build_lc_tools(
        config,
        checkpoint_handler=checkpoint_handler,
        healer=healer,
        on_bash_result=on_bash_result,
    )
    llm = build_llm(config.model)
    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=config.system_prompt,
        checkpointer=checkpointer,
    )


# ---------------------------------------------------------------------------
# Convenience run helper (mirrors AgentRunner.run() signature for easy swap)
# ---------------------------------------------------------------------------

async def run_graph(
    config: AgentConfig,
    initial_prompt: str,
    extra_context: str = "",
    checkpointer=None,
    thread_id: str = "default",
    checkpoint_handler: CheckpointHandler | None = None,
    healer: Healer | None = None,
    on_chunk: Callable[[str], None] | None = None,
    on_tool: Callable[[str], None] | None = None,
    on_bash_result: Callable[[str, str], None] | None = None,
    on_turn: Callable[[int, int], None] | None = None,
) -> str:
    """Run an agent graph to completion and return the final text output.

    Drop-in async replacement for AgentRunner.run(). Streams chunks and tool
    events via the provided callbacks (same contract as AgentRunner).
    """
    graph = build_agent_graph(
        config,
        checkpointer=checkpointer,
        checkpoint_handler=checkpoint_handler,
        healer=healer,
        on_bash_result=on_bash_result,
    )

    user_message = (
        f"{extra_context}\n\n{initial_prompt}" if extra_context else initial_prompt
    )
    run_config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": config.max_turns * 2 + 2,
    }

    last_ai_content = ""
    turn = 0

    async for event in graph.astream_events(
        {"messages": [HumanMessage(content=user_message)]},
        config=run_config,
        version="v2",
    ):
        kind = event.get("event", "")
        data = event.get("data", {})

        if kind == "on_chat_model_stream":
            chunk = data.get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                if on_chunk is not None:
                    on_chunk(chunk.content)

        elif kind == "on_tool_start":
            tool_name = event.get("name", "")
            if on_tool is not None:
                on_tool(tool_name)

        elif kind == "on_chain_end" and event.get("name") == "LangGraph":
            output = data.get("output", {})
            messages = output.get("messages", [])
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    last_ai_content = (
                        msg.content if isinstance(msg.content, str)
                        else " ".join(
                            p.get("text", "") for p in msg.content
                            if isinstance(p, dict)
                        )
                    )
                    break

        elif kind == "on_chain_start" and event.get("name") == "agent":
            turn += 1
            if on_turn is not None:
                on_turn(turn, config.max_turns)

    return last_ai_content
