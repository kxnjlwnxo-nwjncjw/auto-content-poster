import requests
from config.settings import FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN

GRAPH_URL = "https://graph.facebook.com/v19.0"


def post(content: dict) -> bool:
    try:
        url = f"{GRAPH_URL}/{FACEBOOK_PAGE_ID}/feed"
        payload = {
            "message": content["text"],
            "access_token": FACEBOOK_ACCESS_TOKEN,
        }
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print(f"    [Facebook] Posted: {content['text'][:60]}...")
        return True
    except Exception as e:
        print(f"    [Facebook] Error: {e}")
        return False
