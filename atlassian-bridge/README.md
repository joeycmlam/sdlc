# atlassian-bridge

A FastAPI proxy service that provides unified access to Jira REST API v3 and Confluence REST API v2. Centralizes Atlassian credentials server-side so frontend and agent services never handle sensitive tokens.

## Purpose

In the SDLC AI Agent Platform, agents need to:
- Read Jira issues with full details (description, comments, attachments)
- Add comments to Jira issues
- Read Confluence pages
- Update Confluence documentation

Rather than distributing Atlassian API tokens to multiple services, `atlassian-bridge` acts as a secure proxy that:
1. Holds credentials in server-side environment variables
2. Exposes clean REST endpoints to clients
3. Handles authentication, retry logic, and rate limiting
4. Provides request/response transformation

## Architecture

```
┌──────────────────┐       ┌──────────────────┐       ┌───────────────┐
│ Copilot Agent    │ HTTP  │ Atlassian Bridge │ HTTPS │ Jira Cloud    │
│ or Frontend      │──────►│                  │──────►│               │
│                  │       │ :8002            │       │ REST API v3   │
└──────────────────┘       └──────────────────┘       └───────────────┘
                                   │
                                   │ HTTPS
                                   ▼
                           ┌───────────────┐
                           │ Confluence    │
                           │ Cloud         │
                           │ REST API v2   │
                           └───────────────┘
```

## Features

- **Jira Integration**:
  - Get issue details by key
  - List issues by JQL query
  - Add comments to issues
  - Get issue attachments

- **Confluence Integration**:
  - Get page content by ID
  - Search pages
  - Get page attachments

- **Security**:
  - Credentials stored server-side only
  - CORS middleware for frontend access
  - Health check endpoint for monitoring

- **Reliability**:
  - Connection pooling via httpx
  - Automatic retry with exponential backoff (TODO)
  - Request timeout handling

## Quick Start

### Prerequisites

