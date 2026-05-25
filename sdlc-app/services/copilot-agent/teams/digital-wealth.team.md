---
id: digital-wealth
name: "Digital Wealth"
description: "Customer-facing robo-advisory and onboarding apps. Faster cadence — autonomous for drafts, human approval only for GitHub writes."
owner: "digital-wealth-eng@example.com"

default_model: claude-sonnet-4.5
default_execution_mode: human_touch
default_approval_policy:
  - create_github_issue

allowed_agents:
  - ba
  - jira-ba
  - test-designer
  - jira-test-automator
  - test-analyst

jira_project_key: DW
confluence_space_key: WEALTH
---
## Team Standards

- Personas: emphasise the HNW client journey (KYC, suitability, risk tolerance).
- Mobile-first acceptance criteria — every UI requirement must specify mobile viewport behaviour.
- Localisation: traditional Chinese (HK) + English required by default.

## Escalation

- Product questions → #digital-wealth-product
- UX review → @design-team
