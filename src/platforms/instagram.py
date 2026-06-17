from instagrapi import Client
from config.settings import INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD


def get_client():
    cl = Client()
    cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    return cl


def post(content: dict, image_path: str = None) -> bool:
    try:
        cl = get_client()
        caption = content["text"]
        if image_path:
            cl.photo_upload(image_path, caption)
        else:
            # Instagram requires an image — log a warning
            print("    [Instagram] Skipped: no image provided (Instagram requires an image)")
            return False
        print(f"    [Instagram] Posted: {caption[:60]}...")
        return True
    except Exception as e:
        print(f"    [Instagram] Error: {e}")
        return False
