---
id: innovation-lab
name: "Innovation Lab"
description: "Sandbox squad — fully autonomous, no approval gates. Used for prototypes, spikes, and internal-only experiments."
owner: "innovation@example.com"

default_model: claude-sonnet-4.5
default_execution_mode: autonomous
default_approval_policy: []

allowed_agents:
  - ba
  - jira-ba
  - test-designer
  - test-analyst

jira_project_key: LAB
confluence_space_key: INNOV
---
## Team Standards

- Speed over rigor — prototypes only, no production deploys from this team.
- Acceptance criteria should be lightweight (happy path + one edge case).
- Do not target customer-facing systems from this team's sessions.
