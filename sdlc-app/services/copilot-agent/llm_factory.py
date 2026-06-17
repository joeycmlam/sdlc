"""
LLM factory for LangGraph-based agent graphs.

Wraps the GitHub Models endpoint (OpenAI-compatible) via LangChain's ChatOpenAI
so that LangGraph graphs can call the same models as the existing agent.py.

Authentication: GITHUB_TOKEN env var (PAT with 'models:read' scope).
If GITHUB_TOKEN is not set, falls back to `gh auth token` CLI output.
"""

import os
import subprocess

from langchain_openai import ChatOpenAI

_GITHUB_MODELS_URL = "https://models.inference.ai.azure.com"


def _resolve_github_token() -> str:
    """Return a GitHub token for the GitHub Models endpoint.

    Priority:
      1. GITHUB_TOKEN env var (set by users in .env / Docker env)
      2. GH_TOKEN env var (GitHub CLI alias)
      3. `gh auth token` — reads the credential already stored by `gh auth login`
    """
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return result.stdout.strip()
    except Exception as exc:
        raise RuntimeError(
            "No GitHub token found. Set GITHUB_TOKEN in your environment "
            "or run `gh auth login`."
        ) from exc


def build_llm(model: str, **kwargs) -> ChatOpenAI:
    """Return a ChatOpenAI client pointed at the GitHub Models endpoint.

    Args:
        model: Model name as listed on github.com/marketplace/models
               (e.g. "gpt-4o", "claude-sonnet-4-5", "claude-sonnet-4-6").
        **kwargs: Additional ChatOpenAI constructor args (temperature, etc.).

    Usage::

        llm = build_llm("gpt-4o")
        response = llm.invoke([HumanMessage(content="Hello")])
    """
    return ChatOpenAI(
        model=model,
        base_url=os.getenv("COPILOT_BASE_URL", _GITHUB_MODELS_URL),
        api_key=_resolve_github_token(),
        **kwargs,
    )
