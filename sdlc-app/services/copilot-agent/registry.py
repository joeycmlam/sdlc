"""
Agent, Skill, and Team registries.

Loaded at startup by scanning:
  - skills/*.skill.md   → SkillRegistry
  - agents/*.agent.md   → AgentRegistry
  - teams/*.team.md     → TeamRegistry

Each file must have YAML frontmatter with at minimum an ``id`` field.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import frontmatter


@dataclass
class SkillRecord:
    id: str
    name: str
    description: str
    argument_hint: str
    content: str  # markdown body (frontmatter stripped)


@dataclass
class AgentRecord:
    id: str
    name: str
    description: str
    triggers: list[str]   # regex patterns matched against user input
    skills: list[str]     # skill IDs this agent uses
    tools: list[str]      # tool names available to this agent
    prompt: str           # full file content (used as system prompt)


@dataclass
class TeamRecord:
    """A team manifest — the per-team default configuration for sessions.

    Loaded from teams/<id>.team.md. The Markdown body (``guidance``) is
    prepended to each session's extra_context so agents see team standards.
    """
    id: str
    name: str
    description: str
    owner: str
    default_model: str
    default_execution_mode: Literal["autonomous", "human_touch"]
    default_approval_policy: list[str]
    allowed_agents: list[str]
    jira_project_key: Optional[str]
    confluence_space_key: Optional[str]
    guidance: str  # markdown body, used as team-level extra_context

    def is_agent_allowed(self, agent_id: str) -> bool:
        # An empty allowed_agents list means 'no restriction' so that a team
        # which simply hasn't curated its list yet stays unblocked.
        if not self.allowed_agents:
            return True
        return agent_id in self.allowed_agents


class SkillRegistry:
    """Loads all *.skill.md files from a directory into an id-keyed dict."""

    def __init__(self, skills_dir: Path) -> None:
        self._skills: dict[str, SkillRecord] = {}
        self._load(skills_dir)

    def _load(self, skills_dir: Path) -> None:
        for path in sorted(skills_dir.glob("*.skill.md")):
            try:
                post = frontmatter.load(str(path))
                skill_id: str = post.metadata.get("id") or post.metadata.get("name", "")
                if not skill_id:
                    continue
                self._skills[skill_id] = SkillRecord(
                    id=skill_id,
                    name=post.metadata.get("name", skill_id),
                    description=post.metadata.get("description", ""),
                    argument_hint=post.metadata.get("argument-hint", ""),
                    content=post.content,
                )
            except Exception:
                pass  # skip malformed files; errors are silent at startup

    def get(self, skill_id: str) -> Optional[SkillRecord]:
        return self._skills.get(skill_id)

    def all(self) -> dict[str, SkillRecord]:
        return dict(self._skills)


class AgentRegistry:
    """Loads all *.agent.md files from a directory into an id-keyed dict."""

    def __init__(self, agents_dir: Path) -> None:
        self._agents: dict[str, AgentRecord] = {}
        self._load(agents_dir)

    def _load(self, agents_dir: Path) -> None:
        for path in sorted(agents_dir.glob("*.agent.md")):
            try:
                post = frontmatter.load(str(path))
                agent_id: str = post.metadata.get("id", "")
                if not agent_id:
                    continue
                self._agents[agent_id] = AgentRecord(
                    id=agent_id,
                    name=post.metadata.get("name", agent_id),
                    description=post.metadata.get("description", ""),
                    triggers=post.metadata.get("triggers", []),
                    skills=post.metadata.get("skills", []),
                    tools=post.metadata.get("tools", []),
                    prompt=path.read_text(encoding="utf-8").strip(),
                )
            except Exception:
                pass  # skip malformed files; errors are silent at startup

    def get(self, agent_id: str) -> Optional[AgentRecord]:
        return self._agents.get(agent_id)

    def match_trigger(self, user_input: str) -> Optional[AgentRecord]:
        """Return the first agent whose trigger pattern matches *user_input*."""
        for agent in self._agents.values():
            for pattern in agent.triggers:
                if re.search(pattern, user_input, re.IGNORECASE):
                    return agent
        return None

    def all(self) -> dict[str, AgentRecord]:
        return dict(self._agents)


class TeamRegistry:
    """Loads all *.team.md files from a directory into an id-keyed dict."""

    _DEFAULT_MODEL = "claude-sonnet-4.5"
    _VALID_MODES = {"autonomous", "human_touch"}

    def __init__(
        self,
        teams_dir: Path,
        agent_registry: Optional[AgentRegistry] = None,
    ) -> None:
        self._teams: dict[str, TeamRecord] = {}
        self._agent_registry = agent_registry
        self._load(teams_dir)

    def _load(self, teams_dir: Path) -> None:
        if not teams_dir.exists():
            return
        for path in sorted(teams_dir.glob("*.team.md")):
            try:
                post = frontmatter.load(str(path))
                team_id: str = post.metadata.get("id", "")
                if not team_id:
                    continue
                mode = post.metadata.get("default_execution_mode", "autonomous")
                if mode not in self._VALID_MODES:
                    mode = "autonomous"
                allowed = [
                    str(a) for a in (post.metadata.get("allowed_agents") or []) if a
                ]
                self._teams[team_id] = TeamRecord(
                    id=team_id,
                    name=post.metadata.get("name", team_id),
                    description=post.metadata.get("description", ""),
                    owner=post.metadata.get("owner", ""),
                    default_model=post.metadata.get("default_model", self._DEFAULT_MODEL),
                    default_execution_mode=mode,  # type: ignore[arg-type]
                    default_approval_policy=[
                        str(p) for p in (post.metadata.get("default_approval_policy") or []) if p
                    ],
                    allowed_agents=allowed,
                    jira_project_key=post.metadata.get("jira_project_key"),
                    confluence_space_key=post.metadata.get("confluence_space_key"),
                    guidance=post.content.strip(),
                )
            except Exception:
                pass  # skip malformed files; errors are silent at startup

    def get(self, team_id: str) -> Optional[TeamRecord]:
        return self._teams.get(team_id)

    def all(self) -> dict[str, TeamRecord]:
        return dict(self._teams)

    def unknown_allowed_agents(self, team_id: str) -> list[str]:
        """Return agent ids in allowed_agents that aren't in the agent registry.

        Used by /teams to surface manifest typos without failing startup.
        """
        team = self._teams.get(team_id)
        if team is None or self._agent_registry is None:
            return []
        known = set(self._agent_registry.all().keys())
        return [a for a in team.allowed_agents if a not in known]
