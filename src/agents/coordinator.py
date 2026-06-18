"""
Agent Coordinator — starts and monitors all background agents.

Full pipeline (execution order):
  1. content-agent      — generates YouTube video drafts via Claude AI (dedup enabled)
  2. script-agent       — writes full spoken scripts for each draft
  3. higgsfield-agent   — triggers AI video/image generation (3x retry + backoff)
  4. voiceover-agent    — ElevenLabs TTS from script, merges audio into video
  5. auto-reviewer      — auto-approves pending content (if YOUTUBE_AUTO_APPROVE=true)
  6. assembly-agent     — concatenates approved assets into final video (ffmpeg)
  7. caption-agent      — Whisper transcription → SRT → burned subtitles
  8. repurpose-agent    — crops 16:9 → 9:16 Reels/TikTok version (60s max)
  9. poster-agent       — posts at optimal hour based on analytics
  10. analytics-agent   — polls YouTube every 24h for views/likes

Support:
  11. git-agent         — commits content/ files and pushes to origin

Usage:
    from src.agents.coordinator import build_coordinator
    c = build_coordinator()
    c.start_all()
    c.run_forever()
"""
from __future__ import annotations
import time
import signal
import sys
from rich.console import Console
from rich.table import Table
from src.agents.base import Agent

console = Console()


class Coordinator:
    def __init__(self):
        self.agents: list[Agent] = []

    def register(self, agent: Agent) -> None:
        self.agents.append(agent)

    def start_all(self) -> None:
        for agent in self.agents:
            agent.start()
            console.print(f"[bold green]✓[/bold green] {agent.name} started (every {agent.interval_seconds}s)")

    def stop_all(self) -> None:
        for agent in self.agents:
            agent.stop()
        console.print("[yellow]All agents stopped.[/yellow]")

    def print_status(self) -> None:
        t = Table(show_header=True, header_style="bold")
        t.add_column("Agent")
        t.add_column("Status")
        t.add_column("Runs", justify="right")
        t.add_column("Errors", justify="right")
        t.add_column("Last Run")
        t.add_column("Last Error", max_width=40)
        for agent in self.agents:
            s = agent.stat_row()
            status_color = {
                "running": "yellow", "sleeping": "green",
                "idle": "dim", "stopped": "red",
            }.get(s["status"], "white")
            t.add_row(
                s["name"],
                f"[{status_color}]{s['status']}[/{status_color}]",
                str(s["runs"]),
                str(s["errors"]),
                s["last_run"],
                s["last_error"],
            )
        console.print(t)

    def run_forever(self, status_interval: int = 300) -> None:
        def _shutdown(sig, frame):
            console.print("\n[yellow]Shutting down agents…[/yellow]")
            self.stop_all()
            sys.exit(0)

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        console.print("\n[bold cyan]All agents running. Press Ctrl-C to stop.[/bold cyan]\n")
        tick = 0
        while True:
            time.sleep(30)
            tick += 30
            if tick >= status_interval:
                tick = 0
                self.print_status()
            for agent in self.agents:
                if not agent.is_alive() and agent.status != "stopped":
                    console.print(f"[yellow]Restarting dead agent: {agent.name}[/yellow]")
                    agent.start()


def build_coordinator() -> Coordinator:
    """Create and populate the coordinator with all pipeline agents."""
    from src.agents.content_agent import ContentAgent
    from src.agents.script_agent import ScriptAgent
    from src.agents.higgsfield_agent import HiggsFieldAgent
    from src.agents.voiceover_agent import VoiceoverAgent
    from src.agents.auto_reviewer import AutoReviewerAgent
    from src.agents.assembly_agent import AssemblyAgent
    from src.agents.caption_agent import CaptionAgent
    from src.agents.repurpose_agent import RepurposeAgent
    from src.agents.poster_agent import PosterAgent
    from src.agents.analytics_agent import AnalyticsAgent
    from src.agents.git_agent import GitAgent
    from src.youtube.queue import init_db
    from src.higgsfield.generator import ffmpeg_available

    import os

    init_db()
    c = Coordinator()

    # Pipeline agents — in execution order
    c.register(ContentAgent.from_env())
    c.register(ScriptAgent())
    c.register(HiggsFieldAgent())
    c.register(VoiceoverAgent())
    c.register(AutoReviewerAgent())
    c.register(AssemblyAgent())
    c.register(CaptionAgent())
    c.register(RepurposeAgent())
    c.register(PosterAgent())
    c.register(AnalyticsAgent())

    # Support
    c.register(GitAgent.from_env())

    if not ffmpeg_available():
        console.print(
            "[yellow]⚠  ffmpeg not found — assembly, caption, and repurpose agents inactive.[/yellow]\n"
            "   Install: [bold]brew install ffmpeg[/bold]"
        )
    if not os.getenv("ELEVENLABS_API_KEY"):
        console.print("[dim]ℹ  ELEVENLABS_API_KEY not set — voiceover-agent in mock mode[/dim]")

    try:
        import whisper  # type: ignore
    except ImportError:
        console.print("[dim]ℹ  openai-whisper not installed — caption-agent inactive. Run: pip install openai-whisper[/dim]")

    return c
