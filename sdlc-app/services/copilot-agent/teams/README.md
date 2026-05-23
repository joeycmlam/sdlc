# Teams

A **team manifest** lets a single SDLC platform serve multiple delivery teams
or systems, each with its own:

- agent roster (which personas they're allowed to invoke)
- default execution mode (autonomous vs. human_touch)
- approval policy (which write tools require sign-off)
- Jira project + Confluence space (so the agents target the right backlog)
- preferred LLM model

## File format

One YAML-frontmatter Markdown file per team, named `<id>.team.md`. The
Markdown body is free-text — use it to capture team-specific guidance the
agents should follow.

```yaml
---
id: <stable kebab-case id — used in API calls>
name: "<display name>"
description: "<one-line summary>"
owner: "<email or Slack handle>"

# LLM + execution defaults applied when the caller doesn't override them.
default_model: claude-sonnet-4.5
default_execution_mode: autonomous | human_touch
default_approval_policy:
  - create_github_issue
  - jira:write

# Whitelist of agent ids (from agents/*.agent.md `id:` frontmatter) this
# team is allowed to invoke. Sessions targeting a different agent_file
# are rejected with HTTP 403.
allowed_agents: [ba, test-designer, qa-subagent]

# Enterprise-tool scoping injected into extra_context at runtime.
jira_project_key: SCRUM
confluence_space_key: DEV
---
Free-text guidance shown to every agent the team invokes — house style,
naming conventions, regulatory context, escalation contacts, etc.
```

## How sessions resolve team defaults

When `POST /sessions` is called with `team_id: "core-platform"`:

1. The team manifest is loaded.
2. The session's `agent_file` is validated against `allowed_agents`.
3. Any field the caller left unset (`model`, `execution_mode`,
   `approval_policy`) is filled in from the manifest.
4. `jira_project_key` and `confluence_space_key` are prepended to
   `extra_context` so the agent picks the right project/space.

Caller-supplied values always win — teams set defaults, not hard rules.
