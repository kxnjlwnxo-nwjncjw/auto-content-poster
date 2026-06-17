import schedule
import time
import random
from datetime import datetime
from rich.console import Console
from config.settings import PLATFORMS, NICHES, POST_TIMES
from src.content_generator.generator import generate_all_platforms
from src import platforms

console = Console()

PLATFORM_MODULES = {
    "twitter":   platforms.twitter,
    "instagram": platforms.instagram,
    "facebook":  platforms.facebook,
    "telegram":  platforms.telegram,
}


def run_posting_cycle():
    active_platforms = [p for p, enabled in PLATFORMS.items() if enabled and p in PLATFORM_MODULES]
    niche = random.choice(NICHES)

    console.rule(f"[bold green]Posting cycle — Niche: {niche} — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    posts = generate_all_platforms(niche, active_platforms)

    results = {}
    for post in posts:
        platform = post["platform"]
        module = PLATFORM_MODULES[platform]
        success = module.post(post)
        results[platform] = "OK" if success else "FAIL"
        if success:
            from src.post_logger import save_post_preview
            thumb = save_post_preview(post)
            console.print(f"  [dim]Saved preview → {thumb}[/dim]")

    console.print(f"Results: {results}")


def start_scheduler():
    console.print("[bold cyan]Auto Content Poster started[/bold cyan]")
    console.print(f"Active niches: {NICHES}")
    console.print(f"Post times: {POST_TIMES}")

    for t in POST_TIMES:
        schedule.every().day.at(t).do(run_posting_cycle)

    console.print("Scheduler running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(30)
