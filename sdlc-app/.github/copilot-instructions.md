# Copilot Instructions for mypoc Monorepo

This is a full-stack monorepo workspace for proof of concept (POC) projects.

## Project Structure

- `app/` - Next.js App Router (pages, API routes, layouts) — **do not place Python projects here**
- `components/` - React UI components
- `lib/` - Shared TypeScript utilities (`utils.ts`, `types.ts`, `api.ts`)
- `services/` - Python backend services (each service is independent)
- `docs/` - Project documentation
- `.vscode/` - VS Code workspace configuration

## Python Services (`services/`)

Each service under `services/` is self-contained:

```
services/
  ├── copilot-agent/   ← FastAPI server + LLM agent runner
  └── jira-cli/        ← Jira CLI tool for reading/writing tickets
```

### Starting the agent API server

```bash
cd services/copilot-agent && python api_server.py
```

### Running the Jira CLI

```bash
cd services/jira-cli && python jira_cli.py PROJECT-123
```

## How to Add a New Service

1. Create a new directory under `services/`
2. Each service can have its own:
   - Virtual environment (`.venv/`)
   - `requirements.txt` or `pyproject.toml`
   - README with service-specific documentation
   - Main code files

## Example Service Structure

```
services/
  └── my-service/
      ├── README.md
      ├── requirements.txt
      ├── src/
      └── tests/
```
