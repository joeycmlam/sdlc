"""
Agent and Skill registries.

Loaded at startup by scanning:
  - skills/*.skill.md   → SkillRegistry
  - agents/*.agent.md   → AgentRegistry

Each file must have YAML frontmatter with at minimum an ``id`` field.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

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
