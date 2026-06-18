"""SQLite-backed content queue for YouTube review workflow."""
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent.parent / "data" / "youtube_queue.db"

VALID_STATUSES = {"draft", "generating", "pending_review", "approved", "rejected", "posted"}

# Per-asset approval states stored in higgsfield_approvals (JSON object)
# e.g. {"intro": null, "thumbnail": null, "scenes": null}
# null = not reviewed, true = approved, false = rejected


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add Higgsfield columns if this is an existing DB without them."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(content)")}
    additions = {
        "higgsfield_status":    "TEXT DEFAULT 'idle'",
        "higgsfield_error":     "TEXT DEFAULT ''",
        "intro_path":           "TEXT DEFAULT ''",
        "scenes_paths":         "TEXT DEFAULT '[]'",
        "higgsfield_approvals": "TEXT DEFAULT '{}'",
        "assembled_video_path": "TEXT DEFAULT ''",
        "voiceover_path":       "TEXT DEFAULT ''",
        "srt_path":             "TEXT DEFAULT ''",
        "reels_path":           "TEXT DEFAULT ''",
    }
    for col, typedef in additions.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE content ADD COLUMN {col} {typedef}")
    conn.commit()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS content (
                id                   TEXT PRIMARY KEY,
                title                TEXT NOT NULL,
                description          TEXT DEFAULT '',
                thumbnail_path       TEXT DEFAULT '',
                thumbnail_url        TEXT DEFAULT '',
                video_path           TEXT DEFAULT '',
                video_url            TEXT DEFAULT '',
                tags                 TEXT DEFAULT '[]',
                category_id          TEXT DEFAULT '22',
                privacy_status       TEXT DEFAULT 'public',
                scheduled_time       TEXT,
                status               TEXT DEFAULT 'draft',
                rejection_reason     TEXT DEFAULT '',
                youtube_video_id     TEXT DEFAULT '',
                youtube_url          TEXT DEFAULT '',
                notes                TEXT DEFAULT '',
                created_at           TEXT NOT NULL,
                updated_at           TEXT NOT NULL,
                submitted_at         TEXT,
                reviewed_at          TEXT,
                posted_at            TEXT,
                higgsfield_status    TEXT DEFAULT 'idle',
                higgsfield_error     TEXT DEFAULT '',
                intro_path           TEXT DEFAULT '',
                scenes_paths         TEXT DEFAULT '[]',
                higgsfield_approvals TEXT DEFAULT '{}',
                assembled_video_path TEXT DEFAULT '',
                voiceover_path       TEXT DEFAULT '',
                srt_path             TEXT DEFAULT '',
                reels_path           TEXT DEFAULT ''
            )
        """)
        _migrate(conn)
        conn.commit()


def _row_to_dict(row) -> Optional[dict]:
    if row is None:
        return None
    d = dict(row)
    for key, default in (("tags", "[]"), ("scenes_paths", "[]"), ("higgsfield_approvals", "{}")):
        try:
            d[key] = json.loads(d.get(key) or default)
        except (json.JSONDecodeError, TypeError):
            d[key] = json.loads(default)
    return d


def create_draft(
    title: str,
    description: str = "",
    thumbnail_path: str = "",
    thumbnail_url: str = "",
    video_path: str = "",
    video_url: str = "",
    tags: Optional[list] = None,
    category_id: str = "22",
    privacy_status: str = "public",
    scheduled_time: Optional[str] = None,
    notes: str = "",
) -> dict:
    now = datetime.utcnow().isoformat()
    content_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO content (
                id, title, description, thumbnail_path, thumbnail_url,
                video_path, video_url, tags, category_id, privacy_status,
                scheduled_time, status, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)
            """,
            (
                content_id, title, description,
                thumbnail_path, thumbnail_url,
                video_path, video_url,
                json.dumps(tags or []),
                category_id, privacy_status,
                scheduled_time, notes, now, now,
            ),
        )
        conn.commit()
    return get_content(content_id)


def get_content(content_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM content WHERE id = ?", (content_id,)
        ).fetchone()
    return _row_to_dict(row)


def list_content(status: Optional[str] = None) -> list[dict]:
    with _connect() as conn:
        if status and status in VALID_STATUSES:
            rows = conn.execute(
                "SELECT * FROM content WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM content ORDER BY created_at DESC"
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_draft(content_id: str, **kwargs) -> Optional[dict]:
    allowed = {
        "title", "description", "thumbnail_path", "thumbnail_url",
        "video_path", "video_url", "tags", "category_id",
        "privacy_status", "scheduled_time", "notes",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_content(content_id)
    if "tags" in updates and isinstance(updates["tags"], list):
        updates["tags"] = json.dumps(updates["tags"])
    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [content_id]
    with _connect() as conn:
        conn.execute(
            f"UPDATE content SET {set_clause} WHERE id = ? AND status IN ('draft', 'rejected')",
            values,
        )
        conn.commit()
    return get_content(content_id)


def reset_to_draft(content_id: str) -> Optional[dict]:
    """Reset a rejected item back to draft so it can be resubmitted."""
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE content
            SET status = 'draft', rejection_reason = '', reviewed_at = NULL, updated_at = ?
            WHERE id = ? AND status = 'rejected'
            """,
            (now, content_id),
        )
        conn.commit()
    return get_content(content_id)


def submit_for_review(content_id: str) -> Optional[dict]:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE content
            SET status = 'pending_review', submitted_at = ?, updated_at = ?
            WHERE id = ? AND status = 'draft'
            """,
            (now, now, content_id),
        )
        conn.commit()
    return get_content(content_id)


def approve_content(content_id: str) -> Optional[dict]:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE content
            SET status = 'approved', reviewed_at = ?, updated_at = ?
            WHERE id = ? AND status = 'pending_review'
            """,
            (now, now, content_id),
        )
        conn.commit()
    return get_content(content_id)


def reject_content(content_id: str, reason: str = "") -> Optional[dict]:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE content
            SET status = 'rejected', rejection_reason = ?, reviewed_at = ?, updated_at = ?
            WHERE id = ? AND status = 'pending_review'
            """,
            (reason, now, now, content_id),
        )
        conn.commit()
    return get_content(content_id)


