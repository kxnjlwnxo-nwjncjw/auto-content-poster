"""
Caption Agent — transcribes assembled videos with OpenAI Whisper and burns subtitles in.

Every 120s it picks up items with assembled_video_path but no srt_path.
Whisper runs fully locally (no API key, free). Install once with:
  pip install openai-whisper

Pipeline:
  assembled.mp4 → Whisper → assembled.srt → ffmpeg subtitles filter → assembled_captioned.mp4
"""
from __future__ import annotations
import subprocess
import threading
from pathlib import Path
from rich.console import Console
from src.agents.base import Agent

console = Console()

SRT_DIR = Path(__file__).parent.parent.parent / "data" / "srt"

_processing: set[str] = set()
_lock = threading.Lock()


class CaptionAgent(Agent):
    name = "caption-agent"
    interval_seconds = 120

    def tick(self) -> None:
        if not _whisper_available():
            return
        from src.higgsfield.generator import ffmpeg_available
        if not ffmpeg_available():
            return

        from src.youtube.queue import list_content
        items = list_content(status="pending_review") + list_content(status="approved")

        for item in items:
            cid = item["id"]
            if item.get("srt_path"):
                continue
            video = item.get("assembled_video_path")
            if not video or not Path(video).exists():
                continue
            with _lock:
                if cid in _processing:
                    continue
                _processing.add(cid)
            threading.Thread(
                target=_run_captioning,
                args=(cid, item),
                daemon=True,
                name=f"caption-{cid[:8]}",
            ).start()


def _whisper_available() -> bool:
    try:
        import whisper  # type: ignore
        return True
    except ImportError:
        return False


def _run_captioning(content_id: str, item: dict) -> None:
    try:
        import whisper
        from src.higgsfield.generator import _ffmpeg_bin

        SRT_DIR.mkdir(parents=True, exist_ok=True)
        video_in  = item["assembled_video_path"]
        srt_path  = str(SRT_DIR / f"{content_id}.srt")
        out_path  = str(Path(video_in).parent / "assembled_captioned.mp4")

        # Transcribe with Whisper (tiny model for speed)
        model = whisper.load_model("tiny")
        result = model.transcribe(video_in, fp16=False, word_timestamps=False)

        # Write SRT file
        _write_srt(result["segments"], srt_path)

        # Burn subtitles into video
        style = "FontSize=20,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Alignment=2"
        cmd = [
            _ffmpeg_bin(), "-y",
            "-i", video_in,
            "-vf", f"subtitles='{srt_path}':force_style='{style}'",
            "-c:a", "copy",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            out_path,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-1000:])

        from src.youtube.queue import update_draft, set_assembled_video
        update_draft(content_id, srt_path=srt_path)
        set_assembled_video(content_id, out_path)

        console.print(f"[green]caption-agent:[/green] subtitles burned for '{item['title'][:50]}'")

    except Exception as exc:
        console.print(f"[red]caption-agent: failed for {content_id[:8]}: {exc}[/red]")
    finally:
        with _lock:
            _processing.discard(content_id)


def _write_srt(segments: list, path: str) -> None:
    def fmt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{fmt_time(seg['start'])} --> {fmt_time(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
