"""
Content Agent — continuously generates YouTube video drafts using Claude AI.

Every CONTENT_AGENT_INTERVAL_MINUTES (default: 60) it picks a random niche,
calls Claude to generate a complete video content package, creates a draft in the
queue, and submits it for review (which triggers Higgsfield asset generation).
"""
from __future__ import annotations
import json
import os
import random
from rich.console import Console
from src.agents.base import Agent
from src.youtube.queue import init_db, create_draft, submit_for_review, list_content

console = Console()

DEDUP_LOOKBACK = 30


def _recent_titles() -> list[str]:
    """Return the last DEDUP_LOOKBACK titles from the queue to avoid duplicates."""
    try:
        all_items = list_content()
        return [i["title"] for i in all_items[-DEDUP_LOOKBACK:] if i.get("title")]
    except Exception:
        return []


def _generate_youtube_content(niche: str, topic: str, profile: dict) -> dict:
    import anthropic
    from config.settings import ANTHROPIC_API_KEY

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    hashtags = " ".join(profile.get("hashtags", []))
    tone = profile.get("tone", "engaging")

    recent = _recent_titles()
    dedup_block = ""
    if recent:
        dedup_block = f"\n\nRecent titles already in queue (DO NOT duplicate or closely repeat these):\n" + "\n".join(f"- {t}" for t in recent[-10:])

    prompt = f"""You are an expert YouTube content creator for the {niche} niche.
Generate a complete YouTube video content package for this topic: {topic}

Tone: {tone}
Relevant hashtags: {hashtags}{dedup_block}

Return ONLY a valid JSON object with these exact keys (no markdown, no explanation):
{{
  "title": "Compelling YouTube title, 55-70 chars, SEO optimized",
  "description": "Full description 250-400 words. Structure: 1-2 sentence hook, what they'll learn, 5-8 timestamp placeholders (00:00 Intro, 01:30 ...), call to action (like+subscribe), hashtags at end.",
  "tags": ["tag1", "tag2", ...],
  "script_hook": "Opening 15-second hook script — 2-3 punchy sentences to grab attention immediately.",
  "thumbnail_prompt": "One sentence visual description for a high-CTR thumbnail image."
}}

tags must be an array of 20 strings mixing broad and specific YouTube SEO terms."""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


class ContentAgent(Agent):
    name = "content-agent"

    def __init__(self, interval_minutes: int = 60, niches: list[str] | None = None):
        super().__init__()
        self.interval_seconds = interval_minutes * 60
        self.niches = niches or []

    def tick(self) -> None:
        from src.niches.niche_config import NICHE_PROFILES
        from config.settings import NICHES

        niches = self.niches or NICHES
        niche = random.choice(niches)
        profile = NICHE_PROFILES.get(niche, {})
        topics = profile.get("topics", ["general content"])
        topic = random.choice(topics)

        console.print(f"[cyan]content-agent:[/cyan] generating {niche} / {topic}")

        try:
            pkg = _generate_youtube_content(niche, topic, profile)
        except Exception as exc:
            raise RuntimeError(f"Claude generation failed: {exc}") from exc

        init_db()
        title = pkg.get("title", topic)
        draft = create_draft(
            title=title,
            description=pkg.get("description", ""),
            tags=pkg.get("tags", []),
            notes=f"script_hook: {pkg.get('script_hook', '')}\nthumbnail_prompt: {pkg.get('thumbnail_prompt', '')}",
            privacy_status=os.getenv("YOUTUBE_DEFAULT_PRIVACY", "public"),
        )

        item = submit_for_review(draft["id"])
        console.print(f"[green]content-agent:[/green] queued '{title}' ({item['id'][:8]})")

        # Signal git agent to commit this new content file
        _save_content_json(item, pkg)

    @staticmethod
    def from_env() -> "ContentAgent":
        interval = int(os.getenv("CONTENT_AGENT_INTERVAL_MINUTES", "60"))
        niches_raw = os.getenv("CONTENT_AGENT_NICHES", "")
        niches = [n.strip() for n in niches_raw.split(",") if n.strip()] if niches_raw else []
        return ContentAgent(interval_minutes=interval, niches=niches)


def _save_content_json(item: dict, pkg: dict) -> None:
    """Write a JSON content file so the git agent can commit it."""
    from pathlib import Path
    from datetime import datetime

    created = item.get("created_at", datetime.utcnow().isoformat())[:10]
    year_month = created[:7]
    slug = item["title"][:40].lower()
    slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-")
    slug = slug[:40]

    out_dir = Path(__file__).parent.parent.parent / "content" / year_month
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{created}-{item['id'][:8]}-{slug}.json"

    payload = {
        "id": item["id"],
        "title": item["title"],
        "niche": next(
            (t for t in item.get("tags", []) if t), "general"
        ),
        "status": item["status"],
        "tags": item["tags"],
        "created_at": item["created_at"],
        "description": item["description"],
        "script_hook": pkg.get("script_hook", ""),
        "thumbnail_prompt": pkg.get("thumbnail_prompt", ""),
    }
    out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    console.print(f"[dim]content-agent: saved {out_file.relative_to(Path.cwd())}[/dim]")
