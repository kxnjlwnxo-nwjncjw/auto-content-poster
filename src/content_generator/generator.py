import anthropic
import random
from config.settings import ANTHROPIC_API_KEY
from src.niches.niche_config import NICHE_PROFILES

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


PLATFORM_CONSTRAINTS = {
    "twitter":    {"max_chars": 280,  "image": False, "video": False},
    "instagram":  {"max_chars": 2200, "image": True,  "video": True},
    "facebook":   {"max_chars": 63206,"image": True,  "video": True},
    "tiktok":     {"max_chars": 2200, "image": False, "video": True},
    "telegram":   {"max_chars": 4096, "image": True,  "video": True},
    "youtube":    {"max_chars": 5000, "image": False, "video": True},
}


def generate_post(niche: str, platform: str) -> dict:
    profile = NICHE_PROFILES.get(niche)
    if not profile:
        raise ValueError(f"Unknown niche: {niche}")

    topic = random.choice(profile["topics"])
    constraints = PLATFORM_CONSTRAINTS[platform]
    hashtags = " ".join(profile["hashtags"])

    prompt = f"""You are a social media content creator expert for the {niche} niche.
Create a {profile['post_format']}-style post for {platform.capitalize()} about: {topic}

Rules:
- Tone: {profile['tone']}
- Max characters: {constraints['max_chars']}
- {'Include relevant emojis' if profile['emoji'] else 'No emojis'}
- End with these hashtags (if character limit allows): {hashtags}
- Make it engaging, shareable, and authentic
- Do NOT include any intro like "Here's a post:" — output ONLY the post text

Output ONLY the final post text, nothing else."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    post_text = message.content[0].text.strip()

    return {
        "niche": niche,
        "platform": platform,
        "topic": topic,
        "text": post_text,
        "hashtags": profile["hashtags"],
        "needs_image": constraints["image"],
        "needs_video": constraints["video"],
    }


def generate_all_platforms(niche: str, platforms: list[str]) -> list[dict]:
    posts = []
    for platform in platforms:
        try:
            post = generate_post(niche, platform)
            posts.append(post)
            print(f"  [+] Generated {platform} post for niche '{niche}'")
        except Exception as e:
            print(f"  [!] Failed to generate {platform} post for '{niche}': {e}")
    return posts
