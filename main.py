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

    # Run the scheduler
    subparsers.add_parser("start", help="Start the posting scheduler")

    # Generate and post once immediately
    p = subparsers.add_parser("post-now", help="Generate and post right now")
    p.add_argument("--niche", default=None, help="Niche to post for (default: random)")

    # Generate content only (preview, no posting)
    p2 = subparsers.add_parser("preview", help="Preview generated content without posting")
    p2.add_argument("--niche", required=True, help="Niche to preview")
    p2.add_argument("--platform", required=True, help="Platform to generate for")

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

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
