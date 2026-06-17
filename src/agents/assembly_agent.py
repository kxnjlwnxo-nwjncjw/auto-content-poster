"""
Assembly Agent — auto-assembles approved Higgsfield assets into a final video.

Runs every 60s. For each queue item where:
  - All per-asset approvals are True  (intro + thumbnail + scenes)
  - assembled_video_path is not yet set
It calls assemble_video() (ffmpeg concat) and writes the path back to the queue.
The item then becomes postable by the PosterAgent.

Requires ffmpeg installed (brew install ffmpeg). Silently skips if not available.
"""
from __future__ import annotations
import threading
from rich.console import Console
from src.agents.base import Agent
from src.youtube.queue import list_content, all_assets_approved, set_assembled_video

console = Console()

_assembling: set[str] = set()
_lock = threading.Lock()


class AssemblyAgent(Agent):
    name = "assembly-agent"
    interval_seconds = 60

    def tick(self) -> None:
        from src.higgsfield.generator import ffmpeg_available
        if not ffmpeg_available():
            return  # silently wait — logs shown at startup

        items = list_content(status="pending_review")
        for item in items:
            cid = item["id"]
            if item.get("assembled_video_path"):
                continue
            if item.get("higgsfield_status") != "pending_review":
                continue
            if not all_assets_approved(cid):
                continue
            with _lock:
                if cid in _assembling:
                    continue
                _assembling.add(cid)
            t = threading.Thread(
                target=_run_assembly,
                args=(cid, item),
                daemon=True,
                name=f"assemble-{cid[:8]}",
            )
            t.start()
            console.print(f"[cyan]assembly-agent:[/cyan] assembling '{item['title'][:50]}'")


def _run_assembly(content_id: str, item: dict) -> None:
    try:
        from src.higgsfield.generator import assemble_video
        intro = item.get("intro_path")
        scenes = item.get("scenes_paths") or []
        main_vid = item.get("video_path")
        assembled_path = assemble_video(content_id, intro, scenes, main_vid)
        set_assembled_video(content_id, assembled_path)
        console.print(
            f"[green]assembly-agent:[/green] assembled '{item['title'][:40]}' → {assembled_path}"
        )
    except Exception as exc:
        console.print(f"[red]assembly-agent: failed for {content_id[:8]}: {exc}[/red]")
    finally:
        with _lock:
            _assembling.discard(content_id)
