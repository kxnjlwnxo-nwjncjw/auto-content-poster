import tweepy
from config.settings import (
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
)


def get_client():
    return tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_SECRET,
    )


def post(content: dict) -> bool:
    try:
        client = get_client()
        client.create_tweet(text=content["text"][:280])
        print(f"    [Twitter] Posted: {content['text'][:60]}...")
        return True
    except Exception as e:
        print(f"    [Twitter] Error: {e}")
        return False
