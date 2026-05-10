---
id: read-jira
name: read-jira
description: "Read and summarize Jira issues using the jira-cli script. Use when: fetching a Jira ticket, reading a Jira issue, looking up JIRA story details, retrieving comments or attachments from Jira, analyzing a Jira bug or task, understanding requirements from a Jira card, or any request referencing a Jira issue key (e.g. PROJECT-123). Can pipe output into copilot-agent for AI analysis."
argument-hint: "Jira issue key, e.g. PROJECT-123"
---

# Read Jira Issues

Fetch a Jira issue — description, metadata, comments, and attachments — and produce a structured Markdown report. Optionally pipe into `copilot-agent` for AI-powered analysis.

## When to Use

- User says "read Jira ticket", "fetch issue", "look up PROJECT-123", "summarize this Jira story"
- User provides an issue key matching the pattern `[A-Z]+-[0-9]+` (e.g. `ABC-456`)
- User wants to understand requirements, status, or comments from a Jira card
- User wants to analyze a ticket (generate tests, draft PR description, extract acceptance criteria)

## First-Time Setup

Run these commands from the repo root — creates the venv and installs dependencies:

```bash
cd services/jira-cli && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

Then fill in credentials in `services/jira-cli/.env`:

| Variable | Value |
|---|---|
| `JIRA_URL` | e.g. `https://yourorg.atlassian.net` |
| `JIRA_USER` | your Jira account email |
| `JIRA_API_TOKEN` | create at [id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens) |

## Procedure

### Step 1 — Extract the issue key
Identify the Jira issue key from the user's message (`[A-Z]+-[0-9]+`, e.g. `PROJECT-123`).
If none provided, ask: *"Which Jira issue key would you like me to fetch?"*

### Step 2 — Choose a usage pattern

**A) Read and display only** — fetch and show the structured Markdown:

```bash
cd services/jira-cli && source .venv/bin/activate
python jira_cli.py PROJECT-123
```

**B) Read and analyze with AI** — pipe into copilot-agent for AI analysis:

```bash
services/jira-cli/.venv/bin/python services/jira-cli/jira_cli.py PROJECT-123 | python services/copilot-agent/agent.py -a services/copilot-agent/agents/jira-reader.md -m gpt-4o
```

**C) Interactive AI analysis** — fetch first, then start a conversation:

```bash
services/jira-cli/.venv/bin/python services/jira-cli/jira_cli.py PROJECT-123 | python services/copilot-agent/agent.py -a services/copilot-agent/agents/jira-reader.md -m gpt-4o --interactive
```

### Step 3 — Command options

**Read flags:**

| Flag | Purpose |
|---|---|
| `--output FILE` | Save Markdown to a file |
| `--no-attachments` | Skip downloading attachments (list filenames only) |
| `--comments-limit N` | Show only the last N comments |

**Write flags:**

| Flag | Purpose |
|---|---|
| `--add-comment TEXT\|-` | Add a comment; use `-` to read from stdin |
| `--update-description TEXT\|-` | Replace the issue description; use `-` to read from stdin |
| `--attach-file PATH` | Upload a local file as an attachment |
| `--list-transitions` | List all available workflow transitions (outputs a Markdown table) |
| `--transition NAME_OR_ID` | Move the issue to a new status by name (case-insensitive) or numeric ID |

### Step 4 — Present the output

The structured Markdown includes:
- **Metadata table** — type, status, priority, assignee, reporter, dates, labels
- **Description** — full issue description
- **Attachments** — extracted text from `.txt`, `.md`, `.pdf`, `.docx`, `.xlsx`
- **Comments** — all comments with author and timestamp

After displaying, offer to:
- Analyze requirements or acceptance criteria
- Generate unit tests from the ticket
- Draft a PR description
- Identify blockers or action items

## Integration with Other Python Agents

Any Python script in this monorepo can use `jira_cli.py` via subprocess or stdin pipe:

```python
import subprocess
result = subprocess.run(
    ["python", "services/jira-cli/jira_cli.py", "PROJECT-123", "--no-attachments"],
    capture_output=True, text=True
)
jira_markdown = result.stdout
```

## Troubleshooting

| Error | Fix |
|---|---|
| `Missing required environment variable(s)` | Fill in `services/jira-cli/.env` — see First-Time Setup |
| `Error connecting to Jira` | Check `JIRA_URL` format and network access |
| `ModuleNotFoundError` | Run `bash services/copilot-agent/skills/read-jira/setup.sh` |
| `JIRAError: Issue does not exist` | Verify issue key and account permissions |
| PDF/DOCX not extracted | `pip install pdfminer.six python-docx openpyxl` in the venv |
