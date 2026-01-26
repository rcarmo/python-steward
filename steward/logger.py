"""Human and JSON logging helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console
from rich.theme import Theme


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
        self.log_path = Path(log_json_path) if enable_file_logs and log_json_path else Path(
            log_json_path or ".steward-log.jsonl"
        )
        self.enable_human_logs = enable_human_logs
        self.enable_file_logs = enable_file_logs
        self.pretty = pretty
        self.compact = compact
        self.console = Console(theme=_theme(), highlight=False) if pretty else None

    def start_spinner(self):
        if not self.pretty or not self.enable_human_logs:
            return lambda: None
        status = self.console.status("waiting", spinner="dots") if self.console else None
        if status:
            status.start()
            return status.stop
        return lambda: None

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
        """Compact single-line logging for REPL mode."""
        icon = {
            "error": "✗",
            "warn": "⚠",
            "todo": "☐",
            "model": "→",
            "tool": "•",
        }.get(variant, "·")

        style = {
            "error": "red",
            "warn": "yellow",
            "todo": "magenta",
            "model": "cyan",
            "tool": "green dim",
        }.get(variant, "dim")

        # For model responses, show abbreviated content
        if variant == "model":
            if body:
                if self.console:
                    self.console.print(f"  {icon} {body}", style=style)
                else:
                    print(f"  {icon} {body}")
            return

        # For tools, show just the action
        if variant == "tool":
            # Only show tool name and brief summary
            short = body[:100].replace("\n", " ").strip() if body else ""
            if "=" in short:
                short = short.split("=")[0] + "=..."
            if self.console:
                self.console.print(f"  {icon} {title} {short}", style=style)
            else:
                print(f"  {icon} {title} {short}")
            return

        # For errors/warnings, show full message
        if variant in ("error", "warn"):
            short = body[:150].replace("\n", " ") if body else ""
            if self.console:
                self.console.print(f"  {icon} {title}: {short}", style=style)
            else:
                print(f"  {icon} {title}: {short}")
            return

        # Default: brief format
        if body:
            short = body[:80].replace("\n", " ")
            if self.console:
                self.console.print(f"  {icon} {title}: {short}", style=style)
            else:
                print(f"  {icon} {title}: {short}")

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
            "timestamp": datetime.utcnow().isoformat(),
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
