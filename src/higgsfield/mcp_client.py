"""
Higgsfield AI MCP client — stateless JSON-RPC over HTTPS.

Auth: Bearer token from higgsfield.ai/mcp → copy "MCP Token"
Set HIGGSFIELD_MCP_TOKEN in .env.

Models used:
  video : kling3_0_turbo  (text-to-video, fast, 16:9, 3-15s)
  image : soul_cinematic   (cinema-grade stills, best for thumbnails)
"""
from __future__ import annotations
import json
import os
import re
import time
import urllib.request
from pathlib import Path

MCP_URL = "https://mcp.higgsfield.ai/mcp"
_POLL_INTERVAL = 12   # seconds between job_status polls
_TIMEOUT = 600        # 10 min max wait

VIDEO_MODEL = os.getenv("HIGGSFIELD_VIDEO_MODEL", "kling3_0_turbo")
IMAGE_MODEL = os.getenv("HIGGSFIELD_IMAGE_MODEL", "soul_cinematic")
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


class HiggsFieldMCPClient:
    def __init__(self, token: str):
        self.token = token

    # ── Core RPC ───────────────────────────────────────────────────────────────

    def _call(self, method: str, params: dict) -> dict:
        """Stateless JSON-RPC call. Returns the 'result' dict."""
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }).encode()
        req = urllib.request.Request(
            MCP_URL,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            for line in resp:
                line = line.decode().strip()
                if line.startswith("data:"):
                    obj = json.loads(line[5:])
                    if "result" in obj:
                        return obj["result"]
                    if "error" in obj:
                        raise RuntimeError(f"Higgsfield MCP error: {obj['error']}")
        raise RuntimeError("No result received from Higgsfield MCP")

    def tool_call(self, name: str, arguments: dict) -> dict:
        return self._call("tools/call", {"name": name, "arguments": arguments})

    # ── Job submission ─────────────────────────────────────────────────────────

    def generate_video(self, prompt: str, duration: int = 5, aspect_ratio: str = "16:9") -> str:
        """Submit a text-to-video job. Returns job_id UUID."""
        result = self.tool_call("generate_video", {
            "params": {
                "model": VIDEO_MODEL,
                "prompt": prompt,
                "duration": duration,
                "aspect_ratio": aspect_ratio,
            }
        })
        return self._extract_job_id(result)

    def generate_image(self, prompt: str, aspect_ratio: str = "16:9") -> str:
        """Submit a text-to-image job. Returns job_id UUID."""
        result = self.tool_call("generate_image", {
            "params": {
                "model": IMAGE_MODEL,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
            }
        })
        return self._extract_job_id(result)

    def _extract_job_id(self, result: dict) -> str:
        """Pull job UUID from any response shape Higgsfield might return."""
        sc = result.get("structuredContent", {})
        # Try common field names
        for key in ("jobId", "job_id", "id", "generationId"):
            val = sc.get(key)
            if val and _UUID_RE.match(str(val)):
                return str(val)
        # Fall back: scan text content for a UUID
        for block in result.get("content", []):
            if block.get("type") == "text":
                match = _UUID_RE.search(block["text"])
                if match:
                    return match.group()
        raise RuntimeError(f"No job ID found in response: {result}")

    # ── Polling ────────────────────────────────────────────────────────────────

    def wait_for_job(self, job_id: str) -> dict:
        """
        Poll job_status until complete (uses sync=True for server-side waiting).
        Returns structured content dict with output URL.
        """
        deadline = time.time() + _TIMEOUT
        while time.time() < deadline:
            result = self.tool_call("job_status", {"jobId": job_id, "sync": True})
            sc = result.get("structuredContent", {})
            status = (sc.get("status") or "").lower()

            if status in ("completed", "succeeded", "done", "success"):
                return sc
            if status in ("failed", "error", "cancelled"):
                err = sc.get("error") or sc.get("message") or "unknown error"
                raise RuntimeError(f"Job {job_id} failed: {err}")
            # sync=True blocks ~25s server-side, so we poll slowly
            time.sleep(_POLL_INTERVAL)

        raise TimeoutError(f"Job {job_id} timed out after {_TIMEOUT}s")

    def get_output_url(self, job_result: dict) -> str:
        """Extract the download URL from a completed job result."""
        # Try common shapes
        for key in ("url", "output_url", "outputUrl", "videoUrl", "imageUrl"):
            url = job_result.get(key)
            if url:
                return url
        # Try nested generations array
        gens = job_result.get("generations") or job_result.get("outputs") or []
        if gens and isinstance(gens, list):
            first = gens[0]
            for key in ("url", "output_url", "videoUrl", "imageUrl"):
                url = first.get(key)
                if url:
                    return url
        raise RuntimeError(f"No output URL found in job result: {job_result}")

    # ── Download ───────────────────────────────────────────────────────────────

    def download(self, url: str, dest: str) -> str:
        """Download a generated asset to dest path. Returns dest."""
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(dest, "wb") as fh:
                while chunk := resp.read(65536):
                    fh.write(chunk)
        return dest
