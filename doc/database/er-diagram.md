---
Auto-generated: true
Generated on: 2026-05-10 09:41:26 UTC
Generator: doc-architect agent v1.0
Repository: joeycmlam/sdlc
Branch: copilot/prepare-system-documentation
Commit: afd9a49
---

# Conceptual ER Diagram

The live system uses Redis, but the following conceptual entities describe the shape of persisted workflow data.

```mermaid
erDiagram
    SESSION ||--o{ SESSION_EVENT : emits
    SESSION ||--o| GITHUB_ISSUE : creates
    SESSION {
        string id PK
        string state
        string agent_file
        string instruction
        string model
        int max_turns
        string jira_url
        string github_owner
        string github_repo
        string custom_agent
        string result
        string error
        datetime created_at
        datetime updated_at
    }
    SESSION_EVENT {
        string stream_id PK
        string session_id FK
        string type
        string data
    }
    GITHUB_ISSUE {
        int number PK
        string session_id FK
        string html_url
        boolean copilot_assigned
    }
```

## Relationship notes

- A `SESSION` may emit many `SESSION_EVENT` records during a streamed run.
- A `SESSION` may create zero or one GitHub issue through `/github/issues`.
- Jira and Confluence URLs are referenced by value from the session rather than normalized into separate tables.
