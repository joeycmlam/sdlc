#!/usr/bin/env python3
"""
CLI Agent — GitHub Models (azure-ai-inference) edition.

Uses the GitHub Models endpoint with a GitHub personal access token
(GITHUB_TOKEN) so you can run any model available on github.com/marketplace/models.

Usage:
  python agent.py -a agents/assistant.md -m gpt-4o -i "Explain recursion"
  python agent.py -a agents/coder.md -m gpt-4o --interactive
  echo "Summarize this" | python agent.py -a agents/assistant.md -m gpt-4o
  python agent.py -a agents/ba.agent.md -m gpt-4o -i "please provide the analysis of jira - SCRUM-12"

Required environment variable:
  GITHUB_TOKEN  — a GitHub personal access token with 'models:read' scope.
                  Create one at https://github.com/settings/tokens
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the script's own directory, then from jira-cli/ sibling dir
_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / "jira-cli" / ".env")


GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"

# Tool definitions exposed to the model
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash_exec",
            "description": (
                "Execute a shell command and return its stdout/stderr. "
                "Use this to run the Jira CLI, read files, or perform any "
                "shell operation required by the workflow."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    }
                },
                "required": ["command"],
            },
        },
    }
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_agent_file(path: str) -> str:
    agent_path = Path(path)
    if not agent_path.exists():
        print(f"Error: Agent file '{path}' not found.", file=sys.stderr)
        sys.exit(1)
    return agent_path.read_text(encoding="utf-8").strip()


def get_github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print(
            "Error: GITHUB_TOKEN environment variable is not set.\n"
            "Create a token at https://github.com/settings/tokens (needs 'models:read' scope).",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def build_client(token: str):
    """Return a ChatCompletionsClient pointed at the GitHub Models endpoint."""
    try:
        from azure.ai.inference import ChatCompletionsClient
        from azure.core.credentials import AzureKeyCredential
    except ImportError:
        print(
            "Error: azure-ai-inference is not installed.\n"
            "Run: pip install azure-ai-inference",
            file=sys.stderr,
        )
        sys.exit(1)

    return ChatCompletionsClient(
        endpoint=GITHUB_MODELS_ENDPOINT,
        credential=AzureKeyCredential(token),
    )


def execute_tool(name: str, args: dict) -> str:
    """Execute a tool call and return the result as a string."""
    if name == "bash_exec":
        command = args.get("command", "")
        if not command:
            return "[Error: no command provided]"
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return output.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return "[Error: command timed out after 120s]"
        except Exception as exc:
            return f"[Error: {exc}]"
    return f"[Error: unknown tool '{name}']"


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------

def _accumulate_stream(response) -> tuple:
    """
    Consume a streaming response.
    Returns (content: str, tool_calls: list[dict], finish_reason: str | None).
    Each tool_call dict has keys: id, name, args (str).
    Also prints reasoning_content (thinking tokens) if present.
    """
    content = ""
    tool_call_chunks: dict = {}  # id -> {id, name, args}
    _last_tc_id = ""
    finish_reason = None

    for update in response:
        if not update.choices:
            continue
        choice = update.choices[0]
        delta = choice.delta

        # Visible text
        if delta.content:
            print(delta.content, end="", flush=True)
            content += delta.content

        # Reasoning / thinking tokens (o1, o3, deepseek-r1, …)
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            print(f"\033[2m{reasoning}\033[0m", end="", flush=True)

        # Tool-call deltas (arguments stream in chunks).
        # Group by id: a non-empty id signals a new tool call; subsequent
        # chunks for the same call arrive with an empty id.
        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                tc_id = tc_delta.id or ""
                if tc_id:
                    # New tool call starts
                    tool_call_chunks[tc_id] = {"id": tc_id, "name": "", "args": ""}
                    _last_tc_id = tc_id
                else:
                    # Continuation chunk — attach to the most recent tool call
                    tc_id = _last_tc_id
                if tc_delta.function and tc_delta.function.name:
                    tool_call_chunks[tc_id]["name"] += tc_delta.function.name
                if tc_delta.function and tc_delta.function.arguments:
                    tool_call_chunks[tc_id]["args"] += tc_delta.function.arguments

        if choice.finish_reason is not None:
            finish_reason = str(choice.finish_reason)

    if content:
        print()  # final newline after streamed text

    tool_calls = list(tool_call_chunks.values())
    return content, tool_calls, finish_reason


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

def run_agentic_loop(
    client, system_prompt: str, model: str, initial_messages: list, stream: bool
) -> str:
    """
    Run an agentic tool-calling loop until the model produces a final answer
    or the maximum number of turns is reached.

    Prints each tool call and its result so the user can follow the full
    reasoning / execution process.
    """
    from azure.ai.inference.models import (
        AssistantMessage,
        ChatCompletionsToolCall,
        FunctionCall,
        SystemMessage,
        ToolMessage,
        UserMessage,
    )
    from azure.core.exceptions import HttpResponseError

    history = [SystemMessage(system_prompt), *initial_messages]
    max_turns = 20
    last_content = ""
    # Track consecutive text-only turns to prevent infinite continuation loops
    _text_only_turns = 0
    _MAX_TEXT_ONLY = 3

    for _turn in range(max_turns):
        try:
            if stream:
                response = client.complete(
                    model=model, messages=history, stream=True, tools=TOOLS
                )
                content, tool_calls_raw, _ = _accumulate_stream(response)
            else:
                response = client.complete(model=model, messages=history, tools=TOOLS)
                choice = response.choices[0]
                content = choice.message.content or ""

                # Reasoning tokens (non-streaming)
                reasoning = getattr(choice.message, "reasoning_content", None)
                if reasoning:
                    print(f"\033[2m[Thinking]\n{reasoning}\n\033[0m")

                tool_calls_raw = []
                if choice.message.tool_calls:
                    for tc in choice.message.tool_calls:
                        tool_calls_raw.append(
                            {
                                "id": tc.id,
                                "name": tc.function.name,
                                "args": tc.function.arguments or "",
                            }
                        )
                if content and not stream:
                    print(content)

        except HttpResponseError as exc:
            print(
                f"\nAPI error {exc.status_code} ({exc.reason}): {exc.message}",
                file=sys.stderr,
            )
            sys.exit(1)

        last_content = content

        # No tool calls — check whether the model paused mid-workflow or is truly done.
        if not tool_calls_raw:
            has_bash_blocks = bool(re.search(r"```(?:bash|sh)\b", content))
            is_mid_workflow = bool(re.search(
                r"\b(next[,\s]|please wait|i will now|i will next|let me now|"
                r"proceeding to|moving to step|continuing|i'll now|i'll next)\b",
                content,
                re.IGNORECASE,
            ))
            if (has_bash_blocks or is_mid_workflow) and _text_only_turns < _MAX_TEXT_ONLY:
                _text_only_turns += 1
                history.append(AssistantMessage(content=content or None))
                history.append(UserMessage(
                    "Please continue and complete the remaining steps, "
                    "executing all required commands via the bash_exec tool."
                ))
                continue
            return last_content

        _text_only_turns = 0  # reset counter once tool calls resume

        # Append assistant message (with tool calls) to history
        sdk_tool_calls = [
            ChatCompletionsToolCall(
                id=tc["id"],
                function=FunctionCall(name=tc["name"], arguments=tc["args"]),
            )
            for tc in tool_calls_raw
        ]
        history.append(
            AssistantMessage(content=content or None, tool_calls=sdk_tool_calls)
        )

        # Execute each tool, show the call + result, then add to history
        for tc in tool_calls_raw:
            try:
                args = json.loads(tc["args"]) if tc["args"] else {}
            except json.JSONDecodeError:
                args = {}

            cmd_display = args.get("command", tc["args"])
            print(f"\n\033[36m[Tool: {tc['name']}]\033[0m {cmd_display}", flush=True)
            result = execute_tool(tc["name"], args)
            print(f"\033[33m[Result]\033[0m\n{result}\n", flush=True)

            history.append(ToolMessage(tool_call_id=tc["id"], content=result))

    print("[Warning: reached maximum tool-call turns]", file=sys.stderr)
    return last_content


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------

def run_once(client, system_prompt: str, model: str, instruction: str, stream: bool) -> None:
    """Single-turn (with tool-call loop): send one message and print the reply."""
    from azure.ai.inference.models import UserMessage

    run_agentic_loop(client, system_prompt, model, [UserMessage(instruction)], stream)


def run_interactive(client, system_prompt: str, model: str, stream: bool) -> None:
    """Multi-turn interactive chat session (each turn may use tools internally)."""
    from azure.ai.inference.models import AssistantMessage, UserMessage

    history: list = []
    print(f"Agent ready  |  model: {model}  |  endpoint: {GITHUB_MODELS_ENDPOINT}")
    print("Commands: 'exit'/'quit' — stop  |  'reset' — clear history\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        if user_input.lower() == "reset":
            history.clear()
            print("[History cleared]\n")
            continue

        print("Agent: ", end="", flush=True)
        reply = run_agentic_loop(
            client, system_prompt, model, [*history, UserMessage(user_input)], stream
        )

        # Keep conversation history (tool calls are internal to each turn)
        history.append(UserMessage(user_input))
        history.append(AssistantMessage(reply))
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent",
        description="GitHub Models CLI agent (azure-ai-inference).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single-shot
  python agent.py -a agents/assistant.md -m gpt-4o -i "Explain recursion"

  # Pipe instruction from stdin
  echo "Review this code" | python agent.py -a agents/coder.md -m gpt-4o

  # Interactive multi-turn chat
  python agent.py -a agents/coder.md -m gpt-4o --interactive

  # Use a different model (any name from github.com/marketplace/models)
  python agent.py -a agents/assistant.md -m meta-llama-3.1-70b-instruct -i "Hello"
  python agent.py -a agents/assistant.md -m mistral-large -i "Hello"

Environment:
  GITHUB_TOKEN  GitHub personal access token (models:read scope required).
                Create at https://github.com/settings/tokens
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
            "Model name as listed on github.com/marketplace/models "
            "(default: gpt-4o)."
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

    args = parser.parse_args()
    stream = not args.no_stream

    system_prompt = load_agent_file(args.agent_file)
    token = get_github_token()
    client = build_client(token)

    if args.interactive:
        run_interactive(client, system_prompt, args.model, stream)
    elif args.instruction:
        run_once(client, system_prompt, args.model, args.instruction, stream)
    elif not sys.stdin.isatty():
        instruction = sys.stdin.read().strip()
        if not instruction:
            print("Error: Empty instruction from stdin.", file=sys.stderr)
            sys.exit(1)
        run_once(client, system_prompt, args.model, instruction, stream)
    else:
        # No instruction and no pipe — default to interactive
        run_interactive(client, system_prompt, args.model, stream)

    client.close()


if __name__ == "__main__":
    main()