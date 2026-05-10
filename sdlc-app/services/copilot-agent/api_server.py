#!/usr/bin/env python3
"""
FastAPI HTTP service wrapping AgentRunner from agent_copilot.py.

Backed by Redis for session state, Redis Streams for SSE event fan-out,
and Arq for the worker job queue. The /run and /stream endpoints remain
stateless and run the agent in-process.

Endpoints:
  GET  /health                    — liveness check (incl. Redis ping)
  GET  /agents                    — list registered agents + .md files
  GET  /agents/content            — agent file content (?file=<name>)
  GET  /skills                    — list registered skills
  POST /run                       — blocking run, returns {"content": "..."}
  POST /stream                    — SSE streaming run (in-process)

  POST   /sessions                — create a session (stateful)
  GET    /sessions/{id}           — get session state
  POST   /sessions/{id}/run       — enqueue session for the worker pool
  GET    /sessions/{id}/events    — SSE stream of session events (Redis Streams)
  POST   /sessions/{id}/approve   — approve or reject an awaiting_approval session
  GET    /sessions/{id}/result    — get final result
  DELETE /sessions/{id}           — delete session

Usage:
  python api_server.py [--host HOST] [--port PORT] [--reload]
  agent-api [--host HOST] [--port PORT] [--reload]

Required infra:
  - Redis at $REDIS_URL (default redis://localhost:6379/0)
  - At least one Arq worker: `arq worker.WorkerSettings` or `agent-worker`
"""

import argparse
import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Literal, Optional

from dotenv import load_dotenv

# Load .env from the directory containing this file so GITHUB_TOKEN / GH_TOKEN
# are available before any os.getenv() call below.
load_dotenv(Path(__file__).parent / ".env")

import frontmatter
import httpx
import uvicorn
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Snapshot GH_TOKEN BEFORE importing agent_copilot — that module wipes
# GITHUB_TOKEN/GH_TOKEN from os.environ at import time so the Copilot CLI
# uses its own OAuth keyring.  The /github/issues endpoint still needs a
# real GitHub PAT to call the REST API.
_GH_TOKEN: Optional[str] = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")

from agent_copilot import AgentConfig, AgentRunner, CLI  # noqa: F401, E402
from event_bus import EventBus
from registry import AgentRegistry, SkillRegistry
from session_store import RedisSessionStore, SessionState

_here = Path(__file__).parent
AGENTS_DIR = _here / "agents"
SKILLS_DIR = _here / "skills"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

