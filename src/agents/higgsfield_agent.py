"""
Higgsfield Agent — auto-triggers AI asset generation for newly submitted queue items.

Runs every 30s. Picks up any item with:
  - status = 'pending_review'
  - higgsfield_status = 'idle' or 'failed'
and starts the full generation pipeline in a background thread.

Includes exponential backoff: retries up to 3x (delays: 30s, 60s, 120s) before
marking the item permanently failed.
"""
from __future__ import annotations
import threading
import time
from rich.console import Console
from src.agents.base import Agent
from src.youtube.queue import list_content, set_higgsfield_status, set_higgsfield_assets

console = Console()

_generating: set[str] = set()
_lock = threading.Lock()
MAX_RETRIES = 3


class HiggsFieldAgent(Agent):
    name = "higgsfield-agent"
    interval_seconds = 30

    def tick(self) -> None:
        items = list_content(status="pending_review")
        for item in items:
            cid = item["id"]
            hf_status = item.get("higgsfield_status", "idle")
            if hf_status not in ("idle", "failed"):
                continue
            # Don't retry if already exceeded max attempts
            attempt = item.get("higgsfield_retry_count", 0)
            if hf_status == "failed" and attempt >= MAX_RETRIES:
                continue
            with _lock:
                if cid in _generating:
                    continue
                _generating.add(cid)
            t = threading.Thread(
                target=_run_generation_with_backoff,
                args=(cid, item["title"], attempt),
                daemon=True,
                name=f"hf-gen-{cid[:8]}",
            )
            t.start()
            console.print(f"[cyan]higgsfield-agent:[/cyan] started generation for '{item['title'][:50]}' (attempt {attempt + 1}/{MAX_RETRIES})")


def _run_generation_with_backoff(content_id: str, title: str, attempt: int) -> None:
    try:
        set_higgsfield_status(content_id, "generating")
        from src.higgsfield.generator import generate_all_assets
        assets = generate_all_assets(content_id, title)
        set_higgsfield_assets(
            content_id,
            assets["intro_path"],
            assets["thumbnail_path"],
            assets["scenes_paths"],
        )
        console.print(f"[green]higgsfield-agent:[/green] assets ready for '{title[:50]}'")
    except Exception as exc:
        next_attempt = attempt + 1
        if next_attempt < MAX_RETRIES:
            delay = 30 * (2 ** attempt)  # 30s, 60s, 120s
            console.print(
                f"[yellow]higgsfield-agent: attempt {next_attempt}/{MAX_RETRIES} failed for "
                f"{content_id[:8]}: {exc}. Retrying in {delay}s[/yellow]"
            )
            # Store retry count in error field temporarily, reset to idle for next pick-up
            set_higgsfield_status(content_id, "idle", f"retry:{next_attempt}:{exc}")
            time.sleep(delay)
            # Re-trigger immediately after delay
            with _lock:
                _generating.discard(content_id)
            _run_generation_with_backoff(content_id, title, next_attempt)
            return
        else:
            set_higgsfield_status(content_id, "failed", str(exc))
            console.print(f"[red]higgsfield-agent: all {MAX_RETRIES} attempts failed for {content_id[:8]}: {exc}[/red]")
    finally:
        with _lock:
            _generating.discard(content_id)
