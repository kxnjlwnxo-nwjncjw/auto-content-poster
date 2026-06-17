"""Flask web dashboard for YouTube content review workflow."""
import os
import threading
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, send_file, abort

from src.youtube import queue
from src.youtube.notifier import notify_review_needed, notify_posted
from src.youtube.poster import post_to_youtube
from src.youtube.auto_poster import start_auto_poster

STATIC_DIR = Path(__file__).parent / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR))
app.json.sort_keys = False


# ─── Static files ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)


@app.route("/thumbnails/<path:rel_path>")
def serve_thumbnail(rel_path: str):
    """Serve local thumbnail files. Only serves paths registered in the DB."""
    allowed = queue.get_thumbnail_paths()
    match = next(
        (p for p in allowed if p.endswith(rel_path) or rel_path in p),
        None,
    )
    if not match or not os.path.isfile(match):
        abort(404)
    return send_file(match)


@app.route("/higgsfield-assets/<content_id>/<path:filename>")
def serve_higgsfield_asset(content_id: str, filename: str):
    """Serve Higgsfield-generated assets (intro, thumbnail, scenes)."""
    from config.settings import HIGGSFIELD_API_KEY
    data_dir = Path(__file__).parent.parent.parent.parent / "data" / "higgsfield"
    asset_path = data_dir / content_id / filename
    # Validate path is within our data dir (path traversal guard)
    try:
        asset_path.resolve().relative_to(data_dir.resolve())
    except ValueError:
        abort(403)
    if not asset_path.is_file():
        abort(404)
    return send_file(str(asset_path))


# ─── REST API ─────────────────────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    return jsonify(queue.get_stats())


@app.route("/api/content", methods=["GET"])
def api_list():
    status = request.args.get("status") or None
    return jsonify(queue.list_content(status=status))


@app.route("/api/content", methods=["POST"])
def api_create():
    data = request.get_json(force=True) or {}
    if not data.get("title", "").strip():
        return jsonify({"error": "title is required"}), 400
    item = queue.create_draft(
        title=data["title"].strip(),
        description=data.get("description", ""),
        thumbnail_path=data.get("thumbnail_path", ""),
        thumbnail_url=data.get("thumbnail_url", ""),
        video_path=data.get("video_path", ""),
        video_url=data.get("video_url", ""),
        tags=data.get("tags") or [],
        category_id=str(data.get("category_id", "22")),
        privacy_status=data.get("privacy_status", "public"),
        scheduled_time=data.get("scheduled_time") or None,
        notes=data.get("notes", ""),
    )
    return jsonify(item), 201


@app.route("/api/content/<content_id>", methods=["GET"])
def api_get(content_id: str):
    item = queue.get_content(content_id)
    if not item:
        return jsonify({"error": "not found"}), 404
    return jsonify(item)


@app.route("/api/content/<content_id>", methods=["PUT"])
def api_update(content_id: str):
    item = queue.get_content(content_id)
    if not item:
        return jsonify({"error": "not found"}), 404
    if item["status"] not in ("draft", "rejected"):
        return jsonify({"error": "can only edit drafts and rejected items"}), 400
    data = request.get_json(force=True) or {}
    if "tags" in data and isinstance(data["tags"], str):
        data["tags"] = [t.strip() for t in data["tags"].split(",") if t.strip()]
    updated = queue.update_draft(content_id, **data)
    return jsonify(updated)


@app.route("/api/content/<content_id>", methods=["DELETE"])
def api_delete(content_id: str):
    deleted = queue.delete_content(content_id)
    if not deleted:
        return jsonify({"error": "not found or not deleteable (only drafts/rejected can be deleted)"}), 404
    return jsonify({"deleted": True})


@app.route("/api/content/<content_id>/submit", methods=["POST"])
def api_submit(content_id: str):
    """Submit draft for review and auto-trigger Higgsfield generation."""
    item = queue.submit_for_review(content_id)
    if not item or item["status"] != "pending_review":
        return jsonify({"error": "not found or not in draft status"}), 400

    # Kick off Higgsfield asset generation in the background
    _trigger_higgsfield_generation(content_id, item["title"])

    notify_review_needed(item["title"])
    return jsonify(item)


