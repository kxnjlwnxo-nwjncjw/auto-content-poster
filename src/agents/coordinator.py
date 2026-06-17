"""
Agent Coordinator — starts and monitors all background agents.

Pipeline agents (in execution order):
  1. content-agent      — generates YouTube video drafts via Claude AI
  2. script-agent       — writes full spoken scripts for each draft
  3. higgsfield-agent   — triggers AI video/image generation for submitted items
  4. auto-reviewer      — auto-approves pending content (if YOUTUBE_AUTO_APPROVE=true)
  5. assembly-agent     — concatenates approved assets into final video (ffmpeg)
  6. poster-agent       — posts assembled+approved content to YouTube

Support agents:
  7. git-agent          — commits content/ files and pushes to origin

Usage:
    from src.agents.coordinator import Coordinator
    c = Coordinator()
    c.start_all()
    c.print_status()
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
        """Block forever, printing status every N seconds. Ctrl-C stops cleanly."""
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

            # Restart any dead agent threads
            for agent in self.agents:
                if not agent.is_alive() and agent.status != "stopped":
                    console.print(f"[yellow]Restarting dead agent: {agent.name}[/yellow]")
                    agent.start()


def build_coordinator() -> Coordinator:
    """Create and populate the coordinator with all pipeline agents."""
    from src.agents.content_agent import ContentAgent
    from src.agents.script_agent import ScriptAgent
    from src.agents.higgsfield_agent import HiggsFieldAgent
    from src.agents.auto_reviewer import AutoReviewerAgent
    from src.agents.assembly_agent import AssemblyAgent
    from src.agents.poster_agent import PosterAgent
    from src.agents.git_agent import GitAgent
    from src.youtube.queue import init_db
    from src.higgsfield.generator import ffmpeg_available

    init_db()

    c = Coordinator()

    # Pipeline agents — registered in execution order
    c.register(ContentAgent.from_env())
    c.register(ScriptAgent())
    c.register(HiggsFieldAgent())
    c.register(AutoReviewerAgent())
    c.register(AssemblyAgent())
    c.register(PosterAgent())

    # Support agents
    c.register(GitAgent.from_env())

    if not ffmpeg_available():
        console.print(
            "[yellow]⚠  ffmpeg not found — assembly-agent will be inactive until installed.[/yellow]\n"
            "   Install with: [bold]brew install ffmpeg[/bold]"
        )

    return c
