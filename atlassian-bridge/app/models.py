"""Pydantic request/response models for atlassian-bridge."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ---------------------------------------------------------------------------
# Shared request base — callers pass full Atlassian URLs, never credentials
# ---------------------------------------------------------------------------


class AtlassianUrlRequest(BaseModel):
    """Base for any request that takes a full Atlassian URL."""

    url: str = Field(
        ...,
        description="Full Atlassian URL (https://<instance>/browse/<KEY> or wiki/…).",
        examples=["https://myorg.atlassian.net/browse/SCRUM-1"],
    )

    @field_validator("url")
    @classmethod
    def _must_be_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("url must use https://")
        return v


# ---------------------------------------------------------------------------
# Jira
# ---------------------------------------------------------------------------


class JiraFetchRequest(AtlassianUrlRequest):
    """Body for POST /jira/fetch."""


class JiraUpdateRequest(AtlassianUrlRequest):
    """Body for POST /jira/update."""

    comment: str | None = Field(default=None, description="Text to add as a comment.")
    description: str | None = Field(default=None, description="New issue description (ADF or plain text).")
    transition: str | None = Field(default=None, description="Transition name to move the issue to.")


class JiraTransitionsRequest(AtlassianUrlRequest):
    """Body for POST /jira/transitions."""


class JiraComment(BaseModel):
    author: str
    created: str
    body: str


class JiraIssueResponse(BaseModel):
    key: str
    summary: str
    status: str
    issue_type: str
    priority: str | None = None
    assignee: str | None = None
    reporter: str | None = None
    description: str
    acceptance_criteria: str | None = None
    labels: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    comments: list[JiraComment] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    url: str


class JiraTransition(BaseModel):
    id: str
    name: str
    to_status: str


class JiraTransitionsResponse(BaseModel):
    key: str
    transitions: list[JiraTransition]


class JiraUpdateResponse(BaseModel):
    key: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Confluence
# ---------------------------------------------------------------------------


class ConfluenceFetchRequest(AtlassianUrlRequest):
    """Body for POST /confluence/fetch."""


class ConfluenceSearchRequest(BaseModel):
    """Body for POST /confluence/search."""

    query: str = Field(..., min_length=1, description="Full-text search query.")
    space_key: str | None = Field(default=None, description="Restrict to a space (e.g. 'ENG').")
    limit: int = Field(default=10, ge=1, le=50)


class ConfluenceChildrenRequest(AtlassianUrlRequest):
    """Body for POST /confluence/children."""


class ConfluencePageResponse(BaseModel):
    id: str
    title: str
    space_key: str
    url: str
    content_markdown: str
    last_modified: str | None = None
    author: str | None = None


class ConfluencePageSummary(BaseModel):
    id: str
    title: str
    space_key: str
    url: str
    excerpt: str | None = None


class ConfluenceSearchResponse(BaseModel):
    query: str
    space_key: str | None
    results: list[ConfluencePageSummary]


class ConfluenceChildrenResponse(BaseModel):
    parent_id: str
    children: list[ConfluencePageSummary]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "atlassian-bridge"
