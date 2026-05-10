"""Confluence router — fetch pages, search, and list children.

All endpoints receive the full Confluence page URL in the POST body so URLs
never appear in server access logs (SSRF-guarded in client.py).

Confluence REST API v2 base: <instance>/wiki/api/v2/
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException

from .client import (
    _ATLASSIAN_URL,
    confluence_api,
    get_client,
    parse_confluence_page_id,
    validate_atlassian_url,
)
from .models import (
    ConfluenceChildrenRequest,
    ConfluenceChildrenResponse,
    ConfluenceFetchRequest,
    ConfluencePageResponse,
    ConfluencePageSummary,
    ConfluenceSearchRequest,
    ConfluenceSearchResponse,
)

router = APIRouter(prefix="/confluence", tags=["confluence"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STORAGE_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\n{3,}")


def _storage_to_markdown(storage_html: str) -> str:
    """Very lightweight Confluence storage-format → Markdown.

    This handles the most common cases. The storage format is XHTML; a full
    parser would be overkill given agents will re-interpret the content.
    """
    text = storage_html

    # Headings
    for level in range(6, 0, -1):
        text = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            lambda m, l=level: "#" * l + " " + m.group(1).strip(),
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # Bold / italic / code
    text = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<b[^>]*>(.*?)</b>", r"**\1**", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<em[^>]*>(.*?)</em>", r"*\1*", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<i[^>]*>(.*?)</i>", r"*\1*", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", text, flags=re.DOTALL | re.IGNORECASE)

    # Code blocks
    text = re.sub(
        r"<ac:structured-macro[^>]*ac:name=\"code\"[^>]*>.*?<ac:plain-text-body><!\[CDATA\[(.*?)\]\]></ac:plain-text-body>.*?</ac:structured-macro>",
        r"```\n\1\n```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Links
    text = re.sub(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", text, flags=re.DOTALL | re.IGNORECASE)

    # Lists
    text = re.sub(r"<li[^>]*>(.*?)</li>", lambda m: "- " + m.group(1).strip(), text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[ou]l[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</[ou]l>", "\n", text, flags=re.IGNORECASE)

    # Paragraphs → newlines
    text = re.sub(r"</p>|<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "", text, flags=re.IGNORECASE)

    # Strip remaining tags
    text = _STORAGE_TAG_RE.sub("", text)

    # Normalise whitespace
    text = _WHITESPACE_RE.sub("\n\n", text)
    return text.strip()


def _page_url(page_id: str, title: str, space_key: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-")
    return f"{_ATLASSIAN_URL}/wiki/spaces/{space_key}/pages/{page_id}/{slug}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/fetch", response_model=ConfluencePageResponse)
async def fetch_page(req: ConfluenceFetchRequest) -> ConfluencePageResponse:
    """Fetch a Confluence page by full URL and return converted Markdown."""
    page_id = parse_confluence_page_id(req.url)
    client = get_client()

    # Fetch page with body in storage format
    url = confluence_api(f"pages/{page_id}?body-format=storage")
    resp = await client.get(url)
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Confluence page {page_id} not found.")
    if not resp.is_success:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()
    title = data.get("title", "")
    space_key = data.get("spaceId", "")  # v2 uses spaceId; we resolve the key below

    # Resolve space key from spaceId
    if space_key:
        space_resp = await client.get(confluence_api(f"spaces/{space_key}"))
        if space_resp.is_success:
            space_key = space_resp.json().get("key", space_key)

    body_storage = data.get("body", {}).get("storage", {}).get("value", "")
    markdown = _storage_to_markdown(body_storage)

    # Version / author from version object
    version = data.get("version", {})
    last_modified = version.get("createdAt")
    author = version.get("authorId")
    if author:
        # Resolve display name
        user_resp = await client.get(f"{_ATLASSIAN_URL}/rest/api/3/user?accountId={author}")
        if user_resp.is_success:
            author = user_resp.json().get("displayName", author)

    return ConfluencePageResponse(
        id=page_id,
        title=title,
        space_key=space_key,
        url=req.url,
        content_markdown=markdown,
        last_modified=last_modified,
        author=author,
    )


@router.post("/search", response_model=ConfluenceSearchResponse)
async def search_pages(req: ConfluenceSearchRequest) -> ConfluenceSearchResponse:
    """Full-text search across Confluence pages."""
    client = get_client()

    params: dict[str, Any] = {
        "title": req.query,  # v2 search by title
        "limit": req.limit,
    }
    if req.space_key:
        params["space-key"] = req.space_key

    # Use CQL via v1 search for richer full-text support
    cql = f'text ~ "{req.query}" AND type = "page"'
    if req.space_key:
        cql += f' AND space = "{req.space_key}"'

    search_url = f"{_ATLASSIAN_URL}/wiki/rest/api/content/search?cql={cql}&limit={req.limit}&expand=space"
    resp = await client.get(search_url)
    if not resp.is_success:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    results = resp.json().get("results", [])
    summaries: list[ConfluencePageSummary] = []
    for r in results:
        r_id = str(r.get("id", ""))
        r_title = r.get("title", "")
        r_space = r.get("space", {}).get("key", "")
        summaries.append(
            ConfluencePageSummary(
                id=r_id,
                title=r_title,
                space_key=r_space,
                url=_page_url(r_id, r_title, r_space),
                excerpt=r.get("excerpt"),
            )
        )

    return ConfluenceSearchResponse(
        query=req.query,
        space_key=req.space_key,
        results=summaries,
    )


@router.post("/children", response_model=ConfluenceChildrenResponse)
async def list_children(req: ConfluenceChildrenRequest) -> ConfluenceChildrenResponse:
    """List direct child pages of a Confluence page."""
    page_id = parse_confluence_page_id(req.url)
    client = get_client()

    url = confluence_api(f"pages/{page_id}/children?limit=50")
    resp = await client.get(url)
    if not resp.is_success:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()
    children: list[ConfluencePageSummary] = []
    for child in data.get("results", []):
        c_id = str(child.get("id", ""))
        c_title = child.get("title", "")
        c_space = child.get("spaceId", "")
        children.append(
            ConfluencePageSummary(
                id=c_id,
                title=c_title,
                space_key=c_space,
                url=_page_url(c_id, c_title, c_space),
            )
        )

    return ConfluenceChildrenResponse(parent_id=page_id, children=children)
