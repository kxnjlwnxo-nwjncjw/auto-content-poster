from dotenv import load_dotenv
import os

load_dotenv()

# Claude AI
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Twitter / X
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# Instagram
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

# Facebook
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")

# TikTok
TIKTOK_SESSION_ID = os.getenv("TIKTOK_SESSION_ID")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

# YouTube
YOUTUBE_CLIENT_SECRET_FILE = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "config/youtube_client_secret.json")
YOUTUBE_TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", "data/youtube_token.pickle")

# Composio (used by YouTube queue poster)
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")

# Higgsfield AI (video/image generation — get at higgsfield.ai/dashboard)
HIGGSFIELD_API_KEY = os.getenv("HIGGSFIELD_API_KEY")
HIGGSFIELD_SCENES_COUNT = int(os.getenv("HIGGSFIELD_SCENES_COUNT", "3"))

# YouTube review dashboard
YOUTUBE_DASHBOARD_HOST = os.getenv("YOUTUBE_DASHBOARD_HOST", "127.0.0.1")
YOUTUBE_DASHBOARD_PORT = int(os.getenv("YOUTUBE_DASHBOARD_PORT", "8080"))

# Posting schedule (24-hour format)
POST_TIMES = ["08:00", "12:00", "17:00", "20:00"]

# Active platforms (set to True to enable)
PLATFORMS = {
    "twitter": True,
    "instagram": True,
    "facebook": True,
    "tiktok": False,
    "telegram": True,
    "youtube": False,
}

# Active niches
NICHES = [
    "fitness",
    "crypto",
    "motivation",
    "tech",
    "food",
]

# ── Multi-agent system ────────────────────────────────────────────────────────

# Content Agent: how often to generate a new YouTube draft (minutes)
CONTENT_AGENT_INTERVAL_MINUTES = int(os.getenv("CONTENT_AGENT_INTERVAL_MINUTES", "60"))

# Comma-separated niches for the content agent (blank = use all NICHES above)
CONTENT_AGENT_NICHES = os.getenv("CONTENT_AGENT_NICHES", "")

# Default YouTube privacy for auto-generated content
YOUTUBE_DEFAULT_PRIVACY = os.getenv("YOUTUBE_DEFAULT_PRIVACY", "public")

# Auto-approve pending content once Higgsfield assets are ready
YOUTUBE_AUTO_APPROVE = os.getenv("YOUTUBE_AUTO_APPROVE", "false").lower() in ("1", "true", "yes")

# Approve content that has been waiting in pending_review for ≥ N minutes (0 = disabled)
YOUTUBE_REVIEW_WINDOW_MINUTES = int(os.getenv("YOUTUBE_REVIEW_WINDOW_MINUTES", "0"))

# Git Agent: how often to commit & push content/ files (minutes)
GIT_AGENT_INTERVAL_MINUTES = int(os.getenv("GIT_AGENT_INTERVAL_MINUTES", "10"))

# Set to false to commit locally but not push
GIT_AUTO_PUSH = os.getenv("GIT_AUTO_PUSH", "true").lower() not in ("0", "false", "no")

# Git branch to push to
GIT_BRANCH = os.getenv("GIT_BRANCH", "main")
