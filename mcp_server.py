#!/usr/bin/env python3
"""MCP server exposing auto-content-poster tools to Claude and other MCP clients."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from src.niches.niche_config import NICHE_PROFILES
from config.settings import PLATFORMS, NICHES

server = Server("auto-content-poster")

PLATFORM_LIST = ["twitter", "instagram", "facebook", "telegram", "tiktok", "youtube"]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="generate_post",
            description=(
                "Generate a social media post for a specific niche and platform using Claude AI."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "niche": {
                        "type": "string",
                        "description": (
                            f"Content niche. Available: {', '.join(NICHE_PROFILES.keys())}"
                        ),
                    },
                    "platform": {
                        "type": "string",
                        "description": (
                            f"Target platform. Available: {', '.join(PLATFORM_LIST)}"
                        ),
                    },
                },
                "required": ["niche", "platform"],
            },
        ),
        types.Tool(
            name="generate_all_platforms",
            description="Generate posts for all active platforms for a given niche.",
            inputSchema={
                "type": "object",
                "properties": {
                    "niche": {
                        "type": "string",
                        "description": (
                            f"Content niche. Available: {', '.join(NICHE_PROFILES.keys())}"
                        ),
                    },
                },
                "required": ["niche"],
            },
        ),
        types.Tool(
            name="list_niches",
            description="List all available content niches with their topics and tone.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="list_platforms",
            description="List all platforms and their enabled/disabled status.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="post_now",
            description=(
                "Trigger an immediate posting cycle across all active platforms."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "niche": {
                        "type": "string",
                        "description": (
                            "Optional niche override. If omitted, a random niche is used."
                        ),
                    },
                },
            },
        ),
        types.Tool(
            name="clean_logs",
            description="Delete log files older than a given number of days.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Remove logs older than this many days (default: 7).",
                        "default": 7,
                    },
                },
            },
        ),
        types.Tool(
            name="get_post_history",
            description=(
                "Return recent post history with pixelated thumbnail paths and metadata. "
                "Use this to review what was posted and study performance."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "How many days back to look (default: 7).",
                        "default": 7,
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "generate_post":
        from src.content_generator.generator import generate_post
        post = generate_post(arguments["niche"], arguments["platform"])
        result = (
            f"Platform: {post['platform']}\n"
            f"Niche:    {post['niche']}\n"
            f"Topic:    {post['topic']}\n\n"
            f"{post['text']}"
        )
        return [types.TextContent(type="text", text=result)]

    elif name == "generate_all_platforms":
        from src.content_generator.generator import generate_all_platforms
        active = [p for p, on in PLATFORMS.items() if on]
        posts = generate_all_platforms(arguments["niche"], active)
        lines = []
        for p in posts:
            lines.append(f"=== {p['platform'].upper()} ===")
            lines.append(p["text"])
            lines.append("")
        return [types.TextContent(type="text", text="\n".join(lines))]

    elif name == "list_niches":
        lines = []
        for niche, profile in NICHE_PROFILES.items():
            lines.append(f"**{niche}**")
            lines.append(f"  Tone:     {profile['tone']}")
            lines.append(f"  Topics:   {', '.join(profile['topics'])}")
            lines.append(f"  Hashtags: {' '.join(profile['hashtags'])}")
            lines.append("")
        return [types.TextContent(type="text", text="\n".join(lines))]

    elif name == "list_platforms":
        lines = ["Platform status:", ""]
        for platform, enabled in PLATFORMS.items():
            status = "✓ enabled" if enabled else "✗ disabled"
            lines.append(f"  {platform:<12} {status}")
        return [types.TextContent(type="text", text="\n".join(lines))]

    elif name == "post_now":
        import src.scheduler.runner as runner_mod
        niche = arguments.get("niche")
        if niche:
            _original = runner_mod.random.choice
            runner_mod.random.choice = lambda _: niche
            try:
                runner_mod.run_posting_cycle()
            finally:
                runner_mod.random.choice = _original
        else:
            runner_mod.run_posting_cycle()
        return [types.TextContent(type="text", text="Posting cycle complete.")]

    elif name == "clean_logs":
        from src.cleaner import clean_logs
        days = arguments.get("days", 7)
        removed = clean_logs(days)
        return [
            types.TextContent(
                type="text",
                text=f"Removed {removed} log file(s) older than {days} day(s).",
            )
        ]

    elif name == "get_post_history":
        from src.post_logger import get_recent_posts
        days  = arguments.get("days", 7)
        posts = get_recent_posts(days)
        if not posts:
            return [types.TextContent(type="text", text=f"No posts found in the last {days} day(s).")]
        lines = [f"Found {len(posts)} post(s) in the last {days} day(s):\n"]
        for p in posts:
            ts      = (p.get("timestamp") or "")[:16].replace("T", " ")
            m       = p.get("metrics", {})
            metrics = (
                f"likes={m.get('likes')}  comments={m.get('comments')}  "
                f"shares={m.get('shares')}  reach={m.get('reach')}"
            )
            lines.append(
                f"[{ts}] {p.get('platform')} · {p.get('niche')}\n"
                f"  Topic:     {p.get('topic')}\n"
                f"  Thumbnail: {p.get('image_path')}\n"
                f"  Metrics:   {metrics}\n"
                f"  Text:      {(p.get('text') or '')[:80]}…\n"
            )
        return [types.TextContent(type="text", text="\n".join(lines))]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
