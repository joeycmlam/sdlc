---
id: core-platform
name: "Core Platform"
description: "Trading + post-trade infrastructure team. High-risk changes — every Jira/GitHub write requires human sign-off."
owner: "core-platform-leads@example.com"

default_model: claude-sonnet-4.5
default_execution_mode: human_touch
default_approval_policy:
  - create_github_issue
  - jira:write

allowed_agents:
  - ba
  - jira-ba
  - test-designer
  - jira-test-automator
  - test-analyst

jira_project_key: CORE
confluence_space_key: PLATFORM
---
## Team Standards

- All requirements MUST cite the regulatory regime (MiFID II / UCITS / SFC) where applicable.
- Acceptance criteria MUST include both the happy path and a documented rollback step.
- Performance NFRs MUST reference the trading window (08:00–17:30 HKT) where relevant.
- Test scenarios MUST include the "FX cross-rate at month-end" and "intraday price stale" edge cases when prices are involved.

## Escalation

- Compliance questions → #compliance-platform Slack
- Operational risk → core-platform-leads@example.com
