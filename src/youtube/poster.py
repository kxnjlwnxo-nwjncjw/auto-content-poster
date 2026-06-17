"""Post approved content to YouTube via Composio SDK (with YouTube Data API fallback)."""
import os
from rich.console import Console

console = Console()


def post_to_youtube(content: dict) -> tuple[bool, str, str]:
    """
    Post content to YouTube.

    Returns (success, youtube_video_id_or_error, youtube_url).
    Tries Composio first, falls back to YouTube Data API if COMPOSIO_API_KEY is absent.
    """
    api_key = os.getenv("COMPOSIO_API_KEY")
    if api_key:
        return _post_via_composio(content, api_key)
    return _post_via_youtube_api(content)


def _post_via_composio(content: dict, api_key: str) -> tuple[bool, str, str]:
    try:
        from composio import ComposioToolSet, Action  # type: ignore

        toolset = ComposioToolSet(api_key=api_key)
        params: dict = {
            "title": content["title"],
            "description": content.get("description", ""),
            "tags": content.get("tags") or [],
            "category_id": content.get("category_id", "22"),
            "privacy_status": content.get("privacy_status", "public"),
        }

        # Prefer local file; fall back to URL
        if content.get("video_path"):
            params["video_path"] = content["video_path"]
        elif content.get("video_url"):
            params["video_url"] = content["video_url"]
        else:
            return False, "no video source provided", ""

        # Thumbnail (optional)
        if content.get("thumbnail_path"):
            params["thumbnail_path"] = content["thumbnail_path"]
        elif content.get("thumbnail_url"):
            params["thumbnail_url"] = content["thumbnail_url"]

        result = toolset.execute_action(
            action=Action.YOUTUBE_UPLOAD_VIDEO,
            params=params,
        )
        video_id: str = result.get("data", {}).get("id", "")
        yt_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
        console.print(f"[green]Composio upload success → {yt_url}[/green]")
        return True, video_id, yt_url

    except ImportError:
        console.print("[yellow]composio-core not installed. Falling back to YouTube Data API.[/yellow]")
        return _post_via_youtube_api(content)
    except Exception as exc:
        console.print(f"[red]Composio upload error: {exc}[/red]")
        return False, str(exc), ""


def _post_via_youtube_api(content: dict) -> tuple[bool, str, str]:
    """Direct YouTube Data API v3 upload using OAuth2 credentials."""
    try:
        from googleapiclient.discovery import build  # type: ignore
        from googleapiclient.http import MediaFileUpload  # type: ignore
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore
        import pickle

        scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        creds_file = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "config/youtube_client_secret.json")
        token_file = os.getenv("YOUTUBE_TOKEN_FILE", "data/youtube_token.pickle")

        creds = None
        if os.path.exists(token_file):
            with open(token_file, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(creds_file):
                    msg = (
                        f"YouTube credentials not found at {creds_file}. "
                        "Set COMPOSIO_API_KEY or provide youtube_client_secret.json."
                    )
                    console.print(f"[red]{msg}[/red]")
                    return False, msg, ""
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, scopes)
                creds = flow.run_local_server(port=0)
            with open(token_file, "wb") as f:
                pickle.dump(creds, f)

        youtube = build("youtube", "v3", credentials=creds)

        video_path = content.get("video_path")
        if not video_path:
            return False, "video_path required for direct YouTube API upload", ""

        body = {
            "snippet": {
                "title": content["title"],
                "description": content.get("description", ""),
                "tags": content.get("tags") or [],
                "categoryId": content.get("category_id", "22"),
            },
            "status": {"privacyStatus": content.get("privacy_status", "public")},
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = request.execute()

        video_id = response.get("id", "")
        yt_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
        console.print(f"[green]YouTube API upload success → {yt_url}[/green]")
        return True, video_id, yt_url

    except Exception as exc:
        console.print(f"[red]YouTube API upload error: {exc}[/red]")
        return False, str(exc), ""