agent_registry = AgentRegistry(AGENTS_DIR)
skill_registry = SkillRegistry(SKILLS_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.session_store = RedisSessionStore.from_url(REDIS_URL)
    app.state.event_bus = EventBus.from_url(REDIS_URL)
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    try:
        yield
    finally:
        await app.state.session_store.close()
        await app.state.event_bus.close()
        try:
            await app.state.arq_pool.aclose()
        except AttributeError:
            await app.state.arq_pool.close()


app = FastAPI(title="Copilot Agent API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    agent_file: str
    instruction: str
    model: str = "gpt-4o"
    max_turns: int = 20
    extra_context: Optional[str] = None


class CreateSessionRequest(BaseModel):
    agent_file: str
    instruction: str
    model: str = "gpt-4o"
    max_turns: int = 20
    extra_context: str = ""
    jira_url: Optional[str] = None
    confluence_pages: list[str] = []
    create_github_issue: bool = False
    github_owner: Optional[str] = None
    github_repo: Optional[str] = None
    custom_agent: Optional[str] = None


class ApproveRequest(BaseModel):
    action: Literal["approve", "reject"]
    comment: str = ""


class CreateGitHubIssueRequest(BaseModel):
    owner: str
    repo: str
    title: str
    body: str
    assign_to_copilot: bool = True
    additional_assignees: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    custom_agent: Optional[str] = None
    skills: list[str] = Field(default_factory=list)


class CreateGitHubIssueResponse(BaseModel):
    number: int
    html_url: str
    state: str
    assignees: list[str]
    title: str
    copilot_assigned: bool
    copilot_reason: str = Field(
        default="unknown",
        description=(
            "Why Copilot wasn't applied (when copilot_assigned=false). "
            "Values: 'not_requested', 'not_enabled', 'graphql_error', 'ok', 'unknown'."
        ),
    )
    copilot_message: Optional[str] = None
    actor_candidates: list[str] = Field(
        default_factory=list,
        description=(
            "When Copilot lookup ran, the logins of every actor GitHub returned via "
            "`suggestedActors`. Useful for diagnosing why Copilot wasn't found."
        ),
    )


class CopilotStatusResponse(BaseModel):
    owner: str
    repo: str
    copilot_available: bool
    copilot_actor_id: Optional[str] = None
    candidates: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class GitHubCustomAgent(BaseModel):
    """A custom .agent.md profile discovered in a GitHub repo or org."""
    id: str  # filename without extension
    name: str  # display name (frontmatter `name`, else id)
    scope: Literal["repo", "org"]
    source_repo: str  # "owner/repo" where the file lives
    path: str  # path within source_repo
    description: Optional[str] = None
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class GitHubAgentsResponse(BaseModel):
    owner: str
    repo: str
    agents: list[GitHubCustomAgent]


class GitHubAgentContentResponse(BaseModel):
    source_repo: str
    path: str
    content: str
    metadata: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_agent_path(agent_file: str) -> Path:
    """Resolve and validate agent_file, guarding against path traversal."""
    resolved = (_here / agent_file).resolve()
    if not resolved.is_relative_to(_here.resolve()):
        raise HTTPException(status_code=400, detail="Invalid agent_file path.")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"Agent file '{agent_file}' not found.")
    return resolved


def _build_runner(req: RunRequest) -> AgentRunner:
    agent_path = _resolve_agent_path(req.agent_file)
    system_prompt = agent_path.read_text(encoding="utf-8").strip()
    config = AgentConfig(
        system_prompt=system_prompt,
        model=req.model,
        streaming=True,
        max_turns=min(req.max_turns, 50),
        base_dir=_here,
    )
    return AgentRunner(config)


# ---------------------------------------------------------------------------
# Stateless endpoints (unchanged)
# ---------------------------------------------------------------------------

@app.get("/health")
async def health(request: Request):
    store: RedisSessionStore = request.app.state.session_store
    redis_ok = await store.ping()
    return {"status": "ok" if redis_ok else "degraded", "redis": redis_ok}


@app.get("/agents")
async def list_agents():
    registered = [
        {"id": a.id, "name": a.name, "description": a.description,
         "skills": a.skills, "tools": a.tools}
        for a in agent_registry.all().values()
    ]
    all_files = sorted(p.name for p in AGENTS_DIR.glob("*.md")) if AGENTS_DIR.exists() else []
    return {"agents": registered, "files": all_files}


@app.get("/agents/content")
async def agent_content(file: str = Query(..., description="Agent filename, e.g. ba.agent.md")):
    path = _resolve_agent_path(f"agents/{file}")
    try:
        post = frontmatter.load(str(path))
        return {"file": file, "content": post.content, "metadata": dict(post.metadata)}
    except Exception:
        raw = path.read_text(encoding="utf-8")
        return {"file": file, "content": raw, "metadata": {}}


@app.get("/skills")
async def list_skills():
    return {
        "skills": [
            {"id": s.id, "name": s.name, "description": s.description}
            for s in skill_registry.all().values()
        ]
    }


@app.post("/run")
async def run_agent(req: RunRequest):
    runner = _build_runner(req)
    result = await runner.run(req.instruction, extra_context=req.extra_context or "")
    return {"content": result}


@app.post("/stream")
async def stream_agent(req: RunRequest):
    runner = _build_runner(req)
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def on_chunk(chunk: str) -> None:
        if chunk:
            queue.put_nowait(json.dumps({"type": "chunk", "content": chunk}))

    def on_tool(name: str) -> None:
        if name:
            queue.put_nowait(json.dumps({"type": "tool", "name": name}))

    async def _run_and_signal() -> None:
        try:
            result = await runner.run(
                req.instruction,
                extra_context=req.extra_context or "",
                on_chunk=on_chunk,
                on_tool=on_tool,
            )
            queue.put_nowait(json.dumps({"type": "done", "content": result}))
        except Exception as exc:
            queue.put_nowait(json.dumps({"type": "error", "message": str(exc)}))
        finally:
            queue.put_nowait(None)

    async def _generate():
        task = asyncio.create_task(_run_and_signal())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {item}\n\n"
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(_generate(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Session endpoints (Redis-backed, worker-pool execution)
# ---------------------------------------------------------------------------


@app.get("/sessions")
async def list_sessions(request: Request, limit: int = Query(100, ge=1, le=500)) -> dict:
    """List sessions currently in Redis (newest first, capped at `limit`)."""
    store: RedisSessionStore = request.app.state.session_store
    sessions = await store.list(limit=limit)
    return {"sessions": [s.model_dump(mode="json") for s in sessions]}


@app.post("/sessions", status_code=201)
async def create_session(req: CreateSessionRequest, request: Request) -> dict:
    """Create a new session. Does not start execution — call /sessions/{id}/run."""
    _resolve_agent_path(req.agent_file)
    store: RedisSessionStore = request.app.state.session_store
    session = await store.create(
        agent_file=req.agent_file,
        instruction=req.instruction,
        model=req.model,
        max_turns=req.max_turns,
        extra_context=req.extra_context,
        jira_url=req.jira_url,
        confluence_pages=req.confluence_pages,
        create_github_issue=req.create_github_issue,
        github_owner=req.github_owner,
        github_repo=req.github_repo,
        custom_agent=req.custom_agent,
    )
    return session.model_dump(mode="json")


@app.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request) -> dict:
    store: RedisSessionStore = request.app.state.session_store
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return session.model_dump(mode="json")


@app.post("/sessions/{session_id}/run")
async def run_session(session_id: str, request: Request) -> dict:
    """Enqueue a pending session onto the Arq worker pool."""
    store: RedisSessionStore = request.app.state.session_store
    bus: EventBus = request.app.state.event_bus
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    if session.state not in ("pending", "approved"):
        raise HTTPException(
            status_code=409,
            detail=f"Session is in state '{session.state}'; only 'pending' or 'approved' can be run.",
        )

    await store.transition(session_id, "running")
    await bus.publish(session_id, {"type": "state", "session_id": session_id, "state": "running"})

    pool = request.app.state.arq_pool
    await pool.enqueue_job("run_session_job", session_id)
    return {"session_id": session_id, "state": "running"}


@app.get("/sessions/{session_id}/events")
async def session_events(session_id: str, request: Request):
    """SSE stream of events for a session, replayed from the start."""
    store: RedisSessionStore = request.app.state.session_store
    bus: EventBus = request.app.state.event_bus
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    async def _generate():
        async for event in bus.subscribe(session_id, from_start=True):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")


@app.post("/sessions/{session_id}/approve")
async def approve_session(session_id: str, req: ApproveRequest, request: Request) -> dict:
    """Approve or reject a session that is awaiting_approval."""
    store: RedisSessionStore = request.app.state.session_store
    bus: EventBus = request.app.state.event_bus
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    if session.state != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Session is in state '{session.state}'; only 'awaiting_approval' can be approved/rejected.",
        )

    new_state: SessionState = "approved" if req.action == "approve" else "rejected"
    await store.transition(session_id, new_state)
    await bus.publish(session_id, {"type": "state", "session_id": session_id, "state": new_state})

    if new_state == "rejected":
        await store.transition(session_id, "completed")
        await bus.publish(
            session_id,
            {"type": "done", "content": req.comment or "Session rejected.", "session_id": session_id},
        )
        await bus.end(session_id)

    refreshed = await store.get(session_id)
    return refreshed.model_dump(mode="json") if refreshed else {"session_id": session_id, "state": new_state}


@app.get("/sessions/{session_id}/result")
async def get_result(session_id: str, request: Request) -> dict:
    store: RedisSessionStore = request.app.state.session_store
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {
        "session_id": session_id,
        "state": session.state,
        "result": session.result,
        "github_issue_url": session.github_issue_url,
        "error": session.error,
    }


# ---------------------------------------------------------------------------
# GitHub issue creation + Copilot cloud-agent assignment
# ---------------------------------------------------------------------------

# Copilot coding agent assignment is done via the GraphQL
# `replaceActorsForAssignable` mutation (REST silently drops bot logins
# from the `assignees` array). The bot's actual login is "copilot-swe-agent"
# even though the GitHub UI displays it as "Copilot".
_COPILOT_BOT_LOGIN = "copilot-swe-agent"
_GITHUB_API = "https://api.github.com"
_GITHUB_GRAPHQL = "https://api.github.com/graphql"

# Where custom .agent.md files live, by GitHub-native convention.
_REPO_AGENTS_DIR = ".github/agents"
_ORG_REPO = ".github-private"
_ORG_AGENTS_DIR = "agents"


def _github_headers() -> dict[str, str]:
    if not _GH_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="GH_TOKEN (or GITHUB_TOKEN) not configured on the server.",
        )
    return {
        "Authorization": f"Bearer {_GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "copilot-agent-api",
    }


