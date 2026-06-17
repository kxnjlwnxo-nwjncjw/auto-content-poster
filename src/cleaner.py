import time
from pathlib import Path


def clean_logs(days: int = 7) -> int:
    """Remove .log files in the logs/ directory older than `days` days.

    Returns the number of files deleted.
    """
    log_dir = Path(__file__).parent.parent / "logs"
    if not log_dir.exists():
        return 0

    cutoff = time.time() - days * 86400
    removed = 0
    for f in log_dir.glob("*.log"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1
    return removed
