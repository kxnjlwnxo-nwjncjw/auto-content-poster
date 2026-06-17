"""
Script Agent — generates full spoken video scripts for each content draft.

Every 120s it scans for draft/pending_review items without a script file and
calls Claude to produce: chapter breakdown, full spoken dialogue per chapter,
intro hook, outro, and voiceover style notes.

Scripts are saved to data/scripts/{content_id}.json and can be used as a
teleprompter or fed into a TTS system for automatic voiceover generation.
"""
from __future__ import annotations
import json
from pathlib import Path
from rich.console import Console
from src.agents.base import Agent

console = Console()
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "data" / "scripts"


class ScriptAgent(Agent):
    name = "script-agent"
    interval_seconds = 120

    def tick(self) -> None:
        from src.youtube.queue import list_content, update_draft

        candidates = list_content(status="draft") + list_content(status="pending_review")
        for item in candidates:
            script_file = SCRIPTS_DIR / f"{item['id']}.json"
            if script_file.exists():
                continue
            try:
                script = _generate_script(item)
                SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
                script_file.write_text(json.dumps(script, indent=2, ensure_ascii=False))

                # Append script path to notes so it surfaces in the dashboard
                existing = item.get("notes") or ""
                if "script:" not in existing:
                    update_draft(
                        item["id"],
                        notes=existing + f"\nscript: data/scripts/{item['id']}.json",
                    )
                console.print(
                    f"[green]script-agent:[/green] script ready for '{item['title'][:50]}'"
                )
            except Exception as exc:
                console.print(f"[red]script-agent: failed for {item['id'][:8]}: {exc}[/red]")


def _generate_script(item: dict) -> dict:
    import anthropic
    from config.settings import ANTHROPIC_API_KEY

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    title = item["title"]
    desc = (item.get("description") or "")[:500]
    notes = (item.get("notes") or "")[:300]

    prompt = f"""You are an expert YouTube scriptwriter. Write a complete video script.

Title: {title}
Description: {desc}
Notes: {notes}

Return ONLY a valid JSON object (no markdown fences):
{{
  "intro_hook": "First 15 seconds — spoken word for word, must hook immediately",
  "chapters": [
    {{
      "title": "Chapter name",
      "timestamp": "00:00",
      "script": "Full spoken dialogue for this chapter (150-250 words)"
    }}
  ],
  "outro": "Closing 20 seconds — call to subscribe, like, comment",
  "total_estimated_minutes": 8,
  "voiceover_style": "energetic/calm/educational/conversational",
  "key_talking_points": ["point1", "point2", "point3"]
}}

Write 6-8 chapters. Use natural spoken language, not formal writing."""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())
