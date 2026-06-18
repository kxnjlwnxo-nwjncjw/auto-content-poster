"""
Analytics Agent — polls YouTube every 24h for views, likes, and CTR on posted videos.

Uses the Composio MCP YouTube connection (no extra API key needed).
Stores results in data/analytics/{content_id}.json and logs underperforming titles
so the content agent can avoid similar topics.

Low performer threshold: < 100 views after 48h.
"""
from __future__ import annotations
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from rich.console import Console
from src.agents.base import Agent

console = Console()

ANALYTICS_DIR = Path(__file__).parent.parent.parent / "data" / "analytics"
COMPOSIO_MCP_URL = "https://connect.composio.dev/mcp"
LOW_VIEW_THRESHOLD = 100
CHECK_AFTER_HOURS  = 48


class AnalyticsAgent(Agent):
    name = "analytics-agent"
    interval_seconds = 3600  # check every hour, skip items not due yet

    def tick(self) -> None:
        from src.youtube.queue import list_content

        token = os.getenv("COMPOSIO_MCP_TOKEN", "")
        if not token:
            return

        posted = list_content(status="posted")
        for item in posted:
            if not item.get("youtube_video_id"):
                continue
            analytics_file = ANALYTICS_DIR / f"{item['id']}.json"

            # Skip if checked recently (within 23h)
            if analytics_file.exists():
                data = json.loads(analytics_file.read_text())
                last = datetime.fromisoformat(data.get("last_checked", "2000-01-01"))
                if datetime.utcnow() - last < timedelta(hours=23):
                    continue

            try:
                stats = _fetch_video_stats(token, item["youtube_video_id"])
                _save_analytics(item, stats, analytics_file)
                _log_if_underperforming(item, stats)
            except Exception as exc:
                console.print(f"[dim]analytics-agent: skip {item['id'][:8]}: {exc}[/dim]")


def _mcp_session(token: str) -> str:
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "analytics-agent", "version": "1.0"}},
    }).encode()
    req = urllib.request.Request(COMPOSIO_MCP_URL, data=payload, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-03-26",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.headers.get("Mcp-Session-Id", "")


def _mcp_tool(token: str, session: str, tool: str, args: dict) -> dict:
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    }).encode()
    req = urllib.request.Request(COMPOSIO_MCP_URL, data=payload, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-03-26",
        "Mcp-Session-Id": session,
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        for line in r:
            line = line.decode().strip()
            if line.startswith("data:"):
                obj = json.loads(line[5:])
                for block in obj.get("result", {}).get("content", []):
                    if block.get("type") == "text":
                        return json.loads(block["text"])
    return {}


def _fetch_video_stats(token: str, video_id: str) -> dict:
    session = _mcp_session(token)
    result  = _mcp_tool(token, session, "COMPOSIO_MULTI_EXECUTE_TOOL", {
        "connected_account_id": "ca_hrz2i9PX3rtf",
        "tool_slug": "YOUTUBE_GET_VIDEO_DETAILS_BATCH",
        "input_params": {"videoIds": video_id, "part": "statistics,snippet"},
    })
    items = result.get("data", {}).get("items", [])
    if not items:
        return {}
    stats = items[0].get("statistics", {})
    return {
        "views":    int(stats.get("viewCount", 0)),
        "likes":    int(stats.get("likeCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
    }


def _save_analytics(item: dict, stats: dict, path: Path) -> None:
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if path.exists():
        existing = json.loads(path.read_text())

    history = existing.get("history", [])
    history.append({**stats, "checked_at": datetime.utcnow().isoformat()})

    data = {
        "content_id":   item["id"],
        "title":        item["title"],
        "video_id":     item["youtube_video_id"],
        "youtube_url":  item.get("youtube_url", ""),
        "posted_at":    item.get("posted_at", ""),
        "last_checked": datetime.utcnow().isoformat(),
        "latest":       stats,
        "history":      history[-30:],
    }
    path.write_text(json.dumps(data, indent=2))
    console.print(
        f"[dim]analytics-agent:[/dim] '{item['title'][:40]}' — "
        f"views={stats.get('views',0)} likes={stats.get('likes',0)}"
    )


def _log_if_underperforming(item: dict, stats: dict) -> None:
    posted_at = item.get("posted_at")
    if not posted_at:
        return
    age_hours = (datetime.utcnow() - datetime.fromisoformat(posted_at)).total_seconds() / 3600
    if age_hours < CHECK_AFTER_HOURS:
        return
    if stats.get("views", 0) < LOW_VIEW_THRESHOLD:
        log_path = Path(__file__).parent.parent.parent / "data" / "analytics" / "low_performers.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "title": item["title"],
                "views": stats.get("views", 0),
                "age_hours": round(age_hours, 1),
                "logged_at": datetime.utcnow().isoformat(),
            }) + "\n")
        console.print(f"[yellow]analytics-agent: low performer logged — '{item['title'][:50]}'[/yellow]")
