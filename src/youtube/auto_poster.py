"""Background thread that auto-posts approved content when its scheduled time arrives."""
from __future__ import annotations
import threading
import time
from typing import Optional
from rich.console import Console
from src.youtube.queue import get_due_approved, mark_posted
from src.youtube.poster import post_to_youtube
from src.youtube.notifier import notify_posted, notify_post_failed

console = Console()

_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None

CHECK_INTERVAL_SECONDS = 60


def _run_loop() -> None:
    console.print("[dim cyan]YouTube auto-poster started (checking every 60s)[/dim cyan]")
    while not _stop_event.is_set():
        try:
            due = get_due_approved()
            for content in due:
                console.print(f"[cyan]Auto-posting: {content['title']}[/cyan]")
                success, video_id, yt_url = post_to_youtube(content)
                if success:
                    mark_posted(content["id"], video_id, yt_url)
                    notify_posted(content["title"], yt_url)
                    console.print(f"[green]✓ Posted: {yt_url or video_id}[/green]")
                else:
                    notify_post_failed(content["title"], video_id)
                    console.print(f"[red]✗ Failed to post '{content['title']}': {video_id}[/red]")
        except Exception as exc:
            console.print(f"[red]Auto-poster loop error: {exc}[/red]")

        _stop_event.wait(CHECK_INTERVAL_SECONDS)


def start_auto_poster() -> threading.Thread:
    global _thread, _stop_event
    _stop_event = threading.Event()
    _thread = threading.Thread(target=_run_loop, daemon=True, name="yt-auto-poster")
    _thread.start()
    return _thread


def stop_auto_poster() -> None:
    _stop_event.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=5)
