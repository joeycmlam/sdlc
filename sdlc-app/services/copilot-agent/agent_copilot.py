#!/usr/bin/env python3
"""
CLI Agent — GitHub Copilot SDK edition.

Uses the official `github-copilot-sdk` Python package, which delegates to the
GitHub Copilot CLI running locally.  No GITHUB_TOKEN or API key is required —
authentication is handled by the Copilot CLI's own credential store.

Key differences from agent.py (azure-ai-inference):
  - SDK:      github-copilot-sdk  (not azure-ai-inference)
  - Auth:     Copilot CLI credential store  (no GITHUB_TOKEN needed at runtime)
  - Async:    asyncio / async-await throughout
  - Events:   event-driven session model (session.idle signals turn completion)
  - Streaming: assistant.message.delta events
  - Tools:    registered via define_tool() at session creation
  - New tool: invoke_agent — real sub-agent delegation, isolated session+turn budget
  - Loop:     smarter text-only abort, step-aware continuation, --max-turns

Prerequisites:
  pip install github-copilot-sdk
  # GitHub Copilot CLI must be installed and authenticated:
  gh extension install github/gh-copilot
  gh auth login

Usage:
  python agent_copilot.py -a agents/assistant.md -m gpt-4o -i "Explain recursion"
  python agent_copilot.py -a agents/ba.agent.md -m gpt-4o -i "please analyze the jira SCRUM-12" --max-turns 40
  python agent_copilot.py -a agents/coder.md -m gpt-4o --interactive
  echo "Summarize this" | python agent_copilot.py -a agents/assistant.md -m gpt-4o
"""

import argparse
import asyncio
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env files for Jira credentials, but do NOT let a pre-existing GITHUB_TOKEN
# interfere with the Copilot CLI's own OAuth credential store.
# The Copilot CLI only accepts OAuth tokens from gh/Copilot CLI app; a PAT with
# insufficient scopes causes "Authorization error, you may need to run /login".
_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / "jira-cli" / ".env")

# Remove GITHUB_TOKEN / GH_TOKEN so the Copilot CLI uses its keyring credentials.
for _env_key in ("GITHUB_TOKEN", "GH_TOKEN", "COPILOT_GITHUB_TOKEN"):
    os.environ.pop(_env_key, None)


MAX_TURNS_DEFAULT = 20
MAX_TURNS_LIMIT = 50
SUB_AGENT_MAX_TURNS = 10
MAX_RECURSION_DEPTH = 2


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass
class AgentConfig:
    """Immutable configuration for a single agent invocation."""
    system_prompt: str
    model: str
    streaming: bool
    max_turns: int
    depth: int = 0
    base_dir: Path = field(default_factory=lambda: _here)


@dataclass
class TurnState:
    """Mutable state collected during a single assistant turn."""
    content_parts: list[str] = field(default_factory=list)
    tool_called: bool = False
    done: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def content(self) -> str:
        return "".join(self.content_parts)


# ---------------------------------------------------------------------------
# WorkflowAnalyser — pure step/workflow detection logic (no I/O)
# ---------------------------------------------------------------------------

class WorkflowAnalyser:
    """Stateless helpers for step-aware continuation decisions."""

    _STEP_RE = re.compile(r"\bStep\s+(\d+)", re.IGNORECASE)
    _PENDING_STEPS_RE = re.compile(r"\bStep\s+[5-9]\b", re.IGNORECASE)
    _SIGNAL_RE = re.compile(
        r"\b(next[,\s]|please wait|i will now|i will next|let me now|"
        r"proceeding to|moving to step|continuing|i'll now|i'll next)\b",
        re.IGNORECASE,
    )
    _BASH_BLOCK_RE = re.compile(r"```(?:bash|sh)\b")

    @classmethod
    def last_completed_step(cls, messages: list[str]) -> int | None:
        highest = None
        for text in reversed(messages):
            for m in cls._STEP_RE.finditer(text):
                n = int(m.group(1))
                if highest is None or n > highest:
                    highest = n
        return highest

    @classmethod
    def is_mid_workflow(cls, content: str) -> bool:
        return bool(
            cls._BASH_BLOCK_RE.search(content)
            or cls._SIGNAL_RE.search(content)
            or cls._PENDING_STEPS_RE.search(content)
        )

    @classmethod
    def continuation_prompt(cls, assistant_messages: list[str]) -> str:
        last_step = cls.last_completed_step(assistant_messages)
        if last_step is not None:
            return (
                f"Step {last_step} was completed. "
                f"Continue with Step {last_step + 1} now, "
                "executing all required commands via bash_exec or invoke_agent."
            )
        return (
            "Please continue and complete the remaining steps, "
            "executing all required commands via bash_exec or invoke_agent."
        )


