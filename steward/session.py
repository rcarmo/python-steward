"""Session management for Steward."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Default session directory
DEFAULT_SESSION_DIR = Path.home() / ".steward" / "sessions"


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())


def get_session_dir(session_id: str, base_dir: Optional[Path] = None) -> Path:
    """Get the directory for a session."""
    base = base_dir or DEFAULT_SESSION_DIR
    return base / session_id


def init_session(session_id: Optional[str] = None, base_dir: Optional[Path] = None) -> Dict:
    """Initialize a new session or load existing one."""
    sid = session_id or generate_session_id()
    session_dir = get_session_dir(sid, base_dir)
    session_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (session_dir / "checkpoints").mkdir(exist_ok=True)
    (session_dir / "files").mkdir(exist_ok=True)

    # Load or create session state
    state_file = session_dir / "state.json"
    if state_file.exists():
        state = json.loads(state_file.read_text(encoding="utf8"))
    else:
        state = {
            "session_id": sid,
            "created": _utc_now_iso(),
            "checkpoints": [],
            "plan_file": str(session_dir / "plan.md"),
        }
        state_file.write_text(json.dumps(state, indent=2), encoding="utf8")

    return state


def save_checkpoint(
    session_id: str,
    title: str,
    description: str,
    files_changed: Optional[List[str]] = None,
    base_dir: Optional[Path] = None,
) -> str:
    """Save a checkpoint for the session."""
    session_dir = get_session_dir(session_id, base_dir)
    state_file = session_dir / "state.json"

    if not state_file.exists():
        raise ValueError(f"Session {session_id} not found")

    state = json.loads(state_file.read_text(encoding="utf8"))
    checkpoint_num = len(state["checkpoints"]) + 1
    checkpoint_id = f"{checkpoint_num:03d}-{_slugify(title)}"

    checkpoint = {
        "id": checkpoint_id,
        "title": title,
        "description": description,
        "timestamp": _utc_now_iso(),
        "files_changed": files_changed or [],
    }

    # Write checkpoint file
    checkpoint_file = session_dir / "checkpoints" / f"{checkpoint_id}.md"
    checkpoint_content = f"""# {title}

**Timestamp:** {checkpoint["timestamp"]}

## Description
{description}

## Files Changed
{_format_files_list(files_changed or [])}
"""
    checkpoint_file.write_text(checkpoint_content, encoding="utf8")

    # Update checkpoint index
    index_file = session_dir / "checkpoints" / "index.md"
    index_content = "# Checkpoints\n\n"
    state["checkpoints"].append(checkpoint)
    for cp in state["checkpoints"]:
        index_content += f"- [{cp['id']}]({cp['id']}.md) - {cp['title']}\n"
    index_file.write_text(index_content, encoding="utf8")

    # Save state
    state_file.write_text(json.dumps(state, indent=2), encoding="utf8")

    return checkpoint_id


def get_session_context(session_id: str, base_dir: Optional[Path] = None) -> str:
    """Get session context for system prompt injection."""
    session_dir = get_session_dir(session_id, base_dir)
    state_file = session_dir / "state.json"

    if not state_file.exists():
        return ""

    state = json.loads(state_file.read_text(encoding="utf8"))
    plan_file = Path(state.get("plan_file", session_dir / "plan.md"))

    lines = [
        "<session_context>",
        f"Session folder: {session_dir}",
        f"Plan file: {plan_file}  {'(exists)' if plan_file.exists() else '(not yet created)'}",
        "",
        "Contents:",
        f"- checkpoints/: {len(state.get('checkpoints', []))} prior checkpoints (index.md has full list)",
        "- files/: Persistent storage for session artifacts",
    ]

    # Add checkpoint summaries
    checkpoints = state.get("checkpoints", [])
    if checkpoints:
        lines.append("")
        lines.append("Checkpoints (read those relevant to your current task):")
        for cp in checkpoints[-5:]:  # Last 5 checkpoints
            lines.append(f"  {cp['id']}.md - {cp['title']}")

    lines.append("")
    lines.append("Checkpoint titles indicate what was accomplished. Read relevant checkpoints for prior history.")
    lines.append("")
    lines.append("For complex tasks, create plan.md at the session folder root before implementing.")
    lines.append("files/ persists across checkpoints for artifacts that shouldn't be committed.")
    lines.append("")
    lines.append("Memories: use list_memories to review stored facts before new exploration.")
    lines.append("</session_context>")

    return "\n".join(lines)


def get_plan_content(session_id: str, base_dir: Optional[Path] = None) -> Optional[str]:
    """Get the current plan content if it exists."""
    session_dir = get_session_dir(session_id, base_dir)
    plan_file = session_dir / "plan.md"

    if plan_file.exists():
        return plan_file.read_text(encoding="utf8")
    return None


def save_plan(session_id: str, content: str, base_dir: Optional[Path] = None) -> str:
    """Save the plan file."""
    session_dir = get_session_dir(session_id, base_dir)
    plan_file = session_dir / "plan.md"
    plan_file.write_text(content, encoding="utf8")
    return str(plan_file)


def list_sessions(base_dir: Optional[Path] = None) -> List[Dict]:
    """List all sessions."""
    base = base_dir or DEFAULT_SESSION_DIR
    if not base.exists():
        return []

    sessions = []
    for session_dir in base.iterdir():
        if session_dir.is_dir():
            state_file = session_dir / "state.json"
            if state_file.exists():
                state = json.loads(state_file.read_text(encoding="utf8"))
                sessions.append(
                    {
                        "session_id": state.get("session_id"),
                        "created": state.get("created"),
                        "checkpoints": len(state.get("checkpoints", [])),
                    }
                )

    return sorted(sessions, key=lambda x: x.get("created", ""), reverse=True)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    slug = text.lower().replace(" ", "-")
    return "".join(c for c in slug if c.isalnum() or c == "-")[:40]


def _format_files_list(files: List[str]) -> str:
    if not files:
        return "(none)"
    return "\n".join(f"- `{f}`" for f in files)
