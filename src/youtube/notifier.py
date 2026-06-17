"""macOS system notifications for YouTube queue events."""
import subprocess


def _notify(title: str, message: str, subtitle: str = "YouTube Queue") -> None:
    safe = lambda s: s.replace('"', "'").replace("\\", "\\\\")
    script = (
        f'display notification "{safe(message)}" '
        f'with title "{safe(title)}" '
        f'subtitle "{safe(subtitle)}"'
    )
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    except Exception:
        print(f"[YouTube Queue] {title}: {message}")


def notify_review_needed(content_title: str) -> None:
    _notify(
        title="Review Required",
        message=f'"{content_title}" is waiting for your approval.',
        subtitle="YouTube Queue",
    )


def notify_posted(content_title: str, youtube_url: str) -> None:
    _notify(
        title="Posted to YouTube",
        message=f'"{content_title}" is now live.',
        subtitle=youtube_url or "YouTube Queue",
    )


def notify_post_failed(content_title: str, reason: str) -> None:
    _notify(
        title="Post Failed",
        message=f'"{content_title}": {reason}',
        subtitle="YouTube Queue",
    )
