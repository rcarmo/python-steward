"""Skill registry for auto-discovery, matching, and chaining."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from .tools.load_skill import SkillMetadata, parse_skill

# Directories to skip during skill discovery
IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build", ".steward"}


class SkillRegistry:
    """Registry for discovered skills with matching and chaining support."""

    def __init__(self) -> None:
        self._skills: Dict[str, List[SkillMetadata]] = {}
        self._discovered = False

    def discover(self, root: Optional[Path] = None, max_depth: int = 5) -> int:
        """Discover all SKILL.md files in the workspace. Returns count of skills found."""
        root = root or Path.cwd()
        self._skills.clear()

        def search(directory: Path, depth: int = 0) -> None:
            if depth > max_depth:
                return
            try:
                for entry in directory.iterdir():
                    if entry.name in IGNORED_DIRS:
                        continue
                    if entry.name.startswith(".") and entry.name != ".":
                        continue
                    if entry.is_file() and entry.name.lower() == "skill.md":
                        try:
                            content = entry.read_text(encoding="utf8")
                            rel = entry.relative_to(root)
                            skill = parse_skill(content, str(rel))
                            self._skills.setdefault(skill.name, []).append(skill)
                        except (OSError, IOError):
                            pass
                    elif entry.is_dir():
                        search(entry, depth + 1)
            except PermissionError:
                pass

        search(root)
        self._discovered = True
        return len(self._skills)

    def get(self, name: str) -> Optional[SkillMetadata]:
        """Get a skill by name (returns first match if duplicates exist)."""
        skills = self._skills.get(name, [])
        return skills[0] if skills else None

    def get_all_by_name(self, name: str) -> List[SkillMetadata]:
        """Get all skills with the given name."""
        return list(self._skills.get(name, []))

    def all(self) -> List[SkillMetadata]:
        """Get all discovered skills."""
        results: List[SkillMetadata] = []
        for skills in self._skills.values():
            results.extend(skills)
        return results

    def match(self, query: str, limit: int = 5) -> List[tuple[SkillMetadata, float]]:
        """Match skills against a query. Returns list of (skill, score) tuples."""
        if not self._skills:
            return []

        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))
        results: List[tuple[SkillMetadata, float]] = []

        for skill in self.all():
            score = self._score_match(skill, query_lower, query_words)
            if score > 0:
                results.append((skill, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def _score_match(self, skill: SkillMetadata, query_lower: str, query_words: Set[str]) -> float:
        """Score how well a skill matches the query."""
        score = 0.0

        # Exact name match
        if skill.name.lower() == query_lower:
            score += 10.0
        elif skill.name.lower() in query_lower or query_lower in skill.name.lower():
            score += 5.0

        # Trigger keyword matches (high weight)
        for trigger in skill.triggers:
            trigger_lower = trigger.lower()
            if trigger_lower in query_lower:
                score += 3.0
            elif any(word in trigger_lower or trigger_lower in word for word in query_words):
                score += 1.5

        # Description word overlap
        desc_words = set(re.findall(r'\w+', skill.description.lower()))
        overlap = query_words & desc_words
        score += len(overlap) * 0.5

        # Partial word matches in description
        for word in query_words:
            if len(word) >= 4 and word in skill.description.lower():
                score += 0.3

        return score

    def get_chain(self, skill_name: str) -> List[SkillMetadata]:
        """Get the chain of skills that should follow the given skill."""
        skill = self.get(skill_name)
        if not skill:
            return []

        chain_skills: List[SkillMetadata] = []
        for chain_name in skill.chain:
            chain_skills.extend(self.get_all_by_name(chain_name))

        return chain_skills

    def get_dependencies(self, skill_name: str) -> List[SkillMetadata]:
        """Get skills that the given skill requires."""
        skill = self.get(skill_name)
        if not skill:
            return []

        deps: List[SkillMetadata] = []
        for req_name in skill.requires:
            deps.extend(self.get_all_by_name(req_name))

        return deps

    def get_dependents(self, skill_name: str) -> List[SkillMetadata]:
        """Get skills that require the given skill."""
        dependents: List[SkillMetadata] = []
        for skill in self.all():
            if skill_name in skill.requires:
                dependents.append(skill)
        return dependents

    def build_execution_order(self, skill_name: str) -> List[SkillMetadata]:
        """Build ordered list of skills to execute, respecting dependencies."""
        skill = self.get(skill_name)
        if not skill:
            return []

        visited: Set[str] = set()
        visiting: Set[str] = set()
        order: List[SkillMetadata] = []

        def visit(s: SkillMetadata) -> None:
            if s.name in visited:
                return
            if s.name in visiting:
                return
            visiting.add(s.name)

            # First, visit dependencies
            for dep in self.get_dependencies(s.name):
                visit(dep)

            order.append(s)
            visited.add(s.name)
            visiting.remove(s.name)

            # Then, visit chain
            for chain_skill in self.get_chain(s.name):
                visit(chain_skill)

        visit(skill)
        return order

    def format_suggestions(self, matches: List[tuple[SkillMetadata, float]]) -> str:
        """Format skill matches for display."""
        if not matches:
            return "No matching skills found."

        lines = [f"Found {len(matches)} relevant skill(s):\n"]
        for skill, score in matches:
            lines.append(f"**{skill.name}** (relevance: {score:.1f})")
            lines.append(f"  Path: {skill.path}")
            if skill.description:
                desc = skill.description[:150] + "..." if len(skill.description) > 150 else skill.description
                lines.append(f"  {desc}")
            if skill.requires:
                lines.append(f"  Requires: {', '.join(skill.requires)}")
            if skill.chain:
                lines.append(f"  Chains to: {', '.join(skill.chain)}")
            lines.append("")

        lines.append("Use load_skill to read full details.")
        return "\n".join(lines)

    @property
    def is_discovered(self) -> bool:
        return self._discovered


# Global registry instance
_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    """Get the global skill registry, creating if needed."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (mainly for testing)."""
    global _registry
    _registry = None
