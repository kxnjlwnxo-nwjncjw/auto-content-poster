"""
Auto-Reviewer Agent — automatically approves pending content so the pipeline keeps flowing.

Two modes (set via env):
  YOUTUBE_AUTO_APPROVE=true           → approve immediately once Higgsfield assets are ready
                                        (or right away if Higgsfield is not configured)
  YOUTUBE_REVIEW_WINDOW_MINUTES=30    → approve anything that has been waiting ≥ N minutes
                                        (default: disabled — requires YOUTUBE_AUTO_APPROVE=true)

If neither is set, this agent runs silently and does nothing (human review only).
"""
from __future__ import annotations
import os
from datetime import datetime, timedelta
from rich.console import Console
from src.agents.base import Agent
from src.youtube.queue import list_content, approve_content

console = Console()

AUTO_APPROVE = os.getenv("YOUTUBE_AUTO_APPROVE", "false").lower() in ("1", "true", "yes")
REVIEW_WINDOW = int(os.getenv("YOUTUBE_REVIEW_WINDOW_MINUTES", "0"))


def _assets_ready(item: dict) -> bool:
    """True if Higgsfield is done or was never started."""
    hf = item.get("higgsfield_status", "idle")
    return hf in ("idle", "ready")


def _old_enough(item: dict) -> bool:
    """True if the item has been pending review for ≥ REVIEW_WINDOW minutes."""
    if REVIEW_WINDOW <= 0:
        return False
    submitted = item.get("submitted_at")
    if not submitted:
        return False
    age = datetime.utcnow() - datetime.fromisoformat(submitted)
    return age >= timedelta(minutes=REVIEW_WINDOW)


class AutoReviewerAgent(Agent):
    name = "auto-reviewer"
    interval_seconds = 300  # check every 5 minutes

    def tick(self) -> None:
        if not AUTO_APPROVE and REVIEW_WINDOW <= 0:
            return  # nothing to do — human review only

        pending = list_content(status="pending_review")
        if not pending:
            return

        approved_count = 0
        for item in pending:
            should_approve = (
                (AUTO_APPROVE and _assets_ready(item))
                or _old_enough(item)
            )
            if should_approve:
                updated = approve_content(item["id"])
                if updated and updated["status"] == "approved":
                    approved_count += 1
                    console.print(
                        f"[green]auto-reviewer:[/green] approved '{item['title']}' ({item['id'][:8]})"
                    )
                    _append_posted_json(updated)

        if approved_count:
            console.print(f"[dim]auto-reviewer: approved {approved_count} item(s)[/dim]")


def _append_posted_json(item: dict) -> None:
    """Update content JSON file to reflect approved status."""
    from pathlib import Path
    import json

    created = (item.get("created_at") or datetime.utcnow().isoformat())[:10]
    year_month = created[:7]
    content_dir = Path(__file__).parent.parent.parent / "content" / year_month
    # Find existing file for this content ID
    if content_dir.exists():
        for f in content_dir.glob(f"*{item['id'][:8]}*.json"):
            try:
                data = json.loads(f.read_text())
                data["status"] = "approved"
                data["reviewed_at"] = item.get("reviewed_at", "")
                f.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            except Exception:
                pass
