"""Shared httpx client with Atlassian Basic auth.

Credentials are loaded once from environment variables at import time.
The client is lifecycle-managed via FastAPI's lifespan context so a single
connection pool is reused for the lifetime of the process.

SSRF protection: every outbound call validates that the target hostname
matches the configured ATLASSIAN_URL before making the request. Any URL
from a different host is rejected with 403.
"""

from __future__ import annotations

import base64
import os
import re
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status

# ---------------------------------------------------------------------------
# Configuration — read once at startup
# ---------------------------------------------------------------------------

_ATLASSIAN_URL = os.environ.get("ATLASSIAN_URL", "").rstrip("/")
_ATLASSIAN_USER = os.environ.get("ATLASSIAN_USER", "")
_ATLASSIAN_API_TOKEN = os.environ.get("ATLASSIAN_API_TOKEN", "")

# Derived: accepted hostname for SSRF guard
_ALLOWED_HOST: str = urlparse(_ATLASSIAN_URL).hostname or ""


def _basic_token() -> str:
    raw = f"{_ATLASSIAN_USER}:{_ATLASSIAN_API_TOKEN}"
    return base64.b64encode(raw.encode()).decode()


_HEADERS: dict[str, str] = {
    "Authorization": f"Basic {_basic_token()}",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-Atlassian-Token": "no-check",
}

# ---------------------------------------------------------------------------
# SSRF guard
# ---------------------------------------------------------------------------


def validate_atlassian_url(url: str) -> None:
    """Raise 403 if *url* does not belong to the configured Atlassian instance.

    This prevents SSRF: a caller cannot supply an arbitrary URL and have the
    bridge make authenticated requests to a third-party host.
    """
    if not _ALLOWED_HOST:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ATLASSIAN_URL is not configured.",
        )
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="URL must use https://.")
    if (parsed.hostname or "").lower() != _ALLOWED_HOST.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"URL host '{parsed.hostname}' is not the configured Atlassian instance.",
        )


# ---------------------------------------------------------------------------
# Lifecycle-managed client
# ---------------------------------------------------------------------------

_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan_client():
    """Manage a single shared httpx.AsyncClient over the app's lifespan."""
    global _client
    _client = httpx.AsyncClient(
        headers=_HEADERS,
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
    )
    try:
        yield _client
    finally:
        await _client.aclose()
        _client = None


def get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("httpx client not initialised — check lifespan setup.")
    return _client


# ---------------------------------------------------------------------------
# Base URL helpers
# ---------------------------------------------------------------------------


def jira_api(path: str) -> str:
    return f"{_ATLASSIAN_URL}/rest/api/3/{path.lstrip('/')}"


def confluence_api(path: str) -> str:
    return f"{_ATLASSIAN_URL}/wiki/api/v2/{path.lstrip('/')}"


# ---------------------------------------------------------------------------
# Jira URL parsing
# ---------------------------------------------------------------------------

_JIRA_KEY_RE = re.compile(r"/browse/([A-Z][A-Z0-9_]+-\d+)", re.IGNORECASE)


def parse_jira_key(url: str) -> str:
    """Extract the Jira issue key from a full browse URL."""
    validate_atlassian_url(url)
    m = _JIRA_KEY_RE.search(url)
    if not m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot extract Jira issue key from URL: {url}",
        )
    return m.group(1).upper()


# ---------------------------------------------------------------------------
# Confluence URL parsing
# ---------------------------------------------------------------------------

_CONFLUENCE_PAGE_ID_RE = re.compile(r"/pages/(\d+)", re.IGNORECASE)


def parse_confluence_page_id(url: str) -> str:
    """Extract a numeric page ID from a Confluence page URL."""
    validate_atlassian_url(url)
    m = _CONFLUENCE_PAGE_ID_RE.search(url)
    if not m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot extract Confluence page ID from URL: {url}",
        )
    return m.group(1)
