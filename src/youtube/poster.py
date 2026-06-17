"""Post approved content to YouTube via Composio v3 API (with YouTube Data API fallback)."""
from __future__ import annotations
import json
import os
import urllib.request
import urllib.parse
from rich.console import Console

console = Console()

COMPOSIO_MCP_URL = "https://connect.composio.dev/mcp"
CONNECTED_ACCOUNT_ID = "ca_hrz2i9PX3rtf"


def post_to_youtube(content: dict) -> tuple[bool, str, str]:
    """
    Post content to YouTube.

    Returns (success, youtube_video_id_or_error, youtube_url).
    Tries Composio MCP first, falls back to YouTube Data API.
    """
    mcp_token = os.getenv("COMPOSIO_MCP_TOKEN")
    if mcp_token:
        return _post_via_composio_mcp(content, mcp_token)
    return _post_via_youtube_api(content)


def _mcp_call(token: str, method: str, params: dict) -> dict:
    """Make a single JSON-RPC call to the Composio MCP server."""
    session_id = _mcp_init(token)
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 2,
        "method": method,
        "params": params,
    }).encode()
    req = urllib.request.Request(
        COMPOSIO_MCP_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-03-26",
            "Mcp-Session-Id": session_id,
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        for line in resp:
            line = line.decode().strip()
            if line.startswith("data:"):
                obj = json.loads(line[5:])
                if "result" in obj:
                    content_blocks = obj["result"].get("content", [])
                    for block in content_blocks:
                        if block.get("type") == "text":
                            return json.loads(block["text"])
    return {}


def _mcp_init(token: str) -> str:
    """Initialize MCP session and return session ID."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "auto-content-poster", "version": "1.0"},
        },
    }).encode()
    req = urllib.request.Request(
        COMPOSIO_MCP_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-03-26",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.headers.get("Mcp-Session-Id", "")


def _post_via_composio_mcp(content: dict, token: str) -> tuple[bool, str, str]:
    """Upload video to YouTube via Composio MCP COMPOSIO_MULTI_EXECUTE_TOOL."""
    video_path = content.get("assembled_video_path") or content.get("video_path")
    if not video_path or not os.path.exists(str(video_path)):
        return False, "no valid video file to upload", ""

    try:
        result = _mcp_call(token, "tools/call", {
            "name": "COMPOSIO_MULTI_EXECUTE_TOOL",
            "arguments": {
                "connected_account_id": CONNECTED_ACCOUNT_ID,
                "tool_slug": "YOUTUBE_UPLOAD_VIDEO",
                "input_params": {
                    "title": content["title"],
                    "description": content.get("description", ""),
                    "tags": content.get("tags") or [],
                    "categoryId": content.get("category_id", "22"),
                    "privacyStatus": content.get("privacy_status", "public"),
                    "videoPath": video_path,
                },
            },
        })

        data = result.get("data", {})
        if not result.get("successful", False):
            err = result.get("error") or str(data)
            console.print(f"[yellow]Composio MCP upload failed: {err}. Falling back to YouTube API.[/yellow]")
            return _post_via_youtube_api(content)

        video_id = (
            data.get("id")
            or data.get("videoId")
            or data.get("video_id", "")
        )
        yt_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
        console.print(f"[green]Composio MCP upload success → {yt_url or 'posted'}[/green]")
        return True, video_id, yt_url

    except Exception as exc:
        console.print(f"[yellow]Composio MCP error: {exc}. Falling back to YouTube API.[/yellow]")
        return _post_via_youtube_api(content)


def _post_via_youtube_api(content: dict) -> tuple[bool, str, str]:
    """Direct YouTube Data API v3 upload using OAuth2 credentials."""
    try:
        from googleapiclient.discovery import build  # type: ignore
        from googleapiclient.http import MediaFileUpload  # type: ignore
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore
        import pickle

        scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        creds_file = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "config/youtube_client_secret.json")
        token_file = os.getenv("YOUTUBE_TOKEN_FILE", "data/youtube_token.pickle")

        creds = None
        if os.path.exists(token_file):
            with open(token_file, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(creds_file):
                    msg = (
                        f"YouTube credentials not found at {creds_file}. "
                        "Set COMPOSIO_MCP_TOKEN or provide youtube_client_secret.json."
                    )
                    console.print(f"[red]{msg}[/red]")
                    return False, msg, ""
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, scopes)
                creds = flow.run_local_server(port=0)
            with open(token_file, "wb") as f:
                pickle.dump(creds, f)

        youtube = build("youtube", "v3", credentials=creds)

        video_path = content.get("assembled_video_path") or content.get("video_path")
        if not video_path:
            return False, "video_path required for direct YouTube API upload", ""

        body = {
            "snippet": {
                "title": content["title"],
                "description": content.get("description", ""),
                "tags": content.get("tags") or [],
                "categoryId": content.get("category_id", "22"),
            },
            "status": {"privacyStatus": content.get("privacy_status", "public")},
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = request.execute()

        video_id = response.get("id", "")
        yt_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
        console.print(f"[green]YouTube API upload success → {yt_url}[/green]")
        return True, video_id, yt_url

    except Exception as exc:
        console.print(f"[red]YouTube API upload error: {exc}[/red]")
        return False, str(exc), ""