# ---------------------------------------------------------------------------
# BashTool — handles bash_exec tool invocations
# ---------------------------------------------------------------------------

class BashTool:
    """Executes shell commands on behalf of the LLM."""

    _MAX_COMMAND_LEN = 4096

    # Blocklist for unambiguously destructive / injection-vector patterns.
    # Defense-in-depth only — not a complete security boundary.
    _BLOCKLIST_RE = re.compile(
        r"rm\s+-[^\s]*r[^\s]*\s+/[^\s]*/|"          # rm -rf /<path> (recursive from root)
        r"rm\s+-[^\s]*r[^\s]*\s+~|"                  # rm -rf ~
        r"dd\s+.*of=/dev/[sh]d[a-z]|"                 # dd to raw disk device
        r">\s*/dev/[sh]d[a-z]|"                        # redirect to raw disk device
        r"mkfs\.[a-z]|"                                # reformat filesystem
        r":\s*\(\s*\)\s*\{.*\|.*:.*\}|"              # fork bomb :(){};
        r"curl[^|]*\|\s*(?:ba)?sh|"                   # curl | sh / curl | bash
        r"wget[^|]*\|\s*(?:ba)?sh",                    # wget | sh / wget | bash
        re.IGNORECASE | re.DOTALL,
    )

    SCHEMA = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            }
        },
        "required": ["command"],
    }
    DESCRIPTION = (
        "Execute a shell command and return its stdout/stderr. "
        "Use this to run the Jira CLI, read files, or perform any "
        "shell operation required by the workflow."
    )

    @staticmethod
    async def _terminate_process(proc: asyncio.subprocess.Process) -> None:
        if proc.returncode is None:
            proc.kill()
            try:
                await proc.communicate()
            except Exception:
                pass

    async def __call__(self, inv) -> object:
        from copilot.tools import ToolResult

        args = inv.arguments or {}
        command = args.get("command", "")
        if not command:
            return ToolResult(text_result_for_llm="[Error: no command provided]", result_type="failure")
        if "\x00" in command:
            return ToolResult(text_result_for_llm="[Error: command rejected — null bytes are not permitted]", result_type="failure")
        if len(command) > self._MAX_COMMAND_LEN:
            return ToolResult(text_result_for_llm=f"[Error: command exceeds {self._MAX_COMMAND_LEN}-character limit]", result_type="failure")
        if self._BLOCKLIST_RE.search(command):
            return ToolResult(text_result_for_llm="[Error: command rejected — matches destructive-pattern blocklist]", result_type="failure")
        print(f"\n\033[36m[Tool: bash_exec]\033[0m {command}", flush=True)
        try:
            proc = await asyncio.create_subprocess_exec(
                "/bin/sh", "-c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=120
                )
            except asyncio.TimeoutError:
                await self._terminate_process(proc)
                return ToolResult(
                    text_result_for_llm="[Error: command timed out after 120s]",
                    result_type="failure",
                )
            except (KeyboardInterrupt, asyncio.CancelledError):
                await self._terminate_process(proc)
                raise

            output = stdout_bytes.decode(errors="replace")
            if stderr_bytes:
                output += f"\n[stderr]: {stderr_bytes.decode(errors='replace')}"
            if proc.returncode != 0:
                output += f"\n[exit code: {proc.returncode}]"
            text = output.strip() or "(no output)"
            print(f"\033[33m[Result]\033[0m\n{text}\n", flush=True)
            return ToolResult(text_result_for_llm=text)
        except Exception as exc:
            return ToolResult(text_result_for_llm=f"[Error: {exc}]", result_type="failure")


# ---------------------------------------------------------------------------
# AgentRunner — owns one agentic loop
# ---------------------------------------------------------------------------

