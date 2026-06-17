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