- Python ≥ 3.11
- Atlassian API tokens:
  - **Jira**: [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
  - **Confluence**: Same token works for both

### Installation

```bash
# 1. Navigate to the atlassian-bridge directory
cd atlassian-bridge

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# or .venv\Scripts\activate      # Windows

# 3. Install dependencies
pip install -e .
```

### Configuration

Create a `.env` file (or export environment variables):

```bash
# Required
JIRA_URL=https://yourorg.atlassian.net
JIRA_USER=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token

CONFLUENCE_URL=https://yourorg.atlassian.net/wiki
CONFLUENCE_USER=your-email@example.com
CONFLUENCE_API_TOKEN=your-confluence-api-token

# Optional
PORT=8002
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8001
```

### Running

```bash
# Using the installed command
atlassian-bridge

# Or directly with Python
python -m app.main

# With custom port
PORT=9000 atlassian-bridge
```

The service will be available at http://localhost:8002.

## API Reference

### Health Check

```http
GET /health
```

**Response**:
```json
{
  "status": "ok",
  "service": "atlassian-bridge",
  "version": "1.0.0"
}
```

---

### Jira Endpoints

#### Get Issue

```http
GET /jira/issue/{issue_key}
```

**Parameters**:
- `issue_key` (path): Jira issue key (e.g., `SCRUM-123`)

**Response**:
```json
{
  "key": "SCRUM-123",
  "fields": {
    "summary": "Issue summary",
    "description": "Full description",
    "status": { "name": "In Progress" },
    "assignee": { "displayName": "Jane Doe" },
    "priority": { "name": "High" },
    "created": "2026-05-23T10:00:00.000+0000",
    "updated": "2026-05-23T12:00:00.000+0000"
  }
}
```

#### Search Issues (JQL)

```http
GET /jira/search?jql={jql_query}&maxResults={max}&startAt={start}
```

**Parameters**:
- `jql` (query): JQL query string (e.g., `project = SCRUM AND status = "In Progress"`)
- `maxResults` (query, optional): Max results to return (default: 50)
- `startAt` (query, optional): Pagination offset (default: 0)

**Response**:
```json
{
  "issues": [
    {
      "key": "SCRUM-123",
      "fields": { ... }
    }
  ],
  "total": 42,
  "maxResults": 50,
  "startAt": 0
}
```

#### Add Comment

```http
POST /jira/issue/{issue_key}/comment
Content-Type: application/json
```

**Request Body**:
```json
{
  "body": "This is a comment"
}
```

**Response**:
```json
{
  "id": "10001",
  "author": {
    "displayName": "Jane Doe"
  },
  "body": "This is a comment",
  "created": "2026-05-23T12:30:00.000+0000"
}
```

#### Get Issue Attachments

```http
GET /jira/issue/{issue_key}/attachments
```

**Response**:
```json
{
  "attachments": [
    {
      "id": "10000",
      "filename": "screenshot.png",
      "size": 123456,
      "mimeType": "image/png",
      "content": "https://yourorg.atlassian.net/secure/attachment/10000/screenshot.png"
    }
  ]
}
```

---

### Confluence Endpoints

#### Get Page

```http
GET /confluence/page/{page_id}
```

**Parameters**:
- `page_id` (path): Confluence page ID
- `expand` (query, optional): Comma-separated list of fields to expand (e.g., `body.storage,version`)

**Response**:
```json
{
  "id": "12345",
  "title": "Page Title",
  "type": "page",
  "space": {
    "key": "DEV",
    "name": "Development"
  },
  "body": {
    "storage": {
      "value": "<p>Page content in storage format</p>",
      "representation": "storage"
    }
  },
  "version": {
    "number": 5,
    "when": "2026-05-23T10:00:00.000Z"
  }
}
```

#### Search Pages

```http
GET /confluence/search?cql={cql_query}&limit={limit}
```

**Parameters**:
- `cql` (query): CQL query string (e.g., `space = DEV AND type = page`)
- `limit` (query, optional): Max results (default: 25)

**Response**:
```json
{
  "results": [
    {
      "content": {
        "id": "12345",
        "type": "page",
        "title": "Page Title"
      },
      "excerpt": "Page excerpt..."
    }
  ],
  "size": 10
}
```

---

## Usage Examples

### From Python (httpx)

```python
import httpx

async def get_jira_issue(issue_key: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8002/jira/issue/{issue_key}"
        )
        response.raise_for_status()
        return response.json()

# Usage
issue = await get_jira_issue("SCRUM-123")
print(issue["fields"]["summary"])
```

### From curl

```bash
# Get Jira issue
curl http://localhost:8002/jira/issue/SCRUM-123

# Add comment to Jira issue
curl -X POST http://localhost:8002/jira/issue/SCRUM-123/comment \
  -H "Content-Type: application/json" \
  -d '{"body": "Updated from API"}'

# Get Confluence page
curl "http://localhost:8002/confluence/page/12345?expand=body.storage"

# Search Jira with JQL
curl "http://localhost:8002/jira/search?jql=project%20%3D%20SCRUM%20AND%20status%20%3D%20%22In%20Progress%22"
```

### From JavaScript (Fetch API)

```javascript
// Get Jira issue
async function getJiraIssue(issueKey) {
  const response = await fetch(
    `http://localhost:8002/jira/issue/${issueKey}`
  );
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return await response.json();
}

// Add comment
async function addComment(issueKey, body) {
  const response = await fetch(
    `http://localhost:8002/jira/issue/${issueKey}/comment`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body })
    }
  );
  return await response.json();
}
```

---

## Docker

### Build

```bash
docker build -t atlassian-bridge .
```

### Run

```bash
docker run -d \
  --name atlassian-bridge \
  -p 8002:8002 \
  -e JIRA_URL=https://yourorg.atlassian.net \
  -e JIRA_USER=your-email@example.com \
  -e JIRA_API_TOKEN=your-token \
  -e CONFLUENCE_URL=https://yourorg.atlassian.net/wiki \
  -e CONFLUENCE_USER=your-email@example.com \
  -e CONFLUENCE_API_TOKEN=your-token \
  atlassian-bridge
