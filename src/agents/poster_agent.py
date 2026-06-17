"""
Poster Agent — proper Agent subclass that posts approved content to YouTube.

Replaces the raw daemon thread in auto_poster.py with a full Agent so it shows
in the coordinator status table and can be restarted on crash.

Every 60s it checks for approved items whose scheduled_time has passed and
posts them to YouTube via Composio v3 or the YouTube Data API fallback.
"""
from __future__ import annotations
from rich.console import Console
from src.agents.base import Agent

console = Console()


class PosterAgent(Agent):
    name = "poster-agent"
    interval_seconds = 60

    def tick(self) -> None:
        from src.youtube.queue import get_due_approved, mark_posted
        from src.youtube.poster import post_to_youtube
        from src.youtube.notifier import notify_posted, notify_post_failed

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
