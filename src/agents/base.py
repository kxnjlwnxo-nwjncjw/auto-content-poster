"""Base class for all background agents."""
from __future__ import annotations
import threading
import time
from datetime import datetime
from typing import Optional
from rich.console import Console

console = Console()


class Agent:
    """
    A named background agent that runs a recurring task on an interval.
    Tracks run count, last run time, last error, and provides clean shutdown.
    """

    name: str = "agent"
    interval_seconds: int = 60

    def __init__(self):
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.runs: int = 0
        self.errors: int = 0
        self.last_run: datetime | None = None
        self.last_error: str = ""
        self.status: str = "idle"

    def tick(self) -> None:
        """Override in subclass — runs once per interval."""
        raise NotImplementedError

    def _loop(self) -> None:
        console.print(f"[dim cyan]{self.name} started (every {self.interval_seconds}s)[/dim cyan]")
        while not self._stop.is_set():
            self.status = "running"
            try:
                self.tick()
                self.runs += 1
            except Exception as exc:
                self.errors += 1
                self.last_error = str(exc)
                console.print(f"[red]{self.name} error: {exc}[/red]")
            finally:
                self.last_run = datetime.utcnow()
                self.status = "sleeping"
            self._stop.wait(self.interval_seconds)
        self.status = "stopped"

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name=self.name
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stat_row(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "runs": self.runs,
            "errors": self.errors,
            "last_run": self.last_run.isoformat() if self.last_run else "never",
            "last_error": self.last_error or "—",
            "alive": self.is_alive(),
        }
