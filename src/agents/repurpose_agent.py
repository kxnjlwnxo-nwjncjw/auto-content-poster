"""
Repurpose Agent — converts assembled 16:9 YouTube videos into 9:16 short-form clips
for TikTok and Instagram Reels.

Every 120s it scans for items with assembled_video_path set but no reels_path.
Uses ffmpeg to:
  1. Crop + scale 16:9 → 9:16 (1080x1920)
  2. Trim to 60s max (YouTube Shorts / Reels limit)
  3. Burn subtitles if SRT exists

Output saved to data/reels/{content_id}_reels.mp4.
Posting to TikTok/Instagram is a future step (add TIKTOK_SESSION_ID / Instagram creds).
"""
from __future__ import annotations
import subprocess
import threading
from pathlib import Path
from rich.console import Console
from src.agents.base import Agent

console = Console()

REELS_DIR = Path(__file__).parent.parent.parent / "data" / "reels"
SRT_DIR   = Path(__file__).parent.parent.parent / "data" / "srt"
MAX_DURATION = 60

_processing: set[str] = set()
_lock = threading.Lock()


class RepurposeAgent(Agent):
    name = "repurpose-agent"
    interval_seconds = 120

    def tick(self) -> None:
        from src.higgsfield.generator import ffmpeg_available
        if not ffmpeg_available():
            return

        from src.youtube.queue import list_content
        items = list_content(status="pending_review") + list_content(status="approved") + list_content(status="posted")

        for item in items:
            cid = item["id"]
            if item.get("reels_path"):
                continue
            video = item.get("assembled_video_path")
            if not video or not Path(video).exists():
                continue
            with _lock:
                if cid in _processing:
                    continue
                _processing.add(cid)
            threading.Thread(
                target=_make_reels,
                args=(cid, item),
                daemon=True,
                name=f"reels-{cid[:8]}",
            ).start()


def _make_reels(content_id: str, item: dict) -> None:
    try:
        from src.higgsfield.generator import _ffmpeg_bin
        REELS_DIR.mkdir(parents=True, exist_ok=True)

        video_in = item["assembled_video_path"]
        out_path = str(REELS_DIR / f"{content_id}_reels.mp4")
        srt_path = SRT_DIR / f"{content_id}.srt"

        # Build ffmpeg filter: crop centre 9:16, scale to 1080x1920, trim to 60s
        # For 16:9 source: crop width = height * 9/16
        vf = "crop=ih*9/16:ih,scale=1080:1920:flags=lanczos"
        if srt_path.exists():
            vf += f",subtitles='{srt_path}':force_style='FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2'"

        cmd = [
            _ffmpeg_bin(), "-y",
            "-i", video_in,
            "-t", str(MAX_DURATION),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            out_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-1000:])

        from src.youtube.queue import update_draft
        update_draft(content_id, reels_path=out_path)
        console.print(f"[green]repurpose-agent:[/green] reels ready for '{item['title'][:50]}'")

    except Exception as exc:
        console.print(f"[red]repurpose-agent: failed for {content_id[:8]}: {exc}[/red]")
    finally:
        with _lock:
            _processing.discard(content_id)
