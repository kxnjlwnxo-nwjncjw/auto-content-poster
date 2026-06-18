"""
Poster Agent — posts approved content to YouTube at the optimal time.

Smarter scheduling: reads data/analytics/*.json to find the hour-of-day
that historically gets the most views for this channel, then only posts
during that ±1 hour window. Falls back to immediate posting if no analytics yet.

Runs every 60s. Posts approved items whose scheduled_time has passed (or immediately
if no schedule is set and the optimal window is now).
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from rich.console import Console
from src.agents.base import Agent

console = Console()

ANALYTICS_DIR = Path(__file__).parent.parent.parent / "data" / "analytics"


def _best_posting_hour() -> int | None:
    """
    Return the UTC hour (0-23) with the most average views, or None if not enough data.
    Requires at least 3 posted videos with analytics to make a recommendation.
    """
    files = list(ANALYTICS_DIR.glob("*.json"))
    if len(files) < 3:
        return None

    hour_views: dict[int, list[int]] = defaultdict(list)
    for f in files:
        if f.name == "low_performers.jsonl":
            continue
        try:
            data = json.loads(f.read_text())
            posted_at = data.get("posted_at", "")
            views     = data.get("latest", {}).get("views", 0)
            if posted_at and views > 0:
                hour = datetime.fromisoformat(posted_at).hour
                hour_views[hour].append(views)
        except Exception:
            pass

    if not hour_views:
        return None

    return max(hour_views, key=lambda h: sum(hour_views[h]) / len(hour_views[h]))


def _in_optimal_window() -> bool:
    """True if now is within ±1 hour of the best posting time (or no data yet)."""
    best = _best_posting_hour()
    if best is None:
        return True  # no data → post whenever approved
    current_hour = datetime.now(timezone.utc).hour
    return current_hour in {(best - 1) % 24, best, (best + 1) % 24}


class PosterAgent(Agent):
    name = "poster-agent"
    interval_seconds = 60

    def tick(self) -> None:
        from src.youtube.queue import get_due_approved, mark_posted
        from src.youtube.poster import post_to_youtube
        from src.youtube.notifier import notify_posted, notify_post_failed

        if not _in_optimal_window():
            best = _best_posting_hour()
            console.print(f"[dim]poster-agent: outside optimal posting window (best hour: {best:02d}:00 UTC)[/dim]")
            return

        due = get_due_approved()
        for content in due:
            title = content["title"]
            console.print(f"[cyan]poster-agent:[/cyan] posting '{title[:60]}'")
            success, video_id, yt_url = post_to_youtube(content)
            if success:
                mark_posted(content["id"], video_id, yt_url)
                notify_posted(title, yt_url)
                console.print(f"[green]poster-agent:[/green] posted → {yt_url or video_id}")
            else:
                notify_post_failed(title, video_id)
                console.print(f"[red]poster-agent: failed '{title[:50]}': {video_id}[/red]")
