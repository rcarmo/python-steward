"""Human and JSON logging helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console
from rich.theme import Theme

# Tools whose output should persist on screen (not transient)
PERSISTENT_TOOLS = {
    "report_intent",  # Intent should always be visible
    "create",  # File creation
    "edit",  # File editing
    "replace_string_in_file",
    "multi_replace_string_in_file",
    "apply_patch",
    "git_commit",  # Important git operations
    "git_stash",
}


@dataclass
class HumanEntry:
    title: Optional[str] = None
    body: Optional[str] = None
    variant: str = "info"


class Logger:
    def __init__(
        self,
        provider: str,
        model: str,
        log_json_path: Optional[str] = None,
        enable_human_logs: bool = True,
        enable_file_logs: bool = True,
        pretty: bool = True,
        compact: bool = False,
    ) -> None:
        self.provider = provider
        self.model = model
        self.log_path = Path(log_json_path if log_json_path else ".steward-log.jsonl")
        self.enable_human_logs = enable_human_logs
        self.enable_file_logs = enable_file_logs
        self.pretty = pretty
        self.compact = compact
        self.console = Console(theme=_theme(), highlight=False) if pretty else None
        self._last_transient_lines = 0  # Track transient output for clearing

    def start_spinner(self, message: str = "waiting"):
        if not self.pretty or not self.enable_human_logs:
            return lambda: None
        status = self.console.status(message, spinner="dots") if self.console else None
        if status:
            status.start()
            return status.stop
        return lambda: None

    def supports_spinner(self) -> bool:
        return bool(self.pretty and self.enable_human_logs and self.console)

    def _clear_transient(self) -> None:
        """Clear previous transient output."""
        if self._last_transient_lines > 0 and self.console:
            # Move up and clear each transient line
            for _ in range(self._last_transient_lines):
                self.console.print("\033[A\033[2K", end="")
            self._last_transient_lines = 0

    def human(self, entry: HumanEntry) -> None:
        if not self.enable_human_logs:
            return
        title = entry.title or "info"
        body = entry.body or ""
        variant = entry.variant or "info"

        if self.compact:
            self._human_compact(title, body, variant)
        elif self.console:
            self._human_pretty(title, body, variant)
        else:
            print(f"{title}: {body}")

    def _human_compact(self, title: str, body: str, variant: str) -> None:
        """Compact single-line logging for REPL mode.

        Persistent output: intents, file operations, errors stay on screen.
        Transient output: other tool calls appear briefly then get cleared.
        """
        icon = {
            "error": "✗",
            "warn": "⚠",
            "todo": "☐",
            "model": "→",
            "tool": "•",
            "intent": "◈",
            "file": "✎",
        }.get(variant, "·")

        style = {
            "error": "red",
            "warn": "yellow",
            "todo": "magenta",
            "model": "cyan",
            "tool": "dim",
            "intent": "blue bold",
            "file": "green",
        }.get(variant, "dim")

        # Determine if this output should persist or be transient
        is_persistent = variant in ("error", "warn", "intent", "file") or title in PERSISTENT_TOOLS

        # Clear previous transient output before printing persistent
        if is_persistent:
            self._clear_transient()

        # For model step indicators, these are transient
        if variant == "model":
            if body:
                # Clear previous transient, print new transient
                self._clear_transient()
                if self.console:
                    self.console.print(f"  {icon} {body}", style=style)
                else:
                    print(f"  {icon} {body}")
                self._last_transient_lines = 1
            return

        # Intent is always persistent and prominent
        if title == "report_intent":
            if self.console:
                # Extract just the intent text if it starts with "Intent: "
                intent_text = body.replace("Intent: ", "") if body.startswith("Intent: ") else body
                self.console.print(f"  ◈ {intent_text}", style="blue bold")
            else:
                print(f"  ◈ {body}")
            return

        # File operations are persistent
        if title in PERSISTENT_TOOLS:
            short = body[:100].replace("\n", " ").strip() if body else ""
            if self.console:
                self.console.print(f"  ✎ {title}: {short}", style="green")
            else:
                print(f"  ✎ {title}: {short}")
            return

        # For errors/warnings, show full message (persistent)
        if variant in ("error", "warn"):
            short = body[:150].replace("\n", " ") if body else ""
            if self.console:
                self.console.print(f"  {icon} {title}: {short}", style=style)
            else:
                print(f"  {icon} {title}: {short}")
            return

        # Other tools are transient - clear previous, print, track for clearing
        self._clear_transient()
        short = body[:80].replace("\n", " ").strip() if body else ""
        if "=" in short:
            short = short.split("=")[0] + "=..."
        if self.console:
            self.console.print(f"  {icon} {title} {short}", style=style)
        else:
            print(f"  {icon} {title} {short}")
        self._last_transient_lines = 1

    def _human_pretty(self, title: str, body: str, variant: str) -> None:
        """Full pretty logging with boxes/colors."""
        style = {
            "error": "red",
            "warn": "yellow",
            "todo": "magenta",
            "model": "cyan",
            "tool": "green",
        }.get(variant, "cyan")
        prefix = {
            "error": "[error]",
            "warn": "[warn]",
            "todo": "[todo]",
            "model": "[model]",
            "tool": "[tool]",
        }.get(variant, "[info]")
        self.console.print(f"{prefix} {title}")
        if body:
            self.console.print(f"{body}", style=style)

    def json(self, entry: Dict[str, Any]) -> None:
        if not self.enable_file_logs:
            return
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": self.provider,
            "model": self.model,
            **entry,
        }
        try:
            with self.log_path.open("a", encoding="utf8") as fh:
                fh.write(json.dumps(payload))
                fh.write("\n")
        except OSError:
            if self.console:
                self.console.print("log write failed", style="red")


def _theme() -> Theme:
    return Theme(
        {
            "info": "cyan",
            "warn": "yellow",
            "error": "red",
            "todo": "magenta",
            "model": "cyan",
            "tool": "green",
        }
    )