def mark_posted(
    content_id: str,
    youtube_video_id: str = "",
    youtube_url: str = "",
) -> Optional[dict]:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE content
            SET status = 'posted', youtube_video_id = ?, youtube_url = ?,
                posted_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (youtube_video_id, youtube_url, now, now, content_id),
        )
        conn.commit()
    return get_content(content_id)


def delete_content(content_id: str) -> bool:
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM content WHERE id = ? AND status IN ('draft', 'rejected')",
            (content_id,),
        )
        conn.commit()
    return cursor.rowcount > 0


def get_stats() -> dict:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM content GROUP BY status"
        ).fetchall()
    stats = {s: 0 for s in VALID_STATUSES}
    stats["total"] = 0
    for row in rows:
        key = row["status"]
        if key in stats:
            stats[key] = row["count"]
        stats["total"] += row["count"]
    return stats


def get_due_approved() -> list[dict]:
    """Return approved content whose scheduled_time has passed (or has no schedule)."""
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM content
            WHERE status = 'approved'
              AND (scheduled_time IS NULL OR scheduled_time <= ?)
            ORDER BY scheduled_time ASC NULLS LAST
            """,
            (now,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_thumbnail_paths() -> set[str]:
    """Return all thumbnail_path values in the DB (for safe file serving)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT thumbnail_path FROM content WHERE thumbnail_path != ''"
        ).fetchall()
    return {row["thumbnail_path"] for row in rows}


# ── Higgsfield asset management ───────────────────────────────────────────────

def set_higgsfield_status(content_id: str, status: str, error: str = "") -> None:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE content SET higgsfield_status = ?, higgsfield_error = ?, updated_at = ? WHERE id = ?",
            (status, error, now, content_id),
        )
        conn.commit()


def set_higgsfield_assets(
    content_id:   str,
    intro_path:   str,
    thumb_path:   str,
    scene_paths:  list[str],
) -> Optional[dict]:
    """Store generated asset paths and mark Higgsfield as ready."""
    now = datetime.utcnow().isoformat()
    approvals = json.dumps({"intro": None, "thumbnail": None, "scenes": None})
    with _connect() as conn:
        conn.execute(
            """UPDATE content
               SET higgsfield_status    = 'ready',
                   higgsfield_error     = '',
                   intro_path           = ?,
                   thumbnail_path       = ?,
                   scenes_paths         = ?,
                   higgsfield_approvals = ?,
                   status               = 'pending_review',
                   updated_at           = ?
               WHERE id = ?""",
            (intro_path, thumb_path, json.dumps(scene_paths), approvals, now, content_id),
        )
        conn.commit()
    return get_content(content_id)


def approve_asset(content_id: str, asset: str) -> Optional[dict]:
    """
    Mark a single Higgsfield asset (intro|thumbnail|scenes) as approved.
    asset: 'intro' | 'thumbnail' | 'scenes'
    Returns updated content dict.
    """
    item = get_content(content_id)
    if not item:
        return None
    approvals = item.get("higgsfield_approvals") or {}
    if isinstance(approvals, str):
        approvals = json.loads(approvals)
    approvals[asset] = True
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE content SET higgsfield_approvals = ?, updated_at = ? WHERE id = ?",
            (json.dumps(approvals), now, content_id),
        )
        conn.commit()
    return get_content(content_id)


def reject_asset(content_id: str, asset: str) -> Optional[dict]:
    """Mark a single asset as rejected (triggers re-generation in caller)."""
    item = get_content(content_id)
    if not item:
        return None
    approvals = item.get("higgsfield_approvals") or {}
    if isinstance(approvals, str):
        approvals = json.loads(approvals)
    approvals[asset] = False
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE content SET higgsfield_approvals = ?, updated_at = ? WHERE id = ?",
            (json.dumps(approvals), now, content_id),
        )
        conn.commit()
    return get_content(content_id)


def set_assembled_video(content_id: str, assembled_path: str) -> Optional[dict]:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE content SET assembled_video_path = ?, video_path = ?, updated_at = ? WHERE id = ?",
            (assembled_path, assembled_path, now, content_id),
        )
        conn.commit()
    return get_content(content_id)


def all_assets_approved(content_id: str) -> bool:
    item = get_content(content_id)
    if not item:
        return False
    approvals = item.get("higgsfield_approvals") or {}
    if isinstance(approvals, str):
        approvals = json.loads(approvals)
    return all(approvals.get(k) is True for k in ("intro", "thumbnail", "scenes"))


def get_higgsfield_asset_paths() -> set[str]:
    """Return all Higgsfield asset paths registered in DB (for safe file serving)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT intro_path, scenes_paths FROM content"
        ).fetchall()
    paths: set[str] = set()
    for row in rows:
        if row["intro_path"]:
            paths.add(row["intro_path"])
        try:
            for p in json.loads(row["scenes_paths"] or "[]"):
                if p:
                    paths.add(p)
        except (json.JSONDecodeError, TypeError):
            pass
    return paths