@app.route("/api/content/<content_id>/generate-assets", methods=["POST"])
def api_generate_assets(content_id: str):
    """Manually trigger (or re-trigger) Higgsfield asset generation."""
    item = queue.get_content(content_id)
    if not item:
        return jsonify({"error": "not found"}), 404
    if item.get("higgsfield_status") == "generating":
        return jsonify({"error": "generation already in progress"}), 409
    _trigger_higgsfield_generation(content_id, item["title"])
    return jsonify({"ok": True, "higgsfield_status": "generating"})


@app.route("/api/content/<content_id>/approve-asset", methods=["POST"])
def api_approve_asset(content_id: str):
    """
    Approve a specific Higgsfield asset.
    Body: { "asset": "intro" | "thumbnail" | "scenes" }
    """
    data  = request.get_json(force=True) or {}
    asset = data.get("asset", "")
    if asset not in ("intro", "thumbnail", "scenes"):
        return jsonify({"error": "asset must be intro, thumbnail, or scenes"}), 400
    item = queue.approve_asset(content_id, asset)
    if not item:
        return jsonify({"error": "not found"}), 404
    return jsonify(item)


@app.route("/api/content/<content_id>/reject-asset", methods=["POST"])
def api_reject_asset(content_id: str):
    """
    Reject a specific asset and trigger re-generation for just that asset.
    Body: { "asset": "intro" | "thumbnail" | "scenes" }
    """
    data  = request.get_json(force=True) or {}
    asset = data.get("asset", "")
    if asset not in ("intro", "thumbnail", "scenes"):
        return jsonify({"error": "asset must be intro, thumbnail, or scenes"}), 400
    item = queue.reject_asset(content_id, asset)
    if not item:
        return jsonify({"error": "not found"}), 404
    _trigger_single_asset_regeneration(content_id, item["title"], asset)
    return jsonify(item)


@app.route("/api/content/<content_id>/assemble", methods=["POST"])
def api_assemble(content_id: str):
    """
    Assemble intro + scenes (+ optional main video) into a single MP4 via ffmpeg.
    If ffmpeg is unavailable, returns a 422 with instructions.
    On success, sets video_path and marks the item as approved.
    """
    item = queue.get_content(content_id)
    if not item:
        return jsonify({"error": "not found"}), 404

    from src.higgsfield.generator import assemble_video, ffmpeg_available
    if not ffmpeg_available():
        return jsonify({
            "error": "ffmpeg not found",
            "hint": "Install with: brew install ffmpeg — then retry.",
        }), 422

    try:
        assembled_path = assemble_video(
            content_id=content_id,
            intro_path=item.get("intro_path") or None,
            scene_paths=item.get("scenes_paths") or [],
            main_video_path=item.get("video_path") or None,
        )
        updated = queue.set_assembled_video(content_id, assembled_path)
        return jsonify(updated)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/content/<content_id>/approve", methods=["POST"])
def api_approve(content_id: str):
    item = queue.approve_content(content_id)
    if not item or item["status"] != "approved":
        return jsonify({"error": "not found or not in pending_review status"}), 400
    return jsonify(item)


@app.route("/api/content/<content_id>/reject", methods=["POST"])
def api_reject(content_id: str):
    data = request.get_json(force=True) or {}
    reason = str(data.get("reason", "")).strip()
    item = queue.reject_content(content_id, reason)
    if not item or item["status"] != "rejected":
        return jsonify({"error": "not found or not in pending_review status"}), 400
    return jsonify(item)


@app.route("/api/content/<content_id>/reset", methods=["POST"])
def api_reset(content_id: str):
    item = queue.reset_to_draft(content_id)
    if not item or item["status"] != "draft":
        return jsonify({"error": "not found or not in rejected status"}), 400
    return jsonify(item)


