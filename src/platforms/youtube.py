"""YouTube platform module — wraps the queue-based review workflow."""
from src.youtube.queue import create_draft, submit_for_review, init_db
from src.youtube.notifier import notify_review_needed


def post(content: dict) -> bool:
    """
    'Post' for YouTube means: create a draft in the review queue and notify.

    Unlike other platforms, YouTube content is never published directly —
    it goes through the review dashboard first. Run:
        python main.py youtube dashboard
    to review and approve queued content.
    """
    try:
        init_db()
        draft = create_draft(
            title=content.get("topic", content.get("niche", "Untitled")),
            description=content.get("text", ""),
            tags=content.get("hashtags", []),
        )
        item = submit_for_review(draft["id"])
        notify_review_needed(item["title"])
        print(f"    [YouTube] Queued for review: {item['title']} (id={item['id'][:8]})")
        return True
    except Exception as exc:
        print(f"    [YouTube] Error queuing content: {exc}")
        return False