def _augment_body(body: str, custom_agent: Optional[str], skills: list[str]) -> str:
    extras: list[str] = []
    if custom_agent:
        extras.append(f"**Suggested agent:** `{custom_agent}`")
    if skills:
        extras.append("**Skills:** " + ", ".join(f"`{s}`" for s in skills))
    if not extras:
        return body
    return body.rstrip() + "\n\n---\n" + "\n".join(extras) + "\n"


_SUGGESTED_ACTORS_QUERY = """
query CopilotActor($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    suggestedActors(capabilities: [CAN_BE_ASSIGNED], first: 100) {
      nodes {
        ... on Bot { id login }
        ... on User { id login }
      }
    }
  }
}
"""

_REPLACE_ACTORS_MUTATION = """
mutation Assign($input: ReplaceActorsForAssignableInput!) {
  replaceActorsForAssignable(input: $input) {
    assignable {
      ... on Issue {
        assignees(first: 20) { nodes { login } }
      }
    }
  }
}
"""


async def _gh_graphql(
    client: httpx.AsyncClient, query: str, variables: dict
) -> dict:
    resp = await client.post(
        _GITHUB_GRAPHQL,
        headers=_github_headers(),
        json={"query": query, "variables": variables},
    )
    if not resp.is_success:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"GitHub GraphQL error: {resp.text}",
        )
    return resp.json()


