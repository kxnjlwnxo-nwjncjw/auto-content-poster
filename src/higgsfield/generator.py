"""
High-level Higgsfield asset generation for YouTube queue items.

Generates three asset types for each content item:
  - intro      : 5-second cinematic opening video
  - thumbnail  : 1280×720 JPEG image
  - scenes     : N × 5-second b-roll / filler video clips

Assets are stored under data/higgsfield/{content_id}/.
All functions return local file paths.

When HIGGSFIELD_API_KEY is absent the client uses MOCK MODE which writes
placeholder files instantly — the full pipeline still works for testing.
"""
from __future__ import annotations
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.higgsfield.client import HiggsFieldClient
from config.settings import HIGGSFIELD_API_KEY, HIGGSFIELD_SCENES_COUNT

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "higgsfield"


def _client() -> HiggsFieldClient:
    return HiggsFieldClient(api_key=HIGGSFIELD_API_KEY)


def _asset_dir(content_id: str) -> Path:
    p = DATA_DIR / content_id
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── Public generators ──────────────────────────────────────────────────────────

def generate_intro(content_id: str, title: str) -> str:
    """Generate a cinematic 5-second intro video. Returns local path."""
    client = _client()
    dest   = str(_asset_dir(content_id) / "intro.mp4")
    prompt = (
        f"Cinematic YouTube intro animation for a video titled '{title}'. "
        "Bold motion graphics, dramatic camera push-in, dynamic lighting, "
        "professional broadcast quality, 5 seconds, 16:9."
    )
    if client.mock:
        return client.mock_video_marker(dest, f"Intro: {title}")

    job_id = client.create_video_job(prompt, duration=5, aspect_ratio="16:9", style="cinematic")
    job    = client.wait_for_job(job_id)
    return client.download(job["output_url"], dest)


def generate_thumbnail(content_id: str, title: str) -> str:
    """Generate a YouTube thumbnail image. Returns local path."""
    client = _client()
    dest   = str(_asset_dir(content_id) / "thumbnail.jpg")
    prompt = (
        f"YouTube thumbnail for video titled '{title}'. "
        "Bold vibrant colours, high contrast, clear space for title text overlay, "
        "eye-catching composition, professional quality, 1280x720."
    )
    if client.mock:
        return client.mock_thumbnail(dest, title)

    job_id = client.create_image_job(prompt, width=1280, height=720)
    job    = client.wait_for_job(job_id)
    return client.download(job["output_url"], dest)


def generate_scenes(content_id: str, title: str, count: Optional[int] = None) -> list[str]:
    """Generate b-roll scene videos. Returns list of local paths."""
    client  = _client()
    n       = count if count is not None else HIGGSFIELD_SCENES_COUNT
    paths   = []

    scene_prompts = [
        (
            f"Cinematic b-roll scene {i + 1} of {n} for YouTube video titled '{title}'. "
            "Smooth camera movement, relevant visual content, professional cinematography, "
            "dynamic and engaging, 5 seconds, 16:9."
        )
        for i in range(n)
    ]

    if client.mock:
        for i, prompt in enumerate(scene_prompts):
            dest = str(_asset_dir(content_id) / f"scene_{i + 1:03d}.mp4")
            paths.append(client.mock_video_marker(dest, f"Scene {i + 1}: {title}"))
        return paths

    # Submit all scene jobs in parallel
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = {
            pool.submit(client.create_video_job, prompt, 5, "16:9", "cinematic"): i
            for i, prompt in enumerate(scene_prompts)
        }
        job_ids = {}
        for fut in as_completed(futures):
            job_ids[futures[fut]] = fut.result()

    # Wait and download (ordered by index)
    with ThreadPoolExecutor(max_workers=n) as pool:
        def _fetch(i_job):
            idx, jid = i_job
            job  = client.wait_for_job(jid)
            dest = str(_asset_dir(content_id) / f"scene_{idx + 1:03d}.mp4")
            return idx, client.download(job["output_url"], dest)

        results = list(pool.map(_fetch, sorted(job_ids.items())))

    return [path for _, path in sorted(results)]


def generate_all_assets(content_id: str, title: str) -> dict:
    """
    Generate intro, thumbnail, and scenes concurrently.
    Returns dict with keys: intro_path, thumbnail_path, scenes_paths.
    Raises on any generation failure.
    """
    with ThreadPoolExecutor(max_workers=3) as pool:
        intro_f  = pool.submit(generate_intro,     content_id, title)
        thumb_f  = pool.submit(generate_thumbnail, content_id, title)
        scenes_f = pool.submit(generate_scenes,    content_id, title)
        intro_path   = intro_f.result()
        thumb_path   = thumb_f.result()
        scene_paths  = scenes_f.result()

    return {
        "intro_path":     intro_path,
        "thumbnail_path": thumb_path,
        "scenes_paths":   scene_paths,
    }


# ── Video assembly ─────────────────────────────────────────────────────────────

def _ffmpeg_bin() -> str:
    """Return path to ffmpeg binary, checking ~/bin as fallback."""
    import shutil
    from pathlib import Path
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    local = str(Path.home() / "bin" / "ffmpeg")
    if Path(local).exists():
        return local
    return "ffmpeg"


def ffmpeg_available() -> bool:
    try:
        subprocess.run([_ffmpeg_bin(), "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def assemble_video(
    content_id:       str,
    intro_path:       Optional[str],
    scene_paths:      list,
    main_video_path:  Optional[str] = None,
) -> str:
    """
    Concatenate intro + main (optional) + scenes using ffmpeg.
    Returns path to the assembled video, or raises if ffmpeg is unavailable.

    Clip order: intro → main (if given) → scenes
    """
    if not ffmpeg_available():
        raise RuntimeError(
            "ffmpeg is not installed. Install it with: brew install ffmpeg\n"
            "The assembled video cannot be created without ffmpeg."
        )

    clips = []
    if intro_path and Path(intro_path).exists():
        clips.append(intro_path)
    if main_video_path and Path(main_video_path).exists():
        clips.append(main_video_path)
    for sp in (scene_paths or []):
        if sp and Path(sp).exists():
            clips.append(sp)

    if not clips:
        raise ValueError("No valid clips found to assemble.")

    out_dir  = DATA_DIR / content_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(out_dir / "assembled.mp4")

    if len(clips) == 1:
        import shutil
        shutil.copy(clips[0], out_path)
        return out_path

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fh:
        for clip in clips:
            fh.write(f"file '{clip}'\n")
        list_path = fh.name

    try:
        result = subprocess.run(
            [_ffmpeg_bin(), "-y", "-f", "concat", "-safe", "0",
             "-i", list_path, "-c", "copy", out_path],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error:\n{result.stderr[-2000:]}")
    finally:
        Path(list_path).unlink(missing_ok=True)

    return out_path
