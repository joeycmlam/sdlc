---
Auto-generated: true
Generated on: 2026-05-10 09:41:26 UTC
Generator: doc-architect agent v1.0
Repository: joeycmlam/sdlc
Branch: copilot/prepare-system-documentation
Commit: afd9a49
---

# Business Logic Workflows

## 1. Stateless assistant chat

Purpose: let a user run a quick prompt against a selected agent without provisioning a session.

1. User submits a prompt from the chat UI.
2. Next.js calls `/api/stream`.
3. `copilot-agent` runs the selected agent in-process.
4. The UI renders streamed `chunk`, `tool`, and `done` events.

## 2. BA refinement from Jira

Purpose: refine an upstream Jira issue into a better implementation brief.

1. User supplies a Jira URL and chooses a BA-oriented agent.
2. Session creation stores the Jira URL and any supporting Confluence pages.
3. The worker enriches the run with that context.
4. The response is surfaced to the user through the session event stream.

## 3. Approval-gated execution

Purpose: keep a human in the loop before irreversible actions.

1. A running session transitions to `awaiting_approval`.
2. A user approves or rejects the next step through `/sessions/{id}/approve`.
3. The state machine moves to `approved` or `rejected`.
4. The workflow resumes or terminates according to the session logic.

## 4. GitHub issue creation and Copilot assignment

Purpose: turn refined requirements into actionable implementation work.

1. A user submits the issue form or a session requests issue creation.
2. The Python backend creates the GitHub issue.
3. If `assign_to_copilot=true`, the backend attempts to add the `Copilot` assignee.
4. The UI reports the issue URL and whether Copilot assignment succeeded.

## 5. Jira CLI export

Purpose: generate a clean Markdown brief from an existing Jira issue for offline review.

1. A developer runs `python jira_cli.py ISSUE-123`.
2. The CLI fetches the issue, comments, and supported attachments.
3. Content is normalized into Markdown and written to stdout or a file.