async def _resolve_copilot_actor_id(
    client: httpx.AsyncClient, owner: str, repo: str
) -> tuple[Optional[str], list[str], Optional[str]]:
    """Look up the Copilot coding-agent bot for a repository.

    Returns (actor_id, all_candidate_logins, error_message).
    - actor_id is None when Copilot isn't a suggested assignee here.
    - all_candidate_logins is every actor returned by `suggestedActors`,
      shown to the user when Copilot can't be found so they can see what
      GitHub is offering.
    - error_message is set when GraphQL itself returned errors.
    """
    payload = await _gh_graphql(
        client, _SUGGESTED_ACTORS_QUERY, {"owner": owner, "name": repo}
    )
    if payload.get("errors"):
        msg = "; ".join(e.get("message", "") for e in payload["errors"])
        return None, [], msg
    nodes = (
        ((payload.get("data") or {}).get("repository") or {})
        .get("suggestedActors", {})
        .get("nodes", [])
        or []
    )
    candidates: list[str] = []
    actor_id: Optional[str] = None
    for node in nodes:
        if not node:
            continue
        login = node.get("login") or ""
        candidates.append(login)
        low = login.lower()
        if actor_id is None and (low == _COPILOT_BOT_LOGIN.lower() or low.startswith("copilot")):
            actor_id = node.get("id")
    return actor_id, candidates, None


