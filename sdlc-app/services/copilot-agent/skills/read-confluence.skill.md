---
id: read-confluence
name: read-confluence
description: "Fetch and summarize Confluence pages using the atlassian-bridge service. Use when: reading a Confluence page, fetching wiki documentation, retrieving architecture decisions from Confluence, looking up domain knowledge or glossary pages, fetching design documents or runbooks, or when a Jira ticket links to Confluence pages."
argument-hint: "Full Confluence page URL, e.g. https://myorg.atlassian.net/wiki/spaces/ENG/pages/12345/Page-Title"
---

# Read Confluence Pages

Fetch one or more Confluence pages via the `atlassian-bridge` service and extract relevant domain context for use in refinement, BRD authoring, or GitHub issue creation.

## When to Use

- User provides a Confluence page URL
- A Jira ticket's description or remote links reference Confluence pages
- You need architecture decisions, design docs, domain glossaries, or runbooks as context
- You are generating a BRD or acceptance criteria and need domain grounding

## Fetch a Page

```bash
curl -s -X POST http://localhost:8002/confluence/fetch \
  -H "Content-Type: application/json" \
  -d '{"url": "<full-confluence-page-url>"}' | python3 -m json.tool
```

The response includes:
- `id` — Confluence page ID
- `title` — page title
- `space_key` — Confluence space
- `content_markdown` — full page content converted to Markdown
- `last_modified` — ISO timestamp
- `author` — last editor display name

## Search Pages

```bash
curl -s -X POST http://localhost:8002/confluence/search \
  -H "Content-Type: application/json" \
  -d '{"query": "architecture overview", "space_key": "ENG", "limit": 5}' | python3 -m json.tool
```

## List Child Pages

```bash
curl -s -X POST http://localhost:8002/confluence/children \
  -H "Content-Type: application/json" \
  -d '{"url": "<parent-page-url>"}' | python3 -m json.tool
```

## Usage Pattern for BA Refinement

1. Extract Confluence URLs from the Jira ticket description or remote links
2. Call `POST /confluence/fetch` for each URL to get `content_markdown`
3. Use `content_markdown` as domain grounding when:
   - Writing acceptance criteria
   - Authoring BRD sections
   - Identifying glossary terms and canonical names
4. Inject the page URLs as `KnowledgeRef(kind="confluence", value="<url>")` into the GitHub issue body so the cloud Copilot agent can also access them

## Environment

The service reads credentials from environment variables — never include credentials in requests:

| Variable | Value |
|---|---|
| `ATLASSIAN_URL` | `https://your-org.atlassian.net` |
| `ATLASSIAN_USER` | Atlassian account email |
| `ATLASSIAN_API_TOKEN` | Token from id.atlassian.com |

## SSRF Protection

The bridge validates that all incoming URLs belong to the configured `ATLASSIAN_URL` instance. Requests to other hosts are rejected with `403`.
