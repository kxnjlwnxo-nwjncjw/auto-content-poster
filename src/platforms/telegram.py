import requests
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

BASE_URL = f"https://api.telegram.org/bot{{token}}"


def post(content: dict) -> bool:
    try:
        url = BASE_URL.format(token=TELEGRAM_BOT_TOKEN) + "/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": content["text"],
            "parse_mode": "HTML",
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"    [Telegram] Posted: {content['text'][:60]}...")
        return True
    except Exception as e:
        print(f"    [Telegram] Error: {e}")
        return False