class AgentRunner:
    """
    Runs an agentic loop for a single AgentConfig.
    
    Creates its own CopilotClient + Session so sub-agents are fully isolated.
    """

    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._bash_tool = BashTool()
        self._finished: bool = False

    _INVOKE_AGENT_SCHEMA = {
        "type": "object",
        "properties": {
            "agent_file": {
                "type": "string",
                "description": (
                    "Relative path to the .md agent file defining the sub-agent's "
                    "system prompt (e.g. 'agents/jira-reader.md')."
                ),
            },
            "instruction": {
                "type": "string",
                "description": "The task to perform, passed as the user message to the sub-agent.",
            },
            "context": {
                "type": "string",
                "description": (
                    "Optional additional data (e.g. Jira CLI output, requirements text) "
                    "injected as a user message before the instruction."
                ),
            },
        },
        "required": ["agent_file", "instruction"],
    }

    _FINISH_SCHEMA = {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief summary of what was accomplished (shown to the user).",
            }
        },
        "required": [],
    }

    async def run(
        self,
        initial_prompt: str,
        extra_context: str = "",
        on_chunk: Callable[[str], None] | None = None,
        on_tool: Callable[[str], None] | None = None,
    ) -> str:
        from copilot import CopilotClient
        from copilot.session import PermissionHandler

        cfg = self._config
        max_text_only = 3 if cfg.depth > 0 else 5
        text_only_turns = 0
        turn = 0
        assistant_messages: list[str] = []
        last_content = ""

        first_prompt = f"{extra_context}\n\n{initial_prompt}" if extra_context else initial_prompt
        tools = self._build_tools()

        skills_dir = cfg.base_dir / "skills"
        skill_directories = [str(path) for path in skills_dir.glob("*/") if path.is_dir()]

        async with CopilotClient() as client:
            session = await client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                model=cfg.model,
                streaming=cfg.streaming,
                tools=tools,
                skill_directories=skill_directories,
                system_message={"mode": "replace", "content": cfg.system_prompt},
            )

            try:
                while turn < cfg.max_turns:
                    state = TurnState()
                    unsubscribe = session.on(self._make_event_handler(state, on_chunk=on_chunk, on_tool=on_tool))

                    try:
                        prompt = first_prompt if turn == 0 else WorkflowAnalyser.continuation_prompt(assistant_messages)
                        await session.send(prompt)
                        await state.done.wait()
                    finally:
                        unsubscribe()

                    if cfg.streaming and state.content and on_chunk is None:
                        print()

                    last_content = state.content
                    if state.content:
                        assistant_messages.append(state.content)

                    turn += 1

                    # finish tool signals explicit completion — stop before any other checks
                    if self._finished:
                        break

                    if state.tool_called:
                        text_only_turns = 0
                        continue

                    if WorkflowAnalyser.is_mid_workflow(state.content) and text_only_turns < max_text_only:
                        text_only_turns += 1
                        continue

                    break
            finally:
                await session.disconnect()

        if turn >= cfg.max_turns:
            print("[Warning: reached maximum tool-call turns]", file=sys.stderr)

        return last_content

    def _make_event_handler(self, state: TurnState, on_chunk=None, on_tool=None):
        from copilot.generated.session_events import SessionEventType

        streaming = self._config.streaming

        def _handler(event):
            et = event.type
            if streaming and et == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                chunk = getattr(event.data, "delta_content", "") or ""
                if on_chunk is not None:
                    on_chunk(chunk)
                else:
                    print(chunk, end="", flush=True)
                state.content_parts.append(chunk)
            elif et == SessionEventType.ASSISTANT_MESSAGE:
                content = getattr(event.data, "content", "") or ""
                if not streaming:
                    if on_chunk is not None:
                        on_chunk(content)
                    else:
                        print(content)
                state.content_parts.append(content)
            elif et in (SessionEventType.TOOL_EXECUTION_START, SessionEventType.TOOL_EXECUTION_COMPLETE):
                state.tool_called = True
                if on_tool is not None and et == SessionEventType.TOOL_EXECUTION_START:
                    tool_name = getattr(event.data, "tool_name", "") or ""
                    on_tool(tool_name)
            elif et == SessionEventType.SESSION_IDLE:
                state.done.set()
            elif et == SessionEventType.SESSION_ERROR:
                print(
                    f"\n[Session error]: {getattr(event.data, 'message', str(event.data))}",
                    file=sys.stderr,
                )
                state.done.set()

        return _handler

    # Schemas for new tools
    _CREATE_GITHUB_ISSUE_SCHEMA = {
        "type": "object",
        "properties": {
            "owner": {"type": "string", "description": "GitHub owner (org or user)."},
            "repo": {"type": "string", "description": "GitHub repository name."},
            "title": {"type": "string", "description": "Issue title."},
            "prompt": {"type": "string", "description": "Description / body for the issue."},
            "agent": {"type": "string", "description": "Optional agent id to assign (e.g. 'ba', 'qa')."},
            "skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of skill ids to attach.",
            },
        },
        "required": ["owner", "repo", "title", "prompt"],
    }

    _READ_CONFLUENCE_SCHEMA = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full Confluence page URL."},
        },
        "required": ["url"],
    }

    def _build_tools(self) -> list:
        from copilot.tools import Tool

        return [
            Tool(
                name="bash_exec",
                description=BashTool.DESCRIPTION,
                parameters=BashTool.SCHEMA,
                handler=self._bash_tool,
                skip_permission=True,
            ),
            Tool(
                name="invoke_agent",
                description=(
                    "Delegate a sub-task to a specialised sub-agent defined by an agent file. "
                    "Runs the sub-agent in isolation with its own conversation history and turn budget. "
                    "Returns the sub-agent's final text output as a string. "
                    "Use this instead of reading agent files inline or switching persona."
                ),
                parameters=self._INVOKE_AGENT_SCHEMA,
                handler=self._handle_invoke_agent,
                skip_permission=True,
            ),
            Tool(
                name="create_github_issue",
                description=(
                    "Create a GitHub issue in the specified repository and optionally assign it to a "
                    "specialised Copilot agent. Returns the URL of the created issue."
                ),
                parameters=self._CREATE_GITHUB_ISSUE_SCHEMA,
                handler=self._handle_create_github_issue,
                skip_permission=True,
            ),
            Tool(
                name="read_confluence",
                description=(
                    "Fetch the Markdown-rendered content of a Confluence page by its URL. "
                    "Requires the atlassian-bridge service to be running on :8002."
                ),
                parameters=self._READ_CONFLUENCE_SCHEMA,
                handler=self._handle_read_confluence,
                skip_permission=True,
            ),
            Tool(
                name="finish",
                description=(
                    "Signal that the workflow is fully complete. "
                    "Call this as the LAST action once all steps are done and all outputs have been delivered. "
                    "Do NOT call finish mid-workflow or before all required steps are complete."
                ),
                parameters=self._FINISH_SCHEMA,
                handler=self._handle_finish,
                skip_permission=True,
            ),
        ]

    async def _handle_create_github_issue(self, inv) -> object:
        import httpx
        from copilot.tools import ToolResult

        args = inv.arguments or {}
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        title = args.get("title", "")
        prompt = args.get("prompt", "")
        agent = args.get("agent")
        skills = args.get("skills") or []

        if not (owner and repo and title and prompt):
            return ToolResult(
                text_result_for_llm="[Error: create_github_issue requires owner, repo, title, prompt]",
                result_type="failure",
            )

        # Call our own api_server endpoint, which wraps the GitHub REST API and
        # handles Copilot cloud-agent assignment + GH_TOKEN management server-side.
        api_base = os.getenv("AGENT_API_URL", "http://localhost:8000")
        payload: dict = {
            "owner": owner,
            "repo": repo,
            "title": title,
            "body": prompt,
            "assign_to_copilot": True,
        }
        if agent:
            payload["custom_agent"] = agent
        if skills:
            payload["skills"] = skills

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{api_base}/github/issues", json=payload)
                resp.raise_for_status()
                data = resp.json()
            assigned = "assigned to Copilot" if data.get("copilot_assigned") else "Copilot assignment skipped"
            return ToolResult(
                text_result_for_llm=(
                    f"Created issue #{data['number']} ({assigned}): {data['html_url']}"
                )
            )
        except httpx.HTTPStatusError as exc:
            return ToolResult(
                text_result_for_llm=f"[Error creating issue: HTTP {exc.response.status_code} — {exc.response.text}]",
                result_type="failure",
            )
        except Exception as exc:
            return ToolResult(
                text_result_for_llm=f"[Error creating issue: {exc}]",
                result_type="failure",
            )

    async def _handle_read_confluence(self, inv) -> object:
        import httpx
        from copilot.tools import ToolResult

        args = inv.arguments or {}
        url = args.get("url", "")
        if not url:
            return ToolResult(
                text_result_for_llm="[Error: read_confluence requires 'url']",
                result_type="failure",
            )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                _bridge = os.getenv("ATLASSIAN_BRIDGE_URL", "http://localhost:8002")
                resp = await client.post(
                    f"{_bridge}/confluence/fetch",
                    json={"url": url},
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("body_markdown") or data.get("content") or str(data)
                title = data.get("title", "")
                return ToolResult(
                    text_result_for_llm=f"# {title}\n\n{content}" if title else content,
                )
        except httpx.HTTPStatusError as exc:
            return ToolResult(
                text_result_for_llm=f"[Error fetching Confluence page: HTTP {exc.response.status_code} — {exc.response.text}]",
                result_type="failure",
            )
        except Exception as exc:
            return ToolResult(
                text_result_for_llm=f"[Error fetching Confluence page: {exc}]",
                result_type="failure",
            )

    async def _handle_invoke_agent(self, inv) -> object:
        from copilot.tools import ToolResult

        cfg = self._config
        if cfg.depth >= MAX_RECURSION_DEPTH:
            return ToolResult(
                text_result_for_llm="[Error: max sub-agent recursion depth reached]",
                result_type="failure",
            )

        args = inv.arguments or {}
        agent_file = args.get("agent_file", "")
        instruction = args.get("instruction", "")
        context = args.get("context", "")

        if not agent_file:
            return ToolResult(
                text_result_for_llm="[Error: invoke_agent requires 'agent_file']",
                result_type="failure",
            )
        if not instruction:
            return ToolResult(
                text_result_for_llm="[Error: invoke_agent requires 'instruction']",
                result_type="failure",
            )

        agent_path = cfg.base_dir / agent_file
        sub_prompt = CLI.load_agent_file(str(agent_path))
        print(f"\n\033[35m[Sub-agent: {agent_file}]\033[0m depth={cfg.depth + 1}", flush=True)

        sub_config = AgentConfig(
            system_prompt=sub_prompt,
            model=cfg.model,
            streaming=cfg.streaming,
            max_turns=SUB_AGENT_MAX_TURNS,
            depth=cfg.depth + 1,
            base_dir=cfg.base_dir,
        )
        result = await AgentRunner(sub_config).run(instruction, extra_context=context)
        print(f"\033[35m[Sub-agent: {agent_file} complete]\033[0m\n", flush=True)
        return ToolResult(text_result_for_llm=result or "(sub-agent returned no output)")

    async def _handle_finish(self, inv) -> object:
        from copilot.tools import ToolResult

        args = inv.arguments or {}
        summary = args.get("summary", "").strip()
        self._finished = True
        if summary:
            print(f"\n\033[32m[Agent finished]\033[0m {summary}", flush=True)
        else:
            print("\n\033[32m[Agent finished]\033[0m", flush=True)
        return ToolResult(text_result_for_llm="[Workflow complete. Session will now end.]")



# ---------------------------------------------------------------------------
# CLI — argument parsing and entry point
# ---------------------------------------------------------------------------

class CLI:
    """Parses CLI arguments, constructs AgentConfig, and dispatches to AgentRunner."""

    @staticmethod
    def load_agent_file(path: str) -> str:
        agent_path = Path(path)
        if not agent_path.exists():
            print(f"Error: Agent file '{path}' not found.", file=sys.stderr)
            sys.exit(1)
        return agent_path.read_text(encoding="utf-8").strip()

    @staticmethod
    def check_sdk() -> None:
        try:
            import copilot  # noqa: F401
        except ImportError:
            print(
                "Error: github-copilot-sdk is not installed.\n"
                "Run: pip install github-copilot-sdk\n"
                "Also ensure the GitHub Copilot CLI is installed and authenticated:\n"
                "  gh extension install github/gh-copilot && gh auth login",
                file=sys.stderr,
            )
            sys.exit(1)

    async def run_once(self, config: AgentConfig, instruction: str) -> None:
        try:
            await AgentRunner(config).run(instruction)
        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
            raise

    async def run_interactive(self, config: AgentConfig) -> None:
        print(f"Agent ready  |  model: {config.model}  |  sdk: github-copilot-sdk")
        print("Commands: 'exit'/'quit' — stop\n")

        while True:
            try:
                user_input = input("You: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
                print("Goodbye!")
                break

            print("Agent: ", end="", flush=True)
            try:
                await AgentRunner(config).run(user_input)
            except KeyboardInterrupt:
                print("\nInterrupted. Goodbye!", file=sys.stderr)
                break
            print()


    def main(self) -> None:
        parser = argparse.ArgumentParser(
            prog="agent-copilot",
            description="GitHub Copilot SDK CLI agent (github-copilot-sdk).",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Single-shot
  python agent_copilot.py -a agents/assistant.md -m gpt-4o -i "Explain recursion"

  # BA workflow with extended turn budget
  python agent_copilot.py -a agents/ba.agent.md -m gpt-4o -i "SCRUM-12" --max-turns 40

  # Pipe instruction from stdin
  echo "Review this code" | python agent_copilot.py -a agents/coder.md -m gpt-4o

  # Interactive multi-turn chat
  python agent_copilot.py -a agents/coder.md -m gpt-4o --interactive

  # Use a different model (any model available via Copilot CLI)
  python agent_copilot.py -a agents/assistant.md -m claude-sonnet-4-6 -i "Hello"

Prerequisites:
  pip install github-copilot-sdk
  gh extension install github/gh-copilot
  gh auth login
""",
        )

        parser.add_argument(
            "-a", "--agent-file",
            required=True,
            metavar="FILE",
            help="Path to the agent Markdown/text file containing the system prompt.",
        )
        parser.add_argument(
            "-m", "--model",
            default="gpt-4o",
            metavar="MODEL",
            help=(
                "Model name as available via the Copilot CLI "
                "(default: gpt-4o). Examples: claude-sonnet-4-6, gpt-4o."
            ),
        )
        parser.add_argument(
            "-i", "--instruction",
            metavar="TEXT",
            help="User instruction / prompt (single-shot mode). Reads from stdin if omitted and stdin is piped.",
        )
        parser.add_argument(
            "--interactive",
            action="store_true",
            help="Start an interactive multi-turn chat session.",
        )
        parser.add_argument(
            "--no-stream",
            action="store_true",
            help="Disable streaming; wait for the full response before printing.",
        )
        parser.add_argument(
            "--max-turns",
            type=int,
            default=MAX_TURNS_DEFAULT,
            metavar="N",
            help=(
                f"Maximum turns per run (default {MAX_TURNS_DEFAULT}, "
                f"max {MAX_TURNS_LIMIT}). "
                "Increase for complex multi-step workflows like the BA agent."
            ),
        )

        args = parser.parse_args()
        streaming = not args.no_stream
        max_turns = min(args.max_turns, MAX_TURNS_LIMIT)

        self.check_sdk()
        system_prompt = self.load_agent_file(args.agent_file)
        # Inject the real working directory so the LLM never guesses /workspace
        cwd = Path.cwd()
        system_prompt += (
            f"\n\n> **Runtime working directory (injected)**: "
            f"All `bash_exec` commands execute from `{cwd}`. "
            "Use paths relative to this directory. Do NOT use `cd /workspace` or any absolute prefix."
        )
        config = AgentConfig(
            system_prompt=system_prompt,
            model=args.model,
            streaming=streaming,
            max_turns=max_turns,
        )

        try:
            if args.interactive:
                asyncio.run(self.run_interactive(config))
            elif args.instruction:
                asyncio.run(self.run_once(config, args.instruction))
            elif not sys.stdin.isatty():
                instruction = sys.stdin.read().strip()
                if not instruction:
                    print("Error: Empty instruction from stdin.", file=sys.stderr)
                    sys.exit(1)
                asyncio.run(self.run_once(config, instruction))
            else:
                asyncio.run(self.run_interactive(config))
        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
            sys.exit(130)


def main() -> None:
    CLI().main()


if __name__ == "__main__":
    main()
