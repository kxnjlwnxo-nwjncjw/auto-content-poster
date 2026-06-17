import json
import textwrap
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

HISTORY_DIR = Path(__file__).parent.parent / "post_history"

# Low-res canvas — scaled up with NEAREST for pixel look
CARD_W, CARD_H = 100, 75
SCALE = 4   # → 400×300 output

PLATFORM_COLORS: dict[str, tuple[int, int, int]] = {
    "twitter":   (29,  161, 242),
    "instagram": (225,  48, 108),
    "facebook":  (24,  119, 242),
    "telegram":  (42,  171, 238),
    "tiktok":    (1,     1,   1),
    "youtube":   (255,   0,   0),
}


def _pixel_card(post_dict: dict) -> Image.Image:
    platform = post_dict.get("platform", "unknown")
    niche    = post_dict.get("niche", "")
    text     = post_dict.get("text", "")

    bg   = PLATFORM_COLORS.get(platform, (60, 60, 60))
    img  = Image.new("RGB", (CARD_W, CARD_H), bg)
    draw = ImageDraw.Draw(img)

    # Header: platform + niche
    header = f"{platform[:9].upper()} · {niche[:9]}"
    draw.text((2, 2), header, fill=(255, 255, 255))
    draw.line([(0, 12), (CARD_W, 12)], fill=(255, 255, 255))

    # Post body — first 200 chars, word-wrapped
    lines = textwrap.wrap(text[:200], width=16)[:5]
    for i, line in enumerate(lines):
        draw.text((2, 15 + i * 9), line, fill=(230, 230, 230))

    # Footer: timestamp
    ts = datetime.now().strftime("%m/%d  %H:%M")
    draw.text((2, CARD_H - 9), ts, fill=(180, 180, 180))

    # Scale up — NEAREST keeps hard pixel edges
    return img.resize((CARD_W * SCALE, CARD_H * SCALE), Image.NEAREST)


def save_post_preview(post_dict: dict) -> str:
    """Render a pixelated thumbnail + JSON sidecar. Returns the PNG path."""
    now     = datetime.now()
    day_dir = HISTORY_DIR / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    stem      = f"{now.strftime('%H-%M-%S')}_{post_dict.get('platform', 'x')}_{post_dict.get('niche', 'x')}"
    img_path  = day_dir / f"{stem}.png"
    meta_path = day_dir / f"{stem}.json"

    _pixel_card(post_dict).save(img_path, "PNG")

    meta = {
        "timestamp": now.isoformat(),
        "platform":  post_dict.get("platform"),
        "niche":     post_dict.get("niche"),
        "topic":     post_dict.get("topic"),
        "text":      post_dict.get("text"),
        "hashtags":  post_dict.get("hashtags", []),
        # fill these in manually or via a future fetch-metrics command
        "metrics": {
            "likes":    None,
            "comments": None,
            "shares":   None,
            "reach":    None,
        },
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    return str(img_path)


def get_recent_posts(days: int = 7) -> list[dict]:
    """Return metadata for posts from the last N days, newest first."""
    if not HISTORY_DIR.exists():
        return []

    cutoff = datetime.now() - timedelta(days=days)
    posts: list[dict] = []

    for day_dir in sorted(HISTORY_DIR.glob("????-??-??"), reverse=True):
        try:
            day_date = datetime.strptime(day_dir.name, "%Y-%m-%d")
        except ValueError:
            continue
        if day_date < cutoff:
            break
        for meta_file in sorted(day_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(meta_file.read_text())
                img  = meta_file.with_suffix(".png")
                data["image_path"] = str(img) if img.exists() else None
                posts.append(data)
            except Exception:
                pass

    return posts