@app.post("/github/issues", response_model=CreateGitHubIssueResponse, status_code=201)
async def create_github_issue(req: CreateGitHubIssueRequest) -> CreateGitHubIssueResponse:
    """Create a GitHub issue and optionally assign it to the Copilot cloud agent.

    Requires `GH_TOKEN` (or `GITHUB_TOKEN`) on the server. Token needs:
      - REST: `Issues: write`
      - GraphQL (for Copilot assignment): the same token is used; no extra scope.

    Copilot assignment is performed via the GraphQL `replaceActorsForAssignable`
    mutation. If the Copilot coding agent isn't enabled on the target repo
    (i.e. the bot is not in `suggestedActors`), the issue is still created and
    the response carries `copilot_assigned: false` with a precise reason.
    """
    if not (req.owner and req.repo and req.title and req.body):
        raise HTTPException(status_code=400, detail="owner, repo, title, body are required.")

    headers = _github_headers()
    augmented_body = _augment_body(req.body, req.custom_agent, req.skills)

    # Step 1: REST POST creates the issue with humans as assignees.
    # We never put "Copilot" here — REST drops bot logins silently.
    rest_payload: dict = {
        "title": req.title,
        "body": augmented_body,
    }
    humans = list(dict.fromkeys(a for a in req.additional_assignees if a))
    if humans:
        rest_payload["assignees"] = humans
    if req.labels:
        rest_payload["labels"] = req.labels

    create_url = f"{_GITHUB_API}/repos/{req.owner}/{req.repo}/issues"
    async with httpx.AsyncClient(timeout=30) as client:
        create_resp = await client.post(create_url, headers=headers, json=rest_payload)
        if not create_resp.is_success:
            raise HTTPException(
                status_code=create_resp.status_code,
                detail=f"GitHub API error: {create_resp.text}",
            )
        data = create_resp.json()
        issue_node_id: str = data["node_id"]

        # Step 2: assign Copilot via GraphQL if requested.
        copilot_assigned = False
        copilot_reason: str = "unknown"
        copilot_message: Optional[str] = None
        actor_candidates: list[str] = []
        actual_assignees = [a.get("login", "") for a in data.get("assignees", [])]

        if not req.assign_to_copilot:
            copilot_reason = "not_requested"
        else:
            copilot_actor_id, actor_candidates, gql_err = await _resolve_copilot_actor_id(
                client, req.owner, req.repo
            )
            if gql_err:
                copilot_reason = "graphql_error"
                copilot_message = (
                    f"GraphQL error while looking up Copilot bot: {gql_err}"
                )
            elif not copilot_actor_id:
                copilot_reason = "not_enabled"
                hint = (
                    f"The Copilot coding agent is not a suggested assignee for "
                    f"{req.owner}/{req.repo}. Enable it at Settings → Copilot → "
                    f"Coding agent, then retry."
                )
                if actor_candidates:
                    hint += (
                        f" GitHub returned {len(actor_candidates)} suggestable actor(s) "
                        f"({', '.join(actor_candidates[:5])}"
                        f"{'…' if len(actor_candidates) > 5 else ''}) "
                        "but none of them is the Copilot bot."
                    )
                else:
                    hint += (
                        " GitHub returned zero suggested actors — typically that "
                        "means the token can't see this repo, or the repo is "
                        "private and the token lacks access."
                    )
                copilot_message = hint
            else:
                # replaceActorsForAssignable replaces the entire actor list — include
                # existing human assignees so we don't drop them.
                human_ids = [
                    a["node_id"]
                    for a in data.get("assignees", [])
                    if a.get("node_id")
                ]
                actor_ids = [copilot_actor_id, *human_ids]
                mutation = await _gh_graphql(
                    client,
                    _REPLACE_ACTORS_MUTATION,
                    {"input": {"assignableId": issue_node_id, "actorIds": actor_ids}},
                )
                if mutation.get("errors"):
                    copilot_reason = "graphql_error"
                    copilot_message = "; ".join(
                        e.get("message", "") for e in mutation["errors"]
                    )
                else:
                    new_logins = [
                        n.get("login", "")
                        for n in (
                            ((mutation.get("data") or {})
                             .get("replaceActorsForAssignable") or {})
                            .get("assignable", {})
                            .get("assignees", {})
                            .get("nodes", [])
                            or []
                        )
                    ]
                    if new_logins:
                        actual_assignees = new_logins
                    copilot_assigned = any(
                        (l or "").lower().startswith("copilot")
                        for l in actual_assignees
                    )
                    copilot_reason = "ok" if copilot_assigned else "graphql_error"
                    if not copilot_assigned:
                        copilot_message = (
                            "GraphQL mutation returned no errors but the resulting "
                            "assignees do not include a Copilot bot. Refetch the "
                            "issue manually to confirm."
                        )

    return CreateGitHubIssueResponse(
        number=data["number"],
        html_url=data["html_url"],
        state=data.get("state", "open"),
        assignees=actual_assignees,
        title=data.get("title", req.title),
        copilot_assigned=copilot_assigned,
        copilot_reason=copilot_reason,
        copilot_message=copilot_message,
        actor_candidates=actor_candidates,
    )


