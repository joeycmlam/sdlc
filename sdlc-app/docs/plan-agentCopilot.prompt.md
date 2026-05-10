# Plan: agent_copilot.py Improvements

## TL;DR
Review of `agent_copilot.py` (and `api_server.py`) identified 30 issues across security, error handling, logic bugs, performance, and code quality. Grouped into HIGH/MEDIUM/LOW for prioritized implementation.

---

## Phase 1 — Critical (HIGH severity)

1. **SEC-1** `invoke_agent` path traversal: add `resolve()` + `is_relative_to()` guard in `AgentRunner._handle_invoke_agent`
2. **SEC-2** API server binds to `0.0.0.0` with no auth: change default host to `127.0.0.1` in `api_server.py`
3. **ERR-1** `CLI.load_agent_file` calls `sys.exit(1)`: replace with `raise FileNotFoundError(...)`, wrap call site in try/except returning ToolResult failure
4. **ERR-2** Sub-agent exception propagates unhandled in `_handle_invoke_agent`: wrap `AgentRunner(sub_config).run(...)` in try/except
5. **LOGIC-1** Interactive mode creates new session per turn (no history): refactor `AgentRunner` to hold session open across turns; expose `step()` method
6. **PERF-1 / FEAT-1** No output size cap on `BashTool`: add 100 KB truncation after `proc.communicate()`; also truncate `invoke_agent` results before returning to LLM

---

## Phase 2 — Important (MEDIUM severity)

7. **SEC-3** CORS wildcard: restrict `allow_origins` to `["http://localhost:3000"]` or env var
8. **SEC-4** Blocklist bypass (`rm -r subdir` unblocked): broaden `rm` pattern; accept Docker/seccomp as real enforcement
9. **SEC-5** No input validation on `RunRequest`: add `max_length` + `pattern` constraints to Pydantic fields
10. **ERR-3** `SESSION_ERROR` returns silent empty string: add `error` field to `TurnState`, surface in `run()` return
11. **LOGIC-2** `_PENDING_STEPS_RE` misses steps >=10: fix regex to `r"\bStep\s+(?:[5-9]|\d{2,})\b"`
12. **LOGIC-3** `finish` summary not returned to API callers: store in `self._finish_summary`, include in `run()` return
13. **LOGIC-4** CWD not injected via API path: add same CWD injection in `api_server._build_runner`
14. **PERF-2** `skill_directories` glob on every `run()` call: move to `AgentRunner.__init__`
15. **PERF-3** No concurrency limit on API endpoints: add `asyncio.Semaphore` in `api_server.py`
16. **QUAL-1** `AgentRecord` missing `agents` field: add `agents: list[str]` to dataclass, read from frontmatter
17. **FEAT-3** `--interactive` + piped stdin conflict: make flags mutually exclusive
18. **FEAT-4** No outer run timeout in API: wrap `runner.run(...)` with `asyncio.wait_for(..., timeout=600)`

---

## Phase 3 — Polish (LOW severity)

19. **ERR-4** `disconnect()` can mask errors: wrap in `try/except Exception: pass`
20. **ERR-5** Registry parse errors silently swallowed: add `print(warning, file=sys.stderr)`
21. **LOGIC-5** `reversed()` no-op in `last_completed_step`: remove or rewrite with `max()`
22. **PERF-4** `BashTool` re-instantiated per runner: extract module-level singleton
23. **QUAL-2** Magic number `3 if depth > 0 else 5`: named constants `MAX_TEXT_ONLY_TURNS_ROOT/SUB`
24. **QUAL-3** Hardcoded `MAX_TURNS_*` constants: read from env vars with current values as defaults
25. **QUAL-4** `_INVOKE_AGENT_SCHEMA` / `_FINISH_SCHEMA` as class attrs: move to module-level constants
26. **CFG-2** Bash timeout hardcoded: `BASH_TIMEOUT = int(os.getenv("BASH_EXEC_TIMEOUT", "120"))`
27. **CFG-3** `AGENTS_DIR`/`SKILLS_DIR` not configurable: read from env vars
28. **FEAT-5** SDK versions unpinned: pin in `requirements.txt`

---

## Relevant Files
- `services/copilot-agent/agent_copilot.py` — primary target (SEC-1, ERR-1/2, LOGIC-1/2/3/5, PERF-1/2/4, all QUAL/CFG/FEAT)
- `services/copilot-agent/api_server.py` — SEC-2, SEC-3, SEC-5, LOGIC-4, PERF-3, FEAT-4, CFG-1
- `services/copilot-agent/registry.py` — ERR-5, QUAL-1
- `services/copilot-agent/requirements.txt` — FEAT-5

## Decisions
- LOGIC-1 (interactive session persistence) is the largest refactor; all other items are surgical
- Security issues (Phase 1) should be implemented before any public exposure
- PERF-1 truncation limit of 100 KB is a reasonable default; make configurable via env var
