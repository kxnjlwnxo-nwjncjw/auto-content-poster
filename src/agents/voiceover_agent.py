"""
Voiceover Agent — generates AI voiceover from the video script and merges it with
the assembled video using ffmpeg.

Requires ELEVENLABS_API_KEY in .env. Without it, runs in mock mode (silent video).

Every 60s it scans for items where:
  - assembled_video_path exists
  - script file exists at data/scripts/{id}.json
  - voiceover_path is not yet set
It calls ElevenLabs TTS, saves the MP3, then ffmpeg-merges audio into the video.
"""
from __future__ import annotations
import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from rich.console import Console
from src.agents.base import Agent

console = Console()

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "data" / "scripts"
AUDIO_DIR   = Path(__file__).parent.parent.parent / "data" / "audio"

_processing: set[str] = set()
_lock = threading.Lock()


class VoiceoverAgent(Agent):
    name = "voiceover-agent"
    interval_seconds = 60

    def tick(self) -> None:
        from src.youtube.queue import list_content

        api_key = os.getenv("ELEVENLABS_API_KEY", "")
        items = list_content(status="pending_review") + list_content(status="approved")

        for item in items:
            cid = item["id"]
            if item.get("voiceover_path"):
                continue
            if not item.get("assembled_video_path") and not item.get("intro_path"):
                continue
            script_file = SCRIPTS_DIR / f"{cid}.json"
            if not script_file.exists():
                continue
            with _lock:
                if cid in _processing:
                    continue
                _processing.add(cid)
            threading.Thread(
                target=_run_voiceover,
                args=(cid, item, script_file, api_key),
                daemon=True,
                name=f"vo-{cid[:8]}",
            ).start()


def _build_voiceover_text(script: dict) -> str:
    """Flatten script JSON into a single narration string."""
    parts = []
    if script.get("intro_hook"):
        parts.append(script["intro_hook"])
    for ch in script.get("chapters", []):
        if ch.get("script"):
            parts.append(ch["script"])
    if script.get("outro"):
        parts.append(script["outro"])
    return "\n\n".join(parts)


def _run_voiceover(content_id: str, item: dict, script_file: Path, api_key: str) -> None:
    try:
        script = json.loads(script_file.read_text())
        text   = _build_voiceover_text(script)
        if not text.strip():
            return

        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        mp3_path = str(AUDIO_DIR / f"{content_id}.mp3")

        if api_key:
            _tts_elevenlabs(text, mp3_path, api_key)
        else:
            _tts_mock(mp3_path)

        # Merge audio into assembled video if it exists
        video_in  = item.get("assembled_video_path") or item.get("intro_path", "")
        if video_in and Path(video_in).exists():
            video_out = str(Path(video_in).parent / "assembled_voiced.mp4")
            _merge_audio(video_in, mp3_path, video_out)
        else:
            video_out = ""

        # Persist paths
        from src.youtube.queue import update_draft
        update_draft(content_id, voiceover_path=mp3_path)
        if video_out and Path(video_out).exists():
            from src.youtube.queue import set_assembled_video
            set_assembled_video(content_id, video_out)

        console.print(f"[green]voiceover-agent:[/green] audio ready for '{item['title'][:50]}'")
    except Exception as exc:
        console.print(f"[red]voiceover-agent: failed for {content_id[:8]}: {exc}[/red]")
    finally:
        with _lock:
            _processing.discard(content_id)


def _tts_elevenlabs(text: str, dest: str, api_key: str) -> None:
    import urllib.request
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")  # default: Sarah
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = json.dumps({
        "text": text[:4500],  # API limit
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    })
    with urllib.request.urlopen(req, timeout=120) as resp:
        Path(dest).write_bytes(resp.read())


def _tts_mock(dest: str) -> None:
    """Write a 1-second silent MP3 placeholder."""
    # Minimal valid MP3 header (silent frame)
    silent = bytes([
        0xFF, 0xFB, 0x90, 0x00,
        *([0x00] * 413),
    ])
    Path(dest).write_bytes(silent * 10)


def _merge_audio(video: str, audio: str, out: str) -> None:
    from src.higgsfield.generator import _ffmpeg_bin
    subprocess.run([
        _ffmpeg_bin(), "-y",
        "-i", video,
        "-i", audio,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        out,
    ], check=True, capture_output=True, timeout=300)
