"""
LLM factory for LangGraph-based agent graphs.

Wraps an OpenAI-compatible chat endpoint via LangChain's ChatOpenAI so that
LangGraph graphs can call models from multiple providers without caring which
one is in use.

Model strings carry an optional provider prefix:
  - "deepseek/deepseek-chat"  → DeepSeek (https://api.deepseek.com)
  - "github/gpt-5.2"          → GitHub Models (default)
  - "gpt-5.2"                 → GitHub Models (no prefix = default provider)

Add a new provider by appending an entry to ``PROVIDERS`` below.
"""

import os
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional

from langchain_openai import ChatOpenAI


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    # Resolver returns an API key string. Raise RuntimeError if no creds found.
    api_key: Callable[[], str]


def _resolve_github_token() -> str:
    """GITHUB_TOKEN / GH_TOKEN env, then `gh auth token`."""
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


def _require_env(var: str, provider: str) -> Callable[[], str]:
    def resolver() -> str:
        value = os.getenv(var)
        if not value:
            raise RuntimeError(
                f"{provider} provider requires {var} to be set in the environment."
            )
        return value
    return resolver


PROVIDERS: dict[str, Provider] = {
    "github": Provider(
        name="github",
        base_url=os.getenv("COPILOT_BASE_URL", "https://models.inference.ai.azure.com"),
        api_key=_resolve_github_token,
    ),
    "deepseek": Provider(
        name="deepseek",
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        api_key=_require_env("DEEPSEEK_API_KEY", "DeepSeek"),
    ),
}

DEFAULT_PROVIDER = os.getenv("LLM_DEFAULT_PROVIDER", "github")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_model(model: str) -> tuple[Provider, str]:
    """Split ``provider/model`` into (Provider, bare_model_id).

    No prefix → DEFAULT_PROVIDER. Unknown prefix raises ValueError.
    """
    if "/" in model:
        prefix, _, bare = model.partition("/")
        if prefix in PROVIDERS:
            return PROVIDERS[prefix], bare
    # No known prefix: treat the whole string as a default-provider model id.
    if DEFAULT_PROVIDER not in PROVIDERS:
        raise ValueError(
            f"LLM_DEFAULT_PROVIDER='{DEFAULT_PROVIDER}' is not a registered provider."
        )
    return PROVIDERS[DEFAULT_PROVIDER], model


def build_llm(model: str, **kwargs) -> ChatOpenAI:
    """Return a ChatOpenAI client routed to the right provider for ``model``.

    Examples::

        build_llm("gpt-4o")                     # GitHub Models (default)
        build_llm("github/gpt-5.2")             # GitHub Models, explicit
        build_llm("deepseek/deepseek-chat")     # DeepSeek
    """
    provider, bare_model = parse_model(model)
    return ChatOpenAI(
        model=bare_model,
        base_url=provider.base_url,
        api_key=provider.api_key(),
        **kwargs,
    )
