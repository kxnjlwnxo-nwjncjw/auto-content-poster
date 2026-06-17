#!/usr/bin/env python3
"""
Auto Content Poster
AI-powered multi-platform social media content generator and scheduler.
"""
import argparse
from rich.console import Console

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Auto Content Poster")
    subparsers = parser.add_subparsers(dest="command")

    # ── YouTube review workflow ────────────────────────────────────────────────
    yt = subparsers.add_parser("youtube", help="YouTube content queue & review dashboard")
    yt_sub = yt.add_subparsers(dest="yt_command")

    yt_sub.add_parser("dashboard", help="Open the review dashboard (http://localhost:8080)")

    yt_draft = yt_sub.add_parser("draft", help="Add a new video draft to the queue")
    yt_draft.add_argument("--title", required=True, help="Video title")
    yt_draft.add_argument("--description", default="", help="Video description")
    yt_draft.add_argument("--video-path", default="", help="Path to local video file")
    yt_draft.add_argument("--video-url", default="", help="Remote video URL")
    yt_draft.add_argument("--thumbnail-path", default="", help="Path to local thumbnail")
    yt_draft.add_argument("--thumbnail-url", default="", help="Remote thumbnail URL")
    yt_draft.add_argument("--tags", default="", help="Comma-separated tags")
    yt_draft.add_argument("--scheduled", default=None, help="Schedule time (ISO 8601 or YYYY-MM-DD HH:MM)")
    yt_draft.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])

    yt_list = yt_sub.add_parser("list", help="List queued content")
    yt_list.add_argument("--status", default=None, help="Filter by status (draft|pending_review|approved|posted|rejected)")

    yt_submit = yt_sub.add_parser("submit", help="Submit a draft for review")
    yt_submit.add_argument("id", help="Content ID (or prefix)")

    yt_post = yt_sub.add_parser("post", help="Post an approved item to YouTube immediately")
    yt_post.add_argument("id", help="Content ID (or prefix)")

    yt_sub.add_parser("auth", help="Authenticate with YouTube Data API (OAuth flow)")

    # ── Multi-agent system ────────────────────────────────────────────────────
    ag = subparsers.add_parser("agents", help="Run all background content agents")
    ag_sub = ag.add_subparsers(dest="ag_command")

    ag_sub.add_parser("start", help="Start all agents (content generator, auto-reviewer, git pusher)")
    ag_sub.add_parser("status", help="Show live status of all agents")

    ag_gen = ag_sub.add_parser("generate", help="Run the content agent once right now")
    ag_gen.add_argument("--niche", default=None, help="Force a specific niche")

    # Run the scheduler
    subparsers.add_parser("start", help="Start the posting scheduler")

    # Generate and post once immediately
    p = subparsers.add_parser("post-now", help="Generate and post right now")
    p.add_argument("--niche", default=None, help="Niche to post for (default: random)")

    # Generate content only (preview, no posting)
    p2 = subparsers.add_parser("preview", help="Preview generated content without posting")
    p2.add_argument("--niche", required=True, help="Niche to preview")
    p2.add_argument("--platform", required=True, help="Platform to generate for")

    # Clean old log files
    p3 = subparsers.add_parser("clean", help="Delete log files older than N days")
    p3.add_argument("--days", type=int, default=7, help="Delete logs older than this many days (default: 7)")

    # Browse post history
    p4 = subparsers.add_parser("history", help="Show recent post thumbnails and metadata")
    p4.add_argument("--days", type=int, default=7, help="Look back N days (default: 7)")

    args = parser.parse_args()

    if args.command == "start":
        from src.scheduler.runner import start_scheduler
        start_scheduler()

    elif args.command == "post-now":
        from src.scheduler.runner import run_posting_cycle
        run_posting_cycle()

    elif args.command == "preview":
        from src.content_generator.generator import generate_post
        post = generate_post(args.niche, args.platform)
        console.rule(f"[bold]{args.platform.upper()} — {args.niche}[/bold]")
        console.print(post["text"])

    elif args.command == "clean":
        from src.cleaner import clean_logs
        removed = clean_logs(args.days)
        console.print(f"[green]Removed {removed} log file(s) older than {args.days} day(s).[/green]")

    elif args.command == "youtube":
        from src.youtube.queue import init_db, create_draft, submit_for_review, list_content, get_content, mark_posted
        from src.youtube.notifier import notify_review_needed
        init_db()

        yt_cmd = getattr(args, "yt_command", None)

        if yt_cmd == "dashboard":
            from config.settings import YOUTUBE_DASHBOARD_HOST, YOUTUBE_DASHBOARD_PORT
            from src.youtube.dashboard.server import run_dashboard
            run_dashboard(host=YOUTUBE_DASHBOARD_HOST, port=YOUTUBE_DASHBOARD_PORT)

        elif yt_cmd == "draft":
            tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
            item = create_draft(
                title=args.title,
                description=args.description,
                video_path=args.video_path,
                video_url=args.video_url,
                thumbnail_path=args.thumbnail_path,
                thumbnail_url=args.thumbnail_url,
                tags=tags,
                privacy_status=args.privacy,
                scheduled_time=args.scheduled,
            )
            console.print(f"[green]Draft created:[/green] {item['id'][:8]}… — {item['title']}")

        elif yt_cmd == "list":
            items = list_content(status=args.status)
            if not items:
                console.print("[yellow]No content found.[/yellow]")
            else:
                from rich.table import Table
                t = Table(show_header=True)
                t.add_column("ID", style="dim", width=10)
                t.add_column("Title")
                t.add_column("Status")
                t.add_column("Scheduled")
                for it in items:
                    t.add_row(
                        it["id"][:8],
                        it["title"],
                        it["status"],
                        (it["scheduled_time"] or "immediate")[:16],
                    )
                console.print(t)

        elif yt_cmd == "submit":
            items = list_content()
            match = next((i for i in items if i["id"].startswith(args.id)), None)
            if not match:
                console.print(f"[red]No item with id prefix '{args.id}'[/red]")
            else:
                item = submit_for_review(match["id"])
                if item and item["status"] == "pending_review":
                    notify_review_needed(item["title"])
                    console.print(f"[green]Submitted for review:[/green] {item['title']}")
                else:
                    console.print("[red]Could not submit — must be in 'draft' status.[/red]")

        elif yt_cmd == "post":
            from src.youtube.poster import post_to_youtube
            items = list_content()
            match = next((i for i in items if i["id"].startswith(args.id)), None)
            if not match:
                console.print(f"[red]No item with id prefix '{args.id}'[/red]")
            elif match["status"] != "approved":
                console.print(f"[red]Item must be 'approved' before posting (current: {match['status']})[/red]")
            else:
                console.print(f"[cyan]Posting:[/cyan] {match['title']}")
                success, video_id, yt_url = post_to_youtube(match)
                if success:
                    mark_posted(match["id"], video_id, yt_url)
                    console.print(f"[green]Posted:[/green] {yt_url}")
                else:
                    console.print(f"[red]Post failed:[/red] {video_id}")

        elif yt_cmd == "auth":
            console.print("[cyan]Starting YouTube OAuth flow…[/cyan]")
            from src.youtube.poster import _post_via_youtube_api
            console.print("[yellow]This will open a browser for authentication.[/yellow]")
            console.print("After auth, your token will be saved to data/youtube_token.pickle")
            try:
                from google_auth_oauthlib.flow import InstalledAppFlow
                import os, pickle
                creds_file = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "config/youtube_client_secret.json")
                token_file = os.getenv("YOUTUBE_TOKEN_FILE", "data/youtube_token.pickle")
                scopes = ["https://www.googleapis.com/auth/youtube.upload"]
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, scopes)
                creds = flow.run_local_server(port=0)
                import pathlib
                pathlib.Path(token_file).parent.mkdir(exist_ok=True)
                with open(token_file, "wb") as f:
                    pickle.dump(creds, f)
                console.print(f"[green]Authenticated! Token saved to {token_file}[/green]")
            except Exception as e:
                console.print(f"[red]Auth failed: {e}[/red]")

        else:
            console.print("[bold]YouTube Queue commands:[/bold]")
            console.print("  [cyan]python main.py youtube dashboard[/cyan]       — open review dashboard (web UI)")
            console.print("  [cyan]python main.py youtube draft --title ...[/cyan] — create a new draft")
            console.print("  [cyan]python main.py youtube list[/cyan]             — list all queued content")
            console.print("  [cyan]python main.py youtube submit <id>[/cyan]      — submit draft for review")
            console.print("  [cyan]python main.py youtube post <id>[/cyan]        — post approved item now")
            console.print("  [cyan]python main.py youtube auth[/cyan]             — authenticate with YouTube OAuth")

    elif args.command == "agents":
        ag_cmd = getattr(args, "ag_command", None)

        if ag_cmd == "start":
            from src.agents.coordinator import build_coordinator
            console.rule("[bold cyan]Auto Content Agents[/bold cyan]")
            c = build_coordinator()
            c.start_all()
            c.run_forever(status_interval=300)

        elif ag_cmd == "status":
            from src.agents.coordinator import build_coordinator
            c = build_coordinator()
            # Don't start — just build and print status of already-running processes
            # (stateless snapshot; for live monitoring run `agents start`)
            console.print("[yellow]Tip: run 'python main.py agents start' to launch agents.[/yellow]")
            console.print("[dim]Static config snapshot:[/dim]")
            from config.settings import (
                CONTENT_AGENT_INTERVAL_MINUTES, YOUTUBE_AUTO_APPROVE,
                YOUTUBE_REVIEW_WINDOW_MINUTES, GIT_AGENT_INTERVAL_MINUTES, GIT_AUTO_PUSH,
            )
            console.print(f"  content-agent interval : {CONTENT_AGENT_INTERVAL_MINUTES} min")
            console.print(f"  auto-approve           : {YOUTUBE_AUTO_APPROVE}")
            console.print(f"  review window          : {YOUTUBE_REVIEW_WINDOW_MINUTES} min")
            console.print(f"  git-agent interval     : {GIT_AGENT_INTERVAL_MINUTES} min")
            console.print(f"  git auto-push          : {GIT_AUTO_PUSH}")

        elif ag_cmd == "generate":
            from src.agents.content_agent import ContentAgent
            from src.youtube.queue import init_db
            from config.settings import NICHES
            import random as _random
            init_db()
            agent = ContentAgent.from_env()
            if args.niche:
                from src.niches.niche_config import NICHE_PROFILES
                if args.niche not in NICHE_PROFILES:
                    console.print(f"[red]Unknown niche '{args.niche}'. Available: {list(NICHE_PROFILES.keys())}[/red]")
                else:
                    agent.niches = [args.niche]
            console.print("[cyan]Running content agent once…[/cyan]")
            agent.tick()

        else:
            console.print("[bold]Agent commands:[/bold]")
            console.print("  [cyan]python main.py agents start[/cyan]              — start all agents (runs forever)")
            console.print("  [cyan]python main.py agents status[/cyan]             — show agent config")
            console.print("  [cyan]python main.py agents generate[/cyan]           — generate one draft now")
            console.print("  [cyan]python main.py agents generate --niche tech[/cyan] — force a niche")

    elif args.command == "history":
        from src.post_logger import get_recent_posts
        posts = get_recent_posts(args.days)
        if not posts:
            console.print(f"[yellow]No posts found in the last {args.days} day(s).[/yellow]")
        else:
            console.print(f"\n[bold]Last {len(posts)} post(s) — {args.days} day window[/bold]\n")
            for p in posts:
                ts       = p.get("timestamp", "")[:16].replace("T", "  ")
                platform = (p.get("platform") or "").ljust(11)
                niche    = (p.get("niche") or "").ljust(11)
                preview  = (p.get("text") or "")[:60].replace("\n", " ")
                console.print(f"[cyan]{ts}[/cyan]  {platform}  {niche}  {preview}…")
                if p.get("image_path"):
                    console.print(f"  [dim]{p['image_path']}[/dim]")
                m = p.get("metrics", {})
                if any(v is not None for v in m.values()):
                    console.print(f"  [green]likes={m['likes']}  comments={m['comments']}  shares={m['shares']}  reach={m['reach']}[/green]")
            console.print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
