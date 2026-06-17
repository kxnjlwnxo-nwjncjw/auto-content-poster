"""
Git Agent — commits new content files and pushes to origin on a schedule.

Every GIT_AGENT_INTERVAL_MINUTES (default: 10) it:
  1. Checks for uncommitted changes in the content/ directory
  2. Stages and commits them with a descriptive message
  3. Pushes to origin (branch: main or whatever is configured)

Set GIT_AUTO_PUSH=false to commit locally only (no push).
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from datetime import datetime
from rich.console import Console
from src.agents.base import Agent

console = Console()

REPO_ROOT = Path(__file__).parent.parent.parent
GIT_AUTO_PUSH = os.getenv("GIT_AUTO_PUSH", "true").lower() not in ("0", "false", "no")
GIT_BRANCH = os.getenv("GIT_BRANCH", "main")


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=check,
    )


def has_uncommitted_content() -> bool:
    """True if anything under content/ or src/ is new or modified."""
    result = _run(["git", "status", "--porcelain"], check=False)
    for line in result.stdout.splitlines():
        path = line[3:].strip()
        if path.startswith("content/") or path.startswith("src/"):
            return True
    return False


def commit_and_push(message: str | None = None) -> bool:
    """
    Stage all content/ and src/ changes, commit, and optionally push.
    Returns True on success.
    """
    try:
        # Stage content JSON files and any new source files
        _run(["git", "add", "content/", "src/", "config/", "requirements.txt"], check=False)

        # Check if there's actually something staged
        diff = _run(["git", "diff", "--cached", "--stat"], check=False)
        if not diff.stdout.strip():
            return True  # nothing to commit

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        commit_msg = message or f"content: auto-generate batch [{now}]"

        _run(["git", "commit", "-m", commit_msg])
        console.print(f"[green]git-agent:[/green] committed — {commit_msg}")

        if GIT_AUTO_PUSH:
            _run(["git", "push", "origin", GIT_BRANCH])
            console.print(f"[green]git-agent:[/green] pushed to origin/{GIT_BRANCH}")

        return True

    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        console.print(f"[red]git-agent error: {stderr}[/red]")
        return False


class GitAgent(Agent):
    name = "git-agent"

    def __init__(self, interval_minutes: int = 10):
        super().__init__()
        self.interval_seconds = interval_minutes * 60

    def tick(self) -> None:
        if not has_uncommitted_content():
            return
        commit_and_push()

    @staticmethod
    def from_env() -> "GitAgent":
        interval = int(os.getenv("GIT_AGENT_INTERVAL_MINUTES", "10"))
        return GitAgent(interval_minutes=interval)