@app.route("/api/content/<content_id>/post", methods=["POST"])
def api_post_now(content_id: str):
    item = queue.get_content(content_id)
    if not item:
        return jsonify({"error": "not found"}), 404
    if item["status"] != "approved":
        return jsonify({"error": "content must be approved before posting"}), 400

    success, video_id_or_err, yt_url = post_to_youtube(item)
    if success:
        updated = queue.mark_posted(content_id, video_id_or_err, yt_url)
        notify_posted(item["title"], yt_url)
        return jsonify(updated)
    return jsonify({"error": f"posting failed: {video_id_or_err}"}), 500


# ─── Higgsfield background generation helpers ──────────────────────────────────

def _trigger_higgsfield_generation(content_id: str, title: str) -> None:
    """Spawn a daemon thread to generate all three Higgsfield assets."""
    queue.set_higgsfield_status(content_id, "generating")
    t = threading.Thread(
        target=_run_full_generation,
        args=(content_id, title),
        daemon=True,
        name=f"hf-gen-{content_id[:8]}",
    )
    t.start()


def _run_full_generation(content_id: str, title: str) -> None:
    try:
        from src.higgsfield.generator import generate_all_assets
        assets = generate_all_assets(content_id, title)
        queue.set_higgsfield_assets(
            content_id,
            intro_path=assets["intro_path"],
            thumb_path=assets["thumbnail_path"],
            scene_paths=assets["scenes_paths"],
        )
        notify_review_needed(f"{title} (Higgsfield assets ready)")
    except Exception as exc:
        queue.set_higgsfield_status(content_id, "failed", error=str(exc))


def _trigger_single_asset_regeneration(content_id: str, title: str, asset: str) -> None:
    """Spawn a thread to regenerate one specific asset after rejection."""
    t = threading.Thread(
        target=_run_single_regen,
        args=(content_id, title, asset),
        daemon=True,
        name=f"hf-regen-{content_id[:8]}-{asset}",
    )
    t.start()


def _run_single_regen(content_id: str, title: str, asset: str) -> None:
    from src.higgsfield import generator as gen
    import json
    from datetime import datetime

    try:
        if asset == "intro":
            path = gen.generate_intro(content_id, title)
        elif asset == "thumbnail":
            path = gen.generate_thumbnail(content_id, title)
        elif asset == "scenes":
            paths = gen.generate_scenes(content_id, title)
            # Update scenes_paths in DB, reset approval to None
            from src.youtube.queue import _connect, _row_to_dict
            now = datetime.utcnow().isoformat()
            with _connect() as conn:
                row = conn.execute("SELECT higgsfield_approvals FROM content WHERE id = ?", (content_id,)).fetchone()
                approvals = json.loads((row["higgsfield_approvals"] or "{}") if row else "{}")
                approvals["scenes"] = None
                conn.execute(
                    "UPDATE content SET scenes_paths = ?, higgsfield_approvals = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(paths), json.dumps(approvals), now, content_id),
                )
                conn.commit()
            return

        # For intro / thumbnail: update the path field and reset approval
        col = "intro_path" if asset == "intro" else "thumbnail_path"
        from src.youtube.queue import _connect
        now = datetime.utcnow().isoformat()
        with _connect() as conn:
            row = conn.execute("SELECT higgsfield_approvals FROM content WHERE id = ?", (content_id,)).fetchone()
            approvals = json.loads((row["higgsfield_approvals"] or "{}") if row else "{}")
            approvals[asset] = None
            conn.execute(
                f"UPDATE content SET {col} = ?, higgsfield_approvals = ?, updated_at = ? WHERE id = ?",
                (path, json.dumps(approvals), now, content_id),
            )
            conn.commit()
    except Exception:
        pass  # Regen failures are silent; user can re-reject to retry


# ─── Server runner ────────────────────────────────────────────────────────────

def run_dashboard(host: str = "127.0.0.1", port: int = 8080, with_auto_poster: bool = True) -> None:
    queue.init_db()
    if with_auto_poster:
        start_auto_poster()
    print(f"\n  YouTube Queue dashboard → http://{host}:{port}\n")
    app.run(host=host, port=port, debug=False, use_reloader=False)