```

### Docker Compose

See the root [docker-compose.yml](../docker-compose.yml) for full-stack deployment.

---

## Development

### Project Structure

```
atlassian-bridge/
├── Dockerfile              # Container image definition
├── pyproject.toml          # Python package metadata
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI application
│   ├── jira.py            # Jira endpoint handlers
│   ├── confluence.py      # Confluence endpoint handlers
│   ├── client.py          # Shared httpx client with auth
│   └── models.py          # Pydantic models for request/response
```

### Adding New Endpoints

1. **Define the route** in `jira.py` or `confluence.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/jira")

@router.get("/project/{project_key}")
async def get_project(project_key: str):
    # Implementation
    pass
```

2. **Use the shared client** from `client.py`:

```python
from .client import get_jira_client

@router.get("/project/{project_key}")
async def get_project(project_key: str):
    async with get_jira_client() as client:
        response = await client.get(f"/rest/api/3/project/{project_key}")
        response.raise_for_status()
        return response.json()
```

3. **Register the router** in `main.py` (already done for jira and confluence routers).

### Testing

```bash
# Install dev dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/

# With coverage
pytest --cov=app tests/
```

### Hot Reload (Development)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
```

---

## Monitoring

### Health Check

The `/health` endpoint provides basic service status. Integrate with:
- **Docker healthcheck**: `HEALTHCHECK CMD curl -f http://localhost:8002/health`
- **Kubernetes liveness probe**: `httpGet: { path: /health, port: 8002 }`
- **Monitoring tools**: Prometheus, Datadog, etc.

### Logging

Logs are written to stdout/stderr (12-factor app pattern):
- Request logs: FastAPI automatic logging
- Error logs: Python `logging` module
- View logs: `docker logs atlassian-bridge`

### Metrics (TODO)

Future enhancements:
- Prometheus metrics endpoint (`/metrics`)
- Request rate, latency, error rate
- Atlassian API rate limit tracking

---

## Security Considerations

### Credential Management

- **Never commit tokens to Git**: Use `.env` file or environment variables
- **Production**: Use secrets manager (AWS Secrets Manager, Azure Key Vault)
- **Rotation**: Regenerate API tokens periodically

### CORS

The service allows CORS from origins specified in `ALLOWED_ORIGINS`:
- Default: `http://localhost:3000` (Next.js frontend)
- Production: Set to your actual frontend domain

### Rate Limiting (TODO)

Jira and Confluence have rate limits:
- **Jira Cloud**: ~300 requests/minute per user
- **Confluence Cloud**: Similar limits

Future: Implement client-side rate limiting and queuing.

### Input Validation

- FastAPI automatically validates request parameters via Pydantic models
- Path parameters (e.g., `issue_key`) are sanitized
- Query parameters are URL-encoded

---

## Troubleshooting

### 401 Unauthorized

- **Cause**: Invalid API token or email
- **Fix**: Verify credentials at [id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens)

### 403 Forbidden

- **Cause**: User lacks permission for the requested resource
- **Fix**: Check Jira/Confluence permissions for the user account

### 404 Not Found

- **Cause**: Issue/page doesn't exist or is inaccessible
- **Fix**: Verify the resource exists and the user has view permission

### Connection Timeout

- **Cause**: Network issues or Atlassian service down
- **Fix**: Check internet connectivity and [status.atlassian.com](https://status.atlassian.com)

### CORS Errors in Browser

- **Cause**: Frontend origin not in `ALLOWED_ORIGINS`
- **Fix**: Add frontend origin to `ALLOWED_ORIGINS` environment variable

---

## Roadmap

- [ ] Retry logic with exponential backoff
- [ ] Rate limiting and request queuing
- [ ] Prometheus metrics endpoint
- [ ] Webhook support for Jira/Confluence events
- [ ] Bulk operations (batch issue updates)
- [ ] Caching layer (Redis) for frequently accessed resources
- [ ] GraphQL endpoint (unified query interface)
- [ ] Support for Jira Data Center / Server (on-premise)

---

## Related Documentation

- [Main README](../README.md) — Platform overview
- [ARCHITECTURE](../ARCHITECTURE.md) — System architecture
- [Copilot Agent](../sdlc-app/services/copilot-agent/README.md) — Agent service that uses this bridge

---

## License

[Add your license here]
