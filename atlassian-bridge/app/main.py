"""atlassian-bridge — FastAPI entry point.

Provides Jira (REST API v3) and Confluence (REST API v2) endpoints behind
a single service that shares one Atlassian API token.

Services:
  copilot-gateway  :8000  — GitHub REST/GraphQL
  agent-runner     :8001  — Copilot SDK / SSE streaming
  atlassian-bridge :8002  — Jira + Confluence (this service)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .client import lifespan_client
from .confluence import router as confluence_router
from .jira import router as jira_router
from .models import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with lifespan_client():
        yield


app = FastAPI(
    title="atlassian-bridge",
    description="Jira and Confluence proxy — credentials on server, context from caller.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(jira_router)
app.include_router(confluence_router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


def main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=False)


if __name__ == "__main__":
    main()
