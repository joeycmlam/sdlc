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

## Runtime Environment

Inside the Docker container, `jira_cli.py` is pre-installed at `/jira-cli/jira_cli.py` and all required credentials are injected as environment variables (`JIRA_URL`, `JIRA_USER`, `JIRA_API_TOKEN`). No venv activation or `.env` setup is needed.

## Procedure

### Step 1 — Extract the issue key
Identify the Jira issue key from the user's message (`[A-Z]+-[0-9]+`, e.g. `PROJECT-123`).
If none provided, ask: *"Which Jira issue key would you like me to fetch?"*

### Step 2 — Choose a usage pattern

**A) Read and display only** — fetch and show the structured Markdown:

```bash
python /jira-cli/jira_cli.py PROJECT-123
```

**B) Read and analyze with AI** — pipe into copilot-agent for AI analysis:

```bash
python /jira-cli/jira_cli.py PROJECT-123 | python /app/agent.py -a /app/agents/jira-reader.md -m gpt-4o
```

**C) Interactive AI analysis** — fetch first, then start a conversation:

```bash
python /jira-cli/jira_cli.py PROJECT-123 | python /app/agent.py -a /app/agents/jira-reader.md -m gpt-4o --interactive
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
    ["python", "/jira-cli/jira_cli.py", "PROJECT-123", "--no-attachments"],
    capture_output=True, text=True
)
jira_markdown = result.stdout
```

## Troubleshooting

| Error | Fix |
|---|---|
| `Missing required environment variable(s)` | Ensure `JIRA_URL`, `JIRA_USER`, `JIRA_API_TOKEN` are set in container env |
| `Error connecting to Jira` | Check `JIRA_URL` format and network access |
| `ModuleNotFoundError` | Rebuild the Docker image — dependencies must be in `/jira-cli/` |
| `JIRAError: Issue does not exist` | Verify issue key and account permissions |
| PDF/DOCX not extracted | `pip install pdfminer.six python-docx openpyxl` in the venv |
