"""
Higgsfield AI REST client.

API docs: https://docs.higgsfield.ai
Base URL:  https://api.higgsfield.ai/v1

All generation calls are async on Higgsfield's side:
  1. POST /generation/video  (or /generation/image)  → { "id": "gen_xxx", "status": "queued" }
  2. GET  /generation/{id}                            → { "status": "processing"|"completed"|"failed",
                                                          "output_url": "https://..." }

Set HIGGSFIELD_API_KEY in .env to use the real API.
When the key is absent the client runs in MOCK MODE and writes placeholder files locally.
"""
from __future__ import annotations
import os
import time
import uuid
import requests
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw


BASE_URL = "https://api.higgsfield.ai/v1"
_POLL_INTERVAL = 8   # seconds between status checks
_TIMEOUT       = 600  # seconds before giving up on a job


class HiggsFieldClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key  = api_key
        self.mock     = not bool(api_key)
        self._session = requests.Session()
        if api_key:
            self._session.headers.update({
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            })

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _post(self, endpoint: str, payload: dict) -> dict:
        resp = self._session.post(f"{BASE_URL}{endpoint}", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _get(self, endpoint: str) -> dict:
        resp = self._session.get(f"{BASE_URL}{endpoint}", timeout=30)
        resp.raise_for_status()
        return resp.json()

    # ── Job submission ─────────────────────────────────────────────────────────

    def create_video_job(
        self,
        prompt: str,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        style: str = "cinematic",
    ) -> str:
        """Submit a text-to-video job. Returns job ID."""
        if self.mock:
            return f"mock_video_{uuid.uuid4().hex[:8]}"
        data = self._post("/generation/video", {
            "prompt":       prompt,
            "duration":     duration,
            "aspect_ratio": aspect_ratio,
            "style":        style,
        })
        return data["id"]

    def create_image_job(
        self,
        prompt: str,
        width:  int = 1280,
        height: int = 720,
    ) -> str:
        """Submit a text-to-image job. Returns job ID."""
        if self.mock:
            return f"mock_image_{uuid.uuid4().hex[:8]}"
        data = self._post("/generation/image", {
            "prompt": prompt,
            "width":  width,
            "height": height,
        })
        return data["id"]

    # ── Polling ────────────────────────────────────────────────────────────────

    def get_job(self, job_id: str) -> dict:
        if self.mock:
            return {"id": job_id, "status": "completed", "output_url": None}
        return self._get(f"/generation/{job_id}")

    def wait_for_job(self, job_id: str) -> dict:
        """Block until job completes or times out. Returns the completed job dict."""
        if self.mock:
            return {"id": job_id, "status": "completed", "output_url": None}
        deadline = time.time() + _TIMEOUT
        while time.time() < deadline:
            job = self.get_job(job_id)
            status = job.get("status", "")
            if status == "completed":
                return job
            if status in ("failed", "error"):
                raise RuntimeError(f"Higgsfield job {job_id} failed: {job.get('error', 'unknown')}")
            time.sleep(_POLL_INTERVAL)
        raise TimeoutError(f"Higgsfield job {job_id} timed out after {_TIMEOUT}s")

    # ── Download ───────────────────────────────────────────────────────────────

    def download(self, url: str, dest_path: str) -> str:
        """Download a remote file to dest_path. Returns dest_path."""
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        with open(dest_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                fh.write(chunk)
        return dest_path

    # ── Mock asset writers ─────────────────────────────────────────────────────

    def mock_thumbnail(self, dest_path: str, label: str = "AI Thumbnail") -> str:
        """Write a placeholder thumbnail PNG when running in mock mode."""
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        img  = Image.new("RGB", (1280, 720), color=(20, 20, 40))
        draw = ImageDraw.Draw(img)
        # Bold coloured border
        for i in range(6):
            draw.rectangle([i, i, 1279 - i, 719 - i], outline=(220, 50, 50))
        # Label
        draw.text((40, 280), "HIGGSFIELD", fill=(220, 50, 50))
        draw.text((40, 340), label[:60], fill=(255, 255, 255))
        draw.text((40, 400), "[MOCK — add HIGGSFIELD_API_KEY]", fill=(120, 120, 120))
        img.save(dest_path, "JPEG", quality=90)
        return dest_path

    def mock_video_marker(self, dest_path: str, label: str = "AI Video") -> str:
        """Write a tiny text marker file in place of a real video in mock mode."""
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_text(
            f"[HIGGSFIELD MOCK]\n{label}\nAdd HIGGSFIELD_API_KEY to .env to generate real video.\n"
        )
        return dest_path
