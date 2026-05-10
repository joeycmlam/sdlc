"""Jira router — fetch, update, and list transitions.

All endpoints receive the full Jira issue URL in the POST body so URLs
never appear in server access logs (SSRF-guarded in client.py).
"""

from __future__ import annotations

import html
import re
from typing import Any

from fastapi import APIRouter, HTTPException, status

from .client import get_client, jira_api, parse_jira_key
from .models import (
    JiraComment,
    JiraFetchRequest,
    JiraIssueResponse,
    JiraTransition,
    JiraTransitionsRequest,
    JiraTransitionsResponse,
    JiraUpdateRequest,
    JiraUpdateResponse,
)

router = APIRouter(prefix="/jira", tags=["jira"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _adf_to_markdown(node: Any) -> str:
    """Best-effort ADF (Atlassian Document Format) → Markdown conversion."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node

    node_type = node.get("type", "")
    content = node.get("content", [])
    text = node.get("text", "")
    marks = node.get("marks", [])

    # Apply marks (bold, italic, code, link)
    if text:
        for mark in marks:
            mt = mark.get("type", "")
            if mt == "strong":
                text = f"**{text}**"
            elif mt == "em":
                text = f"*{text}*"
            elif mt == "code":
                text = f"`{text}`"
            elif mt == "link":
                href = mark.get("attrs", {}).get("href", "")
                text = f"[{text}]({href})"
        return text

    parts = [_adf_to_markdown(c) for c in content]

    if node_type == "doc":
        return "\n\n".join(p for p in parts if p)
    elif node_type == "paragraph":
        return "".join(parts)
    elif node_type in ("heading",):
        level = node.get("attrs", {}).get("level", 1)
        return "#" * level + " " + "".join(parts)
    elif node_type == "bulletList":
        return "\n".join(f"- {p}" for p in parts if p)
    elif node_type == "orderedList":
        return "\n".join(f"{i + 1}. {p}" for i, p in enumerate(parts) if p)
    elif node_type == "listItem":
        return "".join(parts)
    elif node_type == "codeBlock":
        lang = node.get("attrs", {}).get("language", "")
        return f"```{lang}\n{''.join(parts)}\n```"
    elif node_type == "blockquote":
        return "\n".join(f"> {p}" for p in parts if p)
    elif node_type == "rule":
        return "---"
    elif node_type == "hardBreak":
        return "\n"
    elif node_type == "text":
        return text
    else:
        return "".join(parts)


def _extract_description(fields: dict) -> str:
    desc = fields.get("description")
    if not desc:
        return ""
    if isinstance(desc, dict):
        return _adf_to_markdown(desc).strip()
    return str(desc).strip()


def _extract_comment_body(comment_obj: dict) -> str:
    body = comment_obj.get("body")
    if not body:
        return ""
    if isinstance(body, dict):
        return _adf_to_markdown(body).strip()
    return str(body).strip()


def _extract_ac(description: str) -> str | None:
    """Pull out Acceptance Criteria section if present."""
    m = re.search(
        r"(?:acceptance criteria|ac|given[/\s]when[/\s]then)[:\s]*(.+?)(?=\n#{1,3}\s|\Z)",
        description,
        re.IGNORECASE | re.DOTALL,
    )
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/fetch", response_model=JiraIssueResponse)
async def fetch_issue(req: JiraFetchRequest) -> JiraIssueResponse:
    """Fetch a Jira issue by its full browse URL and return structured Markdown."""
    key = parse_jira_key(req.url)
    client = get_client()
    url = jira_api(f"issue/{key}?expand=renderedFields,names,changelog")

    resp = await client.get(url)
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Jira issue {key} not found.")
    if not resp.is_success:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()
    fields = data.get("fields", {})

    # Comments
    comment_data = fields.get("comment", {})
    raw_comments = comment_data.get("comments", []) if isinstance(comment_data, dict) else []
    comments = [
        JiraComment(
            author=c.get("author", {}).get("displayName", "unknown"),
            created=c.get("created", ""),
            body=_extract_comment_body(c),
        )
        for c in raw_comments
    ]

    # Attachments
    attachments = [
        a.get("filename", "")
        for a in fields.get("attachment", [])
        if a.get("filename")
    ]

    description = _extract_description(fields)

    return JiraIssueResponse(
        key=key,
        summary=fields.get("summary", ""),
        status=fields.get("status", {}).get("name", ""),
        issue_type=fields.get("issuetype", {}).get("name", ""),
        priority=(fields.get("priority") or {}).get("name"),
        assignee=(fields.get("assignee") or {}).get("displayName"),
        reporter=(fields.get("reporter") or {}).get("displayName"),
        description=description,
        acceptance_criteria=_extract_ac(description),
        labels=fields.get("labels", []),
        components=[c.get("name", "") for c in fields.get("components", [])],
        comments=comments,
        attachments=attachments,
        url=req.url,
    )


@router.post("/update", response_model=JiraUpdateResponse)
async def update_issue(req: JiraUpdateRequest) -> JiraUpdateResponse:
    """Add a comment or update a Jira issue's description and/or transition."""
    key = parse_jira_key(req.url)
    client = get_client()

    messages: list[str] = []

    # Add comment
    if req.comment:
        comment_url = jira_api(f"issue/{key}/comment")
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": req.comment}],
                    }
                ],
            }
        }
        resp = await client.post(comment_url, json=payload)
        if not resp.is_success:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        messages.append("comment added")

    # Update description
    if req.description is not None:
        edit_url = jira_api(f"issue/{key}")
        payload = {
            "fields": {
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": req.description}],
                        }
                    ],
                }
            }
        }
        resp = await client.put(edit_url, json=payload)
        if resp.status_code not in (200, 204):
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        messages.append("description updated")

    # Transition
    if req.transition:
        transitions_url = jira_api(f"issue/{key}/transitions")
        tresp = await client.get(transitions_url)
        if not tresp.is_success:
            raise HTTPException(status_code=tresp.status_code, detail=tresp.text)
        available = tresp.json().get("transitions", [])
        match = next(
            (t for t in available if t["name"].lower() == req.transition.lower()), None
        )
        if not match:
            names = [t["name"] for t in available]
            raise HTTPException(
                status_code=400,
                detail=f"Transition '{req.transition}' not found. Available: {names}",
            )
        do_url = jira_api(f"issue/{key}/transitions")
        resp = await client.post(do_url, json={"transition": {"id": match["id"]}})
        if resp.status_code not in (200, 204):
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        messages.append(f"transitioned to '{req.transition}'")

    if not messages:
        raise HTTPException(status_code=400, detail="No update operations specified.")

    return JiraUpdateResponse(
        key=key,
        status="updated",
        message="; ".join(messages),
    )


@router.post("/transitions", response_model=JiraTransitionsResponse)
async def list_transitions(req: JiraTransitionsRequest) -> JiraTransitionsResponse:
    """List available workflow transitions for a Jira issue."""
    key = parse_jira_key(req.url)
    client = get_client()
    url = jira_api(f"issue/{key}/transitions")

    resp = await client.get(url)
    if not resp.is_success:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    raw = resp.json().get("transitions", [])
    return JiraTransitionsResponse(
        key=key,
        transitions=[
            JiraTransition(
                id=t["id"],
                name=t["name"],
                to_status=t.get("to", {}).get("name", ""),
            )
            for t in raw
        ],
    )