@app.get("/github/copilot-status", response_model=CopilotStatusResponse)
async def github_copilot_status(
    owner: str = Query(...),
    repo: str = Query(...),
) -> CopilotStatusResponse:
    """Diagnostic — confirm whether GitHub considers the Copilot coding agent
    available for `owner/repo`. Returns the actor id (when found) and the full
    `suggestedActors` list so you can see exactly what the token is allowed to see.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        actor_id, candidates, err = await _resolve_copilot_actor_id(client, owner, repo)
    return CopilotStatusResponse(
        owner=owner,
        repo=repo,
        copilot_available=actor_id is not None,
        copilot_actor_id=actor_id,
        candidates=candidates,
        notes=err,
    )


# --- GitHub-sourced custom-agent discovery -------------------------------

async def _gh_get(client: httpx.AsyncClient, url: str) -> tuple[int, object]:
    """GET a GitHub API URL. Returns (status_code, parsed_json_or_text)."""
    resp = await client.get(url, headers=_github_headers())
    if resp.headers.get("content-type", "").startswith("application/json"):
        return resp.status_code, resp.json()
    return resp.status_code, resp.text


async def _gh_list_dir(
    client: httpx.AsyncClient, source_repo: str, directory: str
) -> list[dict]:
    """List a directory's entries via the GitHub Contents API. Returns []
    on 404/403 (missing dir or no access) so the caller can degrade gracefully."""
    url = f"{_GITHUB_API}/repos/{source_repo}/contents/{directory}"
    status_code, data = await _gh_get(client, url)
    if status_code in (404, 403):
        return []
    if status_code >= 400:
        raise HTTPException(status_code=status_code, detail=f"GitHub list error: {data}")
    if not isinstance(data, list):
        return []
    return data


async def _gh_fetch_file_text(
    client: httpx.AsyncClient, source_repo: str, path: str
) -> Optional[str]:
    """Fetch a single file's text content from GitHub Contents API.

    Returns None on 404 or any decoding failure.
    """
    import base64

    url = f"{_GITHUB_API}/repos/{source_repo}/contents/{path}"
    status_code, data = await _gh_get(client, url)
    if status_code == 404:
        return None
    if status_code >= 400 or not isinstance(data, dict):
        return None
    if data.get("encoding") != "base64":
        return None
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception:
        return None


def _parse_frontmatter(raw: str) -> dict:
    """Best-effort YAML frontmatter parse using python-frontmatter."""
    try:
        post = frontmatter.loads(raw)
        return dict(post.metadata)
    except Exception:
        return {}


async def _resolve_agents(
    client: httpx.AsyncClient,
    source_repo: str,
    directory: str,
    scope: Literal["repo", "org"],
) -> list[GitHubCustomAgent]:
    entries = await _gh_list_dir(client, source_repo, directory)
    candidates = [
        e for e in entries
        if isinstance(e, dict)
        and e.get("type") == "file"
        and e.get("name", "").endswith((".agent.md", ".md"))
        and e.get("name", "").lower() not in {"readme.md", "index.md"}
    ]

    async def _build_one(entry: dict) -> Optional[GitHubCustomAgent]:
        path = entry.get("path") or ""
        name_file = entry.get("name") or ""
        text = await _gh_fetch_file_text(client, source_repo, path)
        if text is None:
            return None
        meta = _parse_frontmatter(text)
        agent_id = name_file.removesuffix(".agent.md").removesuffix(".md")
        return GitHubCustomAgent(
            id=agent_id,
            name=str(meta.get("name") or agent_id),
            scope=scope,
            source_repo=source_repo,
            path=path,
            description=(str(meta["description"]) if meta.get("description") else None),
            tools=[str(t) for t in (meta.get("tools") or []) if t],
            skills=[str(s) for s in (meta.get("skills") or []) if s],
        )

    results = await asyncio.gather(*(_build_one(e) for e in candidates))
    return [a for a in results if a is not None]


@app.get("/github/agents", response_model=GitHubAgentsResponse)
async def list_github_agents(
    owner: str = Query(..., description="Target repo owner / org login"),
    repo: str = Query(..., description="Target repository name"),
) -> GitHubAgentsResponse:
    """List custom .agent.md profiles discoverable on GitHub for a target repo.

    Two scopes are merged (repo first, then org). Names from repo scope take
    precedence over org-level duplicates.

    - **repo**:  `<owner>/<repo>` → `.github/agents/`
    - **org**:   `<owner>/.github-private` → `agents/`
    """
    _ = _github_headers()  # fail fast if GH_TOKEN missing

    async with httpx.AsyncClient(timeout=30) as client:
        repo_agents, org_agents = await asyncio.gather(
            _resolve_agents(client, f"{owner}/{repo}", _REPO_AGENTS_DIR, "repo"),
            _resolve_agents(client, f"{owner}/{_ORG_REPO}", _ORG_AGENTS_DIR, "org"),
        )

    merged: list[GitHubCustomAgent] = []
    seen: set[str] = set()
    for batch in (repo_agents, org_agents):
        for a in batch:
            if a.id in seen:
                continue
            seen.add(a.id)
            merged.append(a)

    return GitHubAgentsResponse(owner=owner, repo=repo, agents=merged)


@app.get("/github/agents/content", response_model=GitHubAgentContentResponse)
async def get_github_agent_content(
    source_repo: str = Query(..., description="Where the file lives, e.g. 'my-org/.github-private'"),
    path: str = Query(..., description="File path within source_repo, e.g. 'agents/backend.agent.md'"),
) -> GitHubAgentContentResponse:
    """Fetch the raw text + parsed frontmatter of a single GitHub-hosted .agent.md."""
    _ = _github_headers()  # fail fast if GH_TOKEN missing

    async with httpx.AsyncClient(timeout=30) as client:
        text = await _gh_fetch_file_text(client, source_repo, path)
    if text is None:
        raise HTTPException(status_code=404, detail=f"{source_repo}/{path} not found")

    return GitHubAgentContentResponse(
        source_repo=source_repo,
        path=path,
        content=text,
        metadata=_parse_frontmatter(text),
    )


@app.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, request: Request) -> None:
    store: RedisSessionStore = request.app.state.session_store
    found = await store.delete(session_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def cli_main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent-api",
        description="Copilot Agent API server (FastAPI + uvicorn, Redis-backed).",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8001, help="Bind port (default: 8001)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode).")
    args = parser.parse_args()
    uvicorn.run("api_server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    cli_main()
